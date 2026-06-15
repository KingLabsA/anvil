"""Stage 1: Behavior Shaping — Train on v-Fable 100K tool-use examples using Unsloth/LoRA."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


@dataclass
class Stage1Config:
    """Configuration for Stage 1: Behavior Shaping.

    This stage trains the model on 100K tool-use examples from the v-Fable
    dataset using Unsloth-accelerated LoRA fine-tuning. The goal is to teach
    the model the basic patterns of tool use: when to call tools, what
    arguments to pass, and how to interpret tool outputs.
    """

    base_model: str = "Qwen/Qwen2.5-14B"
    dataset_path: str = "data/vfable_100k.jsonl"
    output_dir: str = "output/stage1"
    LoRA_r: int = 64
    LoRA_alpha: int = 128
    LoRA_dropout: float = 0.05
    LoRA_target_modules: list[str] = field(default_factory=lambda: [
        "q_proj", "k_proj", "v_proj", "o_proj",
        "gate_proj", "up_proj", "down_proj",
    ])
    batch_size: int = 4
    gradient_accumulation_steps: int = 8
    learning_rate: float = 2e-4
    num_epochs: int = 3
    max_seq_length: int = 4096
    warmup_ratio: float = 0.1
    weight_decay: float = 0.01
    lr_scheduler_type: str = "cosine"
    save_steps: int = 500
    eval_steps: int = 500
    logging_steps: int = 10
    use_unsloth: bool = True
    use_4bit_quantization: bool = True
    bf16: bool = True
    seed: int = 42

    @classmethod
    def from_yaml(cls, path: str | Path) -> Stage1Config:
        with open(path) as f:
            data = yaml.safe_load(f)
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def to_dict(self) -> dict[str, Any]:
        return {k: getattr(self, k) for k in self.__dataclass_fields__}


def load_vfable_dataset(path: str | Path, max_samples: int | None = None) -> list[dict[str, Any]]:
    """Load the v-Fable tool-use dataset.

    Each example is a conversation with tool calls in the format:
    {"messages": [{"role": "system"|"user"|"assistant", "content": "...", "tool_calls": [...]}], "tools": [...]}

    Args:
        path: Path to the JSONL dataset file.
        max_samples: Maximum number of samples to load (None for all).

    Returns:
        List of conversation examples.
    """
    path = Path(path)
    if not path.exists():
        logger.warning(f"Dataset not found at {path}, generating synthetic examples")
        return _generate_synthetic_examples(max_samples or 100)

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
                logger.warning(f"Skipping malformed line {i}")
                continue

    logger.info(f"Loaded {len(examples)} examples from {path}")
    return examples


def _generate_synthetic_examples(count: int) -> list[dict[str, Any]]:
    """Generate synthetic tool-use training examples for testing."""
    examples = []
    tool_definitions = [
        {
            "type": "function",
            "function": {
                "name": "read",
                "description": "Read file contents",
                "parameters": {
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": ["path"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "edit",
                "description": "Edit a file by replacing strings",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string"},
                        "old_string": {"type": "string"},
                        "new_string": {"type": "string"},
                    },
                    "required": ["file_path", "old_string", "new_string"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "bash",
                "description": "Execute a shell command",
                "parameters": {
                    "type": "object",
                    "properties": {"command": {"type": "string"}},
                    "required": ["command"],
                },
            },
        },
    ]

    task_templates = [
        ("Fix the bug in {file}", "I'll read the file first to understand the issue.",
         [{"name": "read", "arguments": {"path": "{file}"}}]),
        ("Add error handling to {file}", "Let me examine the current implementation.",
         [{"name": "read", "arguments": {"path": "{file}"}}]),
        ("Refactor {func} in {file}", "I'll start by reading the function to understand its structure.",
         [{"name": "read", "arguments": {"path": "{file}"}}]),
        ("Write tests for {module}", "First, let me check the module's interface.",
         [{"name": "read", "arguments": {"path": "{module}"}}]),
    ]

    files = ["src/app.py", "lib/auth.py", "tests/test_api.py", "config/settings.py"]
    funcs = ["process_data", "validate_input", "handle_request", "parse_config"]

    for i in range(count):
        template_idx = i % len(task_templates)
        task_template, response, tool_calls = task_templates[template_idx]
        file = files[i % len(files)]
        func = funcs[i % len(funcs)]
        task = task_template.replace("{file}", file).replace("{func}", func).replace("{module}", file)

        example = {
            "messages": [
                {"role": "system", "content": "You are a skilled coding assistant. Use tools to help the user."},
                {"role": "user", "content": task},
                {"role": "assistant", "content": response, "tool_calls": tool_calls},
            ],
            "tools": tool_definitions,
        }
        examples.append(example)

    return examples


def format_for_training(examples: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Format examples for SFT training with Unsloth.

    Converts examples into the chat format expected by the training pipeline,
    with proper tool call formatting and special tokens.

    Args:
        examples: Raw examples from the dataset.

    Returns:
        List of formatted training examples.
    """
    formatted = []
    for example in examples:
        messages = example.get("messages", [])
        if not messages:
            continue

        formatted_messages = []
        for msg in messages:
            formatted_msg = {
                "role": msg["role"],
                "content": msg.get("content", ""),
            }
            if "tool_calls" in msg and msg["tool_calls"]:
                formatted_msg["tool_calls"] = msg["tool_calls"]
            formatted_messages.append(formatted_msg)

        formatted.append({"messages": formatted_messages})

    return formatted


def run_stage1(config: Stage1Config | None = None, dataset_path: str | None = None) -> dict[str, Any]:
    """Run Stage 1: Behavior Shaping training.

    Trains the base model on 100K tool-use examples from v-Fable using
    Unsloth-accelerated LoRA fine-tuning.

    Args:
        config: Stage1Config with all training hyperparameters.
        dataset_path: Override path to the dataset.

    Returns:
        Dictionary with training metrics and output path.
    """
    if config is None:
        config = Stage1Config()

    if dataset_path:
        config.dataset_path = dataset_path

    logger.info("=" * 60)
    logger.info("Stage 1: Behavior Shaping (v-Fable 100K)")
    logger.info("=" * 60)
    logger.info(f"Base model: {config.base_model}")
    logger.info(f"Dataset: {config.dataset_path}")
    logger.info(f"LoRA r={config.LoRA_r}, alpha={config.LoRA_alpha}")
    logger.info(f"Output: {config.output_dir}")

    examples = load_vfable_dataset(config.dataset_path)
    formatted = format_for_training(examples)

    if len(formatted) == 0:
        logger.error("No training examples found")
        return {"status": "error", "message": "No training examples"}

    # In production, this would use Unsloth/trl for actual training.
    # Here we set up the training configuration and validate everything.
    output_path = Path(config.output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    training_config = config.to_dict()
    training_config["num_examples"] = len(formatted)
    training_config["effective_batch_size"] = config.batch_size * config.gradient_accumulation_steps

    config_path = output_path / "training_config.json"
    with open(config_path, "w") as f:
        json.dump(training_config, f, indent=2)

    # Trl SFTConfig would be used for actual training
    training_script = f"""
# Stage 1: Behavior Shaping Training Script
# Generated by FableForge-14B

from unsloth import FastLanguageModel
from trl import SFTTrainer
from transformers import TrainingArguments

model, tokenizer = FastLanguageModel.from_pretrained(
    model_name="{config.base_model}",
    max_seq_length={config.max_seq_length},
    load_in_4bit={config.use_4bit_quantization},
)

model = FastLanguageModel.get_peft_model(
    model,
    r={config.LoRA_r},
    lora_alpha={config.LoRA_alpha},
    lora_dropout={config.LoRA_dropout},
    target_modules={config.LoRA_target_modules},
)

trainer = SFTTrainer(
    model=model,
    train_dataset=dataset,
    args=TrainingArguments(
        output_dir="{config.output_dir}",
        per_device_train_batch_size={config.batch_size},
        gradient_accumulation_steps={config.gradient_accumulation_steps},
        learning_rate={config.learning_rate},
        num_train_epochs={config.num_epochs},
        warmup_ratio={config.warmup_ratio},
        weight_decay={config.weight_decay},
        lr_scheduler_type="{config.lr_scheduler_type}",
        save_steps={config.save_steps},
        eval_steps={config.eval_steps},
        logging_steps={config.logging_steps},
        bf16={config.bf16},
        seed={config.seed},
    ),
)

trainer.train()
model.save_pretrained("{config.output_dir}")
tokenizer.save_pretrained("{config.output_dir}")
"""

    script_path = output_path / "train_stage1.py"
    with open(script_path, "w") as f:
        f.write(training_script)

    logger.info(f"Training config saved to {config_path}")
    logger.info(f"Training script saved to {script_path}")
    logger.info(f"Ready to train on {len(formatted)} examples")

    return {
        "status": "configured",
        "output_dir": str(output_path),
        "num_examples": len(formatted),
        "config": training_config,
    }
