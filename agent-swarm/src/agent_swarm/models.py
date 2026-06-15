"""Pydantic models for the agent swarm system."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class AgentRole(str, Enum):
    """Roles that micro-agents can assume."""

    READER = "reader"
    EDITOR = "editor"
    BASH = "bash"
    VERIFIER = "verifier"
    PLANNER = "planner"


class ToolDef(BaseModel):
    """Definition of a tool available to an agent."""

    name: str
    description: str
    parameters: dict[str, Any] = Field(default_factory=dict)


class AgentConfig(BaseModel):
    """Configuration for spawning a micro-agent."""

    role: AgentRole
    system_prompt: str = ""
    tools: list[ToolDef] = Field(default_factory=list)
    can_handoff_to: list[AgentRole] = Field(default_factory=list)
    max_iterations: int = 10
    model: str = "gpt-4o-mini"
    temperature: float = 0.2

    @classmethod
    def for_role(cls, role: AgentRole | str) -> AgentConfig:
        """Create a default config for a given role."""
        if isinstance(role, str):
            role = AgentRole(role)
        configs: dict[AgentRole, AgentConfig] = {
            AgentRole.READER: cls(
                role=AgentRole.READER,
                system_prompt=(
                    "You are a Reader agent. Your job is to explore the codebase, "
                    "read files, search for patterns, and gather context. You do NOT "
                    "edit files or run commands. When you have enough context, hand off "
                    "to the Editor, Bash, or Verifier agent as appropriate."
                ),
                tools=[
                    ToolDef(name="read", description="Read file contents at a given path", parameters={"path": {"type": "string"}}),
                    ToolDef(name="grep", description="Search file contents for a pattern", parameters={"pattern": {"type": "string"}, "path": {"type": "string"}}),
                    ToolDef(name="glob", description="Find files matching a pattern", parameters={"pattern": {"type": "string"}}),
                ],
                can_handoff_to=[AgentRole.EDITOR, AgentRole.BASH, AgentRole.VERIFIER, AgentRole.PLANNER],
            ),
            AgentRole.EDITOR: cls(
                role=AgentRole.EDITOR,
                system_prompt=(
                    "You are an Editor agent. Your job is to write and modify code. "
                    "You make precise, targeted edits. After editing, hand off to the "
                    "Verifier to check your work."
                ),
                tools=[
                    ToolDef(name="edit", description="Edit a file by replacing a string", parameters={"file_path": {"type": "string"}, "old_string": {"type": "string"}, "new_string": {"type": "string"}}),
                    ToolDef(name="write", description="Write content to a file", parameters={"file_path": {"type": "string"}, "content": {"type": "string"}}),
                ],
                can_handoff_to=[AgentRole.READER, AgentRole.BASH, AgentRole.VERIFIER, AgentRole.PLANNER],
            ),
            AgentRole.BASH: cls(
                role=AgentRole.BASH,
                system_prompt=(
                    "You are a Bash agent. Your job is to execute shell commands to "
                    "install dependencies, run tests, start servers, and perform "
                    "system operations. You do NOT edit files directly."
                ),
                tools=[
                    ToolDef(name="bash", description="Execute a shell command", parameters={"command": {"type": "string"}, "timeout": {"type": "integer"}}),
                ],
                can_handoff_to=[AgentRole.READER, AgentRole.EDITOR, AgentRole.VERIFIER, AgentRole.PLANNER],
            ),
            AgentRole.VERIFIER: cls(
                role=AgentRole.VERIFIER,
                system_prompt=(
                    "You are a Verifier agent. Your job is to validate that changes "
                    "work correctly by running tests, checking linting, and verifying "
                    "the code does what was intended."
                ),
                tools=[
                    ToolDef(name="bash", description="Execute shell commands for testing", parameters={"command": {"type": "string"}}),
                    ToolDef(name="read", description="Read files to verify changes", parameters={"path": {"type": "string"}}),
                    ToolDef(name="grep", description="Search for patterns in files", parameters={"pattern": {"type": "string"}, "path": {"type": "string"}}),
                ],
                can_handoff_to=[AgentRole.READER, AgentRole.EDITOR, AgentRole.BASH, AgentRole.PLANNER],
            ),
            AgentRole.PLANNER: cls(
                role=AgentRole.PLANNER,
                system_prompt=(
                    "You are a Planner agent. Your job is to break down tasks, define "
                    "the approach, and coordinate which agents should handle which steps. "
                    "You ask clarifying questions when requirements are ambiguous."
                ),
                tools=[
                    ToolDef(name="question", description="Ask the user a clarifying question", parameters={"question": {"type": "string"}}),
                    ToolDef(name="glob", description="Find files to understand project structure", parameters={"pattern": {"type": "string"}}),
                    ToolDef(name="read", description="Read files for context", parameters={"path": {"type": "string"}}),
                ],
                can_handoff_to=[AgentRole.READER, AgentRole.EDITOR, AgentRole.BASH, AgentRole.VERIFIER],
            ),
        }
        return configs[role]


class AgentMessage(BaseModel):
    """A message in the agent swarm conversation."""

    role: str = "assistant"
    content: str = ""
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class HandoffEvent(BaseModel):
    """Record of an agent handoff event."""

    id: str = Field(default_factory=lambda: __import__("uuid").uuid4().hex[:8])
    from_role: AgentRole
    to_role: AgentRole
    context: dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    probability: float = 0.0
    pattern: list[dict[str, Any]] = Field(default_factory=list)


class SwarmResult(BaseModel):
    """Result of a swarm task execution."""

    task_id: str = Field(default_factory=lambda: __import__("uuid").uuid4().hex[:12])
    task_description: str = ""
    status: str = "completed"
    final_agent: str = ""
    final_output: str = ""
    handoffs: list[HandoffEvent] = Field(default_factory=list)
    agent_history: list[dict[str, Any]] = Field(default_factory=list)
    total_handoffs: int = 0
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def success(self) -> bool:
        return self.status == "completed" and self.final_output != ""

    def summary(self) -> str:
        lines = [
            f"Task: {self.task_description}",
            f"Status: {self.status}",
            f"Final Agent: {self.final_agent}",
            f"Total Handoffs: {self.total_handoffs}",
        ]
        if self.final_output:
            lines.append(f"Output: {self.final_output[:200]}")
        return "\n".join(lines)
