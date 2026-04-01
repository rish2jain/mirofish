"""_get_non_negative_int_env and LLM_CACHE_MAX_AGE parsing."""

import pytest

from app.config import _get_non_negative_int_env


def test_non_negative_int_missing_uses_default(monkeypatch):
    monkeypatch.delenv("LLM_CACHE_MAX_AGE", raising=False)
    assert _get_non_negative_int_env("LLM_CACHE_MAX_AGE", 99) == 99


def test_non_negative_int_blank_uses_default(monkeypatch):
    monkeypatch.setenv("LLM_CACHE_MAX_AGE", "   ")
    assert _get_non_negative_int_env("LLM_CACHE_MAX_AGE", 99) == 99


def test_non_negative_int_valid(monkeypatch):
    monkeypatch.setenv("LLM_CACHE_MAX_AGE", "3600")
    assert _get_non_negative_int_env("LLM_CACHE_MAX_AGE", 99) == 3600


def test_non_negative_int_strips_whitespace(monkeypatch):
    monkeypatch.setenv("LLM_CACHE_MAX_AGE", "  42 ")
    assert _get_non_negative_int_env("LLM_CACHE_MAX_AGE", 99) == 42


def test_non_negative_int_negative_clamped_to_zero(monkeypatch):
    monkeypatch.setenv("LLM_CACHE_MAX_AGE", "-5")
    assert _get_non_negative_int_env("LLM_CACHE_MAX_AGE", 99) == 0


def test_non_negative_int_invalid_raises(monkeypatch):
    monkeypatch.setenv("LLM_CACHE_MAX_AGE", "not-a-number")
    with pytest.raises(ValueError, match="LLM_CACHE_MAX_AGE"):
        _get_non_negative_int_env("LLM_CACHE_MAX_AGE", 99)
