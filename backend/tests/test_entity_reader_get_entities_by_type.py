"""Pagination for EntityReader.get_entities_by_type."""

from unittest.mock import patch

from app.services.entity_reader import EntityReader, EntityNode, FilteredEntities


def _nodes(n: int) -> list[EntityNode]:
    return [
        EntityNode(
            uuid=f"u{i}",
            name=f"name{i}",
            labels=["Entity", "Topic"],
            summary="",
            attributes={},
        )
        for i in range(n)
    ]


def test_get_entities_by_type_returns_slice_and_total():
    reader = EntityReader()
    fe = FilteredEntities(
        entities=_nodes(10),
        entity_types={"Topic"},
        total_count=10,
        filtered_count=10,
    )
    with patch.object(reader, "filter_defined_entities", return_value=fe):
        page, total = reader.get_entities_by_type(
            "graph_1",
            "Topic",
            enrich_with_edges=True,
            limit=3,
            offset=4,
        )
    assert total == 10
    assert len(page) == 3
    assert [e.uuid for e in page] == ["u4", "u5", "u6"]


def test_get_entities_by_type_offset_beyond_end():
    reader = EntityReader()
    fe = FilteredEntities(
        entities=_nodes(2),
        entity_types={"Topic"},
        total_count=2,
        filtered_count=2,
    )
    with patch.object(reader, "filter_defined_entities", return_value=fe):
        page, total = reader.get_entities_by_type(
            "graph_1",
            "Topic",
            limit=10,
            offset=5,
        )
    assert total == 2
    assert page == []
