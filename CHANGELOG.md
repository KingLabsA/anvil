# Changelog — FableForge Ecosystem

All notable changes to the FableForge ecosystem will be documented in this file.
For project-specific changes, see each project's individual CHANGELOG.md.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] — 2025-06-15

### Ecosystem-Wide — OpenCode Parity Release

This release brings Anvil to feature parity with OpenCode, adding multi-agent
support, fine-grained permissions, MCP integration, and 6 new tools.

#### Anvil (0.1.0 → 0.2.0)

- **Multi-agent**: Switch agents, `@mention` subagents, define custom agents
  via `BaseAgent`. Four built-in agents (Plan, Build, Explore, Verify).
- **Permissions**: Per-agent allow/deny/ask rules with glob patterns.
- **MCP**: Connect to external tool servers via Model Context Protocol.
- **Undo/Redo**: Snapshot-based history with full session undo/redo.
- **Compaction**: Auto-compact context when tokens exceed limits.
- **Daemon**: Background daemon mode with Unix socket / HTTP API.
- **13 tools**: `glob`, `grep`, `ls`, `bash`, `read`, `write`, `edit`,
  `snapshot`, `undo`, `redo`, `compact`, `agent_switch`, `agent_list`.
- **Config v2**: New `anvil.json` format.
- **Security fixes**: Path traversal (CVE-2025-FSA-001), permission bypass.

See [anvil/CHANGELOG.md](anvil/CHANGELOG.md) for full details.

#### VerifyLoop (0.1.0 → 0.2.0)

- **Multi-verifier pipeline**: Chain syntax, test, lint, and type verifiers
  with per-verifier configuration.
- **Custom verifiers**: Register project-specific verification steps.
- **Parallel verification**: Run independent verifiers concurrently.

#### ErrorRecovery (0.1.0 → 0.2.0)

- **Error classifier v2**: Improved classification with 12 error categories.
- **Recovery strategies**: Configurable recovery strategies per error type.
- **Middleware**: Pluggable middleware hooks for custom recovery logic.

#### AgentSwarm (0.1.0 → 0.2.0)

- **Orchestrator v2**: Support for primary/subagent agent modes.
- **Agent switching**: Hot-swap agents mid-task with context preservation.
- **Permission integration**: Per-agent permission rules from Anvil config.

#### AgentRuntime (0.1.0 → 0.2.0)

- **Docker improvements**: Smaller image, multi-stage build, health checks.
- **State serialization**: Save and restore session state across restarts.

#### AgentSkills (0.1.0 → 0.2.0)

- **Skill registry**: Dynamic skill loading from project `.anvil/skills/`.
- **13 tool mappings**: Skills can use all new Anvil tools.

#### AgentConstitution (0.1.0)

- **Initial release**: Value alignment framework for agent behavior.
- **Constitution checker**: Validate agent outputs against constitutional rules.

#### AgentCurriculum (0.1.0)

- **Initial release**: Training curriculum generation for agent models.
- **Curriculum templates**: Pre-built templates for common training scenarios.

#### AgentFuzzer (0.1.0)

- **Initial release**: Fuzz testing for agent robustness.
- **Mutation strategies**: Prompt mutation, tool call mutation, context corruption.

#### AgentProfiler (0.1.0)

- **Initial release**: Cost and performance profiling for agents.
- **Token tracking**: Per-model, per-agent token usage and cost reports.

#### AgentTelemetry (0.1.0)

- **Initial release**: Observability for agent sessions.
- **OpenTelemetry**: Export traces, metrics, and logs to any OTel backend.

#### BenchAgent (0.1.0)

- **Initial release**: Benchmark framework for evaluating agent capabilities.
- **Task types**: Code generation, debugging, refactoring, multi-step planning.

#### CostOptimizer (0.1.0)

- **Initial release**: LLM cost reduction through model routing and caching.
- **Smart routing**: Route simple tasks to cheaper models (Haiku, GPT-4o-mini).

#### ShellWhisperer (0.1.0)

- **Initial release**: Small model for shell command prediction.
- **ONNX export**: Optimized inference for edge deployment.

#### ReasonCritic (0.1.0)

- **Initial release**: Critique-and-refinement model for agent reasoning.
- **Integration**: Hooks into Anvil's verify-recover loop.

#### FableForge-14B (0.1.0)

- **Initial release**: 14B parameter base model trained on curated code data.
- **Fine-tuning scripts**: LoRA and QLoRA training scripts included.

#### Fable5-Dataset (0.1.0)

- **Initial release**: 5-task benchmark for evaluating agent coding ability.
- **Dataset card**: Full documentation of collection methodology and task design.

#### TraceCompiler (0.1.0 → 0.2.0)

- **Config v2**: New YAML-based configuration for compilation passes.
- **Optimization passes**: Dead code elimination, context compression.

#### TrajectoryDistiller (0.1.0)

- **Initial release**: Extract training data from agent execution traces.
- **Format support**: JSON, JSONL, and custom trace formats.

#### TraceViz (0.1.0)

- **Initial release**: Next.js dashboard for visualizing agent traces.
- **Real-time**: WebSocket-based real-time trace streaming.

#### AgentDev (0.1.0)

- **Initial release**: VS Code extension for Anvil development.
- **Plan/Execute/Verify panels**: Dedicated VS Code panels for each agent phase.

#### CLI (0.1.0)

- **Initial release**: Unified `fableforge` CLI for ecosystem management.

### Infrastructure

- **CI**: Full CI pipeline with change detection, Python 3.10–3.12 matrix,
  TypeScript Node 18/20 matrix, and Docker image builds.
- **Release workflow**: Automated PyPI publishing, GitHub Releases, and
  ghcr.io Docker images on tag push.
- **Version sync**: `scripts/sync_versions.py` for monorepo version management.
- **Community**: CONTRIBUTING.md, CODE_OF_CONDUCT.md, SECURITY.md, issue
  templates, PR templates, and FUNDING.yml.

## [0.1.0] — 2025-03-01

### Ecosystem-Wide — Initial Release

The first public release of the FableForge ecosystem, comprising 21 projects
for building, training, evaluating, and deploying self-verified coding agents.

#### Core Projects

| Project          | Version | Description                                |
|------------------|---------|--------------------------------------------|
| Anvil            | 0.1.0   | Plan → Execute → Verify → Recover engine   |
| VerifyLoop       | 0.1.0   | Verification & repair pipeline             |
| ErrorRecovery    | 0.1.0   | Error classification & handling            |
| AgentSwarm       | 0.1.0   | Multi-agent orchestration                   |
| AgentRuntime     | 0.1.0   | Runtime infrastructure                      |
| AgentSkills      | 0.1.0   | Skill system                                |
| AgentConstitution| 0.1.0   | Value alignment                             |
| AgentCurriculum  | 0.1.0   | Training curriculum                         |
| AgentFuzzer      | 0.1.0   | Agent fuzz testing                          |
| AgentProfiler    | 0.1.0   | Profiling & cost analysis                   |
| AgentTelemetry   | 0.1.0   | Observability                               |
| BenchAgent       | 0.1.0   | Benchmark framework                         |
| CostOptimizer    | 0.1.0   | LLM cost reduction                          |
| ShellWhisperer   | 0.1.0   | Shell command prediction model              |
| ReasonCritic     | 0.1.0   | Critique & refinement model                |
| FableForge-14B   | 0.1.0   | 14B base model                              |
| Fable5-Dataset   | 0.1.0   | 5-task benchmark dataset                    |
| TraceCompiler    | 0.1.0   | Trace optimization compiler                 |
| TrajectoryDistiller | 0.1.0 | Training data extraction                  |
| TraceViz         | 0.1.0   | Trace visualization dashboard               |
| AgentDev         | 0.1.0   | VS Code extension                            |
| CLI              | 0.1.0   | Ecosystem command-line interface             |

[0.2.0]: https://github.com/KingLabsA/anvil/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/KingLabsA/anvil/releases/tag/v0.1.0
