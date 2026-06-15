"""Build LoRA adapters from skill patterns for targeted agent fine-tuning."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from agent_skills.decomposition import SkillCluster

logger = logging.getLogger(__name__)


@dataclass
class LoRABuildConfig:
    """Configuration for building a LoRA adapter from skill patterns."""

    base_model: str = "Qwen/Qwen2.5-14B"
    output_dir: str = "output/lora"
    LoRA_r: int = 16
    LoRA_alpha: int = 32
    LoRA_dropout: float = 0.05
    LoRA_target_modules: list[str] = field(default_factory=lambda: [
        "q_proj", "v_proj",
    ])
    learning_rate: float = 5e-5
    num_epochs: int = 3
    batch_size: int = 4
    max_seq_length: int = 4096
    gradient_accumulation_steps: int = 4
    warmup_ratio: float = 0.1
    # Skill-specific
    min_examples: int = 50
    max_examples: int = 10000
    quality_threshold: float = 0.7


@dataclass
class LoRAAdapter:
    """Metadata for a built LoRA adapter."""

    name: str
    skill_cluster: str
    base_model: str
    output_path: str
    num_examples: int
    LoRA_r: int
    LoRA_alpha: int
    target_modules: list[str]
    quality_score: float
    training_config: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "skill_cluster": self.skill_cluster,
            "base_model": self.base_model,
            "output_path": self.output_path,
            "num_examples": self.num_examples,
            "LoRA_r": self.LoRA_r,
            "LoRA_alpha": self.LoRA_alpha,
            "target_modules": self.target_modules,
            "quality_score": self.quality_score,
        }


# Skill-specific training prompt templates
TRAINING_TEMPLATES: dict[str, str] = {
    "debug": """You are a debugging expert. Analyze the error and provide a fix.

Error: {error}
Code:
```{{language}}
{{code}}
```

Provide the corrected code:""",

    "edit": """You are a code editor. Make the requested change precisely.

Task: {task}
File: {{file_path}}

Current code:
```{{language}}
{{current_code}}
```

Provide the edited code:""",

    "verify": """You are a verification expert. Run tests and check the results.

Test: {test_command}
Expected: {expected_output}

Analyze the test results and determine if the code is correct.""",

    "recover": """You are an error recovery specialist. The previous approach failed.

Error: {error}
Failed approach: {failed_approach}
Remaining attempts: {attempts_left}

Provide an alternative approach:""",

    "plan": """You are a planning agent. Break down the task into clear steps.

Task: {task}
Project context: {project_context}

Provide a step-by-step plan:""",

    "bash": """You are a command executor. Run the shell command and interpret results.

Command: {command}
Working directory: {working_dir}

Execute the command and interpret the output.""",
}


def generate_training_data(cluster: SkillCluster, template_type: str = "debug") -> list[dict[str, str]]:
    """Generate training examples for a skill cluster using templates.

    Args:
        cluster: The SkillCluster to generate data for.
        template_type: Which training template to use.

    Returns:
        List of training examples in chat format.
    """
    template = TRAINING_TEMPLATES.get(template_type, TRAINING_TEMPLATES["debug"])
    examples = []

    for skill in cluster.skills:
        for example in skill.examples:
            tool_seq = example.get("tool_sequence", [])
            errors = example.get("errors", [])
            success = example.get("success", True)

            # Build a realistic training prompt
            prompt = f"I need to {skill.description.lower()}. "
            if tool_seq:
                prompt += f"I'll use these tools: {', '.join(tool_seq[:5])}. "
            if errors:
                prompt += f"I encountered errors: {'; '.join(str(e) for e in errors[:3])}."

            # Build the expected response
            response_parts = []
            for i, tool in enumerate(tool_seq[:8]):
                response_parts.append(f"Step {i+1}: Use {tool} to {skill.description.lower()}")
            if success:
                response_parts.append("The task was completed successfully.")
            else:
                response_parts.append("I need to retry with a different approach.")

            examples.append({
                "messages": [
                    {"role": "system", "content": f"You are an expert at {skill.name}. {skill.description}"},
                    {"role": "user", "content": prompt},
                    {"role": "assistant", "content": "\n".join(response_parts)},
                ],
                "skill": skill.name,
                "cluster": cluster.name,
            })

    return examples


def build_lora(
    skill_cluster: SkillCluster,
    base_model: str = "Qwen/Qwen2.5-14B",
    output_dir: str = "output/lora",
    config: LoRABuildConfig | None = None,
) -> LoRAAdapter:
    """Build a LoRA adapter from a skill cluster.

    Takes a cluster of related skills and builds a focused LoRA adapter
    that can be loaded on top of a base model to enhance those specific skills.

    Args:
        skill_cluster: The SkillCluster to build a LoRA for.
        base_model: Base model to build the adapter for.
        output_dir: Output directory for the adapter.
        config: Build configuration.

    Returns:
        LoRAAdapter with metadata about the built adapter.
    """
    if config is None:
        config = LoRABuildConfig()

    adapter_name = f"lora_{skill_cluster.name}"
    adapter_dir = Path(output_dir) / adapter_name
    adapter_dir.mkdir(parents=True, exist_ok=True)

    # Generate training data from the cluster
    training_data = []
    for skill in skill_cluster.skills:
        template_type = skill.name if skill.name in TRAINING_TEMPLATES else "debug"
        data = generate_training_data(skill_cluster, template_type)
        training_data.extend(data)

    # Filter by quality
    quality_data = [
        ex for ex in training_data
        if len(ex["messages"]) >= 2 and len(ex["messages"][1].get("content", "")) > 20
    ]

    logger.info(f"Generated {len(quality_data)} training examples for {adapter_name}")

    # Build LoRA config
    lora_config = {
        "base_model_name_or_path": base_model,
        "peft_type": "LORA",
        "r": config.LoRA_r,
        "lora_alpha": config.LoRA_alpha,
        "lora_dropout": config.LoRA_dropout,
        "target_modules": config.LoRA_target_modules,
        "task_type": "CAUSAL_LM",
        "bias": "none",
    }

    # Save adapter config
    with open(adapter_dir / "adapter_config.json", "w") as f:
        json.dump(lora_config, f, indent=2)

    # Save skill mapping
    skill_mapping = {
        "cluster": cluster_name if (cluster_name := skill_cluster.name) else "unknown",
        "skills": [s.to_dict() for s in skill_cluster.skills],
        "training_examples": len(quality_data),
    }
    with open(adapter_dir / "skill_mapping.json", "w") as f:
        json.dump(skill_mapping, f, indent=2)

    # Generate training script
    training_script = _generate_training_script(
        adapter_name=adapter_name,
        base_model=base_model,
        adapter_dir=str(adapter_dir),
        training_data=quality_data,
        config=config,
    )
    with open(adapter_dir / "train.py", "w") as f:
        f.write(training_script)

    # Generate YAML config
    yaml_config = {
        "base_model": base_model,
        "adapter_name": adapter_name,
        "output_dir": str(adapter_dir),
        "LoRA_r": config.LoRA_r,
        "LoRA_alpha": config.LoRA_alpha,
        "learning_rate": config.learning_rate,
        "num_epochs": config.num_epochs,
        "batch_size": config.batch_size,
        "num_examples": len(quality_data),
        "skills": [s.name for s in skill_cluster.skills],
    }
    with open(adapter_dir / "training_config.yaml", "w") as f:
        yaml.dump(yaml_config, f, default_flow_style=False)

    adapter = LoRAAdapter(
        name=adapter_name,
        skill_cluster=skill_cluster.name,
        base_model=base_model,
        output_path=str(adapter_dir),
        num_examples=len(quality_data),
        LoRA_r=config.LoRA_r,
        LoRA_alpha=config.LoRA_alpha,
        target_modules=config.LoRA_target_modules,
        quality_score=skill_cluster.avg_success_rate,
        training_config=yaml_config,
    )

    logger.info(f"LoRA adapter '{adapter_name}' built at {adapter_dir}")
    logger.info(f"  Skills: {[s.name for s in skill_cluster.skills]}")
    logger.info(f"  Training examples: {len(quality_data)}")
    logger.info(f"  Quality score: {skill_cluster.avg_success_rate:.2f}")

    return adapter


def _generate_training_script(
    adapter_name: str,
    base_model: str,
    adapter_dir: str,
    training_data: list[dict[str, Any]],
    config: LoRABuildConfig,
) -> str:
    """Generate a training script for the LoRA adapter."""
    # Save training data JSONL
    data_path = f"{adapter_dir}/training_data.jsonl"

    return f"""#!/usr/bin/env python3
\"\"\"LoRA training script for {adapter_name} — Generated by AgentSkills\"\"\"

import json
from pathlib import Path
from datasets import Dataset
from transformers import AutoModelForCausalLM, AutoTokenizer, TrainingArguments
from peft import LoraConfig, get_peft_model, TaskType

# Load training data
data_path = Path("{data_path}")
examples = []
with open(data_path) as f:
    for line in f:
        if line.strip():
            examples.append(json.loads(line))

dataset = Dataset.from_list(examples)

# Load base model
model = AutoModelForCausalLM.from_pretrained(
    "{base_model}",
    torch_dtype="auto",
    device_map="auto",
)
tokenizer = AutoTokenizer.from_pretrained("{base_model}")

# LoRA configuration
lora_config = LoraConfig(
    task_type=TaskType.CAUSAL_LM,
    r={config.LoRA_r},
    lora_alpha={config.LoRA_alpha},
    lora_dropout={config.LoRA_dropout},
    target_modules={config.LoRA_target_modules},
)

model = get_peft_model(model, lora_config)
model.print_trainable_parameters()

# Training arguments
training_args = TrainingArguments(
    output_dir="{adapter_dir}",
    per_device_train_batch_size={config.batch_size},
    gradient_accumulation_steps={config.gradient_accumulation_steps},
    learning_rate={config.learning_rate},
    num_train_epochs={config.num_epochs},
    warmup_ratio={config.warmup_ratio},
    logging_steps=10,
    save_steps=500,
    bf16=True,
)

# Train
from trl import SFTTrainer

trainer = SFTTrainer(
    model=model,
    train_dataset=dataset,
    args=training_args,
)

trainer.train()
model.save_pretrained("{adapter_dir}")
tokenizer.save_pretrained("{adapter_dir}")
print(f"LoRA adapter saved to {adapter_dir}")
"""
