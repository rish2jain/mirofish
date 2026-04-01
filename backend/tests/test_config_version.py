"""Config.VERSION from distribution metadata."""

from app.config import Config, _get_app_version


def test_get_app_version_format():
    v = _get_app_version()
    assert isinstance(v, str)
    assert v.startswith("v")
    assert len(v) >= 2


def test_config_version_matches_helper():
    assert Config.VERSION == _get_app_version()
