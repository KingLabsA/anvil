"""Plan/Act mode — separate planning from execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class AgentMode(str, Enum):
    PLAN = "plan"
    ACT = "act"


@dataclass
class PlanStep:
    description: str
    files_involved: list[str] = field(default_factory=list)
    reasoning: str = ""
    status: str = "pending"  # pending, approved, executing, done, skipped


@dataclass
class Plan:
    task: str
    steps: list[PlanStep] = field(default_factory=list)
    mode: AgentMode = AgentMode.PLAN
    approved: bool = False
    summary: str = ""


class PlanActController:
    """Controls Plan/Act mode switching and plan management."""

    def __init__(self):
        self.mode = AgentMode.PLAN
        self.current_plan: Plan | None = None
        self._plans: list[Plan] = []

    def set_mode(self, mode: AgentMode) -> str:
        self.mode = mode
        return f"Switched to {mode.value} mode"

    def is_plan_mode(self) -> bool:
        return self.mode == AgentMode.PLAN

    def is_act_mode(self) -> bool:
        return self.mode == AgentMode.ACT

    def create_plan(self, task: str, steps: list[dict]) -> Plan:
        plan_steps = [
            PlanStep(
                description=s.get("description", ""),
                files_involved=s.get("files", []),
                reasoning=s.get("reasoning", ""),
            )
            for s in steps
        ]
        self.current_plan = Plan(task=task, steps=plan_steps)
        self._plans.append(self.current_plan)
        return self.current_plan

    def approve_plan(self) -> str:
        if not self.current_plan:
            return "No plan to approve"
        self.current_plan.approved = True
        self.mode = AgentMode.ACT
        return f"Plan approved. Switched to ACT mode. {len(self.current_plan.steps)} steps to execute."

    def reject_plan(self) -> str:
        if not self.current_plan:
            return "No plan to reject"
        self.current_plan = None
        return "Plan rejected. Create a new plan."

    def modify_plan(self, step_idx: int, new_description: str) -> str:
        if not self.current_plan or step_idx >= len(self.current_plan.steps):
            return "Invalid step"
        self.current_plan.steps[step_idx].description = new_description
        return f"Step {step_idx + 1} updated"

    def add_step(self, description: str, files: list[str] | None = None, reasoning: str = "") -> str:
        if not self.current_plan:
            self.current_plan = Plan(task="Manual plan")
            self._plans.append(self.current_plan)
        self.current_plan.steps.append(PlanStep(
            description=description,
            files_involved=files or [],
            reasoning=reasoning,
        ))
        return f"Step added: {description}"

    def remove_step(self, step_idx: int) -> str:
        if not self.current_plan or step_idx >= len(self.current_plan.steps):
            return "Invalid step"
        removed = self.current_plan.steps.pop(step_idx)
        return f"Removed step: {removed.description}"

    def get_plan_display(self) -> str:
        if not self.current_plan:
            return "No active plan"
        lines = [f"📋 Plan: {self.current_plan.task}", ""]
        for i, step in enumerate(self.current_plan.steps):
            icon = {"pending": "⏳", "approved": "✅", "executing": "🔄", "done": "✅", "skipped": "⏭️"}.get(step.status, "⏳")
            lines.append(f"{icon} Step {i+1}: {step.description}")
            if step.files_involved:
                lines.append(f"   Files: {', '.join(step.files_involved)}")
            if step.reasoning:
                lines.append(f"   Why: {step.reasoning}")
        lines.append(f"\nMode: {self.mode.value} | Approved: {self.current_plan.approved}")
        return "\n".join(lines)

    def get_plan_json(self) -> dict:
        if not self.current_plan:
            return {}
        return {
            "task": self.current_plan.task,
            "mode": self.mode.value,
            "approved": self.current_plan.approved,
            "steps": [
                {
                    "index": i,
                    "description": s.description,
                    "files": s.files_involved,
                    "reasoning": s.reasoning,
                    "status": s.status,
                }
                for i, s in enumerate(self.current_plan.steps)
            ],
        }

    def mark_step_done(self, step_idx: int) -> str:
        if not self.current_plan or step_idx >= len(self.current_plan.steps):
            return "Invalid step"
        self.current_plan.steps[step_idx].status = "done"
        done = sum(1 for s in self.current_plan.steps if s.status == "done")
        total = len(self.current_plan.steps)
        return f"Step {step_idx + 1} done. Progress: {done}/{total}"

    def is_complete(self) -> bool:
        if not self.current_plan:
            return False
        return all(s.status in ("done", "skipped") for s in self.current_plan.steps)
