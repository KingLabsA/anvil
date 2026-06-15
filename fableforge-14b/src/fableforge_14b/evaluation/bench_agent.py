"""BenchAgent evaluation for FableForge-14B model."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class TaskCategory(str, Enum):
    CODE_GENERATION = "code_generation"
    DEBUGGING = "debugging"
    REFACTORING = "refactoring"
    TOOL_USE = "tool_use"
    ERROR_RECOVERY = "error_recovery"
    MULTI_STEP = "multi_step"


@dataclass
class BenchTask:
    """A single evaluation task."""

    task_id: str
    category: TaskCategory
    prompt: str
    expected_tools: list[str] = field(default_factory=list)
    expected_outputs: list[str] = field(default_factory=list)
    difficulty: int = 1  # 1-5
    timeout_seconds: int = 120
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class BenchResult:
    """Result of a single evaluation task."""

    task_id: str
    category: TaskCategory
    passed: bool
    score: float
    tool_accuracy: float
    response_time: float
    tokens_used: int
    error: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class BenchReport:
    """Aggregated evaluation report."""

    model_name: str
    total_tasks: int
    passed: int
    failed: int
    overall_score: float
    category_scores: dict[str, float]
    results: list[BenchResult]
    timestamp: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%S"))

    @property
    def pass_rate(self) -> float:
        return self.passed / self.total_tasks if self.total_tasks > 0 else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_name": self.model_name,
            "total_tasks": self.total_tasks,
            "passed": self.passed,
            "failed": self.failed,
            "pass_rate": self.pass_rate,
            "overall_score": self.overall_score,
            "category_scores": self.category_scores,
            "timestamp": self.timestamp,
        }


# Default benchmark tasks
DEFAULT_TASKS: list[dict[str, Any]] = [
    {
        "task_id": "code_001",
        "category": "code_generation",
        "prompt": "Write a Python function that finds the longest palindrome in a string.",
        "expected_tools": ["write"],
        "difficulty": 3,
    },
    {
        "task_id": "code_002",
        "category": "code_generation",
        "prompt": "Implement a stack data structure with push, pop, and peek operations.",
        "expected_tools": ["write"],
        "difficulty": 2,
    },
    {
        "task_id": "debug_001",
        "category": "debugging",
        "prompt": "Fix the segmentation fault in this C function that reverses a linked list.",
        "expected_tools": ["read", "edit", "bash"],
        "difficulty": 4,
    },
    {
        "task_id": "debug_002",
        "category": "debugging",
        "prompt": "This Python function returns wrong results for edge cases. Find and fix the bug.",
        "expected_tools": ["read", "edit", "bash"],
        "difficulty": 3,
    },
    {
        "task_id": "refactor_001",
        "category": "refactoring",
        "prompt": "Refactor this 200-line function into smaller, testable functions.",
        "expected_tools": ["read", "edit", "bash"],
        "difficulty": 4,
    },
    {
        "task_id": "tool_001",
        "category": "tool_use",
        "prompt": "Find all Python files that import 'requests' and list them.",
        "expected_tools": ["grep", "glob"],
        "difficulty": 1,
    },
    {
        "task_id": "tool_002",
        "category": "tool_use",
        "prompt": "Run the test suite and report which tests are failing.",
        "expected_tools": ["bash", "read"],
        "difficulty": 2,
    },
    {
        "task_id": "error_001",
        "category": "error_recovery",
        "prompt": "The application crashes with a TypeError. Find and fix the issue.",
        "expected_tools": ["read", "bash", "edit"],
        "difficulty": 3,
    },
    {
        "task_id": "multi_001",
        "category": "multi_step",
        "prompt": "Add authentication to the FastAPI app. Include JWT tokens, a login endpoint, and protected routes.",
        "expected_tools": ["read", "glob", "edit", "bash"],
        "difficulty": 5,
    },
]


class BenchAgent:
    """Evaluate a FableForge-14B model on the BenchAgent benchmark.

    BenchAgent tests coding agent capabilities across six categories:
    code generation, debugging, refactoring, tool use, error recovery,
    and multi-step tasks. Each category has tasks rated by difficulty (1-5).
    """

    def __init__(self, model_path: str | None = None, api_endpoint: str | None = None):
        self.model_path = model_path
        self.api_endpoint = api_endpoint
        self.tasks: list[BenchTask] = []
        self.results: list[BenchResult] = []

    def load_tasks(self, path: str | Path | None = None) -> None:
        """Load benchmark tasks from a JSON file or use defaults.

        Args:
            path: Path to JSON file with task definitions.
        """
        if path:
            with open(path) as f:
                data = json.load(f)
            self.tasks = [
                BenchTask(
                    task_id=t["task_id"],
                    category=TaskCategory(t["category"]),
                    prompt=t["prompt"],
                    expected_tools=t.get("expected_tools", []),
                    difficulty=t.get("difficulty", 1),
                )
                for t in data
            ]
        else:
            self.tasks = [
                BenchTask(
                    task_id=t["task_id"],
                    category=TaskCategory(t["category"]),
                    prompt=t["prompt"],
                    expected_tools=t.get("expected_tools", []),
                    difficulty=t.get("difficulty", 1),
                )
                for t in DEFAULT_TASKS
            ]

    def evaluate(self, model_name: str = "fableforge-14b") -> BenchReport:
        """Run the full BenchAgent evaluation.

        Args:
            model_name: Name of the model being evaluated.

        Returns:
            BenchReport with aggregated results.
        """
        if not self.tasks:
            self.load_tasks()

        logger.info(f"Starting BenchAgent evaluation for {model_name}")
        logger.info(f"Running {len(self.tasks)} tasks")

        # In production, this would call the model API
        # Here we simulate evaluation results
        self.results = []
        for task in self.tasks:
            result = self._evaluate_task(task)
            self.results.append(result)

        passed = sum(1 for r in self.results if r.passed)
        failed = len(self.results) - passed
        overall = sum(r.score for r in self.results) / len(self.results) if self.results else 0.0

        category_scores: dict[str, list[float]] = {}
        for r in self.results:
            category_scores.setdefault(r.category.value, []).append(r.score)

        avg_category_scores = {
            cat: sum(scores) / len(scores) for cat, scores in category_scores.items()
        }

        report = BenchReport(
            model_name=model_name,
            total_tasks=len(self.results),
            passed=passed,
            failed=failed,
            overall_score=overall,
            category_scores=avg_category_scores,
            results=self.results,
        )

        logger.info(f"Evaluation complete: {passed}/{len(self.results)} passed ({report.pass_rate:.1%})")
        return report

    def _evaluate_task(self, task: BenchTask) -> BenchResult:
        """Evaluate a single task.

        In production, this would call the model and check results.
        Here we simulate based on difficulty.
        """
        # Simulate evaluation — higher difficulty = lower pass rate
        difficulty_penalty = task.difficulty * 0.08
        base_score = 0.95 - difficulty_penalty

        import random
        random.seed(hash(task.task_id))
        score = base_score + random.uniform(-0.1, 0.05)
        score = max(0.0, min(1.0, score))

        return BenchResult(
            task_id=task.task_id,
            category=task.category,
            passed=score >= 0.6,
            score=score,
            tool_accuracy=0.85 + random.uniform(-0.1, 0.1),
            response_time=2.0 + task.difficulty * 1.5 + random.uniform(0, 2),
            tokens_used=500 + task.difficulty * 200 + random.randint(0, 300),
        )

    def save_report(self, report: BenchReport, path: str | Path) -> None:
        """Save evaluation report to JSON."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            **report.to_dict(),
            "results": [
                {
                    "task_id": r.task_id,
                    "category": r.category.value,
                    "passed": r.passed,
                    "score": r.score,
                    "tool_accuracy": r.tool_accuracy,
                    "response_time": r.response_time,
                    "tokens_used": r.tokens_used,
                }
                for r in report.results
            ],
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        logger.info(f"Report saved to {path}")
