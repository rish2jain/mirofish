"""Tests for the simulation comparison endpoint."""

import pytest


@pytest.fixture()
def app_client():
    from app import create_app

    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


class _FakeSimulation:
    def __init__(self, simulation_id: str):
        self.simulation_id = simulation_id

    def to_dict(self):
        return {
            "simulation_id": self.simulation_id,
            "status": "completed",
            "profiles_count": 12,
            "entities_count": 34,
        }


class _FakeRunState:
    def __init__(self, current_round: int):
        self.current_round = current_round

    def to_dict(self):
        return {
            "simulation_id": "unused",
            "current_round": self.current_round,
            "runner_status": "completed",
        }


def test_compare_simulations_requires_both_ids(app_client):
    res = app_client.post("/api/simulation/compare", json={})
    assert res.status_code == 400
    data = res.get_json()
    assert data["success"] is False


def test_compare_simulations_not_found(app_client):
    res = app_client.post(
        "/api/simulation/compare",
        json={"simulation_id_a": "sim_missing_a", "simulation_id_b": "sim_missing_b"},
    )
    assert res.status_code == 404


def test_compare_simulations_success(monkeypatch, app_client):
    from app.api.simulation import management

    def fake_get_simulation(self, simulation_id):
        if simulation_id in {"sim_a", "sim_b"}:
            return _FakeSimulation(simulation_id)
        return None

    def fake_get_run_state(sid):
        return _FakeRunState(3 if sid == "sim_a" else 7)

    def fake_get_timeline(simulation_id):
        return [
            {"round_num": 1, "total_actions": 5, "active_agents_count": 2},
            {"round_num": 2, "total_actions": 8, "active_agents_count": 3},
        ]

    def fake_get_agent_stats(sid):
        return [
            {"agent_id": 1, "agent_name": f"{sid}-agent", "total_actions": 11},
            {"agent_id": 2, "agent_name": f"{sid}-agent-2", "total_actions": 4},
        ]

    monkeypatch.setattr(management.SimulationManager, "get_simulation", fake_get_simulation, raising=False)
    monkeypatch.setattr(management.SimulationRunner, "get_run_state", fake_get_run_state)
    monkeypatch.setattr(management.SimulationRunner, "get_timeline", fake_get_timeline)
    monkeypatch.setattr(management.SimulationRunner, "get_agent_stats", fake_get_agent_stats)
    monkeypatch.setattr(
        management,
        "_recent_posts_summary",
        lambda simulation_id, platform, limit=5: {
            "platform": platform,
            "total": 4 if simulation_id == "sim_b" else 1,
            "posts": [{"id": f"{simulation_id}-{platform}-1", "content": "post"}],
        },
    )

    res = app_client.post(
        "/api/simulation/compare",
        json={"simulation_id_a": "sim_a", "simulation_id_b": "sim_b"},
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["data"]["delta"]["current_round"] == 4
    assert data["data"]["delta"]["total_posts_twitter"] == 3
    assert data["data"]["simulation_a"]["simulation"]["simulation_id"] == "sim_a"
    assert data["data"]["simulation_b"]["simulation"]["simulation_id"] == "sim_b"
