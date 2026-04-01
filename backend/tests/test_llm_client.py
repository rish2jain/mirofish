"""Unit tests for LLMClient helpers (no live API calls)."""

import subprocess

import pytest

from app.utils.llm_client import LLMClient


def test_split_system_message_merges_multiple_system():
    c = LLMClient.__new__(LLMClient)
    sys_t, conv = c._split_system_message(
        [
            {"role": "system", "content": "a"},
            {"role": "system", "content": "b"},
            {"role": "user", "content": "hi"},
        ]
    )
    assert sys_t == "a\n\nb"
    assert conv == [{"role": "user", "content": "hi"}]


def test_clean_content_strips_think_tags():
    c = LLMClient.__new__(LLMClient)
    raw = "<think>ignore this</think>hello"
    assert c._clean_content(raw) == "hello"


def test_clean_content_salvages_json_inside_think_only_response():
    c = LLMClient.__new__(LLMClient)
    raw = '<think>{"x": 1}</think>'
    assert c._clean_content(raw).strip() == '{"x": 1}'


def test_extract_json_from_xml_tags():
    s = '<json_output>{"k": "v"}</json_output>'
    assert LLMClient._extract_json_from_xml(s) == '{"k": "v"}'


def test_extract_json_from_xml_strips_wrappers():
    s = '```\n{"a": 1}\n```'
    out = LLMClient._extract_json_from_xml(s)
    assert '"a": 1' in out


def test_build_cli_prompt_includes_json_instructions():
    p = LLMClient._build_cli_prompt(
        "system text",
        [{"role": "user", "content": "go"}],
        {"type": "json_object"},
    )
    assert "<system>" in p
    assert "json_output" in p
    assert "<user>" in p


def test_detect_provider_from_model(monkeypatch):
    monkeypatch.setattr("app.utils.llm_client.Config.LLM_PROVIDER", "")
    monkeypatch.setattr("app.utils.llm_client.Config.LLM_MODEL_NAME", "claude-3-opus")
    monkeypatch.setattr("app.utils.llm_client.Config.LLM_BASE_URL", "")
    monkeypatch.setattr("app.utils.llm_client.Config.LLM_API_KEY", "sk-test")
    c = LLMClient.__new__(LLMClient)
    c.api_key = "sk-test"
    c.base_url = ""
    c.model = "claude-3-opus"
    c.provider = ""
    c.client = None
    assert c._detect_provider() == "anthropic"


def test_supports_streaming_false_for_cli():
    c = LLMClient.__new__(LLMClient)
    c.provider = "claude-cli"
    c.client = None
    assert c.supports_streaming is False


def test_supports_streaming_false_when_client_missing():
    c = LLMClient.__new__(LLMClient)
    c.provider = "openai"
    c.client = None
    assert c.supports_streaming is False


def test_supports_streaming_true_with_sdk_client():
    c = LLMClient.__new__(LLMClient)
    c.provider = "openai"
    c.client = object()
    assert c.supports_streaming is True


def test_chat_stream_text_warns_when_streaming_unsupported():
    c = LLMClient.__new__(LLMClient)
    c.provider = "gemini-cli"
    c.client = None
    with pytest.warns(UserWarning, match="supports_streaming"):
        gen = c.chat_stream_text([])
        assert list(gen) == []


def test_format_cli_failure_prefers_stderr():
    result = subprocess.CompletedProcess(
        args=["claude"],
        returncode=1,
        stdout="",
        stderr="permission denied",
    )
    assert LLMClient._format_cli_failure("Claude CLI", result) == "Claude CLI failed (rc=1): permission denied"


def test_format_cli_failure_falls_back_to_stdout():
    result = subprocess.CompletedProcess(
        args=["claude"],
        returncode=1,
        stdout="authentication required",
        stderr="",
    )
    assert LLMClient._format_cli_failure("Claude CLI", result) == "Claude CLI failed (rc=1): authentication required"


def test_format_cli_failure_handles_empty_streams():
    result = subprocess.CompletedProcess(
        args=["claude"],
        returncode=1,
        stdout="",
        stderr="",
    )
    assert (
        LLMClient._format_cli_failure("Claude CLI", result)
        == "Claude CLI failed (rc=1): Claude CLI exited with code 1 and produced no output"
    )
