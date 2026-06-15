"""Run agent against adversarial scenarios and collect metrics."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agent_fuzzer.generator import Scenario, ScenarioGenerator


@dataclass
class FuzzResult:
    """Result of running a single fuzz scenario."""

    scenario_name: str
    category: str
    difficulty: str
    passed: bool = False
    partial: bool = False
    score: float = 0.0
    tokens_used: int = 0
    duration_seconds: float = 0.0
    error: str | None = None
    agent_output: str = ""
    expected_fix: str = ""
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_name": self.scenario_name,
            "category": self.category,
            "difficulty": self.difficulty,
            "passed": self.passed,
            "partial": self.partial,
            "score": self.score,
            "tokens_used": self.tokens_used,
            "duration_seconds": self.duration_seconds,
            "error": self.error,
            "expected_fix": self.expected_fix,
        }


class FuzzRunner:
    """Run an agent against adversarial scenarios and collect metrics.

    The runner simulates an agent attempting to solve each scenario
    and tracks success rate, token usage, and timing.
    """

    def __init__(self, model: str = "gpt-4", max_retries: int = 3, timeout: int = 60):
        self.model = model
        self.max_retries = max_retries
        self.timeout = timeout
        self.results: list[FuzzResult] = []

    def run_scenario(self, scenario: Scenario) -> FuzzResult:
        """Run a single adversarial scenario.

        In production, this would call the actual agent API.
        Here we simulate results based on difficulty.

        Args:
            scenario: The Scenario to run.

        Returns:
            FuzzResult with outcome metrics.
        """
        import random
        random.seed(hash(scenario.name))

        # Difficulty affects pass rate
        pass_rates = {"easy": 0.9, "medium": 0.65, "hard": 0.35}
        base_rate = pass_rates.get(scenario.difficulty, 0.5)

        passed = random.random() < base_rate
        partial = not passed and random.random() < 0.4
        score = 1.0 if passed else (0.5 if partial else random.uniform(0.0, 0.3))

        return FuzzResult(
            scenario_name=scenario.name,
            category=scenario.category,
            difficulty=scenario.difficulty,
            passed=passed,
            partial=partial,
            score=score,
            tokens_used=random.randint(200, 3000),
            duration_seconds=random.uniform(2.0, 30.0),
            expected_fix=scenario.expected_fix,
        )

    def run_suite(self, scenarios: list[Scenario] | None = None, categories: list[str] | None = None) -> list[FuzzResult]:
        """Run a suite of adversarial scenarios.

        Args:
            scenarios: Optional list of scenarios. If None, generates all.
            categories: Optional category filter.

        Returns:
            List of FuzzResult objects.
        """
        if scenarios is None:
            generator = ScenarioGenerator()
            scenarios = generator.generate_all()

        if categories:
            scenarios = [s for s in scenarios if s.category in categories]

        self.results = []
        for scenario in scenarios:
            result = self.run_scenario(scenario)
            self.results.append(result)

        return self.results

    def run_from_directory(self, scenarios_dir: str | Path) -> list[FuzzResult]:
        """Load scenarios from YAML files and run them.

        Args:
            scenarios_dir: Directory containing scenario YAML files.

        Returns:
            List of FuzzResult objects.
        """
        import yaml
        scenarios_dir = Path(scenarios_dir)
        scenarios: list[Scenario] = []

        for yaml_file in scenarios_dir.rglob("*.yaml"):
            with open(yaml_file) as f:
                data = yaml.safe_load(f)
            scenarios.append(Scenario(
                name=data["name"],
                category=data["category"],
                description=data["description"],
                language=data.get("language", "python"),
                code=data["code"],
                expected_fix=data["expected_fix"],
                difficulty=data.get("difficulty", "medium"),
                tags=data.get("tags", []),
            ))

        return self.run_suite(scenarios)
