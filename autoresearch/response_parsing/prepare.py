"""
Prepare eval data for the response parsing autoresearch loop.

Run once to verify the eval corpus:
    python prepare.py

Also imported by train.py.
"""

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

EVAL_DIR = os.path.join(os.path.dirname(__file__), "eval_data")


@dataclass
class ParseCase:
    id: str
    description: str
    raw: str
    expected: Optional[Dict[str, Any]]
    category: str


def load_cases() -> List[ParseCase]:
    path = os.path.join(EVAL_DIR, "responses.json")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [
        ParseCase(
            id=c["id"],
            description=c["description"],
            raw=c["raw"],
            expected=c.get("expected"),
            category=c["category"],
        )
        for c in data
    ]


if __name__ == "__main__":
    cases = load_cases()
    by_category: Dict[str, int] = {}
    for c in cases:
        by_category[c.category] = by_category.get(c.category, 0) + 1
    print(f"Loaded {len(cases)} test cases:")
    for cat, count in sorted(by_category.items()):
        print(f"  {cat}: {count}")
    expect_success = sum(1 for c in cases if c.expected is not None)
    expect_fail = sum(1 for c in cases if c.expected is None)
    print(f"\nExpected success: {expect_success}, expected failure: {expect_fail}")
    print("All eval data OK.")
