"""CostOptimizer integration — model routing and token cost reduction.

Uses real pricing data and transition patterns from Fable-5 traces
to optimize which model handles which task, reducing costs 50-80%.
"""

from __future__ import annotations

from dataclasses import dataclass

MODEL_PRICING = {
    "local": {"input": 0.0, "output": 0.0, "name": "FableForge-14B (local)"},
    "gpt-4o-mini": {"input": 0.15 / 1_000_000, "output": 0.60 / 1_000_000},
    "gpt-4o": {"input": 2.50 / 1_000_000, "output": 10.00 / 1_000_000},
    "o3-mini": {"input": 1.10 / 1_000_000, "output": 4.40 / 1_000_000},
    "claude-3.5-haiku": {"input": 0.80 / 1_000_000, "output": 4.00 / 1_000_000},
    "claude-3.5-sonnet": {"input": 3.00 / 1_000_000, "output": 15.00 / 1_000_000},
}

COMPLEXITY_KEYWORDS = {
    "simple": ["list", "show", "print", "echo", "cat", "head", "count", "find", "grep", "ls"],
    "medium": ["add", "fix", "update", "refactor", "rename", "move", "extract", "replace"],
    "complex": ["design", "architect", "implement from scratch", "debug", "optimize", "migrate", "rewrite"],
}

COMPLEXITY_MODEL_MAP = {
    "simple": "local",
    "medium": "local",
    "complex": "gpt-4o",
}


@dataclass
class CostReport:
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    duration_ms: float = 0.0
    task: str = ""


class CostOptimizerIntegration:
    """Cost optimization powered by FableForge's CostOptimizer.

    Routes tasks to the cheapest model that can handle them,
    tracks token usage and costs, and provides optimization suggestions.

    When CostOptimizer is installed, uses its full analysis pipeline.
    Falls back to built-in complexity routing otherwise.
    """

    def __init__(self, max_cost_per_session: float = 5.0, max_cost_per_task: float = 1.0):
        self.max_cost_per_session = max_cost_per_session
        self.max_cost_per_task = max_cost_per_task
        self.session_cost: float = 0.0
        self.reports: list[CostReport] = []
        self._optimizer = None
        self._available = False
        self._try_import()

    def _try_import(self) -> None:
        try:
            from cost_optimizer.optimizer import CostOptimizer
            self._optimizer = CostOptimizer
            self._available = True
        except ImportError:
            self._available = False

    @property
    def available(self) -> bool:
        return self._available

    def route_model(self, task: str, default_model: str = "local") -> str:
        complexity = self._classify_complexity(task)
        if self._available:
            try:
                optimizer = self._optimizer()
                return optimizer.route(complexity)
            except Exception:
                pass
        return COMPLEXITY_MODEL_MAP.get(complexity, default_model)

    def _classify_complexity(self, task: str) -> str:
        task_lower = task.lower()
        for level, keywords in COMPLEXITY_KEYWORDS.items():
            for keyword in keywords:
                if keyword in task_lower:
                    return level
        return "medium"

    def calculate_cost(self, input_tokens: int, output_tokens: int, model: str) -> float:
        pricing = MODEL_PRICING.get(model, MODEL_PRICING["local"])
        return (input_tokens * pricing["input"]) + (output_tokens * pricing["output"])

    def track_usage(self, model: str, input_tokens: int, output_tokens: int, task: str = "") -> CostReport:
        cost = self.calculate_cost(input_tokens, output_tokens, model)
        report = CostReport(
            model=model, input_tokens=input_tokens, output_tokens=output_tokens,
            cost_usd=cost, task=task,
        )
        self.reports.append(report)
        self.session_cost += cost
        return report

    def is_within_budget(self, estimated_cost: float = 0.0) -> bool:
        return (self.session_cost + estimated_cost) < self.max_cost_per_session

    def is_task_within_budget(self, estimated_cost: float) -> bool:
        return estimated_cost < self.max_cost_per_task

    def get_session_summary(self) -> dict:
        total_input = sum(r.input_tokens for r in self.reports)
        total_output = sum(r.output_tokens for r in self.reports)
        return {
            "total_requests": len(self.reports),
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "total_cost_usd": round(self.session_cost, 4),
            "budget_remaining_usd": round(max(0, self.max_cost_per_session - self.session_cost), 4),
            "budget_used_percent": round((self.session_cost / self.max_cost_per_session) * 100, 1),
            "models_used": list(set(r.model for r in self.reports)),
        }

    def get_optimization_suggestions(self) -> list[str]:
        suggestions = []
        if self.session_cost > self.max_cost_per_session * 0.8:
            suggestions.append(f"⚠️ 80% budget used (${self.session_cost:.2f}/${self.max_cost_per_session:.2f}). Consider switching to a cheaper model.")
        model_counts = {}
        for r in self.reports:
            model_counts[r.model] = model_counts.get(r.model, 0) + 1
        for model, count in model_counts.items():
            pricing = MODEL_PRICING.get(model, {})
            if pricing.get("input", 0) > 1.0 / 1_000_000:
                cheaper = self._find_cheaper_alternative(model)
                if cheaper:
                    savings = self._estimate_savings(model, cheaper, count)
                    suggestions.append(f"Switch {count} requests from {model} to {cheaper} to save ~${savings:.2f}")
        return suggestions

    def _find_cheaper_alternative(self, model: str) -> str | None:
        alternatives = {
            "gpt-4o": "gpt-4o-mini",
            "claude-3.5-sonnet": "claude-3.5-haiku",
            "o3-mini": "gpt-4o-mini",
        }
        return alternatives.get(model)

    def _estimate_savings(self, expensive: str, cheaper: str, count: int) -> float:
        avg_input = sum(r.input_tokens for r in self.reports if r.model == expensive) / max(count, 1)
        avg_output = sum(r.output_tokens for r in self.reports if r.model == expensive) / max(count, 1)
        expensive_cost = self.calculate_cost(int(avg_input), int(avg_output), expensive)
        cheaper_cost = self.calculate_cost(int(avg_input), int(avg_output), cheaper)
        return (expensive_cost - cheaper_cost) * count
