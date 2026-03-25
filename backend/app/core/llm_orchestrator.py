"""
LLM Orchestrator — auto-detects local CLI tools at startup.
Priority: Claude CLI -> Codex CLI -> Gemini CLI -> API fallback.
"""

import shutil
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from ..config import Config
from ..utils.logger import get_logger

logger = get_logger('mirofish.orchestrator')


class LLMBackend(str, Enum):
    CLAUDE_CLI = "claude-cli"
    CODEX_CLI = "codex-cli"
    GEMINI_CLI = "gemini-cli"
    API = "api"


@dataclass(frozen=True)
class OrchestrationResult:
    backend: LLMBackend
    binary_path: Optional[str]
    provider: str
    base_url: str
    model: str
    api_key: str


# Map CLI backend to its default model name
_CLI_DEFAULTS = {
    LLMBackend.CLAUDE_CLI: {"binary": "claude", "provider": "claude-cli", "model": "claude-sonnet-4-20250514"},
    LLMBackend.CODEX_CLI: {"binary": "codex", "provider": "codex-cli", "model": "codex"},
    LLMBackend.GEMINI_CLI: {"binary": "gemini", "provider": "gemini-cli", "model": "gemini-2.5-flash"},
}


def detect_backend() -> OrchestrationResult:
    """
    Detect the best available LLM backend.

    If LLM_PROVIDER is explicitly set in env/.env, respect that choice.
    Otherwise, probe for local CLI tools in priority order.
    """
    explicit_provider = (Config.LLM_PROVIDER or "").strip().lower()

    # Explicit config — respect it
    if explicit_provider:
        if explicit_provider in ("claude-cli", "codex-cli", "gemini-cli"):
            backend = LLMBackend(explicit_provider)
            defaults = _CLI_DEFAULTS[backend]
            binary = shutil.which(defaults["binary"])
            if not binary:
                logger.warning(
                    "LLM_PROVIDER=%s but '%s' not found on PATH. "
                    "Will attempt to use it anyway.",
                    explicit_provider, defaults["binary"]
                )
            return OrchestrationResult(
                backend=backend,
                binary_path=binary,
                provider=defaults["provider"],
                base_url=Config.LLM_BASE_URL,
                model=Config.LLM_MODEL_NAME or defaults["model"],
                api_key=Config.LLM_API_KEY or "",
            )
        # Explicit API provider (openai, anthropic, etc.)
        return OrchestrationResult(
            backend=LLMBackend.API,
            binary_path=None,
            provider=explicit_provider,
            base_url=Config.LLM_BASE_URL,
            model=Config.LLM_MODEL_NAME,
            api_key=Config.LLM_API_KEY,
        )

    # Auto-detection: probe CLIs in priority order
    for backend, defaults in _CLI_DEFAULTS.items():
        binary = shutil.which(defaults["binary"])
        if binary:
            logger.info(
                "Auto-detected %s at %s", defaults["binary"], binary
            )
            return OrchestrationResult(
                backend=backend,
                binary_path=binary,
                provider=defaults["provider"],
                base_url="",
                model=defaults["model"],
                api_key="",
            )

    # No CLI found — require API config
    if not Config.LLM_API_KEY:
        logger.error(
            "No local LLM CLIs (claude, codex, gemini) found on PATH. "
            "Please install one or configure API keys in .env."
        )

    return OrchestrationResult(
        backend=LLMBackend.API,
        binary_path=None,
        provider=Config.LLM_PROVIDER or "openai",
        base_url=Config.LLM_BASE_URL,
        model=Config.LLM_MODEL_NAME,
        api_key=Config.LLM_API_KEY,
    )
