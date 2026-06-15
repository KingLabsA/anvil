"""Learning rate and batch size scheduling per curriculum stage."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import yaml


@dataclass
class ScheduleConfig:
    """Learning rate and batch size schedule for a single stage."""

    stage_id: int
    learning_rate: float
    batch_size: int
    warmup_steps: int = 0
    lora_r: int = 64
    lora_alpha: int = 128
    gradient_accumulation_steps: int = 4
    weight_decay: float = 0.01
    num_epochs: int = 2

    def to_dict(self) -> dict[str, Any]:
        return {k: getattr(self, k) for k in self.__dataclass_fields__}


# Default schedule: progressively lower learning rates and higher discriminative LoRA
DEFAULT_SCHEDULE: list[ScheduleConfig] = [
    ScheduleConfig(stage_id=1, learning_rate=2e-4, batch_size=8, lora_r=64, num_epochs=3),
    ScheduleConfig(stage_id=2, learning_rate=1e-4, batch_size=4, lora_r=64, num_epochs=2),
    ScheduleConfig(stage_id=3, learning_rate=5e-5, batch_size=4, lora_r=32, num_epochs=2),
    ScheduleConfig(stage_id=4, learning_rate=3e-5, batch_size=2, lora_r=32, num_epochs=2),
    ScheduleConfig(stage_id=5, learning_rate=1e-5, batch_size=2, lora_r=16, num_epochs=1),
]


class CurriculumScheduler:
    """Schedule learning rates, batch sizes, and LoRA parameters per stage.

    The scheduler follows a curriculum learning approach where later stages
    use lower learning rates (to preserve earlier learning), smaller LoRA
    ranks (more discriminative fine-tuning), and smaller batch sizes
    (more gradient updates per sample).
    """

    def __init__(self, schedule: list[ScheduleConfig] | None = None):
        self.schedule = schedule or DEFAULT_SCHEDULE

    def get_config(self, stage_id: int) -> ScheduleConfig:
        """Get training config for a specific stage.

        Args:
            stage_id: Curriculum stage (1-5).

        Returns:
            ScheduleConfig for the stage.

        Raises:
            ValueError: If stage_id is out of range.
        """
        for s in self.schedule:
            if s.stage_id == stage_id:
                return s
        raise ValueError(f"Unknown stage {stage_id}. Available: 1-{len(self.schedule)}")

    def get_all_configs(self) -> list[ScheduleConfig]:
        """Get all stage configs in order."""
        return list(self.schedule)

    def save_configs(self, output_dir: str) -> None:
        """Save all stage configs as YAML files."""
        from pathlib import Path
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        for config in self.schedule:
            path = output_path / f"stage{config.stage_id}.yaml"
            with open(path, "w") as f:
                yaml.dump(config.to_dict(), f, default_flow_style=False)
