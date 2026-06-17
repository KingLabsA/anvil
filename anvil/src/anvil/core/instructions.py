"""Persistent instructions system - load project-specific instructions from ANVIL.md files."""

from pathlib import Path
from typing import Optional


class InstructionsLoader:
    """Load and merge instructions from multiple ANVIL.md files."""

    def __init__(self, workspace_root: Path):
        self.workspace_root = workspace_root
        self.instructions_files = [
            'ANVIL.md',
            '.anvil/rules.md',
            '.anvil/instructions.md',
        ]

    def load_all(self) -> str:
        """Load all instruction files and merge them."""
        all_instructions = []

        for filename in self.instructions_files:
            path = self.workspace_root / filename
            if path.exists():
                all_instructions.append(f"# From {filename}\n{path.read_text()}")

        try:
            for subdir in self.workspace_root.iterdir():
                if subdir.is_dir() and not subdir.name.startswith('.'):
                    for filename in self.instructions_files:
                        path = subdir / filename
                        if path.exists():
                            all_instructions.append(
                                f"# From {subdir.name}/{filename}\n{path.read_text()}"
                            )
        except OSError:
            pass

        return "\n\n".join(all_instructions)

    def get_system_prompt_addition(self) -> str:
        """Get instructions formatted as system prompt addition."""
        instructions = self.load_all()
        if not instructions:
            return ""

        return (
            "\n## Project-Specific Instructions\n\n"
            "The following are project-specific instructions from ANVIL.md files. "
            "Follow these strictly:\n\n"
            f"{instructions}\n\n"
            "## End Project Instructions\n"
        )


class InstructionsWatcher:
    """Watch for changes to ANVIL.md files and reload."""

    def __init__(self, workspace_root: Path, loader: InstructionsLoader):
        self.workspace_root = workspace_root
        self.loader = loader
        self.last_modified: dict[str, float] = {}
        self._snapshot()

    def _snapshot(self) -> None:
        for filename in self.loader.instructions_files:
            path = self.workspace_root / filename
            if path.exists():
                self.last_modified[filename] = path.stat().st_mtime

    def check_for_changes(self) -> bool:
        """Check if any instruction files have changed."""
        changed = False

        for filename in self.loader.instructions_files:
            path = self.workspace_root / filename
            if path.exists():
                mtime = path.stat().st_mtime
                if filename not in self.last_modified or self.last_modified[filename] != mtime:
                    self.last_modified[filename] = mtime
                    changed = True

        return changed

    def reload_if_changed(self) -> Optional[str]:
        """Reload instructions if files have changed."""
        if self.check_for_changes():
            return self.loader.load_all()
        return None


class InstructionsTemplate:
    """Generate ANVIL.md template for new projects."""

    _TEMPLATES: dict[str, str] = {
        "general": """\
# Anvil Project Instructions

## Code Style
- Use consistent naming conventions
- Follow existing code patterns
- Add type hints to all functions
- Write docstrings for public APIs

## Testing
- Write tests for all new features
- Run tests before committing
- Maintain >80% code coverage

## Architecture
- Follow SOLID principles
- Keep functions small and focused
- Use dependency injection
- Prefer composition over inheritance

## Documentation
- Update README.md for user-facing changes
- Add inline comments for complex logic
- Keep docstrings up to date

## Git
- Write clear commit messages
- Use conventional commits format
- Keep commits atomic
- Don't commit secrets or credentials

## Security
- Validate all inputs
- Use parameterized queries
- Don't expose sensitive data in logs
- Follow OWASP guidelines
""",
        "python": """\
# Python Project Instructions

## Code Style
- Follow PEP 8
- Use type hints (PEP 484)
- Use f-strings for formatting
- Prefer list/dict comprehensions

## Imports
- Sort imports (isort)
- Group: stdlib, third-party, local
- Use absolute imports

## Testing
- Use pytest
- Use fixtures for setup
- Parametrize tests where possible
- Use pytest-cov for coverage

## Dependencies
- Pin versions in requirements.txt
- Use virtual environments
- Minimize dependencies
- Check for security vulnerabilities

## Async
- Use async/await for I/O-bound tasks
- Use asyncio.gather for concurrent operations
- Be careful with shared state
""",
        "typescript": """\
# TypeScript Project Instructions

## Code Style
- Use TypeScript strict mode
- Prefer interfaces over types
- Use const/let, never var
- Avoid any type

## React
- Use functional components
- Use hooks for state management
- Memoize expensive computations
- Use React.memo for pure components

## Testing
- Use Jest + React Testing Library
- Test behavior, not implementation
- Use describe/it blocks
- Mock external dependencies

## Build
- Use Vite or Next.js
- Optimize bundle size
- Use code splitting
- Enable tree shaking
""",
    }

    @classmethod
    def generate_template(cls, project_type: str = "general") -> str:
        """Generate a template ANVIL.md file."""
        return cls._TEMPLATES.get(project_type, cls._TEMPLATES["general"])

    @staticmethod
    def create_anvil_md(workspace_root: Path, project_type: str = "general") -> Path:
        """Create ANVIL.md file in workspace."""
        template = InstructionsTemplate.generate_template(project_type)
        anvil_md = workspace_root / "ANVIL.md"
        anvil_md.write_text(template)
        return anvil_md
