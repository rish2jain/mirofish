"""
AutoResearch experiment runner for simulation parameter optimization.

Usage:
    cd autoresearch/simulation_params && python3 train.py

NO LLM calls, no OASIS required. Uses a simulation proxy that estimates
output quality from parameters. Each run takes <1 second.

The proxy models:
- Expected total actions from agent activity levels and round counts
- Action diversity from action weight distributions
- Agent participation from activity levels and round budgets
- Posts-per-agent from posting rates and simulation duration
- Cost efficiency from total rounds * agents (compute proxy)
"""

import importlib.util
import json
import math
import os
import time
from typing import Any, Dict, List

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


def load_strategy():
    spec = importlib.util.spec_from_file_location(
        "param_strategy",
        os.path.join(SCRIPT_DIR, "configs", "param_strategy.py"),
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load_data():
    from prepare import load_scenarios
    return load_scenarios()


# ---------------------------------------------------------------------------
# Simulation proxy: estimate output metrics from parameters
# ---------------------------------------------------------------------------


def estimate_total_actions(
    params: Dict[str, Any],
    scenario_agents: Dict[str, int],
) -> float:
    """Estimate total unique actions the simulation would produce."""
    budget = params["round_budget"]
    activity = params["activity_levels"]
    total_rounds = budget["total_rounds"]
    time_cfg = params["time_config"]
    hours_per_round = time_cfg["minutes_per_round"] / 60.0

    total = 0.0
    for agent_type, count in scenario_agents.items():
        lvl = activity.get(agent_type, activity.get("general", {}))
        posts_h = lvl.get("posts_per_hour", 1.0)
        comments_h = lvl.get("comments_per_hour", 2.0)
        act_lvl = lvl.get("activity_level", 0.5)

        # Actions per agent per round
        actions_per_round = (posts_h + comments_h) * hours_per_round * act_lvl
        total += count * actions_per_round * total_rounds

    return total


def estimate_action_diversity(params: Dict[str, Any]) -> float:
    """Estimate action type diversity (Shannon entropy normalized to 0-1)."""
    weights = params["action_weights"]
    entropies = []

    for platform, action_weights in weights.items():
        values = [v for v in action_weights.values() if v > 0]
        if not values:
            continue
        total = sum(values)
        probs = [v / total for v in values]
        entropy = -sum(p * math.log2(p) for p in probs if p > 0)
        max_entropy = math.log2(len(probs)) if len(probs) > 1 else 1.0
        entropies.append(entropy / max_entropy if max_entropy > 0 else 0)

    return sum(entropies) / len(entropies) if entropies else 0.0


def estimate_agent_participation(
    params: Dict[str, Any],
    scenario_agents: Dict[str, int],
) -> float:
    """Estimate fraction of agents that would be active (non-idle)."""
    activity = params["activity_levels"]
    total_agents = sum(scenario_agents.values())
    if total_agents == 0:
        return 0.0

    active = 0.0
    for agent_type, count in scenario_agents.items():
        lvl = activity.get(agent_type, activity.get("general", {}))
        act = lvl.get("activity_level", 0.5)
        # Agents with activity > 0.2 are considered participating
        if act > 0.2:
            active += count
        else:
            active += count * 0.3  # Low-activity agents still participate somewhat

    return min(1.0, active / total_agents)


def estimate_posts_per_agent(
    params: Dict[str, Any],
    scenario_agents: Dict[str, int],
) -> float:
    """Estimate average posts per agent over the simulation."""
    activity = params["activity_levels"]
    time_cfg = params["time_config"]
    total_hours = time_cfg["total_simulation_hours"]

    total_posts = 0.0
    total_agents = sum(scenario_agents.values())
    if total_agents == 0:
        return 0.0

    for agent_type, count in scenario_agents.items():
        lvl = activity.get(agent_type, activity.get("general", {}))
        posts_h = lvl.get("posts_per_hour", 1.0)
        act = lvl.get("activity_level", 0.5)
        total_posts += count * posts_h * act * total_hours

    return total_posts / total_agents


def estimate_compute_cost(
    params: Dict[str, Any],
    num_agents: int,
) -> float:
    """Estimate relative compute cost (LLM calls ~ agents * rounds)."""
    budget = params["round_budget"]
    return num_agents * budget["total_rounds"]


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


def score_scenario(
    params: Dict[str, Any],
    scenario,
) -> Dict[str, float]:
    """Score parameters against a scenario's gold metrics."""
    gold = scenario.gold_metrics

    # Estimate metrics
    est_actions = estimate_total_actions(params, scenario.agent_types)
    est_diversity = estimate_action_diversity(params)
    est_participation = estimate_agent_participation(params, scenario.agent_types)
    est_posts_per_agent = estimate_posts_per_agent(params, scenario.agent_types)
    est_rounds = params["round_budget"]["total_rounds"]
    est_cost = estimate_compute_cost(params, scenario.num_agents)

    # Score each dimension (0-1, higher is better)

    # Action count: score based on meeting minimum threshold
    min_actions = gold["min_unique_actions"]
    action_score = min(1.0, est_actions / min_actions) if min_actions > 0 else 1.0
    # Penalty for extreme overshoot (waste)
    if est_actions > min_actions * 3:
        action_score *= 0.9

    # Diversity: direct comparison
    diversity_score = min(1.0, est_diversity / gold["min_action_diversity"]) \
        if gold["min_action_diversity"] > 0 else 1.0

    # Participation: direct comparison
    participation_score = min(1.0, est_participation / gold["min_agent_participation"]) \
        if gold["min_agent_participation"] > 0 else 1.0

    # Posts per agent: closeness to ideal (penalize both over and under)
    ideal_ppa = gold["ideal_posts_per_agent"]
    if ideal_ppa > 0:
        ratio = est_posts_per_agent / ideal_ppa
        ppa_score = 1.0 - min(1.0, abs(1.0 - ratio))
    else:
        ppa_score = 1.0

    # Round efficiency: closeness to ideal rounds
    ideal_rounds = gold["ideal_rounds"]
    if ideal_rounds > 0:
        ratio = est_rounds / ideal_rounds
        round_score = 1.0 - min(1.0, abs(1.0 - ratio) * 0.5)
    else:
        round_score = 1.0

    # Cost efficiency: lower is better (normalize by max expected)
    max_cost = scenario.num_agents * ideal_rounds * 5
    cost_score = max(0.0, 1.0 - (est_cost / max_cost)) if max_cost > 0 else 0.5

    return {
        "action_score": action_score,
        "diversity_score": diversity_score,
        "participation_score": participation_score,
        "ppa_score": ppa_score,
        "round_score": round_score,
        "cost_score": cost_score,
        "est_actions": est_actions,
        "est_diversity": est_diversity,
        "est_participation": est_participation,
        "est_posts_per_agent": est_posts_per_agent,
        "est_rounds": est_rounds,
        "est_cost": est_cost,
    }


def compute_sim_score(per_scenario: List[Dict[str, float]]) -> float:
    """
    Composite metric:
      0.20 * action_score      (meeting minimum action threshold)
    + 0.15 * diversity_score   (action type variety)
    + 0.20 * participation_score (agent engagement)
    + 0.15 * ppa_score         (posts-per-agent closeness to ideal)
    + 0.15 * round_score       (round count efficiency)
    + 0.15 * cost_score        (compute cost efficiency)
    """
    n = len(per_scenario)
    if n == 0:
        return 0.0

    def avg(key):
        return sum(s[key] for s in per_scenario) / n

    return (
        0.20 * avg("action_score")
        + 0.15 * avg("diversity_score")
        + 0.20 * avg("participation_score")
        + 0.15 * avg("ppa_score")
        + 0.15 * avg("round_score")
        + 0.15 * avg("cost_score")
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def run_experiment() -> Dict[str, Any]:
    strategy = load_strategy()
    scenarios = load_data()
    start = time.time()

    per_scenario = []

    for scenario in scenarios:
        params = strategy.generate_params(scenario.to_dict())
        scores = score_scenario(params, scenario)
        per_scenario.append(scores)

        composite = (
            0.20 * scores["action_score"]
            + 0.15 * scores["diversity_score"]
            + 0.20 * scores["participation_score"]
            + 0.15 * scores["ppa_score"]
            + 0.15 * scores["round_score"]
            + 0.15 * scores["cost_score"]
        )

        symbol = "+" if composite >= 0.6 else "x"
        print(
            f"  [{symbol}] {scenario.id}: "
            f"act={scores['action_score']:.2f} "
            f"div={scores['diversity_score']:.2f} "
            f"part={scores['participation_score']:.2f} "
            f"ppa={scores['ppa_score']:.2f} "
            f"rnd={scores['round_score']:.2f} "
            f"cost={scores['cost_score']:.2f} "
            f"=> {composite:.3f}"
        )
        print(
            f"        est: {scores['est_actions']:.0f} actions, "
            f"{scores['est_rounds']} rounds, "
            f"{scores['est_posts_per_agent']:.1f} posts/agent, "
            f"cost={scores['est_cost']:.0f}"
        )

    elapsed = time.time() - start
    score = compute_sim_score(per_scenario)

    n = len(per_scenario)

    def avg(key):
        if n == 0:
            return 0.0
        return sum(s[key] for s in per_scenario) / n

    print(f"\n{'='*55}")
    print(f"SIM PARAM SCORE:     {score:.4f}")
    print(f"  Action Score:      {avg('action_score'):.4f}")
    print(f"  Diversity Score:   {avg('diversity_score'):.4f}")
    print(f"  Participation:     {avg('participation_score'):.4f}")
    print(f"  Posts/Agent:       {avg('ppa_score'):.4f}")
    print(f"  Round Efficiency:  {avg('round_score'):.4f}")
    print(f"  Cost Efficiency:   {avg('cost_score'):.4f}")
    print(f"  Elapsed: {elapsed:.3f}s")
    print(f"{'='*55}")

    result_entry = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "sim_param_score": round(score, 4),
        "action_score": round(avg("action_score"), 4),
        "diversity_score": round(avg("diversity_score"), 4),
        "participation_score": round(avg("participation_score"), 4),
        "ppa_score": round(avg("ppa_score"), 4),
        "round_score": round(avg("round_score"), 4),
        "cost_score": round(avg("cost_score"), 4),
        "num_scenarios": len(scenarios),
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
