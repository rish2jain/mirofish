"""Tests for Phase 3–5 API additions: compare endpoints, config validate, simulation SSE."""

import json
from datetime import datetime

import pytest

from app.config import Config
from app.core.task_manager import Task, TaskStatus
from app.services.report_models import Report, ReportStatus
from app.services.report_manager import ReportManager


@pytest.fixture()
def app_client():
    from app import create_app

    app = create_app()
    app.config["TESTING"] = True
    with app.test_client() as c:
        yield c


def test_compare_reports_requires_both_ids(app_client):
    res = app_client.post("/api/report/compare", json={})
    assert res.status_code == 400
    data = res.get_json()
    assert data.get("success") is False


def test_compare_reports_not_found(app_client):
    res = app_client.post(
        "/api/report/compare",
        json={"report_id_a": "report_nonexistent_a", "report_id_b": "report_nonexistent_b"},
    )
    assert res.status_code == 404


def test_compare_reports_success(monkeypatch, app_client):
    ra = Report(
        report_id="report_cmp_a",
        simulation_id="sim_a",
        graph_id="g1",
        simulation_requirement="r",
        status=ReportStatus.COMPLETED,
        markdown_content="# Report A\n\nHello",
        created_at="t1",
    )
    rb = Report(
        report_id="report_cmp_b",
        simulation_id="sim_b",
        graph_id="g1",
        simulation_requirement="r",
        status=ReportStatus.COMPLETED,
        markdown_content="# Report B\n\nWorld",
        created_at="t2",
    )

    def fake_get(cls, report_id: str):
        if report_id == ra.report_id:
            return ra
        if report_id == rb.report_id:
            return rb
        return None

    monkeypatch.setattr(ReportManager, "get_report", classmethod(fake_get))
    monkeypatch.setattr(
        ReportManager,
        "get_generated_sections",
        classmethod(lambda cls, report_id: None),
    )

    res = app_client.post(
        "/api/report/compare",
        json={"report_id_a": ra.report_id, "report_id_b": rb.report_id},
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["data"]["report_a"]["markdown_content"].startswith("# Report A")
    assert data["data"]["report_b"]["markdown_content"].startswith("# Report B")


class _FakeSimulationState:
    def __init__(self, simulation_id: str, *, entities_count: int, profiles_count: int, status: str = "ready"):
        self.simulation_id = simulation_id
        self.entities_count = entities_count
        self.profiles_count = profiles_count
        self.status = status

    def to_dict(self):
        return {
            "simulation_id": self.simulation_id,
            "entities_count": self.entities_count,
            "profiles_count": self.profiles_count,
            "status": self.status,
        }


def test_compare_simulations_requires_both_ids(app_client):
    res = app_client.post("/api/simulation/compare", json={})
    assert res.status_code == 400
    data = res.get_json()
    assert data.get("success") is False


def test_compare_simulations_not_found(monkeypatch, app_client):
    monkeypatch.setattr(
        "app.api.simulation.management.SimulationManager.get_simulation",
        lambda self, simulation_id: None,
    )

    res = app_client.post(
        "/api/simulation/compare",
        json={"simulation_id_a": "sim_missing_a", "simulation_id_b": "sim_missing_b"},
    )
    assert res.status_code == 404


def test_compare_simulations_success(monkeypatch, app_client):
    def fake_get_simulation(self, simulation_id):
        if simulation_id == "sim_a":
            return _FakeSimulationState("sim_a", entities_count=3, profiles_count=8)
        if simulation_id == "sim_b":
            return _FakeSimulationState("sim_b", entities_count=7, profiles_count=13)
        return None

    monkeypatch.setattr(
        "app.api.simulation.management.SimulationManager.get_simulation",
        fake_get_simulation,
    )
    monkeypatch.setattr(
        "app.api.simulation.management.SimulationRunner.get_run_state",
        lambda simulation_id: type(
            "RunState",
            (),
            {
                "to_dict": lambda self: {
                    "simulation_id": simulation_id,
                    "runner_status": "completed" if simulation_id == "sim_b" else "running",
                    "current_round": 5 if simulation_id == "sim_b" else 2,
                    "total_rounds": 6,
                    "twitter_actions_count": 0,
                    "reddit_actions_count": 0,
                    "total_actions_count": 0,
                }
            },
        )(),
    )
    monkeypatch.setattr(
        "app.api.simulation.management.SimulationRunner.get_timeline",
        lambda simulation_id: [{"round_num": 1, "total_actions": 4, "active_agents_count": 2}],
    )
    monkeypatch.setattr(
        "app.api.simulation.management.SimulationRunner.get_agent_stats",
        lambda simulation_id: [{"agent_id": f"{simulation_id}-agent", "agent_name": "Agent", "total_actions": 4}],
    )
    monkeypatch.setattr(
        "app.api.simulation.management._recent_posts_summary",
        lambda simulation_id, platform, limit=5: {
            "platform": platform,
            "total": 9 if simulation_id == "sim_b" else 4,
            "posts": [{"id": f"{simulation_id}-{platform}-1", "content": f"{simulation_id} {platform} post"}],
        },
    )

    res = app_client.post(
        "/api/simulation/compare",
        json={"simulation_id_a": "sim_a", "simulation_id_b": "sim_b"},
    )
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert data["data"]["simulation_a"]["simulation"]["simulation_id"] == "sim_a"
    assert data["data"]["simulation_b"]["simulation"]["simulation_id"] == "sim_b"
    assert data["data"]["delta"]["entities_count"] == 4
    assert data["data"]["delta"]["profiles_count"] == 5
    assert data["data"]["delta"]["current_round"] == 3
    assert data["data"]["delta"]["total_posts_twitter"] == 5
    assert data["data"]["delta"]["total_posts_reddit"] == 5


def test_config_validate_rejects_invalid_graph_backend(monkeypatch):
    monkeypatch.setattr(Config, "LLM_API_KEY", "sk-test", raising=False)
    monkeypatch.setattr(Config, "GRAPH_BACKEND", "not-a-backend", raising=False)
    errors = Config.validate(llm_backend="openai")
    assert any("GRAPH_BACKEND" in e for e in errors)


class _FakeRunState:
    def __init__(self, runner_status="completed"):
        self._runner_status = runner_status

    def to_dict(self):
        return {
            "simulation_id": "sim_sse_1",
            "runner_status": self._runner_status,
            "current_round": 3,
            "total_rounds": 3,
            "twitter_actions_count": 0,
            "reddit_actions_count": 0,
            "total_actions_count": 0,
        }


def test_stream_run_status_rejects_unsafe_id(app_client):
    res = app_client.get("/api/simulation/bad!id/run-status/stream")
    assert res.status_code == 400


def test_stream_run_status_returns_sse(monkeypatch, app_client):
    monkeypatch.setattr(
        "app.api.simulation.run_control.SimulationRunner.get_run_state",
        lambda sid: _FakeRunState("completed"),
    )
    res = app_client.get("/api/simulation/sim_sse_1/run-status/stream")
    assert res.status_code == 200
    assert "text/event-stream" in (res.headers.get("Content-Type") or "")
    text = res.get_data(as_text=True)
    assert "completed" in text
    payload = text.split("data: ", 1)[1].strip().split("\n")[0]
    obj = json.loads(payload)
    assert obj["success"] is True
    assert obj["data"]["runner_status"] == "completed"


def test_graph_task_sse_rejects_unsafe_id(app_client):
    res = app_client.get("/api/graph/task/bad!id/sse")
    assert res.status_code == 400


def test_graph_task_get_rejects_unsafe_id(app_client):
    res = app_client.get("/api/graph/task/bad!id")
    assert res.status_code == 400


def test_graph_task_sse_not_found(app_client):
    res = app_client.get("/api/graph/task/00000000-0000-0000-0000-000000000099/sse")
    assert res.status_code == 200
    assert "text/event-stream" in (res.headers.get("Content-Type") or "")
    text = res.get_data(as_text=True)
    payload = text.split("data: ", 1)[1].strip().split("\n")[0]
    obj = json.loads(payload)
    assert obj["success"] is False


def test_graph_task_sse_streams_completed(monkeypatch, app_client):
    now = datetime.now()
    done = Task(
        task_id="tid-sse-graph-1",
        task_type="graph_build",
        status=TaskStatus.COMPLETED,
        created_at=now,
        updated_at=now,
        progress=100,
        message="done",
    )

    def fake_get_task(self, tid):
        if tid == done.task_id:
            return done
        return None

    monkeypatch.setattr("app.api.graph.TaskManager.get_task", fake_get_task)

    res = app_client.get(f"/api/graph/task/{done.task_id}/sse")
    assert res.status_code == 200
    assert "text/event-stream" in (res.headers.get("Content-Type") or "")
    text = res.get_data(as_text=True)
    assert "completed" in text
    payload = text.split("data: ", 1)[1].strip().split("\n")[0]
    obj = json.loads(payload)
    assert obj["success"] is True
    assert obj["data"]["status"] == "completed"
    assert obj["data"]["task_id"] == done.task_id
