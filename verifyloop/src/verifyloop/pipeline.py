"""Full Pipeline: Plan → Execute → Verify → Recover loop."""

from __future__ import annotations

import time
from collections.abc import Callable, Coroutine
from datetime import UTC, datetime
from typing import Any

from verifyloop.executor import Executor
from verifyloop.memory import ConversationContext, InMemoryStore, MemoryStore
from verifyloop.models import (
    AgentRun,
    ExecuteStep,
    PipelineConfig,
    RunStatus,
    Step,
    StepType,
    TokenUsage,
)
from verifyloop.planner import PlanGenerator
from verifyloop.recoverer import Recoverer
from verifyloop.verifier import Verifier, VerifierConfig

CallbackFn = Callable[[str, dict[str, Any]], Coroutine[Any, Any, None]] | None


class AgentPipeline:
    def __init__(self, config: PipelineConfig | None = None) -> None:
        self.config = config or PipelineConfig()
        self._planner = PlanGenerator(
            model=self.config.model,
        )
        self._executor = Executor(
            working_dir=self.config.working_dir,
            sandbox=self.config.sandbox,
            sandbox_image=self.config.sandbox_image,
        )
        self._verifier = Verifier(
            VerifierConfig(
                verify_model=self.config.verify_model,
                confidence_threshold=self.config.confidence_threshold,
            )
        )
        self._recoverer = Recoverer(
            model=self.config.model,
            max_recovery_attempts=self.config.max_recovery_attempts,
        )
        self._memory: MemoryStore = InMemoryStore()
        self._context = ConversationContext(self._memory)
        self._callbacks: list[CallbackFn] = []

    @property
    def token_usage(self) -> TokenUsage:
        return (
            self._planner.token_usage
            .merge(self._verifier.token_usage)
            .merge(self._recoverer.token_usage)
        )

    def on_event(self, callback: CallbackFn) -> None:
        self._callbacks.append(callback)

    async def _emit(self, event: str, data: dict[str, Any]) -> None:
        for cb in self._callbacks:
            if cb is not None:
                try:
                    await cb(event, data)
                except Exception:
                    pass

    async def run(
        self,
        task: str,
        context: str = "",
        max_iterations: int | None = None,
    ) -> AgentRun:
        max_iters = max_iterations or self.config.max_iterations
        run = AgentRun(
            task=task,
            max_iterations=max_iters,
            status=RunStatus.PENDING,
        )
        start_time = time.monotonic()

        try:
            await self._emit("run_start", {"task": task})

            for iteration in range(1, max_iters + 1):
                run.iteration = iteration
                await self._emit("iteration_start", {"iteration": iteration})

                # Phase 1: Plan
                run.status = RunStatus.PLANNING
                await self._emit("phase_start", {"phase": "plan", "iteration": iteration})

                plan = await self._planner.generate_plan(task, context or self._context.build_context_string())
                run.add_step(Step(
                    step_type=StepType.PLAN,
                    content=plan.description,
                    confidence=0.7,
                ))
                await self._emit("phase_complete", {
                    "phase": "plan",
                    "description": plan.description,
                    "substeps": plan.substeps,
                })

                if self.config.dry_run:
                    run.status = RunStatus.COMPLETED
                    run.duration_seconds = time.monotonic() - start_time
                    return run

                # Phase 2: Execute
                run.status = RunStatus.EXECUTING
                await self._emit("phase_start", {"phase": "execute", "iteration": iteration})

                execute_steps: list[ExecuteStep] = []
                for substep in plan.substep_details:
                    if self.config.interactive:
                        proceed = await self._confirm_substep(substep)
                        if not proceed:
                            continue

                    step_result = await self._executor.execute(substep.tool, substep.arguments)
                    execute_steps.append(step_result)
                    run.add_step(Step(
                        step_type=StepType.EXECUTE,
                        content=f"{substep.tool}: {substep.description}",
                        tool_calls=[{"tool": substep.tool, "args": substep.arguments}],
                        confidence=1.0 if step_result.success else 0.0,
                    ))
                    await self._emit("step_complete", {
                        "tool": substep.tool,
                        "success": step_result.success,
                        "iteration": iteration,
                    })

                    if substep.tool == "read" and step_result.success:
                        self._context.add_file_context(
                            substep.arguments.get("file_path", ""), step_result.result
                        )

                # Phase 3: Verify
                run.status = RunStatus.VERIFYING
                await self._emit("phase_start", {"phase": "verify", "iteration": iteration})

                verification = await self._verifier.verify_code_edits(plan, execute_steps)
                run.add_step(Step(
                    step_type=StepType.VERIFY,
                    content=f"Passed: {verification.passed}, Confidence: {verification.confidence:.2f}",
                    confidence=verification.confidence,
                ))
                await self._emit("phase_complete", {
                    "phase": "verify",
                    "passed": verification.passed,
                    "confidence": verification.confidence,
                    "failures": verification.failures,
                })

                if verification.passed and verification.confidence >= self.config.confidence_threshold:
                    run.status = RunStatus.COMPLETED
                    run.duration_seconds = time.monotonic() - start_time
                    run.completed_at = datetime.now(UTC)
                    run.token_usage = self.token_usage
                    await self._emit("run_complete", {"status": "completed", "iterations": iteration})
                    return run

                # Phase 4: Recover (if verification failed)
                run.status = RunStatus.RECOVERING
                await self._emit("phase_start", {"phase": "recover", "iteration": iteration})

                failure_messages = verification.failures or ["Verification failed"]
                all_errors = "; ".join(failure_messages)

                for recovery_attempt in range(1, self.config.max_recovery_attempts + 1):
                    recovery = await self._recoverer.recover(
                        error=all_errors,
                        context=self._context.build_context_string(),
                        attempt=recovery_attempt,
                        failed_step=execute_steps[-1] if execute_steps else None,
                    )
                    run.add_step(Step(
                        step_type=StepType.RECOVER,
                        content=f"Recovery attempt {recovery_attempt}: {recovery.recovery_attempt}",
                        confidence=0.5,
                    ))
                    await self._emit("recovery_attempt", {
                        "attempt": recovery_attempt,
                        "type": recovery.recovery_type,
                        "description": recovery.recovery_attempt,
                    })

                    if recovery.patched_arguments:
                        tool = recovery.patched_arguments.get("tool", "bash")
                        args = recovery.patched_arguments.get("arguments", {})
                        recovery_exec = await self._executor.execute(tool, args)
                        execute_steps.append(recovery_exec)

                        # Re-verify after recovery
                        recheck = await self._verifier.verify_code_edits(plan, execute_steps)
                        if recheck.passed and recheck.confidence >= self.config.confidence_threshold:
                            run.status = RunStatus.COMPLETED
                            run.duration_seconds = time.monotonic() - start_time
                            run.completed_at = datetime.now(UTC)
                            run.token_usage = self.token_usage
                            await self._emit("run_complete", {"status": "completed_after_recovery"})
                            return run

                    if recovery.exhausted:
                        break

                # If we get here, recovery didn't fix it — loop back for next iteration
                context = self._context.build_context_string() + f"\nPrevious failures: {all_errors}"

            run.status = RunStatus.FAILED
            run.duration_seconds = time.monotonic() - start_time
            run.completed_at = datetime.now(UTC)
            run.token_usage = self.token_usage
            await self._emit("run_complete", {"status": "failed", "iterations": max_iters})
            return run

        except Exception as exc:
            run.status = RunStatus.FAILED
            run.duration_seconds = time.monotonic() - start_time
            run.completed_at = datetime.now(UTC)
            run.metadata["error"] = str(exc)
            run.token_usage = self.token_usage
            await self._emit("run_error", {"error": str(exc)})
            return run

    async def _confirm_substep(self, substep: Any) -> bool:
        try:
            from rich.console import Console
            from rich.prompt import Confirm

            console = Console()
            console.print(f"\n[bold blue]Step:[/] {substep.description}")
            console.print(f"  [dim]Tool: {substep.tool}[/dim]")
            console.print(f"  [dim]Args: {substep.arguments}[/dim]")
            return Confirm.ask("Execute this step?", default=True)
        except ImportError:
            return True
