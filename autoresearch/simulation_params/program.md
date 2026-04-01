# AutoResearch: Simulation Parameter Optimization

## Objective

Optimize the simulation parameter strategy in `configs/param_strategy.py` to
maximize "information richness" of OASIS simulation output while staying within
reasonable compute budgets. The strategy decides time config, activity levels,
action distributions, platform weights, and round budgeting for different
scenario types.

## How It Works

1. Read this file for research directions.
2. Modify **only** `configs/param_strategy.py`.
3. Run `python3 train.py` — evaluates parameters against 5 scenario types
   using a simulation proxy (no OASIS needed).
4. Score is appended to `results/history.jsonl`.
5. Decide keep/revert based on the metric.

**No LLM calls, no OASIS needed.** Each run takes <1 second.

## Metric: sim_param_score

```
sim_param_score = 0.20 * action_score
                + 0.15 * diversity_score
                + 0.20 * participation_score
                + 0.15 * ppa_score
                + 0.15 * round_score
                + 0.15 * cost_score
```

- **action_score**: Meeting minimum total action thresholds
- **diversity_score**: Shannon entropy of action type distribution
- **participation_score**: Fraction of agents actively participating
- **ppa_score**: Closeness to ideal posts-per-agent
- **round_score**: Closeness to ideal round count
- **cost_score**: Compute efficiency (agents * rounds)

## Scenarios

| ID | Agents | Urgency | Hours | Topic |
|----|--------|---------|-------|-------|
| regulatory_fast | 15 | high | 48 | regulatory |
| crisis_comms | 20 | critical | 72 | crisis |
| ma_reaction | 18 | medium | 120 | financial |
| geopolitical | 25 | high | 168 | geopolitical |
| small_focused | 8 | low | 24 | niche |

Each has gold metrics: min_unique_actions, min_action_diversity,
min_agent_participation, ideal_posts_per_agent, ideal_rounds.

## Research Directions

### Round 1-5: Time config tuning
- Adjust minutes_per_round for each urgency level
- Test shorter rounds for crisis (15-20 min) vs current 30 min
- Test longer rounds for low urgency (120 min) to save compute
- Adjust total_simulation_hours based on agent count (more agents = shorter)

### Round 6-10: Activity level optimization
- Differentiate activity levels more aggressively by agent type
- Journalists should be much more active during crises
- Officials should post less frequently but with higher influence
- Test "burst" patterns: high initial activity that tapers off

### Round 11-15: Action distribution
- Increase CREATE_POST weight for crisis scenarios
- Increase REPOST/QUOTE_POST for viral topics
- Reduce DO_NOTHING in high-urgency scenarios
- Test topic-specific distributions (financial -> more SEARCH_POSTS)

### Round 16-20: Platform balancing
- Adjust viral_threshold by scenario (lower for crises)
- Tune echo_chamber_strength by topic (higher for geopolitical)
- Test asymmetric platform configs (Twitter for breaking, Reddit for analysis)
- Adjust recency_weight dynamically (higher early, lower later)

### Round 21+: Cross-scenario optimization
- Find parameters that work well across ALL scenarios, not just one
- Test agent count scaling formulas (activity inversely proportional to count)
- Implement adaptive round budgeting (more rounds when action count is low)
- Optimize the cost/quality tradeoff frontier

## Constraints

- **Only modify** `configs/param_strategy.py`
- No external dependencies (stdlib only)
- Functions must keep their signatures
- Keep module under 400 lines
- `generate_params()` must return a dict with keys:
  time_config, activity_levels, platform_config, action_weights, round_budget

## Key Insight

The biggest lever is the **minutes_per_round** / **total_rounds** tradeoff.
More rounds = more actions but higher cost. The sweet spot is scenario-dependent.
The second lever is **activity_level** per agent type — getting this right
determines whether all agents participate or some go idle.
