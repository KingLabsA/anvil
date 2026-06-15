"""Task execution runner with sandboxing, timeouts, and token tracking."""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import time
from pathlib import Path

from bench_agent.models import Task, TaskCategory, TaskResult
from bench_agent.tasks import TASKS_BY_CATEGORY, ALL_TASKS


class TaskRunner:
    def __init__(
        self,
        sandbox_root: str | Path | None = None,
        per_turn_timeout: float = 30.0,
        total_timeout: float = 300.0,
    ) -> None:
        self.sandbox_root = Path(sandbox_root) if sandbox_root else Path(tempfile.mkdtemp())
        self.per_turn_timeout = per_turn_timeout
        self.total_timeout = total_timeout

    def _setup_sandbox(self, task: Task, sandbox_dir: Path) -> Path:
        sandbox_dir.mkdir(parents=True, exist_ok=True)
        for filename, content in task.initial_state.items():
            filepath = sandbox_dir / filename
            filepath.parent.mkdir(parents=True, exist_ok=True)
            filepath.write_text(content)
        return sandbox_dir

    def _cleanup_sandbox(self, sandbox_dir: Path) -> None:
        if sandbox_dir.exists():
            shutil.rmtree(sandbox_dir, ignore_errors=True)

    def _verify_task(self, task: Task, sandbox_dir: Path) -> bool:
        if not task.verification_script:
            return self._verify_expected_outcome(task, sandbox_dir)
        try:
            result = subprocess.run(
                ["python3", "-c", task.verification_script],
                cwd=str(sandbox_dir),
                capture_output=True,
                text=True,
                timeout=15,
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, Exception):
            return False

    def _verify_expected_outcome(self, task: Task, sandbox_dir: Path) -> bool:
        expected = task.expected_outcome
        if not expected:
            return True

        if "files" in expected:
            for filename, expected_content in expected["files"].items():
                filepath = sandbox_dir / filename
                if not filepath.exists():
                    return False
                actual = filepath.read_text()
                if actual.strip() != expected_content.strip():
                    return False

        if "file_exists" in expected:
            for filename in expected["file_exists"]:
                if not (sandbox_dir / filename).exists():
                    return False

        if "exit_code" in expected:
            pass

        return True

    def _count_tokens(self, text: str) -> int:
        return max(1, len(text) // 4)

    def run_task(
        self, task: Task, model: str, max_turns: int | None = None
    ) -> TaskResult:
        max_turns = max_turns or task.max_turns
        sandbox_dir = self.sandbox_root / f"task_{task.task_id}"
        errors: list[str] = []
        recovery_attempts = 0
        start_time = time.time()

        try:
            self._setup_sandbox(task, sandbox_dir)

            turns_used = 1
            tokens_used = 0

            prompt = f"You are a coding assistant. Complete this task:\n\n{task.description}\n\n"
            prompt += f"Working directory: {sandbox_dir}\n"
            prompt += f"Tools allowed: {', '.join(task.tools_required)}\n"
            prompt += f"Max turns: {max_turns}\n"

            if task.initial_state:
                prompt += "\nInitial files:\n"
                for fname, content in task.initial_state.items():
                    prompt += f"\n--- {fname} ---\n{content}\n"

            tokens_used += self._count_tokens(prompt)

            for turn in range(max_turns):
                turns_used = turn + 1
                if time.time() - start_time > self.total_timeout:
                    errors.append(f"Total timeout exceeded after {turns_used} turns")
                    break

            success = self._verify_task(task, sandbox_dir)

        except Exception as e:
            errors.append(str(e))
            success = False
            turns_used = 1
        finally:
            self._cleanup_sandbox(sandbox_dir)

        duration = time.time() - start_time

        return TaskResult(
            task_id=task.task_id,
            model=model,
            success=success,
            turns_used=turns_used,
            tokens_used=tokens_used,
            errors=errors,
            recovery_attempts=recovery_attempts,
            duration_seconds=round(duration, 2),
        )

    def run_benchmark(
        self,
        model: str,
        categories: list[TaskCategory] | None = None,
        num_tasks: int | None = None,
    ) -> list[TaskResult]:
        if categories:
            tasks: list[Task] = []
            for cat in categories:
                tasks.extend(TASKS_BY_CATEGORY.get(cat, []))
        else:
            tasks = list(ALL_TASKS)

        if num_tasks:
            tasks = tasks[:num_tasks]

        results: list[TaskResult] = []
        for task in tasks:
            result = self.run_task(task, model)
            results.append(result)

        return results
