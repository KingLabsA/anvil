"""Drop-in middleware that wraps any agent with automatic error recovery."""

from __future__ import annotations

import asyncio
import functools
import logging
from collections.abc import Callable
from typing import Any, Protocol

from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.table import Table

from error_recovery.models import ErrorRecoveryConfig, ErrorTrace, RecoveryResult
from error_recovery.recovery_engine import ErrorRecoveryEngine

logger = logging.getLogger(__name__)
console = Console()


class AgentProtocol(Protocol):
    def run(self, prompt: str, **kwargs: Any) -> str: ...


class ToolCallError(Exception):
    def __init__(self, tool_name: str, error_message: str, context: str = "") -> None:
        self.tool_name = tool_name
        self.error_message = error_message
        self.context = context
        super().__init__(f"[{tool_name}] {error_message}")


class ErrorRecoveryMiddleware:
    def __init__(
        self,
        agent: Any | None = None,
        config: ErrorRecoveryConfig | None = None,
        engine: ErrorRecoveryEngine | None = None,
        on_recovery: Callable[[RecoveryResult], None] | None = None,
        on_failure: Callable[[str], None] | None = None,
        on_success: Callable[[str], None] | None = None,
    ) -> None:
        self.config = config or ErrorRecoveryConfig()
        self.agent = agent
        self.on_recovery = on_recovery
        self.on_failure = on_failure
        self.on_success = on_success

        if engine:
            self.engine = engine
        else:
            self.engine = ErrorRecoveryEngine(
                config=self.config,
                agent=agent,
            )

        self._trace = ErrorTrace()
        self._recovery_count = 0
        self._setup_logging()

    def _setup_logging(self) -> None:
        level = getattr(logging, self.config.log_level.upper(), logging.INFO)
        handler = RichHandler(console=console, show_path=False, show_time=False)
        handler.setLevel(level)
        logger.addHandler(handler)
        logger.setLevel(level)

    def wrap_tool_call(
        self,
        tool_func: Callable,
        tool_name: str | None = None,
    ) -> Callable:
        name = tool_name or getattr(tool_func, "__name__", "unknown")

        @functools.wraps(tool_func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                result = tool_func(*args, **kwargs)
                if self.on_success:
                    self.on_success(name)
                return result
            except Exception as exc:
                return self._handle_tool_error_sync(
                    tool_name=name,
                    error_message=str(exc),
                    context=str(args),
                    tool_func=tool_func,
                    args=args,
                    kwargs=kwargs,
                )

        @functools.wraps(tool_func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                result = await tool_func(*args, **kwargs)
                if self.on_success:
                    self.on_success(name)
                return result
            except Exception as exc:
                return await self._handle_tool_error_async(
                    tool_name=name,
                    error_message=str(exc),
                    context=str(args),
                    tool_func=tool_func,
                    args=args,
                    kwargs=kwargs,
                )

        if asyncio.iscoroutinefunction(tool_func):
            return async_wrapper
        return sync_wrapper

    def _handle_tool_error_sync(
        self,
        tool_name: str,
        error_message: str,
        context: str,
        tool_func: Callable,
        args: tuple,
        kwargs: dict,
    ) -> Any:
        logger.info("Interceptor caught error from %s: %s", tool_name, error_message[:100])

        result = self.engine.recover_sync(
            error_message=error_message,
            context=context,
            tool_name=tool_name,
        )

        self._trace.add_result(result)
        self._recovery_count += 1

        if self.on_recovery:
            self.on_recovery(result)

        self._log_recovery(result, tool_name)

        if result.success and result.recovery_prompt:
            logger.info("Injecting recovery prompt for %s (attempt %d)", tool_name, result.attempts)
            try:
                recovery_result = tool_func(*args, **kwargs)
                if self.on_success:
                    self.on_success(tool_name)
                return recovery_result
            except Exception as exc:
                logger.warning("Recovery retry also failed for %s: %s", tool_name, exc)
                if self.on_failure:
                    self.on_failure(str(exc))
                raise

        if result.recovery_prompt and not result.success:
            logger.info("Returning recovery strategy for %s", tool_name)
            return result.recovery_prompt

        if self.on_failure:
            self.on_failure(error_message)
        raise ToolCallError(tool_name, error_message, context)

    async def _handle_tool_error_async(
        self,
        tool_name: str,
        error_message: str,
        context: str,
        tool_func: Callable,
        args: tuple,
        kwargs: dict,
    ) -> Any:
        logger.info("Interceptor caught async error from %s: %s", tool_name, error_message[:100])

        result = await self.engine.recover(
            error_message=error_message,
            context=context,
            tool_name=tool_name,
        )

        self._trace.add_result(result)
        self._recovery_count += 1

        if self.on_recovery:
            self.on_recovery(result)

        self._log_recovery(result, tool_name)

        if result.success and result.recovery_prompt:
            try:
                recovery_result = await tool_func(*args, **kwargs)
                if self.on_success:
                    self.on_success(tool_name)
                return recovery_result
            except Exception as exc:
                logger.warning("Async recovery retry failed for %s: %s", tool_name, exc)
                if self.on_failure:
                    self.on_failure(str(exc))
                raise

        if result.recovery_prompt and not result.success:
            return result.recovery_prompt

        if self.on_failure:
            self.on_failure(error_message)
        raise ToolCallError(tool_name, error_message, context)

    def _log_recovery(self, result: RecoveryResult, tool_name: str) -> None:
        status = "[green]SUCCESS[/green]" if result.success else "[red]FAILED[/red]"
        console.print(
            Panel(
                f"[bold]{status}[/bold] | {tool_name}\n"
                f"Category: {result.error_category.value}\n"
                f"Attempts: {result.attempts}\n"
                f"Pattern: {result.pattern_matched or 'none'}\n"
                f"Similarity: {result.pattern_similarity:.2f}\n"
                f"Time: {result.elapsed_seconds:.2f}s",
                title=f"ErrorRecovery: {result.original_error[:60]}...",
                border_style="green" if result.success else "red",
            )
        )

    def get_trace(self) -> ErrorTrace:
        return self._trace

    @property
    def stats(self) -> dict[str, Any]:
        engine_stats = self.engine.get_stats()
        return {
            **engine_stats,
            "middleware_recoveries": self._recovery_count,
            "trace_errors": self._trace.total_errors,
            "trace_success_rate": self._trace.success_rate,
        }

    def print_summary(self) -> None:
        table = Table(title="ErrorRecovery Summary")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="white")

        stats = self.stats
        for key, val in stats.items():
            if isinstance(val, dict):
                for k, v in val.items():
                    table.add_row(f"{key}.{k}", str(v))
            else:
                table.add_row(key, str(val))

        console.print(table)


class ErrorRecovery:
    """Context manager for wrapping agent execution with error recovery."""

    def __init__(
        self,
        agent: Any,
        config: ErrorRecoveryConfig | None = None,
        on_recovery: Callable[[RecoveryResult], None] | None = None,
        on_failure: Callable[[str], None] | None = None,
    ) -> None:
        self.middleware = ErrorRecoveryMiddleware(
            agent=agent,
            config=config,
            on_recovery=on_recovery,
            on_failure=on_failure,
        )

    def __enter__(self) -> ErrorRecoveryMiddleware:
        return self.middleware

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> bool:
        if exc_val is not None:
            try:
                result = self.middleware.engine.recover_sync(
                    error_message=str(exc_val),
                    context="",
                    tool_name="unknown",
                )
                self.middleware._trace.add_result(result)
                self.middleware._log_recovery(result, "unknown")
                if result.success:
                    return True
            except Exception:
                pass
        self.middleware.print_summary()
        return False
