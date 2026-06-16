# FableForge-14B

[![FableForge Ecosystem](https://img.shields.io/badge/FableForge-Ecosystem-purple?style=flat-square)](https://github.com/KingLabsA?q=fableforge) [![PyPI](https://img.shields.io/pypi/v/fableforge-14b?style=flat-square)](https://pypi.org/project/fableforge-14b/) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](LICENSE)


[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE) [![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/) [![Tests](https://img.shields.io/badge/tests-0-yellow.svg)](tests/)


Four-stage training pipeline for a 14B parameter coding agent model, trained on Fable5 datasets.

## Overview

FableForge-14B builds a production-quality coding agent through four carefully designed training stages:

1. **Stage 1: Behavior Shaping** — Learn tool-use patterns from v-Fable 100K examples
2. **Stage 2: Skill Distillation** — Master coding excellence from 100K curated code samples
3. **Stage 3: Error Recovery** — Debug like an expert using Glint + armand0e 18K error patterns
4. **Stage 4: DPO Alignment** — Align agent behavior with expert preferences

## Installation

```bash
pip install fableforge-14b
```

## Training Pipeline

### Stage 1: Behavior Shaping

Teaches the model when and how to use coding tools (read, edit, bash, grep, glob).

```python
from fableforge_14b.training.stage1_behavior_shaping import run_stage1, Stage1Config

config = Stage1Config(
    base_model="Qwen/Qwen2.5-14B",
    dataset_path="data/vfable_100k.jsonl",
    LoRA_r=64,
    LoRA_alpha=128,
)
result = run_stage1(config)
```

### Stage 2: Skill Distillation

Trains on 100K high-quality code generation examples across 6 skill categories.

```python
from fableforge_14b.training.stage2_skill_distillation import run_stage2, Stage2Config

config = Stage2Config(stage1_adapter="output/stage1")
result = run_stage2(config)
```

### Stage 3: Error Recovery

Trains on 18K real error patterns to diagnose and fix bugs expertly.

```python
from fableforge_14b.training.stage3_error_recovery import run_stage3, Stage3Config

config = Stage3Config(stage2_adapter="output/stage2")
result = run_stage3(config)
```

### Stage 4: DPO Alignment

Direct Preference Optimization to align with expert agent behavior.

```python
from fableforge_14b.training.stage4_dpo_alignment import run_stage4, Stage4Config

config = Stage4Config(stage3_adapter="output/stage3")
result = run_stage4(config)
```

## Model Merging

Merge LoRA adapters into the base model:

```python
from fableforge_14b.model.merge_lora import merge_lora_adapters, MergeConfig

config = MergeConfig(
    base_model="Qwen/Qwen2.5-14B",
    adapters=["output/stage1", "output/stage2", "output/stage3", "output/stage4"],
)
result = merge_lora_adapters(config)
```

## Quantization

Export in GGUF, AWQ, or GPTQ formats:

```python
from fableforge_14b.model.quantize import quantize, QuantizeConfig

config = QuantizeConfig(
    model_path="output/merged",
    formats=["gguf", "awq", "gptq"],
)
result = quantize(config)
```

## Inference Server

Start a vLLM inference server with tool calling support:

```python
from fableforge_14b.inference.server import InferenceServer, ServerConfig

server = InferenceServer(ServerConfig(
    model_path="output/merged",
    port=8000,
    enable_tool_calling=True,
))
result = server.start()
```

## Evaluation

Run the BenchAgent evaluation benchmark:

```python
from fableforge_14b.evaluation.bench_agent import BenchAgent

bench = BenchAgent(model_path="output/merged")
bench.load_tasks()  # loads default tasks
report = bench.evaluate(model_name="fableforge-14b")
bench.save_report(report, "output/bench_results.json")
```

## Training Configs

Each stage has a YAML config in `src/fableforge_14b/training/configs/`:

- `stage1.yaml` — Behavior shaping (LoRA r=64, 3 epochs, 100K examples)
- `stage2.yaml` — Skill distillation (LoRA r=64, 2 epochs, 100K examples)
- `stage3.yaml` — Error recovery (LoRA r=32, 2 epochs, 18K examples)
- `stage4.yaml` — DPO alignment (LoRA r=16, 1 epoch, preference pairs)

## Datasets

| Stage | Dataset | Size | Focus |
|-------|---------|------|-------|
| 1 | v-Fable | 100K | Tool-use patterns |
| 2 | Coding Excellence | 100K | Code generation quality |
| 3 | Glint + armand0e | 18K | Error diagnosis & recovery |
| 4 | DPO Preferences | 50K pairs | Behavior alignment |

## License

MIT

## Quick Start

```bash
fableforge-14b run "your task here"
```

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
