# VerifyLoop

[![FableForge Ecosystem](https://img.shields.io/badge/FableForge-Ecosystem-purple?style=flat-square)](https://github.com/KingLabsA?q=fableforge) [![PyPI](https://img.shields.io/pypi/v/verifyloop?style=flat-square)](https://pypi.org/project/verifyloop/) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](LICENSE)


[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE) [![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/) [![Tests](https://img.shields.io/badge/tests-65-green.svg)](tests/)


> **The Instagram moment for agents.** Plan → Execute → Verify → Recover.

VerifyLoop is an agent framework where the **verify** step uses a trained model — not a prompt. Every other agent framework verifies with the same LLM that generated the code. That's like asking the person who wrote the bug to confirm there's no bug.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     AgentPipeline                        │
│                                                          │
│  ┌─────────┐    ┌──────────┐    ┌─────────┐    ┌──────┐ │
│  │  PLAN    │───▶│ EXECUTE  │───▶│ VERIFY  │───▶│ DONE │ │
│  │         │    │          │    │         │    │  ✓   │ │
│  └─────────┘    └──────────┘    └────┬────┘    └──────┘ │
│                                      │                    │
│                               ┌──────▼──────┐            │
│                               │  Confidence  │            │
│                               │   < 0.8 ?    │            │
│                               └──────┬──────┘            │
│                                      │ Yes               │
│                               ┌──────▼──────┐            │
│                               │  RECOVER    │            │
│                               │  Fix errors │            │
│                               └──────┬──────┘            │
│                                      │                    │
│                              Loop back to EXECUTE         │
└─────────────────────────────────────────────────────────┘
```

### Why VerifyLoop is different

| Feature | Other Agents | VerifyLoop |
|---------|-------------|------------|
| Verification | LLM prompt (same model) | Trained ReasonCritic model |
| Error recovery | Retry or re-prompt | Pattern-matched recovery strategies |
| Confidence scoring | None or vibes | Numeric confidence threshold |
| Recovery loop | None or ad-hoc | Structured Plan→Exec→Verify→Recover |
| Token tracking | Best-effort | Built-in per-phase tracking |

## Quick Start

### Install

```bash
pip install verifyloop
```

### CLI

```bash
# Run a task
vl run "add authentication to app.py"

# Run from a task file
vl run --task-file tasks/fix_bug.json

# Interactive mode (confirm each step)
vl run --interactive "refactor the database layer"

# Specify models
vl run --model gpt-4o --verify-model reason-critic-7b "write tests"

# Dry run (plan only, don't execute)
vl run --dry-run "create a REST API"

# Limit iterations
vl run --max-iterations 3 "fix the flaky test"

# Docker sandbox for bash commands
vl run --sandbox "install dependencies and run tests"
```

### Python API

```python
import asyncio
from verifyloop import AgentPipeline, PipelineConfig

async def main():
    config = PipelineConfig(
        model="gpt-4o",
        verify_model="reason-critic-7b",
        max_iterations=5,
        confidence_threshold=0.8,
    )

    pipeline = AgentPipeline(config)

    # Stream events
    async def on_event(event, data):
        print(f"[{event}] {data}")

    pipeline.on_event(on_event)

    result = await pipeline.run(
        task="Add a hello() function to app.py",
        context="Python project with a Flask web app",
    )

    print(f"Status: {result.status}")
    print(f"Steps: {len(result.steps)}")
    print(f"Duration: {result.duration_seconds:.2f}s")

asyncio.run(main())
```

### Individual Components

```python
from verifyloop import PlanGenerator, Executor, Verifier, VerifierConfig, Recoverer

# Use components individually
planner = PlanGenerator(model="gpt-4o")
plan = await planner.generate_plan("Fix the login bug in auth.py")

executor = Executor(working_dir=".")
step = await executor.bash("pytest tests/")

verifier = Verifier(VerifierConfig(verify_model="reason-critic-7b"))
result = await verifier.verify_file_state("auth.py", expected_content="def login()")

recoverer = Recoverer(model="gpt-4o")
recovery = await recoverer.recover("FileNotFoundError: auth.py not found")
```

## API Reference

### `PipelineConfig`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `model` | `str` | `"gpt-4o"` | LLM model for planning/recovery |
| `verify_model` | `str` | `"reason-critic-7b"` | Trained verification model |
| `max_iterations` | `int` | `5` | Max Plan→Execute→Verify loops |
| `confidence_threshold` | `float` | `0.8` | Minimum confidence to accept result |
| `max_recovery_attempts` | `int` | `3` | Max recovery attempts per iteration |
| `working_dir` | `str` | `"."` | Working directory for file ops |
| `dry_run` | `bool` | `False` | Plan only, don't execute |
| `interactive` | `bool` | `False` | Confirm each step before execution |
| `sandbox` | `bool` | `False` | Run bash in Docker container |
| `sandbox_image` | `str` | `"python:3.11-slim"` | Docker image for sandbox |

### `AgentPipeline`

```python
pipeline = AgentPipeline(config)

# Run a task
result: AgentRun = await pipeline.run(task, context, max_iterations)

# Register event callbacks
pipeline.on_event(callback)  # async def callback(event: str, data: dict)

# Access token usage
print(pipeline.token_usage)
```

### `AgentRun`

| Field | Type | Description |
|-------|------|-------------|
| `task` | `str` | Original task description |
| `steps` | `list[Step]` | All plan/execute/verify/recover steps |
| `status` | `RunStatus` | `pending` / `planning` / `executing` / `verifying` / `recovering` / `completed` / `failed` |
| `token_usage` | `TokenUsage` | Prompt + completion token counts |
| `duration_seconds` | `float` | Total wall-clock time |
| `iteration` | `int` | Which iteration completed |
| `metadata` | `dict` | Additional metadata |

### `Executor`

```python
executor = Executor(working_dir=".", sandbox=False)

# Tools
result = await executor.bash("ls -la")
result = await executor.read("app.py")
result = await executor.write("new_file.py", content)
result = await executor.edit("app.py", old_content, new_content)
result = await executor.web_search("python requests library")
result = await executor.web_fetch("https://example.com/docs")

# File history and rollback
history = executor.get_file_history("app.py")
executor.rollback_file("app.py")
```

### `Verifier`

```python
verifier = Verifier(VerifierConfig(
    verify_model="reason-critic-7b",
    confidence_threshold=0.8,
    prefer_trained_model=True,
))

# Verification methods
result = await verifier.verify_code_edits(plan, execute_steps)
result = await verifier.verify_bash_output("pytest", output, expected="passed")
result = await verifier.verify_file_state("app.py", expected_content="def hello")
result = await verifier.verify_tests("pytest tests/", working_dir=".")
```

### `Recoverer`

```python
recoverer = Recoverer(model="gpt-4o", max_recovery_attempts=3)

# Recovery with pattern matching
recovery = await recoverer.recover(
    error="SyntaxError: invalid syntax",
    context="File: app.py, Line 42",
    attempt=1,
)

# Pattern types: edit, create, retry, simplify, analyze
print(recovery.recovery_type)   # "edit"
print(recovery.recovery_attempt) # "Fix syntax error in the file"
print(recovery.exhausted)        # False

# Check if retry is worthwhile
should_retry = recoverer.should_retry("TimeoutError", attempt=2)  # True
```

### `InMemoryStore` / `FileStore`

```python
from verifyloop import InMemoryStore, FileStore

# In-memory (default)
memory = InMemoryStore()
await memory.store("key", {"data": "value"})
result = await memory.retrieve("key")
results = await memory.search("value")

# Persistent file storage
memory = FileStore(base_dir=".verifyloop_memory")
await memory.store("key", {"data": "value"}, namespace="project1")
```

### `ConversationContext`

```python
from verifyloop.memory import ConversationContext

ctx = ConversationContext()
ctx.add_message("user", "Fix the bug in main.py")
ctx.add_file_context("main.py", "def broken():\n    return 1/0")

# Build context string for LLM
context = ctx.build_context_string()
```

## Configuration

### Environment Variables

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | OpenAI API key (for GPT models) |
| `ANTHROPIC_API_KEY` | Anthropic API key (for Claude models) |
| `VERIFYLOOP_VERIFY_MODEL` | Override the verification model |
| `VERIFYLOOP_CONFIDENCE` | Override confidence threshold (0.0-1.0) |

### Task File Format

```json
{
  "task": "Add authentication to app.py",
  "context": "Flask application with a login route",
  "model": "gpt-4o",
  "verify_model": "reason-critic-7b",
  "max_iterations": 3
}
```

## Comparison with Other Agent Frameworks

### vs. AutoGPT / BabyAGI

| Aspect | AutoGPT | VerifyLoop |
|--------|---------|------------|
| Planning | Single prompt | Decomposed substeps with tool estimation |
| Verification | None | Trained model with confidence scoring |
| Recovery | Basic retry | Pattern-matched strategies (5 types) |
| Loop control | Infinite loop risk | Bounded iterations + convergence check |

### vs. LangChain Agents

| Aspect | LangChain | VerifyLoop |
|--------|-----------|------------|
| Verification | LLM-as-judge (same model) | Dedicated trained verification model |
| Structured output | Optional | Enforced via Pydantic models |
| Recovery | Chain retries | Typed recovery with strategy selection |
| Token tracking | Callback-based | Built-in per-phase tracking |

### vs. Claude Code / Cursor

| Aspect | Claude Code | VerifyLoop |
|--------|-------------|------------|
| Verification | Same model self-review | Dedicated ReasonCritic model |
| Recovery | Re-prompt | Pattern-matched with LLM fallback |
| Programmatic | Limited CLI | Full Python API + CLI |
| Extensibility | Plugin system | Tool interface + plugin system |

## Verification Model: ReasonCritic

The key differentiator. VerifyLoop uses **ReasonCritic**, a trained model specifically for verification:

1. **Not a prompt** — It's a model fine-tuned on verification tasks (code review, test analysis, output comparison)
2. **Falls back gracefully** — If ReasonCritic is unavailable, falls back to a general LLM with structured verification prompts
3. **Confidence scoring** — Numeric 0-1 confidence score, not binary pass/fail
4. **Actionable failures** — Every failure comes with fix suggestions, not just "it broke"

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
