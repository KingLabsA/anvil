"""Distill skills into LoRA weights using Unsloth and PEFT.

Loads a base model, creates training data from SkillExample objects,
trains a LoRA adapter, and saves adapter weights.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import yaml

from trace_compiler.skill_extractor import SkillExample, SkillType

logger = logging.getLogger(__name__)

DEFAULT_SYSTEM_PROMPTS: dict[SkillType, str] = {
    SkillType.DEBUG: (
        "You are an expert debugging assistant. When presented with an error, "
        "traceback, or failing behavior, analyze the root cause and provide "
        "a targeted fix with explanation."
    ),
    SkillType.EDIT: (
        "You are an expert code editor. Given a task and existing code, "
        "make precise, minimal edits that accomplish the goal while "
        "preserving existing behavior and style."
    ),
    SkillType.VERIFY: (
        "You are an expert verification assistant. After making changes, "
        "you verify correctness by running tests, checking outputs, and "
        "confirming the change has the intended effect."
    ),
    SkillType.RECOVER: (
        "You are an expert error recovery assistant. When an operation fails, "
        "you analyze the error, determine recovery steps, and implement "
        "a fix that addresses the root cause."
    ),
    SkillType.PLAN: (
        "You are an expert planning assistant. Before implementing changes, "
        "you outline a clear strategy, identify affected components, and "
        "sequence the work for minimal risk and maximum clarity."
    ),
}

MODEL_ALIASES: dict[str, str] = {
    "qwen3-1.5b": "Qwen/Qwen2.5-Coder-1.5B",
    "qwen3-7b": "Qwen/Qwen2.5-Coder-7B",
    "qwen2.5-1.5b": "Qwen/Qwen2.5-Coder-1.5B",
    "qwen2.5-7b": "Qwen/Qwen2.5-Coder-7B",
    "codellama-7b": "codellama/CodeLlama-7b-hf",
    "mistral-7b": "mistralai/Mistral-7B-v0.1",
}


def resolve_model(model: str) -> str:
    return MODEL_ALIASES.get(model.lower(), model)


class TrainingConfig:
    def __init__(
        self,
        model_name: str = "Qwen/Qwen2.5-Coder-1.5B",
        lora_r: int = 16,
        lora_alpha: int = 32,
        lora_dropout: float = 0.05,
        learning_rate: float = 2e-4,
        num_epochs: int = 3,
        batch_size: int = 4,
        gradient_accumulation_steps: int = 4,
        max_seq_length: int = 4096,
        warmup_steps: int = 10,
        weight_decay: float = 0.01,
        logging_steps: int = 10,
        save_steps: int = 100,
        output_dir: str = "./output",
    ) -> None:
        self.model_name = model_name
        self.lora_r = lora_r
        self.lora_alpha = lora_alpha
        self.lora_dropout = lora_dropout
        self.learning_rate = learning_rate
        self.num_epochs = num_epochs
        self.batch_size = batch_size
        self.gradient_accumulation_steps = gradient_accumulation_steps
        self.max_seq_length = max_seq_length
        self.warmup_steps = warmup_steps
        self.weight_decay = weight_decay
        self.logging_steps = logging_steps
        self.save_steps = save_steps
        self.output_dir = output_dir

    @classmethod
    def from_yaml(cls, path: Path | str) -> TrainingConfig:
        path = Path(path)
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
        training = data.get("training", data)
        return cls(
            model_name=training.get("model_name", "Qwen/Qwen2.5-Coder-1.5B"),
            lora_r=training.get("lora_r", 16),
            lora_alpha=training.get("lora_alpha", 32),
            lora_dropout=training.get("lora_dropout", 0.05),
            learning_rate=training.get("learning_rate", 2e-4),
            num_epochs=training.get("num_epochs", 3),
            batch_size=training.get("batch_size", 4),
            gradient_accumulation_steps=training.get("gradient_accumulation_steps", 4),
            max_seq_length=training.get("max_seq_length", 4096),
            warmup_steps=training.get("warmup_steps", 10),
            weight_decay=training.get("weight_decay", 0.01),
            logging_steps=training.get("logging_steps", 10),
            save_steps=training.get("save_steps", 100),
            output_dir=training.get("output_dir", "./output"),
        )


class Distiller:
    def __init__(self, config: TrainingConfig | None = None) -> None:
        self.config = config or TrainingConfig()
        self._model = None
        self._tokenizer = None

    def _load_model(self):
        try:
            from unsloth import FastLanguageModel

            model, tokenizer = FastLanguageModel.from_pretrained(
                model_name=self.config.model_name,
                max_seq_length=self.config.max_seq_length,
                load_in_4bit=True,
                dtype=None,
            )
            model = FastLanguageModel.get_peft_model(
                model,
                r=self.config.lora_r,
                lora_alpha=self.config.lora_alpha,
                lora_dropout=self.config.lora_dropout,
                target_modules=[
                    "q_proj", "k_proj", "v_proj", "o_proj",
                    "gate_proj", "up_proj", "down_proj",
                ],
                bias="none",
                use_gradient_checkpointing="unsloth",
                random_state=42,
            )
            self._model = model
            self._tokenizer = tokenizer
            return model, tokenizer
        except ImportError:
            logger.info("Unsloth not available, falling back to standard PEFT")
            return self._load_model_peft()

    def _load_model_peft(self):
        from transformers import AutoModelForCausalLM, AutoTokenizer

        model = AutoModelForCausalLM.from_pretrained(
            self.config.model_name,
            load_in_4bit=True,
            device_map="auto",
        )
        tokenizer = AutoTokenizer.from_pretrained(self.config.model_name)
        tokenizer.pad_token = tokenizer.eos_token

        from peft import LoraConfig, get_peft_model

        lora_config = LoraConfig(
            r=self.config.lora_r,
            lora_alpha=self.config.lora_alpha,
            lora_dropout=self.config.lora_dropout,
            target_modules=[
                "q_proj", "k_proj", "v_proj", "o_proj",
                "gate_proj", "up_proj", "down_proj",
            ],
            bias="none",
            task_type="CAUSAL_LM",
        )
        model = get_peft_model(model, lora_config)
        self._model = model
        self._tokenizer = tokenizer
        return model, tokenizer

    def _build_system_prompt(self, skill_type: SkillType) -> str:
        return DEFAULT_SYSTEM_PROMPTS.get(
            skill_type,
            "You are a helpful coding assistant.",
        )

    def _create_dataset(
        self,
        examples: list[SkillExample],
        skill_type: SkillType,
    ) -> Any:
        from datasets import Dataset

        system_prompt = self._build_system_prompt(skill_type)
        formatted: list[dict[str, str]] = []

        for ex in examples:
            messages = [{"role": "system", "content": system_prompt}]
            for msg in ex.messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if isinstance(content, list):
                    parts: list[str] = []
                    for block in content:
                        if isinstance(block, dict):
                            if block.get("type") == "text":
                                parts.append(block.get("text", ""))
                            elif block.get("type") == "tool_use":
                                name = block.get("name", "unknown")
                                inp = block.get("input", {})
                                parts.append(f"[Tool: {name}({json.dumps(inp)})]")
                            elif block.get("type") == "thinking":
                                parts.append(f"[Thinking: {block.get('thinking', '')}]")
                        else:
                            parts.append(str(block))
                    content = "\n".join(parts)
                if content.strip():
                    messages.append({"role": role, "content": content})

            if len(messages) < 2:
                continue

            text = self._tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=False
            )
            formatted.append({"text": text})

        if not formatted:
            raise ValueError(f"No valid training samples for skill type: {skill_type.value}")

        return Dataset.from_list(formatted)

    def _create_dataset_from_messages(
        self,
        all_messages: list[list[dict[str, Any]]],
        skill_type: SkillType,
    ) -> Any:
        from datasets import Dataset

        system_prompt = self._build_system_prompt(skill_type)
        formatted: list[dict[str, str]] = []

        for messages in all_messages:
            full_messages = [{"role": "system", "content": system_prompt}]
            for msg in messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if isinstance(content, list):
                    parts: list[str] = []
                    for block in content:
                        if isinstance(block, dict):
                            if block.get("type") == "text":
                                parts.append(block.get("text", ""))
                            elif block.get("type") == "tool_use":
                                name = block.get("name", "unknown")
                                inp = block.get("input", {})
                                parts.append(f"[Tool: {name}({json.dumps(inp)})]")
                            elif block.get("type") == "thinking":
                                parts.append(f"[Thinking: {block.get('thinking', '')}]")
                        else:
                            parts.append(str(block))
                    content = "\n".join(parts)
                if content.strip():
                    full_messages.append({"role": role, "content": content})

            if len(full_messages) < 2:
                continue

            text = self._tokenizer.apply_chat_template(
                full_messages, tokenize=False, add_generation_prompt=False
            )
            formatted.append({"text": text})

        if not formatted:
            raise ValueError(f"No valid training samples for skill type: {skill_type.value}")

        return Dataset.from_list(formatted)

    def train(
        self,
        examples: list[SkillExample],
        skill_type: SkillType,
        output_dir: str | None = None,
    ) -> Path:
        output_dir = output_dir or self.config.output_dir
        output_path = Path(output_dir) / skill_type.value
        output_path.mkdir(parents=True, exist_ok=True)

        model, tokenizer = self._load_model()
        dataset = self._create_dataset(examples, skill_type)

        from transformers import TrainingArguments
        from trl import SFTTrainer

        training_args = TrainingArguments(
            output_dir=str(output_path),
            num_train_epochs=self.config.num_epochs,
            per_device_train_batch_size=self.config.batch_size,
            gradient_accumulation_steps=self.config.gradient_accumulation_steps,
            learning_rate=self.config.learning_rate,
            warmup_steps=self.config.warmup_steps,
            weight_decay=self.config.weight_decay,
            logging_steps=self.config.logging_steps,
            save_steps=self.config.save_steps,
            fp16=not hasattr(model, "is_quantized") or not model.is_quantized,
            bf16=False,
            optim="adamw_8bit",
            seed=42,
            report_to="none",
        )

        trainer = SFTTrainer(
            model=model,
            tokenizer=tokenizer,
            train_dataset=dataset,
            args=training_args,
            max_seq_length=self.config.max_seq_length,
            dataset_text_field="text",
        )

        logger.info(
            "Starting LoRA training for %s skill: %d examples",
            skill_type.value,
            len(examples),
        )

        trainer.train()

        model.save_pretrained(str(output_path))
        tokenizer.save_pretrained(str(output_path))

        config_metadata = {
            "skill_type": skill_type.value,
            "base_model": self.config.model_name,
            "lora_r": self.config.lora_r,
            "lora_alpha": self.config.lora_alpha,
            "num_examples": len(examples),
            "num_epochs": self.config.num_epochs,
        }
        with open(output_path / "adapter_config.json", "w", encoding="utf-8") as f:
            json.dump(config_metadata, f, indent=2)

        logger.info("Saved LoRA adapter to %s", output_path)
        return output_path

    def train_from_messages(
        self,
        all_messages: list[list[dict[str, Any]]],
        skill_type: SkillType,
        output_dir: str | None = None,
    ) -> Path:
        output_dir = output_dir or self.config.output_dir
        output_path = Path(output_dir) / skill_type.value
        output_path.mkdir(parents=True, exist_ok=True)

        model, tokenizer = self._load_model()
        dataset = self._create_dataset_from_messages(all_messages, skill_type)

        from transformers import TrainingArguments
        from trl import SFTTrainer

        training_args = TrainingArguments(
            output_dir=str(output_path),
            num_train_epochs=self.config.num_epochs,
            per_device_train_batch_size=self.config.batch_size,
            gradient_accumulation_steps=self.config.gradient_accumulation_steps,
            learning_rate=self.config.learning_rate,
            warmup_steps=self.config.warmup_steps,
            weight_decay=self.config.weight_decay,
            logging_steps=self.config.logging_steps,
            save_steps=self.config.save_steps,
            fp16=not hasattr(model, "is_quantized") or not model.is_quantized,
            bf16=False,
            optim="adamw_8bit",
            seed=42,
            report_to="none",
        )

        trainer = SFTTrainer(
            model=model,
            tokenizer=tokenizer,
            train_dataset=dataset,
            args=training_args,
            max_seq_length=self.config.max_seq_length,
            dataset_text_field="text",
        )

        logger.info(
            "Starting LoRA training for %s skill: %d message groups",
            skill_type.value,
            len(all_messages),
        )

        trainer.train()

        model.save_pretrained(str(output_path))
        tokenizer.save_pretrained(str(output_path))

        config_metadata = {
            "skill_type": skill_type.value,
            "base_model": self.config.model_name,
            "lora_r": self.config.lora_r,
            "lora_alpha": self.config.lora_alpha,
            "num_examples": len(all_messages),
            "num_epochs": self.config.num_epochs,
        }
        with open(output_path / "adapter_config.json", "w", encoding="utf-8") as f:
            json.dump(config_metadata, f, indent=2)

        logger.info("Saved LoRA adapter to %s", output_path)
        return output_path
