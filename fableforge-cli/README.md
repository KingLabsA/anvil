# FableForge CLI

Umbrella command-line interface for the [FableForge](https://kinglabsa.github.io/fableforge/) ecosystem.

## Install

```bash
pip install fableforge-cli
```

## Usage

```bash
# Show all 21 projects
fableforge list

# Show ecosystem status
fableforge status

# Run Anvil (self-verified coding agent)
fableforge anvil run "create a FastAPI hello world"

# List FableForge models
fableforge model list

# Generate with ShellWhisperer-1.5B
fableforge model generate "list all Python files recursively" --model fableforge-ai/ShellWhisperer-1.5B
```

## Commands

| Command | Description |
|---|---|
| `fableforge list` | List all ecosystem projects |
| `fableforge status` | Show ecosystem health |
| `fableforge run <project>` | Run a sub-project CLI |
| `fableforge anvil run <task>` | Dispatch to Anvil agent |
| `fableforge model list` | List FableForge HF models |
| `fableforge model generate` | Generate with a FableForge model |
| `fableforge install-all -e` | Install all packages in editable mode |
