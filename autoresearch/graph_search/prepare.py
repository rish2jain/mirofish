"""
Prepare eval data for graph search autoresearch.

Run once to verify:
    python prepare.py

Also imported by train.py.
"""

import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

EVAL_DIR = os.path.join(os.path.dirname(__file__), "eval_data")


@dataclass
class GraphData:
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]

    def node_by_uuid(self, uuid: str) -> Optional[Dict]:
        for n in self.nodes:
            if n["uuid"] == uuid:
                return n
        return None

    def edge_by_uuid(self, uuid: str) -> Optional[Dict]:
        for e in self.edges:
            if e["uuid"] == uuid:
                return e
        return None


@dataclass
class QueryCase:
    id: str
    query: str
    context: str
    gold_edge_uuids: List[str]
    gold_node_uuids: List[str]
    gold_facts_keywords: List[str]
    difficulty: str


def load_graph() -> GraphData:
    path = os.path.join(EVAL_DIR, "graph.json")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return GraphData(
        nodes=data["nodes"],
        edges=data["edges"],
    )


def load_queries() -> List[QueryCase]:
    path = os.path.join(EVAL_DIR, "queries.json")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [
        QueryCase(
            id=q["id"],
            query=q["query"],
            context=q.get("context", ""),
            gold_edge_uuids=q.get("gold_edge_uuids", []),
            gold_node_uuids=q.get("gold_node_uuids", []),
            gold_facts_keywords=q.get("gold_facts_keywords", []),
            difficulty=q.get("difficulty", "medium"),
        )
        for q in data
    ]


if __name__ == "__main__":
    graph = load_graph()
    queries = load_queries()
    print(f"Graph: {len(graph.nodes)} nodes, {len(graph.edges)} edges")
    print(f"Queries: {len(queries)} test cases")
    for q in queries:
        print(
            f"  [{q.difficulty:6s}] {q.id}: "
            f"{len(q.gold_edge_uuids)} gold edges, "
            f"{len(q.gold_node_uuids)} gold nodes, "
            f"{len(q.gold_facts_keywords)} keywords"
        )
    print("All eval data OK.")
