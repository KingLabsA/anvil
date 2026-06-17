"""Analyze workspace context to determine agent and skill needs."""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class TechStackInfo:
    """Detected technology stack for a workspace."""

    languages: list[str] = field(default_factory=list)
    frameworks: list[str] = field(default_factory=list)
    build_tools: list[str] = field(default_factory=list)
    package_managers: list[str] = field(default_factory=list)
    test_frameworks: list[str] = field(default_factory=list)
    ci_cd: list[str] = field(default_factory=list)
    databases: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "languages": self.languages,
            "frameworks": self.frameworks,
            "build_tools": self.build_tools,
            "package_managers": self.package_managers,
            "test_frameworks": self.test_frameworks,
            "ci_cd": self.ci_cd,
            "databases": self.databases,
        }


@dataclass
class WorkspaceContext:
    """Full context analysis of a workspace."""

    tech_stack: TechStackInfo
    common_tasks: list[str] = field(default_factory=list)
    code_patterns: list[dict[str, Any]] = field(default_factory=list)
    dependencies: dict[str, list[str]] = field(default_factory=dict)
    test_coverage: float = 0.0
    project_type: str = "unknown"
    entry_points: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "tech_stack": self.tech_stack.to_dict(),
            "common_tasks": self.common_tasks,
            "code_patterns": self.code_patterns,
            "dependencies": self.dependencies,
            "test_coverage": self.test_coverage,
            "project_type": self.project_type,
            "entry_points": self.entry_points,
        }


_LANG_FILE_MAP: dict[str, list[str]] = {
    ".py": ["Python"],
    ".js": ["JavaScript"],
    ".ts": ["TypeScript"],
    ".tsx": ["TypeScript", "React"],
    ".jsx": ["JavaScript", "React"],
    ".go": ["Go"],
    ".rs": ["Rust"],
    ".java": ["Java"],
    ".kt": ["Kotlin"],
    ".swift": ["Swift"],
    ".rb": ["Ruby"],
    ".php": ["PHP"],
    ".cs": ["C#"],
    ".cpp": ["C++"],
    ".c": ["C"],
    ".h": ["C"],
    ".hpp": ["C++"],
}

_FRAMEWORK_INDICATORS: dict[str, list[tuple[str, str]]] = {
    "Next.js": [("next", "package.json"), ("next.config", "js|mjs|ts")],
    "React": [("react", "package.json"), ("react-dom", "package.json")],
    "Django": [("django", "requirements.txt|pyproject.toml|Pipfile")],
    "Flask": [("flask", "requirements.txt|pyproject.toml|Pipfile")],
    "FastAPI": [("fastapi", "requirements.txt|pyproject.toml|Pipfile")],
    "Spring Boot": [("spring-boot", "pom.xml|build.gradle")],
    "Express": [("express", "package.json")],
    "Vue.js": [("vue", "package.json")],
    "Svelte": [("svelte", "package.json")],
    "Angular": [("@angular/core", "package.json")],
    "Rails": [("rails", "Gemfile")],
    "Laravel": [("laravel/framework", "composer.json")],
}

_TEST_INDICATORS: dict[str, str] = {
    "pytest": "pytest.ini|pyproject.toml|conftest.py",
    "Jest": "jest.config",
    "Vitest": "vitest.config",
    "Mocha": "mocha",
    "Go Test": "_test.go",
    "JUnit": "junit",
    "RSpec": "spec/",
}


class ContextAnalyzer:
    """Analyze workspace context to determine agent and skill needs.

    Scans the codebase to detect tech stack, common tasks, code patterns,
    dependencies, and test coverage. The resulting context drives automatic
    agent and skill creation decisions.
    """

    def __init__(self) -> None:
        self._cache: dict[str, WorkspaceContext] = {}

    def analyze_workspace(self, workspace_path: str) -> WorkspaceContext:
        """Analyze workspace to understand full context.

        Parameters
        ----------
        workspace_path : str
            Root directory of the workspace to analyze.

        Returns
        -------
        WorkspaceContext
            Comprehensive context about the workspace.
        """
        root = Path(workspace_path)
        if not root.exists():
            raise FileNotFoundError(f"Workspace path does not exist: {workspace_path}")

        cache_key = str(root.resolve())
        if cache_key in self._cache:
            return self._cache[cache_key]

        tech_stack = self.detect_tech_stack(workspace_path)
        common_tasks = self.identify_common_tasks(workspace_path)
        code_patterns = self.extract_code_patterns(workspace_path)
        dependencies = self.analyze_dependencies(workspace_path)
        test_coverage = self.check_test_coverage(workspace_path)
        project_type = self._detect_project_type(tech_stack, root)
        entry_points = self._find_entry_points(root, tech_stack)

        context = WorkspaceContext(
            tech_stack=tech_stack,
            common_tasks=common_tasks,
            code_patterns=code_patterns,
            dependencies=dependencies,
            test_coverage=test_coverage,
            project_type=project_type,
            entry_points=entry_points,
        )

        self._cache[cache_key] = context
        return context

    def detect_tech_stack(self, workspace_path: str) -> TechStackInfo:
        """Detect technologies used in workspace.

        Scans for configuration files, dependency manifests, and source
        file extensions to build a picture of the tech stack.
        """
        root = Path(workspace_path)
        info = TechStackInfo()

        languages: set[str] = set()
        for ext, langs in _LANG_FILE_MAP.items():
            matches = list(root.rglob(f"*{ext}"))
            if matches:
                languages.update(langs)

        skip_dirs = {"node_modules", ".git", "__pycache__", ".venv", "venv", "dist", "build", ".next"}
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in skip_dirs]
            for fname in filenames:
                ext = Path(fname).suffix
                if ext in _LANG_FILE_MAP:
                    languages.update(_LANG_FILE_MAP[ext])

        info.languages = sorted(languages)
        info.frameworks = self._detect_frameworks(root)
        info.build_tools = self._detect_build_tools(root)
        info.package_managers = self._detect_package_managers(root)
        info.test_frameworks = self._detect_test_frameworks(root)
        info.ci_cd = self._detect_ci_cd(root)
        info.databases = self._detect_databases(root)

        return info

    def identify_common_tasks(self, workspace_path: str) -> list[str]:
        """Identify common tasks from git history, scripts, and CI configs.

        Analyzes commit messages, Makefile targets, npm scripts, and CI
        pipeline steps to determine what tasks are commonly performed.
        """
        root = Path(workspace_path)
        tasks: list[str] = []

        tasks.extend(self._tasks_from_git_log(root))
        tasks.extend(self._tasks_from_scripts(root))
        tasks.extend(self._tasks_from_package_json(root))
        tasks.extend(self._tasks_from_makefile(root))

        return list(dict.fromkeys(tasks))

    def extract_code_patterns(self, workspace_path: str) -> list[dict[str, Any]]:
        """Extract common code patterns from the workspace.

        Identifies repetitive structures, boilerplate, and potential
        anti-patterns that could benefit from dedicated agents or skills.
        """
        root = Path(workspace_path)
        patterns: list[dict[str, Any]] = []

        patterns.extend(self._find_repetitive_imports(root))
        patterns.extend(self._find_boilerplate(root))
        patterns.extend(self._find_error_handling_patterns(root))

        return patterns

    def analyze_dependencies(self, workspace_path: str) -> dict[str, list[str]]:
        """Analyze project dependencies by ecosystem.

        Returns a mapping of ecosystem (npm, pip, cargo, etc.) to
        the list of dependency names.
        """
        root = Path(workspace_path)
        deps: dict[str, list[str]] = {}

        pkg_json = root / "package.json"
        if pkg_json.exists():
            deps["npm"] = self._parse_package_json_deps(pkg_json)

        for req_file in ("requirements.txt", "Pipfile", "pyproject.toml"):
            req_path = root / req_file
            if req_path.exists():
                deps["pip"] = self._parse_python_deps(req_path)
                break

        cargo_toml = root / "Cargo.toml"
        if cargo_toml.exists():
            deps["cargo"] = self._parse_cargo_deps(cargo_toml)

        go_mod = root / "go.mod"
        if go_mod.exists():
            deps["go"] = self._parse_go_deps(go_mod)

        return deps

    def check_test_coverage(self, workspace_path: str) -> float:
        """Estimate test coverage by comparing test files to source files.

        Returns a ratio of test files to source files as a rough
        coverage indicator. For precise coverage, run the project's
        test suite with coverage instrumentation.
        """
        root = Path(workspace_path)
        skip_dirs = {"node_modules", ".git", "__pycache__", ".venv", "venv", "dist", "build"}

        source_count = 0
        test_count = 0

        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in skip_dirs]
            for fname in filenames:
                fpath = Path(dirpath) / fname
                ext = fpath.suffix
                if ext not in _LANG_FILE_MAP:
                    continue
                source_count += 1
                if self._is_test_file(fpath, root):
                    test_count += 1

        if source_count == 0:
            return 0.0
        return round(test_count / source_count, 3)

    # ── private helpers ────────────────────────────────────────────────

    def _detect_project_type(self, stack: TechStackInfo, root: Path) -> str:
        if (root / "lerna.json").exists() or (root / "pnpm-workspace.yaml").exists():
            return "monorepo"
        if any("Next.js" in f for f in stack.frameworks):
            return "nextjs-app"
        if any("Django" in f for f in stack.frameworks):
            return "django-app"
        if any("FastAPI" in f for f in stack.frameworks):
            return "fastapi-app"
        if any("Flask" in f for f in stack.frameworks):
            return "flask-app"
        if any("Spring Boot" in f for f in stack.frameworks):
            return "spring-boot-app"
        if any("React" in f for f in stack.frameworks):
            return "react-app"
        if any("Vue.js" in f for f in stack.frameworks):
            return "vue-app"
        if "Go" in stack.languages:
            return "go-app"
        if "Rust" in stack.languages:
            return "rust-app"
        return "generic"

    def _find_entry_points(self, root: Path, stack: TechStackInfo) -> list[str]:
        entries: list[str] = []
        candidates = [
            "main.py", "app.py", "server.py", "index.ts", "index.js",
            "src/main.ts", "src/index.ts", "src/app.ts", "src/server.ts",
            "cmd/main.go", "src/main.rs", "src/lib.rs",
        ]
        for c in candidates:
            if (root / c).exists():
                entries.append(c)
        return entries

    def _detect_frameworks(self, root: Path) -> list[str]:
        found: list[str] = []
        for framework, checks in _FRAMEWORK_INDICATORS.items():
            for indicator, file_pattern in checks:
                for pattern in file_pattern.split("|"):
                    for candidate in root.rglob(pattern):
                        if candidate.is_file():
                            try:
                                content = candidate.read_text(encoding="utf-8", errors="ignore")
                                if indicator in content:
                                    found.append(framework)
                                    break
                            except (OSError, PermissionError):
                                pass
                    else:
                        continue
                    break
        return sorted(set(found))

    def _detect_build_tools(self, root: Path) -> list[str]:
        tools: list[str] = []
        indicators = {
            "webpack": "webpack.config",
            "vite": "vite.config",
            "esbuild": None,
            "turbopack": None,
            "Make": "Makefile",
            "CMake": "CMakeLists.txt",
            "Gradle": "build.gradle",
            "Maven": "pom.xml",
            "Bazel": "BUILD",
            "Turborepo": "turbo.json",
        }
        for name, filename in indicators.items():
            if filename is None:
                pkg = root / "package.json"
                if pkg.exists():
                    try:
                        data = json.loads(pkg.read_text())
                        all_deps = {
                            **data.get("dependencies", {}),
                            **data.get("devDependencies", {}),
                        }
                        if name in all_deps:
                            tools.append(name)
                    except (json.JSONDecodeError, KeyError):
                        pass
            elif (root / filename).exists() or any(root.rglob(filename)):
                tools.append(name)
        return sorted(set(tools))

    def _detect_package_managers(self, root: Path) -> list[str]:
        managers: list[str] = []
        if (root / "package-lock.json").exists():
            managers.append("npm")
        if (root / "yarn.lock").exists():
            managers.append("yarn")
        if (root / "pnpm-lock.yaml").exists():
            managers.append("pnpm")
        if (root / "bun.lockb").exists():
            managers.append("bun")
        if (root / "requirements.txt").exists() or (root / "pyproject.toml").exists():
            managers.append("pip")
        if (root / "Pipfile").exists():
            managers.append("pipenv")
        if (root / "poetry.lock").exists():
            managers.append("poetry")
        if (root / "Cargo.lock").exists():
            managers.append("cargo")
        if (root / "go.sum").exists():
            managers.append("go-modules")
        return sorted(set(managers))

    def _detect_test_frameworks(self, root: Path) -> list[str]:
        found: list[str] = []
        for name, pattern in _TEST_INDICATORS.items():
            if "|" in pattern:
                for p in pattern.split("|"):
                    if any(root.rglob(p)):
                        found.append(name)
                        break
            elif pattern.endswith("/"):
                if any(root.rglob(pattern.rstrip("/"))):
                    found.append(name)
            elif any(root.rglob(f"*{pattern}*")):
                found.append(name)
        return sorted(set(found))

    def _detect_ci_cd(self, root: Path) -> list[str]:
        ci: list[str] = []
        if (root / ".github" / "workflows").exists():
            ci.append("GitHub Actions")
        if (root / ".gitlab-ci.yml").exists():
            ci.append("GitLab CI")
        if (root / "Jenkinsfile").exists():
            ci.append("Jenkins")
        if (root / ".circleci").exists():
            ci.append("CircleCI")
        if (root / "azure-pipelines.yml").exists():
            ci.append("Azure Pipelines")
        return ci

    def _detect_databases(self, root: Path) -> list[str]:
        dbs: list[str] = []
        indicators = {
            "PostgreSQL": ["postgresql", "psycopg", "pg", "prisma.*postgresql"],
            "MySQL": ["mysql", "pymysql", "sequelize.*mysql"],
            "SQLite": ["sqlite", "better-sqlite"],
            "MongoDB": ["mongodb", "mongoose", "pymongo"],
            "Redis": ["redis", "ioredis"],
            "DynamoDB": ["dynamodb", "@aws-sdk/client-dynamodb"],
        }
        search_files = ["package.json", "requirements.txt", "pyproject.toml",
                        "docker-compose.yml", "docker-compose.yaml"]
        content = ""
        for sf in search_files:
            fp = root / sf
            if fp.exists():
                try:
                    content += fp.read_text(encoding="utf-8", errors="ignore").lower()
                except (OSError, PermissionError):
                    pass

        for db_name, keywords in indicators.items():
            if any(kw.lower() in content for kw in keywords):
                dbs.append(db_name)
        return sorted(set(dbs))

    def _tasks_from_git_log(self, root: Path) -> list[str]:
        try:
            result = subprocess.run(
                ["git", "log", "--oneline", "-50"],
                capture_output=True, text=True, timeout=10, cwd=root,
            )
            if result.returncode != 0:
                return []
        except (subprocess.SubprocessError, FileNotFoundError):
            return []

        tasks: list[str] = []
        keywords = {
            "add": "feature", "fix": "bugfix", "update": "update",
            "refactor": "refactor", "test": "testing", "deploy": "deployment",
            "auth": "authentication", "api": "api", "ui": "ui",
            "migrate": "migration", "config": "configuration",
        }
        for line in result.stdout.strip().split("\n"):
            msg = line.split(" ", 1)[-1].lower() if " " in line else line.lower()
            for kw, category in keywords.items():
                if kw in msg:
                    tasks.append(f"{category}: {line.split(' ', 1)[-1][:100]}")
                    break
        return tasks[:20]

    def _tasks_from_scripts(self, root: Path) -> list[str]:
        tasks: list[str] = []
        scripts_dir = root / "scripts"
        if scripts_dir.exists() and scripts_dir.is_dir():
            for script in scripts_dir.iterdir():
                if script.is_file():
                    tasks.append(f"script: {script.name}")
        return tasks[:10]

    def _tasks_from_package_json(self, root: Path) -> list[str]:
        pkg = root / "package.json"
        if not pkg.exists():
            return []
        try:
            data = json.loads(pkg.read_text())
        except (json.JSONDecodeError, KeyError):
            return []
        scripts = data.get("scripts", {})
        return [f"npm run {name}" for name in scripts][:15]

    def _tasks_from_makefile(self, root: Path) -> list[str]:
        makefile = root / "Makefile"
        if not makefile.exists():
            return []
        tasks: list[str] = []
        try:
            content = makefile.read_text(encoding="utf-8", errors="ignore")
        except (OSError, PermissionError):
            return []
        for line in content.split("\n"):
            m = re.match(r"^([a-zA-Z_-]+)\s*:", line)
            if m:
                tasks.append(f"make {m.group(1)}")
        return tasks[:15]

    def _find_repetitive_imports(self, root: Path) -> list[dict[str, Any]]:
        patterns: list[dict[str, Any]] = []
        import_counts: dict[str, int] = {}
        skip_dirs = {"node_modules", ".git", "__pycache__", ".venv", "venv", "dist", "build"}
        count = 0

        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in skip_dirs]
            for fname in filenames:
                if not fname.endswith((".py", ".ts", ".tsx", ".js", ".jsx")):
                    continue
                fpath = Path(dirpath) / fname
                try:
                    content = fpath.read_text(encoding="utf-8", errors="ignore")
                except (OSError, PermissionError):
                    continue
                for line in content.split("\n")[:50]:
                    line = line.strip()
                    if line.startswith(("import ", "from ")) or line.startswith("const ") and "require(" in line:
                        import_counts[line] = import_counts.get(line, 0) + 1
                count += 1
                if count > 500:
                    break
            if count > 500:
                break

        for imp, cnt in sorted(import_counts.items(), key=lambda x: -x[1])[:10]:
            if cnt >= 3:
                patterns.append({
                    "type": "repetitive_import",
                    "pattern": imp,
                    "occurrences": cnt,
                    "suggestion": f"Consider a shared module for: {imp[:80]}",
                })
        return patterns

    def _find_boilerplate(self, root: Path) -> list[dict[str, Any]]:
        patterns: list[dict[str, Any]] = []
        boilerplate_indicators = {
            "error_handler": ["try {", "catch (", "except Exception", "except ("],
            "logging_setup": ["logging.getLogger", "console.log", "logger ="],
            "env_config": ["os.environ", "process.env", "dotenv"],
            "auth_middleware": ["authenticate", "authorize", "middleware"],
        }
        for pattern_name, indicators in boilerplate_indicators.items():
            count = 0
            skip_dirs = {"node_modules", ".git", "__pycache__"}
            for dirpath, dirnames, filenames in os.walk(root):
                dirnames[:] = [d for d in dirnames if d not in skip_dirs]
                for fname in filenames:
                    if not fname.endswith((".py", ".ts", ".tsx", ".js")):
                        continue
                    try:
                        content = (Path(dirpath) / fname).read_text(encoding="utf-8", errors="ignore")
                    except (OSError, PermissionError):
                        continue
                    if any(ind in content for ind in indicators):
                        count += 1
            if count >= 3:
                patterns.append({
                    "type": "boilerplate",
                    "pattern": pattern_name,
                    "occurrences": count,
                    "suggestion": f"Consider a skill for {pattern_name} ({count} occurrences)",
                })
        return patterns

    def _find_error_handling_patterns(self, root: Path) -> list[dict[str, Any]]:
        return []

    def _is_test_file(self, fpath: Path, root: Path) -> bool:
        name = fpath.name.lower()
        parts = fpath.relative_to(root).parts
        if any(d in ("tests", "test", "__tests__", "spec", "specs") for d in parts):
            return True
        if name.startswith("test_") or name.endswith("_test.py"):
            return True
        if name.endswith((".test.ts", ".test.tsx", ".test.js", ".spec.ts", ".spec.tsx", ".spec.js")):
            return True
        if name.endswith("_test.go"):
            return True
        return False

    def _parse_package_json_deps(self, path: Path) -> list[str]:
        try:
            data = json.loads(path.read_text())
            deps = list(data.get("dependencies", {}).keys())
            deps.extend(data.get("devDependencies", {}).keys())
            return sorted(set(deps))
        except (json.JSONDecodeError, KeyError):
            return []

    def _parse_python_deps(self, path: Path) -> list[str]:
        deps: list[str] = []
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except (OSError, PermissionError):
            return []

        if path.name == "requirements.txt":
            for line in content.split("\n"):
                line = line.strip()
                if line and not line.startswith("#") and not line.startswith("-"):
                    dep = re.split(r"[>=<!\[]", line)[0].strip()
                    if dep:
                        deps.append(dep)
        elif path.name == "Pipfile":
            in_deps = False
            for line in content.split("\n"):
                stripped = line.strip()
                if stripped == "[packages]" or stripped == "[dev-packages]":
                    in_deps = True
                    continue
                if stripped.startswith("["):
                    in_deps = False
                    continue
                if in_deps and "=" in stripped:
                    dep = stripped.split("=")[0].strip().strip('"')
                    if dep:
                        deps.append(dep)
        elif path.name == "pyproject.toml":
            in_deps = False
            for line in content.split("\n"):
                stripped = line.strip()
                if "dependencies" in stripped.lower() and stripped.endswith("]"):
                    in_deps = True
                    continue
                if in_deps:
                    if stripped == "]":
                        in_deps = False
                        continue
                    dep = stripped.strip('"').strip(",").strip()
                    dep = re.split(r"[>=<!]", dep)[0].strip()
                    if dep:
                        deps.append(dep)
        return sorted(set(deps))

    def _parse_cargo_deps(self, path: Path) -> list[str]:
        deps: list[str] = []
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except (OSError, PermissionError):
            return []
        in_deps = False
        for line in content.split("\n"):
            stripped = line.strip()
            if stripped == "[dependencies]" or stripped == "[dev-dependencies]":
                in_deps = True
                continue
            if stripped.startswith("["):
                in_deps = False
                continue
            if in_deps and "=" in stripped:
                dep = stripped.split("=")[0].strip()
                if dep:
                    deps.append(dep)
        return sorted(set(deps))

    def _parse_go_deps(self, path: Path) -> list[str]:
        deps: list[str] = []
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except (OSError, PermissionError):
            return []
        in_require = False
        for line in content.split("\n"):
            stripped = line.strip()
            if stripped == "require (":
                in_require = True
                continue
            if stripped == ")":
                in_require = False
                continue
            if in_require and stripped:
                dep = stripped.split()[0] if stripped.split() else ""
                if dep:
                    deps.append(dep)
            elif stripped.startswith("require ") and "(" not in stripped:
                dep = stripped.split()[1] if len(stripped.split()) > 1 else ""
                if dep:
                    deps.append(dep)
        return sorted(set(deps))
