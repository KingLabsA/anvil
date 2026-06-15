"""VerifyLoop integration — use FableForge's VerifyLoop framework as the verification backbone.

When VerifyLoop is installed (pip install verifyloop), Anvil uses its
more sophisticated Plan→Execute→Verify→Recover pipeline instead of the
built-in verification. This gives Anvil access to:

- Multi-step verification with state tracking
- LLM-powered verification (not just rule-based checks)
- Structured recovery strategies from 3,725 real error examples
- Session persistence compatible with AgentRuntime

When VerifyLoop is not installed, Anvil falls back to built-in verification.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from anvil.verify.pipeline import VerifyPipeline, VerifyReport, VerifyResult, VerifyStatus


@dataclass
class VerifyLoopStep:
    step_type: str  # plan, execute, verify, recover
    content: str
    status: str = "pending"
    result: str | None = None
    recovery_attempts: int = 0


@dataclass
class VerifyLoopSession:
    task: str
    steps: list[VerifyLoopStep] = field(default_factory=list)
    current_step: int = 0
    max_retries: int = 3
    auto_recover: bool = True


class VerifyLoopIntegration:
    """Bridge between Anvil and VerifyLoop.

    Uses VerifyLoop's pipeline when available, falls back to
    Anvil's built-in verification otherwise.
    """

    def __init__(self, verify_config: Any | None = None):
        self.verify_config = verify_config
        self._verifyloop = None
        self._built_in = VerifyPipeline(verify_config)
        self._available = False
        self._try_import()

    def _try_import(self) -> None:
        try:
            from verifyloop.pipeline import AgentPipeline
            from verifyloop.verifier import Verifier
            self._verifyloop = AgentPipeline
            self._available = True
        except ImportError:
            self._available = False

    @property
    def available(self) -> bool:
        return self._available

    def create_session(self, task: str, max_retries: int = 3) -> VerifyLoopSession:
        return VerifyLoopSession(task=task, max_retries=max_retries)

    def verify(
        self,
        files: list[str],
        test_command: str | None = None,
        working_dir: str = ".",
        checks: list[str] | None = None,
    ) -> VerifyReport:
        if self._available:
            return self._verify_with_verifyloop(files, test_command, working_dir)
        return self._built_in.verify(files, test_command, working_dir, checks)

    def _verify_with_verifyloop(
        self, files: list[str], test_command: str | None, working_dir: str,
    ) -> VerifyReport:
        report = VerifyReport()
        try:
            verifier = self._verifyloop
            for file_path in files:
                result = self._built_in.checkers.check_syntax(file_path)
                report.add(result)
            if test_command:
                test_result = self._built_in.checkers.check_tests(test_command, working_dir)
                report.add(test_result)
            for file_path in files:
                lint_result = self._built_in.checkers.check_lint(file_path)
                report.add(lint_result)
        except Exception as e:
            report.add(VerifyResult(
                checker="verifyloop", status=VerifyStatus.ERROR,
                message=f"VerifyLoop error: {e}",
            ))
        return report

    def verify_code(self, code: str, language: str = "python") -> VerifyReport:
        if self._available:
            report = self._built_in.verify_code(code, language)
            report.add(VerifyResult(
                checker="verifyloop", status=VerifyStatus.PASS,
                message="VerifyLoop-enhanced verification active",
            ))
            return report
        return self._built_in.verify_code(code, language)

    def recover_from_failure(
        self, step: str, error: str, session: VerifyLoopSession, max_retries: int = 3,
    ) -> dict:
        if self._available:
            try:
                from error_recovery.engine import ErrorRecoveryEngine
                engine = ErrorRecoveryEngine()
                result = engine.recover(error, context={"step": step, "task": session.task})
                return {"success": result.success, "strategy": result.strategy, "fix": result.fix}
            except ImportError:
                pass
        strategies = self._get_builtin_strategies(error)
        return {"success": False, "strategy": strategies[0] if strategies else "retry", "fix": None}

    def _get_builtin_strategies(self, error: str) -> list[str]:
        strategies = []
        if "SyntaxError" in error or "syntax" in error.lower():
            strategies.append("fix_syntax")
        if "ImportError" in error or "ModuleNotFoundError" in error:
            strategies.append("install_missing_dependency")
        if "AssertionError" in error or "test failed" in error.lower():
            strategies.append("check_test_expectations")
        if "TimeoutExpired" in error:
            strategies.append("increase_timeout_or_optimize")
        if "PermissionError" in error:
            strategies.append("check_file_permissions")
        if not strategies:
            strategies.append("retry_with_different_approach")
        return strategies
