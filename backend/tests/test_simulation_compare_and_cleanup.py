"""Tests for simulation compare and background task cleanup."""

import atexit
import signal
import threading

import pytest

from app.api.simulation import management as simulation_management
from app.utils.background_tasks import BackgroundTaskRegistry


@pytest.fixture()
def app_client():
    from app import create_app

    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


@pytest.fixture(autouse=True)
def reset_background_registry(monkeypatch):
    monkeypatch.setattr(BackgroundTaskRegistry, "_threads", {}, raising=False)
    monkeypatch.setattr(BackgroundTaskRegistry, "_cleanup_registered", False, raising=False)
    monkeypatch.setattr(BackgroundTaskRegistry, "_cleanup_done", False, raising=False)
    yield


def test_compare_simulations_requires_both_ids(app_client):
    res = app_client.post("/api/simulation/compare", json={})
    assert res.status_code == 400
    data = res.get_json()
    assert data["success"] is False


def test_compare_simulations_not_found(monkeypatch, app_client):
    def fake_payload(simulation_id: str):
        if simulation_id == "sim_a":
            return {
                "simulation": {"simulation_id": "sim_a", "entities_count": 1, "profiles_count": 2},
                "run_state": {"current_round": 1},
                "timeline": [],
                "timeline_tail": [],
                "top_agents": [],
                "posts": {"twitter": {"total": 0, "posts": []}, "reddit": {"total": 0, "posts": []}},
            }
        raise FileNotFoundError(f"Simulation not found: {simulation_id}")

    monkeypatch.setattr(simulation_management, "_simulation_compare_payload", fake_payload)

    res = app_client.post(
        "/api/simulation/compare",
        json={"simulation_id_a": "sim_a", "simulation_id_b": "sim_missing"},
    )
    assert res.status_code == 404
    data = res.get_json()
    assert data["success"] is False


def test_compare_simulations_success(monkeypatch, app_client):
    payload_a = {
        "simulation": {"simulation_id": "sim_a", "entities_count": 10, "profiles_count": 4},
        "run_state": {"current_round": 2},
        "timeline": [{"round_num": 1}, {"round_num": 2}],
        "timeline_tail": [{"round_num": 1}, {"round_num": 2}],
        "top_agents": [{"agent_id": 1, "name": "A"}],
        "posts": {
            "twitter": {"total": 3, "posts": [{"id": 1}]},
            "reddit": {"total": 1, "posts": [{"id": 9}]},
        },
    }
    payload_b = {
        "simulation": {"simulation_id": "sim_b", "entities_count": 13, "profiles_count": 6},
        "run_state": {"current_round": 5},
        "timeline": [{"round_num": 1}, {"round_num": 2}, {"round_num": 3}],
        "timeline_tail": [{"round_num": 2}, {"round_num": 3}],
        "top_agents": [{"agent_id": 2, "name": "B"}],
        "posts": {
            "twitter": {"total": 5, "posts": [{"id": 2}]},
            "reddit": {"total": 4, "posts": [{"id": 10}]},
        },
    }

    monkeypatch.setattr(
        simulation_management,
        "_simulation_compare_payload",
        lambda simulation_id: payload_a if simulation_id == "sim_a" else payload_b,
    )

    res = app_client.post(
        "/api/simulation/compare",
        json={"simulation_id_a": "sim_a", "simulation_id_b": "sim_b"},
    )
    assert res.status_code == 200

    data = res.get_json()["data"]
    assert data["delta"] == {
        "entities_count": 3,
        "profiles_count": 2,
        "current_round": 3,
        "total_posts_twitter": 2,
        "total_posts_reddit": 3,
    }
    assert data["simulation_a"]["simulation"]["simulation_id"] == "sim_a"
    assert data["simulation_b"]["simulation"]["simulation_id"] == "sim_b"


def test_background_task_registry_tracks_and_joins_threads():
    started = threading.Event()
    release = threading.Event()

    def worker():
        started.set()
        release.wait(1)

    thread = BackgroundTaskRegistry.start(name="test-task", target=worker)
    assert started.wait(1)
    assert thread.is_alive()

    release.set()
    BackgroundTaskRegistry.join_all(timeout_per_thread=1.0)

    assert not thread.is_alive()
    assert BackgroundTaskRegistry._threads == {}


def test_register_cleanup_skips_debug_parent(monkeypatch):
    calls = []
    monkeypatch.setenv("FLASK_DEBUG", "1")
    monkeypatch.delenv("WERKZEUG_RUN_MAIN", raising=False)
    monkeypatch.setattr(atexit, "register", lambda fn: calls.append(fn))
    monkeypatch.setattr(signal, "signal", lambda *args, **kwargs: calls.append(args))

    BackgroundTaskRegistry.register_cleanup()

    assert calls == []
    assert BackgroundTaskRegistry._cleanup_registered is True


def test_register_cleanup_installs_handlers(monkeypatch):
    atexit_calls = []
    signal_calls = []
    monkeypatch.delenv("FLASK_DEBUG", raising=False)
    monkeypatch.delenv("WERKZEUG_RUN_MAIN", raising=False)
    monkeypatch.setattr(atexit, "register", lambda fn: atexit_calls.append(fn))
    monkeypatch.setattr(signal, "signal", lambda sig, handler: signal_calls.append(sig))

    BackgroundTaskRegistry.register_cleanup()

    assert len(atexit_calls) == 1
    assert signal.SIGTERM in signal_calls
    assert signal.SIGINT in signal_calls
