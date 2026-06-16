# TraceCompiler

[![FableForge Ecosystem](https://img.shields.io/badge/FableForge-Ecosystem-purple?style=flat-square)](https://github.com/KingLabsA?q=fableforge) [![PyPI](https://img.shields.io/pypi/v/fableforge-trace-compiler?style=flat-square)](https://pypi.org/project/fableforge-trace-compiler/) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](LICENSE)


[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE) [![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/) [![Tests](https://img.shields.io/badge/tests-0-yellow.svg)](tests/)


Compile agent traces into distilled LoRA weights for specific coding behaviors.

## Overview

TraceCompiler parses JSONL traces from multiple agent formats (Glint, armand0e, v-Fable), extracts named skill examples (debug, edit, verify, recover, plan), and distills them into LoRA adapter weights that can be loaded onto a base language model.

## Architecture

```
JSONL Traces → Parser → SkillExtractor → Distiller → LoRA Adapter
                                                       ↓
                                                  Evaluator → Report
```

## Supported Trace Formats

### Glint Format
```json
{
  "uid": "glint-001",
  "source_file": "main.py",
  "session": "session-abc",
  "model": "claude-3-opus",
  "context": "Fix the bug on line 10",
  "cot": "Let me analyze this error...",
  "output_type": "text",
  "output": "The issue is a missing import.",
  "completion": "",
  "origin": "glint"
}
```

### armand0e Format
```json
{
  "type": "ai",
  "message": {
    "content": [
      {"type": "thinking", "thinking": "Analyzing the code..."},
      {"type": "text", "text": "Here's the fix."},
      {"type": "tool_use", "id": "call_1", "name": "bash", "input": {"command": "pytest"}}
    ],
    "model": "claude-3-opus"
  },
  "parentUuid": "msg-parent",
  "uuid": "msg-child"
}
```

### v-Fable Format

Same as Glint but with `"origin": "v-Fable"`.

## Installation

```bash
pip install -e .
```

For development:

```bash
pip install -e ".[dev]"
```

## Usage

### Parse Traces

```bash
# Parse a trace file and display summary
trace-compiler parse traces.jsonl

# Parse and save to file
trace-compiler parse traces.jsonl -o parsed.json

# Verbose output
trace-compiler parse traces.jsonl -v

# Specify format explicitly
trace-compiler parse traces.jsonl --format glint
```

### Extract Skills

```bash
# Extract debug skill examples
trace-compiler extract --skill debug traces.jsonl

# Extract with custom confidence threshold
trace-compiler extract --skill debug --min-confidence 0.7 traces.jsonl

# Extract and save examples
trace-compiler extract --skill debug -o examples.json traces.jsonl
```

Available skills:
- `debug` — Error recovery traces
- `edit` — Code edit tool calls
- `verify` — Verification reasoning
- `recover` — Error → recovery patterns
- `plan` — Planning reasoning

### Compile into LoRA Adapter

```bash
# Compile using default settings (Qwen2.5-Coder-1.5B)
trace-compiler compile --skill debug traces.jsonl

# Use a specific model alias
trace-compiler compile --skill debug --model qwen3-7b traces.jsonl

# Use a training config file
trace-compiler compile --skill debug --config configs/debug.yaml traces.jsonl

# Specify output directory
trace-compiler compile --skill debug -o ./my-adapters traces.jsonl
```

Model aliases:
- `qwen3-1.5b` → `Qwen/Qwen2.5-Coder-1.5B`
- `qwen3-7b` → `Qwen/Qwen2.5-Coder-7B`
- `codellama-7b` → `codellama/CodeLlama-7b-hf`
- `mistral-7b` → `mistralai/Mistral-7B-v0.1`

Or pass a full HuggingFace model ID.

### Evaluate Adapted Model

```bash
# Evaluate a debug skill adapter
trace-compiler evaluate --skill debug --adapter ./output/debug traces.jsonl

# Specify model and save report
trace-compiler evaluate --skill debug --model qwen3-1.5b \
  --adapter ./output/debug -o report.json traces.jsonl
```

### Inspect Trace Files

```bash
# Quick format detection
trace-compiler inspect traces.jsonl

# Verbose inspection with content analysis
trace-compiler inspect traces.jsonl -v
```

## Training Configuration

Each skill type has a default config in `configs/`. You can customize:

```yaml
# configs/debug.yaml
skill_type: debug

training:
  model_name: Qwen/Qwen2.5-Coder-1.5B
  lora_r: 16
  lora_alpha: 32
  lora_dropout: 0.05
  learning_rate: 2.0e-4
  num_epochs: 3
  batch_size: 4
  gradient_accumulation_steps: 4
  max_seq_length: 4096
  warmup_steps: 10
  weight_decay: 0.01
```

### LoRA Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `lora_r` | 16 | LoRA rank (higher = more capacity, slower) |
| `lora_alpha` | 32 | LoRA scaling factor (typically 2x rank) |
| `lora_dropout` | 0.05 | Dropout probability for LoRA layers |
| `max_seq_length` | 4096 | Maximum sequence length for training |

### Target Modules

Default target modules: `q_proj`, `k_proj`, `v_proj`, `o_proj`, `gate_proj`, `up_proj`, `down_proj`

## Skill Extraction Details

### DEBUG Skill
Detects error recovery patterns — traces containing error messages, exceptions, tracebacks followed by investigation and fixes.

### EDIT Skill
Identifies code modification traces — tool calls to edit/replace/write tools, or content containing edit instructions.

### VERIFY Skill
Extracts verification reasoning — traces where the model runs tests, checks outputs, or explicitly verifies changes.

### RECOVER Skill
Finds error-to-recovery sequences — an error message followed by a fix attempt within a short window.

### PLAN Skill
Detects planning patterns — traces where the model explicitly outlines a strategy before implementation.

## Programmatic Usage

```python
from trace_compiler import TraceParser, SkillExtractor, SkillType, Distiller, TrainingConfig

# Parse traces
parser = TraceParser()
records = parser.parse_file("traces.jsonl")

# Extract skills
extractor = SkillExtractor(min_confidence=0.6)
debug_examples = extractor.extract(records, skill_type=SkillType.DEBUG)

# Configure and train
config = TrainingConfig.from_yaml("configs/debug.yaml")
distiller = Distiller(config=config)
adapter_path = distiller.train(debug_examples, SkillType.DEBUG)
print(f"Adapter saved to: {adapter_path}")
```

## Evaluation

The evaluator runs benchmark prompts against the base model and the adapted model, scoring responses against skill-specific criteria:

- **DEBUG**: Identifies errors, suggests fixes, explains root causes
- **EDIT**: Makes minimal, correct edits preserving existing behavior
- **VERIFY**: Suggests systematic verification with edge cases
- **RECOVER**: Diagnoses failures and provides recovery steps
- **PLAN**: Produces structured, prioritized plans

Scores are computed using keyword matching against criteria. A positive improvement delta indicates the adapter improved over the base model.

## Requirements

- Python 3.10+
- PyTorch 2.1+
- CUDA-capable GPU recommended for training
- 8GB+ VRAM for Qwen2.5-Coder-1.5B with LoRA
- 16GB+ VRAM for Qwen2.5-Coder-7B with LoRA

## License

MIT

## Ecosystem

Part of the [FableForge](../) ecosystem — 21 open-source projects built from 210K real agent traces:

| Project | Description |
| --- | --- |
| **[Anvil](../anvil)** | Self-verified coding agent |
| **[VerifyLoop](../verifyloop)** | Plan→Execute→Verify→Recover framework |
| **[ErrorRecovery](../error-recovery)** | Self-healing middleware (3,725 error patterns) |
| **[FableForge-14B](../fableforge-14b)** | The fine-tuned 14B model (4-stage training) |
| **[ShellWhisperer](../shell-whisperer)** | 1.5B edge agent (phone/RPi, 50ms) |
| **[ReasonCritic](../reason-critic)** | Verification model (130 benchmark tasks) |
| **[TraceCompiler](../trace-compiler)** | Compile traces → LoRA skills |
| **[AgentRuntime](../agent-runtime)** | Persistent agent daemon (systemd for AI) |
| **[AgentSwarm](../agent-swarm)** | Multi-agent from real trace transitions |
| **[AgentTelemetry](../agent-telemetry)** | Datadog for agents (token tracking, costs) |
| **[BenchAgent](../bench-agent)** | HumanEval for tool-use (107 tasks) |
| **[AgentDev](../agent-dev)** | VSCode extension with verification |
| **[TraceViz](../trace-viz)** | Trace replay visualizer (Next.js) |
| **[AgentSkills](../agent-skills)** | npm for agent behaviors |
| **[AgentCurriculum](../agent-curriculum)** | 5-stage progressive training |
| **[AgentFuzzer](../agent-fuzzer)** | Adversarial testing for agents |
| **[AgentConstitution](../agent-constitution)** | Safety guardrails from traces |
| **[CostOptimizer](../cost-optimizer)** | Token cost reduction (50-80%) |
| **[AgentProfiler](../agent-profiler)** | Behavioral fingerprinting |
| **[TrajectoryDistiller](../trajectory-distiller)** | Trace→training data pipeline |
| **[Fable5-Dataset](../fable5-dataset)** | HuggingFace dataset release |

---

## 🌐 FableForge Ecosystem

This project is part of **FableForge** — 21 open-source tools for building reliable AI agents.

| Component | Purpose |
|-----------|---------|
| [Anvil](https://github.com/KingLabsA/anvil) | 🔨 Flagship self-verifying agent |
| [VerifyLoop](https://github.com/KingLabsA/verifyloop) | Plan → Execute → Verify loop |
| [Error Recovery](https://github.com/KingLabsA/error-recovery) | Failure classification & recovery |
| [ReasonCritic](https://github.com/KingLabsA/reason-critic) | Trained verification model |
| [Agent Swarm](https://github.com/KingLabsA/agent-swarm) | Multi-agent orchestration |
| [Agent Telemetry](https://github.com/KingLabsA/agent-telemetry) | Observability & tracing |
| [Agent Profiler](https://github.com/KingLabsA/agent-profiler) | Performance profiling |
| [Agent Constitution](https://github.com/KingLabsA/agent-constitution) | Safety guardrails |
| [Agent Curriculum](https://github.com/KingLabsA/agent-curriculum) | Learning progression |
| [Agent Fuzzer](https://github.com/KingLabsA/agent-fuzzer) | Adversarial testing |
| [Agent Runtime](https://github.com/KingLabsA/agent-runtime) | Execution sandbox |
| [Agent Skills](https://github.com/KingLabsA/agent-skills) | Tool definitions |
| [Cost Optimizer](https://github.com/KingLabsA/cost-optimizer) | Token cost management |
| [Trajectory Distiller](https://github.com/KingLabsA/trajectory-distiller) | Pattern extraction |
| [Trace Compiler](https://github.com/KingLabsA/trace-compiler) | Trace-to-pipeline |
| [Bench Agent](https://github.com/KingLabsA/bench-agent) | Benchmarking |
| [Shell Whisperer](https://github.com/KingLabsA/shell-whisperer) | Shell/bash model |
| [FableForge-14B](https://github.com/KingLabsA/fableforge-14b) | Code gen model |
| [Fable5 Dataset](https://github.com/KingLabsA/fable5-dataset) | Training dataset |
| [Trace Viz](https://github.com/KingLabsA/trace-viz) | Trace visualization |

<p align="center">
  <a href="https://kinglabsa.github.io/fableforge/">🌐 Website</a> · 
  <a href="https://pypi.org/project/fableforge/">📦 PyPI</a> · 
  <a href="https://huggingface.co/fableforge-ai">🤗 HuggingFace</a>
</p>
