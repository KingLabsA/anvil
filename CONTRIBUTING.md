# Contributing to FableForge

First off, thanks for taking the time to contribute! FableForge is an open-source ecosystem of 21 projects, and we welcome contributions of all kinds — bug fixes, features, docs, tests, and ideas.

## Quick Links

- [Code of Conduct](#code-of-conduct)
- [How to Contribute](#how-to-contribute)
- [Development Setup](#development-setup)
- [Running Tests](#running-tests)
- [Code Style](#code-style)
- [Adding New Projects](#adding-new-projects)
- [Reporting Issues](#reporting-issues)
- [Pull Request Process](#pull-request-process)

## Code of Conduct

Be respectful. Be constructive. We're all here to build great tooling for coding agents. Harassment, trolling, and unproductive negativity are not welcome.

## How to Contribute

1. **Fork** the repository on GitHub.
2. **Create a branch** from `main`:
   ```bash
   git checkout -b my-feature-name
   ```
3. **Make your changes** with clear, focused commits.
4. **Push** to your fork:
   ```bash
   git push origin my-feature-name
   ```
5. **Open a Pull Request** against the `main` branch of the FableForge repo.

### Commit Messages

Use clear, descriptive commit messages:

```
feat(anvil): add timeout support to shell execution
fix(error-recovery): handle malformed trace output
docs(verifyloop): update configuration reference
```

Prefix with `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, or `perf`. Scope with the project name in parentheses.

## Development Setup

Each project is a standalone Python package under its own directory. To set up a project for development:

```bash
# Clone the repo
git clone https://github.com/KingLabsA/anvil.git
cd fableforge

# Pick a project, e.g. anvil
cd anvil

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate

# Install in editable mode with dev dependencies
pip install -e ".[dev]"
```

### GPU / Training Dependencies

Some projects (like `fableforge-14b` and `trace-compiler`) have heavy ML dependencies (PyTorch, transformers, etc.) that require a GPU. These are optional:

```bash
# Core install (no GPU required)
pip install -e .

# Install with GPU/training dependencies
pip install -e ".[train]"
# or
pip install -e ".[gpu]"

# Everything
pip install -e ".[all]"
```

### Node.js Projects

`trace-viz` is a Next.js project and `agent-dev` is a VS Code extension:

```bash
# trace-viz
cd trace-viz
npm install
npm run dev

# agent-dev
cd agent-dev
npm install
npm run compile
```

## Running Tests

### Python Projects

Every Python project uses `pytest`:

```bash
cd <project>
pip install -e ".[dev]"
pytest
```

Run with coverage:

```bash
pytest --cov=<package_name> --cov-report=term-missing
```

Run a single test file:

```bash
pytest tests/test_specific.py
pytest tests/test_specific.py::TestClassName::test_method_name
```

### Node.js Projects

```bash
# trace-viz
cd trace-viz
npm test

# agent-dev
cd agent-dev
npm run test
```

## Code Style

We use **ruff** for Python linting and formatting across all projects.

### Format

```bash
# Check formatting
ruff format --check .

# Auto-format
ruff format .
```

### Lint

```bash
# Check for issues
ruff check .

# Auto-fix what's fixable
ruff check --fix .
```

### Configuration

Each project has `tool.ruff` configuration in `pyproject.toml`:

- **Target**: Python 3.10+
- **Line length**: 100 characters
- **Rules**: `E`, `F`, `I`, `N`, `W`, `UP` (errors, pyflakes, imports, naming, whitespace, upgrades)

### Type Hints

We encourage type hints. Run `mypy` where configured:

```bash
mypy src/
```

## Adding New Projects

New projects should follow this structure:

```
<project-name>/
├── LICENSE                  # MIT License
├── README.md               # Project description, usage, API
├── pyproject.toml           # Package config (see template below)
├── src/
│   └── <package_name>/
│       ├── __init__.py
│       ├── cli.py          # Click-based CLI (if applicable)
│       └── ...
├── tests/
│   ├── __init__.py
│   └── test_*.py
├── configs/                # Default configuration files
├── docs/                   # Extended documentation
└── examples/               # Usage examples
```

### pyproject.toml Template

```toml
[build-system]
requires = ["setuptools>=68.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "<package-name>"
version = "0.1.0"
description = "<one-line description>"
readme = "README.md"
license = {text = "MIT"}
requires-python = ">=3.10"
authors = [{name = "FableForge", email = "team@fableforge.ai"}]

dependencies = [
    "rich>=13.0",
    "click>=8.1",
    "pydantic>=2.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.4",
    "pytest-cov>=4.1",
    "ruff>=0.1",
    "mypy>=1.7",
]

[project.scripts]
<command-name> = "<package_name>.cli:main"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]

[tool.ruff]
target-version = "py310"
line-length = 100

[tool.ruff.lint]
select = ["E", "F", "I", "N", "W", "UP"]
```

### Checklist for New Projects

- [ ] `LICENSE` — MIT with "FableForge Contributors"
- [ ] `README.md` — Description, installation, usage, configuration, API reference
- [ ] `pyproject.toml` — Follows the template above
- [ ] `src/<package_name>/__init__.py` — Package init with `__version__`
- [ ] `tests/` — At least one test file
- [ ] `configs/` — Default config if applicable
- [ ] `docs/` — Extended docs if applicable
- [ ] `examples/` — Usage examples

## Reporting Issues

### Bug Reports

Open a [GitHub Issue](https://github.com/KingLabsA/anvil/issues) with:

1. **Project name** — Which of the 21 projects is affected?
2. **Version** — What version are you running?
3. **Environment** — OS, Python version, GPU/CPU?
4. **Steps to reproduce** — Minimal, deterministic steps.
5. **Expected behavior** — What should happen?
6. **Actual behavior** — What happened instead? Include full error output and tracebacks.
7. **Configuration** — Any non-default config or environment variables?

### Feature Requests

Open a GitHub Issue with the `enhancement` label. Describe:

1. **The problem** — What are you trying to do that isn't possible today?
2. **The proposed solution** — How should it work?
3. **Alternatives considered** — What other approaches did you think about?

## Pull Request Process

1. **One PR per feature/fix** — Keep PRs focused and reviewable.
2. **Update tests** — New code needs new tests. Bug fixes need regression tests.
3. **Update docs** — If you changed behavior, update the README or docs.
4. **Run the linter** — `ruff check . && ruff format --check .`
5. **CI must pass** — All tests and checks must be green.
6. **Review** — At least one maintainer review before merge.
7. **Squash merge** — We squash-merge feature branches into `main`.

### PR Title Format

```
<type>(<scope>): <description>
```

Examples:
- `feat(anvil): add retry-with-context to verification loop`
- `fix(error-recovery): handle None in trace parser`
- `docs(contributing): add GPU dependency section`

### What Happens After You Open a PR

1. Automated CI checks run (lint, type-check, test).
2. A maintainer reviews your code.
3. Feedback may be given — please address it promptly.
4. Once approved, a maintainer merges the PR.
5. Your changes will appear in the next release.

---

Thank you for contributing to FableForge! Every contribution — from typo fixes to major features — makes the ecosystem better for everyone.
