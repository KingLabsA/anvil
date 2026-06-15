"""Pydantic models for BenchAgent benchmark definitions and results."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class TaskCategory(str, Enum):
    BASH = "bash"
    EDIT = "edit"
    READ = "read"
    WRITE = "write"
    MULTI_TOOL = "multi_tool"
    ERROR_RECOVERY = "error_recovery"


class Difficulty(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class Task(BaseModel):
    task_id: str
    category: TaskCategory
    difficulty: Difficulty
    description: str
    initial_state: dict[str, str] = Field(
        default_factory=dict,
        description="Mapping of filename -> file content to create before the task",
    )
    expected_outcome: dict[str, Any] = Field(
        default_factory=dict,
        description="Expected result: keys may include 'files', 'exit_code', 'stdout', 'file_exists'",
    )
    tools_required: list[str] = Field(default_factory=list)
    max_turns: int = 10
    verification_script: str = ""


class TaskResult(BaseModel):
    task_id: str
    model: str
    success: bool = False
    turns_used: int = 0
    tokens_used: int = 0
    errors: list[str] = Field(default_factory=list)
    recovery_attempts: int = 0
    duration_seconds: float = 0.0
    actual_output: dict[str, Any] = Field(default_factory=dict)


class ScoreReport(BaseModel):
    model: str
    total_score: float = 0.0
    category_scores: dict[str, float] = Field(default_factory=dict)
    tool_scores: dict[str, float] = Field(default_factory=dict)
    error_recovery_rate: float = 0.0
    leaderboard_rank: int = 0


class Leaderboard(BaseModel):
    entries: list[ScoreReport] = Field(default_factory=list)
    last_updated: str = ""
