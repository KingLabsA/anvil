"""Session tracking for Anvil — every action recorded."""

from __future__ import annotations

import base64
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

    def export(self) -> dict[str, Any]:
        """Export session to a JSON-serializable dictionary."""
        return {
            "id": self.id,
            "task": self.task,
            "project_root": self.project_root,
            "steps": [asdict(step) for step in self.steps],
            "stats": asdict(self.stats),
            "started_at": self.started_at,
            "ended_at": self.ended_at,
        }

    def to_json(self, indent: int = 2) -> str:
        """Export session as JSON string."""
        return json.dumps(self.export(), indent=indent, default=str)

    def to_shareable_link(self) -> str:
        """Generate a base64-encoded shareable link for the session."""
        data = self.to_json(indent=None)
        encoded = base64.urlsafe_b64encode(data.encode()).decode()
        return f"anvil://{encoded}"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Session:
        """Import session from a dictionary."""
        session = cls(
            task=data["task"],
            session_id=data.get("id"),
            project_root=data.get("project_root"),
            persist=False,  # Don't auto-save imported sessions
        )
        
        # Restore steps
        for step_data in data.get("steps", []):
            tool_calls = [
                ToolCall(**tc) for tc in step_data.get("tool_calls", [])
            ]
            step = Step(
                kind=StepKind(step_data["kind"]),
                content=step_data["content"],
                tool_calls=tool_calls,
                status=StepStatus(step_data["status"]),
                verify_result=step_data.get("verify_result"),
                recovery_attempts=step_data.get("recovery_attempts", 0),
                duration_ms=step_data.get("duration_ms", 0.0),
                timestamp=step_data.get("timestamp", time.time()),
            )
            session.steps.append(step)
        
        # Restore stats
        if "stats" in data:
            session.stats = SessionStats(**data["stats"])
        
        # Restore timestamps
        session.started_at = data.get("started_at", time.time())
        session.ended_at = data.get("ended_at")
        
        return session

    @classmethod
    def from_json(cls, json_str: str) -> Session:
        """Import session from a JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)

    @classmethod
    def from_shareable_link(cls, link: str) -> Session:
        """Import session from a shareable link."""
        if not link.startswith("anvil://"):
            raise ValueError("Invalid shareable link format")
        
        encoded = link[8:]  # Remove "anvil://" prefix
        decoded = base64.urlsafe_b64decode(encoded.encode()).decode()
        return cls.from_json(decoded)

    @classmethod
    def list_sessions(cls) -> list[dict[str, Any]]:
        """List all saved sessions."""
        sessions_dir = Path.home() / ".anvil" / "sessions"
        if not sessions_dir.exists():
            return []
        
        sessions = []
        for session_dir in sessions_dir.iterdir():
            if session_dir.is_dir():
                summary_file = session_dir / "summary.json"
                if summary_file.exists():
                    try:
                        summary = json.loads(summary_file.read_text())
                        sessions.append({
                            "id": session_dir.name,
                            "task": summary.get("task"),
                            "status": summary.get("status"),
                            "steps": summary.get("steps"),
                            "duration_seconds": summary.get("duration_seconds"),
                        })
                    except (json.JSONDecodeError, KeyError):
                        continue
        
        return sorted(sessions, key=lambda s: s.get("id", ""))
