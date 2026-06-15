"""Session tracking for Anvil — every action recorded."""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class StepStatus(str, Enum):
    PLANNED = "planned"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    RECOVERING = "recovering"
    RECOVERED = "recovered"


class StepKind(str, Enum):
    PLAN = "plan"
    EXECUTE = "execute"
    VERIFY = "verify"
    RECOVER = "recover"
    THINK = "think"


@dataclass
class ToolCall:
    tool: str
    args: dict[str, Any]
    result: str | None = None
    error: str | None = None
    duration_ms: float = 0.0
    timestamp: float = field(default_factory=time.time)


@dataclass
class Step:
    kind: StepKind
    content: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    status: StepStatus = StepStatus.PLANNED
    verify_result: dict | None = None
    recovery_attempts: int = 0
    duration_ms: float = 0.0
    timestamp: float = field(default_factory=time.time)


@dataclass
class SessionStats:
    total_steps: int = 0
    successful_steps: int = 0
    failed_steps: int = 0
    recovered_steps: int = 0
    total_tool_calls: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    error_rate: float = 0.0
    recovery_rate: float = 0.0
    duration_seconds: float = 0.0

    def update(self, step: Step) -> None:
        self.total_steps += 1
        self.total_tool_calls += len(step.tool_calls)
        if step.status == StepStatus.SUCCESS:
            self.successful_steps += 1
        elif step.status == StepStatus.RECOVERED:
            self.recovered_steps += 1
            self.successful_steps += 1
        elif step.status == StepStatus.FAILED:
            self.failed_steps += 1
        if self.total_steps > 0:
            self.error_rate = self.failed_steps / self.total_steps
            total_with_errors = self.failed_steps + self.recovered_steps
            if total_with_errors > 0:
                self.recovery_rate = self.recovered_steps / total_with_errors


class Session:
    def __init__(
        self,
        task: str,
        session_id: str | None = None,
        project_root: str | None = None,
        persist: bool = True,
    ):
        self.id = session_id or str(uuid.uuid4())[:8]
        self.task = task
        self.project_root = project_root or str(Path.cwd())
        self.steps: list[Step] = []
        self.stats = SessionStats()
        self.persist = persist
        self.started_at = time.time()
        self.ended_at: float | None = None

    def add_step(self, step: Step) -> None:
        self.steps.append(step)
        self.stats.update(step)
        if self.persist:
            self._save_step(step)

    def end(self, status: str = "completed") -> dict:
        self.ended_at = time.time()
        self.stats.duration_seconds = self.ended_at - self.started_at
        summary = self.summary()
        if self.persist:
            self._save_summary(summary)
        return summary

    def summary(self) -> dict:
        return {
            "session_id": self.id,
            "task": self.task,
            "status": "completed" if self.ended_at else "running",
            "steps": len(self.steps),
            "stats": asdict(self.stats),
            "duration_seconds": self.stats.duration_seconds,
        }

    def _save_step(self, step: Step) -> None:
        state_dir = Path.home() / ".anvil" / "sessions" / self.id
        state_dir.mkdir(parents=True, exist_ok=True)
        step_file = state_dir / f"step_{len(self.steps):04d}.json"
        step_file.write_text(json.dumps(asdict(step), default=str, indent=2))

    def _save_summary(self, summary: dict) -> None:
        state_dir = Path.home() / ".anvil" / "sessions" / self.id
        state_dir.mkdir(parents=True, exist_ok=True)
        (state_dir / "summary.json").write_text(
            json.dumps(summary, default=str, indent=2)
        )

    @classmethod
    def load(cls, session_id: str) -> Session | None:
        state_dir = Path.home() / ".anvil" / "sessions" / session_id
        if not state_dir.exists():
            return None
        summary = json.loads((state_dir / "summary.json").read_text())
        session = cls(task=summary["task"], session_id=session_id)
        session.stats = SessionStats(**summary["stats"])
        return session

    def format_progress(self) -> str:
        lines = [f"Session {self.id}: {self.task}"]
        for i, step in enumerate(self.steps):
            icon = {
                StepStatus.SUCCESS: "✓",
                StepStatus.FAILED: "✗",
                StepStatus.RECOVERED: "↻",
                StepStatus.RUNNING: "…",
                StepStatus.RECOVERING: "↻",
                StepStatus.PLANNED: "○",
                StepStatus.SKIPPED: "—",
            }.get(step.status, "?")
            lines.append(f"  {icon} [{step.kind.value}] {step.content[:80]}")
        lines.append(
            f"\nStats: {self.stats.successful_steps}/{self.stats.total_steps} steps "
            f"| {self.stats.error_rate:.0%} error rate "
            f"| {self.stats.recovery_rate:.0%} recovery rate"
        )
        return "\n".join(lines)
