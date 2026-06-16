# Contributing to Anvil

Thank you for your interest in contributing to Anvil! This guide will help you get started.

## Code of Conduct

Please read and follow our [Code of Conduct](./CODE_OF_CONDUCT.md).

## How to Contribute

### Reporting Bugs

1. Check if the bug is already reported in [Issues](https://github.com/KingLabsA/anvil/issues)
2. If not, create a new issue with:
   - Clear title and description
   - Steps to reproduce
   - Expected vs actual behavior
   - Environment details (OS, Python version, etc.)
   - Code samples if applicable

### Suggesting Features

1. Check if the feature is already requested in [Issues](https://github.com/KingLabsA/anvil/issues)
2. If not, create a new issue with:
   - Clear title and description
   - Use case and benefits
   - Implementation ideas (optional)

### Contributing Code

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/my-feature`
3. Make your changes
4. Write or update tests
5. Run tests: `pytest`
6. Run linter: `ruff check .`
7. Commit your changes: `git commit -m "Add my feature"`
8. Push to your fork: `git push origin feature/my-feature`
9. Create a Pull Request

### Code Style

- Follow PEP 8 for Python code
- Use type hints
- Write docstrings for functions and classes
- Keep functions focused and small
- Write clear commit messages

### Testing

- Write tests for new features
- Update tests for modified features
- Ensure all tests pass: `pytest`
- Aim for good test coverage

### Documentation

- Update documentation for new features
- Fix typos and improve clarity
- Add examples where helpful

## Development Setup

### Prerequisites

- Python 3.10+
- pip
- git

### Setup

```bash
# Clone your fork
git clone https://github.com/YOUR_USERNAME/anvil.git
cd anvil

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run linter
ruff check .
```

## Project Structure

```
anvil/
├── src/anvil/           # Source code
│   ├── core/           # Core functionality
│   ├── tools/          # Built-in tools
│   ├── models/         # Model integrations
│   ├── verify/         # Verification system
│   └── extensions/     # Extension system
├── tests/              # Tests
├── docs/               # Documentation
└── pyproject.toml      # Project configuration
```

## Pull Request Process

1. Ensure your code follows the code style
2. Ensure all tests pass
3. Update documentation if needed
4. Create a Pull Request with:
   - Clear title and description
   - Reference to related issues
   - Screenshots if applicable
5. Wait for review
6. Address feedback
7. Merge when approved

## Review Process

- All PRs require at least one review
- Address all review comments
- Ensure CI passes
- Maintain code quality

## Getting Help

- Check the [Documentation](./docs/)
- Ask in [Discussions](https://github.com/KingLabsA/anvil/discussions)
- Join our [Discord](https://discord.gg/anvil)

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

## Thank You!

Your contributions help make Anvil better for everyone. Thank you!
