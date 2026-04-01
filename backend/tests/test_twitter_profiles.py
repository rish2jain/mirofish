import csv
from pathlib import Path

import pytest
from flask import Flask

from app.api.simulation import management as simulation_management
from app.config import Config
from app.services.simulation_manager import SimulationManager, SimulationState


@pytest.fixture
def twitter_profiles_csv(tmp_path: Path) -> Path:
    sim_dir = tmp_path / 'sim_test'
    sim_dir.mkdir()

    profile_path = sim_dir / 'twitter_profiles.csv'
    with profile_path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['user_id', 'name', 'username', 'user_char', 'description'])
        writer.writerow([
            '0',
            'Alice Example',
            'alice_example',
            'Detailed Alice persona',
            'Alice bio',
        ])

    return profile_path


def test_simulation_manager_loads_twitter_profiles_csv(tmp_path: Path, twitter_profiles_csv: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(SimulationManager, 'SIMULATION_DATA_DIR', str(tmp_path))

    manager = SimulationManager()
    manager._simulations['sim_test'] = SimulationState(
        simulation_id='sim_test',
        project_id='proj_test',
        graph_id='graph_test',
    )

    profiles = manager.get_profiles('sim_test', platform='twitter')

    assert profiles == [
        {
            'user_id': 0,
            'username': 'alice_example',
            'name': 'Alice Example',
            'bio': 'Alice bio',
            'persona': 'Detailed Alice persona',
            'description': 'Alice bio',
            'user_char': 'Detailed Alice persona',
        }
    ]


def test_realtime_profiles_endpoint_normalizes_twitter_csv(tmp_path: Path, twitter_profiles_csv: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(Config, 'OASIS_SIMULATION_DATA_DIR', str(tmp_path))

    app = Flask(__name__)
    with app.test_request_context('/api/simulation/sim_test/profiles/realtime?platform=twitter'):
        response = simulation_management.get_simulation_profiles_realtime('sim_test')

    payload = response.get_json()

    assert payload['success'] is True
    assert payload['data']['platform'] == 'twitter'
    assert payload['data']['count'] == 1
    assert payload['data']['profiles'][0]['username'] == 'alice_example'
    assert payload['data']['profiles'][0]['name'] == 'Alice Example'
    assert payload['data']['profiles'][0]['bio'] == 'Alice bio'
    assert payload['data']['profiles'][0]['persona'] == 'Detailed Alice persona'
