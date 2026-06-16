# ErrorRecovery-Engine

[![FableForge Ecosystem](https://img.shields.io/badge/FableForge-Ecosystem-purple?style=flat-square)](https://github.com/KingLabsA?q=fableforge) [![PyPI](https://img.shields.io/pypi/v/error-recovery?style=flat-square)](https://pypi.org/project/error-recovery/) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](LICENSE)


[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE) [![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/) [![Tests](https://img.shields.io/badge/tests-0-yellow.svg)](tests/)


> Self-healing agent middleware that intercepts agent errors and injects recovery prompts. Drop-in, works with any agent.

## How It Works

```
Agent Error → Classify → Pattern Match → Inject Recovery Prompt → Retry → Verify
                                    ↓ (no match)
                              LLM Fallback Prompt
```

1. **Classify** the error into one of 9 categories (bash, edit, read, write, test, network, import, type, unknown)
2. **Match** against a database of recovery patterns using FAISS semantic search
3. **Inject** the recovery prompt into the agent's next execution
4. **Verify** the recovery succeeded; retry with exponential backoff if needed

## Installation

```bash
pip install error-recovery
```

With server support:

```bash
pip install error-recovery[server]
```

From source:

```bash
cd error-recovery
pip install -e ".[dev]"
```

## Quick Start

### As Middleware (Drop-in)

```python
from error_recovery import ErrorRecovery

class MyAgent:
    def run(self, prompt: str, **kwargs) -> str:
        # Your agent logic here
        return "result"

agent = MyAgent()

# Use as context manager
with ErrorRecovery(agent) as mw:
    result = agent.run("do something risky")

# Or create middleware directly
from error_recovery import ErrorRecoveryMiddleware

mw = ErrorRecoveryMiddleware(agent)
wrapped_tool = mw.wrap_tool_call(my_function, tool_name="my_tool")
result = wrapped_tool(args)
```

### As Engine (Programmatic)

```python
from error_recovery import ErrorRecoveryEngine, ErrorRecoveryConfig

config = ErrorRecoveryConfig(max_attempts=3, similarity_threshold=0.8)
engine = ErrorRecoveryEngine(config=config)

result = engine.recover_sync(
    error_message="bash: command not found: xyz",
    context="Running shell command",
    tool_name="bash",
)

print(f"Category: {result.error_category.value}")
print(f"Recovery: {result.recovery_prompt}")
print(f"Success: {result.success}")
```

### As CLI

```bash
# Test recovery on an error message
error-recovery recover --error "command not found: xyz" --tool bash

# Analyze error patterns in a trace file
error-recovery analyze trace.jsonl

# Build a FAISS index from pattern data
error-recovery build-index --data ./patterns/ --output ./my_index/

# Start the recovery API server
error-recovery serve --port 8000
```

### As API Server

```bash
pip install error-recovery[server]
error-recovery serve --port 8000
```

```bash
# Recover from an error
curl -X POST http://localhost:8000/recover \
  -H "Content-Type: application/json" \
  -d '{"error_message": "command not found: xyz", "tool_name": "bash"}'

# Health check
curl http://localhost:8000/health

# Stats
curl http://localhost:8000/stats
```

## Error Categories

| Category | Description | Examples |
|----------|-------------|---------|
| `BASH_ERROR` | Shell/command errors | command not found, permission denied, exit code ≠ 0 |
| `EDIT_ERROR` | File editing errors | pattern not matched, multiple matches |
| `READ_ERROR` | File read errors | file not found, permission denied |
| `WRITE_ERROR` | File write errors | permission denied, disk full |
| `TEST_ERROR` | Test failures | assertion failed, timeout, fixture not found |
| `NETWORK_ERROR` | Network errors | connection refused, DNS failure, SSL errors |
| `IMPORT_ERROR` | Import/dependency errors | ModuleNotFoundError, circular import |
| `TYPE_ERROR` | Type/value errors | TypeError, KeyError, AttributeError |
| `UNKNOWN` | Unclassified errors | - |

## Configuration

```python
from error_recovery import ErrorRecoveryConfig

config = ErrorRecoveryConfig(
    max_attempts=3,              # Max recovery attempts
    similarity_threshold=0.8,     # Minimum similarity for pattern match
    fallback_to_llm=True,        # Use LLM fallback when no pattern matches
    backoff_base=2.0,            # Exponential backoff base
    backoff_max=30.0,            # Max backoff seconds
    cooling_period_seconds=0.0,  # Cooldown between retries
    model_name="all-MiniLM-L6-v2",  # Sentence transformer model
    top_k=5,                     # Number of pattern matches to return
    track_success_rates=True,     # Track pattern success rates
)
```

## Pattern Matching

The engine uses **sentence-transformers** for semantic similarity and **FAISS** for fast nearest-neighbor search. Each pattern has:

- `error_type` — Category (e.g., `bash_error`)
- `pattern` — Regex pattern for fast exact matching
- `error_message` — Description for semantic matching
- `recovery_prompt` — The prompt to inject for recovery
- `success_rate` — Historical success rate (0.0–1.0)
- `tags` — Searchable tags

### Built-in Patterns

- **bash_errors.json** — 53 common bash error patterns
- **edit_errors.json** — 15 file editing patterns
- **test_errors.json** — 15 test failure patterns
- **general.json** — 25 network, import, type, and general patterns

### Custom Patterns

Add your own patterns as JSON files in the patterns directory:

```json
[
  {
    "error_type": "bash_error",
    "error_message": "terraform apply failed",
    "pattern": "terraform.*apply.*failed",
    "recovery_prompt": "Terraform apply failed. Check: (1) run 'terraform plan' first, (2) check for state drift, (3) verify provider credentials.",
    "success_rate": 0.70,
    "tags": ["terraform", "iac"]
  }
]
```

Load them:

```python
from error_recovery import PatternMatcher

matcher = PatternMatcher()
matcher.load_patterns("/path/to/custom_patterns/")
matcher.build_index()
```

## Callbacks

```python
def on_recovery(result: RecoveryResult):
    print(f"Recovered: {result.original_error} → {result.recovery_prompt[:50]}")

def on_failure(error: str):
    print(f"Failed to recover: {error}")

def on_success(tool_name: str):
    print(f"Tool {tool_name} succeeded after recovery")

mw = ErrorRecoveryMiddleware(
    on_recovery=on_recovery,
    on_failure=on_failure,
    on_success=on_success,
)
```

## Architecture

```
error_recovery/
├── models.py              # Pydantic models (ErrorPattern, RecoveryResult, Config)
├── error_classifier.py    # Regex + keyword error classification
├── pattern_matcher.py     # FAISS + sentence-transformers semantic matching
├── recovery_engine.py     # Core recovery logic (classify → match → inject → verify)
├── middleware.py           # Drop-in agent middleware wrapper
├── cli.py                 # CLI: recover, analyze, build-index, serve
└── patterns/               # Built-in recovery patterns
    ├── bash_errors.json    # 53 patterns
    ├── edit_errors.json    # 15 patterns
    ├── test_errors.json    # 15 patterns
    └── general.json         # 25 patterns
```

## Running Tests

```bash
pip install -e ".[dev]"
pytest tests/ -v
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
