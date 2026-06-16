# FableForge Docs

Welcome to the FableForge documentation. FableForge is the open-source ecosystem for building **self-verified coding agents** that plan, execute, verify, and recover — stopping only when tests pass.

## Quick Links

| Project | Purpose |
|---------|---------|
| [Anvil](https://github.com/KingLabsA/anvil) | 🔨 Flagship self-verifying agent |
| [VerifyLoop](https://github.com/KingLabsA/verifyloop) | Plan → Execute → Verify loop |
| [Error Recovery](https://github.com/KingLabsA/error-recovery) | Failure classification & recovery |
| [ReasonCritic](https://github.com/KingLabsA/reason-critic) | Trained verification model |
| [Shell Whisperer](https://github.com/KingLabsA/shell-whisperer) | Shell/bash command model |
| [FableForge-14B](https://github.com/KingLabsA/fableforge-14b) | Code generation model |
| [Agent Swarm](https://github.com/KingLabsA/agent-swarm) | Multi-agent orchestration |
| [Agent Runtime](https://github.com/KingLabsA/agent-runtime) | Execution sandbox |
| [Agent Telemetry](https://github.com/KingLabsA/agent-telemetry) | Observability & tracing |

## Key Concepts

- **Verify Loop**: Anvil runs a continuous Plan → Execute → Verify → Recover cycle
- **Self-Verification**: Unlike other agents, Anvil uses a dedicated verification model to check its own output
- **Recovery**: When tests fail, Anvil diagnoses the root cause and applies targeted fixes

## Community

- [GitHub](https://github.com/KingLabsA) - Star, fork, and contribute
- [Discord](https://discord.gg/fableforge) - Get help and discuss agent design