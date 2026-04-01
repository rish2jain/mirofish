"""
Prepare eval data for simulation parameter autoresearch.

Run once to verify:
    python3 prepare.py

Also imported by train.py.
"""

import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List

EVAL_DIR = os.path.join(os.path.dirname(__file__), "eval_data")


@dataclass
class Scenario:
    id: str
    name: str
    description: str
    num_agents: int
    topic_type: str
    urgency: str
    expected_duration_hours: int
    agent_types: Dict[str, int]
    gold_metrics: Dict[str, float]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "num_agents": self.num_agents,
            "topic_type": self.topic_type,
            "urgency": self.urgency,
            "expected_duration_hours": self.expected_duration_hours,
            "agent_types": self.agent_types,
            "gold_metrics": self.gold_metrics,
        }


def load_scenarios() -> List[Scenario]:
    path = os.path.join(EVAL_DIR, "scenarios.json")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [
        Scenario(
            id=s["id"],
            name=s["name"],
            description=s["description"],
            num_agents=s["num_agents"],
            topic_type=s["topic_type"],
            urgency=s["urgency"],
            expected_duration_hours=s["expected_duration_hours"],
            agent_types=s["agent_types"],
            gold_metrics=s["gold_metrics"],
        )
        for s in data
    ]


if __name__ == "__main__":
    scenarios = load_scenarios()
    print(f"Loaded {len(scenarios)} scenarios:")
    for s in scenarios:
        print(
            f"  {s.id}: {s.num_agents} agents, {s.urgency} urgency, "
            f"{s.expected_duration_hours}h, {s.topic_type}"
        )
    print("All eval data OK.")
