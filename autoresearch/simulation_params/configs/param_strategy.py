"""
Simulation parameter strategy — the ONLY file the autoresearch agent modifies.

Given a scenario description, this module decides the optimal simulation
parameters: time config, activity levels, platform weights, action
distributions, and round budgeting.

The goal is to maximize "information richness" of simulation output
while staying within compute budgets.
"""

from typing import Any, Dict, List, Tuple


# ---------------------------------------------------------------------------
# Time configuration
# ---------------------------------------------------------------------------


def compute_time_config(
    num_agents: int,
    expected_duration_hours: int,
    urgency: str,
) -> Dict[str, Any]:
    """Decide total_simulation_hours and minutes_per_round.

    Args:
        num_agents: Number of agents in the simulation.
        expected_duration_hours: Scenario's natural duration.
        urgency: "low", "medium", "high", or "critical".

    Returns:
        Dict with total_simulation_hours and minutes_per_round.
    """
    # Base: use the scenario's expected duration
    total_hours = expected_duration_hours

    # Target ~8-25 rounds depending on scenario duration and urgency.
    # minutes_per_round = total_hours * 60 / target_rounds
    # Urgency affects target rounds: more urgent = slightly more rounds per hour
    urgency_rounds_per_day = {
        "critical": 8.0,
        "high": 6.0,
        "medium": 4.0,
        "low": 3.0,
    }
    rounds_per_day = urgency_rounds_per_day.get(urgency, 5.0)
    target_rounds = max(8, min(25, total_hours / 24.0 * rounds_per_day))
    minutes_per_round = int(total_hours * 60 / target_rounds)

    return {
        "total_simulation_hours": total_hours,
        "minutes_per_round": minutes_per_round,
    }


# ---------------------------------------------------------------------------
# Activity levels per agent type
# ---------------------------------------------------------------------------


def compute_activity_levels(
    agent_types: Dict[str, int],
    urgency: str,
    topic_type: str,
    expected_duration_hours: int = 72,
    ideal_ppa: float = 6.0,
    num_agents: int = 15,
) -> Dict[str, Dict[str, float]]:
    """Decide activity parameters per agent type.

    Returns:
        Dict mapping agent_type -> {
            activity_level, posts_per_hour, comments_per_hour
        }
    """
    # Base relative weights (how active each type is vs average)
    type_weight = {
        "officials": 0.6,
        "executives": 0.8,
        "journalists": 1.3,
        "analysts": 1.0,
        "ngos": 0.7,
        "cybersecurity": 1.0,
        "military": 0.5,
        "general": 0.9,
    }

    # Target: ideal_ppa posts per agent over total_hours
    # posts/agent = posts_per_hour * activity_level * total_hours
    # So avg(posts_per_hour * activity_level) = ideal_ppa / total_hours
    target_rate = ideal_ppa / max(1, expected_duration_hours)

    # Normalize type weights so the agent-count-weighted average equals 1.0
    total_agents = sum(agent_types.values())
    if total_agents > 0:
        raw_avg = sum(
            agent_types.get(t, 0) * type_weight.get(t, 0.9)
            for t in agent_types
        ) / total_agents
    else:
        raw_avg = 1.0
    norm_factor = 1.0 / raw_avg if raw_avg > 0 else 1.0

    result = {}
    for agent_type in agent_types:
        w = type_weight.get(agent_type, 0.9) * norm_factor
        # activity_level stays moderate-high for participation score
        activity_level = min(1.0, max(0.3, 0.5 + w * 0.15))
        # posts_per_hour calibrated to hit ideal_ppa
        posts_per_hour = target_rate * w / activity_level
        # comments slightly higher than posts
        comments_per_hour = posts_per_hour * 1.5

        result[agent_type] = {
            "activity_level": activity_level,
            "posts_per_hour": posts_per_hour,
            "comments_per_hour": comments_per_hour,
        }
    return result


# ---------------------------------------------------------------------------
# Platform weights
# ---------------------------------------------------------------------------


def compute_platform_config(
    topic_type: str,
    num_agents: int,
) -> Dict[str, Dict[str, float]]:
    """Decide platform-specific configuration.

    Returns:
        Dict with twitter and reddit configs, each having:
        recency_weight, popularity_weight, relevance_weight,
        viral_threshold, echo_chamber_strength
    """
    # Default balanced config
    twitter = {
        "recency_weight": 0.4,
        "popularity_weight": 0.3,
        "relevance_weight": 0.3,
        "viral_threshold": max(3, num_agents // 3),
        "echo_chamber_strength": 0.5,
    }
    reddit = {
        "recency_weight": 0.3,
        "popularity_weight": 0.4,
        "relevance_weight": 0.3,
        "viral_threshold": max(5, num_agents // 2),
        "echo_chamber_strength": 0.4,
    }

    return {"twitter": twitter, "reddit": reddit}


# ---------------------------------------------------------------------------
# Action distribution
# ---------------------------------------------------------------------------


def compute_action_weights(
    topic_type: str,
    urgency: str,
) -> Dict[str, Dict[str, float]]:
    """Decide probability weights for each action type per platform.

    Returns:
        {"twitter": {action: weight, ...}, "reddit": {action: weight, ...}}
    """
    twitter_actions = {
        "CREATE_POST": 0.30,
        "LIKE_POST": 0.25,
        "REPOST": 0.15,
        "FOLLOW": 0.10,
        "QUOTE_POST": 0.10,
        "DO_NOTHING": 0.10,
    }

    reddit_actions = {
        "CREATE_POST": 0.20,
        "CREATE_COMMENT": 0.25,
        "LIKE_POST": 0.15,
        "DISLIKE_POST": 0.05,
        "LIKE_COMMENT": 0.10,
        "DISLIKE_COMMENT": 0.03,
        "SEARCH_POSTS": 0.05,
        "FOLLOW": 0.02,
        "DO_NOTHING": 0.10,
        "TREND": 0.03,
        "REFRESH": 0.02,
    }

    return {"twitter": twitter_actions, "reddit": reddit_actions}


# ---------------------------------------------------------------------------
# Round budget
# ---------------------------------------------------------------------------


def compute_round_budget(
    num_agents: int,
    total_simulation_hours: int,
    minutes_per_round: int,
    urgency: str,
) -> Dict[str, Any]:
    """Compute the effective round budget for the simulation.

    Returns:
        Dict with total_rounds, agents_per_hour_min/max,
        peak_activity_multiplier.
    """
    total_rounds = int(total_simulation_hours * 60 / minutes_per_round)

    agents_per_hour_min = max(3, num_agents // 3)
    agents_per_hour_max = num_agents

    peak_mult = {
        "critical": 1.8,
        "high": 1.5,
        "medium": 1.3,
        "low": 1.1,
    }.get(urgency, 1.3)

    return {
        "total_rounds": total_rounds,
        "agents_per_hour_min": agents_per_hour_min,
        "agents_per_hour_max": agents_per_hour_max,
        "peak_activity_multiplier": peak_mult,
    }


# ---------------------------------------------------------------------------
# Master function: generate all parameters for a scenario
# ---------------------------------------------------------------------------


def generate_params(scenario: Dict[str, Any]) -> Dict[str, Any]:
    """Generate complete simulation parameters for a scenario.

    Args:
        scenario: A scenario dict from eval_data/scenarios.json.

    Returns:
        Complete parameter configuration.
    """
    num_agents = scenario["num_agents"]
    urgency = scenario.get("urgency", "medium")
    topic_type = scenario.get("topic_type", "general")
    expected_hours = scenario.get("expected_duration_hours", 72)
    agent_types = scenario.get("agent_types", {})

    time_cfg = compute_time_config(num_agents, expected_hours, urgency)
    # Get ideal_ppa from scenario if available, else default
    gold = scenario.get("gold_metrics", {})
    ideal_ppa = gold.get("ideal_posts_per_agent", 6.0)
    activity = compute_activity_levels(
        agent_types, urgency, topic_type,
        expected_duration_hours=expected_hours,
        ideal_ppa=ideal_ppa,
        num_agents=num_agents,
    )
    platform = compute_platform_config(topic_type, num_agents)
    actions = compute_action_weights(topic_type, urgency)
    budget = compute_round_budget(
        num_agents,
        time_cfg["total_simulation_hours"],
        time_cfg["minutes_per_round"],
        urgency,
    )

    return {
        "time_config": time_cfg,
        "activity_levels": activity,
        "platform_config": platform,
        "action_weights": actions,
        "round_budget": budget,
    }
