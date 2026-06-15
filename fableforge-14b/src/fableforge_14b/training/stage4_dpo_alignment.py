"""Stage 4: DPO Alignment — Direct Preference Optimization for agent behavior."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


@dataclass
class Stage4Config:
    """Configuration for Stage 4: DPO Alignment.

    Direct Preference Optimization fine-tunes the model to prefer correct,
    efficient, and safe agent behaviors over suboptimal ones.
    """

    base_model: str = ""
    stage3_adapter: str = "output/stage3"
    dataset_path: str = "data/dpo_preferences.jsonl"
    output_dir: str = "output/stage4"
    LoRA_r: int = 16
    LoRA_alpha: int = 32
    LoRA_dropout: float = 0.05
    LoRA_target_modules: list[str] = field(default_factory=lambda: [
        "q_proj", "v_proj",
    ])
    batch_size: int = 2
    gradient_accumulation_steps: int = 16
    learning_rate: float = 3e-5
    num_epochs: int = 1
    max_seq_length: int = 8192
    warmup_ratio: float = 0.03
    weight_decay: float = 0.01
    lr_scheduler_type: str = "cosine"
    save_steps: int = 200
    eval_steps: int = 200
    logging_steps: int = 10
    bf16: bool = True
    seed: int = 42
    # DPO-specific
    dpo_beta: float = 0.1
    dpo_loss_type: str = "sigmoid"
    dpo_label_smoothing: float = 0.0
    max_prompt_length: int = 2048
    max_chosen_length: int = 4096
    max_rejected_length: int = 4096
    reference_free: bool = False

    @classmethod
    def from_yaml(cls, path: str | Path) -> Stage4Config:
        with open(path) as f:
            data = yaml.safe_load(f)
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def to_dict(self) -> dict[str, Any]:
        return {k: getattr(self, k) for k in self.__dataclass_fields__}


def load_dpo_dataset(path: str | Path, max_samples: int | None = None) -> list[dict[str, Any]]:
    """Load DPO preference pairs dataset.

    Each example contains a prompt, a chosen (preferred) response, and
    a rejected (dispreferred) response.

    Args:
        path: Path to the JSONL dataset file.
        max_samples: Maximum number of samples to load.

    Returns:
        List of DPO preference examples.
    """
    path = Path(path)
    if not path.exists():
        logger.warning(f"Dataset not found at {path}, generating synthetic examples")
        return _generate_dpo_examples(max_samples or 100)

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

    logger.info(f"Loaded {len(examples)} DPO examples from {path}")
    return examples


def _generate_dpo_examples(count: int) -> list[dict[str, Any]]:
    """Generate synthetic DPO preference pairs for testing."""
    preference_pairs = [
        {
            "prompt": "Fix the bug in the authentication function.",
            "chosen": "I'll read the authentication file first to understand the issue, then make a targeted fix.\n\nAfter reading the file, I can see the bug is on line 23 where the token comparison uses `=` instead of `==`. Here's the fix:\n\n```python\nif token == expected_token:  # Fixed: was single =\n    return True\n```\n\nThis was an assignment where a comparison was intended.",
            "rejected": "Let me just rewrite the whole function from scratch since there might be other bugs too.\n\n```python\ndef auth(token):\n    # Rewriting everything\n    if token == 'secret':\n        return True\n    return False\n```\n\nThat should fix it, probably.",
            "category": "targeted_fix",
        },
        {
            "prompt": "Add error handling to the database query function.",
            "chosen": "I'll add specific exception handling for the most common database errors:\n\n```python\nasync def query_database(sql: str, params: tuple = ()) -> list[dict]:\n    \"\"\"Execute a database query with proper error handling.\"\"\"\n    try:\n        async with pool.acquire() as conn:\n            rows = await conn.fetch(sql, *params)\n            return [dict(row) for row in rows]\n    except asyncpg.UndefinedTableError:\n        logger.error(f\"Table not found in query: {sql[:100]}\")\n        raise ValueError(f\"Table does not exist: check schema\") from None\n    except asyncpg.ConnectionDoesNotExistError:\n        logger.error(\"Database connection failed\")\n        raise ConnectionError(\"Unable to connect to database\") from None\n    except asyncpg.PostgresError as e:\n        logger.error(f\"Database error: {e}\")\n        raise RuntimeError(f\"Query failed: {e}\") from None\n```\n\nEach error type has a specific handler with appropriate logging and re-raising.",
            "rejected": "Just add a try/except:\n\n```python\nasync def query_database(sql, params=()):\n    try:\n        async with pool.acquire() as conn:\n            return await conn.fetch(sql, *params)\n    except:\n        print('error')\n        return []\n```\n\nDone!",
            "category": "error_handling",
        },
        {
            "prompt": "Optimize this slow function that processes a list of items.",
            "chosen": "Let me first understand the current implementation's characteristics:\n\n```python\nfrom collections import defaultdict\n\ndef process_items(items: list[dict]) -> dict[str, list[dict]]:\n    \"\"\"Group items by category and deduplicate.\"\"\"\n    grouped = defaultdict(list)\n    seen = set()\n    for item in items:\n        key = item[\"category\"]\n        item_id = item[\"id\"]\n        if item_id not in seen:\n            seen.add(item_id)\n            grouped[key].append(item)\n    return dict(grouped)\n```\n\nThe original was O(n²) due to `in` checks on a list. This version uses a set for O(1) lookups, reducing time complexity from O(n²) to O(n). The defaultdict also eliminates the need for key existence checks.",
            "rejected": "Just use a list comprehension:\n\n```python\ndef process_items(items):\n    return {k: [x for x in items if x['category'] == k]\n            for k in set(x['category'] for x in items)}\n```\n\nList comprehensions are always faster.",
            "category": "optimization",
        },
    ]

    examples = []
    for i in range(count):
        pair = preference_pairs[i % len(preference_pairs)]
        examples.append({
            "prompt": pair["prompt"],
            "chosen": [{"role": "assistant", "content": pair["chosen"]}],
            "rejected": [{"role": "assistant", "content": pair["rejected"]}],
            "category": pair["category"],
        })

    return examples


def validate_dpo_examples(examples: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    """Validate DPO examples have required fields and valid content.

    Args:
        examples: Raw DPO examples.

    Returns:
        Tuple of (valid_examples, error_messages).
    """
    valid = []
    errors = []
    for i, ex in enumerate(examples):
        if "prompt" not in ex:
            errors.append(f"Example {i}: missing 'prompt' field")
            continue
        if "chosen" not in ex or "rejected" not in ex:
            errors.append(f"Example {i}: missing 'chosen' or 'rejected' field")
            continue
        chosen_text = ex["chosen"] if isinstance(ex["chosen"], str) else str(ex["chosen"])
        rejected_text = ex["rejected"] if isinstance(ex["rejected"], str) else str(ex["rejected"])
        if len(chosen_text) < 10:
            errors.append(f"Example {i}: chosen response too short ({len(chosen_text)} chars)")
            continue
        if len(rejected_text) < 10:
            errors.append(f"Example {i}: rejected response too short ({len(rejected_text)} chars)")
            continue
        valid.append(ex)

    logger.info(f"Validated {len(examples)} examples: {len(valid)} valid, {len(errors)} errors")
    return valid, errors


def run_stage4(config: Stage4Config | None = None, dataset_path: str | None = None) -> dict[str, Any]:
    """Run Stage 4: DPO Alignment.

    Fine-tunes the model using Direct Preference Optimization to align
    agent behavior with expert preferences.

    Args:
        config: Stage4Config with all training hyperparameters.
        dataset_path: Override path to the dataset.

    Returns:
        Dictionary with training configuration and output path.
    """
    if config is None:
        config = Stage4Config()

    if dataset_path:
        config.dataset_path = dataset_path

    logger.info("=" * 60)
    logger.info("Stage 4: DPO Alignment")
    logger.info("=" * 60)
    logger.info(f"Stage 3 adapter: {config.stage3_adapter}")
    logger.info(f"Dataset: {config.dataset_path}")
    logger.info(f"DPO beta: {config.dpo_beta}")
    logger.info(f"Output: {config.output_dir}")

    examples = load_dpo_dataset(config.dataset_path)
    valid_examples, errors = validate_dpo_examples(examples)

    if errors:
        logger.warning(f"Validation errors: {errors[:5]}...")

    output_path = Path(config.output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    training_config = config.to_dict()
    training_config["num_examples"] = len(valid_examples)
    training_config["validation_errors"] = len(errors)

    config_path = output_path / "training_config.json"
    with open(config_path, "w") as f:
        json.dump(training_config, f, indent=2)

    logger.info(f"Training config saved to {config_path}")
    logger.info(f"Ready for DPO training on {len(valid_examples)} preference pairs")

    return {
        "status": "configured",
        "output_dir": str(output_path),
        "num_examples": len(valid_examples),
        "validation_errors": len(errors),
        "config": training_config,
    }
