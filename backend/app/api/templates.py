"""Template API endpoints."""

from __future__ import annotations

import json
import os
import re
import threading
import time
from flask import Blueprint, jsonify, request
from pydantic import BaseModel, ValidationError

from ..config import Config
from ..utils.api_auth import require_service_api_key
from ..utils.logger import get_logger


class SimulationTemplate(BaseModel):
    """Minimal schema for template JSON files (unknown keys preserved)."""

    id: str
    model_config = {"extra": "allow"}

logger = get_logger('mirofish.api.templates')

templates_bp = Blueprint('templates', __name__)

TEMPLATES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../templates'))

# Safe template id for filesystem (filename stem before .json); prevents path traversal.
_TEMPLATE_ID_SAFE_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,191}$")


def _resolve_safe_template_write_path(tid: str) -> tuple[str | None, str | None]:
    """
    Return (absolute filepath, None) for tid.json under TEMPLATES_DIR, or (None, error_message).
    """
    if not tid or not isinstance(tid, str):
        return None, "Invalid template id"
    if os.path.basename(tid) != tid:
        return None, "Invalid template id"
    if ".." in tid or "/" in tid or "\\" in tid:
        return None, "Invalid template id"
    if not _TEMPLATE_ID_SAFE_RE.match(tid):
        return None, "Invalid template id"

    root = os.path.abspath(os.path.realpath(TEMPLATES_DIR))
    os.makedirs(root, exist_ok=True)
    candidate = os.path.join(root, f"{tid}.json")
    filepath = os.path.abspath(os.path.normpath(candidate))
    try:
        if os.path.commonpath([root, filepath]) != root:
            return None, "Invalid template id"
    except ValueError:
        return None, "Invalid template id"
    return filepath, None


# In-memory cache: (ordered list, id -> template). Invalidates on TTL or invalidate_templates_cache().
_TEMPLATES_CACHE = None  # tuple[list, dict] | None
_TEMPLATES_CACHE_TS = 0.0
_TEMPLATES_CACHE_TTL_SEC = 60.0
_TEMPLATES_CACHE_LOCK = threading.Lock()
_TEMPLATES_CACHE_COND = threading.Condition(_TEMPLATES_CACHE_LOCK)
_TEMPLATES_LOADING = False


def invalidate_templates_cache():
    """Clear the template list cache. Call after writing template JSON files on disk."""
    global _TEMPLATES_CACHE, _TEMPLATES_CACHE_TS
    with _TEMPLATES_CACHE_COND:
        _TEMPLATES_CACHE = None
        _TEMPLATES_CACHE_TS = 0.0


def _templates_payload():
    """Return (templates_list, template_index_by_id), loading from disk when cache is stale."""
    global _TEMPLATES_CACHE, _TEMPLATES_CACHE_TS, _TEMPLATES_LOADING

    with _TEMPLATES_CACHE_COND:
        now = time.monotonic()
        if _TEMPLATES_CACHE is not None and (now - _TEMPLATES_CACHE_TS) < _TEMPLATES_CACHE_TTL_SEC:
            return _TEMPLATES_CACHE

        while _TEMPLATES_LOADING:
            _TEMPLATES_CACHE_COND.wait()
            now = time.monotonic()
            if _TEMPLATES_CACHE is not None and (now - _TEMPLATES_CACHE_TS) < _TEMPLATES_CACHE_TTL_SEC:
                return _TEMPLATES_CACHE

        now = time.monotonic()
        if _TEMPLATES_CACHE is not None and (now - _TEMPLATES_CACHE_TS) < _TEMPLATES_CACHE_TTL_SEC:
            return _TEMPLATES_CACHE

        _TEMPLATES_LOADING = True

    payload = None
    try:
        templates = []
        if os.path.isdir(TEMPLATES_DIR):
            for filename in sorted(os.listdir(TEMPLATES_DIR)):
                if filename.endswith('.json'):
                    filepath = os.path.join(TEMPLATES_DIR, filename)
                    try:
                        with open(filepath, 'r', encoding='utf-8') as f:
                            raw = json.load(f)
                            try:
                                templates.append(
                                    SimulationTemplate.model_validate(raw).model_dump(mode="python")
                                )
                            except ValidationError as ve:
                                logger.warning("Invalid template %s: %s", filename, ve)
                    except (json.JSONDecodeError, IOError) as e:
                        logger.warning("Failed to load template %s: %s", filename, e)

        template_index = {}
        for t in templates:
            tid = t.get("id")
            if tid is not None and tid not in template_index:
                template_index[tid] = t

        payload = (templates, template_index)
    finally:
        with _TEMPLATES_CACHE_COND:
            if payload is None and _TEMPLATES_CACHE is None:
                payload = ([], {})
            if payload is not None:
                now = time.monotonic()
                if _TEMPLATES_CACHE is None or (now - _TEMPLATES_CACHE_TS) >= _TEMPLATES_CACHE_TTL_SEC:
                    _TEMPLATES_CACHE = payload
                    _TEMPLATES_CACHE_TS = now
            _TEMPLATES_LOADING = False
            _TEMPLATES_CACHE_COND.notify_all()

    with _TEMPLATES_CACHE_COND:
        out = _TEMPLATES_CACHE
    return out if out is not None else ([], {})


def _load_templates():
    """Load all template JSON files from the templates directory (cached)."""
    return _templates_payload()[0]


@templates_bp.route('/', methods=['GET'])
def list_templates():
    """List all available simulation templates."""
    templates = _load_templates()
    return jsonify({
        'success': True,
        'data': templates
    })


@templates_bp.route('/<template_id>', methods=['GET'])
def get_template(template_id):
    """Get a single template by ID."""
    template_index = _templates_payload()[1]
    t = template_index.get(template_id)
    if t is not None:
        return jsonify({'success': True, 'data': t})
    return jsonify({'success': False, 'error': f'Template "{template_id}" not found'}), 404


def _allow_template_write() -> bool:
    return Config.MIROFISH_ALLOW_TEMPLATE_WRITE or Config.DEBUG


def _persist_template_from_request(template_id: str | None):
    """Validate JSON body, write file, invalidate cache. Returns Flask response."""
    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        return jsonify({'success': False, 'error': 'JSON object required'}), 400
    body_id = data.get('id')
    if template_id and body_id not in (None, '') and str(template_id) != str(body_id):
        return jsonify(
            {'success': False, 'error': 'URL id and body id must match'}
        ), 400
    if template_id and not data.get('id'):
        data = {**data, 'id': template_id}
    try:
        validated = SimulationTemplate.model_validate(data).model_dump(mode='python')
    except ValidationError as ve:
        return jsonify({'success': False, 'error': str(ve)}), 400

    tid = validated.get('id')
    if not tid:
        return jsonify({'success': False, 'error': 'id is required'}), 400

    filepath, path_err = _resolve_safe_template_write_path(str(tid))
    if path_err or not filepath:
        return jsonify({'success': False, 'error': path_err or 'Invalid template id'}), 400
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(validated, f, ensure_ascii=False, indent=2)
    except OSError as e:
        logger.error('Failed to write template %s: %s', filepath, e)
        return jsonify({'success': False, 'error': 'Failed to write template file'}), 500

    invalidate_templates_cache()
    return jsonify({'success': True, 'data': validated})


@templates_bp.route('/<template_id>', methods=['PUT'])
def upsert_template(template_id):
    """
    Create or replace a template JSON on disk (opt-in: MIROFISH_ALLOW_TEMPLATE_WRITE=1 or FLASK_DEBUG).
    Requires MIROFISH_API_KEY when that env is set.
    """
    auth_err = require_service_api_key()
    if auth_err:
        return auth_err
    if not _allow_template_write():
        return jsonify({'success': False, 'error': 'Template write disabled'}), 403
    return _persist_template_from_request(template_id)


@templates_bp.route('/', methods=['POST'])
def create_template():
    """Create a new template (same guards as PUT). Body must include id."""
    auth_err = require_service_api_key()
    if auth_err:
        return auth_err
    if not _allow_template_write():
        return jsonify({'success': False, 'error': 'Template write disabled'}), 403
    return _persist_template_from_request(None)
