# AgentTelemetry

[![FableForge Ecosystem](https://img.shields.io/badge/FableForge-Ecosystem-purple?style=flat-square)](https://github.com/KingLabsA?q=fableforge) [![PyPI](https://img.shields.io/pypi/v/fableforge-agent-telemetry?style=flat-square)](https://pypi.org/project/fableforge-agent-telemetry/) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](LICENSE)


[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE) [![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/) [![Tests](https://img.shields.io/badge/tests-0-yellow.svg)](tests/)


**Datadog for AI agents** — real-time observability, token tracking, cost estimation, and error rates for autonomous agent sessions.

## Features

- **Multi-format trace ingestion** — Parse traces from Glint-Research, armand0e, and v-Fable formats with auto-detection
- **Token tracking** — Count tokens with tiktoken, estimate costs with real per-model pricing
- **Cost estimation** — Detailed breakdowns for Claude 3.5 Sonnet, Claude 3 Opus, Claude 3 Haiku, GPT-4, GPT-4o, GPT-4o-mini, Qwen3-Coder
- **Error tracking** — Automated error classification (bash, edit, timeout, rate limit, auth, context overflow, etc.) and recovery rate calculation
- **Interactive dashboard** — FastAPI + Plotly charts for session timelines, heatmaps, cost pies, and error breakdowns
- **Dual storage** — ClickHouse for production, SQLite for local/dev with automatic fallback
- **CLI** — Analyze traces, start dashboards, and generate reports from the command line

## Installation

```bash
pip install -e .

# With ClickHouse support (production):
pip install -e ".[clickhouse]"

# Development:
pip install -e ".[dev]"
```

## Quick Start

### Analyze a Trace File

```bash
# Auto-detect format and analyze
agenttelemetry analyze trace.jsonl

# Specify format explicitly
agenttelemetry analyze trace.jsonl --format glint

# Analyze without storing
agenttelemetry analyze trace.jsonl --no-store
```

### Cost Report

```bash
# Detailed cost breakdown
agenttelemetry cost trace.jsonl

# Output:
Model:           gpt-4
Input tokens:       1,234,567  ($0.037037)
Output tokens:        98,765  ($0.005926)
Cache read:          500,000  ($0.000000)
Cache creation:           0  ($0.000000)
─────────────────────────────────────
Total:           $0.042963
```

### Error Report

```bash
# Show errors with classification and recovery rates
agenttelemetry errors trace.jsonl
```

### Token Counting

```bash
# Count tokens in a string
agenttelemetry tokens "Hello, world!" --model gpt-4
```

### Dashboard

```bash
# Start the interactive dashboard
agenttelemetry dashboard

# Custom host/port
agenttelemetry dashboard --host 0.0.0.0 --port 9000
```

Open `http://127.0.0.1:8088/dashboard` to see session metrics, timelines, heatmaps, and cost reports.

## Analyzing Fable5 Traces

Fable5 (v-Fable) traces can be analyzed directly:

```bash
# Ingest a Fable5 session trace
agenttelemetry analyze ~/.fable/sessions/2025-01-15-abc123.jsonl

# View cost breakdown
agenttelemetry cost ~/.fable/sessions/2025-01-15-abc123.jsonl

# Check errors and recovery
agenttelemetry errors ~/.fable/sessions/2025-01-15-abc123.jsonl

# Start dashboard with ingested data
agenttelemetry dashboard
# Then open http://127.0.0.1:8088/dashboard
```

### v-Fable Trace Format

The v-Fable format uses these fields per JSONL line:

```json
{
  "kind": "tool_use",
  "timestamp": "2025-01-15T10:30:00Z",
  "session_id": "abc123",
  "span_id": "span-001",
  "parent_span_id": null,
  "tool_name": "Bash",
  "tokens": {"prompt": 1500, "completion": 800, "cache_read": 200, "cache_write": 50},
  "duration_ms": 2345.6,
  "cost_usd": 0.0234,
  "model": "claude-3.5-sonnet",
  "status": "success",
  "error_message": null
}
```

### Glint-Research Format

```json
{
  "type": "tool_call",
  "timestamp": "2025-01-15T10:30:00Z",
  "session_id": "glint-session-1",
  "span_id": "span-001",
  "tool": "Edit",
  "usage": {
    "input_tokens": 2000,
    "output_tokens": 500,
    "cache_read_input_tokens": 300,
    "cache_creation_input_tokens": 100
  },
  "duration_ms": 1500.0,
  "model": "gpt-4o",
  "error": null
}
```

### armand0e Format

Uses paired `invocation`/`response` events:

```json
{"event": "invocation", "id": "span-001", "session": "arm-session", "tool": {"name": "Write", "input": {"path": "/tmp/file.py"}}, "model": "claude-3.5-sonnet"}
{"event": "response", "id": "span-001", "tokens": {"in": 1500, "out": 800, "cached": 200}, "latency_ms": 1800.0, "model": "claude-3.5-sonnet"}
```

## Pricing Reference

| Model | Input ($/1M tok) | Output ($/1M tok) | Cache Read ($/1M) | Cache Write ($/1M) |
|---|---|---|---|---|
| Claude 3.5 Sonnet | $3.00 | $15.00 | $0.30 | $3.75 |
| Claude 3 Opus | $15.00 | $75.00 | $1.50 | $18.75 |
| Claude 3 Haiku | $0.25 | $1.25 | $0.03 | $0.30 |
| GPT-4 | $30.00 | $60.00 | — | — |
| GPT-4o | $2.50 | $10.00 | $1.25 | — |
| GPT-4o-mini | $0.15 | $0.60 | $0.075 | — |
| Qwen3-Coder | $0.50 | $2.00 | $0.10 | $0.50 |

## Architecture

```
agent_telemetry/
├── __init__.py          # Package exports
├── models.py            # Pydantic models (Span, SessionMetrics, ToolMetrics, CostReport)
├── collector.py         # Trace ingestion (parse_glint_trace, parse_armand0e_trace, parse_vfable_trace)
├── token_tracker.py     # Token counting + cost estimation with real pricing
├── error_tracker.py      # Error detection, classification, recovery rate
├── storage.py           # ClickHouse + SQLite dual storage
├── dashboard.py         # FastAPI dashboard with Plotly charts
└── cli.py               # Click CLI (analyze, dashboard, cost, errors, tokens)
```

## API Endpoints

| Endpoint | Description |
|---|---|
| `GET /dashboard` | Main dashboard with session list |
| `GET /sessions/{id}` | Session detail with metrics table |
| `GET /sessions/{id}/timeline` | Tool call timeline (Plotly bar chart) |
| `GET /sessions/{id}/heatmap` | Tool usage heatmap (Plotly) |
| `GET /cost/report` | Cost breakdown across all sessions |
| `GET /cost/report?session_id=X` | Cost breakdown for a specific session |
| `GET /errors/report` | Error report across all sessions |
| `GET /errors/report?session_id=X` | Error report for a specific session |

## Python API

```python
from agent_telemetry.collector import ingest_trace, calculate_metrics
from agent_telemetry.token_tracker import estimate_cost, count_tokens
from agent_telemetry.error_tracker import generate_error_report
from agent_telemetry.storage import TelemetryStorage

# Analyze a trace
spans = ingest_trace("trace.jsonl", fmt="vfable")
metrics = calculate_metrics(spans)

# Estimate cost
cost = estimate_cost(10000, 5000, model="claude-3.5-sonnet", cache_read=3000)
print(f"Total: ${cost.total_cost:.6f}")

# Store in database
storage = TelemetryStorage()
storage.store_spans(spans)
storage.store_session_metrics(metrics["session"])

# Generate error report
report = generate_error_report("session-123", spans=spans)
print(f"Errors: {report.total_errors}, Recovery rate: {report.recovery_rate:.0%}")

# Query spans
session_spans = storage.query_spans(session_id="session-123")
tool_spans = storage.query_spans(tool_name="Bash")
```

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/

# Run specific test file
pytest tests/test_token_tracker.py -v
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
