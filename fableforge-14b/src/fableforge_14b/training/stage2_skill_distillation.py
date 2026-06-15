"""Stage 2: Skill Distillation — Train on coding-excellence 100K code gen examples."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


@dataclass
class Stage2Config:
    """Configuration for Stage 2: Skill Distillation.

    This stage trains the model on 100K curated coding-excellence examples.
    These are high-quality code generation samples that teach the model to
    write correct, efficient, and idiomatic code.
    """

    base_model: str = ""
    stage1_adapter: str = "output/stage1"
    dataset_path: str = "data/coding_excellence_100k.jsonl"
    output_dir: str = "output/stage2"
    LoRA_r: int = 64
    LoRA_alpha: int = 128
    LoRA_dropout: float = 0.05
    LoRA_target_modules: list[str] = field(default_factory=lambda: [
        "q_proj", "k_proj", "v_proj", "o_proj",
        "gate_proj", "up_proj", "down_proj",
    ])
    batch_size: int = 4
    gradient_accumulation_steps: int = 8
    learning_rate: float = 1e-4
    num_epochs: int = 2
    max_seq_length: int = 8192
    warmup_ratio: float = 0.05
    weight_decay: float = 0.01
    lr_scheduler_type: str = "cosine"
    save_steps: int = 500
    eval_steps: int = 500
    logging_steps: int = 10
    use_unsloth: bool = True
    bf16: bool = True
    seed: int = 42
    # Skill-specific settings
    skill_categories: list[str] = field(default_factory=lambda: [
        "algorithm_implementation",
        "api_design",
        "debugging",
        "refactoring",
        "testing",
        "documentation",
    ])
    code_quality_filter: str = "high"
    min_pass_rate: float = 0.85

    @classmethod
    def from_yaml(cls, path: str | Path) -> Stage2Config:
        with open(path) as f:
            data = yaml.safe_load(f)
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def to_dict(self) -> dict[str, Any]:
        return {k: getattr(self, k) for k in self.__dataclass_fields__}


def load_coding_excellence_dataset(path: str | Path, max_samples: int | None = None) -> list[dict[str, Any]]:
    """Load the coding-excellence dataset.

    Each example contains a coding task with a high-quality solution that passes
    all tests. The format follows ShareGPT/OpenAI chat format.

    Args:
        path: Path to the JSONL dataset file.
        max_samples: Maximum number of samples to load.

    Returns:
        List of code generation examples.
    """
    path = Path(path)
    if not path.exists():
        logger.warning(f"Dataset not found at {path}, generating synthetic examples")
        return _generate_coding_examples(max_samples or 100)

    examples = []
    with open(path) as f:
        for i, line in enumerate(f):
            if max_samples and i >= max_samples:
                break
            line = line.strip()
            if not line:
                continue
            try:
                example = json.loads(line)
                examples.append(example)
            except json.JSONDecodeError:
                continue

    logger.info(f"Loaded {len(examples)} coding excellence examples from {path}")
    return examples


def _generate_coding_examples(count: int) -> list[dict[str, Any]]:
    """Generate synthetic code generation examples for testing."""
    examples = []
    skill_prompts = {
        "algorithm_implementation": [
            ("Implement a binary search tree with insert, search, and delete operations in Python.",
             "class BinarySearchTree:\n    def __init__(self):\n        self.root = None\n\n    def insert(self, value):\n        if self.root is None:\n            self.root = TreeNode(value)\n        else:\n            self._insert_recursive(self.root, value)\n\n    def search(self, value):\n        return self._search_recursive(self.root, value)\n\n    def delete(self, value):\n        self.root = self._delete_recursive(self.root, value)"),
        ],
        "api_design": [
            ("Design a REST API for a task management system with CRUD operations.",
             'from fastapi import FastAPI, HTTPException\nfrom pydantic import BaseModel\n\napp = FastAPI()\n\nclass TaskCreate(BaseModel):\n    title: str\n    description: str = ""\n    priority: int = 0\n\n@app.post("/tasks")\nasync def create_task(task: TaskCreate):\n    task_id = len(tasks_db) + 1\n    new_task = {**task.dict(), "id": task_id, "completed": False}\n    tasks_db[task_id] = new_task\n    return new_task'),
        ],
        "debugging": [
            ("Fix the off-by-one error in this binary search implementation.",
             "def binary_search(arr, target):\n    left, right = 0, len(arr) - 1  # Fixed: was len(arr)\n    while left <= right:  # Fixed: was <\n        mid = left + (right - left) // 2\n        if arr[mid] == target:\n            return mid\n        elif arr[mid] < target:\n            left = mid + 1\n        else:\n            right = mid - 1\n    return -1"),
        ],
        "refactoring": [
            ("Refactor this function to use list comprehension and type hints.",
             "from typing import List, Optional\n\ndef filter_active_users(users: List[dict]) -> List[dict]:\n    \"\"\"Filter users with active status.\"\"\"\n    return [user for user in users if user.get(\"active\", False)]"),
        ],
        "testing": [
            ("Write comprehensive pytest tests for a Stack class.",
             'import pytest\nfrom stack import Stack\n\ndef test_push_pop():\n    stack = Stack()\n    stack.push(1)\n    stack.push(2)\n    assert stack.pop() == 2\n    assert stack.pop() == 1\n\ndef test_empty_stack_pop():\n    stack = Stack()\n    with pytest.raises(IndexError):\n        stack.pop()\n\ndef test_peek():\n    stack = Stack()\n    stack.push(42)\n    assert stack.peek() == 42\n    assert stack.size() == 1'),
        ],
        "documentation": [
            ("Add comprehensive docstrings to this data processing module.",
             'def process_data(data: list[dict], key: str, threshold: float = 0.5) -> list[dict]:\n    """Filter and transform data records.\n\n    Args:\n        data: List of dictionaries containing the input records.\n        key: The dictionary key to filter on.\n        threshold: Minimum value threshold for filtering. Defaults to 0.5.\n\n    Returns:\n        A filtered list of dictionaries where data[key] >= threshold.\n\n    Raises:\n        KeyError: If key is not found in any record.\n\n    Example:\n        >>> process_data([{\"score\": 0.7}, {\"score\": 0.3}], \"score\")\n        [{\"score\": 0.7}]\n    """\n    return [record for record in data if record.get(key, 0) >= threshold]'),
        ],
    }

    categories = list(skill_prompts.keys())
    for i in range(count):
        cat = categories[i % len(categories)]
        prompts = skill_prompts[cat]
        prompt, response = prompts[i % len(prompts)]
        examples.append({
            "category": cat,
            "messages": [
                {"role": "system", "content": f"You are an expert at {cat.replace('_', ' ')}. Write correct, efficient, well-documented code."},
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": response},
            ],
            "quality_score": 0.9 + (i % 10) * 0.01,
            "passes_tests": True,
        })

    return examples


def filter_by_quality(examples: list[dict[str, Any]], min_score: float = 0.85) -> list[dict[str, Any]]:
    """Filter examples by quality score.

    Args:
        examples: Raw examples.
        min_score: Minimum quality score (0.0–1.0).

    Returns:
        Filtered examples.
    """
    filtered = [
        ex for ex in examples
        if ex.get("quality_score", 1.0) >= min_score and ex.get("passes_tests", True)
    ]
    logger.info(f"Filtered {len(examples)} → {len(filtered)} examples (min_score={min_score})")
    return filtered


def run_stage2(config: Stage2Config | None = None, dataset_path: str | None = None) -> dict[str, Any]:
    """Run Stage 2: Skill Distillation training.

    Trains on 100K curated coding-excellence examples to teach the model
    to write correct, efficient, and idiomatic code across multiple skill
    categories.

    Args:
        config: Stage2Config with all training hyperparameters.
        dataset_path: Override path to the dataset.

    Returns:
        Dictionary with training configuration and output path.
    """
    if config is None:
        config = Stage2Config()

    if dataset_path:
        config.dataset_path = dataset_path

    logger.info("=" * 60)
    logger.info("Stage 2: Skill Distillation (Coding Excellence 100K)")
    logger.info("=" * 60)
    logger.info(f"Stage 1 adapter: {config.stage1_adapter}")
    logger.info(f"Dataset: {config.dataset_path}")
    logger.info(f"Skill categories: {config.skill_categories}")
    logger.info(f"Output: {config.output_dir}")

    examples = load_coding_excellence_dataset(config.dataset_path)
    filtered = filter_by_quality(examples, min_score=config.min_pass_rate)

    output_path = Path(config.output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    training_config = config.to_dict()
    training_config["num_examples"] = len(filtered)
    training_config["num_filtered_out"] = len(examples) - len(filtered)

    config_path = output_path / "training_config.json"
    with open(config_path, "w") as f:
        json.dump(training_config, f, indent=2)

    logger.info(f"Training config saved to {config_path}")
    logger.info(f"Ready to train on {len(filtered)} filtered examples")

    return {
        "status": "configured",
        "output_dir": str(output_path),
        "num_examples": len(filtered),
        "num_filtered_out": len(examples) - len(filtered),
        "config": training_config,
    }
