# Fable5 Dataset

[![FableForge Ecosystem](https://img.shields.io/badge/FableForge-Ecosystem-purple?style=flat-square)](https://github.com/KingLabsA?q=fableforge) [![PyPI](https://img.shields.io/pypi/v/fable5-dataset?style=flat-square)](https://pypi.org/project/fable5-dataset/) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](LICENSE)


[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE) [![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/) [![Tests](https://img.shields.io/badge/tests-0-yellow.svg)](tests/)


Load, preprocess, and manage the Fable5 agent trace datasets for fine-tuning and evaluation.

## Installation

```bash
pip install fable5-dataset
```

## Dataset Sources

| Source | Format | Description |
|--------|--------|-------------|
| **Glint** | Session-based with turns | Full agent sessions with tool use |
| **armand0e** | Conversation with tool_calls | Multi-turn conversations with function calling |
| **vfable** | Trajectory with tool_use | Agent trajectories with sequential tool use |
| **Coding Excellence** | Session-based with quality scores | High-quality coding sessions rated by experts |
| **OpenCoven** | Source/target pairs | Instruction-following input/output pairs |
| **Victor** | Prompt/response pairs | Single-turn coding instruction pairs |

## Quick Start

### Load Datasets

```bash
# Load the Glint dataset
fable5 load glint

# Load all datasets with PII removal
fable5 load all --remove-pii

# Load with quality filter
fable5 load coding_excellence --min-quality 0.8 -o filtered.jsonl
```

### View Statistics

```bash
# View stats for a specific dataset
fable5 stats --source glint

# View stats from a local file
fable5 stats traces.jsonl

# Compare all datasets
fable5 stats --source all
```

### Convert Formats

```bash
# Convert to OpenAI chat format
fable5 convert traces.jsonl --format openai_chat -o train.jsonl

# Convert to Alpaca format
fable5 convert traces.jsonl --format alpaca -o alpaca.jsonl
```

### Generate Benchmarks

```bash
# Generate 50 benchmark tasks from Glint
fable5 benchmark --source glint --num-tasks 50

# Generate category-specific benchmarks
fable5 benchmark --source coding_excellence --categories debugging implementation -o bench.jsonl
```

### Split Data

```bash
# Split into 95/5 train/val
fable5 split traces.jsonl --train-ratio 0.95 --val-ratio 0.05

# Stratified split by tool distribution
fable5 split traces.jsonl --stratify-by tool --output-dir splits/
```

## Programming API

```python
from fable5_dataset import DatasetLoader, Preprocessor, BenchmarkGenerator, DatasetStats

# Load datasets
loader = DatasetLoader()
records = loader.load_dataset("glint", normalize=True, remove_pii=True)
all_data = loader.load_dataset("all")

# Preprocess
preprocessor = Preprocessor()
normalized = preprocessor.normalize_format(records, source_format="glint")
cleaned = preprocessor.remove_pii(normalized)
filtered = preprocessor.filter_quality(cleaned, min_quality=0.7)

# Statistics
stats = DatasetStats()
result = stats.compute_stats(records)
print(result.summary())
print(result.to_dict())

# Benchmark generation
gen = BenchmarkGenerator()
tasks = gen.generate_benchmark(records, num_tasks=50, categories=["debugging", "implementation"])
gen.save_benchmark(tasks, "benchmark.jsonl")

# Compare datasets
comparisons = stats.compare_datasets(all_data)
for name, ds_stats in comparisons.items():
    print(f"{name}: {ds_stats.total_rows} records, {ds_stats.avg_turns_per_session:.1f} avg turns")
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
