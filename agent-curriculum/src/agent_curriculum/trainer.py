"""Train model through curriculum stages with progressive difficulty."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from agent_curriculum.stage_builder import StageBuilder, CurriculumStage
from agent_curriculum.difficulty_scorer import DifficultyScorer

logger = logging.getLogger(__name__)


@dataclass
class TrainingResult:
    """Result of training a single curriculum stage."""

    stage_id: int
    stage_name: str
    num_traces: int
    status: str = "configured"
    output_dir: str = ""
    metrics: dict[str, Any] = field(default_factory=dict)


class CurriculumTrainer:
    """Train a model through curriculum stages with progressive difficulty.

    The curriculum approach trains the model on easy examples first (basic
    tool use) and progressively introduces harder examples (multi-step
    reasoning with errors), allowing the model to build foundational
    skills before tackling complex tasks.
    """

    def __init__(
        self,
        base_model: str = "Qwen/Qwen2.5-14B",
        output_dir: str = "output/curriculum",
        scorer: DifficultyScorer | None = None,
        builder: StageBuilder | None = None,
    ):
        self.base_model = base_model
        self.output_dir = Path(output_dir)
        self.scorer = scorer or DifficultyScorer()
        self.builder = builder or StageBuilder(scorer=self.scorer)
        self.results: list[TrainingResult] = []

    def train_curriculum(
        self,
        trace_path: str | Path,
        start_stage: int = 1,
        end_stage: int = 5,
    ) -> list[TrainingResult]:
        """Train the model through curriculum stages.

        Args:
            trace_path: Path to JSONL file with agent traces.
            start_stage: Stage to start from (1-5).
            end_stage: Stage to end at (1-5).

        Returns:
            List of TrainingResult objects.
        """
        # Build stages from traces
        stages = self.builder.build_stages(trace_path)

        self.results = []
        for stage in stages:
            if stage.stage_id < start_stage or stage.stage_id > end_stage:
                continue

            result = self._train_stage(stage)
            self.results.append(result)

            logger.info(f"Stage {stage.stage_id} ({stage.name}): {result.status}")
            logger.info(f"  Traces: {result.num_traces}, Output: {result.output_dir}")

        return self.results

    def _train_stage(self, stage: CurriculumStage) -> TrainingResult:
        """Train a single curriculum stage.

        In production, this would call the training pipeline (Unsloth/trl).
        Here we configure and prepare the training.
        """
        stage_dir = self.output_dir / f"stage{stage.stage_id}_{stage.name}"
        stage_dir.mkdir(parents=True, exist_ok=True)

        # Save stage traces
        traces_path = stage_dir / "traces.jsonl"
        with open(traces_path, "w") as f:
            for trace in stage.traces:
                f.write(json.dumps(trace) + "\n")

        # Save stage config
        config = {
            **stage.config,
            "base_model": self.base_model,
            "stage_id": stage.stage_id,
            "stage_name": stage.name,
            "num_traces": len(stage.traces),
            "difficulty_range": list(stage.difficulty_range),
        }
        config_path = stage_dir / "training_config.json"
        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)

        return TrainingResult(
            stage_id=stage.stage_id,
            stage_name=stage.name,
            num_traces=len(stage.traces),
            status="configured",
            output_dir=str(stage_dir),
            metrics={
                "num_traces": len(stage.traces),
                "difficulty_range": list(stage.difficulty_range),
                "learning_rate": stage.config.get("learning_rate"),
                "batch_size": stage.config.get("batch_size"),
                "lora_r": stage.config.get("lora_r"),
            },
        )
