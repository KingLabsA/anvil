"""Fine-tune Qwen3-1.5B on shell commands using LoRA or full fine-tuning.

Supports Unsloth for fast training on consumer GPUs.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from shell_whisperer.data_extractor import TrainingPair, load_training_data
from shell_whisperer.prompts import get_prompt

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "Qwen/Qwen3-1.5B"
DEFAULT_MAX_SEQ_LENGTH = 2048


@dataclass
class TrainConfig:
    """Configuration for training."""

    model_name: str = DEFAULT_MODEL
    output_dir: str = "./models/shell-whisperer-lora"
    epochs: int = 3
    learning_rate: float = 2e-4
    batch_size: int = 4
    gradient_accumulation_steps: int = 4
    max_seq_length: int = DEFAULT_MAX_SEQ_LENGTH
    lora_r: int = 16
    lora_alpha: int = 32
    lora_dropout: float = 0.05
    lora_target_modules: list[str] = field(
        default_factory=lambda: [
            "q_proj", "k_proj", "v_proj", "o_proj",
            "gate_proj", "up_proj", "down_proj",
        ]
    )
    use_unsloth: bool = True
    use_4bit: bool = True
    full_finetune: bool = False
    warmup_ratio: float = 0.03
    weight_decay: float = 0.01
    logging_steps: int = 10
    save_steps: int = 100
    eval_steps: int = 100
    fsdp: bool = False
    os_type: str = "linux"


def load_base_model(
    model_name: str = DEFAULT_MODEL,
    max_seq_length: int = DEFAULT_MAX_SEQ_LENGTH,
    load_in_4bit: bool = True,
    use_unsloth: bool = True,
) -> tuple[Any, Any]:
    """Load the base model and tokenizer."""
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

    if use_unsloth:
        try:
            from unsloth import FastLanguageModel

            model, tokenizer = FastLanguageModel.from_pretrained(
                model_name=model_name,
                max_seq_length=max_seq_length,
                load_in_4bit=load_in_4bit,
                dtype=None,  # auto-detect
            )
            logger.info("Loaded model via Unsloth: %s", model_name)
            return model, tokenizer
        except ImportError:
            logger.warning("Unsloth not available, falling back to standard loading")

    bnb_config = None
    if load_in_4bit:
        bnb_config = BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.bfloat16,
            bnb_4bit_use_double_quant=True,
        )

    tokenizer = AutoTokenizer.from_pretrained(
        model_name,
        padding_side="right",
        use_fast=True,
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        quantization_config=bnb_config,
        device_map="auto",
        torch_dtype=torch.bfloat16 if torch.cuda.is_available() else torch.float32,
        attn_implementation="sdpa",
    )

    logger.info("Loaded model: %s", model_name)
    return model, tokenizer


def prepare_dataset(
    training_pairs: list[TrainingPair],
    tokenizer: Any,
    system_prompt: str | None = None,
    max_seq_length: int = DEFAULT_MAX_SEQ_LENGTH,
    test_split: float = 0.1,
) -> tuple[Any, Any]:
    """Convert training pairs into a tokenized HuggingFace Dataset."""
    from datasets import Dataset

    if system_prompt is None:
        system_prompt = get_prompt("linux")

    def _format_messages(pair: TrainingPair) -> dict:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": pair.natural_language},
            {"role": "assistant", "content": pair.bash_command},
        ]
        return {"messages": messages}

    formatted = [_format_messages(p) for p in training_pairs]

    def _tokenize(example: dict) -> dict:
        text = tokenizer.apply_chat_template(
            example["messages"],
            tokenize=False,
            add_generation_prompt=False,
        )
        tokenized = tokenizer(
            text,
            truncation=True,
            max_length=max_seq_length,
            padding=False,
        )
        tokenized["labels"] = tokenized["input_ids"].copy()
        return tokenized

    dataset = Dataset.from_list(formatted)
    dataset = dataset.map(_tokenize, remove_columns=dataset.column_names)

    if test_split > 0 and len(dataset) > 1:
        split = dataset.train_test_split(test_size=test_split, seed=42)
        return split["train"], split["test"]

    return dataset, Dataset.from_list([])


def train_lora(
    output_dir: str = "./models/shell-whisperer-lora",
    config: TrainConfig | None = None,
    training_pairs: list[TrainingPair] | None = None,
    data_path: str | None = None,
) -> str:
    """Fine-tune using LoRA (Low-Rank Adaptation)."""
    import torch
    from transformers import DataCollatorForSeq2Seq, Trainer, TrainingArguments

    if config is None:
        config = TrainConfig(output_dir=output_dir)

    # Load data
    if training_pairs is None:
        paths = [data_path] if data_path else []
        training_pairs = load_training_data(*paths, include_builtin=True)

    if not training_pairs:
        raise ValueError("No training data provided or loaded")

    logger.info("Training with %d pairs", len(training_pairs))

    # Load model
    model, tokenizer = load_base_model(
        model_name=config.model_name,
        max_seq_length=config.max_seq_length,
        load_in_4bit=config.use_4bit,
        use_unsloth=config.use_unsloth,
    )

    # Add LoRA
    if not config.full_finetune:
        if config.use_unsloth:
            try:
                from unsloth import FastLanguageModel

                model = FastLanguageModel.get_peft_model(
                    model,
                    r=config.lora_r,
                    lora_alpha=config.lora_alpha,
                    lora_dropout=config.lora_dropout,
                    target_modules=config.lora_target_modules,
                    bias="none",
                    use_gradient_checkpointing="unsloth",
                    random_state=42,
                )
            except ImportError:
                model = _add_lora_standard(model, config)
        else:
            model = _add_lora_standard(model, config)

    # Prepare dataset
    system_prompt = get_prompt(config.os_type)
    train_ds, eval_ds = prepare_dataset(
        training_pairs,
        tokenizer,
        system_prompt=system_prompt,
        max_seq_length=config.max_seq_length,
    )

    # Training arguments
    training_args = TrainingArguments(
        output_dir=config.output_dir,
        num_train_epochs=config.epochs,
        per_device_train_batch_size=config.batch_size,
        gradient_accumulation_steps=config.gradient_accumulation_steps,
        learning_rate=config.learning_rate,
        warmup_ratio=config.warmup_ratio,
        weight_decay=config.weight_decay,
        logging_steps=config.logging_steps,
        save_steps=config.save_steps,
        eval_strategy="steps" if len(eval_ds) > 0 else "no",
        eval_steps=config.eval_steps if len(eval_ds) > 0 else None,
        bf16=torch.cuda.is_available() and torch.cuda.is_bf16_supported(),
        tf32=torch.cuda.is_available(),
        optim="adamw_8bit" if config.use_4bit else "adamw_torch",
        lr_scheduler_type="cosine",
        seed=42,
        report_to="none",
        remove_unused_columns=False,
    )

    # Data collator
    data_collator = DataCollatorForSeq2Seq(
        tokenizer=tokenizer,
        padding=True,
        max_length=config.max_seq_length,
    )

    # Train
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=eval_ds if len(eval_ds) > 0 else None,
        data_collator=data_collator,
    )

    logger.info("Starting training...")
    trainer.train()

    # Save
    output_path = Path(config.output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    if not config.full_finetune:
        model.save_pretrained(str(output_path))
        tokenizer.save_pretrained(str(output_path))
    else:
        model.save_pretrained(str(output_path))
        tokenizer.save_pretrained(str(output_path))

    logger.info("Model saved to %s", output_path)
    return str(output_path)


def _add_lora_standard(model: Any, config: TrainConfig) -> Any:
    """Add LoRA adapter using standard PEFT (not Unsloth)."""
    from peft import LoraConfig, TaskType, get_peft_model

    lora_config = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=config.lora_r,
        lora_alpha=config.lora_alpha,
        lora_dropout=config.lora_dropout,
        target_modules=config.lora_target_modules,
        bias="none",
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()
    return model


def merge_and_save(
    adapter_path: str = "./models/shell-whisperer-lora",
    base_model_name: str = DEFAULT_MODEL,
    output_dir: str = "./models/shell-whisperer-merged",
    push_to_hub: bool = False,
    hub_repo_id: str | None = None,
) -> str:
    """Merge LoRA adapter with base model and save the result."""
    import torch
    from peft import AutoPeftModelForCausalLM
    from transformers import AutoTokenizer

    logger.info("Merging adapter from %s with base %s", adapter_path, base_model_name)

    model = AutoPeftModelForCausalLM.from_pretrained(
        adapter_path,
        device_map="auto",
        torch_dtype=torch.bfloat16,
    )

    merged_model = model.merge_and_unload()
    tokenizer = AutoTokenizer.from_pretrained(adapter_path)

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    merged_model.save_pretrained(str(output_path))
    tokenizer.save_pretrained(str(output_path))

    if push_to_hub and hub_repo_id:
        merged_model.push_to_hub(hub_repo_id)
        tokenizer.push_to_hub(hub_repo_id)
        logger.info("Pushed to Hub: %s", hub_repo_id)

    logger.info("Merged model saved to %s", output_path)
    return str(output_path)
