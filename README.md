<p align="center">
  <img src="https://img.shields.io/badge/Anvil-0.3.0-orange?style=for-the-badge&logo=hammer&logoColor=white" alt="Anvil Version"/>
  <img src="https://img.shields.io/badge/tests-727-green?style=for-the-badge" alt="Tests"/>
  <img src="https://img.shields.io/badge/python-3.10%2B-blue?style=for-the-badge" alt="Python"/>
  <img src="https://img.shields.io/badge/license-MIT-yellow?style=for-the-badge" alt="License"/>
</p>

<h1 align="center">🔨 Anvil — The Self-Verified Coding Agent</h1>

<p align="center"><em>"Where code gets forged, hammered, and tested until it holds."</em></p>

---

**Anvil** is a complete self-verifying coding agent ecosystem. It doesn't just write code — it plans, executes, **verifies with a trained model**, and recovers from failures autonomously.

## Why Anvil?

### 🎯 Unique Features No One Else Has

| Feature | Anvil | Cursor | Continue | Aider | Cline |
|---------|-------|--------|----------|-------|-------|
| **Verify Loop** | ✅ | ❌ | ❌ | ❌ | ❌ |
| **Error Recovery** | ✅ | ❌ | ❌ | ❌ | ❌ |
| **Multi-Interface** | ✅ | ❌ | ❌ | ❌ | ❌ |
| **Extension System** | ✅ | ❌ | ✅ | ❌ | ❌ |
| **Onboarding Tour** | ✅ | ❌ | ❌ | ❌ | ❌ |
| **Open Source** | ✅ | ❌ | ✅ | ✅ | ✅ |
| **Self-hosted** | ✅ | ❌ | ✅ | ✅ | ✅ |

**What makes Anvil different:**

1. **Verify Loop** - Every change is automatically verified. Other agents generate code and hope it works. Anvil generates, verifies, and fixes until it's correct.

2. **Error Recovery** - When verification fails, Anvil doesn't just report the error. It diagnoses the issue and automatically fixes it, then re-verifies.

3. **Multi-Interface** - Use Anvil your way: Desktop app, Web UI, CLI, VS Code extension, JetBrains plugin, or MCP server. All interfaces share the same powerful backend.

4. **Extension System** - Extend Anvil with custom skills, tools, and integrations. Build your own or install from the community.

5. **Onboarding Tour** - New to Anvil? Interactive guided tours teach you the basics in minutes.

### 🚀 Features You'd Expect

All the modern coding assistant features you're used to:

- **Inline Edit** (Cmd/Ctrl+K) - Edit code directly in the editor
- **Tab Autocomplete** - Ghost text suggestions as you type
- **Slash Commands** - Quick actions like `/test`, `/fix`, `/explain`
- **@-mentions** - Reference files, symbols, and documentation
- **Git Integration** - Auto-commit, diff viewing, undo
- **Custom Rules** - Define AI behavior with custom instructions
- **API Cost Tracking** - See token usage and costs in real-time
- **Checkpoints** - Rollback AI changes with one click
- **Codebase Context** - Index and search your entire codebase
- **Memory System** - Anvil remembers your preferences across sessions

### 💡 Philosophy

**Anvil is built on three principles:**

1. **Verification over generation** - Code isn't done until it's verified. Period.
2. **Local-first** - Works offline, no account required. Your code stays on your machine.
3. **Extensible** - Open source, extensible, and built for the community.

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

### Core Capabilities
- 🔨 **Plan-Execute-Verify-Recover** loop — autonomous coding with verification
- 🧠 **Model-based verification** — trained to catch errors, not just prompt-based
- 🛡️ **Error Recovery** — automatic diagnosis and recovery from failures
- 🔄 **VerifyLoop** — iterative verification until code is correct
- 🐝 **Agent Swarm** — orchestrate multiple specialized agents
- 📊 **Telemetry** — built-in observability and performance tracking

### Product Surface
- 💻 **CLI** — Full command-line interface for all operations
- 🌐 **Web UI** — Beautiful browser-based interface
- 🖥️ **Desktop App** — Native Tauri application (macOS/Windows/Linux)
- 📦 **TypeScript SDK** — Full integration for JavaScript/TypeScript
- 🤖 **MCP Server** — Model Context Protocol for AI agent integration
- 📚 **Documentation Site** — Comprehensive Next.js documentation

### Advanced Features
- 🧠 **Agent Memory** — Persistent cross-session learning
- 🛠️ **Skill Marketplace** — Install and share reusable skills
- 📡 **Multi-Model Support** — OpenAI, Anthropic, local models
- 🔒 **Permission System** — Fine-grained tool access control
- 📝 **Session Sharing** — Export and share coding sessions

### Modern IDE Features
- ✏️ **Inline Edit** (Cmd/Ctrl+K) - Edit code directly in the editor
- ⚡ **Tab Autocomplete** - Ghost text suggestions as you type
- ⚙️ **Slash Commands** - Quick actions: `/test`, `/fix`, `/explain`, `/refactor`
- 📌 **@-mentions** - Reference files, symbols, and documentation
- 🔀 **Git Integration** - Auto-commit, diff viewing, undo
- 📏 **Custom Rules** - Define AI behavior with custom instructions
- 💰 **API Cost Tracking** - See token usage and costs in real-time
- ⏪ **Checkpoints** - Rollback AI changes with one click
- 📚 **Codebase Context** - Index and search your entire codebase
- 🎯 **Memory System** - Anvil remembers your preferences across sessions
- 👥 **Real-time Collaboration** - Work together with WebSocket support
- 🔍 **Integrated Debugging** - Breakpoints, step-through, variable inspection
- 📊 **Monitoring & Metrics** - Prometheus metrics for observability

## Installation

### 🖥️ Desktop App (Recommended)

Download the native desktop app for your platform:

| Platform | Download | Size |
|----------|----------|------|
| **macOS** | [Download .dmg](https://github.com/KingLabsA/anvil/releases/latest/download/Anvil-Desktop-aarch64.dmg) | ~80 MB |
| **Windows** | [Download .msi](https://github.com/KingLabsA/anvil/releases/latest/download/Anvil-Desktop-x64.msi) | ~70 MB |
| **Linux** | [Download .AppImage](https://github.com/KingLabsA/anvil/releases/latest/download/Anvil-Desktop-x86_64.AppImage) | ~75 MB |

**No login required!** Anvil works fully offline. Authentication is only needed if you want cloud features or device sync.

<details>
<summary>📦 Alternative Installation Methods</summary>

### CLI Install (for developers)

```bash
# One-liner install script
curl -fsSL https://raw.githubusercontent.com/KingLabsA/anvil/main/install.sh | bash

# Or install with pip
pip install fableforge-anvil-agent[all]
```

### Docker

```bash
# Pull and run
docker pull ghcr.io/kinglabsa/anvil:0.3.0
docker run -it ghcr.io/kinglabsa/anvil:0.3.0 anvil run "Hello world"

# Or use docker-compose
git clone https://github.com/KingLabsA/anvil.git
cd anvil
docker-compose up -d
```

### Build from Source

```bash
git clone https://github.com/KingLabsA/anvil.git
cd anvil

# Install Python dependencies
pip install -e ".[all]"

# Build desktop app (requires Rust and Node.js)
cd desktop/anvil-desktop
npm install
npm run tauri build
```

</details>

## Architecture

Anvil is built as a modular, extensible platform:

```
┌─────────────────────────────────────────────────────────────┐
│                        Anvil Platform                        │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │  Desktop │  │   Web    │  │   CLI    │  │   MCP    │   │
│  │   App    │  │   UI     │  │          │  │  Server  │   │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘   │
│       │              │              │              │         │
│       └──────────────┴──────────────┴──────────────┘         │
│                          │                                    │
│                    ┌─────▼─────┐                             │
│                    │   REST    │                             │
│                    │   API     │                             │
│                    └─────┬─────┘                             │
│                          │                                    │
│       ┌──────────────────┼──────────────────┐               │
│       │                  │                  │               │
│  ┌────▼────┐      ┌─────▼─────┐     ┌─────▼─────┐        │
│  │  Auth   │      │  Database │     │ WebSocket │        │
│  │  (JWT)  │      │ (SQLite)  │     │  Server   │        │
│  └─────────┘      └───────────┘     └───────────┘        │
│                                                               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │ Monitor  │  │  Debug   │  │Extension │  │  Memory  │   │
│  │(Prometheus│  │  System  │  │  System  │  │  System  │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

### Core Components

- **Backend API** - FastAPI-based RESTful API with authentication
- **Database** - SQLite (default) with PostgreSQL support
- **WebSocket Server** - Real-time collaboration and updates
- **Extension System** - Plugin architecture for extensibility
- **Memory System** - Persistent learning across sessions
- **Monitoring** - Prometheus metrics and observability
- **Debug Adapter** - Integrated debugging support

### Interfaces

- **Desktop App** - Native Tauri application (macOS/Windows/Linux)
- **Web UI** - Browser-based IDE with Monaco editor
- **CLI** - Full-featured command-line interface
- **VS Code Extension** - Editor integration
- **JetBrains Plugin** - IntelliJ/PyCharm/WebStorm integration
- **MCP Server** - Model Context Protocol for AI agent integration

## Quick Start

### 🎬 See It In Action

```bash
# 1. Open Anvil Desktop (or run: anvil serve for web UI)

# 2. Try inline edit (Cmd/Ctrl+K)
# Select code and describe the change you want

# 3. Try tab autocomplete
# Start typing and Anvil suggests completions

# 4. Try slash commands in chat
# Type / to see available commands
```

### 💻 CLI Usage

```bash
# Run a task
anvil run "Create a REST API for a todo app"

# With specific model
anvil run --model gpt-4o "Refactor the authentication module"

# Interactive chat
anvil chat

# Start web UI
anvil serve
# Open http://localhost:8000
```

### Python API

```python
from anvil import AnvilAgent

# Create agent
agent = AnvilAgent(model="gpt-4")

# Run task with verification
result = agent.run("Create a REST API for a todo app")
print(result.success)  # True
print(result.output)   # Generated code
```

### TypeScript SDK

```typescript
import { AnvilClient } from '@anvil-ai/sdk';

const anvil = new AnvilClient({
  baseUrl: 'http://localhost:8000',
  model: 'gpt-4o',
});

// Run task
const result = await anvil.run('Create a REST API');
console.log(result.success);
```

## Deployment

### Local Development

```bash
anvil serve --port 8000
```

### Docker (Recommended for Teams)

```bash
docker-compose up -d
```

### VPS/Cloud

See [DEPLOYMENT.md](DEPLOYMENT.md) for comprehensive deployment guide including:
- DigitalOcean/AWS/GCP VM setup
- Railway/Render/Fly.io PaaS deployment
- Kubernetes configuration
- Production security (auth, SSL, rate limiting)
- Monitoring and backup strategies

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

## Models

Anvil integrates with these FableForge models:

- [**FableForge-14B**](https://huggingface.co/fableforge-ai/FableForge-14B) — Main code generation model
- [**ShellWhisperer-1.5B**](https://huggingface.co/fableforge-ai/ShellWhisperer-1.5B) — Lightweight shell/bash specialist
- [**ReasonCritic-7B**](https://huggingface.co/fableforge-ai/ReasonCritic-7B) — Verification and critique model

## Testing

```bash
# Run all 727 tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=anvil --cov-report=html

# Run specific test suite
pytest tests/test_memory.py -v
```

## Configuration

Create `.anvil.json` in your project root:

```json
{
  "model": {
    "model": "local",
    "max_tokens": 4096
  },
  "verify": {
    "enabled": true,
    "auto_recover": true,
    "max_retries": 3
  },
  "tools": {
    "allow_shell": true,
    "sandbox": false
  },
  "memory": {
    "enabled": true,
    "max_items": 1000
  }
}
```

## Ecosystem

Anvil is part of the **FableForge** ecosystem — 21 open-source projects for building reliable AI agents:

<p align="center">
  <a href="https://kinglabsa.github.io/fableforge/">🌐 Website</a> · 
  <a href="https://pypi.org/project/fableforge-anvil-agent/">📦 PyPI</a> · 
  <a href="https://ghcr.io/kinglabsa/anvil">🐳 Docker</a> · 
  <a href="https://huggingface.co/fableforge-ai">🤗 HuggingFace</a> ·
  <a href="https://github.com/KingLabsA/anvil/tree/main/docs">📚 Docs</a>
</p>

## Contributing

Contributions are welcome! Please read our contributing guidelines and submit pull requests to the main repository.

## License

MIT © [KingLabs](https://github.com/KingLabsA)

## Star History

If you find Anvil useful, please consider giving it a star! ⭐
