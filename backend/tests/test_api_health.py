"""Lightweight API smoke tests (no LLM, no uploads)."""

import pytest


@pytest.fixture()
def app_client():
    from app import create_app

    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_health_returns_ok(app_client):
    res = app_client.get("/health")
    assert res.status_code == 200
    data = res.get_json()
    assert data is not None
    assert data.get("status") == "ok"


def test_templates_list_ok(app_client):
    res = app_client.get("/api/templates/")
    assert res.status_code == 200
    body = res.get_json()
    assert body.get("success") is True
    assert isinstance(body.get("data"), list)
