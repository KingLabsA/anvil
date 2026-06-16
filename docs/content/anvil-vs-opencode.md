# Anvil vs OpenCode: A Detailed Comparison

> **Last Updated:** June 2026
> **Anvil:** FableForge's autonomous coding agent
> **OpenCode:** Open-source AI coding agent by Anomaly (opencode.ai, 174K+ GitHub stars)

This document provides an honest, side-by-side comparison of FableForge Anvil and OpenCode.
The goal is to help developers choose the right tool — or understand how they complement each other.

---

## Table of Contents

1. [Architecture](#1-architecture)
2. [Tools / Built-in Capabilities](#2-tools--built-in-capabilities)
3. [Verification](#3-verification)
4. [Error Recovery](#4-error-recovery)
5. [Model Support](#5-model-support)
6. [Cost Optimization](#6-cost-optimization)
7. [Ecosystem](#7-ecosystem)
8. [Training Pipeline](#8-training-pipeline)
9. [Daemon Mode](#9-daemon-mode)
10. [Session Management](#10-session-management)
11. [What Anvil Has That OpenCode Doesn't](#11-what-anvil-has-that-opencode-doesnt)
12. [What OpenCode Has That Anvil Doesn't](#12-what-opencode-has-that-anvil-doesnt)
13. [When to Use Anvil vs OpenCode](#13-when-to-use-anvil-vs-opencode)
14. [Can They Work Together?](#14-can-they-work-together)

---

## 1. Architecture

### Anvil

Anvil follows a structured **Plan → Execute → Verify → Recover** loop:

1. **Plan:** Analyzes the task, decomposes it into subtasks, and identifies dependencies.
2. **Execute:** Runs each subtask using its tool suite (Bash, Read, Write, Edit, Grep, Glob, LS).
3. **Verify:** After each execution step, independently verifies the output through its
   VerifyPipeline — checking syntax, running tests, linting, and validating imports.
4. **Recover:** If verification fails, the ErrorRecovery system categorizes the error,
   matches it against known patterns, and applies a recovery strategy before retrying.

This loop is deterministic and enforceable. Anvil cannot skip the verify step. It cannot
proceed past an error without attempting recovery. The architecture assumes that LLMs
make mistakes and that verification is not optional.

### OpenCode

OpenCode uses an **agent-based architecture** with two primary modes:

- **Build mode**: Full-access agent that can read, write, edit files, and run bash commands.
- **Plan mode**: Read-only agent that analyzes code and suggests changes without modifying anything.

It also has three built-in subagents:
- **General**: Multi-step research and task execution (full tool access except todo).
- **Explore**: Fast, read-only codebase exploration.
- **Scout**: Read-only external dependency and documentation research.

OpenCode's architecture is more organic — the LLM decides what to do step-by-step, and
the user can switch between Build and Plan modes with the Tab key. There's no enforced
verification loop; the LLM may or may not run tests after making changes, depending on
the prompt and agent configuration.

**Key difference:** Anvil mandates verification as part of its core loop. OpenCode leaves
verification to the LLM's discretion and user prompting.

---

## 2. Tools / Built-in Capabilities

### Anvil (7 tools)

| Tool     | Purpose                                          |
|----------|--------------------------------------------------|
| Bash     | Execute shell commands                           |
| Read     | Read file contents                               |
| Write    | Create or overwrite files                        |
| Edit     | Modify existing files with string replacement    |
| Grep     | Search file contents with regex                   |
| Glob     | Find files by pattern                             |
| LS       | List directory contents                           |

Anvil's tool set is intentionally minimal. Each tool is purpose-built for the
Plan→Execute→Verify→Recover loop. The verification and recovery systems consume
the output of these tools at each step.

### OpenCode (13+ built-in tools + unlimited via MCP)

| Tool          | Purpose                                        |
|---------------|------------------------------------------------|
| bash          | Execute shell commands                         |
| edit          | Modify files with exact string replacement     |
| write         | Create or overwrite files                      |
| read          | Read file contents with line range support      |
| grep          | Search file contents with regex                 |
| glob          | Find files by pattern                           |
| lsp           | LSP-powered code intelligence (experimental)    |
| apply_patch   | Apply patch/diff files                          |
| skill         | Load skill definitions (SKILL.md files)          |
| todowrite     | Manage todo/task lists during sessions          |
| webfetch      | Fetch and read web pages                        |
| websearch     | Search the web (via Exa AI)                    |
| question      | Ask the user clarifying questions               |

Plus **MCP (Model Context Protocol)** support for unlimited extensibility — add any
external tool or service (Sentry, Context7, databases, APIs, Git providers, etc.) as
an MCP server.

**Key difference:** OpenCode has a significantly larger built-in tool set and MCP
extensibility. Anvil has 7 focused tools. OpenCode has 13+ built-in tools and
unlimited MCP extensibility.

---

## 3. Verification

### Anvil

Anvil has a built-in **VerifyPipeline** that runs automatically after every execution step:

1. **Syntax Verification**: Checks that generated code parses correctly (language-aware).
2. **Test Verification**: Runs the project's test suite and confirms pass/fail.
3. **Lint Verification**: Runs configured linters and confirms zero errors.
4. **Import Verification**: Validates that all imports resolve to existing modules.

If any verification step fails, the result is fed into the ErrorRecovery system before
retrying. The developer does not need to remember to run tests — Anvil always runs them.

### OpenCode

OpenCode does not have a built-in verification pipeline. Verification is handled by:

1. **LSP integration (experimental)**: Can provide real-time diagnostics, go-to-definition,
   find references, hover info, and call hierarchy. But this is opt-in and experimental.
2. **Agent configuration**: You can create custom agents with specific prompts that
   instruct the LLM to run tests after changes. But this is prompt-driven, not enforced.
3. **User prompting**: Asking OpenCode to "run the tests" or "check for lint errors"
   triggers manual verification through bash commands.
4. **AGENTS.md rules**: You can add instructions like "Always run tests after making
   changes" to your AGENTS.md file, but this is still LLM-discretionary.

**Key difference:** Anvil enforces verification architecturally. OpenCode relies on
prompting and user discipline. Anvil will always verify; OpenCode may forget to.

---

## 4. Error Recovery

### Anvil

Anvil includes a dedicated **ErrorRecovery** system with:

- **9 error categories**: Syntax errors, import errors, type errors, runtime errors,
  test failures, lint failures, dependency errors, timeout errors, and unknown errors.
- **Pattern-matched recovery strategies**: Each error category has specific recovery
  approaches (e.g., for import errors, check package installation; for syntax errors,
  re-validate the code block; for test failures, analyze the test output and fix the
  implementation or the test).
- **Automatic retry**: After applying a recovery strategy, Anvil automatically retries
  the failed step, up to a configurable maximum.
- **Escalation**: If all recovery attempts fail, Anvil surfaces a detailed diagnostic
  to the user with the error chain and attempted fixes.

### OpenCode

OpenCode does not have a dedicated error recovery system. Error handling is implicit:

- **Agent resilience**: The LLM may notice an error in bash output and attempt to fix it.
  This is prompt-driven and depends on the model's capability.
- **Undo/Redo**: OpenCode has a built-in `/undo` command that reverts all changes from
  the last interaction, allowing the user to re-prompt.
- **Doom loop detection**: OpenCode has a `doom_loop` permission that can detect when an
  agent appears stuck and prompt recovery.
- **Subagent isolation**: Errors in subagents (General, Explore, Scout) don't crash the
  primary session.

**Key difference:** Anvil has architecturally enforced error recovery with categorized
strategies. OpenCode relies on the LLM's inherent ability to notice errors and the
user's willingness to undo and retry.

---

## 5. Model Support

### Anvil

Anvil supports **6 backend providers**:

| Backend          | Models                               |
|------------------|--------------------------------------|
| Local/Ollama     | Any local model via Ollama           |
| GPT-4o           | OpenAI GPT-4o                        |
| GPT-4o-mini      | OpenAI GPT-4o-mini                   |
| o3-mini          | OpenAI o3-mini                       |
| Claude 3.5       | Anthropic Claude 3.5 Sonnet          |
| Custom           | Any OpenAI-compatible API endpoint   |

### OpenCode

OpenCode supports **75+ LLM providers** through the AI SDK and Models.dev, including:

| Provider              | Notes                                    |
|-----------------------|------------------------------------------|
| OpenAI                | GPT-4o, GPT-5, o3, etc.                 |
| Anthropic             | Claude Sonnet 4, Claude Opus 4           |
| Google Vertex AI      | Gemini models                            |
| Amazon Bedrock        | AWS-hosted models                        |
| Azure OpenAI          | Azure-hosted OpenAI models               |
| Ollama                | Local models                             |
| LM Studio             | Local models                             |
| DeepSeek              | DeepSeek V4 Pro, etc.                    |
| Groq                  | High-speed inference                     |
| Cerebras              | Fast inference                           |
| Fireworks AI          | Serverless GPU inference                 |
| Together AI           | Open model hosting                       |
| OpenRouter            | Multi-provider routing                   |
| GitHub Copilot        | Use Copilot subscription                 |
| ChatGPT Plus/Pro      | Use existing OpenAI subscription         |
| GitLab Duo            | GitLab's AI platform                     |
| Cloudflare Workers AI | Edge-deployed models                     |
| NVIDIA                | Nemotron and hosted models               |
| Hugging Face          | Open models via HF                       |
| 302.AI, Cortecs,     | Many more regional providers             |
| MiniMax, Moonshot,    |                                          |
| xAI, Venice AI, etc. |                                          |

Plus **OpenCode Zen** — a curated list of tested and verified models, and **OpenCode Go** —
a low-cost subscription for popular models.

**Key difference:** OpenCode has dramatically broader model support. Anvil supports 6
specific backends; OpenCode supports 75+ providers through a standardized interface.
If you need a specific provider or want to leverage existing subscriptions (GitHub
Copilot, ChatGPT Plus), OpenCode is far more flexible.

---

## 6. Cost Optimization

### Anvil

Anvil includes a built-in **CostOptimizer** that:

- **Routes by complexity**: Simple tasks (e.g., formatting, lint fixes) are sent to
  local/free models. Complex tasks (e.g., architectural decisions, multi-file refactors)
  are routed to high-capability API models.
- **Tracks token usage**: Estimates cost per interaction and maintains a running total.
- **Budget awareness**: Can be configured with a per-session or per-project budget cap.
- **Automatic downshift**: If a task fails on a cheaper model, Anvil can escalate to
  a more capable model.

### OpenCode

OpenCode does not have built-in cost optimization. However:

- **Model selection**: You choose which model to use at any time (switch with `/models`).
- **Agent-specific models**: You can configure different models per agent (e.g., a cheap
  model for the Plan agent, a capable model for the Build agent).
  ```json
  {
    "agent": {
      "plan": { "model": "anthropic/claude-haiku-4-20250514" },
      "build": { "model": "anthropic/claude-sonnet-4-20250514" }
    }
  }
  ```
- **OpenCode Go**: A low-cost subscription plan for popular models.
- **OpenCode Zen**: Curated models with predictable pricing.
- **Max steps**: The `steps` config limits agentic iterations to control costs.
- **Local models**: Full Ollama / LM Studio support for zero-cost inference.

**Key difference:** Anvil has automatic cost routing built into the architecture.
OpenCode gives you manual control over model selection and agent configuration, plus
curated pricing plans, but doesn't automatically route by task complexity.

---

## 7. Ecosystem

### Anvil

Anvil is part of FableForge's ecosystem of **21 interconnected projects**:

| Project          | Purpose                                       |
|------------------|------------------------------------------------|
| VerifyLoop       | Iterative verification until tests pass        |
| AgentSwarm       | Multi-agent orchestration                      |
| BenchAgent        | Benchmarking harness for agents                |
| Anvil            | Core coding agent (this comparison)             |
| ...and 17 more   | Training pipelines, evaluation, recovery, etc. |

These projects share conventions, error categories, and the Plan→Execute→Verify→Recover
loop structure. They're designed to work together, creating a cohesive but opinionated
ecosystem.

### OpenCode

OpenCode's ecosystem is community-driven and extensible:

- **174K+ GitHub stars**, 900+ contributors, 13,000+ commits
- **7.5M+ monthly active developers**
- **75+ LLM providers** via Models.dev
- **MCP protocol support**: Connect any external service (Sentry, databases, APIs,
  Git providers, Context7, etc.)
- **Plugin system**: `opencode-plugin-*` packages extend functionality (e.g.,
  `opencode-helicone-session` for observability)
- **Skills system**: Hundreds of community-contributed skill definitions (SKILL.md files)
  for specialized workflows
- **IDE extensions**: VS Code, Neovim, and others
- **Desktop app**: macOS, Windows, Linux
- **SDK**: For building custom tools and integrations
- **Enterprise features**: Including SSO, audit logs, and policy enforcement

**Key difference:** Anvil has a tightly integrated but smaller ecosystem. OpenCode
has a massive, open community with extensive extensibility through MCP and plugins.

---

## 8. Training Pipeline

### Anvil

Anvil uses a **4-stage QLoRA training pipeline** fine-tuned on **210K+ real agent traces**:

1. **Stage 1 — Base model**: Start from a general-purpose code model.
2. **Stage 2 — Code instruction tuning**: Fine-tune on code instruction datasets.
3. **Stage 3 — Agent trace fine-tuning**: QLoRA on 210K+ traces from real agent sessions
   (planning, execution, verification, recovery).
4. **Stage 4 — Safety and alignment**: Additional alignment for safe, helpful outputs.

This produces a model specifically trained for the agentic loop — it knows how to plan,
execute, verify, and recover without requiring explicit prompting.

### OpenCode

OpenCode does **not** ship a fine-tuned model. Instead, it:

- Uses **any model from 75+ providers** via the AI SDK.
- Includes **OpenCode Zen**: A curated list of models that the OpenCode team has tested
  and verified to work well as coding agents.
- Uses **prompt engineering** (AGENTS.md, system prompts, skill definitions) to adapt
  general-purpose models to coding tasks.
- Relies on the **inherent capabilities** of the chosen model, not fine-tuning.

**Key difference:** Anvil is a fine-tuned model + agent framework. OpenCode is a
model-agnostic agent framework. Anvil's model is purpose-built; OpenCode's strength
is that it works with whichever model you prefer.

---

## 9. Daemon Mode

### Anvil

Anvil can run as an **HTTP daemon on port 8765**:

- Accepts tasks via REST API (`POST /task`)
- Returns results via HTTP responses
- Maintains a persistent agent session across requests
- Suitable for CI/CD integration, automated pipelines, and headless operation
- Can be started with `anvil --daemon` and kept running as a background service

This makes Anvil suitable for automated workflows where a coding agent needs to run
without human interaction — for example, fixing failing CI builds or running
scheduled code quality checks.

### OpenCode

OpenCode does not have a traditional daemon mode. However:

- **CLI mode**: OpenCode can be run non-interactively via `opencode run "prompt"`
  for single-task execution.
- **Go mode**: A headless mode for programmatic execution.
- **Server mode**: OpenCode has a server component that can be used for integration.
- **SDK**: The OpenCode SDK allows programmatic interaction.
- **MCP server**: OpenCode can act as an MCP server itself, allowing other tools to
  call into it.

OpenCode is primarily designed as an interactive tool (TUI or desktop app), but the
CLI, server, and SDK options provide paths for automation.

**Key difference:** Anvil has a built-in daemon mode for long-running, automated tasks.
OpenCode is interactive-first but provides CLI and server interfaces for automation.

---

## 10. Session Management

### Anvil

Anvil provides **full session history with recovery**:

- Every session is stored with complete message history, tool calls, and results.
- Sessions can be resumed after interruptions or crashes.
- The ErrorRecovery system uses session history to understand context when recovering.
- Session state is persisted to disk, allowing the agent to pick up where it left off.
- Sessions can be listed, inspected, and resumed from the command line.

### OpenCode

OpenCode provides session management through its TUI:

- **Session history**: All conversations are saved and can be browsed.
- **Share links**: Any session can be shared via a URL (`/share` command) for
  collaboration or debugging.
- **Undo/Redo**: Full undo/redo of changes made during a session.
- **Subagent sessions**: When subagents create child sessions, you can navigate between
  parent and child sessions with keyboard shortcuts.
- **Session titles**: Automatically generated by a background agent.
- **Session summaries**: Auto-generated by a compaction agent for long sessions.
- **Compaction agent**: A hidden system agent that compresses long contexts to avoid
  hitting context limits.

**Key difference:** Anvil focuses on crash recovery and resumability. OpenCode focuses
on collaboration (sharing) and context management (compaction). Both handle session
persistence, but with different priorities.

---

## 11. What Anvil Has That OpenCode Doesn't

| Feature                        | Description                                                    |
|--------------------------------|----------------------------------------------------------------|
| **Built-in VerifyPipeline**    | Architecturally enforced syntax, test, lint, and import checks after every step |
| **Built-in ErrorRecovery**     | 9 error categories with pattern-matched recovery strategies    |
| **CostOptimizer**             | Automatic complexity-based model routing (simple→local, complex→API) |
| **Fine-tuned model**           | QLoRA on 210K+ real agent traces, purpose-built for agentic coding |
| **Daemon mode**                | HTTP daemon on port 8765 for headless/CI operation              |
| **Structured PEVR loop**       | Plan→Execute→Verify→Recover is enforced, not optional           |
| **Tight ecosystem**             | 21 interconnected projects sharing conventions and patterns      |
| **Budget caps**                | Per-session and per-project budget limits                       |
| **Automatic retry with recovery** | Errors don't just fail; they trigger categorized recovery    |

---

## 12. What OpenCode Has That Anvil Doesn't

| Feature                        | Description                                                    |
|--------------------------------|----------------------------------------------------------------|
| **75+ LLM providers**          | Massive provider support through Models.dev                    |
| **MCP extensibility**           | Connect any external service as a tool (Sentry, databases, APIs, etc.) |
| **GitHub Copilot / ChatGPT subscription** | Use existing subscriptions, no extra API costs    |
| **Desktop app**                 | Native macOS, Windows, Linux application                        |
| **IDE extensions**              | VS Code and Neovim integration                                  |
| **LSP integration**             | (Experimental) Real go-to-definition, references, hover info    |
| **Subagent system**             | General, Explore, and Scout agents for specialized tasks        |
| **Agent customization**         | Create custom agents with specific prompts, models, and permissions |
| **Share links**                 | Share any session via URL for collaboration                     |
| **Web fetch/search**            | Built-in webfetch and websearch (via Exa AI)                   |
| **Skills system**                | Hundreds of community skill definitions                         |
| **Plugin ecosystem**             | Extend OpenCode with npm packages                              |
| **Plan mode**                   | Built-in read-only analysis agent (Tab to switch)              |
| **Undo/Redo**                   | Full undo/redo of changes per interaction                       |
| **Enterprise features**          | SSO, audit logs, policy enforcement                            |
| **174K+ stars, 900+ contributors** | Massive community and rapid development                   |
| **Cross-platform**              | Terminal, desktop, IDE, and web interfaces                     |
| **Permission system**            | Fine-grained `allow`/`ask`/`deny` per tool, per agent, per command |
| **Context compaction**           | Automatic context compression for long sessions                 |
| **Question tool**               | Built-in structured user interaction                            |
| **Custom tools**                | Define your own tools in the config                             |
| **OAuth for MCP**               | Automatic OAuth flow for MCP server authentication              |
| **OpenCode Zen**                | Curated, tested models with predictable pricing                 |

---

## 13. When to Use Anvil vs OpenCode

### Use Anvil When:

- **You need guaranteed verification.** If "always run tests before declaring done" is
  a hard requirement, Anvil's VerifyPipeline enforces this architecturally.
- **You need automated error recovery.** If your workflow involves long-running agents
  that must self-heal without human intervention, Anvil's ErrorRecovery is designed
  for this.
- **You're building CI/CD automation.** The daemon mode makes Anvil suitable for
  headless, automated pipelines.
- **Cost optimization is critical.** Anvil's CostOptimizer automatically routes simple
  tasks to cheaper models, reducing API spend without manual configuration.
- **You want a purpose-built model.** Anvil's fine-tuned model is trained specifically
  for the agentic coding loop.
- **You prefer opinionated defaults.** Anvil makes decisions for you (verification,
  recovery, cost routing) so you don't have to configure them.

### Use OpenCode When:

- **You want maximum model flexibility.** If you need to use a specific provider,
  local model, or existing subscription (Copilot, ChatGPT), OpenCode supports 75+.
- **You need MCP integrations.** If your workflow involves databases, APIs, Sentry,
  Git providers, or other services, MCP gives you plug-and-play extensibility.
- **You want an interactive coding partner.** OpenCode's TUI, desktop app, and IDE
  extensions make it a comfortable companion for day-to-day development.
- **You value community and ecosystem.** 174K stars, 900+ contributors, and hundreds
  of skills and plugins mean rapid development and diverse use cases.
- **You need collaboration features.** Share links, multi-session support, and
  subagent orchestration make OpenCode great for teams.
- **You want fine-grained control.** OpenCode's permission system lets you configure
  exactly what each agent can and cannot do, per tool, per agent, and per command.
- **You want to choose your own verification strategy.** If you prefer running tests
  manually, using a CI system, or defining custom verification in AGENTS.md, OpenCode
  gives you that flexibility.

---

## 14. Can They Work Together?

**Yes, absolutely.** Here are several patterns:

### Pattern 1: Anvil for CI, OpenCode for Daily Development

Use OpenCode as your interactive coding agent during development. When code is committed,
use Anvil's daemon mode in CI to verify tests pass, run lint checks, and automatically
fix failures.

```
Developer → OpenCode (interactive development) → Git push
                                           ↓
                         CI/CD → Anvil daemon (verify + auto-fix)
```

### Pattern 2: OpenCode for Exploration, Anvil for Execution

Use OpenCode's Explore and Scout agents to understand codebases and research solutions.
When you have a clear plan, hand off to Anvil for reliable, verified execution.

```
Developer → OpenCode Plan mode (analysis) → Plan document
                                              ↓
                              Anvil (verified execution)
```

### Pattern 3: Anvil's Verification as an OpenCode Skill

Define an Anvil-style verification workflow as an OpenCode skill (SKILL.md) that
instructs the agent to always run syntax checks, tests, and linting after changes.
This brings some of Anvil's verification discipline into OpenCode's flexible framework.

### Pattern 4: OpenCode MCP Server for Anvil

Run OpenCode as an MCP server and have Anvil call it for tasks that benefit from
OpenCode's broader tool set (web search, LSP intelligence, specific MCP integrations).

### Pattern 5: Hybrid Cost Optimization

Use Anvil's CostOptimizer for routine tasks, and switch to OpenCode with a powerful
model (Claude Sonnet 4, GPT-5) for complex architectural decisions that need the
broadest model capabilities.

---

## Summary Table

| Dimension             | Anvil                                    | OpenCode                                          |
|-----------------------|------------------------------------------|---------------------------------------------------|
| **Architecture**      | Plan→Execute→Verify→Recover (enforced)   | Agent-based (Build/Plan modes, subagents)         |
| **Built-in Tools**    | 7 (Bash, Read, Write, Edit, Grep, Glob, LS) | 13+ (Bash, Edit, Write, Read, Grep, Glob, LSP, apply_patch, skill, todowrite, webfetch, websearch, question) + MCP |
| **Verification**      | Built-in VerifyPipeline (auto)           | Manual / LLM-discretionary / AGENTS.md rules     |
| **Error Recovery**    | Built-in (9 categories, pattern-matched) | LLM self-correction + undo/redo                   |
| **Model Support**     | 6 backends                              | 75+ providers                                    |
| **Cost Optimization** | Built-in CostOptimizer (auto routing)    | Manual model selection + agent config + Zen/Go    |
| **Ecosystem**         | 21 FableForge projects                   | 174K stars, 900+ contributors, MCP, plugins       |
| **Training**          | QLoRA on 210K+ agent traces              | Model-agnostic (uses any provider's model)        |
| **Daemon Mode**       | HTTP daemon on port 8765                 | CLI/Server/SDK for automation                     |
| **Session Mgmt**      | Full history with crash recovery          | Share links, undo/redo, compaction                |
| **Extensibility**     | FableForge ecosystem only                | MCP, plugins, skills, custom tools                |
| **Desktop App**       | No                                       | Yes (macOS, Windows, Linux)                       |
| **IDE Integration**   | Terminal only                            | VS Code, Neovim, desktop, web                     |
| **Permissions**       | Not documented                           | Fine-grained per-tool, per-agent, per-command      |
| **Community**         | FableForge team                          | 7.5M+ monthly users, massive open-source community |

---

## The Bottom Line

**Anvil** is the right choice when you need *discipline* — enforced verification,
automatic error recovery, cost optimization, and a model trained specifically for
the agentic loop. It excels in CI/CD automation and production workflows where
reliability is non-negotiable.

**OpenCode** is the right choice when you need *flexibility* — 75+ model providers,
MCP extensibility, a massive community, interactive workflows, and fine-grained
control over what your agent can do. It excels as a daily coding companion and
as an extensible platform for custom workflows.

They are not competitors in the zero-sum sense. They solve different problems:
Anvil solves the *reliability* problem; OpenCode solves the *flexibility* problem.
Using them together gives you both.