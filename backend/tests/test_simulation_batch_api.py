"""Batch simulation create API — create_simulation return value handling."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


@pytest.fixture()
def batch_client(monkeypatch, tmp_path):
    monkeypatch.setattr("app.config.Config.UPLOAD_FOLDER", str(tmp_path))

    from app import create_app

    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c, monkeypatch


def _post(batch_client, items):
    client, _ = batch_client
    return client.post(
        "/api/simulation/batch/create",
        json={"items": items},
    )


def test_batch_rejects_none_state_from_create_simulation(batch_client):
    _, monkeypatch = batch_client

    monkeypatch.setattr(
        "app.api.simulation.batch.ProjectManager.get_project",
        lambda pid: SimpleNamespace(graph_id="g1", project_id=pid),
    )

    mock_session = MagicMock()
    mock_session.create_simulation.return_value = None
    mock_session.state = SimpleNamespace(session_id="wb_sess")

    def _fake_open(cls, **kwargs):
        return mock_session

    monkeypatch.setattr(
        "app.api.simulation.batch.WorkbenchSession.open",
        classmethod(_fake_open),
    )

    res = _post(batch_client, [{"project_id": "p1"}])
    assert res.status_code == 200
    body = res.get_json()
    assert body["success"] is False
    assert body["summary"] == {"total": 1, "succeeded": 0, "failed": 1}
    r0 = body["data"]["results"][0]
    assert r0["success"] is False
    assert "to_dict" in r0["error"].lower()
    mock_session.create_simulation.assert_called_once()


def test_batch_rejects_state_without_callable_to_dict(batch_client):
    _, monkeypatch = batch_client

    monkeypatch.setattr(
        "app.api.simulation.batch.ProjectManager.get_project",
        lambda pid: SimpleNamespace(graph_id="g1", project_id=pid),
    )

    mock_session = MagicMock()
    mock_session.create_simulation.return_value = object()
    mock_session.state = SimpleNamespace(session_id="wb_sess")

    monkeypatch.setattr(
        "app.api.simulation.batch.WorkbenchSession.open",
        classmethod(lambda cls, **kwargs: mock_session),
    )

    res = _post(batch_client, [{"project_id": "p1"}])
    body = res.get_json()
    assert body["success"] is False
    assert body["summary"] == {"total": 1, "succeeded": 0, "failed": 1}
    r0 = body["data"]["results"][0]
    assert r0["success"] is False
    assert "to_dict" in r0["error"].lower()


def test_batch_rejects_empty_workbench_session_id(batch_client):
    _, monkeypatch = batch_client

    monkeypatch.setattr(
        "app.api.simulation.batch.ProjectManager.get_project",
        lambda pid: SimpleNamespace(graph_id="g1", project_id=pid),
    )

    good_state = MagicMock()
    good_state.to_dict.return_value = {"simulation_id": "sim1"}

    mock_session = MagicMock()
    mock_session.create_simulation.return_value = good_state
    mock_session.state = SimpleNamespace(session_id="  ")

    monkeypatch.setattr(
        "app.api.simulation.batch.WorkbenchSession.open",
        classmethod(lambda cls, **kwargs: mock_session),
    )

    res = _post(batch_client, [{"project_id": "p1"}])
    body = res.get_json()
    assert body["success"] is False
    assert body["summary"] == {"total": 1, "succeeded": 0, "failed": 1}
    r0 = body["data"]["results"][0]
    assert r0["success"] is False
    assert "session_id" in r0["error"].lower()


def test_batch_item_exception_response_is_generic(batch_client):
    _, monkeypatch = batch_client

    monkeypatch.setattr(
        "app.api.simulation.batch.ProjectManager.get_project",
        lambda pid: SimpleNamespace(graph_id="g1", project_id=pid),
    )

    def _boom(cls, **kwargs):
        raise RuntimeError("secret-db-connection-string")

    monkeypatch.setattr(
        "app.api.simulation.batch.WorkbenchSession.open",
        classmethod(_boom),
    )

    res = _post(batch_client, [{"project_id": "p1"}])
    assert res.status_code == 200
    body = res.get_json()
    assert body["success"] is False
    assert body["summary"] == {"total": 1, "succeeded": 0, "failed": 1}
    r0 = body["data"]["results"][0]
    assert r0["success"] is False
    assert r0["error"] == "Internal error processing item"
    assert "secret" not in r0["error"].lower()


def test_batch_summary_all_succeed(batch_client):
    _, monkeypatch = batch_client

    monkeypatch.setattr(
        "app.api.simulation.batch.ProjectManager.get_project",
        lambda pid: SimpleNamespace(graph_id="g1", project_id=pid),
    )

    good_state = MagicMock()
    good_state.to_dict.return_value = {"simulation_id": "sim1"}

    mock_session = MagicMock()
    mock_session.create_simulation.return_value = good_state
    mock_session.state = SimpleNamespace(session_id="wb_sess")

    monkeypatch.setattr(
        "app.api.simulation.batch.WorkbenchSession.open",
        classmethod(lambda cls, **kwargs: mock_session),
    )

    res = _post(
        batch_client,
        [
            {"project_id": "p1"},
            {"project_id": "p2"},
        ],
    )
    body = res.get_json()
    assert body["success"] is True
    assert body["summary"] == {"total": 2, "succeeded": 2, "failed": 0}
    assert len(body["data"]["results"]) == 2


def test_batch_summary_partial_success(batch_client):
    _, monkeypatch = batch_client

    monkeypatch.setattr(
        "app.api.simulation.batch.ProjectManager.get_project",
        lambda pid: SimpleNamespace(graph_id="g1", project_id=pid),
    )

    good_state = MagicMock()
    good_state.to_dict.return_value = {"simulation_id": "sim1"}

    mock_session = MagicMock()
    mock_session.create_simulation.return_value = good_state
    mock_session.state = SimpleNamespace(session_id="wb_sess")

    monkeypatch.setattr(
        "app.api.simulation.batch.WorkbenchSession.open",
        classmethod(lambda cls, **kwargs: mock_session),
    )

    res = _post(
        batch_client,
        [
            {},
            {"project_id": "p1"},
        ],
    )
    body = res.get_json()
    assert body["success"] is True
    assert body["summary"] == {"total": 2, "succeeded": 1, "failed": 1}
    assert body["data"]["results"][0]["success"] is False
    assert body["data"]["results"][1]["success"] is True
