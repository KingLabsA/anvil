"""Generate fuzzing reports with success/failure rates."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agent_fuzzer.runner import FuzzResult


@dataclass
class CategorySummary:
    """Summary for a single category."""

    category: str
    total: int = 0
    passed: int = 0
    partial: int = 0
    failed: int = 0
    avg_score: float = 0.0
    avg_tokens: float = 0.0
    avg_duration: float = 0.0
    pass_rate: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "total": self.total,
            "passed": self.passed,
            "partial": self.partial,
            "failed": self.failed,
            "pass_rate": f"{self.pass_rate:.1%}",
            "avg_score": round(self.avg_score, 3),
            "avg_tokens": round(self.avg_tokens, 1),
            "avg_duration": f"{self.avg_duration:.1f}s",
        }


class FuzzReporter:
    """Generate reports from fuzzing results."""

    def __init__(self, results: list[FuzzResult] | None = None):
        self.results = results or []

    def generate_report(self) -> dict[str, Any]:
        """Generate a comprehensive fuzzing report.

        Returns:
            Dictionary with overall and per-category metrics.
        """
        if not self.results:
            return {"status": "no results", "total": 0}

        total = len(self.results)
        passed = sum(1 for r in self.results if r.passed)
        partial = sum(1 for r in self.results if r.partial and not r.passed)
        failed = total - passed - partial
        avg_score = sum(r.score for r in self.results) / total if total else 0
        avg_tokens = sum(r.tokens_used for r in self.results) / total if total else 0
        avg_duration = sum(r.duration_seconds for r in self.results) / total if total else 0

        # Category summaries
        categories: dict[str, list[FuzzResult]] = {}
        for r in self.results:
            categories.setdefault(r.category, []).append(r)

        category_summaries = {}
        for cat, cat_results in categories.items():
            cat_total = len(cat_results)
            cat_passed = sum(1 for r in cat_results if r.passed)
            cat_partial = sum(1 for r in cat_results if r.partial and not r.passed)
            summary = CategorySummary(
                category=cat,
                total=cat_total,
                passed=cat_passed,
                partial=cat_partial,
                failed=cat_total - cat_passed - cat_partial,
                avg_score=sum(r.score for r in cat_results) / cat_total if cat_total else 0,
                avg_tokens=sum(r.tokens_used for r in cat_results) / cat_total if cat_total else 0,
                avg_duration=sum(r.duration_seconds for r in cat_results) / cat_total if cat_total else 0,
                pass_rate=cat_passed / cat_total if cat_total else 0,
            )
            category_summaries[cat] = summary.to_dict()

        # Difficulty breakdown
        difficulty_summary = {}
        for diff in ["easy", "medium", "hard"]:
            diff_results = [r for r in self.results if r.difficulty == diff]
            if diff_results:
                diff_total = len(diff_results)
                diff_passed = sum(1 for r in diff_results if r.passed)
                difficulty_summary[diff] = {
                    "total": diff_total,
                    "passed": diff_passed,
                    "pass_rate": f"{diff_passed/diff_total:.1%}",
                }

        return {
            "status": "complete",
            "total": total,
            "passed": passed,
            "partial": partial,
            "failed": failed,
            "pass_rate": f"{passed/total:.1%}" if total else "N/A",
            "avg_score": round(avg_score, 3),
            "avg_tokens": round(avg_tokens, 1),
            "avg_duration": f"{avg_duration:.1f}s",
            "by_category": category_summaries,
            "by_difficulty": difficulty_summary,
        }

    def save_report(self, path: str | Path, format: str = "json") -> None:
        """Save the report to a file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        report = self.generate_report()
        with open(path, "w") as f:
            json.dump(report, f, indent=2)
