"""Tests for ontology_response unwrap helpers."""

from app.utils.ontology_response import (
    empty_ontology_response,
    unwrap_malformed_ontology,
)


def test_unwrap_passes_through_dict():
    d = {"entity_types": [{"name": "X"}], "edge_types": [], "analysis_summary": "a"}
    assert unwrap_malformed_ontology(d) is d


def test_unwrap_list_prefers_ontology_shaped_dict():
    inner = {"entity_types": [], "edge_types": [{"name": "E"}], "analysis_summary": ""}
    raw = [{"noise": 1}, inner]
    assert unwrap_malformed_ontology(raw) is inner


def test_unwrap_single_element_dict_list():
    inner = {"foo": 1}
    assert unwrap_malformed_ontology([inner]) is inner


def test_unwrap_list_returns_empty_default_when_no_match():
    out = unwrap_malformed_ontology([1, 2, 3])
    assert out == empty_ontology_response()


def test_unwrap_non_dict_non_list():
    assert unwrap_malformed_ontology(None) == empty_ontology_response()
    assert unwrap_malformed_ontology("x") == empty_ontology_response()
