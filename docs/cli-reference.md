# CLI Reference

This document provides a complete reference for the Anvil CLI.

## Global Options

```bash
anvil [OPTIONS] COMMAND [ARGS]
```

- `--help`: Show help message
- `--version`: Show version
- `--config PATH`: Path to config file
- `--verbose`: Enable verbose output
- `--quiet`: Suppress output

## Commands

### serve

Start the Anvil server.

```bash
anvil serve [OPTIONS]
```

**Options:**

- `--host HOST`: Server host (default: `localhost`)
- `--port PORT`: Server port (default: `8000`)
- `--debug`: Enable debug mode

**Example:**

```bash
anvil serve --port 8080
```

### ask

Ask Anvil a question.

```bash
anvil ask [OPTIONS] QUESTION
```

**Options:**

- `--model MODEL`: Model to use (default: `local`)
- `--context FILE`: File to use as context

**Example:**

```bash
anvil ask "How do I sort a list in Python?"
anvil ask --context main.py "What does this code do?"
```

### run

Run a coding task.

```bash
anvil run [OPTIONS] TASK
```

**Options:**

- `--model MODEL`: Model to use (default: `local`)
- `--max-iterations N`: Maximum iterations (default: 20)
- `--output FILE`: Output file path

**Example:**

```bash
anvil run "Add error handling to all API endpoints"
anvil run --max-iterations 30 "Refactor the authentication module"
```

### analyze

Analyze code for issues.

```bash
anvil analyze [OPTIONS] FILE
```

**Options:**

- `--language LANG`: Programming language (default: auto-detect)
- `--output FILE`: Output file path
- `--format FORMAT`: Output format (`json`, `text`)

**Example:**

```bash
anvil analyze main.py
anvil analyze --format json main.py > analysis.json
```

### explain

Explain code.

```bash
anvil explain [OPTIONS] FILE
```

**Options:**

- `--language LANG`: Programming language (default: auto-detect)
- `--output FILE`: Output file path

**Example:**

```bash
anvil explain main.py
anvil explain --output explanation.txt complex_function.py
```

### optimize

Optimize code.

```bash
anvil optimize [OPTIONS] FILE
```

**Options:**

- `--language LANG`: Programming language (default: auto-detect)
- `--output FILE`: Output file path
- `--apply`: Apply optimizations to file

**Example:**

```bash
anvil optimize main.py
anvil optimize --apply slow_function.py
```

### review

Review code.

```bash
anvil review [OPTIONS] FILE
```

**Options:**

- `--language LANG`: Programming language (default: auto-detect)
- `--output FILE`: Output file path
- `--format FORMAT`: Output format (`json`, `text`)

**Example:**

```bash
anvil review main.py
anvil review --format json main.py > review.json
```

### fix

Fix issues in code.

```bash
anvil fix [OPTIONS] FILE
```

**Options:**

- `--language LANG`: Programming language (default: auto-detect)
- `--output FILE`: Output file path
- `--apply`: Apply fixes to file

**Example:**

```bash
anvil fix main.py
anvil fix --apply buggy_code.py
```

### config

Manage configuration.

```bash
anvil config [OPTIONS] COMMAND
```

**Commands:**

- `show`: Show current configuration
- `set KEY VALUE`: Set configuration value
- `get KEY`: Get configuration value
- `reset`: Reset to defaults

**Example:**

```bash
anvil config show
anvil config set model.default local
anvil config get model.default
anvil config reset
```

### extension

Manage extensions.

```bash
anvil extension [OPTIONS] COMMAND
```

**Commands:**

- `list`: List installed extensions
- `install NAME`: Install an extension
- `uninstall NAME`: Uninstall an extension
- `enable NAME`: Enable an extension
- `disable NAME`: Disable an extension

**Example:**

```bash
anvil extension list
anvil extension install my-extension
anvil extension uninstall my-extension
```

### version

Show version information.

```bash
anvil version
```

## Environment Variables

You can configure Anvil using environment variables:

- `ANVIL_HOST`: Server host
- `ANVIL_PORT`: Server port
- `ANVIL_MODEL_DEFAULT`: Default model
- `ANVIL_API_KEY`: API key
- `ANVIL_LOG_LEVEL`: Log level

## Examples

### Basic Usage

```bash
# Start the server
anvil serve

# Ask a question
anvil ask "How do I implement binary search?"

# Run a task
anvil run "Create a REST API with authentication"

# Analyze code
anvil analyze main.py

# Fix issues
anvil fix --apply main.py
```

### Advanced Usage

```bash
# Use a specific model
anvil ask --model api "Explain this algorithm"

# Limit iterations
anvil run --max-iterations 10 "Refactor this module"

# Output to file
anvil analyze --format json main.py > analysis.json

# Apply fixes automatically
anvil fix --apply buggy_code.py
```

### Scripting

```bash
# Analyze all Python files
for file in *.py; do
  anvil analyze "$file" > "${file%.py}.analysis.json"
done

# Fix all issues
for file in *.py; do
  anvil fix --apply "$file"
done
```

## Exit Codes

- `0`: Success
- `1`: Error
- `2`: Invalid arguments

## Next Steps

- Read the [API Reference](./api-reference.md)
- Learn about [Extensions](./extensions.md)
- Check out [Examples](./examples.md)
