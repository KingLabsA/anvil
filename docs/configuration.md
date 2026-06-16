# Configuration Guide

This guide covers all configuration options for Anvil.

## Configuration File

Anvil looks for configuration in the following locations (in order):

1. `./anvil.json` (current directory)
2. `~/.anvil/config.json` (home directory)
3. Environment variables

## Configuration Options

### Server Configuration

```json
{
  "server": {
    "host": "localhost",
    "port": 8000,
    "debug": false,
    "cors_origins": ["http://localhost:3000"]
  }
}
```

- `host`: Server host (default: `localhost`)
- `port`: Server port (default: `8000`)
- `debug`: Enable debug mode (default: `false`)
- `cors_origins`: Allowed CORS origins (default: `["*"]`)

### Model Configuration

```json
{
  "model": {
    "default": "local",
    "local": {
      "model_name": "fableforge-14b",
      "device": "auto"
    },
    "api": {
      "provider": "openai",
      "model": "gpt-4",
      "api_key": "your-api-key"
    }
  }
}
```

- `default`: Default model to use (`local` or `api`)
- `local.model_name`: Local model name
- `local.device`: Device to use (`cpu`, `cuda`, `mps`, or `auto`)
- `api.provider`: API provider (`openai`, `anthropic`)
- `api.model`: API model name
- `api.api_key`: API key (or use environment variable)

### Database Configuration

```json
{
  "database": {
    "url": "sqlite:///./anvil.db",
    "pool_size": 5,
    "max_overflow": 10
  }
}
```

- `url`: Database URL (default: `sqlite:///./anvil.db`)
- `pool_size`: Connection pool size (default: `5`)
- `max_overflow`: Max overflow connections (default: `10`)

### Verify Configuration

```json
{
  "verify": {
    "enabled": true,
    "auto_recover": true,
    "max_retries": 3,
    "timeout": 30
  }
}
```

- `enabled`: Enable verification (default: `true`)
- `auto_recover`: Enable auto-recovery (default: `true`)
- `max_retries`: Max recovery retries (default: `3`)
- `timeout`: Verification timeout in seconds (default: `30`)

### Logging Configuration

```json
{
  "logging": {
    "level": "INFO",
    "file": "anvil.log",
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  }
}
```

- `level`: Log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`)
- `file`: Log file path (optional)
- `format`: Log format string

## Environment Variables

You can also configure Anvil using environment variables:

```bash
# Server
export ANVIL_HOST=localhost
export ANVIL_PORT=8000
export ANVIL_DEBUG=false

# Model
export ANVIL_MODEL_DEFAULT=local
export ANVIL_LOCAL_MODEL=fableforge-14b
export ANVIL_API_PROVIDER=openai
export ANVIL_API_MODEL=gpt-4
export ANVIL_API_KEY=your-api-key

# Database
export ANVIL_DATABASE_URL=sqlite:///./anvil.db

# Logging
export ANVIL_LOG_LEVEL=INFO
```

## Example Configuration

Here's a complete example configuration:

```json
{
  "server": {
    "host": "localhost",
    "port": 8000,
    "debug": false
  },
  "model": {
    "default": "local",
    "local": {
      "model_name": "fableforge-14b",
      "device": "auto"
    }
  },
  "database": {
    "url": "sqlite:///./anvil.db"
  },
  "verify": {
    "enabled": true,
    "auto_recover": true,
    "max_retries": 3
  },
  "logging": {
    "level": "INFO"
  }
}
```

## Configuration Priority

Configuration is loaded in the following order (later sources override earlier ones):

1. Default values
2. `~/.anvil/config.json`
3. `./anvil.json`
4. Environment variables
5. Command-line arguments

## Next Steps

- Read the [API Reference](./api-reference.md)
- Explore the [CLI Reference](./cli-reference.md)
- Learn about [Extensions](./extensions.md)
