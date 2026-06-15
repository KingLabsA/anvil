"""Build curriculum training stages from difficulty-scored traces."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from agent_curriculum.difficulty_scorer import DifficultyScore, DifficultyScorer


@dataclass
class CurriculumStage:
    """A single stage in the training curriculum."""

    stage_id: int
    name: str
    description: str
    difficulty_range: tuple[float, float]
    max_tools: int
    max_errors: int
    traces: list[dict[str, Any]] = field(default_factory=list)
    scores: list[DifficultyScore] = field(default_factory=list)
    config: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "stage_id": self.stage_id,
            "name": self.name,
            "description": self.description,
            "difficulty_range": list(self.difficulty_range),
            "max_tools": self.max_tools,
            "max_errors": self.max_errors,
            "num_traces": len(self.traces),
            "config": self.config,
        }


# Pre-defined curriculum stages
STAGE_DEFINITIONS = [
    CurriculumStage(
        stage_id=1,
        name="basic",
        description="Basic tool use — simple read/edit/bash tasks with no errors",
        difficulty_range=(0.0, 0.2),
        max_tools=5,
        max_errors=0,
        config={
            "learning_rate": 2e-4,
            "batch_size": 8,
            "num_epochs": 3,
            "lora_r": 64,
        },
    ),
    CurriculumStage(
        stage_id=2,
        name="intermediate",
        description="Intermediate tasks — multi-tool sequences with simple error recovery",
        difficulty_range=(0.2, 0.4),
        max_tools=15,
        max_errors=2,
        config={
            "learning_rate": 1e-4,
            "batch_size": 4,
            "num_epochs": 2,
            "lora_r": 64,
        },
    ),
    CurriculumStage(
        stage_id=3,
        name="advanced",
        description="Advanced tasks — complex multi-step with error recovery",
        difficulty_range=(0.4, 0.6),
        max_tools=30,
        max_errors=5,
        config={
            "learning_rate": 5e-5,
            "batch_size": 4,
            "num_epochs": 2,
            "lora_r": 32,
        },
    ),
    CurriculumStage(
        stage_id=4,
        name="expert",
        description="Expert tasks — multi-session with complex error patterns",
        difficulty_range=(0.6, 0.8),
        max_tools=60,
        max_errors=10,
        config={
            "learning_rate": 3e-5,
            "batch_size": 2,
            "num_epochs": 2,
            "lora_r": 32,
        },
    ),
    CurriculumStage(
        stage_id=5,
        name="master",
        description="Master tasks — long-horizon planning with complex recovery",
        difficulty_range=(0.8, 1.0),
        max_tools=100,
        max_errors=20,
        config={
            "learning_rate": 1e-5,
            "batch_size": 2,
            "num_epochs": 1,
            "lora_r": 16,
        },
    ),
]


class StageBuilder:
    """Build training stages from difficulty-scored traces.

    Assigns traces to curriculum stages based on difficulty scores and
    generates YAML configs for each stage.
    """

    def __init__(self, scorer: DifficultyScorer | None = None, stages: list[CurriculumStage] | None = None):
        self.scorer = scorer or DifficultyScorer()
        self.stages = stages or [CurriculumStage(**s.__dict__) if isinstance(s, CurriculumStage) else CurriculumStage(**s) for s in STAGE_DEFINITIONS]

    def build_stages(self, trace_path: str | Path) -> list[CurriculumStage]:
        """Build curriculum stages from a trace file.

        Args:
            trace_path: Path to JSONL file with agent traces.

        Returns:
            List of CurriculumStage objects with assigned traces.
        """
        trace_path = Path(trace_path)
        scores = self.scorer.score_file(trace_path)

        # Load traces
        traces: list[dict[str, Any]] = []
        with open(trace_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    traces.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

        # Assign traces to stages based on difficulty
        for score, trace in zip(scores, traces):
            for stage in self.stages:
                low, high = stage.difficulty_range
                if low <= score.overall_difficulty < high:
                    stage.traces.append(trace)
                    stage.scores.append(score)
                    break

        # Add unmatched traces to the closest stage
        assigned_traces = set()
        for stage in self.stages:
            for t in stage.traces:
                if "id" in t:
                    assigned_traces.add(t["id"])

        return self.stages

    def generate_configs(self, output_dir: str | Path) -> list[Path]:
        """Generate YAML config files for each stage.

        Args:
            output_dir: Directory to write config files.

        Returns:
            List of paths to generated config files.
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        config_paths = []

        for stage in self.stages:
            config = {
                "stage_id": stage.stage_id,
                "name": stage.name,
                "description": stage.description,
                "difficulty_range": list(stage.difficulty_range),
                "num_traces": len(stage.traces),
                **stage.config,
            }
            config_path = output_dir / f"stage{stage.stage_id}.yaml"
            with open(config_path, "w") as f:
                yaml.dump(config, f, default_flow_style=False)
            config_paths.append(config_path)

        return config_paths
