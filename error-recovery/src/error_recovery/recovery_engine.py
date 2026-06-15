"""Core recovery engine: classify, match, inject, verify."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Protocol

from rich.console import Console

from error_recovery.error_classifier import ErrorClassifier
from error_recovery.models import ErrorCategory, ErrorPattern, ErrorRecoveryConfig, RecoveryResult
from error_recovery.pattern_matcher import PatternMatcher

logger = logging.getLogger(__name__)
console = Console()


class AgentProtocol(Protocol):
    def run(self, prompt: str, **kwargs: Any) -> str: ...


class LLMPromptInjector:
    def __init__(self, agent: AgentProtocol | Any) -> None:
        self._agent = agent

    async def inject_and_execute(
        self,
        original_prompt: str,
        recovery_prompt: str,
        context: str = "",
    ) -> str:
        combined = self._build_recovery_prompt(original_prompt, recovery_prompt, context)
        try:
            if asyncio.iscoroutinefunction(self._agent.run):
                result = await self._agent.run(combined)
            else:
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, self._agent.run, combined)
            return result if isinstance(result, str) else str(result)
        except Exception as exc:
            logger.warning("LLM injection failed: %s", exc)
            return f"__RECOVERY_FAILED__: {exc}"

    def _build_recovery_prompt(
        self, original: str, recovery: str, context: str
    ) -> str:
        parts = [
            "A previous attempt encountered an error. Apply the recovery strategy below.",
            "",
            f"RECOVERY STRATEGY:\n{recovery}",
        ]
        if context:
            parts.append(f"\nCONTEXT:\n{context}")
        parts.append(f"\nORIGINAL TASK:\n{original}")
        parts.append("\nImplement the recovery strategy and complete the original task.")
        return "\n".join(parts)


class ErrorRecoveryEngine:
    def __init__(
        self,
        config: ErrorRecoveryConfig | None = None,
        classifier: ErrorClassifier | None = None,
        pattern_matcher: PatternMatcher | None = None,
        agent: AgentProtocol | Any | None = None,
    ) -> None:
        self.config = config or ErrorRecoveryConfig()
        self.classifier = classifier or ErrorClassifier()
        self.pattern_matcher = pattern_matcher or PatternMatcher(
            similarity_threshold=self.config.similarity_threshold,
            model_name=self.config.model_name,
            pattern_data_dir=self.config.pattern_data_dir or "",
            top_k=self.config.top_k,
        )
        self._injector = LLMPromptInjector(agent) if agent else None
        self._agent = agent
        self._results: list[RecoveryResult] = []
        self._pattern_stats: dict[str, Any] = {}

        self.pattern_matcher.load_patterns()
        if self.pattern_matcher.pattern_count > 0:
            self.pattern_matcher.build_index()

    async def recover(
        self,
        error_message: str,
        context: str = "",
        tool_name: str = "",
        attempt: int = 1,
    ) -> RecoveryResult:
        start_time = time.monotonic()

        category, confidence = self.classifier.classify_with_confidence(error_message, tool_name)

        pattern_match = self._find_pattern(error_message, tool_name, category, attempt)

        if pattern_match:
            recovery_prompt = pattern_match.recovery_prompt
            pattern_id = pattern_match.id
            similarity = pattern_match.success_rate
        elif self.config.fallback_to_llm:
            recovery_prompt = self._generate_llm_fallback(error_message, category, context)
            pattern_id = None
            similarity = 0.0
        else:
            return RecoveryResult(
                original_error=error_message,
                error_category=category,
                recovery_prompt="",
                success=False,
                attempts=attempt,
                pattern_matched=None,
                pattern_similarity=0.0,
                elapsed_seconds=time.monotonic() - start_time,
            )

        if attempt < self.config.max_attempts and self._should_retry(error_message):
            backoff = self.config.backoff_seconds(attempt)
            logger.info("Backoff %.1fs before attempt %d", backoff, attempt)
            await asyncio.sleep(backoff)

        new_output = ""
        success = False

        if self._injector and self._agent:
            try:
                new_output = await self._injector.inject_and_execute(
                    context or error_message, recovery_prompt, context
                )
                success = not new_output.startswith("__RECOVERY_FAILED__")
            except Exception as exc:
                logger.warning("Recovery execution failed: %s", exc)
                new_output = str(exc)
                success = False

            if not success and attempt < self.config.max_attempts:
                result = await self.recover(
                    error_message=new_output if not success else error_message,
                    context=context,
                    tool_name=tool_name,
                    attempt=attempt + 1,
                )
                result.elapsed_seconds = time.monotonic() - start_time
                return result
        else:
            success = pattern_match is not None and pattern_match.success_rate > 0.5
            new_output = f"[Recovery strategy]: {recovery_prompt}" if recovery_prompt else ""

        result = RecoveryResult(
            original_error=error_message,
            error_category=category,
            recovery_prompt=recovery_prompt,
            new_output=new_output,
            success=success,
            attempts=attempt,
            pattern_matched=pattern_id,
            pattern_similarity=similarity,
            elapsed_seconds=time.monotonic() - start_time,
        )

        self._results.append(result)
        if pattern_id and self.config.track_success_rates:
            self._update_pattern_stats(pattern_id, success)

        return result

    def recover_sync(
        self,
        error_message: str,
        context: str = "",
        tool_name: str = "",
        attempt: int = 1,
    ) -> RecoveryResult:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(
                        asyncio.run,
                        self.recover(error_message, context, tool_name, attempt),
                    )
                    return future.result(timeout=120)
            return loop.run_until_complete(
                self.recover(error_message, context, tool_name, attempt)
            )
        except RuntimeError:
            return asyncio.run(self.recover(error_message, context, tool_name, attempt))

    def _find_pattern(
        self, error_message: str, tool_name: str, category: ErrorCategory, attempt: int
    ) -> ErrorPattern | None:
        try:
            matches = self.pattern_matcher.match(
                error_message, tool_name=tool_name, category=category
            )
            if matches:
                best_pattern, best_score = matches[0]
                effective_rate = best_pattern.success_rate * best_score
                if effective_rate >= 0.3 or attempt > 1:
                    return best_pattern
        except Exception as exc:
            logger.warning("Pattern matching failed: %s", exc)
        return None

    def _generate_llm_fallback(
        self, error_message: str, category: ErrorCategory, context: str
    ) -> str:
        category_hints: dict[ErrorCategory, str] = {
            ErrorCategory.BASH_ERROR: (
                "The command failed. Try: (1) check if the command exists, "
                "(2) check for typos, (3) verify the working directory, "
                "(4) try with full path, (5) check if dependencies are installed."
            ),
            ErrorCategory.EDIT_ERROR: (
                "The edit failed. Try: (1) verify the file path, "
                "(2) read the file first to get exact content, "
                "(3) use smaller context for the match, "
                "(4) check for whitespace differences."
            ),
            ErrorCategory.READ_ERROR: (
                "The file read failed. Try: (1) verify the file path, "
                "(2) check file permissions, (3) try an alternative path, "
                "(4) list the directory first."
            ),
            ErrorCategory.WRITE_ERROR: (
                "The write failed. Try: (1) check disk space, "
                "(2) verify directory permissions, (3) create parent directories first, "
                "(4) check if the file is locked."
            ),
            ErrorCategory.TEST_ERROR: (
                "The test failed. Try: (1) read the test output carefully, "
                "(2) fix the underlying code issue, (3) check if the test is flaky, "
                "(4) verify test dependencies are installed."
            ),
            ErrorCategory.NETWORK_ERROR: (
                "The network request failed. Try: (1) check connectivity, "
                "(2) retry with backoff, (3) use a different endpoint, "
                "(4) check DNS resolution, (5) verify proxy settings."
            ),
            ErrorCategory.IMPORT_ERROR: (
                "The import failed. Try: (1) install the missing package, "
                "(2) check the package name spelling, (3) verify the Python environment, "
                "(4) check version compatibility."
            ),
            ErrorCategory.TYPE_ERROR: (
                "A type error occurred. Try: (1) add null/None checks, "
                "(2) add type validation, (3) use defensive programming, "
                "(4) check the data structure shape."
            ),
        }
        hint = category_hints.get(category, "An unexpected error occurred. Analyze the error and try an alternative approach.")
        return f"{hint}\n\nError details: {error_message}"

    def _should_retry(self, error_message: str) -> bool:
        non_retryable = [
            "permission denied",
            "authentication failed",
            "invalid api key",
            "forbidden",
            "unauthorized",
        ]
        msg_lower = error_message.lower()
        return not any(nr in msg_lower for nr in non_retryable)

    def _update_pattern_stats(self, pattern_id: str, success: bool) -> None:
        if pattern_id not in self._pattern_stats:
            self._pattern_stats[pattern_id] = {"uses": 0, "successes": 0}
        self._pattern_stats[pattern_id]["uses"] += 1
        if success:
            self._pattern_stats[pattern_id]["successes"] += 1

    def get_stats(self) -> dict[str, Any]:
        total = len(self._results)
        successful = sum(1 for r in self._results if r.success)
        by_category: dict[str, int] = {}
        for r in self._results:
            cat = r.error_category.value
            by_category[cat] = by_category.get(cat, 0) + 1

        return {
            "total_recoveries": total,
            "successful_recoveries": successful,
            "success_rate": successful / total if total else 0.0,
            "by_category": by_category,
            "pattern_stats": dict(self._pattern_stats),
        }
