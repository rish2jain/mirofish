"""Interview read-only routes: GET query params and POST body fallback."""

import pytest


@pytest.fixture()
def app_client():
    from app import create_app

    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_interview_history_get_uses_query_params(app_client, monkeypatch):
    seen = {}

    def capture(simulation_id, platform=None, agent_id=None, limit=100):
        seen["simulation_id"] = simulation_id
        seen["platform"] = platform
        seen["agent_id"] = agent_id
        seen["limit"] = limit
        return []

    monkeypatch.setattr(
        "app.api.simulation.interview.SimulationRunner.get_interview_history",
        capture,
    )

    res = app_client.get(
        "/api/simulation/interview/history",
        query_string={
            "simulation_id": "sim_x",
            "platform": "reddit",
            "agent_id": "3",
            "limit": "25",
        },
    )
    assert res.status_code == 200
    assert seen == {
        "simulation_id": "sim_x",
        "platform": "reddit",
        "agent_id": 3,
        "limit": 25,
    }


def test_interview_history_post_body_fallback_when_no_query(app_client, monkeypatch):
    seen = {}

    def capture(simulation_id, platform=None, agent_id=None, limit=100):
        seen["simulation_id"] = simulation_id
        seen["limit"] = limit
        return []

    monkeypatch.setattr(
        "app.api.simulation.interview.SimulationRunner.get_interview_history",
        capture,
    )

    res = app_client.post(
        "/api/simulation/interview/history",
        json={"simulation_id": "sim_legacy", "limit": 50},
        content_type="application/json",
    )
    assert res.status_code == 200
    assert seen["simulation_id"] == "sim_legacy"
    assert seen["limit"] == 50


def test_env_status_get_query_param(app_client, monkeypatch):
    monkeypatch.setattr(
        "app.api.simulation.interview.SimulationRunner.check_env_alive",
        lambda sid: sid == "sim_ok",
    )
    monkeypatch.setattr(
        "app.api.simulation.interview.SimulationRunner.get_env_status_detail",
        lambda sid: {"twitter_available": True, "reddit_available": False},
    )

    res = app_client.get(
        "/api/simulation/env-status",
        query_string={"simulation_id": "sim_ok"},
    )
    assert res.status_code == 200
    body = res.get_json()
    assert body["success"] is True
    assert body["data"]["env_alive"] is True


def test_env_status_post_json_fallback(app_client, monkeypatch):
    monkeypatch.setattr(
        "app.api.simulation.interview.SimulationRunner.check_env_alive",
        lambda sid: True,
    )
    monkeypatch.setattr(
        "app.api.simulation.interview.SimulationRunner.get_env_status_detail",
        lambda sid: {"twitter_available": False, "reddit_available": True},
    )

    res = app_client.post(
        "/api/simulation/env-status",
        json={"simulation_id": "sim_p"},
        content_type="application/json",
    )
    assert res.status_code == 200
    assert res.get_json()["data"]["simulation_id"] == "sim_p"
