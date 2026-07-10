"""Task execution runner with sandboxing, model calling, and token tracking."""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Callable

from bench_agent.models import Task, TaskCategory, TaskResult
from bench_agent.tasks import TASKS_BY_CATEGORY, ALL_TASKS


ModelFn = Callable[[str], str]


class TaskRunner:
    def __init__(
        self,
        sandbox_root: str | Path | None = None,
        per_turn_timeout: float = 30.0,
        total_timeout: float = 300.0,
        model_fn: ModelFn | None = None,
    ) -> None:
        self.sandbox_root = Path(sandbox_root) if sandbox_root else Path(tempfile.mkdtemp())
        self.per_turn_timeout = per_turn_timeout
        self.total_timeout = total_timeout
        self.model_fn = model_fn

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

    def _verify_task(self, task: Task, sandbox_dir: Path, model_output: str = "") -> bool:
        if task.verification_script:
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
        return self._verify_expected_outcome(task, sandbox_dir, model_output)

    def _verify_expected_outcome(self, task: Task, sandbox_dir: Path, model_output: str = "") -> bool:
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

        if "stdout_contains" in expected:
            for substr in expected["stdout_contains"]:
                if substr not in model_output:
                    return False

        if "stdout_pattern" in expected:
            if not re.search(expected["stdout_pattern"], model_output):
                return False

        return True

    def _count_tokens(self, text: str) -> int:
        return max(1, len(text) // 4)

    def _extract_bash_commands(self, text: str) -> list[str]:
        commands = []
        for match in re.finditer(r'```(?:bash|sh|shell)?\n(.+?)\n```', text, re.DOTALL):
            commands.append(match.group(1).strip())
        for match in re.finditer(r'```\n?(.+?)\n?```', text, re.DOTALL):
            cmd = match.group(1).strip()
            if cmd and not cmd.startswith(('{', 'def ', 'class ', 'import ', 'from ', '#', '/*')):
                commands.append(cmd)
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        for line in lines:
            if line.startswith(('$ ', '> ')):
                commands.append(line[2:])
        return commands

    def _run_bash_in_sandbox(self, command: str, sandbox_dir: Path) -> str:
        try:
            result = subprocess.run(
                command, shell=True, capture_output=True, text=True,
                timeout=self.per_turn_timeout, cwd=str(sandbox_dir),
            )
            output = result.stdout
            if result.stderr:
                output += f"\n[stderr]\n{result.stderr}" if output else result.stderr
            return output[:10000]
        except subprocess.TimeoutExpired:
            return "[TIMEOUT]"
        except Exception as e:
            return f"[ERROR] {e}"

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
            model_output = ""

            prompt = f"You are a coding assistant. Complete this task:\n\n{task.description}\n\n"
            prompt += f"Working directory: {sandbox_dir}\n"
            prompt += f"Tools allowed: {', '.join(task.tools_required)}\n"
            prompt += f"Max turns: {max_turns}\n"

            if task.initial_state:
                prompt += "\nInitial files:\n"
                for fname, content in task.initial_state.items():
                    prompt += f"\n--- {fname} ---\n{content}\n"

            prompt += "\nYou can use bash commands enclosed in ```bash ... ``` blocks.\n"

            tokens_used += self._count_tokens(prompt)

            for turn in range(max_turns):
                turns_used = turn + 1
                if time.time() - start_time > self.total_timeout:
                    errors.append(f"Total timeout exceeded after {turns_used} turns")
                    break

                if self.model_fn is None:
                    break

                response = self.model_fn(prompt)
                tokens_used += self._count_tokens(response)
                model_output += response + "\n"

                commands = self._extract_bash_commands(response)
                if not commands:
                    break

                prompt = ""
                for cmd in commands:
                    cmd_output = self._run_bash_in_sandbox(cmd, sandbox_dir)
                    prompt += f"$ {cmd}\n{cmd_output}\n"
                    tokens_used += self._count_tokens(cmd_output)
                    if time.time() - start_time > self.total_timeout:
                        errors.append("Total timeout exceeded during command execution")
                        break

                if not prompt:
                    break

                prompt += "\nContinue or respond with 'DONE' if the task is complete.\n"

            success = self._verify_task(task, sandbox_dir, model_output)

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
