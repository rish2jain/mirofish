"""
Prepare eval data for the autoresearch prompt optimization loop.

Run once to verify the eval corpus is intact:
    uv run python prepare.py

This module is also imported by train.py.
"""

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

EVAL_DIR = os.path.join(os.path.dirname(__file__), "eval_data")

# (document text file, gold standard file)
EVAL_PAIRS: List[Tuple[str, str]] = [
    ("doc_1_regulatory.txt", "doc_1_gold.json"),
    ("doc_2_crisis.txt", "doc_2_gold.json"),
    ("doc_3_ma.txt", "doc_3_gold.json"),
]


@dataclass
class EvalCase:
    name: str
    text: str
    gold_entities: List[Dict[str, str]]
    gold_relationships: List[Dict[str, str]]


def load_ontology() -> Dict[str, Any]:
    path = os.path.join(EVAL_DIR, "ontology.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def format_entity_types(ontology: Dict[str, Any]) -> str:
    lines = []
    for et in ontology.get("entity_types", []):
        name = et.get("name", "Unknown")
        desc = et.get("description", "")
        attrs = et.get("attributes", [])
        attr_names = [a.get("name", "") for a in attrs]
        line = f"- **{name}**: {desc}"
        if attr_names:
            line += f" (attributes: {', '.join(attr_names)})"
        lines.append(line)
    return "\n".join(lines) if lines else "No entity types defined."


def format_edge_types(ontology: Dict[str, Any]) -> str:
    lines = []
    for et in ontology.get("edge_types", []):
        name = et.get("name", "Unknown")
        desc = et.get("description", "")
        sources = []
        for st in et.get("source_targets", []):
            sources.append(
                f"{st.get('source', '?')} -> {st.get('target', '?')}"
            )
        line = f"- **{name}**: {desc}"
        if sources:
            line += f" ({', '.join(sources)})"
        lines.append(line)
    return "\n".join(lines) if lines else "No relationship types defined."


def load_eval_cases() -> List[EvalCase]:
    cases = []
    for text_file, gold_file in EVAL_PAIRS:
        text_path = os.path.join(EVAL_DIR, text_file)
        gold_path = os.path.join(EVAL_DIR, gold_file)

        with open(text_path, "r", encoding="utf-8") as f:
            text = f.read().strip()
        with open(gold_path, "r", encoding="utf-8") as f:
            gold = json.load(f)

        cases.append(
            EvalCase(
                name=text_file,
                text=text,
                gold_entities=gold.get("entities", []),
                gold_relationships=gold.get("relationships", []),
            )
        )
    return cases


if __name__ == "__main__":
    ontology = load_ontology()
    cases = load_eval_cases()
    print(f"Ontology: {len(ontology['entity_types'])} entity types, "
          f"{len(ontology['edge_types'])} edge types")
    for case in cases:
        print(
            f"  {case.name}: {len(case.text)} chars, "
            f"{len(case.gold_entities)} gold entities, "
            f"{len(case.gold_relationships)} gold relationships"
        )
    print("\nFormatted entity types:")
    print(format_entity_types(ontology))
    print("\nFormatted edge types:")
    print(format_edge_types(ontology))
    print("\nAll eval data OK.")
