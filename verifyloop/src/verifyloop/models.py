"""Core data models for the VerifyLoop framework."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class StepType(str, Enum):
    PLAN = "plan"
    EXECUTE = "execute"
    VERIFY = "verify"
    RECOVER = "recover"


class Step(BaseModel):
    step_type: StepType
    content: str
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    confidence: float = 0.0
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Substep(BaseModel):
    description: str
    tool: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    order: int = 0


class PlanStep(BaseModel):
    description: str
    substeps: list[str] = Field(default_factory=list)
    estimated_tools: list[str] = Field(default_factory=list)
    substep_details: list[Substep] = Field(default_factory=list)
    complexity: Literal["low", "medium", "high"] = "medium"
    context_tokens: int = 0
    estimated_duration_seconds: float = 0.0


class ExecuteStep(BaseModel):
    tool: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    result: str = ""
    success: bool = False
    duration_seconds: float = 0.0
    exit_code: int | None = None
    error: str | None = None
    artifacts: dict[str, str] = Field(default_factory=dict)

    @property
    def failed(self) -> bool:
        return not self.success


class VerifyCheckResult(BaseModel):
    check: str
    passed: bool
    detail: str = ""


class VerifyStep(BaseModel):
    checks: list[str] = Field(default_factory=list)
    check_results: list[VerifyCheckResult] = Field(default_factory=list)
    passed: bool = False
    confidence: float = 0.0
    failures: list[str] = Field(default_factory=list)
    fix_suggestions: list[str] = Field(default_factory=list)
    verification_model: str = "reason-critic-7b"
    used_trained_model: bool = False


class RecoverStep(BaseModel):
    original_error: str
    recovery_attempt: str = ""
    recovery_type: Literal["edit", "create", "retry", "simplify", "analyze"] = "edit"
    success: bool = False
    attempt_number: int = 1
    max_attempts: int = 3
    patched_arguments: dict[str, Any] = Field(default_factory=dict)

    @property
    def exhausted(self) -> bool:
        return self.attempt_number >= self.max_attempts and not self.success


class RunStatus(str, Enum):
    PENDING = "pending"
    PLANNING = "planning"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    RECOVERING = "recovering"
    COMPLETED = "completed"
    FAILED = "failed"


class TokenUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    def merge(self, other: TokenUsage) -> TokenUsage:
        return TokenUsage(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
        )


class AgentRun(BaseModel):
    task: str
    steps: list[Step] = Field(default_factory=list)
    status: RunStatus = RunStatus.PENDING
    token_usage: TokenUsage = Field(default_factory=TokenUsage)
    duration_seconds: float = 0.0
    iteration: int = 0
    max_iterations: int = 5
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    def add_step(self, step: Step) -> None:
        self.steps.append(step)

    def elapsed(self) -> float:
        if self.completed_at:
            return (self.completed_at - self.created_at).total_seconds()
        return (datetime.now(UTC) - self.created_at).total_seconds()


class PipelineConfig(BaseModel):
    model: str = "gpt-4o"
    verify_model: str = "reason-critic-7b"
    max_iterations: int = 5
    confidence_threshold: float = 0.8
    max_recovery_attempts: int = 3
    working_dir: str = "."
    dry_run: bool = False
    interactive: bool = False
    sandbox: bool = False
    sandbox_image: str = "python:3.11-slim"
    callbacks: dict[str, Any] = Field(default_factory=dict)
