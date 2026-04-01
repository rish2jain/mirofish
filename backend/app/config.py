"""
Configuration management.
"""

from __future__ import annotations

import os
import secrets

from dotenv import load_dotenv


def _get_bool_env(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _get_non_negative_int_env(name: str, default: int) -> int:
    """
    Parse a non-negative integer from the environment.

    Missing or blank uses ``default``. Invalid values raise ``ValueError``.
    Negative values are clamped to 0.
    """
    raw = os.environ.get(name)
    if raw is None:
        return default
    stripped = raw.strip()
    if not stripped:
        return default
    try:
        value = int(stripped)
    except ValueError as exc:
        raise ValueError(
            f"{name} must be a non-negative integer, got {raw!r}"
        ) from exc
    return max(0, value)


def _resolve_path(default_path: str, env_name: str) -> str:
    raw_value = os.environ.get(env_name, default_path)
    return os.path.abspath(raw_value)


def _get_secret_key() -> str:
    explicit = os.environ.get("SECRET_KEY")
    if explicit:
        return explicit

    default_config_root = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "../config")
    )
    config_root = os.path.abspath(
        os.environ.get("MIROFISH_APP_CONFIG_DIR")
        or os.environ.get("APP_CONFIG_DIR")
        or os.environ.get("CONFIG_DIR")
        or default_config_root
    )
    secrets_dir = os.path.join(config_root, "secrets")
    os.makedirs(secrets_dir, exist_ok=True)
    secret_path = os.path.join(secrets_dir, ".secret_key")

    try:
        if os.path.isfile(secret_path):
            with open(secret_path, "r", encoding="utf-8") as f:
                existing = f.read().strip()
                if existing:
                    return existing
    except OSError:
        pass

    generated = secrets.token_hex(32)
    try:
        with open(secret_path, "w", encoding="utf-8") as f:
            f.write(generated)
    except OSError:
        # Fall back to in-memory generation if the file is not writable.
        return generated
    try:
        os.chmod(secret_path, 0o600)
    except OSError:
        pass
    return generated


# Load the .env file from project root.
project_root_env = os.path.join(os.path.dirname(__file__), "../../.env")

if os.path.exists(project_root_env):
    load_dotenv(project_root_env, override=True)
else:
    load_dotenv(override=True)


def _get_cors_origins():
    raw = os.environ.get("CORS_ORIGINS", "").strip()
    if not raw:
        return [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:5001",
            "http://127.0.0.1:5001",
        ]
    if raw == "*":
        return "*"
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def _get_llm_api_key() -> str:
    explicit = os.environ.get('LLM_API_KEY', '')
    if explicit:
        return explicit

    provider = (os.environ.get('LLM_PROVIDER', '') or '').strip().lower()
    if provider == 'anthropic':
        return os.environ.get('ANTHROPIC_API_KEY', '')

    return os.environ.get('OPENAI_API_KEY', '') or os.environ.get('ANTHROPIC_API_KEY', '')


def _get_env_or_default(name: str, default: str) -> str:
    value = os.environ.get(name)
    return value if value not in (None, '') else default


def _get_app_version() -> str:
    """Release string from installed distribution ``mirofish-backend`` (pyproject version)."""
    try:
        from importlib.metadata import version

        ver = version("mirofish-backend").strip()
    except Exception:
        return "v0.0.0"
    if not ver:
        return "v0.0.0"
    return ver if ver.lower().startswith("v") else f"v{ver}"


class Config:
    """Flask configuration class."""

    # Flask config
    DEBUG = _get_bool_env("FLASK_DEBUG", False)
    # If true, /health includes llm_binary path (else only llm_cli_on_path)
    EXPOSE_BINARY_PATH = _get_bool_env("EXPOSE_BINARY_PATH", False)
    SECRET_KEY = _get_secret_key()
    CORS_ORIGINS = _get_cors_origins()

    # JSON config
    JSON_AS_ASCII = False

    # Exposed to clients (e.g. simulation history); single source: pyproject.toml
    VERSION = _get_app_version()

    # LLM config
    LLM_API_KEY = _get_llm_api_key()
    LLM_BASE_URL = _get_env_or_default('LLM_BASE_URL', 'https://api.openai.com/v1')
    LLM_MODEL_NAME = _get_env_or_default('LLM_MODEL_NAME', 'gpt-4o-mini')
    LLM_PROVIDER = os.environ.get('LLM_PROVIDER', '')  # 'openai', 'anthropic', 'claude-cli', 'codex-cli'

    # Graph storage config
    GRAPH_BACKEND = os.environ.get("GRAPH_BACKEND", "kuzu").lower()
    KUZU_DB_PATH = _resolve_path(os.path.join(os.path.dirname(__file__), "../data/kuzu_db"), "KUZU_DB_PATH")
    DATA_DIR = _resolve_path(os.path.join(os.path.dirname(__file__), "../data/json_graphs"), "DATA_DIR")
    GRAPH_DB_PATH = KUZU_DB_PATH

    # File upload config
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024
    UPLOAD_FOLDER = os.path.abspath(os.path.join(os.path.dirname(__file__), "../uploads"))
    ALLOWED_EXTENSIONS = {"pdf", "md", "txt", "markdown"}

    # Text processing config
    DEFAULT_CHUNK_SIZE = 500
    DEFAULT_CHUNK_OVERLAP = 50

    # CLI subprocess timeout (seconds) — applies to all CLI-based LLM providers
    CLI_TIMEOUT = _get_non_negative_int_env("CLI_TIMEOUT", 180)

    # OASIS simulation config
    OASIS_DEFAULT_MAX_ROUNDS = int(os.environ.get("OASIS_DEFAULT_MAX_ROUNDS", "10"))
    OASIS_SIMULATION_DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../uploads/simulations"))

    # OASIS platform available actions
    OASIS_TWITTER_ACTIONS = [
        "CREATE_POST", "LIKE_POST", "REPOST", "FOLLOW", "DO_NOTHING", "QUOTE_POST"
    ]
    OASIS_REDDIT_ACTIONS = [
        "LIKE_POST", "DISLIKE_POST", "CREATE_POST", "CREATE_COMMENT",
        "LIKE_COMMENT", "DISLIKE_COMMENT", "SEARCH_POSTS", "SEARCH_USER",
        "TREND", "REFRESH", "DO_NOTHING", "FOLLOW", "MUTE",
    ]

    # Report agent config
    REPORT_AGENT_MAX_TOOL_CALLS = int(os.environ.get("REPORT_AGENT_MAX_TOOL_CALLS", "5"))
    REPORT_AGENT_MAX_REFLECTION_ROUNDS = int(os.environ.get("REPORT_AGENT_MAX_REFLECTION_ROUNDS", "2"))
    REPORT_AGENT_TEMPERATURE = float(os.environ.get("REPORT_AGENT_TEMPERATURE", "0.5"))
    # Optional: generate sections concurrently (faster; coherence uses outline only, not prior section text)
    REPORT_SECTION_PARALLEL = _get_bool_env("REPORT_SECTION_PARALLEL", False)
    REPORT_SECTION_PARALLEL_MAX_WORKERS = _get_non_negative_int_env(
        "REPORT_SECTION_PARALLEL_MAX_WORKERS", 4
    )
    # Optional: run InsightForge sub-query graph searches in parallel (separate DB handles per worker)
    INSIGHT_FORGE_PARALLEL_SUBQUERIES = _get_bool_env("INSIGHT_FORGE_PARALLEL_SUBQUERIES", True)
    INSIGHT_FORGE_SUBQUERY_WORKERS = _get_non_negative_int_env(
        "INSIGHT_FORGE_SUBQUERY_WORKERS", 4
    )

    # LLM response cache (content-hash based, file-backed)
    LLM_CACHE_ENABLED = _get_bool_env("LLM_CACHE_ENABLED", True)
    LLM_CACHE_MAX_AGE = _get_non_negative_int_env("LLM_CACHE_MAX_AGE", 86400 * 7)  # 7 days

    # Parallel entity extraction
    PARALLEL_ENTITY_EXTRACTION = _get_bool_env("PARALLEL_ENTITY_EXTRACTION", True)
    PARALLEL_ENTITY_EXTRACTION_WORKERS = _get_non_negative_int_env(
        "PARALLEL_ENTITY_EXTRACTION_WORKERS", 4
    )

    # Feature flags / shared deployments
    MIROFISH_ALLOW_TEMPLATE_WRITE = _get_bool_env("MIROFISH_ALLOW_TEMPLATE_WRITE", False)
    MIROFISH_API_KEY = os.environ.get("MIROFISH_API_KEY", "").strip()
    MIROFISH_REQUIRE_USER_HEADER = _get_bool_env("MIROFISH_REQUIRE_USER_HEADER", False)
    BATCH_SIM_MAX_ITEMS = _get_non_negative_int_env("BATCH_SIM_MAX_ITEMS", 20)

    @classmethod
    def validate(cls, llm_backend=None):
        """Validate required configuration."""
        errors = []
        # If a CLI backend was auto-detected, API key is not required
        cli_backends = {"claude-cli", "codex-cli", "gemini-cli"}
        effective_provider = llm_backend or cls.LLM_PROVIDER
        if effective_provider not in cli_backends and not cls.LLM_API_KEY:
            errors.append(
                "No local LLM CLIs (claude, codex, gemini) found on PATH. "
                "Please either install one or configure API keys in .env "
                "(LLM_API_KEY, LLM_BASE_URL, LLM_MODEL_NAME)."
            )
        if cls.GRAPH_BACKEND not in {"kuzu", "json"}:
            errors.append("GRAPH_BACKEND must be either 'kuzu' or 'json'")
        return errors
