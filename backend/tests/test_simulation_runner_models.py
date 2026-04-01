"""Lightweight tests for simulation runner dataclasses (no subprocess)."""

from app.services.simulation_runner import (
    AgentAction,
    RunnerStatus,
    SimulationRunState,
)


def test_simulation_run_state_to_dict_progress():
    st = SimulationRunState(
        simulation_id="sim_x",
        runner_status=RunnerStatus.RUNNING,
        current_round=2,
        total_rounds=10,
    )
    d = st.to_dict()
    assert d["simulation_id"] == "sim_x"
    assert d["runner_status"] == "running"
    assert d["current_round"] == 2
    assert d["total_rounds"] == 10
    assert d["progress_percent"] == 20.0
    assert d["total_actions_count"] == 0


def test_simulation_run_state_add_action_counts_twitter():
    st = SimulationRunState(simulation_id="s1")
    act = AgentAction(
        round_num=1,
        timestamp="t",
        platform="twitter",
        agent_id=1,
        agent_name="a",
        action_type="POST",
    )
    st.add_action(act)
    assert st.twitter_actions_count == 1
    assert st.reddit_actions_count == 0
    assert len(st.recent_actions) == 1


def test_simulation_run_state_to_detail_dict():
    st = SimulationRunState(simulation_id="s2")
    st.add_action(
        AgentAction(
            round_num=1,
            timestamp="t",
            platform="reddit",
            agent_id=2,
            agent_name="b",
            action_type="LIKE",
        )
    )
    d = st.to_detail_dict()
    assert d["recent_actions"][0]["platform"] == "reddit"
    assert d["rounds_count"] == 0
