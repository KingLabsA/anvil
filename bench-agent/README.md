# BenchAgent — HumanEval for Tool Use

[![FableForge Ecosystem](https://img.shields.io/badge/FableForge-Ecosystem-purple?style=flat-square)](https://github.com/KingLabsA?q=fableforge) [![PyPI](https://img.shields.io/pypi/v/fableforge-bench-agent?style=flat-square)](https://pypi.org/project/fableforge-bench-agent/) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](LICENSE)


[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE) [![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/) [![Tests](https://img.shields.io/badge/tests-0-yellow.svg)](tests/)


A standardized benchmark for evaluating LLM tool-use capabilities across multiple categories: bash commands, code editing, code reading, code writing, multi-tool orchestration, and error recovery.

## Installation

```bash
pip install bench-agent
```

For development:

```bash
pip install -e ".[dev]"
```

## Quick Start

```bash
# List available tasks
bench-agent list-tasks

# List tasks by category
bench-agent list-tasks --category bash

# Run benchmark against a model
bench-agent run --model gpt-4 --category bash

# Run all categories
bench-agent run --model fableforge-14b --all

# View leaderboard
bench-agent leaderboard

# Export leaderboard as markdown
bench-agent export --format markdown
```

## Task Categories

### BASH (21 tasks)
Shell command execution: finding files, processing text, managing processes, network operations, log parsing, and system administration tasks.

### EDIT (22 tasks)
Code modification: fixing bugs, refactoring code, adding features, changing APIs, adding type hints, converting sync to async, error handling, and API evolution.

### READ (16 tasks)
Code comprehension: understanding structure, finding patterns, tracing execution, identifying vulnerabilities, and explaining code behavior.

### WRITE (16 tasks)
Code creation: generating new files, configuration, tests, Dockerfiles, project scaffolding, and CI/CD pipelines.

### MULTI-TOOL (16 tasks)
Complex tasks requiring 3+ tools in sequence: read → analyze → modify → verify, full project setup, and multi-file refactoring.

### ERROR RECOVERY (16 tasks)
Fixing broken code, recovering from errors, handling edge cases: syntax errors, runtime errors, race conditions, security vulnerabilities, and infinite loops.

## Scoring Methodology

Each task produces a `TaskResult` with:

| Metric | Weight | Description |
|--------|--------|-------------|
| Functional correctness | 60% | Does the solution work as expected? |
| Efficiency | 25% | Fewer turns and tokens = higher score |
| Error recovery | 15% | How well does the model recover from errors? |

For failed tasks, partial credit applies:

| Component | Weight | Description |
|-----------|--------|-------------|
| Partial completion | 50% | How close to a correct solution? |
| Error recovery rate | 30% | Were errors identified and addressed? |
| Efficiency | 20% | Resource usage despite failure |

### Score Calculation

```
Overall Score = 0.6 * functional_score + 0.15 * recovery_score + 0.25 * efficiency_score
```

For failed tasks:
```
Score = 0.5 * partial_credit + 0.3 * recovery_score + 0.2 * efficiency_score
```

Final scores are scaled to 0–100.

## Task Structure

Each task defines:

- **task_id**: Unique identifier (e.g., `bash-001`, `edit-015`)
- **category**: One of the six categories
- **difficulty**: `easy`, `medium`, or `hard`
- **description**: What the model needs to accomplish
- **initial_state**: Files to create before task execution
- **expected_outcome**: What constitutes success
- **tools_required**: Which tools the model should use
- **max_turns**: Maximum tool-use turns allowed
- **verification_script**: Python script to verify correctness

## Task Counts

| Category | Count |
|----------|-------|
| BASH | 21 |
| EDIT | 22 |
| READ | 16 |
| WRITE | 16 |
| MULTI-TOOL | 16 |
| ERROR RECOVERY | 16 |
| **Total** | **107** |

## Python API

```python
from bench_agent.evaluator import evaluate_model
from bench_agent.runner import TaskRunner
from bench_agent.tasks import BASH_TASKS, EDIT_TASKS

# Run evaluation
report = evaluate_model(
    model_name="gpt-4",
    provider="openai",
    categories=[TaskCategory.BASH, TaskCategory.EDIT],
    num_tasks=10,
)

print(f"Total Score: {report.total_score}")
print(f"Category Scores: {report.category_scores}")
print(f"Error Recovery Rate: {report.error_recovery_rate}")
```

## Leaderboard

```python
from bench_agent.leaderboard import load_leaderboard, update_leaderboard, export_markdown

lb = load_leaderboard("leaderboard.json")
lb = update_leaderboard(lb, "gpt-4", results)
print(export_markdown(lb))
```

## Architecture

```
src/bench_agent/
├── __init__.py          # Package init
├── models.py            # Pydantic data models
├── tasks.py             # 107 task definitions
├── runner.py            # Task execution runner
├── scorer.py            # Scoring system
├── leaderboard.py       # Leaderboard management
├── evaluator.py         # Model evaluation
└── cli.py               # Click CLI interface
```

## Development

```bash
# Run tests
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=bench_agent

# Lint
ruff check src/
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
