"""
Token cost estimator for LLM usage across CLI and API modes.

Provides approximate cost estimates from token counts and published model prices.
CLI mode estimates tokens from character counts (1 token ≈ 4 chars).
"""

import math
from dataclasses import dataclass

# Published list prices per 1M tokens (input, output), USD.
# Prices as of: 2025-03 — verify before relying on estimates; vendors change rates.
# Sources (check current pages when updating this table):
#   OpenAI: https://openai.com/api/pricing/
#   Anthropic: https://www.anthropic.com/pricing
#   Google (Gemini API): https://ai.google.dev/pricing
MODEL_PRICES = {
    # OpenAI
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4-turbo": (10.00, 30.00),
    "o1": (15.00, 60.00),
    "o1-mini": (3.00, 12.00),
    "o3-mini": (1.10, 4.40),
    # Anthropic
    "claude-sonnet-4-20250514": (3.00, 15.00),
    "claude-opus-4-20250514": (15.00, 75.00),
    "claude-haiku-3-5": (0.80, 4.00),
    # Google
    "gemini-2.5-pro": (1.25, 10.00),
    "gemini-2.5-flash": (0.15, 0.60),
    # CLI placeholders (subscription-based, cost is amortized)
    "claude": (0.0, 0.0),
    "codex": (0.0, 0.0),
    "gemini": (0.0, 0.0),
}

_ZERO_PRICES = (0.0, 0.0)
# Longest keys first for prefix/substring matching (built once; see _lookup_prices).
MODEL_PRICES_SORTED = sorted(
    [(k, v) for k, v in MODEL_PRICES.items() if v != _ZERO_PRICES],
    key=lambda kv: len(kv[0]),
    reverse=True,
)


@dataclass(frozen=True)
class CostEstimate:
    """Token usage and cost estimate for an operation."""

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    model: str
    input_cost_usd: float
    output_cost_usd: float
    total_cost_usd: float
    is_cli: bool
    note: str

    def to_dict(self):
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "model": self.model,
            "input_cost_usd": round(self.input_cost_usd, 6),
            "output_cost_usd": round(self.output_cost_usd, 6),
            "total_cost_usd": round(self.total_cost_usd, 6),
            "is_cli": self.is_cli,
            "note": self.note,
        }


def estimate_tokens_from_text(text: str) -> int:
    """Estimate token count from text (1 token ≈ 4 characters)."""
    if not text:
        return 0
    return max(1, math.ceil(len(text) / 4))


def _lookup_prices(model: str):
    """Find the best matching price entry for a model string."""
    model_lower = (model or "").lower()

    # Exact match
    if model_lower in MODEL_PRICES:
        return MODEL_PRICES[model_lower]

    # Longest keys first: prefer specific catalog IDs over shorter substrings.
    # Do not use reverse containment (model_lower in key): short names could
    # match longer keys (e.g. "o1" inside "o1-mini").
    for key, prices in MODEL_PRICES_SORTED:
        if model_lower.startswith(key) or key in model_lower:
            return prices

    # Unknown model — return zero
    return (0.0, 0.0)


def estimate_cost(
    prompt_tokens: int,
    completion_tokens: int,
    model: str,
    is_cli: bool = False,
) -> CostEstimate:
    """
    Estimate the cost for a given token usage.

    Args:
        prompt_tokens: Number of input tokens
        completion_tokens: Number of output tokens
        model: Model identifier
        is_cli: Whether this is a CLI-based provider

    Returns:
        CostEstimate with breakdown
    """
    input_price, output_price = _lookup_prices(model)
    total_tokens = prompt_tokens + completion_tokens

    input_cost = (prompt_tokens / 1_000_000) * input_price
    output_cost = (completion_tokens / 1_000_000) * output_price
    total_cost = input_cost + output_cost

    note = ""
    if is_cli:
        note = (
            "CLI subscription — no per-token cost. "
            "Token estimate is approximate."
        )
        total_cost = 0.0
        input_cost = 0.0
        output_cost = 0.0
    elif input_price == 0.0 and output_price == 0.0:
        note = f"Unknown model pricing for '{model}'. Cost shown as $0."

    return CostEstimate(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        model=model,
        input_cost_usd=input_cost,
        output_cost_usd=output_cost,
        total_cost_usd=total_cost,
        is_cli=is_cli,
        note=note,
    )


def estimate_simulation_cost(
    num_agents: int,
    num_rounds: int,
    model: str,
    is_cli: bool = False,
    avg_prompt_tokens_per_call: int = 800,
    avg_completion_tokens_per_call: int = 200,
) -> CostEstimate:
    """
    Estimate total cost for a simulation run.

    Each agent makes approximately 1 LLM call per round.

    Args:
        num_agents: Number of simulated agents
        num_rounds: Number of simulation rounds
        model: Model identifier
        is_cli: Whether using CLI provider
        avg_prompt_tokens_per_call: Average prompt tokens per LLM call
        avg_completion_tokens_per_call: Average completion tokens per LLM call

    Returns:
        CostEstimate for the full simulation
    """
    total_calls = num_agents * num_rounds
    total_prompt = total_calls * avg_prompt_tokens_per_call
    total_completion = total_calls * avg_completion_tokens_per_call

    return estimate_cost(
        prompt_tokens=total_prompt,
        completion_tokens=total_completion,
        model=model,
        is_cli=is_cli,
    )
