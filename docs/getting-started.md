# Getting Started with Anvil

This guide will help you get up and running with Anvil in under 5 minutes.

## Prerequisites

- Python 3.10 or higher
- pip (Python package manager)

## Installation

### Option 1: pip (Recommended)

```bash
pip install fableforge-anvil-agent
```

### Option 2: From Source

```bash
git clone https://github.com/KingLabsA/anvil.git
cd anvil
pip install -e .
```

## First Steps

### 1. Start the Server

```bash
anvil serve
```

This starts the Anvil server on `http://localhost:8000`.

### 2. Open the Web UI

Open your browser and navigate to:

```
http://localhost:8000
```

### 3. Ask Anvil Something

Try asking Anvil a question:

- "Explain this code"
- "Optimize this function"
- "Review this code for bugs"
- "Fix the issues in this code"

### 4. Use the CLI

You can also use Anvil from the command line:

```bash
# Ask a question
anvil ask "How do I sort a list in Python?"

# Analyze code
anvil analyze main.py

# Run a task
anvil run "Add error handling to all API endpoints"
```

## Next Steps

- Read the [Installation Guide](./installation.md) for detailed installation options
- Check the [Configuration Guide](./configuration.md) to customize Anvil
- Explore the [API Reference](./api-reference.md) for programmatic usage
- Learn about [Extensions](./extensions.md) to extend Anvil's capabilities

## Need Help?

- Check the [FAQ](./faq.md)
- Open an [issue on GitHub](https://github.com/KingLabsA/anvil/issues)
- Join our [Discord community](https://discord.gg/anvil)
