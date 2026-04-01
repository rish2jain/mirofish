"""GraphBuilderService.get_graph_data with injected storage (no Kuzu)."""

from app.services.graph_builder import GraphBuilderService


class _FakeGraphStorage:
    def list_nodes(self):
        return [
            {
                "id": "n1",
                "name": "Alice",
                "label": "Person",
                "summary": "",
                "attributes": {},
                "facts": [],
                "created_at": "",
                "updated_at": "",
            }
        ]

    def get_edges(self):
        return [
            {
                "id": "e1",
                "relation": "KNOWS",
                "fact": "",
                "source_id": "n1",
                "target_id": "n1",
                "attributes": {},
                "weight": 1.0,
                "created_at": "",
                "episodes": [],
            }
        ]


def test_get_graph_data_with_explicit_storage():
    svc = GraphBuilderService(storage=_FakeGraphStorage())
    out = svc.get_graph_data("g-test")
    assert out["graph_id"] == "g-test"
    assert out["node_count"] == 1
    assert out["edge_count"] == 1
    assert out["nodes"][0]["uuid"] == "n1"
    assert out["nodes"][0]["name"] == "Alice"
    assert out["edges"][0]["source_node_uuid"] == "n1"
    assert out["edges"][0]["target_node_uuid"] == "n1"
