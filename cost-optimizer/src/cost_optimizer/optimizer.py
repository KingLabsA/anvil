"""Cost optimization strategies."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from cost_optimizer.analyzer import TokenAnalyzer, TokenReport
from cost_optimizer.pricing import PricingData


@dataclass
class Optimization:
    """A single optimization recommendation."""

    strategy: str           # e.g. "cache_repeated_reads", "route_to_cheaper_model"
    description: str
    estimated_savings_usd: float
    estimated_savings_pct: float
    effort: str             # "low", "medium", "high"
    priority: str          # "critical", "high", "medium", "low"
    implementation: str = ""
    affected_waste_items: list[int] = field(default_factory=list)

    def __str__(self) -> str:
        return (f"[{self.priority.upper()}] {self.strategy}: {self.description} "
                f"(saves ${self.estimated_savings_usd:.2f}, {self.estimated_savings_pct:.1f}%, "
                f"effort: {self.effort})")


class CostOptimizer:
    """Generate optimization recommendations from token analysis."""

    def __init__(self, default_model: str = "claude-3-5-sonnet-20241022") -> None:
        self.default_model = default_model
        self._analyzer = TokenAnalyzer(default_model=default_model)
        self._pricing = PricingData()

    def optimize(self, token_report: TokenReport) -> list[Optimization]:
        """Generate optimization recommendations from a token report.

        Args:
            token_report: The token analysis report.

        Returns:
            Sorted list of Optimization recommendations.
        """
        optimizations: list[Optimization] = []

        waste_by_type = token_report.waste_by_type
        total_cost = token_report.total_cost_usd

        if total_cost == 0:
            return optimizations

        redundant_read_items = [w for w in token_report.waste_items if w.waste_type == "redundant_read"]
        if redundant_read_items:
            savings = sum(w.cost_wasted_usd for w in redundant_read_items)
            avg_reads = sum(len(w.turn_indices) for w in redundant_read_items) / len(redundant_read_items)
            optimizations.append(Optimization(
                strategy="cache_repeated_reads",
                description=f"Cache file reads. Found {len(redundant_read_items)} files read {avg_reads:.1f}x on average.",
                estimated_savings_usd=savings,
                estimated_savings_pct=savings / total_cost * 100,
                effort="low",
                priority="high" if savings / total_cost > 0.10 else "medium",
                implementation="Implement a file-content cache that stores read results for the session duration. "
                                "Before reading a file, check the cache first. Invalidate on edit operations.",
                affected_waste_items=[i for i, w in enumerate(token_report.waste_items) if w.waste_type == "redundant_read"],
            ))

        over_verification_items = [w for w in token_report.waste_items if w.waste_type == "over_verification"]
        if over_verification_items:
            savings = sum(w.cost_wasted_usd for w in over_verification_items)
            optimizations.append(Optimization(
                strategy="reduce_verification_loops",
                description=f"Reduce post-edit verification. Found {len(over_verification_items)} unnecessary re-reads.",
                estimated_savings_usd=savings,
                estimated_savings_pct=savings / total_cost * 100,
                effort="low",
                priority="high" if savings / total_cost > 0.10 else "medium",
                implementation="Use strict/surgical edit operations and skip the verify-read step. "
                                "Only verify when edits affect critical sections.",
                affected_waste_items=[i for i, w in enumerate(token_report.waste_items) if w.waste_type == "over_verification"],
            ))

        repeated_tool_items = [w for w in token_report.waste_items if w.waste_type == "repeated_tool"]
        if repeated_tool_items:
            savings = sum(w.cost_wasted_usd for w in repeated_tool_items)
            optimizations.append(Optimization(
                strategy="deduplicate_tool_calls",
                description=f"Deduplicate tool calls. Found {len(repeated_tool_items)} tools called with identical args.",
                estimated_savings_usd=savings,
                estimated_savings_pct=savings / total_cost * 100,
                effort="medium",
                priority="medium",
                implementation="Add a tool-result cache keyed by (tool_name, args_hash). "
                                "Return cached results for duplicate calls within the same session.",
                affected_waste_items=[i for i, w in enumerate(token_report.waste_items) if w.waste_type == "repeated_tool"],
            ))

        excessive_context_items = [w for w in token_report.waste_items if w.waste_type == "excessive_context"]
        if excessive_context_items:
            savings = sum(w.cost_wasted_usd for w in excessive_context_items)
            optimizations.append(Optimization(
                strategy="compress_context",
                description=f"Compress context. Found {len(excessive_context_items)} turns with 3x+ average context.",
                estimated_savings_usd=savings,
                estimated_savings_pct=savings / total_cost * 100,
                effort="medium",
                priority="high" if savings / total_cost > 0.20 else "medium",
                implementation="Summarize earlier conversation turns when context exceeds a threshold. "
                                "Use a sliding window with summarization instead of full context accumulation.",
                affected_waste_items=[i for i, w in enumerate(token_report.waste_items) if w.waste_type == "excessive_context"],
            ))

        model_router_savings = self._calculate_model_routing_savings(token_report)
        if model_router_savings > 0:
            optimizations.append(Optimization(
                strategy="route_to_cheaper_model",
                description=f"Route simple tasks to cheaper models. Estimated {model_router_savings / total_cost * 100:.1f}% savings.",
                estimated_savings_usd=model_router_savings,
                estimated_savings_pct=model_router_savings / total_cost * 100,
                effort="medium",
                priority="high" if model_router_savings / total_cost > 0.30 else "medium",
                implementation="Implement a task-complexity router: simple queries → Claude 3.5 Haiku, "
                               "moderate tasks → Claude 3.5 Sonnet, complex reasoning → Claude 3 Opus.",
            ))

        optimizations.sort(key=lambda o: {"critical": 0, "high": 1, "medium": 2, "low": 3}[o.priority])
        return optimizations

    def _calculate_model_routing_savings(self, report: TokenReport) -> float:
        """Estimate savings from routing simple tasks to cheaper models."""
        cheap_model = self._pricing.get_model("claude-3-5-haiku-20241022")
        current_model = self._pricing.get_model(self.default_model)

        if not cheap_model or not current_model:
            return 0.0

        current_cost = current_model.calculate_cost(report.total_input_tokens, report.total_output_tokens)

        simple_fraction = 0.30
        simple_input = int(report.total_input_tokens * simple_fraction)
        simple_output = int(report.total_output_tokens * simple_fraction)

        cheap_cost = cheap_model.calculate_cost(simple_input, simple_output)
        remaining_input = report.total_input_tokens - simple_input
        remaining_output = report.total_output_tokens - simple_output
        remaining_cost = current_model.calculate_cost(remaining_input, remaining_output)

        blended_cost = cheap_cost + remaining_cost
        savings = current_cost - blended_cost
        return max(0, savings)

    def optimize_trace(self, traces: str | list[dict[str, Any]]) -> list[Optimization]:
        """Convenience method: analyze and optimize in one step."""
        report = self._analyzer.analyze_trace(traces)
        return self.optimize(report)
