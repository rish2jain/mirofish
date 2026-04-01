"""SimulationRunner platform completion helper."""

from pathlib import Path

import pytest

from app.services.simulation_runner import SimulationRunState, SimulationRunner


@pytest.fixture()
def run_state_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(SimulationRunner, "RUN_STATE_DIR", str(tmp_path))
    yield tmp_path


def test_check_all_platforms_completed_requires_each_enabled_done(run_state_dir):
    sim_id = "sim_platform_test"
    base = Path(run_state_dir) / sim_id
    (base / "twitter").mkdir(parents=True)
    (base / "reddit").mkdir(parents=True)
    (base / "twitter" / "actions.jsonl").write_text("", encoding="utf-8")
    (base / "reddit" / "actions.jsonl").write_text("", encoding="utf-8")

    state = SimulationRunState(simulation_id=sim_id)
    state.twitter_completed = True
    state.reddit_completed = False
    assert SimulationRunner._check_all_platforms_completed(state) is False

    state.reddit_completed = True
    assert SimulationRunner._check_all_platforms_completed(state) is True


def test_check_all_platforms_single_twitter_only(run_state_dir):
    sim_id = "sim_twitter_only"
    base = Path(run_state_dir) / sim_id
    (base / "twitter").mkdir(parents=True)
    (base / "twitter" / "actions.jsonl").write_text("", encoding="utf-8")

    state = SimulationRunState(simulation_id=sim_id)
    state.twitter_completed = True
    assert SimulationRunner._check_all_platforms_completed(state) is True
