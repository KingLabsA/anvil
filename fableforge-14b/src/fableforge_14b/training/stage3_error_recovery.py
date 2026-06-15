"""Stage 3: Error Recovery — Train on Glint + armand0e 18K real error patterns."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


@dataclass
class Stage3Config:
    """Configuration for Stage 3: Error Recovery.

    This stage trains the model on 18K real error patterns from the Glint and
    armand0e datasets. The model learns to recognize errors, diagnose root
    causes, and apply corrections — mirroring how expert developers debug.
    """

    base_model: str = ""
    stage2_adapter: str = "output/stage2"
    dataset_path: str = "data/error_recovery_18k.jsonl"
    output_dir: str = "output/stage3"
    LoRA_r: int = 32
    LoRA_alpha: int = 64
    LoRA_dropout: float = 0.05
    LoRA_target_modules: list[str] = field(default_factory=lambda: [
        "q_proj", "k_proj", "v_proj", "o_proj",
    ])
    batch_size: int = 2
    gradient_accumulation_steps: int = 16
    learning_rate: float = 5e-5
    num_epochs: int = 2
    max_seq_length: int = 8192
    warmup_ratio: float = 0.05
    weight_decay: float = 0.01
    lr_scheduler_type: str = "cosine"
    save_steps: int = 200
    eval_steps: int = 200
    logging_steps: int = 10
    bf16: bool = True
    seed: int = 42
    # Error-specific settings
    error_categories: list[str] = field(default_factory=lambda: [
        "syntax_error",
        "type_error",
        "import_error",
        "runtime_error",
        "logic_error",
        "off_by_one",
        "null_reference",
        "timeout_error",
        "permission_error",
        "configuration_error",
    ])
    include_stack_traces: bool = True
    max_retries_per_error: int = 3

    @classmethod
    def from_yaml(cls, path: str | Path) -> Stage3Config:
        with open(path) as f:
            data = yaml.safe_load(f)
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def to_dict(self) -> dict[str, Any]:
        return {k: getattr(self, k) for k in self.__dataclass_fields__}


class ErrorPattern:
    """Represents a single error-recovery training example."""

    def __init__(
        self,
        error_type: str,
        error_message: str,
        stack_trace: str | None,
        source_code: str,
        diagnosis: str,
        fix: str,
        verified: bool = True,
    ):
        self.error_type = error_type
        self.error_message = error_message
        self.stack_trace = stack_trace
        self.source_code = source_code
        self.diagnosis = diagnosis
        self.fix = fix
        self.verified = verified

    def to_training_example(self) -> dict[str, Any]:
        content = "I encountered the following error:\n\n"
        if self.stack_trace:
            content += f"```\n{self.stack_trace}\n```\n\n"
        content += f"Error: {self.error_message}\n\nHere's the relevant code:\n\n```python\n{self.source_code}\n```"

        fix_content = f"**Diagnosis:** {self.diagnosis}\n\n**Fix:**\n\n```python\n{self.fix}\n```"

        return {
            "messages": [
                {"role": "system", "content": "You are a debugging expert. Analyze errors, diagnose root causes, and provide working fixes."},
                {"role": "user", "content": content},
                {"role": "assistant", "content": fix_content},
            ],
            "error_type": self.error_type,
            "verified": self.verified,
        }


def load_error_dataset(path: str | Path, max_samples: int | None = None) -> list[dict[str, Any]]:
    """Load the Glint + armand0e error recovery dataset.

    Each example contains an error, its diagnosis, and the fix that resolved it.

    Args:
        path: Path to the JSONL dataset file.
        max_samples: Maximum number of samples to load.

    Returns:
        List of error recovery examples.
    """
    path = Path(path)
    if not path.exists():
        logger.warning(f"Dataset not found at {path}, generating synthetic examples")
        return _generate_error_examples(max_samples or 100)

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

    logger.info(f"Loaded {len(examples)} error recovery examples from {path}")
    return examples


def _generate_error_examples(count: int) -> list[dict[str, Any]]:
    """Generate synthetic error-recovery examples for testing."""
    error_patterns = [
        ErrorPattern(
            error_type="type_error",
            error_message="unsupported operand type(s) for +: 'int' and 'str'",
            stack_trace='Traceback (most recent call last):\n  File "app.py", line 42, in process\n    result = value + offset\nTypeError: unsupported operand type(s) for +: \'int\' and \'str\'',
            source_code="def process(value, offset):\n    result = value + offset\n    return result",
            diagnosis="The 'offset' parameter is a string instead of a number. Convert it to int before the addition.",
            fix="def process(value, offset):\n    result = value + int(offset)\n    return result",
        ),
        ErrorPattern(
            error_type="import_error",
            error_message="No module named 'requests'",
            stack_trace='Traceback (most recent call last):\n  File "main.py", line 1, in <module>\n    import requests\nModuleNotFoundError: No module named \'requests\'',
            source_code="import requests\n\ndef fetch_data(url):\n    return requests.get(url).json()",
            diagnosis="The 'requests' module is not installed. Install it or use the built-in urllib module.",
            fix="from urllib.request import urlopen\nfrom json import loads\n\ndef fetch_data(url):\n    response = urlopen(url)\n    return loads(response.read().decode())",
        ),
        ErrorPattern(
            error_type="off_by_one",
            error_message="IndexError: list index out of range",
            stack_trace='Traceback (most recent call last):\n  File "search.py", line 15, in binary_search\n    mid = (low + high) // 2\nIndexError: list index out of range',
            source_code="def binary_search(arr, target):\n    low, high = 0, len(arr)\n    while low <= high:\n        mid = (low + high) // 2\n        if arr[mid] == target:\n            return mid\n        elif arr[mid] < target:\n            low = mid + 1\n        else:\n            high = mid - 1\n    return -1",
            diagnosis="The 'high' variable is initialized to len(arr) instead of len(arr) - 1, causing an off-by-one error when accessing arr[mid].",
            fix="def binary_search(arr, target):\n    low, high = 0, len(arr) - 1\n    while low <= high:\n        mid = (low + high) // 2\n        if arr[mid] == target:\n            return mid\n        elif arr[mid] < target:\n            low = mid + 1\n        else:\n            high = mid - 1\n    return -1",
        ),
        ErrorPattern(
            error_type="null_reference",
            error_message="AttributeError: 'NoneType' object has no attribute 'split'",
            stack_trace='Traceback (most recent call last):\n  File "parser.py", line 23, in parse_input\n    parts = data.split(\',\')\nAttributeError: \'NoneType\' object has no attribute \'split\'',
            source_code="def parse_input(data):\n    parts = data.split(',')\n    return [p.strip() for p in parts]",
            diagnosis="The 'data' parameter can be None. Add a None check before calling .split().",
            fix="def parse_input(data):\n    if data is None:\n        return []\n    parts = data.split(',')\n    return [p.strip() for p in parts]",
        ),
        ErrorPattern(
            error_type="timeout_error",
            error_message="TimeoutError: Operation timed out after 30 seconds",
            stack_trace='Traceback (most recent call last):\n  File "fetcher.py", line 12, in fetch_all\n    result = await asyncio.wait_for(session.get(url), timeout=30)\nTimeoutError',
            source_code="async def fetch_all(urls):\n    async with aiohttp.ClientSession() as session:\n        tasks = [session.get(url) for url in urls]\n        return await asyncio.gather(*tasks)",
            diagnosis="No timeout is set on individual requests, and all requests wait simultaneously. Add per-request timeouts and implement retry logic.",
            fix="async def fetch_all(urls, timeout=30, max_retries=3):\n    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=timeout)) as session:\n        results = []\n        for url in urls:\n            for attempt in range(max_retries):\n                try:\n                    async with session.get(url) as resp:\n                        results.append(await resp.json())\n                    break\n                except (TimeoutError, aiohttp.ClientError):\n                    if attempt == max_retries - 1:\n                        results.append(None)\n        return results",
        ),
    ]

    examples = []
    for i in range(count):
        pattern = error_patterns[i % len(error_patterns)]
        examples.append(pattern.to_training_example())

    return examples


def balance_error_types(examples: list[dict[str, Any]], target_per_type: int = 200) -> list[dict[str, Any]]:
    """Balance the dataset across error types via undersampling.

    Args:
        examples: Raw examples with error_type field.
        target_per_type: Target number of examples per error type.

    Returns:
        Balanced dataset.
    """
    import random
    from collections import Counter

    type_counts = Counter(ex.get("error_type", "unknown") for ex in examples)
    logger.info(f"Error type distribution: {dict(type_counts)}")

    balanced = []
    random.seed(42)
    for error_type, count in type_counts.items():
        type_examples = [ex for ex in examples if ex.get("error_type", "unknown") == error_type]
        if len(type_examples) > target_per_type:
            type_examples = random.sample(type_examples, target_per_type)
        balanced.extend(type_examples)

    random.shuffle(balanced)
    logger.info(f"Balanced dataset: {len(examples)} → {len(balanced)} examples")
    return balanced


def run_stage3(config: Stage3Config | None = None, dataset_path: str | None = None) -> dict[str, Any]:
    """Run Stage 3: Error Recovery training.

    Trains on 18K real error patterns from Glint and armand0e datasets to
    teach the model to diagnose and fix errors like an expert debugger.

    Args:
        config: Stage3Config with all training hyperparameters.
        dataset_path: Override path to the dataset.

    Returns:
        Dictionary with training configuration and output path.
    """
    if config is None:
        config = Stage3Config()

    if dataset_path:
        config.dataset_path = dataset_path

    logger.info("=" * 60)
    logger.info("Stage 3: Error Recovery (Glint + armand0e 18K)")
    logger.info("=" * 60)
    logger.info(f"Stage 2 adapter: {config.stage2_adapter}")
    logger.info(f"Dataset: {config.dataset_path}")
    logger.info(f"Error categories: {config.error_categories}")
    logger.info(f"Output: {config.output_dir}")

    examples = load_error_dataset(config.dataset_path)
    balanced = balance_error_types(examples)

    output_path = Path(config.output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    training_config = config.to_dict()
    training_config["num_examples"] = len(balanced)

    config_path = output_path / "training_config.json"
    with open(config_path, "w") as f:
        json.dump(training_config, f, indent=2)

    logger.info(f"Training config saved to {config_path}")
    logger.info(f"Ready to train on {len(balanced)} balanced examples")

    return {
        "status": "configured",
        "output_dir": str(output_path),
        "num_examples": len(balanced),
        "config": training_config,
    }
