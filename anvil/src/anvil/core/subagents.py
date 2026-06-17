"""Subagent system — spawn isolated agents with own context window."""

from __future__ import annotations

import asyncio
import uuid
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from anvil.agents.agent_base import BaseAgent
from anvil.core.session import Session


class SubagentStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class SubagentResult:
    id: str
    task: str
    output: str
    status: SubagentStatus
    duration_ms: float = 0.0
    agent_name: str = ""
    error: str | None = None
    files_changed: list[str] = field(default_factory=list)
    token_usage: dict[str, int] = field(default_factory=dict)


@dataclass
class SubagentTask:
    id: str
    task: str
    agent_name: str
    model: str
    max_turns: int = 20
    tools_allowed: list[str] | None = None
    tools_denied: list[str] | None = None
    created_at: float = field(default_factory=time.time)


class SubagentManager:
    """Manages spawning and tracking subagents."""

    def __init__(self, engine: Any = None):
        self.engine = engine
        self._active: dict[str, SubagentTask] = {}
        self._results: dict[str, SubagentResult] = {}
        self._history: list[SubagentResult] = []

    def spawn(
        self,
        task: str,
        agent_name: str = "general",
        model: str | None = None,
        max_turns: int = 20,
        tools_allowed: list[str] | None = None,
        tools_denied: list[str] | None = None,
    ) -> str:
        """Spawn a subagent. Returns the task ID."""
        task_id = str(uuid.uuid4())[:8]
        subtask = SubagentTask(
            id=task_id,
            task=task,
            agent_name=agent_name,
            model=model or "gpt-4o-mini",
            max_turns=max_turns,
            tools_allowed=tools_allowed,
            tools_denied=tools_denied,
        )
        self._active[task_id] = subtask
        return task_id

    def execute(self, task_id: str) -> SubagentResult:
        """Execute a subagent synchronously."""
        if task_id not in self._active:
            return SubagentResult(
                id=task_id, task="", output="Task not found",
                status=SubagentStatus.FAILED, error="Task not found"
            )

        subtask = self._active.pop(task_id)
        start = time.time()

        try:
            if self.engine:
                result = self.engine.run(
                    subtask.task,
                    max_iterations=subtask.max_turns,
                )
                duration = (time.time() - start) * 1000
                subresult = SubagentResult(
                    id=task_id,
                    task=subtask.task,
                    output=result.output or "",
                    status=SubagentStatus.COMPLETED if result.success else SubagentStatus.FAILED,
                    duration_ms=duration,
                    agent_name=subtask.agent_name,
                    error=result.error,
                    files_changed=getattr(result, 'files_changed', []),
                )
            else:
                subresult = SubagentResult(
                    id=task_id,
                    task=subtask.task,
                    output="No engine available",
                    status=SubagentStatus.FAILED,
                    error="No engine configured",
                )
        except Exception as e:
            duration = (time.time() - start) * 1000
            subresult = SubagentResult(
                id=task_id,
                task=subtask.task,
                output="",
                status=SubagentStatus.FAILED,
                duration_ms=duration,
                error=str(e),
            )

        self._results[task_id] = subresult
        self._history.append(subresult)
        return subresult

    async def execute_async(self, task_id: str) -> SubagentResult:
        """Execute a subagent asynchronously."""
        return await asyncio.get_event_loop().run_in_executor(None, self.execute, task_id)

    def get_result(self, task_id: str) -> SubagentResult | None:
        return self._results.get(task_id)

    def get_history(self) -> list[SubagentResult]:
        return list(self._history)

    def get_active(self) -> list[SubagentTask]:
        return list(self._active.values())

    def fan_out(
        self,
        tasks: list[str],
        agent_name: str = "general",
        model: str | None = None,
    ) -> list[str]:
        """Spawn multiple subagents in parallel. Returns list of task IDs."""
        return [
            self.spawn(t, agent_name=agent_name, model=model)
            for t in tasks
        ]

    def gather(self, task_ids: list[str]) -> list[SubagentResult]:
        """Execute all subagents and gather results."""
        return [self.execute(tid) for tid in task_ids]

    def summarize(self, results: list[SubagentResult]) -> str:
        """Summarize multiple subagent results into one output."""
        parts = []
        for r in results:
            status = "✅" if r.status == SubagentStatus.COMPLETED else "❌"
            parts.append(f"{status} [{r.agent_name}] {r.task[:60]}...\n{r.output[:500]}")
        return "\n\n---\n\n".join(parts)
