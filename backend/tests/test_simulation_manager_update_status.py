"""SimulationManager.update_simulation_status"""

from app.services.simulation_manager import SimulationManager, SimulationStatus


def test_update_simulation_status_persists(tmp_path, monkeypatch):
    monkeypatch.setattr(SimulationManager, "SIMULATION_DATA_DIR", str(tmp_path))
    m = SimulationManager()
    state = m.create_simulation(project_id="p1", graph_id="g1")
    sid = state.simulation_id

    assert m.update_simulation_status(sid, SimulationStatus.COMPLETED) is True
    assert m.get_simulation(sid).status == SimulationStatus.COMPLETED


def test_update_simulation_status_missing_returns_false(tmp_path, monkeypatch):
    monkeypatch.setattr(SimulationManager, "SIMULATION_DATA_DIR", str(tmp_path))
    m = SimulationManager()
    assert m.update_simulation_status("sim_does_not_exist", SimulationStatus.FAILED) is False
