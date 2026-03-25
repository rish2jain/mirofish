"""Template API endpoints."""

import json
import os
from flask import Blueprint, jsonify

from ..utils.logger import get_logger

logger = get_logger('mirofish.api.templates')

templates_bp = Blueprint('templates', __name__)

TEMPLATES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../templates'))


def _load_templates():
    """Load all template JSON files from the templates directory."""
    templates = []
    if not os.path.isdir(TEMPLATES_DIR):
        return templates
    for filename in sorted(os.listdir(TEMPLATES_DIR)):
        if filename.endswith('.json'):
            filepath = os.path.join(TEMPLATES_DIR, filename)
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    template = json.load(f)
                    templates.append(template)
            except (json.JSONDecodeError, IOError) as e:
                logger.warning("Failed to load template %s: %s", filename, e)
    return templates


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
    templates = _load_templates()
    for t in templates:
        if t.get('id') == template_id:
            return jsonify({'success': True, 'data': t})
    return jsonify({'success': False, 'error': f'Template "{template_id}" not found'}), 404
