# Trajectory Distiller

[![FableForge Ecosystem](https://img.shields.io/badge/FableForge-Ecosystem-purple?style=flat-square)](https://github.com/KingLabsA?q=fableforge) [![PyPI](https://img.shields.io/pypi/v/fableforge-trajectory-distiller?style=flat-square)](https://pypi.org/project/fableforge-trajectory-distiller/) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](LICENSE)


[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE) [![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/) [![Tests](https://img.shields.io/badge/tests-0-yellow.svg)](tests/)


Convert agent traces from multiple formats into training datasets for fine-tuning.

## Installation

```bash
pip install trajectory-distiller
```

## Supported Input Formats

| Format | Description |
|--------|-------------|
| `glint` | Session-based format with turns array |
| `armand0e` | Conversation-based format with tool_calls |
| `vfable` | Trajectory-based format with tool_use |
| `opencoven` | Source/target pair format |
| `victor` | Prompt/response pair format |

## Supported Output Formats

| Format | Description |
|--------|-------------|
| `openai_chat` | OpenAI chat completion format |
| `alpaca` | Alpaca instruction format |
| `sharegpt` | ShareGPT conversation format |
| `conversation` | General conversation format |

## Quick Start

### Distill Traces

```bash
# Convert glint traces to OpenAI chat format (auto-detected)
distill input.jsonl --format openai_chat --output train.jsonl

# Convert armand0e format explicitly
distill input.jsonl --input-format armand0e --format sharegpt -o train.jsonl

# Convert to alpaca format
distill input.jsonl --format alpaca -o alpaca_train.jsonl
```

### Filter Traces

```bash
# Filter to records using specific tools
distill filter traces.jsonl --tool bash --tool edit

# Filter by error rate and quality
distill filter traces.jsonl --min-errors 0.1 --min-quality 0.5

# Filter by session length
distill filter traces.jsonl --min-turns 5 --max-turns 50

# Combine filters and save
distill filter traces.jsonl --tool bash --min-quality 0.3 -o filtered.jsonl
```

### Split Dataset

```bash
# Split into 95/5 train/val
distill split traces.jsonl --train-ratio 0.95 --val-ratio 0.05

# Stratify by tool distribution
distill split traces.jsonl --stratify-by tool --output-dir splits/

# Split with test set
distill split traces.jsonl --train-ratio 0.8 --val-ratio 0.1 --test-ratio 0.1
```

## Fable5 Dataset Usage

```bash
# Glint dataset
distill glint_traces.jsonl --format openai_chat -o glint_openai.jsonl

# armand0e dataset
distill armand0e_data.jsonl --input-format armand0e --format alpaca -o armand0e_alpaca.jsonl

# vfable dataset
distill vfable_traces.jsonl --input-format vfable --format sharegpt -o vfable_sharegpt.jsonl

# opencoven dataset
distill opencoven_pairs.jsonl --input-format opencoven --format openai_chat -o opencoven_openai.jsonl

# victor dataset
distill victor_pairs.jsonl --input-format victor --format conversation -o victor_conv.jsonl
```

## Programming API

```python
from trajectory_distiller import Distiller, FormatConverter, TraceFilter, DataSplitter

# Distill traces
distiller = Distiller()
records = distiller.distill("traces.jsonl", output_format="openai_chat")

# Filter traces
trace_filter = TraceFilter()
filtered = trace_filter.filter_by_tool(records, tools=["bash", "edit"])
filtered = trace_filter.filter_by_quality(filtered, min_quality_score=0.5)

# Convert formats
converter = FormatConverter()
alpaca_records = converter.to_alpaca(records)
sharegpt_records = converter.to_sharegpt(records)

# Split data
splitter = DataSplitter()
splits = splitter.split(records, train_ratio=0.95, stratify_by="tool")
splits.save("output/")
print(splits.stats())
```

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
