"""Optional API key and user header checks for shared deployments."""

from __future__ import annotations

import hmac
from datetime import datetime, timezone

from flask import jsonify, request

from ..config import Config
from .logger import get_logger

logger = get_logger("mirofish.api_auth")


def optional_user_id() -> str | None:
    """Trimmed ``X-MiroFish-User`` header, or None if absent/blank.

    Always reads the header when present; does not consult
    ``Config.MIROFISH_REQUIRE_USER_HEADER``. Callers that must enforce the header
    should use ``require_user_header()`` or check the flag explicitly.
    """
    uid = (request.headers.get("X-MiroFish-User") or "").strip()
    return uid or None


def require_user_header():
    """Enforce ``X-MiroFish-User`` when ``Config.MIROFISH_REQUIRE_USER_HEADER`` is true.

    Return (None) if OK, or (response, status) if the header is required but
    ``optional_user_id()`` is empty.
    """
    if not Config.MIROFISH_REQUIRE_USER_HEADER:
        return None
    if optional_user_id():
        return None
    return jsonify({"success": False, "error": "X-MiroFish-User header required"}), 400


def require_service_api_key():
    """Return (None) if OK, or (response, status) if MIROFISH_API_KEY is set and header invalid."""
    expected = Config.MIROFISH_API_KEY
    if not expected:
        return None
    auth = (request.headers.get("Authorization") or "").strip()
    token = auth[7:].strip() if auth.startswith("Bearer ") else ""
    if hmac.compare_digest(token, expected):
        return None
    ua = (request.headers.get("User-Agent") or "").strip()
    if len(ua) > 200:
        ua = ua[:200] + "..."
    logger.warning(
        "MIROFISH_API_KEY auth failed | ts=%s | remote_addr=%s | user_agent=%r | %s %s",
        datetime.now(timezone.utc).isoformat(),
        request.remote_addr,
        ua,
        request.method,
        request.path,
    )
    return jsonify({"success": False, "error": "Unauthorized"}), 401
