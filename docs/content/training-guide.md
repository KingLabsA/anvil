# FableForge Model Training Guide

> Train all three FableForge models using **free resources** — no GPU required.

**Models:**
- **FableForge-14B** — General coding agent (14B parameters)
- **ShellWhisperer-1.5B** — Shell/command specialist (1.5B parameters)
- **ReasonCritic-7B** — Verification and reasoning critic (7B parameters)

---

## Overview

### What Each Model Does

| Model | Role | Size | Base | Why It Exists |
|-------|------|------|------|---------------|
| FableForge-14B | Primary coding agent | 14B | Qwen2.5-14B | General-purpose plan→execute→verify. Handles the full loop. |
| ShellWhisperer-1.5B | Shell/command execution | 1.5B | Qwen2.5-1.5B | Fast, cheap shell command generation. Runs locally even on limited hardware. |
| ReasonCritic-7B | Verification & reasoning | 7B | Qwen2.5-7B | Evaluates code changes for correctness. Powers the Verify phase. |

### Training Pipeline (4 Stages)

All three models follow the same 4-stage training pipeline:

```
Stage 1: Behavior Cloning
                │
                ▼
Stage 2: Skill Fine-tuning
                │
                ▼
Stage 3: Error Recovery Training
                │
                ▼
Stage 4: DPO (Direct Preference Optimization)
```

| Stage | Data Source | Purpose | Duration (T4) |
|-------|-----------|---------|---------------|
| 1. Behavior Cloning | Fable-5 trajectory dataset | Learn basic coding patterns | 2-4 hours |
| 2. Skill Fine-tuning | Filtered skill-specific data | Master tool use & verification | 1-3 hours |
| 3. Error Recovery | Error→fix pairs | Learn to recover from failures | 1-2 hours |
| 4. DPO | Preference pairs | Improve output quality | 2-4 hours |

---

## Free Training Resources (2026)

All training can be done for free using these resources:

### Google Colab (T4 GPU — 16GB VRAM)

- **Best for:** ShellWhisperer-1.5B (full training) and FableForge-14B/ReasonCritic-7B (LoRA only)
- **VRAM:** 16GB (T4) or 24GB (T4 after Colab Pro upgrade)
- **Runtime:** Free tier gives ~12 hours/day with GPU
- **Limitations:** Session resets after ~12 hours (checkpoint and resume)

### Unsloth

- **Purpose:** Fast, memory-efficient fine-tuning with 2-5x speedup over standard HF trainers
- **Best for:** All three models on free-tier hardware
- **Key feature:** Supports 4-bit QLoRA training, reducing VRAM requirements by ~60%

### Axolotl

- **Purpose:** Production-grade training configuration and multi-stage training
- **Best for:** Complex training pipelines with multiple stages
- **Key feature:** YAML-based config, native LoRA/QLoRA support

### Hugging Face Jobs

- **Purpose:** Free compute credits for open-source model training
- **Best for:** One-time training runs or benchmarking
- **Key feature:** Apply forcompute grants at huggingface.co/grants

### ms-swift (ModelScope SWIFT)

- **Purpose:** Model-agnostic training framework with strong LoRA support
- **Best for:** Training on ModelScope ecosystem models
- **Key feature:** Built-in evaluation and model merging

### SLMGEN

- **Purpose:** Small Language Model generation pipeline
- **Best for:** Generating the ShellWhisperer-1.5B from scratch
- **Key feature:** Automated data curation and training for small models

---

## Step-by-Step: Train FableForge-14B on Colab

This section walks you through training the 14B model using LoRA on a free Colab T4 GPU via Unsloth.

### Prerequisites

```python
# Step 0: Install Unsloth and dependencies (run in Colab)
!pip install unsloth
!pip install trl transformers datasets accelerate peft bitsandbytes
!pip install huggingface_hub
```

### Stage 1: Behavior Cloning

The first stage teaches the model basic coding patterns from the Fable-5 dataset.

#### 1.1: Download and Prepare Data

```python
from datasets import load_dataset
from trajectory_distiller import TrajectoryConverter

# Download Fable-5 dataset
raw_dataset = load_dataset("fableforge/fable-5", split="train")

# Convert trajectories to training format
converter = TrajectoryConverter(
    format="chatml",  # ChatML format for Qwen2.5
    include_thinking=True,  # Include reasoning chains
    include_tool_calls=True,  # Include tool invocations
    include_tool_results=True,  # Include tool outputs
)

train_data = converter.convert(raw_dataset)
train_data = train_data.train_test_split(test_size=0.05, seed=42)

print(f"Training samples: {len(train_data['train'])}")
print(f"Validation samples: {len(train_data['test'])}")
```

#### 1.2: Configure the Model

```python
from unsloth import FastLanguageModel

model, tokenizer = FastLanguageModel.from_pretrained(
    model_name="Qwen/Qwen2.5-14B",
    max_seq_length=4096,
    load_in_4bit=True,  # QLoRA: 4-bit quantization for T4
    dtype=None,  # Auto-detect
)

# Add LoRA adapters
model = FastLanguageModel.get_peft_model(
    model,
    r=64,  # LoRA rank — start with 64, increase to 128 for better quality
    lora_alpha=16,
    lora_dropout=0,
    target_modules=[
        "q_proj", "k_proj", "v_proj", "o_proj",
        "gate_proj", "up_proj", "down_proj",
    ],
    bias="none",
    use_gradient_checkpointing="unsloth",  # Unsloth's optimized gradient checkpointing
    random_state=42,
)
```

#### 1.3: Train (Behavior Cloning)

```python
from trl import SFTTrainer
from transformers import TrainingArguments

training_args = TrainingArguments(
    output_dir="./fableforge-14b-stage1",
    num_train_epochs=3,
    per_device_train_batch_size=2,
    gradient_accumulation_steps=8,  # Effective batch size = 2 * 8 = 16
    learning_rate=2e-5,
    lr_scheduler_type="cosine",
    warmup_ratio=0.1,
    logging_steps=10,
    save_steps=100,
    save_total_limit=3,
    bf16=False,  # T4 doesn't support bf16
    fp16=True,   # Use fp16 on T4
    optim="adamw_8bit",
    max_grad_norm=1.0,
    eval_strategy="steps",
    eval_steps=100,
)

trainer = SFTTrainer(
    model=model,
    tokenizer=tokenizer,
    train_dataset=train_data["train"],
    eval_dataset=train_data["test"],
    args=training_args,
    dataset_text_field="text",
    max_seq_length=4096,
)

trainer.train()
```

#### 1.4: Save Checkpoint

```python
# Save LoRA adapter
model.save_pretrained("./fableforge-14b-stage1-adapter")
tokenizer.save_pretrained("./fableforge-14b-stage1-adapter")

# Push to Hugging Face
model.push_to_hub("fableforge/fableforge-14b-stage1-adapter")
tokenizer.push_to_hub("fableforge/fableforge-14b-stage1-adapter")
```

### Stage 2: Skill Fine-tuning

Fine-tune on tool-use and verification-specific data.

#### 2.1: Prepare Skill Data

```python
from trajectory_distiller import SkillFilter

# Filter for tool-use and verification trajectories
skill_filter = SkillFilter(
    categories=["tool_use", "verification", "code_generation", "debugging"],
    min_quality_score=0.8,  # Only high-quality trajectories
)

skill_data = skill_filter.filter(train_data["train"])

# Create synthetic verification data
synthetic_verify = create_verification_dataset(
    base_data=skill_data,
    num_samples=5000,
    include_positive=True,   # Correct code changes
    include_negative=True,   # Incorrect changes with corrections
)

combined_data = concatenate_datasets([skill_data, synthetic_verify])
```

#### 2.2: Train (Skill Fine-tuning)

```python
# Load Stage 1 model
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name="./fableforge-14b-stage1-adapter",
    max_seq_length=4096,
    load_in_4bit=True,
)

# Continue training with skill-specific data
training_args = TrainingArguments(
    output_dir="./fableforge-14b-stage2",
    num_train_epochs=2,
    per_device_train_batch_size=2,
    gradient_accumulation_steps=8,
    learning_rate=1e-5,  # Lower LR for fine-tuning
    lr_scheduler_type="cosine",
    warmup_ratio=0.05,
    logging_steps=10,
    save_steps=100,
    fp16=True,
    optim="adamw_8bit",
)

trainer = SFTTrainer(
    model=model,
    tokenizer=tokenizer,
    train_dataset=combined_data,
    args=training_args,
    max_seq_length=4096,
)

trainer.train()
model.save_pretrained("./fableforge-14b-stage2-adapter")
```

### Stage 3: Error Recovery Training

Train on error→fix pairs so the model learns to recover from failures.

#### 3.1: Generate Error Recovery Data

```python
from trajectory_distiller import ErrorRecoveryGenerator

generator = ErrorRecoveryGenerator(
    model_name="Qwen/Qwen2.5-14B",  # Use a strong model for generation
    error_types=[
        "syntax_error",
        "runtime_error",
        "test_failure",
        "type_error",
        "import_error",
        "logic_error",
    ],
)

recovery_data = generator.generate(
    base_code=train_data["train"],
    num_samples=3000,
    # For each sample:
    # 1. Introduce a realistic error into correct code
    # 2. Generate the fix
    # 3. Create a training pair: (error_context → fixed_code)
)
```

#### 3.2: Train (Error Recovery)

```python
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name="./fableforge-14b-stage2-adapter",
    max_seq_length=4096,
    load_in_4bit=True,
)

training_args = TrainingArguments(
    output_dir="./fableforge-14b-stage3",
    num_train_epochs=2,
    per_device_train_batch_size=2,
    gradient_accumulation_steps=8,
    learning_rate=5e-6,
    lr_scheduler_type="cosine",
    warmup_ratio=0.05,
    fp16=True,
    optim="adamw_8bit",
)

trainer = SFTTrainer(
    model=model,
    tokenizer=tokenizer,
    train_dataset=recovery_data,
    args=training_args,
    max_seq_length=4096,
)

trainer.train()
model.save_pretrained("./fableforge-14b-stage3-adapter")
```

### Stage 4: DPO (Direct Preference Optimization)

The final stage improves output quality using preference pairs (chosen vs. rejected).

#### 4.1: Generate Preference Pairs

```python
from trajectory_distiller import PreferencePairGenerator

pair_generator = PreferencePairGenerator()
pairs = pair_generator.generate(
    # For each task, generate 2-3 variants and rank them
    tasks=train_data["train"].select(range(1000)),
    num_variants=3,  # Generate 3 responses per task
    ranking_criteria=[
        "correctness",     # Does it work?
        "efficiency",     # Is it efficient?
        "readability",    # Is it clean code?
        "safety",         # No security issues?
    ],
)
```

#### 4.2: Train (DPO)

```python
from trl import DPOTrainer, DPOConfig

dpo_config = DPOConfig(
    output_dir="./fableforge-14b-stage4-dpo",
    num_train_epochs=1,
    per_device_train_batch_size=1,
    gradient_accumulation_steps=16,
    learning_rate=5e-7,  # Very low LR for DPO
    lr_scheduler_type="cosine",
    fp16=True,
    optim="adamw_8bit",
    beta=0.1,  # DPO beta parameter
    max_length=4096,
    max_prompt_length=2048,
)

dpo_trainer = DPOTrainer(
    model=model,
    ref_model=None,  # Will use the same model as reference
    args=dpo_config,
    train_dataset=pairs,
    processing_class=tokenizer,
)

dpo_trainer.train()
```

#### 4.3: Merge and Save Final Model

```python
# Merge LoRA adapter into base model
model.save_pretrained_merged(
    "./fableforge-14b-final",
    tokenizer=tokenizer,
    save_method="merged_16bit",  # Full precision merge for best quality
)

# Push to Hugging Face
model.push_to_hub_merged(
    "fableforge/fableforge-14b",
    tokenizer=tokenizer,
    save_method="merged_16bit",
)
```

---

## Step-by-Step: Train ShellWhisperer-1.5B on Colab

The 1.5B model is small enough for **full fine-tuning** (not just LoRA) on a free T4.

### Stage 1: Behavior Cloning (Full Fine-tuning)

```python
from unsloth import FastLanguageModel

# ShellWhisperer is small — we can fine-tune ALL parameters
model, tokenizer = FastLanguageModel.from_pretrained(
    model_name="Qwen/Qwen2.5-1.5B",
    max_seq_length=2048,  # Shell commands are shorter
    load_in_4bit=False,  # Full precision for full fine-tuning
    dtype=torch.float16,
)

# No LoRA needed — fine-tune all parameters
# Just make sure gradient checkpointing is on for memory efficiency
model.gradient_checkpointing_enable()

# Prepare shell-specific data
shell_dataset = load_dataset("fableforge/fable-5", split="train")
shell_dataset = shell_dataset.filter(lambda x: x["category"] == "shell_command")

training_args = TrainingArguments(
    output_dir="./shellwhisperer-1.5b-stage1",
    num_train_epochs=5,  # More epochs for smaller model
    per_device_train_batch_size=4,  # Larger batch — smaller model
    gradient_accumulation_steps=4,
    learning_rate=5e-5,  # Higher LR for full fine-tuning
    lr_scheduler_type="cosine",
    warmup_ratio=0.1,
    fp16=True,
    logging_steps=5,
    save_steps=50,
)

trainer = SFTTrainer(
    model=model,
    tokenizer=tokenizer,
    train_dataset=shell_dataset,
    args=training_args,
    max_seq_length=2048,
)

trainer.train()
model.save_pretrained("./shellwhisperer-1.5b-stage1")
```

### Stages 2-4: Follow Same Pattern

The remaining stages follow the same pattern as FableForge-14B, but with these adjustments:

- **Lower learning rate:** 2e-5 for stages 2-3, 1e-6 for stage 4
- **Larger batch size:** 4-8 (model fits in memory)
- **Shorter sequences:** 2048 max length
- **More epochs:** 3-5 per stage (smaller model needs more passes)

### ShellWhisperer-Specific Data

ShellWhisperer needs specialized data:

```python
from trajectory_distiller import ShellDataAugmentor

augmentor = ShellDataAugmentor(
    command_types=[
        "file_operations",   # ls, cp, mv, rm, find
        "text_processing",   # grep, sed, awk, sort, uniq
        "process_mgmt",      # ps, top, kill, htop
        "network",           # curl, wget, ssh, scp
        "package_mgmt",      # pip, npm, apt, brew
        "git",               # git add, commit, push, diff
        "docker",            # docker build, run, compose
        "python",             # python, pip, venv
    ],
    os_targets=["linux", "macos"],
    shell_types=["bash", "zsh"],
)

shell_data = augmentor.generate(num_samples=10000)
```

---

## Step-by-Step: Train ReasonCritic-7B on Colab

ReasonCritic is trained on verification data — pairs of code changes and their quality assessments.

### Stage 1: Behavior Cloning (LoRA)

```python
from unsloth import FastLanguageModel

model, tokenizer = FastLanguageModel.from_pretrained(
    model_name="Qwen/Qwen2.5-7B",
    max_seq_length=4096,
    load_in_4bit=True,
)

model = FastLanguageModel.get_peft_model(
    model,
    r=32,  # Lower rank for 7B model on T4
    lora_alpha=16,
    target_modules=[
        "q_proj", "k_proj", "v_proj", "o_proj",
        "gate_proj", "up_proj", "down_proj",
    ],
    use_gradient_checkpointing="unsloth",
)

# Prepare verification training data
verify_dataset = create_verification_training_data(
    # Positive examples: correct code changes
    positive=train_data["train"],
    # Negative examples: buggy code changes with explanations
    negative_count=5000,
    # Explanation style: step-by-step reasoning
    explanation_style="chain_of_thought",
)
```

### ReasonCritic-Specific Training

ReasonCritic needs special training for the verification task:

```python
# Verification data format:
# {
#   "messages": [
#     {"role": "system", "content": "You are a code verification expert..."},
#     {"role": "user", "content": "Review this code change:\n{diff}"},
#     {"role": "assistant", "content": "Let me analyze this step by step:\n1. ...\n2. ...\nVerdict: PASS with suggestions"},
#   ]
# }

training_args = TrainingArguments(
    output_dir="./reasoncritic-7b-stage1",
    num_train_epochs=3,
    per_device_train_batch_size=2,
    gradient_accumulation_steps=8,
    learning_rate=2e-5,
    lr_scheduler_type="cosine",
    warmup_ratio=0.1,
    fp16=True,
    optim="adamw_8bit",
)
```

---

## Data Preparation with trajectory-distiller

The `trajectory-distiller` project converts raw execution traces into training data.

### Converting Traces

```python
from trajectory_distiller import TraceConverter

converter = TraceConverter(
    input_format="anvil_trace",  # Anvil session format
    output_format="chatml",       # ChatML conversation format
    include_thinking=True,
    include_tool_calls=True,
    include_verification=True,
)

# Convert a single trace
training_sample = converter.convert(trace_file="traces/session_001.json")

# Batch convert
converter.batch_convert(
    input_dir="traces/",
    output_dir="training_data/",
    num_workers=4,
)
```

### Quality Filtering

```python
from trajectory_distiller import QualityFilter

filter = QualityFilter(
    min_score=0.7,           # Minimum trajectory quality score
    max_repetitions=3,       # Maximum allowed repetition in tool calls
    require_verification=True, # Only include trajectories with verification
    exclude_patterns=[       # Exclude problematic patterns
        "infinite_loop",
        "repeated_failure",
        "no_tool_use",
    ],
)

filtered = filter.apply(training_data)
print(f"Kept {len(filtered)} of {len(training_data)} samples ({len(filtered)/len(training_data)*100:.1f}%)")
```

### Generating the 4-Stage Pipeline Data

```python
from trajectory_distiller import PipelineGenerator

generator = PipelineGenerator(
    base_data="training_data/filtered/",
    output_dir="training_data/pipeline/",
)

# Stage 1: Behavior cloning data
stage1_data = generator.stage1(
    format="chatml",
    include_all_categories=True,
)

# Stage 2: Skill-specific data
stage2_data = generator.stage2(
    categories=["tool_use", "verification", "debugging"],
    synthetic_verification=True,
    num_synthetic=5000,
)

# Stage 3: Error recovery data
stage3_data = generator.stage3(
    error_types=["syntax", "runtime", "test_failure", "logic"],
    num_samples=3000,
)

# Stage 4: DPO preference pairs
stage4_data = generator.stage4(
    num_variants=3,
    ranking_criteria=["correctness", "efficiency", "readability"],
    num_pairs=2000,
)
```

---

## Evaluation and Benchmarking

Use `bench-agent` to evaluate trained models against the FableForge benchmark suite.

### Running Benchmarks

```python
from bench_agent import BenchmarkRunner

runner = BenchmarkRunner(
    model_name="fableforge/fableforge-14b",
    backend="ollama",  # or "openai", "anthropic", "vllm"
    benchmark_suite="full",  # or "quick" for fast iteration
)

results = runner.run()
print(f"Overall score: {results.overall_score:.2f}/100")
print(f"Plan score:    {results.plan_score:.2f}/100")
print(f"Execute score: {results.execute_score:.2f}/100")
print(f"Verify score:  {results.verify_score:.2f}/100")
print(f"Recover score: {results.recover_score:.2f}/100")
```

### Comparison Benchmarks

```python
# Compare models
models = [
    ("fableforge/fableforge-14b", "ollama"),
    ("fableforge/fableforge-14b-stage3", "ollama"),
    ("gpt-4o", "openai"),
    ("claude-sonnet-4-20250514", "anthropic"),
]

for model_name, backend in models:
    runner = BenchmarkRunner(model_name=model_name, backend=backend)
    results = runner.run()
    print(f"{model_name}: {results.overall_score:.2f}")
```

### Benchmark Categories

| Category | What it Tests | Weight |
|----------|--------------|--------|
| `plan` | Task decomposition quality | 25% |
| `execute` | Code generation accuracy | 30% |
| `verify` | Self-correction ability | 25% |
| `recover` | Error recovery success rate | 20% |

---

## Export to Ollama / GGUF / vLLM

After training, export models for inference:

### Export to Ollama

```python
from unsloth import FastLanguageModel

# Load final model
model, tokenizer = FastLanguageModel.from_pretrained("./fableforge-14b-final")

# Export as GGUF for Ollama
model.save_pretrained_gguf(
    "fableforge-14b",
    tokenizer=tokenizer,
    quantization_method="q4_k_m",  # Good quality/speed balance
)

# Create Modelfile
# ```
# FROM ./fableforge-14b-Q4_K_M.gguf
# PARAMETER temperature 0.7
# PARAMETER num_ctx 8192
# SYSTEM You are FableForge, an expert coding agent...
# ```

# Build and test
# $ ollama create fableforge-14b -f Modelfile
# $ ollama run fableforge-14b "Explain this code"
```

### Export to vLLM

```python
# Save in HuggingFace format (already done)
model.save_pretrained("./fableforge-14b-final")
tokenizer.save_pretrained("./fableforge-14b-final")

# Push to Hugging Face
model.push_to_hub("fableforge/fableforge-14b")
tokenizer.push_to_hub("fableforge/fableforge-14b")

# Run with vLLM
# $ python -m vllm.entrypoints.openai.api_server \
#     --model fableforge/fableforge-14b \
#     --host 0.0.0.0 --port 8000
```

### Quantization Options

| Method | Size | Quality | Speed | Best For |
|--------|------|---------|-------|----------|
| Q4_K_M | ~5GB | Good | Fast | Production inference |
| Q5_K_M | ~6GB | Better | Fast | Balanced use |
| Q8_0 | ~9GB | Very Good | Medium | High-quality inference |
| FP16 | ~14GB | Best | Slow | Training/fine-tuning |

---

## Tips for Free-Tier Training

### VRAM Management

- **Gradient checkpointing:** Always enabled via Unsloth — reduces VRAM by ~60%
- **4-bit QLoRA:** Reduces model from ~28GB (14B fp16) to ~8GB on GPU
- **Gradient accumulation:** Effective batch size = `batch_size * gradient_accumulation_steps`

```python
# T4 VRAM allocation strategy (16GB):
# - Model (4-bit): ~8GB
# - Activations: ~4GB (with gradient checkpointing)
# - Optimizer states: ~2GB (8-bit AdamW)
# - Buffers/cached: ~2GB
# Total: ~16GB (fits on T4!)
```

### Mixed Precision

- **T4:** Use `fp16=True` (T4 has Tensor Cores for fp16)
- **Never use `bf16=True` on T4** — it will silently fall back to fp32 and OOM
- **A100/H100:** Use `bf16=True` for better numerical stability

### Checkpointing and Resuming

Colab sessions can disconnect. Always save checkpoints:

```python
from transformers import TrainingArguments

training_args = TrainingArguments(
    output_dir="./checkpoints",
    save_strategy="steps",
    save_steps=100,      # Save every 100 steps
    save_total_limit=3,   # Keep only 3 checkpoints
    # ...
)

# To resume:
# trainer.train(resume_from_checkpoint="./checkpoints/checkpoint-500")
```

### Multi-Session Training on Colab

For models that don't finish in one session:

```python
# Session 1: Train until disconnect, save checkpoint
# Session 2: Load checkpoint and continue

model, tokenizer = FastLanguageModel.from_pretrained(
    "./checkpoints/checkpoint-500",  # Resume from checkpoint
    max_seq_length=4096,
    load_in_4bit=True,
)

# Continue training
trainer = SFTTrainer(
    model=model,
    tokenizer=tokenizer,
    args=training_args,
    train_dataset=train_data,
)
trainer.train(resume_from_checkpoint=True)
```

### Monitoring with wandb

Track training metrics with Weights & Biases:

```python
# Add to TrainingArguments
training_args = TrainingArguments(
    # ...
    report_to="wandb",
    run_name="fableforge-14b-stage1",
)

# Login to wandb
import wandb
wandb.login(key="your-wandb-key")

# Or set environment variable
# export WANDB_API_KEY=your-key
```

### Reducing Training Time

| Technique | Time Reduction | Quality Impact |
|-----------|---------------|----------------|
| QLoRA (4-bit) | 60% less VRAM | Minimal |
| Gradient checkpointing | 50% less VRAM | None |
| Unsloth optimizations | 2-5x faster | None |
| Smaller LoRA rank (r=32) | 30% faster | Slight |
| Shorter sequences (2048) | 40% faster | Moderate for long tasks |
| Fewer epochs (2 vs 5) | 60% faster | Moderate |

### Cost Estimation (Free Tier)

| Model | Stage | Colab T4 Hours | Cost |
|-------|-------|---------------|------|
| ShellWhisperer-1.5B | Full training | 4-6 | Free |
| ReasonCritic-7B | LoRA training | 6-10 | Free |
| FableForge-14B | LoRA training | 8-12 | Free |
| FableForge-14B | DPO stage | 4-6 | Free |

**Total:** ~22-34 free Colab hours for all three models.
