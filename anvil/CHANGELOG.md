# Changelog — Anvil

All notable changes to the Anvil project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] — 2025-06-15

### Added — OpenCode Parity

- **Multi-agent support**: Switch between agents, use `@mention` to invoke
  subagents, and define custom agents via `BaseAgent` configuration. Four
  built-in agents: Plan, Build, Explore, Verify. (#42)
- **Fine-grained permissions**: `PermissionConfig` with per-agent allow/deny/ask
  rules, glob-based pattern matching, and priority resolution. (#55)
- **MCP (Model Context Protocol)**: Connect Anvil to external tool servers
  via the MCP protocol. Configured in `anvil.json` under `mcp_servers`. (#61)
- **Undo/Redo**: Full session undo/redo for file operations with snapshot-based
  history. Press `Ctrl+Z` in TUI mode or call `session.undo()`. (#38)
- **Compaction**: Automatically compact conversation context when it exceeds
  token limits, preserving critical information. Configurable threshold. (#47)
- **Daemon mode**: Run Anvil as a background daemon with `anvil daemon`.
  Communicate via Unix socket or HTTP API. (#50)
- **13 new tools**: `glob`, `grep`, `ls`, `bash`, `read`, `write`, `edit`,
  `snapshot`, `undo`, `redo`, `compact`, `agent_switch`, `agent_list`. (#44, #52)
- **Configuration v2**: New `anvil.json` config format with model settings,
  permissions, MCP servers, agent definitions, and tool configuration. (#40)
- **TUI improvements**: Syntax highlighting, diff view for edits, agent status
  panel, compact mode indicator. (#57)

### Changed

- **Engine refactor**: `AnvilEngine` now orchestrates agent switching and
  permission checks within the Plan → Execute → Verify → Recover loop. (#42)
- **Session model**: `Session` now tracks agent context, permission decisions,
  and snapshot history alongside step execution. (#45)
- **Verify pipeline**: `VerifyPipeline` now supports custom verifiers and
  per-agent verification configs. (#48)

### Fixed

- **Token counting**: Fixed overcounting in multi-byte UTF-8 content. (#39)
- **File edit race**: Fixed concurrent edit detection on macOS. (#41)
- **Permission bypass**: Closed a bypass where `ask` rules could be skipped
  by listing tools the agent didn't have. (#53)
- **Compact context loss**: Fixed an edge case where compaction dropped the
  most recent tool call. (#58)

### Security

- **Path traversal**: Canonicalize all file paths and reject paths outside
  the project sandbox. (#46, CVE-2025-FSA-001)
- **Permission escalation**: Enforce permission checks even for built-in
  agents. (#53)

## [0.1.0] — 2025-03-01

### Added

- **Core loop**: Plan → Execute → Verify → Recover workflow. The foundational
  engine that distinguishes Anvil from other coding agents. (#1)
- **7 tools**: `bash`, `read`, `write`, `edit`, `grep`, `glob`, `ls`. (#5)
- **Verify pipeline**: Syntax checking, test execution, lint, and type
  verification integrated into the agent loop. (#3)
- **4 integrations**: OpenAI, Anthropic, local (llama.cpp), and custom model
  providers via `ModelRegistry`. (#8)
- **Session management**: Full step history, cost tracking, and session
  persistence. (#10)
- **CLI**: `anvil run`, `anvil verify`, `anvil agents`, `anvil config`. (#6)
- **Configuration**: `AnvilConfig` with model selection, verification toggles,
  and step limits. (#4)
- **Dockerfile**: Production-ready Docker image for containerized deployment. (#12)

### Changed

- Nothing (initial release).

### Fixed

- Nothing (initial release).

### Security

- Sandbox path resolution for file operations. (#2)

[0.2.0]: https://github.com/KingLabsA/anvil/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/KingLabsA/anvil/releases/tag/v0.1.0
