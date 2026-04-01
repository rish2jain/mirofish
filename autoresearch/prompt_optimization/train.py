"""
AutoResearch experiment runner for entity extraction prompt optimization.

Usage:
    cd backend && uv run python ../autoresearch/prompt_optimization/train.py

Reads the current prompt from prompts/entity_extraction.py, runs extraction
on all eval documents, scores against gold standards, and appends results
to results/history.jsonl.
"""

import importlib.util
import json
import os
import sys
import time
from difflib import SequenceMatcher
from typing import Any, Dict, List, Tuple

# ---------------------------------------------------------------------------
# Setup: ensure backend is importable
# ---------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, "../../backend"))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from prepare import (  # noqa: E402
    EvalCase,
    format_edge_types,
    format_entity_types,
    load_eval_cases,
    load_ontology,
)

# ---------------------------------------------------------------------------
# Load the prompt module dynamically (so changes take effect without restart)
# ---------------------------------------------------------------------------


def load_prompt_module():
    filename = os.path.join(SCRIPT_DIR, "prompts", "entity_extraction.py")
    spec = importlib.util.spec_from_file_location("entity_extraction", filename)
    if spec is None or spec.loader is None:
        raise ImportError(
            f"Cannot load prompt module from {filename}: invalid spec or missing loader"
        )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Scoring helpers
# ---------------------------------------------------------------------------


def fuzzy_match(a: str, b: str, threshold: float = 0.75) -> bool:
    """Case-insensitive fuzzy string match."""
    return SequenceMatcher(
        None, a.strip().lower(), b.strip().lower()
    ).ratio() >= threshold


def score_entities(
    extracted: List[Dict], gold: List[Dict]
) -> Tuple[float, float]:
    """Return (precision, recall) for entity extraction."""
    if not gold:
        return (1.0, 1.0) if not extracted else (0.0, 1.0)

    gold_names = [g["name"] for g in gold]
    extracted_names = [e.get("name", "") for e in extracted]

    # Precision: fraction of extracted that match a gold entity
    matched_extracted = 0
    for en in extracted_names:
        if any(fuzzy_match(en, gn) for gn in gold_names):
            matched_extracted += 1
    precision = (
        matched_extracted / len(extracted_names) if extracted_names else 0.0
    )

    # Recall: fraction of gold entities found
    matched_gold = 0
    for gn in gold_names:
        if any(fuzzy_match(en, gn) for en in extracted_names):
            matched_gold += 1
    recall = matched_gold / len(gold_names)

    return precision, recall


def score_relationships(
    extracted: List[Dict], gold: List[Dict]
) -> float:
    """Return F1 for relationship triples (source, target, type)."""
    if not gold:
        return 1.0 if not extracted else 0.0

    def triple(r: Dict) -> Tuple[str, str, str]:
        return (
            r.get("source", "").strip().lower(),
            r.get("target", "").strip().lower(),
            r.get("type", "").strip().lower(),
        )

    def fuzzy_triple_match(
        t: Tuple[str, str, str], candidates: List[Tuple[str, str, str]]
    ) -> bool:
        for c in candidates:
            if (
                fuzzy_match(t[0], c[0])
                and fuzzy_match(t[1], c[1])
                and (t[2] == c[2] or fuzzy_match(t[2], c[2], 0.8))
            ):
                return True
        return False

    gold_triples = [triple(r) for r in gold]
    ext_triples = [triple(r) for r in extracted]

    # Precision
    tp_p = sum(
        1
        for et in ext_triples
        if fuzzy_triple_match(et, gold_triples)
    )
    precision = tp_p / len(ext_triples) if ext_triples else 0.0

    # Recall
    tp_r = sum(
        1
        for gt in gold_triples
        if fuzzy_triple_match(gt, ext_triples)
    )
    recall = tp_r / len(gold_triples) if gold_triples else 0.0

    if precision + recall == 0:
        return 0.0
    return 2 * precision * recall / (precision + recall)


def compute_extraction_score(
    entity_precision: float,
    entity_recall: float,
    relationship_f1: float,
    valid_json_rate: float,
) -> float:
    """
    Composite metric:
      0.4 * entity_precision
    + 0.3 * entity_recall
    + 0.2 * relationship_f1
    + 0.1 * valid_json_rate
    """
    return (
        0.4 * entity_precision
        + 0.3 * entity_recall
        + 0.2 * relationship_f1
        + 0.1 * valid_json_rate
    )


# ---------------------------------------------------------------------------
# Run one extraction using the LLM
# ---------------------------------------------------------------------------


def run_extraction(
    system_prompt: str,
    user_message: str,
) -> Tuple[Dict[str, Any], bool]:
    """
    Call the LLM and return (parsed_result, valid_json).

    Returns ({"entities": [], "relationships": []}, False) on failure.
    """
    from app.utils.llm_client import LLMClient

    client = LLMClient()
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]

    try:
        result = client.chat_json(
            messages=messages,
            temperature=0.2,
            max_tokens=4096,
        )
        return result, True
    except Exception as e:
        print(f"  [ERROR] LLM call failed: {e}")
        return {"entities": [], "relationships": []}, False


# ---------------------------------------------------------------------------
# Main experiment loop
# ---------------------------------------------------------------------------


def run_experiment() -> Dict[str, Any]:
    prompt_mod = load_prompt_module()
    system_prompt = prompt_mod.SYSTEM_PROMPT
    user_template = prompt_mod.USER_TEMPLATE

    ontology = load_ontology()
    entity_types_desc = format_entity_types(ontology)
    edge_types_desc = format_edge_types(ontology)
    cases = load_eval_cases()

    # Measure prompt size
    prompt_tokens_est = len(system_prompt) // 4
    print(f"Prompt size: ~{prompt_tokens_est} tokens")
    if prompt_tokens_est > 2000:
        print(
            f"  WARNING: Prompt exceeds 2000 token budget "
            f"({prompt_tokens_est})"
        )

    all_precisions = []
    all_recalls = []
    all_rel_f1s = []
    valid_jsons = 0
    total_docs = len(cases)
    start_time = time.time()

    for case in cases:
        print(f"\n--- {case.name} ---")
        user_msg = user_template.format(
            entity_types_desc=entity_types_desc,
            edge_types_desc=edge_types_desc,
            text=case.text,
        )

        result, valid = run_extraction(system_prompt, user_msg)
        if valid:
            valid_jsons += 1

        entities = result.get("entities", [])
        relationships = result.get("relationships", [])
        print(
            f"  Extracted: {len(entities)} entities, "
            f"{len(relationships)} relationships "
            f"(valid_json={valid})"
        )

        prec, rec = score_entities(entities, case.gold_entities)
        rel_f1 = score_relationships(
            relationships, case.gold_relationships
        )
        print(
            f"  Entity P={prec:.3f} R={rec:.3f} | "
            f"Relationship F1={rel_f1:.3f}"
        )

        all_precisions.append(prec)
        all_recalls.append(rec)
        all_rel_f1s.append(rel_f1)

    elapsed = time.time() - start_time

    if total_docs == 0:
        avg_prec = avg_rec = avg_rel_f1 = json_rate = 0.0
    else:
        avg_prec = sum(all_precisions) / total_docs
        avg_rec = sum(all_recalls) / total_docs
        avg_rel_f1 = sum(all_rel_f1s) / total_docs
        json_rate = valid_jsons / total_docs

    score = compute_extraction_score(
        avg_prec, avg_rec, avg_rel_f1, json_rate
    )

    result_entry = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "extraction_score": round(score, 4),
        "entity_precision": round(avg_prec, 4),
        "entity_recall": round(avg_rec, 4),
        "relationship_f1": round(avg_rel_f1, 4),
        "valid_json_rate": round(json_rate, 4),
        "prompt_tokens_est": prompt_tokens_est,
        "elapsed_seconds": round(elapsed, 1),
        "num_docs": total_docs,
    }

    print(f"\n{'='*50}")
    print(f"EXTRACTION SCORE: {score:.4f}")
    print(f"  Entity Precision:  {avg_prec:.4f}")
    print(f"  Entity Recall:     {avg_rec:.4f}")
    print(f"  Relationship F1:   {avg_rel_f1:.4f}")
    print(f"  Valid JSON Rate:   {json_rate:.4f}")
    print(f"  Elapsed:           {elapsed:.1f}s")
    print(f"{'='*50}")

    # Append to history
    history_path = os.path.join(SCRIPT_DIR, "results", "history.jsonl")
    os.makedirs(os.path.dirname(history_path), exist_ok=True)
    with open(history_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(result_entry) + "\n")
    print(f"Result appended to {history_path}")

    return result_entry


if __name__ == "__main__":
    run_experiment()
