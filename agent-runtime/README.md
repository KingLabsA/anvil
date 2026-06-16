# AgentRuntime — systemd for AI Agents

[![FableForge Ecosystem](https://img.shields.io/badge/FableForge-Ecosystem-purple?style=flat-square)](https://github.com/KingLabsA?q=fableforge) [![PyPI](https://img.shields.io/pypi/v/fableforge-agent-runtime?style=flat-square)](https://pypi.org/project/fableforge-agent-runtime/) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](LICENSE)


[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE) [![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/) [![Tests](https://img.shields.io/badge/tests-0-yellow.svg)](tests/)


A persistent agent daemon that manages AI agent processes, serializes state, and resumes sessions. Think of it as **systemd for AI agents** — start, pause, resume, and checkpoint agent sessions with full state persistence.

## Architecture

```
┌─────────────┐     ┌──────────────────┐     ┌────────────────┐
│   CLI       │────▶│   FastAPI Server │────▶│  SessionManager│
│  (agentd)   │     │   (port 8721)    │     │                │
└─────────────┘     └──────────────────┘     └───────┬────────┘
                                                      │
                              ┌─────────────────────────┼─────────────────────┐
                              │                         │                     │
                     ┌────────▼────────┐      ┌────────▼────────┐   ┌───────▼──────┐
                     │ StateSerializer │      │   MemoryStore   │   │    Daemon     │
                     │   (SQLite)      │      │  (Short+Long)   │   │  (Heartbeat)  │
                     └─────────────────┘      └─────────────────┘   └──────────────┘
```

## Features

- **Session Lifecycle**: Create, start, pause, resume, stop agent sessions
- **State Persistence**: Full session state serialized to SQLite
- **Checkpoints**: Save and restore complete state at any point
- **Memory Management**: Short-term (conversation context) and long-term (key-value with semantic search)
- **Memory Consolidation**: Auto-summarize old short-term memories
- **Auto-Checkpoint**: Configurable interval for automatic state snapshots
- **Graceful Shutdown**: State preservation on daemon stop
- **Session Timeout**: Automatic cleanup of stopped sessions
- **REST API**: Full HTTP API via FastAPI
- **CLI**: Command-line interface for all operations
- **Docker**: Production-ready container image

## Quick Start

### Install

```bash
pip install -e .
```

### Start the Daemon

```bash
agentd start --port 8721
```

### Create a Session

```bash
agentd create --name "my-agent" --model fableforge-14b --system-prompt "You are a helpful assistant"
```

### List Sessions

```bash
agentd list
```

### Resume a Session

```bash
agentd resume <session-id> --checkpoint-id <checkpoint-id>
```

### Stop the Daemon

```bash
agentd stop
```

## API Reference

### POST /sessions

Create a new session.

```json
{
  "name": "my-agent",
  "model": "fableforge-14b",
  "system_prompt": "You are a helpful assistant.",
  "tools": ["search", "calculator"]
}
```

### GET /sessions

List all sessions.

### GET /sessions/{id}

Get session state.

### POST /sessions/{id}/start

Start a session (begins heartbeat and auto-checkpoint).

### POST /sessions/{id}/pause

Pause a running session (creates checkpoint, cancels heartbeat).

### POST /sessions/{id}/resume

Resume a paused or stopped session.

```json
{
  "session_id": "abc123",
  "checkpoint_id": "cp_456"
}
```

### POST /sessions/{id}/stop

Stop a session (creates final checkpoint).

### GET /sessions/{id}/memory

List memory keys or retrieve specific key: `?key=my_key`

### POST /sessions/{id}/memory

Store a memory entry.

```json
{
  "key": "user_preference",
  "value": {"theme": "dark", "language": "en"}
}
```

### GET /sessions/{id}/checkpoints

List all checkpoints for a session.

### POST /sessions/{id}/checkpoints

Create a checkpoint. Query param: `?label=my-checkpoint`

### GET /health

Daemon health status.

## Session States

```
CREATED ──▶ RUNNING ──◆──▶ PAUSED ──▶ RUNNING
              │    │         │
              │    └──▶ STOPPED
              └──▶ ERROR
```

## Memory Architecture

### Short-Term Memory

- Last N messages per session (default 50)
- Automatic pruning when window exceeded
- Used for conversation context

### Long-Term Memory

- Key-value store with optional embeddings
- Cosine similarity semantic search
- Persistent across sessions
- Consolidation: summarizes old short-term into long-term

### Consolidation

When short-term memory exceeds a threshold, the daemon:
1. Summarizes the recent conversation
2. Stores the summary in long-term memory
3. Prunes old short-term entries

## Configuration

| Env Variable | Default | Description |
|---|---|---|
| `AGENT_RUNTIME_DB` | `~/.agent_runtime/state.db` | SQLite database path |
| `AGENT_RUNTIME_MEMORY_DB` | `~/.agent_runtime/memory.db` | Memory database path |
| `AGENT_RUNTIME_PORT` | `8721` | HTTP server port |
| `AGENT_RUNTIME_HOST` | `0.0.0.0` | HTTP server bind address |
| `AGENT_RUNTIME_CHECKPOINT_INTERVAL` | `60` | Auto-checkpoint interval (seconds) |
| `AGENT_RUNTIME_SESSION_TIMEOUT` | `3600` | Session timeout (seconds) |

## Docker

```bash
docker build -f docker/Dockerfile -t agent-runtime .
docker run -p 8721:8721 -v agent_data:/root/.agent_runtime agent-runtime
```

## Testing

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

## Project Structure

```
agent-runtime/
├── pyproject.toml
├── docker/
│   └── Dockerfile
├── src/
│   └── agent_runtime/
│       ├── __init__.py
│       ├── models.py              # Pydantic models
│       ├── state_serializer.py    # SQLite state persistence
│       ├── memory_store.py        # Short/long-term memory
│       ├── session_manager.py     # Session lifecycle
│       ├── daemon.py              # Background daemon process
│       ├── server.py              # FastAPI HTTP server
│       └── cli.py                 # CLI interface
├── tests/
│   └── test_state_serializer.py
└── README.md
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
