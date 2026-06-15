"""Token usage tracking and cost estimation for LLM API calls."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import tiktoken


@dataclass
class ModelPricing:
    input_per_million: float
    output_per_million: float
    cache_read_per_million: float
    cache_write_per_million: float

    @property
    def input_per_token(self) -> float:
        return self.input_per_million / 1_000_000

    @property
    def output_per_token(self) -> float:
        return self.output_per_million / 1_000_000

    @property
    def cache_read_per_token(self) -> float:
        return self.cache_read_per_million / 1_000_000

    @property
    def cache_write_per_token(self) -> float:
        return self.cache_write_per_million / 1_000_000


PRICING: dict[str, ModelPricing] = {
    "claude-3.5-sonnet": ModelPricing(
        input_per_million=3.00,
        output_per_million=15.00,
        cache_read_per_million=0.30,
        cache_write_per_million=3.75,
    ),
    "claude-3-opus": ModelPricing(
        input_per_million=15.00,
        output_per_million=75.00,
        cache_read_per_million=1.50,
        cache_write_per_million=18.75,
    ),
    "claude-3-haiku": ModelPricing(
        input_per_million=0.25,
        output_per_million=1.25,
        cache_read_per_million=0.03,
        cache_write_per_million=0.30,
    ),
    "gpt-4": ModelPricing(
        input_per_million=30.00,
        output_per_million=60.00,
        cache_read_per_million=0.00,
        cache_write_per_million=0.00,
    ),
    "gpt-4o": ModelPricing(
        input_per_million=2.50,
        output_per_million=10.00,
        cache_read_per_million=1.25,
        cache_write_per_million=0.00,
    ),
    "gpt-4o-mini": ModelPricing(
        input_per_million=0.15,
        output_per_million=0.60,
        cache_read_per_million=0.075,
        cache_write_per_million=0.00,
    ),
    "qwen3-coder": ModelPricing(
        input_per_million=0.50,
        output_per_million=2.00,
        cache_read_per_million=0.10,
        cache_write_per_million=0.50,
    ),
}

TIKTOKEN_MODEL_MAP: dict[str, str] = {
    "claude-3.5-sonnet": "cl100k_base",
    "claude-3-opus": "cl100k_base",
    "claude-3-haiku": "cl100k_base",
    "gpt-4": "cl100k_base",
    "gpt-4o": "o200k_base",
    "gpt-4o-mini": "o200k_base",
    "qwen3-coder": "cl100k_base",
}

DEFAULT_ENCODING = "cl100k_base"


def _get_encoding(model: str) -> Any:
    encoding_name = TIKTOKEN_MODEL_MAP.get(model, DEFAULT_ENCODING)
    return tiktoken.get_encoding(encoding_name)


def count_tokens(text: str, model: str = "gpt-4") -> int:
    """Count the number of tokens in *text* for the given *model*.

    Falls back to ``cl100k_base`` for unknown models.
    """
    encoding = _get_encoding(model)
    return len(encoding.encode(text))


def estimate_cost(
    input_tokens: int,
    output_tokens: int,
    model: str = "gpt-4",
    cache_read: int = 0,
    cache_creation: int = 0,
) -> CostBreakdown:
    """Return a ``CostBreakdown`` for a single API call.

    Unknown model names fall back to GPT-4 pricing.
    """
    pricing = PRICING.get(model, PRICING["gpt-4"])

    input_cost = input_tokens * pricing.input_per_token
    output_cost = output_tokens * pricing.output_per_token
    cache_read_cost = cache_read * pricing.cache_read_per_token
    cache_creation_cost = cache_creation * pricing.cache_write_per_token

    cache_total = cache_read_cost + cache_creation_cost
    total = input_cost + output_cost + cache_total

    return CostBreakdown(
        input_cost=input_cost,
        output_cost=output_cost,
        cache_read_cost=cache_read_cost,
        cache_creation_cost=cache_creation_cost,
        cache_cost=cache_total,
        total_cost=total,
        model=model,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read_tokens=cache_read,
        cache_creation_tokens=cache_creation,
    )


@dataclass
class CostBreakdown:
    input_cost: float
    output_cost: float
    cache_read_cost: float
    cache_creation_cost: float
    cache_cost: float
    total_cost: float
    model: str
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_creation_tokens: int

    def __str__(self) -> str:
        lines = [
            f"Model:           {self.model}",
            f"Input tokens:    {self.input_tokens:>10,}  (${self.input_cost:.6f})",
            f"Output tokens:   {self.output_tokens:>10,}  (${self.output_cost:.6f})",
            f"Cache read:      {self.cache_read_tokens:>10,}  (${self.cache_read_cost:.6f})",
            f"Cache creation:  {self.cache_creation_tokens:>10,}  (${self.cache_creation_cost:.6f})",
            "─────────────────────────────────────",
            f"Total:           ${self.total_cost:.6f}",
        ]
        return "\n".join(lines)


def format_cost_table(breakdowns: list[CostBreakdown]) -> str:
    """Pretty-print a table of multiple cost breakdowns."""
    if not breakdowns:
        return "No data."

    total_input = sum(b.input_tokens for b in breakdowns)
    total_output = sum(b.output_tokens for b in breakdowns)
    total_cache_read = sum(b.cache_read_tokens for b in breakdowns)
    total_cache_creation = sum(b.cache_creation_tokens for b in breakdowns)
    grand_total = sum(b.total_cost for b in breakdowns)

    rows = [
        f"{'Model':<20} {'Input':>10} {'Output':>10} {'Cache R':>10} {'Cache W':>10} {'Cost':>12}",
        f"{'─'*20} {'─'*10} {'─'*10} {'─'*10} {'─'*10} {'─'*12}",
    ]
    for b in breakdowns:
        rows.append(
            f"{b.model:<20} {b.input_tokens:>10,} {b.output_tokens:>10,} "
            f"{b.cache_read_tokens:>10,} {b.cache_creation_tokens:>10,} ${b.total_cost:>11.6f}"
        )
    rows.append(f"{'─'*20} {'─'*10} {'─'*10} {'─'*10} {'─'*10} {'─'*12}")
    rows.append(
        f"{'TOTAL':<20} {total_input:>10,} {total_output:>10,} "
        f"{total_cache_read:>10,} {total_cache_creation:>10,} ${grand_total:>11.6f}"
    )
    return "\n".join(rows)
