"""Webhook dead-letter queue (per subscription) after delivery retries."""

import json
import urllib.error

import pytest

from app.config import Config


@pytest.fixture()
def webhook_upload_root(tmp_path, monkeypatch):
    monkeypatch.setattr(Config, "UPLOAD_FOLDER", str(tmp_path))
    yield tmp_path


def test_dlq_appends_after_post_failure(webhook_upload_root, monkeypatch):
    from app.services import webhook_service

    sub = {
        "id": "subdeadbeef01",
        "url": "http://127.0.0.1:9/nope",
        "events": ["simulation.completed"],
        "secret": "",
    }
    monkeypatch.setattr(
        webhook_service,
        "_load_raw",
        lambda: {"subscriptions": [sub]},
    )

    def boom(*_a, **_k):
        raise urllib.error.URLError("injected failure")

    monkeypatch.setattr(webhook_service, "_post_one", boom)

    def run_sync(cls, *, name, target, args=None, kwargs=None, daemon=True):
        target(*(args or ()), **(kwargs or {}))

    monkeypatch.setattr(
        webhook_service.BackgroundTaskRegistry,
        "start",
        classmethod(run_sync),
    )

    webhook_service.dispatch_event("simulation.completed", {"simulation_id": "sim-x"})

    dlq_dir = webhook_upload_root / "webhooks" / "dlq"
    assert dlq_dir.is_dir()
    files = list(dlq_dir.glob("*.jsonl"))
    assert len(files) == 1
    line = files[0].read_text(encoding="utf-8").strip().splitlines()[-1]
    row = json.loads(line)
    assert row["subscription_id"] == "subdeadbeef01"
    assert row["url"] == sub["url"]
    assert "injected failure" in row["error"]
    assert row["envelope"]["event"] == "simulation.completed"
