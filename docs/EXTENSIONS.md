# Anvil Extension System

The Anvil extension system allows you to extend Anvil's functionality with custom tools, hooks, and integrations.

## Creating an Extension

### Structure

```
my-extension/
├── extension.json    # Extension metadata
└── main.py           # Extension code
```

### extension.json

```json
{
  "name": "my-extension",
  "version": "0.1.0",
  "description": "My custom Anvil extension",
  "author": "Your Name",
  "main": "main.py",
  "tools": ["my_tool"],
  "hooks": ["on_task_start", "on_task_complete"]
}
```

### main.py

```python
def my_tool(input_text: str) -> str:
    """Custom tool implementation."""
    return f"Processed: {input_text}"

def on_task_start(task: str) -> None:
    """Called when a task starts."""
    print(f"Starting task: {task}")

def on_task_complete(task: str, success: bool) -> None:
    """Called when a task completes."""
    print(f"Task completed: {success}")
```

## Available Hooks

- `on_task_start(task: str)` - Called when a task starts
- `on_task_complete(task: str, success: bool)` - Called when a task completes
- `on_file_change(file_path: str)` - Called when a file changes
- `on_verify_start(file_path: str)` - Called before verification
- `on_verify_complete(file_path: str, passed: bool)` - Called after verification

## Installing Extensions

### From Local Directory

```bash
anvil extensions install ./my-extension
```

### From Git Repository

```bash
anvil extensions install https://github.com/user/anvil-extension.git
```

## Managing Extensions

```bash
# List installed extensions
anvil extensions list

# Enable/disable extensions
anvil extensions enable my-extension
anvil extensions disable my-extension

# Uninstall extension
anvil extensions uninstall my-extension
```

## Using Extension Tools

Extension tools are automatically available in the Anvil CLI and web UI:

```bash
anvil tool my_tool "input text"
```

## Extension Examples

See `examples/extensions/` for example extensions:

- `example-extension` - Basic extension with tools and hooks

## Publishing Extensions

To publish your extension:

1. Create a GitHub repository
2. Add a README with installation instructions
3. Tag releases with semantic versioning
4. Share the repository URL

Users can install your extension with:

```bash
anvil extensions install https://github.com/username/my-extension.git
```

## Best Practices

1. **Version your extensions** - Use semantic versioning
2. **Document your tools** - Add docstrings to all tool functions
3. **Handle errors gracefully** - Catch exceptions and provide helpful messages
4. **Keep extensions focused** - Each extension should do one thing well
5. **Test your extensions** - Write tests for your tools and hooks

## API Reference

### ExtensionManager

```python
from anvil.extensions import ExtensionManager

manager = ExtensionManager()

# Install extension
manager.install("./my-extension")

# List extensions
extensions = manager.list_extensions()

# Get extension
ext = manager.get_extension("my-extension")

# Enable/disable
manager.enable("my-extension")
manager.disable("my-extension")

# Uninstall
manager.uninstall("my-extension")

# Call hooks
results = manager.call_hook("on_task_start", "task description")

# Get tool
tool = manager.get_tool("my_tool")
if tool:
    result = tool("input")
```

## Support

For help with extensions:

- GitHub Issues: https://github.com/KingLabsA/anvil/issues
- Documentation: https://github.com/KingLabsA/anvil#readme
