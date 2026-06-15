"""Project initialization — detect tech stack and generate .anvil/ directory.

Anvil's `init` command creates a project-aware configuration by:
1. Scanning the project directory to detect language, framework, test tools, etc.
2. Generating an AGENTS.md context file with detected conventions
3. Creating .anvil/ directory with agents/, commands/, rules/, config.json
4. Supporting both interactive and non-interactive modes
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm
from rich.table import Table

console = Console()

# ── Detection patterns ────────────────────────────────────────────────────

LANGUAGE_MARKERS: dict[str, list[str]] = {
    "python": ["pyproject.toml", "setup.py", "setup.cfg", "requirements.txt", "Pipfile", "poetry.lock", "uv.lock", ".python-version"],
    "javascript": ["package.json", ".nvmrc", ".node-version", "yarn.lock", "pnpm-lock.yaml", "bun.lockb"],
    "typescript": ["tsconfig.json", "tsconfig.*.json"],
    "go": ["go.mod", "go.sum"],
    "rust": ["Cargo.toml", "Cargo.lock"],
    "java": ["pom.xml", "build.gradle", "build.gradle.kts", ".gradle/"],
    "elixir": ["mix.exs"],
    "ruby": ["Gemfile", ".ruby-version"],
    "php": ["composer.json"],
    "csharp": [".csproj", ".sln", "Directory.Build.props"],
    "swift": ["Package.swift", "*.xcodeproj"],
    "kotlin": ["*.kt", "*.kts"],
}

FRAMEWORK_MARKERS: dict[str, list[str]] = {
    "django": ["manage.py", "django", "settings.py"],
    "flask": ["flask", "app.py"],
    "fastapi": ["fastapi", "FastAPI"],
    "starlette": ["starlette"],
    "sanic": ["sanic"],
    "react": ["react", "react-dom", "next.config"],
    "next.js": ["next.config", "next.config.js", "next.config.ts", "next.config.mjs"],
    "vue": ["vue", "nuxt.config"],
    "nuxt": ["nuxt.config"],
    "svelte": ["svelte.config", "svelte.config.js"],
    "express": ["express"],
    "nestjs": ["@nestjs/core", "nest-cli.json"],
    "spring-boot": ["spring-boot", "spring.boot"],
    "rails": ["config/routes.rb", "Gemfile"],
    "laravel": ["artisan", "composer.json"],
    "gin": ["gin-gonic", "gin"],
    "actix": ["actix-web"],
    "rocket": ["rocket"],
    "axum": ["axum"],
}

TEST_FRAMEWORK_MARKERS: dict[str, list[str]] = {
    "pytest": ["pytest.ini", "pyproject.toml:tool.pytest", "setup.cfg:tool:pytest", "conftest.py"],
    "unittest": ["unittest", "test_*.py"],
    "jest": ["jest.config", "package.json:jest"],
    "vitest": ["vitest.config", "package.json:vitest"],
    "mocha": ["mocha", ".mocharc"],
    "go-test": ["go.mod:*_test.go"],
    "cargo-test": ["Cargo.toml:tests"],
    "junit": ["junit", "test/**/*.java"],
    "rspec": ["spec", ".rspec", "rspec"],
    "playwright": ["playwright.config", "e2e/"],
    "cypress": ["cypress.json", "cypress/"],
}

LINTER_MARKERS: dict[str, list[str]] = {
    "ruff": ["ruff.toml", "pyproject.toml:tool.ruff", ".ruff_cache"],
    "flake8": [".flake8", "setup.cfg:flake8", "tox.ini:flake8"],
    "pylint": [".pylintrc", "pyproject.toml:tool.pylint"],
    "mypy": ["mypy.ini", "pyproject.toml:tool.mypy", ".mypy_cache"],
    "eslint": [".eslintrc", ".eslintrc.js", ".eslintrc.json", "eslint.config"],
    "prettier": [".prettierrc", ".prettierrc.js", ".prettierrc.json", "prettier.config"],
    "clippy": ["Cargo.toml:clippy"],
    "golint": ["golint"],
    "rubocop": [".rubocop.yml"],
    "stylelint": [".stylelintrc", "stylelint.config"],
}

PACKAGE_MANAGER_MARKERS: dict[str, list[str]] = {
    "pip": ["requirements.txt", "setup.py"],
    "poetry": ["poetry.lock", "pyproject.toml:tool.poetry"],
    "uv": ["uv.lock"],
    "pipenv": ["Pipfile", "Pipfile.lock"],
    "npm": ["package-lock.json"],
    "yarn": ["yarn.lock"],
    "pnpm": ["pnpm-lock.yaml"],
    "bun": ["bun.lockb"],
    "cargo": ["Cargo.toml"],
    "go-modules": ["go.mod"],
    "maven": ["pom.xml"],
    "gradle": ["build.gradle", "build.gradle.kts"],
}


@dataclass
class ProjectAnalysis:
    language: str = ""
    languages: list[str] = field(default_factory=list)
    framework: str = ""
    frameworks: list[str] = field(default_factory=list)
    test_framework: str = ""
    test_frameworks: list[str] = field(default_factory=list)
    linter: str = ""
    linters: list[str] = field(default_factory=list)
    package_manager: str = ""
    package_managers: list[str] = field(default_factory=list)
    has_git: bool = False
    has_docker: bool = False
    has_ci: bool = False
    ci_system: str = ""
    directory_structure: dict[str, list[str]] = field(default_factory=dict)
    key_files: list[str] = field(default_factory=list)
    project_description: str = ""
    project_name: str = ""
    version: str = ""


class ProjectAnalyzer:
    """Scan a project directory and detect language, framework, and tooling."""

    def __init__(self, project_dir: str | None = None):
        self.project_dir = Path(project_dir or os.getcwd()).resolve()

    def analyze(self) -> ProjectAnalysis:
        result = ProjectAnalysis()

        if not self.project_dir.exists():
            return result

        result.has_git = (self.project_dir / ".git").exists()
        result.has_docker = (self.project_dir / "Dockerfile").exists() or (self.project_dir / "docker-compose.yml").exists()
        result.has_ci, result.ci_system = self._detect_ci()

        result.languages = self._detect_languages()
        result.language = result.languages[0] if result.languages else ""

        result.frameworks = self._detect_frameworks()
        result.framework = result.frameworks[0] if result.frameworks else ""

        result.test_frameworks = self._detect_test_frameworks()
        result.test_framework = result.test_frameworks[0] if result.test_frameworks else ""

        result.linters = self._detect_linters()
        result.linter = result.linters[0] if result.linters else ""

        result.package_managers = self._detect_package_managers()
        result.package_manager = result.package_managers[0] if result.package_managers else ""

        result.directory_structure = self._detect_directory_structure()
        result.key_files = self._detect_key_files()
        result.project_name = self._detect_project_name()
        result.version = self._detect_version()
        result.project_description = self._detect_description()

        return result

    def _detect_languages(self) -> list[str]:
        detected = []
        for lang, markers in LANGUAGE_MARKERS.items():
            for marker in markers:
                if (self.project_dir / marker).exists():
                    detected.append(lang)
                    break
        if not detected:
            py_files = list(self.project_dir.glob("*.py"))
            if py_files:
                detected.append("python")
            ts_files = list(self.project_dir.glob("*.ts")) + list(self.project_dir.glob("*.tsx"))
            if ts_files:
                if "typescript" not in detected:
                    detected.append("typescript")
        return detected

    def _detect_frameworks(self) -> list[str]:
        detected = []
        for fw, markers in FRAMEWORK_MARKERS.items():
            for marker in markers:
                if (self.project_dir / marker).exists():
                    detected.append(fw)
                    break
            if fw not in detected:
                for marker in markers:
                    if ":" in marker:
                        file_part, key_part = marker.split(":", 1)
                        filepath = self.project_dir / file_part
                        if filepath.exists():
                            try:
                                content = filepath.read_text(encoding="utf-8", errors="replace")
                                if key_part in content:
                                    detected.append(fw)
                                    break
                            except Exception:
                                continue
        return detected

    def _detect_test_frameworks(self) -> list[str]:
        detected = []
        for tf, markers in TEST_FRAMEWORK_MARKERS.items():
            for marker in markers:
                if ":" in marker:
                    file_part, key_part = marker.split(":", 1)
                    filepath = self.project_dir / file_part
                    if filepath.exists():
                        try:
                            content = filepath.read_text(encoding="utf-8", errors="replace")
                            if key_part in content:
                                detected.append(tf)
                                break
                        except Exception:
                            continue
                else:
                    if (self.project_dir / marker).exists():
                        detected.append(tf)
                        break
        return detected

    def _detect_linters(self) -> list[str]:
        detected = []
        for linter, markers in LINTER_MARKERS.items():
            for marker in markers:
                if ":" in marker:
                    file_part, key_part = marker.split(":", 1)
                    filepath = self.project_dir / file_part
                    if filepath.exists():
                        try:
                            content = filepath.read_text(encoding="utf-8", errors="replace")
                            if key_part in content:
                                detected.append(linter)
                                break
                        except Exception:
                            continue
                else:
                    if (self.project_dir / marker).exists():
                        detected.append(linter)
                        break
        return detected

    def _detect_package_managers(self) -> list[str]:
        detected = []
        for pm, markers in PACKAGE_MANAGER_MARKERS.items():
            for marker in markers:
                if ":" in marker:
                    file_part, _ = marker.split(":", 1)
                    if (self.project_dir / file_part).exists():
                        filepath = self.project_dir / file_part
                        try:
                            content = filepath.read_text(encoding="utf-8", errors="replace")
                            key_part = marker.split(":", 1)[1]
                            if key_part in content:
                                detected.append(pm)
                                break
                        except Exception:
                            continue
                else:
                    if (self.project_dir / marker).exists():
                        detected.append(pm)
                        break
        return detected

    def _detect_ci(self) -> tuple[bool, str]:
        ci_systems = {
            "github_actions": [".github/workflows"],
            "gitlab_ci": [".gitlab-ci.yml"],
            "circleci": [".circleci"],
            "jenkins": ["Jenkinsfile"],
            "travis": [".travis.yml"],
        }
        for ci, markers in ci_systems.items():
            for marker in markers:
                if (self.project_dir / marker).exists():
                    return True, ci
        return False, ""

    def _detect_directory_structure(self) -> dict[str, list[str]]:
        structure: dict[str, list[str]] = {}
        common_dirs = [
            "src", "lib", "app", "api", "tests", "test", "spec",
            "docs", "scripts", "config", "configs", "migrations",
            "templates", "static", "public", "assets",
            "components", "pages", "routes", "models", "views",
            "controllers", "services", "utils", "helpers",
        ]
        for d in common_dirs:
            dir_path = self.project_dir / d
            if dir_path.is_dir():
                try:
                    structure[d] = [p.name for p in sorted(dir_path.iterdir())[:20]]
                except OSError:
                    structure[d] = []
        return structure

    def _detect_key_files(self) -> list[str]:
        key_file_patterns = [
            "pyproject.toml", "setup.py", "setup.cfg", "requirements.txt",
            "package.json", "tsconfig.json", "Cargo.toml", "go.mod",
            "Dockerfile", "docker-compose.yml", ".env.example",
            "README.md", "README.rst", "README.txt", "README",
            "Makefile", "justfile", "Taskfile.yml",
            ".flake8", ".eslintrc.js", ".prettierrc",
            "tox.ini", ".pre-commit-config.yaml",
            "CONTRIBUTING.md", "CHANGELOG.md", "LICENSE",
        ]
        found = []
        for pattern in key_file_patterns:
            if (self.project_dir / pattern).exists():
                found.append(pattern)
        return found

    def _detect_project_name(self) -> str:
        for config_file in ["pyproject.toml", "package.json", "Cargo.toml", "go.mod"]:
            filepath = self.project_dir / config_file
            if filepath.exists():
                try:
                    content = filepath.read_text(encoding="utf-8", errors="replace")
                    if config_file == "pyproject.toml":
                        match = re.search(r'name\s*=\s*["\']([^"\']+)["\']', content)
                        if match:
                            return match.group(1)
                    elif config_file == "package.json":
                        data = json.loads(content)
                        return data.get("name", self.project_dir.name)
                    elif config_file == "Cargo.toml":
                        match = re.search(r'name\s*=\s*"([^"]+)"', content)
                        if match:
                            return match.group(1)
                except Exception:
                    continue
        return self.project_dir.name

    def _detect_version(self) -> str:
        for config_file in ["pyproject.toml", "package.json", "Cargo.toml"]:
            filepath = self.project_dir / config_file
            if filepath.exists():
                try:
                    content = filepath.read_text(encoding="utf-8", errors="replace")
                    if config_file == "pyproject.toml":
                        match = re.search(r'version\s*=\s*["\']([^"\']+)["\']', content)
                        if match:
                            return match.group(1)
                    elif config_file == "package.json":
                        data = json.loads(content)
                        return data.get("version", "0.1.0")
                    elif config_file == "Cargo.toml":
                        match = re.search(r'version\s*=\s*"([^"]+)"', content)
                        if match:
                            return match.group(1)
                except Exception:
                    continue
        return "0.1.0"

    def _detect_description(self) -> str:
        for readme_name in ["README.md", "README.rst", "README.txt", "README"]:
            filepath = self.project_dir / readme_name
            if filepath.exists():
                try:
                    content = filepath.read_text(encoding="utf-8", errors="replace")
                    lines = content.strip().split("\n")
                    for line in lines:
                        line = line.strip().lstrip("#").strip()
                        if len(line) > 10 and len(line) < 300:
                            return line
                except Exception:
                    continue
        for config_file in ["pyproject.toml", "package.json"]:
            filepath = self.project_dir / config_file
            if filepath.exists():
                try:
                    content = filepath.read_text(encoding="utf-8", errors="replace")
                    if config_file == "pyproject.toml":
                        match = re.search(r'description\s*=\s*["\']([^"\']+)["\']', content)
                        if match:
                            return match.group(1)
                    elif config_file == "package.json":
                        data = json.loads(content)
                        desc = data.get("description", "")
                        if desc:
                            return desc
                except Exception:
                    continue
        return f"{self.project_dir.name} project"


class AgentsMdGenerator:
    """Generate AGENTS.md from project analysis."""

    def __init__(self, analysis: ProjectAnalysis, project_dir: str | None = None):
        self.analysis = analysis
        self.project_dir = Path(project_dir or os.getcwd()).resolve()

    def generate(self) -> str:
        sections = []

        sections.append(f"# {self.analysis.project_name}")
        sections.append("")
        sections.append(self.analysis.project_description)
        sections.append("")

        sections.append("## Tech Stack")
        sections.append("")
        if self.analysis.language:
            sections.append(f"- **Language**: {self.analysis.language}")
        if self.analysis.framework:
            sections.append(f"- **Framework**: {self.analysis.framework}")
        if self.analysis.test_framework:
            sections.append(f"- **Testing**: {self.analysis.test_framework}")
        if self.analysis.linter:
            sections.append(f"- **Linter**: {self.analysis.linter}")
        if self.analysis.package_manager:
            sections.append(f"- **Package Manager**: {self.analysis.package_manager}")
        if self.analysis.has_docker:
            sections.append("- **Containerization**: Docker")
        if self.analysis.has_ci:
            sections.append(f"- **CI/CD**: {self.analysis.ci_system}")
        sections.append("")

        sections.append("## Key Files")
        sections.append("")
        if self.analysis.key_files:
            for f in self.analysis.key_files[:15]:
                sections.append(f"- `{f}`")
        else:
            sections.append("- No key configuration files detected")
        sections.append("")

        sections.append("## Project Structure")
        sections.append("")
        if self.analysis.directory_structure:
            for dir_name, files in self.analysis.directory_structure.items():
                sections.append(f"- `{dir_name}/`: {', '.join(files[:5])}{'...' if len(files) > 5 else ''}")
        else:
            sections.append("- No standard directory structure detected")
        sections.append("")

        sections.append("## Commands")
        sections.append("")
        self._add_commands(sections)
        sections.append("")

        sections.append("## Coding Conventions")
        sections.append("")
        self._add_conventions(sections)
        sections.append("")

        sections.append("## Common Patterns")
        sections.append("")
        self._add_patterns(sections)
        sections.append("")

        sections.append("<!-- Generated by anvil init -->")
        return "\n".join(sections)

    def _add_commands(self, sections: list[str]):
        lang = self.analysis.language
        fw = self.analysis.framework

        if lang == "python":
            if fw == "django":
                sections.extend([
                    "- Run server: `python manage.py runserver`",
                    "- Run tests: `python manage.py test` or `pytest`",
                    "- Run linter: `ruff check .` or `flake8`",
                    "- Apply migrations: `python manage.py migrate`",
                ])
            elif fw == "fastapi":
                sections.extend([
                    "- Run server: `uvicorn app.main:app --reload`",
                    "- Run tests: `pytest`",
                    "- Run linter: `ruff check .`",
                    "- Type check: `mypy .`",
                ])
            else:
                sections.extend([
                    "- Run tests: `pytest`",
                    "- Run linter: `ruff check .` or `flake8`",
                    "- Type check: `mypy .`",
                    "- Format: `ruff format .` or `black .`",
                ])
        elif lang in ("javascript", "typescript"):
            sections.extend([
                "- Install: `npm install` or `yarn`",
                "- Run tests: `npm test` or `npm run test`",
                "- Run linter: `npm run lint`",
                "- Build: `npm run build`",
                "- Dev server: `npm run dev`",
            ])
        elif lang == "go":
            sections.extend([
                "- Run tests: `go test ./...`",
                "- Run linter: `golangci-lint run`",
                "- Build: `go build ./...`",
                "- Format: `gofmt -w .`",
            ])
        elif lang == "rust":
            sections.extend([
                "- Run tests: `cargo test`",
                "- Run linter: `cargo clippy`",
                "- Build: `cargo build`",
                "- Format: `cargo fmt`",
            ])
        elif lang == "java":
            sections.extend([
                "- Build: `mvn compile` or `./gradlew build`",
                "- Run tests: `mvn test` or `./gradlew test`",
                "- Run linter: `mvn checkstyle:check` or `./gradlew checkstyleMain`",
            ])
        else:
            sections.extend([
                "- Run tests: check project config for test commands",
                "- Run linter: check project config for lint commands",
            ])

    def _add_conventions(self, sections: list[str]):
        lang = self.analysis.language
        linter = self.analysis.linter

        if lang == "python":
            if linter == "ruff":
                sections.extend([
                    "- Follow PEP 8 style (enforced by ruff)",
                    "- Use type hints where possible",
                    "- Max line length: 100 (check ruff config)",
                    "- Use f-strings for string formatting",
                    "- Use pathlib for file paths",
                ])
            else:
                sections.extend([
                    "- Follow PEP 8 style guidelines",
                    "- Use type hints where possible",
                    "- Write docstrings for public functions",
                    "- Use f-strings for string formatting",
                ])
        elif lang in ("javascript", "typescript"):
            sections.extend([
                "- Use ESLint and Prettier for code style",
                "- Prefer const/let over var",
                "- Use TypeScript strict mode if available",
                "- Write JSDoc comments for public APIs",
            ])
        elif lang == "go":
            sections.extend([
                "- Follow Effective Go guidelines",
                "- Use gofmt for formatting",
                "- Write table-driven tests",
                "- Handle errors explicitly, don't panic",
            ])
        elif lang == "rust":
            sections.extend([
                "- Follow Rust API Guidelines",
                "- Use `cargo clippy` for linting",
                "- Use `Result` for error handling",
                "- Document public APIs with doc comments",
            ])
        else:
            sections.append("- Follow the project's existing code style")

    def _add_patterns(self, sections: list[str]):
        lang = self.analysis.language
        fw = self.analysis.framework

        if lang == "python":
            sections.extend([
                "- Use virtual environments for dependency isolation",
                "- Pin dependencies in requirements.txt or pyproject.toml",
                "- Use pytest fixtures for test setup",
                "- Prefer composition over inheritance",
            ])
        elif lang in ("javascript", "typescript"):
            sections.extend([
                "- Use npm/pnpm scripts for common tasks",
                "- Prefer async/await over .then() chains",
                "- Use environment variables for configuration",
                "- Follow the project's existing module pattern",
            ])


class ProjectInitializer:
    """Initialize an Anvil project by detecting the tech stack and creating config."""

    def __init__(self, project_dir: str | None = None, interactive: bool = True):
        self.project_dir = Path(project_dir or os.getcwd()).resolve()
        self.interactive = interactive
        self.analyzer = ProjectAnalyzer(str(self.project_dir))

    def init(self) -> dict[str, Any]:
        console.print(Panel(
            "[bold cyan]Anvil Project Initialization[/]\n"
            f"Scanning [bold]{self.project_dir}[/]...",
            border_style="cyan",
        ))

        analysis = self.analyzer.analyze()

        console.print()
        self._display_analysis(analysis)
        console.print()

        if self.interactive:
            if not Confirm.ask("Proceed with these settings?", default=True):
                console.print("[yellow]Initialization cancelled.[/]")
                return {"status": "cancelled"}

        self._create_anvil_directory(analysis)
        agents_md = self._generate_agents_md(analysis)
        self._write_agents_md(agents_md)
        config = self._generate_config(analysis)
        self._write_config(config)

        console.print()
        console.print(Panel(
            "[bold green]✓ Project initialized![/]\n\n"
            "Created:\n"
            "  • [cyan].anvil/config.json[/]\n"
            "  • [cyan].anvil/agents/[/]\n"
            "  • [cyan].anvil/commands/[/]\n"
            "  • [cyan].anvil/rules/[/]\n"
            "  • [cyan]AGENTS.md[/]\n\n"
            "Next steps:\n"
            "  1. Review [bold]AGENTS.md[/] and customize\n"
            "  2. Add custom agents to [bold].anvil/agents/[/]\n"
            "  3. Add custom commands to [bold].anvil/commands/[/]\n"
            "  4. Run [bold]anvil chat[/] to start coding",
            border_style="green",
        ))

        return {
            "status": "initialized",
            "analysis": asdict(analysis),
            "project_dir": str(self.project_dir),
        }

    def _display_analysis(self, analysis: ProjectAnalysis):
        table = Table(show_header=True, title="Detected Project Settings")
        table.add_column("Setting", style="cyan")
        table.add_column("Value", style="white")

        table.add_row("Project Name", analysis.project_name or self.project_dir.name)
        table.add_row("Language", ", ".join(analysis.languages) or "unknown")
        table.add_row("Framework", ", ".join(analysis.frameworks) or "none")
        table.add_row("Testing", ", ".join(analysis.test_frameworks) or "unknown")
        table.add_row("Linter", ", ".join(analysis.linters) or "unknown")
        table.add_row("Package Manager", ", ".join(analysis.package_managers) or "unknown")
        table.add_row("Git", "yes" if analysis.has_git else "no")
        table.add_row("Docker", "yes" if analysis.has_docker else "no")
        if analysis.has_ci:
            table.add_row("CI/CD", analysis.ci_system)

        if analysis.directory_structure:
            dirs = ", ".join(analysis.directory_structure.keys()[:8])
            table.add_row("Directories", dirs + ("..." if len(analysis.directory_structure) > 8 else ""))

        console.print(table)

    def _create_anvil_directory(self, analysis: ProjectAnalysis):
        anvil_dir = self.project_dir / ".anvil"
        agents_dir = anvil_dir / "agents"
        commands_dir = anvil_dir / "commands"
        rules_dir = anvil_dir / "rules"

        for d in [anvil_dir, agents_dir, commands_dir, rules_dir]:
            d.mkdir(parents=True, exist_ok=True)

        gitignore = anvil_dir / ".gitkeep"
        for d in [agents_dir, commands_dir, rules_dir]:
            (d / ".gitkeep").write_text("")

    def _generate_agents_md(self, analysis: ProjectAnalysis) -> str:
        generator = AgentsMdGenerator(analysis, str(self.project_dir))
        return generator.generate()

    def _write_agents_md(self, content: str):
        filepath = self.project_dir / "AGENTS.md"
        filepath.write_text(content, encoding="utf-8")

    def _generate_config(self, analysis: ProjectAnalysis) -> dict[str, Any]:
        config: dict[str, Any] = {
            "version": "0.2.0",
            "project_name": analysis.project_name,
            "project_root": str(self.project_dir),
        }

        config["model"] = {
            "model": "local",
            "api_base": None,
            "api_key": None,
            "max_tokens": 4096,
            "temperature": 0.2,
        }

        config["verify"] = {
            "enabled": True,
            "auto_recover": True,
            "max_retries": 3,
            "check_syntax": True,
            "check_tests": True,
            "check_lint": True,
            "check_types": analysis.language in ("python", "typescript"),
            "timeout_seconds": 30,
        }

        config["tools"] = {
            "allow_shell": True,
            "allow_file_write": True,
            "allow_file_read": True,
            "allow_web": False,
            "sandbox": False,
            "max_file_size_mb": 10,
            "working_dir": str(self.project_dir),
        }

        config["default_agent"] = "build"

        config["permission"] = {
            "*": "allow",
        }

        config["cost"] = {
            "max_cost_per_session_usd": 5.0,
            "max_cost_per_task_usd": 1.0,
            "warn_at_percent": 80,
            "route_by_complexity": True,
        }

        config["compaction"] = {
            "mode": "summarise",
            "reserved_tokens": 2048,
            "prune_threshold": 0.75,
        }

        test_cmd = self._detect_test_command(analysis)
        if test_cmd:
            config["test_command"] = test_cmd

        lint_cmd = self._detect_lint_command(analysis)
        if lint_cmd:
            config["lint_command"] = lint_cmd

        return config

    def _write_config(self, config: dict[str, Any]):
        filepath = self.project_dir / ".anvil" / "config.json"
        filepath.write_text(json.dumps(config, indent=2, default=str), encoding="utf-8")

    def _detect_test_command(self, analysis: ProjectAnalysis) -> str | None:
        lang = analysis.language
        fw = analysis.framework

        if lang == "python":
            if fw == "django":
                return "python manage.py test"
            return "pytest -x"
        elif lang in ("javascript", "typescript"):
            return "npm test"
        elif lang == "go":
            return "go test ./..."
        elif lang == "rust":
            return "cargo test"
        elif lang in ("java", "kotlin"):
            if (self.project_dir / "pom.xml").exists():
                return "mvn test"
            return "./gradlew test"
        return None

    def _detect_lint_command(self, analysis: ProjectAnalysis) -> str | None:
        linter = analysis.linter

        if linter == "ruff":
            return "ruff check ."
        elif linter == "flake8":
            return "flake8 ."
        elif linter == "pylint":
            return "pylint src/"
        elif linter == "mypy":
            return "mypy ."
        elif linter == "eslint":
            return "npx eslint ."
        elif linter == "clippy":
            return "cargo clippy"
        return None
