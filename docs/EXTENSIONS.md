# Extensions Guide

This guide covers how to create and use Anvil extensions.

## What are Extensions?

Extensions allow you to extend Anvil's capabilities with custom tools, models, and features.

## Installing Extensions

### From Extension Registry

```bash
# List available extensions
anvil extension list

# Install an extension
anvil extension install my-extension

# Uninstall an extension
anvil extension uninstall my-extension
```

### From Source

```bash
# Clone the extension
git clone https://github.com/user/my-extension.git

# Install
anvil extension install ./my-extension
```

## Using Extensions

Once installed, extensions are automatically available in Anvil.

```bash
# Use an extension's tool
anvil run "Use my-custom-tool to analyze the code"
```

## Creating Extensions

### Extension Structure

```
my-extension/
├── manifest.json       # Extension manifest
├── tools/             # Custom tools
│   └── my_tool.py
├── models/            # Custom models
│   └── my_model.py
└── README.md          # Documentation
```

### Manifest File

Create a `manifest.json` file:

```json
{
  "name": "my-extension",
  "version": "1.0.0",
  "description": "My custom Anvil extension",
  "author": "Your Name",
  "tools": ["my_tool"],
  "models": ["my_model"]
}
```

### Creating a Tool

Create a tool in `tools/my_tool.py`:

```python
from anvil.extensions import Tool

class MyTool(Tool):
    name = "my_tool"
    description = "My custom tool"
    
    def execute(self, input_data):
        # Your tool logic here
        result = process(input_data)
        return result
```

### Creating a Model

Create a model in `models/my_model.py`:

```python
from anvil.extensions import Model

class MyModel(Model):
    name = "my_model"
    description = "My custom model"
    
    def generate(self, prompt):
        # Your model logic here
        response = process(prompt)
        return response
```

### Registering Components

In your extension's `__init__.py`:

```python
from anvil.extensions import register_tool, register_model
from .tools.my_tool import MyTool
from .models.my_model import MyModel

register_tool(MyTool)
register_model(MyModel)
```

## Extension API

### Tool API

```python
from anvil.extensions import Tool

class MyTool(Tool):
    name = "my_tool"
    description = "My custom tool"
    
    def execute(self, input_data):
        """
        Execute the tool.
        
        Args:
            input_data: Input data for the tool
            
        Returns:
            Result of the tool execution
        """
        return result
```

### Model API

```python
from anvil.extensions import Model

class MyModel(Model):
    name = "my_model"
    description = "My custom model"
    
    def generate(self, prompt, **kwargs):
        """
        Generate a response.
        
        Args:
            prompt: Input prompt
            **kwargs: Additional arguments
            
        Returns:
            Generated response
        """
        return response
```

## Publishing Extensions

### To Extension Registry

1. Create an account on the Anvil Extension Registry
2. Package your extension:

```bash
cd my-extension
zip -r my-extension.zip .
```

3. Upload to the registry

### To GitHub

1. Push your extension to GitHub
2. Users can install with:

```bash
anvil extension install github:user/my-extension
```

## Best Practices

### Tool Development

- Keep tools focused on a single responsibility
- Provide clear documentation
- Handle errors gracefully
- Return structured data when possible

### Model Development

- Document model capabilities and limitations
- Provide examples of good inputs
- Handle edge cases gracefully
- Consider performance implications

### Extension Development

- Follow the extension structure
- Provide comprehensive documentation
- Include examples
- Test thoroughly
- Version your extensions

## Examples

### Simple Tool

```python
from anvil.extensions import Tool

class WordCountTool(Tool):
    name = "word_count"
    description = "Count words in text"
    
    def execute(self, text):
        return len(text.split())
```

### API Tool

```python
import requests
from anvil.extensions import Tool

class WeatherTool(Tool):
    name = "weather"
    description = "Get weather for a location"
    
    def execute(self, location):
        response = requests.get(
            f"https://api.weather.com/{location}"
        )
        return response.json()
```

### Custom Model

```python
from transformers import pipeline
from anvil.extensions import Model

class CustomModel(Model):
    name = "custom_model"
    description = "My custom model"
    
    def __init__(self):
        self.pipeline = pipeline("text-generation", model="my-model")
    
    def generate(self, prompt):
        return self.pipeline(prompt)[0]["generated_text"]
```

## Troubleshooting

### Extension Not Loading

- Check the manifest file
- Verify the extension structure
- Check the logs for errors

### Tool Not Working

- Verify the tool is registered
- Check the tool implementation
- Check the logs for errors

### Model Not Working

- Verify the model is registered
- Check the model implementation
- Check the logs for errors

## Next Steps

- Read the [API Reference](./api-reference.md)
- Check out [Examples](./examples.md)
- Join the [Community](./community.md)
