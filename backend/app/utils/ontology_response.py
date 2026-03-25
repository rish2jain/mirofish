"""Helpers for normalizing malformed LLM ontology JSON (list vs dict)."""

from typing import Any, Dict


def empty_ontology_response() -> Dict[str, Any]:
    """Default ontology dict when the model returns nothing usable."""
    return {
        "entity_types": [],
        "edge_types": [],
        "analysis_summary": "",
    }


def unwrap_malformed_ontology(raw: Any) -> Dict[str, Any]:
    """
    Turn list-shaped or invalid LLM responses into a single ontology dict.

    - ``dict`` → returned as-is
    - ``list`` → first dict containing ``entity_types`` or ``edge_types``;
      else a one-element list of dict → that dict; else empty default
    - anything else → empty default
    """
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict) and (
                "entity_types" in item or "edge_types" in item
            ):
                return item
        if len(raw) == 1 and isinstance(raw[0], dict):
            return raw[0]
        return empty_ontology_response()
    return empty_ontology_response()
