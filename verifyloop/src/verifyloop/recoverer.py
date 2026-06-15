"""Recover phase: analyze errors and generate targeted recovery strategies."""

from __future__ import annotations

import re
from enum import Enum
from typing import Any

import litellm

from verifyloop.models import ExecuteStep, RecoverStep, TokenUsage


class RecoveryType(str, Enum):
    EDIT = "edit"
    CREATE = "create"
    RETRY = "retry"
    SIMPLIFY = "simplify"
    ANALYZE = "analyze"
    BASH = "bash"


RECOVERY_PATTERNS: list[tuple[re.Pattern[str], RecoveryType, str]] = [
    (re.compile(r"SyntaxError"), RecoveryType.EDIT, "Fix syntax error in the file"),
    (re.compile(r"IndentationError"), RecoveryType.EDIT, "Fix indentation in the file"),
    (re.compile(r"FileNotFoundError|No such file"), RecoveryType.CREATE, "Create the missing file or find correct path"),
    (re.compile(r"ModuleNotFoundError|ImportError"), RecoveryType.BASH, "Install missing module or fix import"),
    (re.compile(r"TimeoutError|timed out"), RecoveryType.SIMPLIFY, "Simplify the approach or increase timeout"),
    (re.compile(r"Permission denied"), RecoveryType.BASH, "Fix file permissions"),
    (re.compile(r"AssertionError|FAILED"), RecoveryType.ANALYZE, "Analyze test failure and fix the code"),
    (re.compile(r"TypeError"), RecoveryType.EDIT, "Fix type mismatch in the code"),
    (re.compile(r"NameError"), RecoveryType.EDIT, "Fix undefined variable or missing import"),
    (re.compile(r"KeyError"), RecoveryType.EDIT, "Fix missing key access or add default"),
    (re.compile(r"IndexError"), RecoveryType.EDIT, "Fix out-of-bounds access"),
    (re.compile(r"AttributeError"), RecoveryType.EDIT, "Fix attribute access on wrong type"),
    (re.compile(r"ConnectionError|ConnectionRefused"), RecoveryType.RETRY, "Retry the connection or check service availability"),
    (re.compile(r"old_content not found"), RecoveryType.EDIT, "Read the file first, then edit with exact content match"),
]

RECOVERY_SYSTEM_PROMPT = """You are a recovery agent. Given an error and its context, produce a JSON recovery plan:

{
  "recovery_type": "edit" | "create" | "retry" | "simplify" | "analyze",
  "recovery_attempt": "Description of what to do",
  "patched_arguments": {
    "tool": "tool_name",
    "arguments": {"arg": "value"}
  },
  "reasoning": "Why this recovery should work"
}

Be specific about exact file paths, line numbers, and content changes.
Respond ONLY with valid JSON, no markdown fences."""


class Recoverer:
    def __init__(
        self,
        model: str = "gpt-4o",
        max_recovery_attempts: int = 3,
        api_key: str | None = None,
        api_base: str | None = None,
    ) -> None:
        self.model = model
        self.max_recovery_attempts = max_recovery_attempts
        self.api_key = api_key
        self.api_base = api_base
        self._token_usage = TokenUsage()
        self._recovery_history: list[dict[str, Any]] = []

    @property
    def token_usage(self) -> TokenUsage:
        return self._token_usage

    async def recover(
        self,
        error: str,
        context: str = "",
        attempt: int = 1,
        failed_step: ExecuteStep | None = None,
    ) -> RecoverStep:
        if attempt > self.max_recovery_attempts:
            return RecoverStep(
                original_error=error,
                recovery_attempt="Max recovery attempts exhausted",
                recovery_type="analyze",
                success=False,
                attempt_number=attempt,
                max_attempts=self.max_recovery_attempts,
            )

        pattern_recovery = self._match_pattern_recovery(error)
        if pattern_recovery and attempt == 1:
            recovery = pattern_recovery
        else:
            recovery = await self._llm_recovery(error, context, attempt, failed_step)

        self._recovery_history.append({
            "error": error,
            "attempt": attempt,
            "recovery_type": recovery.recovery_type,
            "recovery_attempt": recovery.recovery_attempt,
        })

        return recovery

    def _match_pattern_recovery(self, error: str) -> RecoverStep | None:
        for pattern, recovery_type, description in RECOVERY_PATTERNS:
            if pattern.search(error):
                return RecoverStep(
                    original_error=error,
                    recovery_attempt=description,
                    recovery_type=recovery_type.value,
                    success=False,
                    attempt_number=1,
                    max_attempts=self.max_recovery_attempts,
                )
        return None

    async def _llm_recovery(
        self,
        error: str,
        context: str,
        attempt: int,
        failed_step: ExecuteStep | None = None,
    ) -> RecoverStep:
        messages = [{"role": "system", "content": RECOVERY_SYSTEM_PROMPT}]

        user_msg = f"Error: {error}\nAttempt: {attempt}/{self.max_recovery_attempts}"
        if context:
            user_msg += f"\n\nContext:\n{context}"
        if failed_step:
            user_msg += (
                f"\n\nFailed step tool: {failed_step.tool}"
                f"\nFailed step arguments: {failed_step.arguments}"
            )
            if failed_step.error:
                user_msg += f"\nFailed step error: {failed_step.error}"

        messages.append({"role": "user", "content": user_msg})

        try:
            kwargs: dict[str, Any] = {
                "model": self.model,
                "messages": messages,
                "temperature": 0.1,
                "max_tokens": 1024,
            }
            if self.api_key:
                kwargs["api_key"] = self.api_key
            if self.api_base:
                kwargs["api_base"] = self.api_base

            response = await litellm.acompletion(**kwargs)

            self._token_usage = self._token_usage.merge(
                TokenUsage(
                    prompt_tokens=response.usage.prompt_tokens if response.usage else 0,
                    completion_tokens=response.usage.completion_tokens if response.usage else 0,
                    total_tokens=response.usage.total_tokens if response.usage else 0,
                )
            )

            content = response.choices[0].message.content or "{}"
            content = re.sub(r"^```(?:json)?\s*", "", content.strip())
            content = re.sub(r"\s*```$", "", content.strip())

            import json
            data = json.loads(content)

            return RecoverStep(
                original_error=error,
                recovery_attempt=data.get("recovery_attempt", ""),
                recovery_type=data.get("recovery_type", "analyze"),
                success=False,
                attempt_number=attempt,
                max_attempts=self.max_recovery_attempts,
                patched_arguments=data.get("patched_arguments", {}),
            )
        except Exception:
            recovery = self._match_pattern_recovery(error)
            if recovery:
                recovery.attempt_number = attempt
                return recovery

            return RecoverStep(
                original_error=error,
                recovery_attempt=f"Generic recovery attempt {attempt}: retry with simpler approach",
                recovery_type="simplify",
                success=False,
                attempt_number=attempt,
                max_attempts=self.max_recovery_attempts,
            )

    def get_recovery_history(self) -> list[dict[str, Any]]:
        return list(self._recovery_history)

    def should_retry(self, error: str, attempt: int) -> bool:
        if attempt >= self.max_recovery_attempts:
            return False
        for pattern, _, _ in RECOVERY_PATTERNS:
            if pattern.search(error):
                return True
        return attempt < self.max_recovery_attempts
