# Installation Guide

This guide covers all installation methods for Anvil.

## System Requirements

- **Python**: 3.10 or higher
- **Operating System**: macOS, Linux, or Windows
- **Memory**: 2GB RAM minimum (4GB recommended)
- **Disk Space**: 500MB for Anvil + dependencies

## Installation Methods

### Method 1: pip (Recommended)

The easiest way to install Anvil is via pip:

```bash
pip install fableforge-anvil-agent
```

#### With Optional Dependencies

Install with all optional features:

```bash
pip install fableforge-anvil-agent[all]
```

Install specific features:

```bash
# With local model support
pip install fableforge-anvil-agent[local]

# With API model support
pip install fableforge-anvil-agent[api]

# With TUI support
pip install fableforge-anvil-agent[tui]

# With development tools
pip install fableforge-anvil-agent[dev]
```

### Method 2: From Source

For the latest development version:

```bash
# Clone the repository
git clone https://github.com/KingLabsA/anvil.git
cd anvil

# Install in development mode
pip install -e ".[dev]"
```

### Method 3: Docker

Using Docker:

```bash
# Pull the image
docker pull fableforge/anvil:latest

# Run the container
docker run -p 8000:8000 fableforge/anvil:latest
```

Using Docker Compose:

```bash
# Clone the repository
git clone https://github.com/KingLabsA/anvil.git
cd anvil

# Start with Docker Compose
docker-compose up -d
```

### Method 4: Pre-built Binaries

Download pre-built binaries from the [releases page](https://github.com/KingLabsA/anvil/releases).

#### macOS

```bash
# Download
curl -L -o anvil https://github.com/KingLabsA/anvil/releases/latest/download/anvil-macos

# Make executable
chmod +x anvil

# Move to PATH
sudo mv anvil /usr/local/bin/
```

#### Linux

```bash
# Download
curl -L -o anvil https://github.com/KingLabsA/anvil/releases/latest/download/anvil-linux

# Make executable
chmod +x anvil

# Move to PATH
sudo mv anvil /usr/local/bin/
```

#### Windows

Download the `.exe` file from the releases page and add it to your PATH.

## Verify Installation

After installation, verify that Anvil is installed correctly:

```bash
anvil --version
```

You should see the version number printed.

## Configuration

After installation, you may want to configure Anvil. See the [Configuration Guide](./configuration.md) for details.

## Troubleshooting

### Python Version Issues

If you get an error about Python version, make sure you're using Python 3.10 or higher:

```bash
python --version
```

### Permission Errors

If you get permission errors, try installing with the `--user` flag:

```bash
pip install --user fableforge-anvil-agent
```

### Dependency Conflicts

If you have dependency conflicts, try installing in a virtual environment:

```bash
python -m venv anvil-env
source anvil-env/bin/activate  # On Windows: anvil-env\Scripts\activate
pip install fableforge-anvil-agent
```

## Next Steps

- Read the [Getting Started Guide](./getting-started.md)
- Configure Anvil with the [Configuration Guide](./configuration.md)
- Explore the [API Reference](./api-reference.md)
