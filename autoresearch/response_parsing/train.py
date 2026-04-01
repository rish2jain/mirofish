"""
AutoResearch experiment runner for LLM response parsing optimization.

Usage:
    cd autoresearch/response_parsing && python train.py

NO LLM calls required — this is a pure parsing test against a static corpus
of 25 pre-recorded LLM responses. Runs in <1 second.

Loads the parser from parsers/response_parser.py, runs it against all eval
cases, and scores the results.
"""

import importlib.util
import json
import os
import time
from typing import Any, Dict, Optional

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


# ---------------------------------------------------------------------------
# Load the parser module dynamically
# ---------------------------------------------------------------------------


def load_parser_module():
    spec = importlib.util.spec_from_file_location(
        "response_parser",
        os.path.join(SCRIPT_DIR, "parsers", "response_parser.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Load eval data
# ---------------------------------------------------------------------------


def load_cases():
    from prepare import load_cases as _load
    return _load()


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def deep_equal(a: Any, b: Any) -> bool:
    """Deep equality check for JSON-serializable objects."""
    if type(a) != type(b):
        return False
    if isinstance(a, dict):
        if set(a.keys()) != set(b.keys()):
            return False
        return all(deep_equal(a[k], b[k]) for k in a)
    if isinstance(a, list):
        if len(a) != len(b):
            return False
        return all(deep_equal(x, y) for x, y in zip(a, b))
    return a == b


def keys_match(
    parsed: Optional[Dict], expected: Optional[Dict]
) -> bool:
    """Check if parsed result has the same top-level keys as expected."""
    if parsed is None and expected is None:
        return True
    if parsed is None or expected is None:
        return False
    return set(parsed.keys()) == set(expected.keys())


def values_match(
    parsed: Optional[Dict], expected: Optional[Dict]
) -> bool:
    """Check if parsed result deeply equals expected."""
    if parsed is None and expected is None:
        return True
    if parsed is None or expected is None:
        return False
    return deep_equal(parsed, expected)


def compute_parse_score(results: list) -> Dict[str, float]:
    """
    Composite scoring:
      parse_rate    = fraction of cases where parser returned non-None
                      when expected is non-None (true positives) +
                      fraction where parser returned None when expected
                      is None (true negatives)
      exact_match   = fraction of non-error cases where output == expected
      key_match     = fraction of non-error cases where top-level keys match
      error_handling = fraction of error cases correctly returned as None
      robustness    = weighted average across categories

    Final score:
      0.35 * exact_match + 0.25 * key_match + 0.20 * parse_rate
      + 0.20 * error_handling
    """
    total = len(results)
    if total == 0:
        return {
            "parse_score": 0.0,
            "exact_match": 0.0,
            "key_match": 0.0,
            "parse_rate": 0.0,
            "error_handling": 0.0,
            "category_scores": {},
        }

    success_cases = [r for r in results if r["expected"] is not None]
    error_cases = [r for r in results if r["expected"] is None]

    # Parse rate (true positive rate for success cases)
    parse_tp = sum(
        1 for r in success_cases if r["parsed"] is not None
    )
    parse_rate = parse_tp / len(success_cases) if success_cases else 1.0

    # Exact match (for success cases only)
    exact = sum(1 for r in success_cases if r["exact_match"])
    exact_match = exact / len(success_cases) if success_cases else 1.0

    # Key match (for success cases only)
    keys = sum(1 for r in success_cases if r["keys_match"])
    key_match = keys / len(success_cases) if success_cases else 1.0

    # Error handling (true negative rate)
    error_tn = sum(1 for r in error_cases if r["parsed"] is None)
    error_handling = (
        error_tn / len(error_cases) if error_cases else 1.0
    )

    # Category breakdown
    categories: Dict[str, list] = {}
    for r in results:
        cat = r["category"]
        categories.setdefault(cat, []).append(r)

    cat_scores = {}
    for cat, items in categories.items():
        success_items = [i for i in items if i["expected"] is not None]
        if success_items:
            cat_exact = sum(1 for i in success_items if i["exact_match"])
            cat_scores[cat] = cat_exact / len(success_items)
        else:
            error_items = [i for i in items if i["expected"] is None]
            cat_none = sum(1 for i in error_items if i["parsed"] is None)
            cat_scores[cat] = (
                cat_none / len(error_items) if error_items else 1.0
            )

    score = (
        0.35 * exact_match
        + 0.25 * key_match
        + 0.20 * parse_rate
        + 0.20 * error_handling
    )

    return {
        "parse_score": round(score, 4),
        "exact_match": round(exact_match, 4),
        "key_match": round(key_match, 4),
        "parse_rate": round(parse_rate, 4),
        "error_handling": round(error_handling, 4),
        "category_scores": {
            k: round(v, 4) for k, v in sorted(cat_scores.items())
        },
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def run_experiment() -> Dict[str, Any]:
    parser_mod = load_parser_module()
    parse_fn = parser_mod.parse_llm_response
    cases = load_cases()

    start = time.time()
    results = []

    for case in cases:
        parsed = parse_fn(case.raw)
        exact = values_match(parsed, case.expected)
        keys = keys_match(parsed, case.expected)

        status = "PASS" if exact else "FAIL"
        # For error cases, PASS if both are None
        if case.expected is None:
            status = "PASS" if parsed is None else "FAIL"

        results.append({
            "id": case.id,
            "category": case.category,
            "expected": case.expected,
            "parsed": parsed,
            "exact_match": exact,
            "keys_match": keys,
            "status": status,
        })

        symbol = "+" if status == "PASS" else "x"
        print(f"  [{symbol}] {case.id}: {status}")
        if status == "FAIL":
            exp_str = json.dumps(case.expected)[:80] if case.expected else "None"
            got_str = json.dumps(parsed)[:80] if parsed else "None"
            print(f"      expected: {exp_str}")
            print(f"      got:      {got_str}")

    elapsed = time.time() - start
    scores = compute_parse_score(results)

    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = sum(1 for r in results if r["status"] == "FAIL")

    print(f"\n{'='*50}")
    print(f"PARSE SCORE:     {scores['parse_score']:.4f}")
    print(f"  Exact Match:   {scores['exact_match']:.4f}")
    print(f"  Key Match:     {scores['key_match']:.4f}")
    print(f"  Parse Rate:    {scores['parse_rate']:.4f}")
    print(f"  Error Handling:{scores['error_handling']:.4f}")
    print(f"  Passed: {passed}/{len(results)}, Failed: {failed}")
    print(f"  Elapsed: {elapsed:.3f}s")
    print(f"\nCategory breakdown:")
    for cat, score in scores["category_scores"].items():
        print(f"  {cat:12s}: {score:.4f}")
    print(f"{'='*50}")

    # Append to history
    result_entry = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        **scores,
        "passed": passed,
        "failed": failed,
        "total": len(results),
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
