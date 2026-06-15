"""Train ReasonCritic-7B with three-stage training pipeline.

Stage 1: Contrastive learning on correct/incorrect pairs
Stage 2: LoRA fine-tuning on verification data
Stage 3: DPO alignment for preference optimization
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from reason_critic.data_prep import (
    ContrastivePair,
    VerificationExample,
    format_contrastive_prompt,
    generate_incorrect_versions,
)

logger = logging.getLogger(__name__)


@dataclass
class TrainingConfig:
    """Configuration for the three-stage training pipeline."""

    model_name: str = "Qwen/Qwen3-7B"
    output_dir: str = "./output"
    max_seq_length: int = 2048

    # Stage 1: Contrastive
    contrastive_epochs: int = 3
    contrastive_batch_size: int = 8
    contrastive_learning_rate: float = 2e-5

    # Stage 2: LoRA
    lora_r: int = 16
    lora_alpha: int = 32
    lora_dropout: float = 0.05
    lora_epochs: int = 2
    lora_batch_size: int = 4
    lora_learning_rate: float = 1e-4

    # Stage 3: DPO
    dpo_epochs: int = 1
    dpo_batch_size: int = 4
    dpo_learning_rate: float = 5e-5
    dpo_beta: float = 0.1

    # General
    gradient_accumulation_steps: int = 4
    warmup_ratio: float = 0.1
    weight_decay: float = 0.01
    logging_steps: int = 10
    save_steps: int = 500
    bf16: bool = True


VERIFICATION_PROMPT_TEMPLATE = """You are a code verification critic. Analyze the following code and determine if it is correct or contains bugs.

Language: {language}

```{language}
{code}
```

Respond in this exact format:
VERDICT: [PASS or FAIL]
CONFIDENCE: [0.0 to 1.0]
ISSUES: [comma-separated list of issues, or "none" if PASS]
SUGGESTIONS: [comma-separated list of suggestions, or "none" if PASS]
EXPLANATION: [brief explanation]
"""


def load_base_model(model_name: str = "Qwen/Qwen3-7B", max_seq_length: int = 2048):
    """Load the base model and tokenizer for training.

    Uses Unsloth for optimized loading when available.
    """
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    try:
        from unsloth import FastLanguageModel

        model, tokenizer = FastLanguageModel.from_pretrained(
            model_name=model_name,
            max_seq_length=max_seq_length,
            dtype=None,
            load_in_4bit=True,
        )
        logger.info(f"Loaded model with Unsloth: {model_name}")
    except ImportError:
        logger.info("Unsloth not available, using standard transformers loading")

        tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token

        model = AutoModelForCausalLM.from_pretrained(
            model_name,
            torch_dtype=torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16,
            device_map="auto",
            trust_remote_code=True,
        )
        logger.info(f"Loaded model: {model_name}")

    return model, tokenizer


def _tokenize_examples(examples, tokenizer, max_seq_length):
    """Tokenize a batch of examples for training."""
    prompts = examples["text"]
    tokenized = tokenizer(
        prompts,
        truncation=True,
        max_length=max_seq_length,
        padding="max_length",
        return_tensors=None,
    )
    tokenized["labels"] = tokenized["input_ids"].copy()
    return tokenized


def train_contrastive(
    pairs: list[ContrastivePair],
    output_dir: str,
    config: TrainingConfig | None = None,
    model=None,
    tokenizer=None,
) -> str:
    """Stage 1: Contrastive learning on correct/incorrect pairs."""
    from datasets import Dataset
    from transformers import DataCollatorForLanguageModeling, Trainer, TrainingArguments

    config = config or TrainingConfig()
    stage1_dir = str(Path(output_dir) / "stage1-contrastive")

    if model is None or tokenizer is None:
        model, tokenizer = load_base_model(config.model_name, config.max_seq_length)

    logger.info(f"Stage 1: Contrastive learning with {len(pairs)} pairs")

    formatted = []
    for pair in pairs:
        prompts = format_contrastive_prompt(pair)
        preferred_text = (
            f"{prompts['preferred']}\n\n"
            f"VERDICT: PASS\nCONFIDENCE: 0.95\n"
            f"EXPLANATION: {pair.explanation} — the code is correct."
        )
        dispreferred_text = (
            f"{prompts['dispreferred']}\n\n"
            f"VERDICT: FAIL\nCONFIDENCE: 0.95\n"
            f"EXPLANATION: {pair.explanation} — bug: {pair.bug_type}."
        )
        formatted.append({"text": preferred_text})
        formatted.append({"text": dispreferred_text})

    dataset = Dataset.from_list(formatted)

    def tokenize_fn(batch):
        return _tokenize_examples(batch, tokenizer, config.max_seq_length)

    tokenized_dataset = dataset.map(
        tokenize_fn,
        batched=True,
        remove_columns=dataset.column_names,
    )

    training_args = TrainingArguments(
        output_dir=stage1_dir,
        num_train_epochs=config.contrastive_epochs,
        per_device_train_batch_size=config.contrastive_batch_size,
        gradient_accumulation_steps=config.gradient_accumulation_steps,
        learning_rate=config.contrastive_learning_rate,
        warmup_ratio=config.warmup_ratio,
        weight_decay=config.weight_decay,
        logging_steps=config.logging_steps,
        save_steps=config.save_steps,
        bf16=config.bf16,
        report_to="none",
    )

    data_collator = DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False)

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized_dataset,
        data_collator=data_collator,
    )

    trainer.train()
    trainer.save_model(stage1_dir)
    tokenizer.save_pretrained(stage1_dir)

    logger.info(f"Stage 1 model saved to: {stage1_dir}")
    return stage1_dir


def train_lora(
    pairs: list[ContrastivePair],
    output_dir: str,
    config: TrainingConfig | None = None,
    model=None,
    tokenizer=None,
    stage1_dir: str | None = None,
) -> str:
    """Stage 2: LoRA fine-tuning on verification data."""
    from datasets import Dataset
    from peft import LoraConfig, TaskType, get_peft_model
    from transformers import DataCollatorForLanguageModeling, Trainer, TrainingArguments

    config = config or TrainingConfig()
    stage2_dir = str(Path(output_dir) / "stage2-lora")

    if model is None:
        load_from = stage1_dir or config.model_name
        model, tokenizer = load_base_model(load_from, config.max_seq_length)

    logger.info(f"Stage 2: LoRA fine-tuning with {len(pairs)} pairs")

    lora_config = LoraConfig(
        task_type=TaskType.CAUSAL_LM,
        r=config.lora_r,
        lora_alpha=config.lora_alpha,
        lora_dropout=config.lora_dropout,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        bias="none",
    )

    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    formatted = []
    for pair in pairs:
        prompts = format_contrastive_prompt(pair)
        text = (
            f"{prompts['preferred']}\n\n"
            f"VERDICT: PASS\nCONFIDENCE: 0.98\n"
            f"EXPLANATION: Correct implementation."
        )
        formatted.append({"text": text})

        text_fail = (
            f"{prompts['dispreferred']}\n\n"
            f"VERDICT: FAIL\nCONFIDENCE: 0.95\n"
            f"ISSUES: {pair.explanation}\n"
            f"SUGGESTIONS: Fix the {pair.bug_type} bug.\n"
            f"EXPLANATION: Contains {pair.bug_type} error."
        )
        formatted.append({"text": text_fail})

    dataset = Dataset.from_list(formatted)

    def tokenize_fn(batch):
        return _tokenize_examples(batch, tokenizer, config.max_seq_length)

    tokenized_dataset = dataset.map(
        tokenize_fn,
        batched=True,
        remove_columns=dataset.column_names,
    )

    training_args = TrainingArguments(
        output_dir=stage2_dir,
        num_train_epochs=config.lora_epochs,
        per_device_train_batch_size=config.lora_batch_size,
        gradient_accumulation_steps=config.gradient_accumulation_steps,
        learning_rate=config.lora_learning_rate,
        warmup_ratio=config.warmup_ratio,
        weight_decay=config.weight_decay,
        logging_steps=config.logging_steps,
        save_steps=config.save_steps,
        bf16=config.bf16,
        report_to="none",
    )

    data_collator = DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False)

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized_dataset,
        data_collator=data_collator,
    )

    trainer.train()
    model.save_pretrained(stage2_dir)
    tokenizer.save_pretrained(stage2_dir)

    logger.info(f"Stage 2 LoRA model saved to: {stage2_dir}")
    return stage2_dir


def train_dpo(
    preferred: list[str],
    dispreferred: list[str],
    output_dir: str,
    config: TrainingConfig | None = None,
    model=None,
    tokenizer=None,
    stage2_dir: str | None = None,
) -> str:
    """Stage 3: DPO alignment for preference optimization."""
    import torch
    from datasets import Dataset
    from transformers import AutoModelForCausalLM

    config = config or TrainingConfig()
    stage3_dir = str(Path(output_dir) / "stage3-dpo")

    if len(preferred) != len(dispreferred):
        raise ValueError("preferred and dispreferred must be same length")

    try:
        from trl import DPOConfig, DPOTrainer
    except ImportError:
        logger.warning("trl not installed. DPO training requires: pip install reason-critic[dpo]")
        raise

    if model is None or tokenizer is None:
        load_from = stage2_dir or config.model_name
        model, tokenizer = load_base_model(load_from, config.max_seq_length)

    logger.info(f"Stage 3: DPO alignment with {len(preferred)} preference pairs")

    dpo_dataset = Dataset.from_list(
        [
            {"prompt": "", "chosen": p, "rejected": d}
            for p, d in zip(preferred, dispreferred)
        ]
    )

    dpo_config = DPOConfig(
        output_dir=stage3_dir,
        num_train_epochs=config.dpo_epochs,
        per_device_train_batch_size=config.dpo_batch_size,
        gradient_accumulation_steps=config.gradient_accumulation_steps,
        learning_rate=config.dpo_learning_rate,
        warmup_ratio=config.warmup_ratio,
        bf16=config.bf16,
        beta=config.dpo_beta,
        logging_steps=config.logging_steps,
        save_steps=config.save_steps,
        report_to="none",
    )

    reference_model = AutoModelForCausalLM.from_pretrained(
        stage2_dir or config.model_name,
        torch_dtype=torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16,
        device_map="auto",
        trust_remote_code=True,
    )

    dpo_trainer = DPOTrainer(
        model=model,
        ref_model=reference_model,
        args=dpo_config,
        train_dataset=dpo_dataset,
        tokenizer=tokenizer,
    )

    dpo_trainer.train()
    dpo_trainer.save_model(stage3_dir)
    tokenizer.save_pretrained(stage3_dir)

    logger.info(f"Stage 3 DPO model saved to: {stage3_dir}")
    return stage3_dir


def run_three_stage_pipeline(
    examples: list[VerificationExample],
    pairs: list[ContrastivePair],
    output_dir: str = "./reason-critic-output",
    config: TrainingConfig | None = None,
) -> dict[str, str]:
    """Run the complete three-stage training pipeline."""
    config = config or TrainingConfig()

    logger.info("Starting three-stage training pipeline")
    logger.info(f"  Examples: {len(examples)}, Pairs: {len(pairs)}")

    # Stage 1: Contrastive
    model, tokenizer = load_base_model(config.model_name, config.max_seq_length)
    stage1_dir = train_contrastive(pairs, output_dir, config, model, tokenizer)

    # Stage 2: LoRA
    model, tokenizer = load_base_model(stage1_dir, config.max_seq_length)

    # Build additional pairs from examples for LoRA
    training_pairs = pairs[:]
    for ex in examples:
        if ex.label == "PASS":
            buggy_versions = generate_incorrect_versions(ex.code, num_versions=1)
            for bv in buggy_versions:
                training_pairs.append(
                    ContrastivePair(
                        correct_code=ex.code,
                        incorrect_code=bv["code"],
                        explanation=bv["description"],
                        bug_type=bv["bug_type"],
                        language=ex.language,
                    )
                )

    stage2_dir = train_lora(
        training_pairs, output_dir, config, model, tokenizer, stage1_dir
    )

    # Stage 3: DPO
    preferred = []
    dispreferred = []
    for pair in pairs:
        prompts = format_contrastive_prompt(pair)
        preferred.append(
            f"{prompts['preferred']}\n\n"
            f"VERDICT: PASS\nCONFIDENCE: 0.98\n"
            f"EXPLANATION: Correct code with no issues detected."
        )
        dispreferred.append(
            f"{prompts['dispreferred']}\n\n"
            f"VERDICT: PASS\nCONFIDENCE: 0.95\n"
            f"EXPLANATION: Code appears correct."
        )

    stage3_dir = train_dpo(
        preferred, dispreferred, output_dir, config,
        model=None, tokenizer=None, stage2_dir=stage2_dir,
    )

    results = {
        "stage1_contrastive": stage1_dir,
        "stage2_lora": stage2_dir,
        "stage3_dpo": stage3_dir,
    }

    logger.info(f"Three-stage pipeline complete: {results}")
    return results
