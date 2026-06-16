# ShellWhisperer

[![FableForge Ecosystem](https://img.shields.io/badge/FableForge-Ecosystem-purple?style=flat-square)](https://github.com/KingLabsA?q=fableforge) [![PyPI](https://img.shields.io/pypi/v/fableforge-shell-whisperer?style=flat-square)](https://pypi.org/project/fableforge-shell-whisperer/) [![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](LICENSE)


[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE) [![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/) [![Tests](https://img.shields.io/badge/tests-0-yellow.svg)](tests/)


> **Natural language → shell commands. 50ms on edge.**

A 1.5B parameter edge-native shell agent fine-tuned from Qwen3-1.5B. Converts natural language descriptions into safe, correct shell commands — designed to run on phones and edge devices via ONNX Runtime or llama.cpp GGUF.

## Features

- **Edge-native**: Runs in <50ms on mobile/edge via ONNX or GGUF
- **Multi-OS**: Linux, macOS, Windows PowerShell prompts
- **Safety-first**: Built-in guardrails against destructive commands (rm -rf /, fork bombs, pipe-to-shell)
- **Context-aware**: Uses working directory, OS type, and recent command history
- **Multiple backends**: HuggingFace Transformers, ONNX Runtime, llama.cpp
- **Streaming**: WebSocket streaming for real-time output
- **Fine-tune your own**: LoRA training on Fable5 traces or custom data

## Quick Start

### Install

```bash
pip install shell-whisperer

# With training support:
pip install "shell-whisperer[train]"

# With GGUF inference:
pip install "shell-whisperer[gguf]"

# Everything:
pip install "shell-whisperer[train,gguf,dev]"
```

### One-shot Prediction

```bash
# Basic usage
sw "find all python files over 100 lines"
# → find . -name "*.py" -exec wc -l {} + | awk '$1 > 100'

sw "kill the process on port 8080"
# → lsof -ti:8080 | xargs kill -9

sw --os-type macos "install ffmpeg"
# → brew install ffmpeg

sw --os-type windows "show all listening ports"
# → Get-NetTCPConnection -State Listen | Format-Table LocalPort, OwningProcess -AutoSize
```

### Interactive Mode

```bash
sw --interactive

sw> find all python files over 100 lines
┌─────────────────────────────────────────────────────────┐
│ find . -name "*.py" -exec wc -l {} + | awk '$1 > 100'  │
└─────────────────────────────────────────────────────────┘
42.5ms

sw> !os macos
OS set to: macos

sw> install ffmpeg
┌──────────────────────┐
│ brew install ffmpeg  │
└──────────────────────┘
28.1ms
```

### Start API Server

```bash
sw --serve --port 8000
# Or specify model:
sw --serve --model ./models/shell-whisperer-merged --port 8000
```

## Fine-Tuning

### Prepare Training Data

ShellWhisperer extracts training pairs from Fable5 trace formats:

```python
from shell_whisperer.data_extractor import load_training_data

# Load from JSONL traces (auto-detects format)
pairs = load_training_data("./traces/glint_data.jsonl", fmt="auto")

# Or specify format explicitly
from shell_whisperer.data_extractor import (
    extract_bash_from_glint,
    extract_bash_from_armand0e,
    extract_bash_from_vfable,
)

pairs = extract_bash_from_glint("./traces/glint.jsonl")
pairs = extract_bash_from_armand0e("./traces/armand0e.jsonl")
pairs = extract_bash_from_vfable("./traces/vfable.jsonl")
```

#### Supported Trace Formats

**Glint** — Command traces with shell intent metadata:
```jsonl
{"type": "shell_intent", "intent": "find all python files over 100 lines"}
{"type": "shell_command", "command": "find . -name '*.py' -exec wc -l {} + | awk '$1 > 100'", "shell": "bash", "exit_code": 0}
```

**armand0e** — Structured shell session logs:
```jsonl
{"event": "command_executed", "prompt": "show disk usage sorted by size", "command": "du -sh * | sort -rh", "exit_status": 0}
```

**v-Fable** — Validated Fable traces with confirmation signals:
```jsonl
{"role": "user", "utterance": "find all json files modified recently"}
{"role": "assistant", "tool_call": {"name": "execute_shell", "arguments": {"command": "find . -name '*.json' -mtime -7"}}, "validation": {"confirmed": true, "exit_code": 0}}
```

### Train with LoRA

```bash
# LoRA fine-tune (default)
sw train --data ./traces/data.jsonl --epochs 3

# Full fine-tune
sw train --data ./traces/data.jsonl --full-finetune

# Custom parameters
sw train \
  --data ./traces/data.jsonl \
  --model-name Qwen/Qwen3-1.5B \
  --output-dir ./models/my-shell-whisperer \
  --epochs 5 \
  --lr 1e-4 \
  --batch-size 8 \
  --os-type linux
```

### Training in Python

```python
from shell_whisperer.trainer import TrainConfig, train_lora
from shell_whisperer.data_extractor import load_training_data

# Load data
pairs = load_training_data("./traces/data.jsonl", include_builtin=True)
print(f"Training with {len(pairs)} pairs")

# Configure and train
config = TrainConfig(
    model_name="Qwen/Qwen3-1.5B",
    output_dir="./models/shell-whisperer-lora",
    epochs=3,
    learning_rate=2e-4,
    lora_r=16,
    use_4bit=True,
    use_unsloth=True,
)

adapter_path = train_lora(config=config, training_pairs=pairs)

# Merge adapter with base model
from shell_whisperer.trainer import merge_and_save

merge_and_save(
    adapter_path=adapter_path,
    output_dir="./models/shell-whisperer-merged",
)
```

## Export for Edge

```bash
# Export to ONNX
sw export --format onnx --model ./models/shell-whisperer-merged

# Export to GGUF (for llama.cpp)
sw export --format gguf --model ./models/shell-whisperer-merged

# 4-bit quantization (smallest, fastest)
sw export --format 4bit --model ./models/shell-whisperer-merged

# 8-bit quantization
sw export --format 8bit --model ./models/shell-whisperer-merged

# Export all formats
sw export --format all --model ./models/shell-whisperer-merged
```

### Memory Estimates

| Format | RAM Required | Latency (edge) |
|--------|-------------|----------------|
| FP32   | ~6.0 GB     | ~200ms         |
| FP16   | ~3.0 GB     | ~100ms         |
| 8-bit  | ~1.5 GB     | ~60ms          |
| 4-bit  | ~0.75 GB    | ~50ms          |
| GGUF Q4_K_M | ~0.84 GB | ~50ms    |

## Inference

### Python API

```python
from shell_whisperer import ShellWhisperer

# Load model
sw = ShellWhisperer(os_type="linux")
sw.load_model("./models/shell-whisperer-merged")

# Predict
result = sw.predict("find all python files over 100 lines")
print(result.command)
# → find . -name "*.py" -exec wc -l {} + | awk '$1 > 100'

# Context-aware prediction
result = sw.predict(
    "find config files",
    working_directory="/etc",
    recent_history=["ls -la", "cd /etc"],
    os_type="linux",
)

# Batch prediction
results = sw.predict_batch([
    "find all python files over 100 lines",
    "kill the process on port 8080",
    "show disk usage sorted by size",
])

# Streaming
for token in sw.predict_stream("find all python files"):
    print(token, end="", flush=True)

# Safety warnings
result = sw.predict("delete everything")
if result.safety_warnings:
    for warning in result.safety_warnings:
        print(f"⚠ {warning}")

sw.unload()
```

### REST API

```bash
# Start server
sw --serve --port 8000

# Predict
curl -X POST http://localhost:8000/predict \
  -H "Content-Type: application/json" \
  -d '{"prompt": "find all python files over 100 lines", "os_type": "linux"}'

# Batch predict
curl -X POST http://localhost:8000/predict/batch \
  -H "Content-Type: application/json" \
  -d '{"prompts": ["find python files", "kill port 8080"]}'

# Health check
curl http://localhost:8000/health

# Model info
curl http://localhost:8000/info
```

### WebSocket Streaming

```javascript
const ws = new WebSocket("ws://localhost:8000/ws/stream");

ws.onopen = () => {
  ws.send(JSON.stringify({
    prompt: "find all python files over 100 lines",
    os_type: "linux"
  }));
};

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.token) {
    process.stdout.write(data.token);
  } else if (data.done) {
    console.log("\nCommand:", data.command);
    if (data.safety_warnings.length) {
      console.log("Warnings:", data.safety_warnings);
    }
  }
};
```

## Example Training Pairs

Built-in high-quality pairs from real-world shell usage:

| Natural Language | Shell Command | Quality |
|----------------|---------------|---------|
| find all python files over 100 lines | `find . -name "*.py" -exec wc -l {} + \| awk '$1 > 100'` | 0.85 |
| kill the process on port 8080 | `lsof -ti:8080 \| xargs kill -9` | 0.80 |
| show disk usage sorted by size | `du -sh * \| sort -rh` | 0.75 |
| recursively search for TODO in all python files | `grep -rn "TODO" --include="*.py" .` | 0.83 |
| rename all .txt files to .md | `for f in *.txt; do mv "$f" "${f%.txt}.md"; done` | 0.84 |
| remove all stopped docker containers | `docker container prune -f` | 0.73 |
| show all git commits by the current user this month | `git log --author="$(git config user.name)" --since="$(date +%Y-%m-01)" --oneline` | 0.88 |
| list all unique IPs that connected via SSH | `grep "Accepted" /var/log/auth.log \| awk '{print $11}' \| sort -u` | 0.84 |

## Safety System

ShellWhisperer includes a built-in safety layer that:

1. **Blocks destructive commands**: `rm -rf /`, fork bombs, `dd` to disk
2. **Warns on sudo**: Flags commands requiring elevated privileges
3. **Flags pipe-to-shell**: Warns about `curl | bash` patterns
4. **Prevents chmod 777**: Warns about insecure permissions

```python
result = sw.predict("delete all files")
# Safety warning: ⚠ SAFETY: Destructive: recursive force-delete
```

## Architecture

```
┌─────────────────────────────────────────┐
│           Natural Language Input         │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│         System Prompt (OS-specific)       │
│    LINUX_PROMPT / MACOS_PROMPT /         │
│    WINDOWS_PROMPT + Safety Rules          │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│       Qwen3-1.5B (LoRA fine-tuned)       │
│         1.5B parameters                  │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│          Output Cleaning                  │
│   - Strip markdown/backticks             │
│   - Remove model prefixes                │
│   - Multi-line pipe/chain handling        │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│          Safety Check                     │
│   - rm -rf protection                    │
│   - sudo warning                         │
│   - pipe-to-shell detection              │
└──────────────┬──────────────────────────┘
               │
┌──────────────▼──────────────────────────┐
│         Shell Command Output              │
└───────────────────────────────────────────┘
```

## Project Structure

```
shell-whisperer/
├── pyproject.toml
├── README.md
├── src/shell_whisperer/
│   ├── __init__.py           # Package init + exports
│   ├── prompts.py            # OS-specific system prompts + safety rules
│   ├── data_extractor.py     # Fable5 trace extraction + quality filtering
│   ├── trainer.py            # LoRA/Full fine-tuning on Qwen3-1.5B
│   ├── exporter.py           # ONNX, GGUF, 4-bit/8-bit export + memory estimation
│   ├── inference.py          # Multi-backend inference (Transformers, ONNX, llama.cpp)
│   ├── server.py             # FastAPI server (REST + WebSocket)
│   └── cli.py                # CLI: sw predict, train, export, serve
└── tests/
    ├── test_data_extractor.py
    └── test_inference.py
```

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Lint
ruff check src/ tests/

# Type check
mypy src/
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
