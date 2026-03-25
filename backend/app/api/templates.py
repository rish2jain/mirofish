"""Template API endpoints."""

import json
import os
import threading
import time
from flask import Blueprint, jsonify

from ..utils.logger import get_logger

logger = get_logger('mirofish.api.templates')

templates_bp = Blueprint('templates', __name__)

TEMPLATES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../templates'))

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
                            template = json.load(f)
                            templates.append(template)
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
