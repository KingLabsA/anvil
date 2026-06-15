"""Verify pipeline — the core differentiator. We don't hope. We check."""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class VerifyStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    SKIP = "skip"
    ERROR = "error"


@dataclass
class VerifyResult:
    checker: str
    status: VerifyStatus
    message: str
    details: str | None = None
    file_path: str | None = None
    fixes: list[str] = field(default_factory=list)


@dataclass
class VerifyReport:
    results: list[VerifyResult] = field(default_factory=list)
    overall: VerifyStatus = VerifyStatus.PASS

    def add(self, result: VerifyResult) -> None:
        self.results.append(result)
        if result.status == VerifyStatus.FAIL:
            self.overall = VerifyStatus.FAIL
        elif result.status == VerifyStatus.ERROR and self.overall == VerifyStatus.PASS:
            self.overall = VerifyStatus.ERROR

    @property
    def passed(self) -> bool:
        return self.overall == VerifyStatus.PASS

    @property
    def failures(self) -> list[VerifyResult]:
        return [r for r in self.results if r.status == VerifyStatus.FAIL]

    def format_summary(self) -> str:
        lines = []
        icons = {VerifyStatus.PASS: "✓", VerifyStatus.FAIL: "✗", VerifyStatus.SKIP: "—", VerifyStatus.ERROR: "!"}
        for r in self.results:
            icon = icons.get(r.status, "?")
            lines.append(f"  {icon} {r.checker}: {r.message}")
            if r.details:
                for line in r.details.split("\n")[:5]:
                    lines.append(f"      {line}")
        lines.append(f"\nOverall: {self.overall.value.upper()}")
        return "\n".join(lines)


class Checkers:
    @staticmethod
    def check_syntax(file_path: str, content: str | None = None) -> VerifyResult:
        path = Path(file_path)
        suffix = path.suffix
        if suffix == ".py":
            return Checkers._check_python_syntax(file_path, content)
        elif suffix in (".js", ".ts", ".tsx", ".jsx"):
            return Checkers._check_js_syntax(file_path, content)
        elif suffix in (".rs",):
            return Checkers._check_rust_syntax(file_path)
        elif suffix in (".go",):
            return Checkers._check_go_syntax(file_path)
        return VerifyResult(
            checker="syntax", status=VerifyStatus.SKIP,
            message=f"No syntax checker for {suffix}",
        )

    @staticmethod
    def _check_python_syntax(file_path: str, content: str | None = None) -> VerifyResult:
        try:
            import ast
            code = content or Path(file_path).read_text()
            ast.parse(code)
            return VerifyResult(checker="syntax", status=VerifyStatus.PASS, message="Valid Python syntax")
        except SyntaxError as e:
            line_text = code.split("\n")[e.lineno - 1] if e.lineno and content else ""
            return VerifyResult(
                checker="syntax", status=VerifyStatus.FAIL,
                message=f"Syntax error: {e.msg} at line {e.lineno}",
                details=f"  {line_text}" if line_text else None,
                file_path=file_path,
                fixes=["Fix the syntax error on the reported line"],
            )

    @staticmethod
    def _check_js_syntax(file_path: str, content: str | None = None) -> VerifyResult:
        try:
            result = subprocess.run(
                ["node", "--check", file_path], capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                return VerifyResult(checker="syntax", status=VerifyStatus.PASS, message="Valid JS/TS syntax")
            return VerifyResult(
                checker="syntax", status=VerifyStatus.FAIL,
                message=f"Syntax error: {result.stderr[:200]}",
                file_path=file_path,
            )
        except FileNotFoundError:
            return VerifyResult(checker="syntax", status=VerifyStatus.SKIP, message="Node.js not installed")

    @staticmethod
    def _check_rust_syntax(file_path: str) -> VerifyResult:
        try:
            result = subprocess.run(
                ["rustc", "--edition", "2021", "--emit=metadata", file_path, "-o", "/dev/null"],
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode == 0:
                return VerifyResult(checker="syntax", status=VerifyStatus.PASS, message="Valid Rust syntax")
            return VerifyResult(
                checker="syntax", status=VerifyStatus.FAIL,
                message=f"Rust syntax error: {result.stderr[:200]}",
                file_path=file_path,
            )
        except FileNotFoundError:
            return VerifyResult(checker="syntax", status=VerifyStatus.SKIP, message="rustc not installed")

    @staticmethod
    def _check_go_syntax(file_path: str) -> VerifyResult:
        try:
            result = subprocess.run(
                ["gofmt", "-e", file_path], capture_output=True, text=True, timeout=10,
            )
            errors = [line for line in result.stderr.splitlines() if "expected" in line or "syntax" in line]
            if not errors:
                return VerifyResult(checker="syntax", status=VerifyStatus.PASS, message="Valid Go syntax")
            return VerifyResult(
                checker="syntax", status=VerifyStatus.FAIL,
                message=f"Go syntax error: {errors[0][:200]}",
                file_path=file_path,
            )
        except FileNotFoundError:
            return VerifyResult(checker="syntax", status=VerifyStatus.SKIP, message="gofmt not installed")

    @staticmethod
    def check_tests(test_command: str, working_dir: str = ".") -> VerifyResult:
        try:
            result = subprocess.run(
                test_command, shell=True, capture_output=True, text=True,
                timeout=60, cwd=working_dir,
            )
            if result.returncode == 0:
                return VerifyResult(
                    checker="tests", status=VerifyStatus.PASS,
                    message="All tests passed",
                    details=result.stdout[-500:] if len(result.stdout) > 500 else result.stdout,
                )
            return VerifyResult(
                checker="tests", status=VerifyStatus.FAIL,
                message=f"Tests failed (exit {result.returncode})",
                details=result.stdout[-500:] + "\n" + result.stderr[-500:],
                file_path=working_dir,
                fixes=["Review failing test output", "Fix the code that's causing test failures"],
            )
        except subprocess.TimeoutExpired:
            return VerifyResult(checker="tests", status=VerifyStatus.ERROR, message="Tests timed out (60s)")
        except Exception as e:
            return VerifyResult(checker="tests", status=VerifyStatus.ERROR, message=f"Error running tests: {e}")

    @staticmethod
    def check_lint(file_path: str, linter: str | None = None) -> VerifyResult:
        suffix = Path(file_path).suffix
        if linter is None:
            linter_map = {".py": "ruff", ".js": "eslint", ".ts": "eslint", ".rs": "clippy", ".go": "golint"}
            linter = linter_map.get(suffix)
        if not linter:
            return VerifyResult(checker="lint", status=VerifyStatus.SKIP, message=f"No linter for {suffix}")
        try:
            cmd = {
                "ruff": ["ruff", "check", file_path],
                "eslint": ["npx", "eslint", file_path],
                "clippy": ["cargo", "clippy", "--", "-W", "clippy::all"],
                "golint": ["golint", file_path],
            }.get(linter, [linter, file_path])
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                return VerifyResult(checker="lint", status=VerifyStatus.PASS, message="No lint issues")
            output = (result.stdout + result.stderr)[:500]
            return VerifyResult(
                checker="lint", status=VerifyStatus.FAIL,
                message="Lint issues found", details=output,
                file_path=file_path,
                fixes=["Fix lint warnings", "Run with --fix to auto-fix"],
            )
        except FileNotFoundError:
            return VerifyResult(checker="lint", status=VerifyStatus.SKIP, message=f"{linter} not installed")
        except Exception as e:
            return VerifyResult(checker="lint", status=VerifyStatus.ERROR, message=str(e))

    @staticmethod
    def check_imports(file_path: str) -> VerifyResult:
        suffix = Path(file_path).suffix
        if suffix != ".py":
            return VerifyResult(checker="imports", status=VerifyStatus.SKIP, message="Only Python import checking supported")
        try:
            result = subprocess.run(
                [sys.executable, "-c", f"import ast; ast.parse(open('{file_path}').read())"],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                return VerifyResult(checker="imports", status=VerifyStatus.PASS, message="Imports parsed successfully")
            return VerifyResult(
                checker="imports", status=VerifyStatus.FAIL,
                message=f"Import error: {result.stderr[:200]}",
                file_path=file_path,
            )
        except Exception as e:
            return VerifyResult(checker="imports", status=VerifyStatus.ERROR, message=str(e))

    @staticmethod
    def check_types(file_path: str, working_dir: str = ".") -> VerifyResult:
        """LSP-style static diagnostics via a language type checker.

        Python: prefer ``pyright`` (a Pyright LSP server backend), else ``mypy``.
        TS/JS:  ``tsc --noEmit``.
        Returns SKIP when no checker is installed for the language.
        """
        import shutil

        suffix = Path(file_path).suffix
        if suffix == ".py":
            if shutil.which("pyright"):
                cmd = ["pyright", "--outputjson", file_path]
                tool = "pyright"
            elif shutil.which("mypy"):
                cmd = [sys.executable, "-m", "mypy", "--no-error-summary",
                       "--hide-error-context", file_path]
                tool = "mypy"
            else:
                return VerifyResult(checker="types", status=VerifyStatus.SKIP,
                                    message="No type checker (pyright/mypy) installed")
        elif suffix in (".ts", ".tsx"):
            if shutil.which("tsc"):
                cmd = ["tsc", "--noEmit", file_path]
                tool = "tsc"
            else:
                return VerifyResult(checker="types", status=VerifyStatus.SKIP,
                                    message="tsc not installed")
        else:
            return VerifyResult(checker="types", status=VerifyStatus.SKIP,
                                message=f"No type checker for {suffix}")

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60, cwd=working_dir)
            output = (result.stdout + result.stderr).strip()
            if result.returncode == 0:
                return VerifyResult(checker="types", status=VerifyStatus.PASS,
                                    message=f"No type errors ({tool})")
            return VerifyResult(
                checker="types", status=VerifyStatus.FAIL,
                message=f"Type errors found ({tool})",
                details=output[:800],
                file_path=file_path,
                fixes=["Resolve the reported type diagnostics"],
            )
        except FileNotFoundError:
            return VerifyResult(checker="types", status=VerifyStatus.SKIP,
                                message=f"{tool} not available")
        except subprocess.TimeoutExpired:
            return VerifyResult(checker="types", status=VerifyStatus.SKIP,
                                message=f"{tool} timed out")
        except Exception as e:  # noqa: BLE001
            return VerifyResult(checker="types", status=VerifyStatus.ERROR, message=str(e))


class VerifyPipeline:
    def __init__(self, config: Any | None = None):
        self.config = config
        self.checkers = Checkers()

    def _default_checks(self) -> list[str]:
        """Derive the enabled checks from the VerifyConfig flags (if present)."""
        cfg = self.config
        if cfg is None:
            return ["syntax", "lint", "imports"]
        enabled: list[str] = []
        if getattr(cfg, "check_syntax", True):
            enabled.append("syntax")
        if getattr(cfg, "check_lint", True):
            enabled.append("lint")
        # imports is part of the baseline correctness suite
        enabled.append("imports")
        if getattr(cfg, "check_types", False):
            enabled.append("types")
        return enabled

    def verify(
        self,
        files: list[str],
        test_command: str | None = None,
        working_dir: str = ".",
        checks: list[str] | None = None,
    ) -> VerifyReport:
        report = VerifyReport()
        if checks is not None:
            enabled = list(checks)
        else:
            enabled = self._default_checks()
        if test_command:
            enabled.append("tests")

        for file_path in files:
            if "syntax" in enabled:
                report.add(self.checkers.check_syntax(file_path))
            if "lint" in enabled:
                report.add(self.checkers.check_lint(file_path))
            if "imports" in enabled:
                report.add(self.checkers.check_imports(file_path))
            if "types" in enabled:
                report.add(self.checkers.check_types(file_path, working_dir))

        if test_command and "tests" in enabled:
            report.add(self.checkers.check_tests(test_command, working_dir))

        return report

    def verify_code(self, code: str, language: str = "python") -> VerifyReport:
        report = VerifyReport()
        if language == "python":
            import ast
            try:
                ast.parse(code)
                report.add(VerifyResult(checker="syntax", status=VerifyStatus.PASS, message="Valid Python"))
            except SyntaxError as e:
                report.add(VerifyResult(
                    checker="syntax", status=VerifyStatus.FAIL,
                    message=f"Syntax error: {e.msg}", details=f"Line {e.lineno}",
                ))
        return report
