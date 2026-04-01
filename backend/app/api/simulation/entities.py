"""Simulation API — entity routes."""
import re

from flask import request, jsonify

from .. import simulation_bp
from ...services.entity_reader import get_entity_reader

from .common import logger

_DEFAULT_BY_TYPE_LIMIT = 100
_MAX_BY_TYPE_LIMIT = 500

# Path segment for entity id: UUIDs, short test ids (e.g. n1), no spaces or markup.
_ENTITY_PATH_ID_RE = re.compile(r"^[A-Za-z0-9_.\-]{1,128}$")


def _is_safe_entity_path_id(entity_uuid: str) -> bool:
    return bool(entity_uuid and _ENTITY_PATH_ID_RE.fullmatch(entity_uuid))


# ============== Entity Reading Endpoints ==============

@simulation_bp.route('/entities/<graph_id>', methods=['GET'])
def get_graph_entities(graph_id: str):
    """
    Get all entities from the graph (filtered)

    Returns only nodes matching predefined entity types (nodes whose Labels are not just Entity)

    Query parameters:
        entity_types: Comma-separated list of entity types (optional, for additional filtering)
        enrich: Whether to fetch related edge information (default true)
    """
    try:

        entity_types_str = request.args.get('entity_types', '')
        entity_types = [t.strip() for t in entity_types_str.split(',') if t.strip()] if entity_types_str else None
        enrich = request.args.get('enrich', 'true').lower() == 'true'

        logger.info(f"Fetching graph entities: graph_id={graph_id}, entity_types={entity_types}, enrich={enrich}")
        
        reader = get_entity_reader()
        result = reader.filter_defined_entities(
            graph_id=graph_id,
            defined_entity_types=entity_types,
            enrich_with_edges=enrich
        )
        
        return jsonify({
            "success": True,
            "data": result.to_dict()
        })
        
    except Exception:
        logger.exception("Failed to fetch graph entities")
        return jsonify({
            "success": False,
            "error": "Internal server error"
        }), 500


@simulation_bp.route('/entities/<graph_id>/<entity_uuid>', methods=['GET'])
def get_entity_detail(graph_id: str, entity_uuid: str):
    """Get detailed information for a single entity"""
    try:
        if not _is_safe_entity_path_id(entity_uuid):
            logger.warning(
                "Entity detail rejected invalid id shape (graph_id=%s, len=%s, prefix=%r)",
                graph_id,
                len(entity_uuid or ""),
                (entity_uuid or "")[:80],
            )
            return jsonify({
                "success": False,
                "error": "Invalid entity identifier",
            }), 400

        reader = get_entity_reader()
        entity = reader.get_entity_with_context(graph_id, entity_uuid)

        if not entity:
            logger.info(
                "Entity not found (graph_id=%s, entity_uuid=%s)",
                graph_id,
                entity_uuid,
            )
            return jsonify({
                "success": False,
                "error": "Entity not found",
            }), 404

        return jsonify({
            "success": True,
            "data": entity.to_dict()
        })
        
    except Exception:
        logger.exception("Failed to fetch entity details")
        return jsonify({
            "success": False,
            "error": "Internal server error"
        }), 500


@simulation_bp.route('/entities/<graph_id>/by-type/<entity_type>', methods=['GET'])
def get_entities_by_type(graph_id: str, entity_type: str):
    """Get entities of a specified type (paginated via limit and offset query params)."""
    try:
        enrich = request.args.get('enrich', 'true').lower() == 'true'

        limit_raw = request.args.get('limit', str(_DEFAULT_BY_TYPE_LIMIT))
        offset_raw = request.args.get('offset', '0')
        try:
            limit = int(limit_raw)
            offset = int(offset_raw)
        except (TypeError, ValueError):
            return jsonify({
                "success": False,
                "error": "limit and offset must be integers",
            }), 400
        if offset < 0:
            return jsonify({
                "success": False,
                "error": "offset must be >= 0",
            }), 400
        if limit < 1 or limit > _MAX_BY_TYPE_LIMIT:
            return jsonify({
                "success": False,
                "error": f"limit must be between 1 and {_MAX_BY_TYPE_LIMIT}",
            }), 400

        reader = get_entity_reader()
        entities, total = reader.get_entities_by_type(
            graph_id=graph_id,
            entity_type=entity_type,
            enrich_with_edges=enrich,
            limit=limit,
            offset=offset,
        )

        return jsonify({
            "success": True,
            "data": {
                "entity_type": entity_type,
                "entities": [e.to_dict() for e in entities],
                "pagination": {
                    "limit": limit,
                    "offset": offset,
                    "total": total,
                    "count": len(entities),
                },
            },
        })

    except Exception:
        logger.exception("Failed to fetch entities")
        return jsonify({
            "success": False,
            "error": "Internal server error"
        }), 500


