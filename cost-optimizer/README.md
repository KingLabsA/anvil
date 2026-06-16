# Cost Optimizer

[![FableForge Ecosystem](https://img.shields.io/badge/FableForge-Ecosystem-purple?style=flat-square)](https://github.com/KingLabsA?q=fableforge) [![PyPI](https://img.shields.io/pypi/v/fableforge-cost-optimizer?style=flat-square)](https://pypi.org/project/fableforge-cost-optimizer/) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](LICENSE)


[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE) [![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/) [![Tests](https://img.shields.io/badge/tests-0-yellow.svg)](tests/)


Analyze token waste in LLM agent traces and optimize cost through intelligent model routing.

## Installation

```bash
pip install cost-optimizer
```

## Quick Start

### Analyze Traces

```bash
# Analyze a trace file for waste
costopt analyze trace.jsonl

# Specify model for cost calculation
costopt analyze trace.jsonl --model gpt-4o

# Save results
costopt analyze trace.jsonl -o results.json
```

### Estimate Costs

```bash
# Estimate cost for 1M tokens on Claude 3.5 Sonnet
costopt estimate --model claude-3-5-sonnet-20241022 --tokens 1000000

# Compare costs across all models
costopt estimate --model claude-3-5-sonnet-20241022 --tokens 1000000 --compare
```

### Optimize

```bash
# Get optimization recommendations
costopt optimize trace.jsonl
```

## Programming API

```python
from cost_optimizer import TokenAnalyzer, CostOptimizer, ModelRouter, PricingData

# Analyze traces
analyzer = TokenAnalyzer(default_model="claude-3-5-sonnet-20241022")
report = analyzer.analyze_trace("trace.jsonl")
print(f"Waste: {report.total_waste_tokens} tokens")

# Get optimization recommendations
optimizer = CostOptimizer()
optimizations = optimizer.optimize(report)
for opt in optimizations:
    print(f"{opt.strategy}: saves ${opt.estimated_savings_usd:.2f}")

# Route to cheaper models
router = ModelRouter()
model = router.route("simple formatting task")  # → claude-3-5-haiku-20241022
assessment = router.assess("design a distributed system architecture")
print(f"Complexity: {assessment.complexity_score}, Model: {assessment.recommended_model}")

# Calculate costs
cost = PricingData.calculate_cost(1000000, "claude-3-5-sonnet-20241022")
```

## Supported Models

| Model | Tier | Input/1M tokens | Output/1M tokens |
|-------|------|-----------------|-------------------|
| Claude 3.5 Haiku | mini | $0.80 | $4.00 |
| GPT-4o Mini | mini | $0.15 | $0.60 |
| Qwen3 Coder | mini | $0.50 | $1.50 |
| Claude 3.5 Sonnet | standard | $3.00 | $15.00 |
| GPT-4o | standard | $2.50 | $10.00 |
| GPT-4 Turbo | premium | $10.00 | $30.00 |
| GPT-4 | premium | $30.00 | $60.00 |
| Claude 3 Opus | flagship | $15.00 | $75.00 |

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
