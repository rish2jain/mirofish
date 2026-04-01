"""
AutoResearch experiment runner for graph search strategy optimization.

Usage:
    cd autoresearch/graph_search && python3 train.py

NO LLM calls, no running graph DB required. Simulates the search pipeline
against a static graph (25 nodes, 22 edges) using the strategy functions
in strategies/search_strategy.py. Runs in <1 second.

Scores:
- edge_recall: fraction of gold edges retrieved
- node_recall: fraction of gold nodes whose connected edges are retrieved
- keyword_recall: fraction of gold keywords found in retrieved facts
- ranking_quality: gold edges in top-N positions
"""

import importlib.util
import json
import os
import time
from typing import Any, Dict, List, Set, Tuple

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def load_strategy():
    spec = importlib.util.spec_from_file_location(
        "search_strategy",
        os.path.join(SCRIPT_DIR, "strategies", "search_strategy.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_data():
    from prepare import load_graph, load_queries
    return load_graph(), load_queries()


def run_search(
    strategy,
    graph_edges: List[Dict],
    graph_nodes: List[Dict],
    query: str,
    limit: int = 15,
) -> Tuple[List[Dict], List[str]]:
    """Run search using strategy functions. Returns (matched_edges, facts)."""
    keywords = strategy.tokenize_query(query)
    query_lower = query.lower()

    ranked = strategy.rank_edges(graph_edges, query_lower, keywords, limit)
    matched_edges = [edge for _score, edge in ranked]

    # Also rank nodes
    ranked_nodes = strategy.rank_nodes(
        graph_nodes, query_lower, keywords, limit
    )

    facts = []
    for _score, edge in ranked:
        fact = edge.get("fact", "")
        if fact:
            facts.append(fact)
    for _score, node in ranked_nodes:
        summary = node.get("summary", "")
        if summary:
            facts.append(f"[{node.get('name', '')}]: {summary}")

    facts = strategy.deduplicate_facts(facts)
    return matched_edges, facts


def score_query(
    matched_edges: List[Dict],
    facts: List[str],
    gold_edge_uuids: List[str],
    gold_node_uuids: List[str],
    gold_keywords: List[str],
    graph_data,
) -> Dict[str, float]:
    """Score search results for a single query."""

    # Edge recall: fraction of gold edges retrieved
    retrieved_edge_uuids = {e.get("uuid", "") for e in matched_edges}
    edge_hits = sum(
        1 for eu in gold_edge_uuids if eu in retrieved_edge_uuids
    )
    edge_recall = (
        edge_hits / len(gold_edge_uuids) if gold_edge_uuids else 1.0
    )

    # Node recall: fraction of gold nodes that appear as source/target
    # in retrieved edges
    retrieved_node_uuids: Set[str] = set()
    for e in matched_edges:
        retrieved_node_uuids.add(e.get("source_node_uuid", ""))
        retrieved_node_uuids.add(e.get("target_node_uuid", ""))
    node_hits = sum(
        1 for nu in gold_node_uuids if nu in retrieved_node_uuids
    )
    node_recall = (
        node_hits / len(gold_node_uuids) if gold_node_uuids else 1.0
    )

    # Keyword recall: fraction of gold keywords found in any fact
    all_facts_lower = " ".join(facts).lower()
    kw_hits = sum(
        1 for kw in gold_keywords if kw.lower() in all_facts_lower
    )
    kw_recall = (
        kw_hits / len(gold_keywords) if gold_keywords else 1.0
    )

    # Ranking quality: average reciprocal rank of gold edges
    rr_sum = 0.0
    for gold_uuid in gold_edge_uuids:
        for rank, edge in enumerate(matched_edges, 1):
            if edge.get("uuid") == gold_uuid:
                rr_sum += 1.0 / rank
                break
    mrr = (
        rr_sum / len(gold_edge_uuids) if gold_edge_uuids else 1.0
    )

    return {
        "edge_recall": edge_recall,
        "node_recall": node_recall,
        "keyword_recall": kw_recall,
        "mrr": mrr,
    }


def compute_search_score(per_query_scores: List[Dict]) -> float:
    """
    Composite metric:
      0.30 * avg_edge_recall
    + 0.20 * avg_node_recall
    + 0.30 * avg_keyword_recall
    + 0.20 * avg_mrr
    """
    n = len(per_query_scores)
    if n == 0:
        return 0.0

    avg_er = sum(s["edge_recall"] for s in per_query_scores) / n
    avg_nr = sum(s["node_recall"] for s in per_query_scores) / n
    avg_kr = sum(s["keyword_recall"] for s in per_query_scores) / n
    avg_mrr = sum(s["mrr"] for s in per_query_scores) / n

    return 0.30 * avg_er + 0.20 * avg_nr + 0.30 * avg_kr + 0.20 * avg_mrr


def run_experiment() -> Dict[str, Any]:
    strategy = load_strategy()
    graph, queries = load_data()

    start = time.time()
    per_query = []
    difficulty_scores: Dict[str, List[float]] = {}

    for q in queries:
        matched_edges, facts = run_search(
            strategy, graph.edges, graph.nodes, q.query
        )

        scores = score_query(
            matched_edges,
            facts,
            q.gold_edge_uuids,
            q.gold_node_uuids,
            q.gold_facts_keywords,
            graph,
        )
        per_query.append(scores)

        difficulty_scores.setdefault(q.difficulty, []).append(
            0.30 * scores["edge_recall"]
            + 0.20 * scores["node_recall"]
            + 0.30 * scores["keyword_recall"]
            + 0.20 * scores["mrr"]
        )

        er = scores["edge_recall"]
        nr = scores["node_recall"]
        kr = scores["keyword_recall"]
        mrr = scores["mrr"]
        symbol = "+" if kr >= 0.5 else "x"
        print(
            f"  [{symbol}] {q.id} ({q.difficulty}): "
            f"ER={er:.2f} NR={nr:.2f} KR={kr:.2f} MRR={mrr:.2f}"
        )

    elapsed = time.time() - start
    score = compute_search_score(per_query)

    n = len(per_query)
    avg_er = sum(s["edge_recall"] for s in per_query) / n
    avg_nr = sum(s["node_recall"] for s in per_query) / n
    avg_kr = sum(s["keyword_recall"] for s in per_query) / n
    avg_mrr = sum(s["mrr"] for s in per_query) / n

    print(f"\n{'='*55}")
    print(f"SEARCH SCORE:      {score:.4f}")
    print(f"  Edge Recall:     {avg_er:.4f}")
    print(f"  Node Recall:     {avg_nr:.4f}")
    print(f"  Keyword Recall:  {avg_kr:.4f}")
    print(f"  MRR:             {avg_mrr:.4f}")
    print(f"\nDifficulty breakdown:")
    for diff, scores_list in sorted(difficulty_scores.items()):
        avg = sum(scores_list) / len(scores_list)
        print(f"  {diff:6s}: {avg:.4f} (n={len(scores_list)})")
    print(f"  Elapsed: {elapsed:.3f}s")
    print(f"{'='*55}")

    result_entry = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "search_score": round(score, 4),
        "edge_recall": round(avg_er, 4),
        "node_recall": round(avg_nr, 4),
        "keyword_recall": round(avg_kr, 4),
        "mrr": round(avg_mrr, 4),
        "difficulty": {
            k: round(sum(v) / len(v), 4)
            for k, v in sorted(difficulty_scores.items())
        },
        "num_queries": len(queries),
        "elapsed_seconds": round(elapsed, 3),
    }

    history_path = os.path.join(SCRIPT_DIR, "results", "history.jsonl")
    os.makedirs(os.path.dirname(history_path), exist_ok=True)
    with open(history_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(result_entry) + "\n")
    print(f"Result appended to {history_path}")

    return result_entry


if __name__ == "__main__":
    run_experiment()
