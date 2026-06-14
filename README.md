<p align="center">
  <img src="https://img.shields.io/badge/Anvil-0.1.0-orange?style=for-the-badge&logo=hammer&logoColor=white" alt="Anvil Version"/>
  <img src="https://img.shields.io/badge/tests-593-green?style=for-the-badge" alt="Tests"/>
  <img src="https://img.shields.io/badge/python-3.10%2B-blue?style=for-the-badge" alt="Python"/>
  <img src="https://img.shields.io/badge/license-MIT-yellow?style=for-the-badge" alt="License"/>
</p>

<h1 align="center">🔨 Anvil — Where Code Gets Forged</h1>

<p align="center"><em>"Where code gets forged, hammered, and tested until it holds."</em></p>

---

**Anvil** is the flagship self-verifying coding agent from the [FableForge](https://github.com/KingLabsA?q=fableforge) ecosystem. It doesn't just write code — it plans, executes, **verifies with a trained model**, and recovers from failures autonomously.

## Why Anvil?

Every other agent verifies with the **same LLM that generated the code**. That's like asking the person who wrote the bug to confirm there's no bug. Anvil uses a dedicated verification model ([ReasonCritic-7B](https://huggingface.co/fableforge-ai/ReasonCritic-7B)) trained to catch what generating models miss.

```
┌─────────────────────────────────────────────────────────┐
│                     Anvil Pipeline                       │
│                                                          │
│  ┌─────────┐    ┌──────────┐    ┌─────────┐    ┌──────┐ │
│  │  PLAN    │───▶│ EXECUTE  │───▶│ VERIFY  │───▶│ DONE │ │
│  │ (LLM)   │    │ (LLM)   │    │(Model)  │    │  ✓   │ │
│  └─────────┘    └──────────┘    └────┬────┘    └──────┘ │
│                                      │ fail              │
│                                 ┌────▼────┐             │
│                                 │ RECOVER │─────────────┤
│                                 │(ErrorRecovery)        │
│                                 └─────────┘             │
└─────────────────────────────────────────────────────────┘
```

## Features

- 🔨 **Plan-Execute-Verify-Recover** loop — the Instagram moment for agents
- 🧠 **Model-based verification** — not prompt-based, trained to catch errors
- 🛡️ **Error Recovery** — powered by [error-recovery](https://github.com/KingLabsA/error-recovery)
- 🔄 **VerifyLoop** — built on [verifyloop](https://github.com/KingLabsA/verifyloop)
- 🐝 **Agent Swarm** — orchestrate multiple agents via [agent-swarm](https://github.com/KingLabsA/agent-swarm)
- 📊 **Telemetry** — built-in observability via [agent-telemetry](https://github.com/KingLabsA/agent-telemetry)
- 🧪 **593 tests passing** — battle-tested before it ships

## Quick Start

```bash
pip install fableforge-anvil-agent
anvil --help
```

### Basic Usage

```python
from anvil import AnvilAgent

agent = AnvilAgent(model="gpt-4")
result = agent.run("Create a REST API for a todo app")
print(result)
```

### CLI Usage

```bash
# Run a task
anvil run "Fix the authentication bug in src/auth.py"

# With verification model
anvil run --verifier reason-critic "Refactor the database layer"

# With swarm mode
anvil swarm --agents 3 "Build the entire backend"
```

## Architecture

Anvil integrates all FableForge components into a unified agent:

| Component | Package | Purpose |
|-----------|---------|---------|
| [VerifyLoop](https://github.com/KingLabsA/verifyloop) | `verifyloop` | Plan → Execute → Verify loop |
| [Error Recovery](https://github.com/KingLabsA/error-recovery) | `error-recovery` | Failure classification & recovery |
| [ReasonCritic](https://github.com/KingLabsA/reason-critic) | `reason-critic` | Trained verification model |
| [Agent Swarm](https://github.com/KingLabsA/agent-swarm) | `fableforge-agent-swarm` | Multi-agent orchestration |
| [Agent Telemetry](https://github.com/KingLabsA/agent-telemetry) | `fableforge-agent-telemetry` | Observability & tracing |
| [Agent Profiler](https://github.com/KingLabsA/agent-profiler) | `fableforge-agent-profiler` | Performance profiling |
| [Agent Constitution](https://github.com/KingLabsA/agent-constitution) | `agent-constitution` | Safety guardrails |
| [Agent Curriculum](https://github.com/KingLabsA/agent-curriculum) | `agent-curriculum` | Learning progression |
| [Agent Skills](https://github.com/KingLabsA/agent-skills) | `fableforge-agent-skills` | Tool definitions |
| [Agent Fuzzer](https://github.com/KingLabsA/agent-fuzzer) | `agent-fuzzer` | Adversarial testing |
| [Agent Runtime](https://github.com/KingLabsA/agent-runtime) | `fableforge-agent-runtime` | Execution sandbox |
| [Cost Optimizer](https://github.com/KingLabsA/cost-optimizer) | `fableforge-cost-optimizer` | Token cost management |
| [Trajectory Distiller](https://github.com/KingLabsA/trajectory-distiller) | `fableforge-trajectory-distiller` | Extract patterns from runs |
| [Trace Compiler](https://github.com/KingLabsA/trace-compiler) | `fableforge-trace-compiler` | Compile traces to pipelines |
| [Bench Agent](https://github.com/KingLabsA/bench-agent) | `fableforge-bench-agent` | Benchmarking framework |

## Docker

```bash
docker pull ghcr.io/kinglabsa/anvil:0.2.0
docker run -it ghcr.io/kinglabsa/anvil:0.2.0 anvil run "Hello world"
```

## Models

Anvil integrates with these FableForge models:

- [**FableForge-14B**](https://huggingface.co/fableforge-ai/FableForge-14B) — Main code generation model
- [**ShellWhisperer-1.5B**](https://huggingface.co/fableforge-ai/ShellWhisperer-1.5B) — Lightweight shell/bash specialist
- [**ReasonCritic-7B**](https://huggingface.co/fableforge-ai/ReasonCritic-7B) — Verification and critique model

## Testing

```bash
# Run all 593 tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=anvil --cov-report=html
```

## Ecosystem

Anvil is part of the **FableForge** ecosystem — 21 open-source projects for building reliable AI agents:

<p align="center">
  <a href="https://kinglabsa.github.io/fableforge/">🌐 Website</a> · 
  <a href="https://pypi.org/project/fableforge-anvil-agent/">📦 PyPI</a> · 
  <a href="https://ghcr.io/kinglabsa/anvil">🐳 Docker</a> · 
  <a href="https://huggingface.co/fableforge-ai">🤗 HuggingFace</a>
</p>

## License

MIT © [KingLabs](https://github.com/KingLabsA)
