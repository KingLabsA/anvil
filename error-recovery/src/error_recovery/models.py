"""Pydantic models for error recovery."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class ErrorCategory(str, Enum):
    BASH_ERROR = "bash_error"
    EDIT_ERROR = "edit_error"
    READ_ERROR = "read_error"
    WRITE_ERROR = "write_error"
    TEST_ERROR = "test_error"
    NETWORK_ERROR = "network_error"
    IMPORT_ERROR = "import_error"
    TYPE_ERROR = "type_error"
    UNKNOWN = "unknown"


class ErrorPattern(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    error_type: ErrorCategory
    error_message: str
    tool_name: str = ""
    recovery_prompt: str
    success_rate: float = Field(default=0.5, ge=0.0, le=1.0)
    pattern: str = ""
    tags: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    def matches(self, error_message: str) -> bool:
        import re

        if self.pattern:
            try:
                return bool(re.search(self.pattern, error_message, re.IGNORECASE))
            except re.error:
                pass
        return self.error_message.lower() in error_message.lower()


class RecoveryResult(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    original_error: str
    error_category: ErrorCategory = ErrorCategory.UNKNOWN
    recovery_prompt: str = ""
    new_output: str = ""
    success: bool = False
    attempts: int = 1
    pattern_matched: str | None = None
    pattern_similarity: float = 0.0
    elapsed_seconds: float = 0.0
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    @property
    def recovered(self) -> bool:
        return self.success and self.attempts <= 3


class ErrorRecoveryConfig(BaseModel):
    max_attempts: int = Field(default=3, ge=1, le=10)
    similarity_threshold: float = Field(default=0.8, ge=0.0, le=1.0)
    fallback_to_llm: bool = True
    backoff_base: float = Field(default=2.0, ge=1.0)
    backoff_max: float = Field(default=30.0, ge=5.0)
    cooling_period_seconds: float = Field(default=0.0, ge=0.0)
    log_level: str = "INFO"
    pattern_data_dir: str = ""
    index_dir: str = ""
    model_name: str = "all-MiniLM-L6-v2"
    top_k: int = Field(default=5, ge=1, le=20)
    track_success_rates: bool = True

    def backoff_seconds(self, attempt: int) -> float:

        delay = min(self.backoff_base**attempt, self.backoff_max)
        jitter = delay * 0.1 * (hash(str(attempt)) % 10) / 10
        return delay + jitter


class ErrorTrace(BaseModel):
    trace_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    errors: list[RecoveryResult] = Field(default_factory=list)
    tool_name: str = ""
    context: str = ""

    def add_result(self, result: RecoveryResult) -> None:
        self.errors.append(result)

    @property
    def total_errors(self) -> int:
        return len(self.errors)

    @property
    def success_rate(self) -> float:
        if not self.errors:
            return 0.0
        return sum(1 for e in self.errors if e.success) / len(self.errors)

    @property
    def category_breakdown(self) -> dict[str, int]:
        breakdown: dict[str, int] = {}
        for e in self.errors:
            cat = e.error_category.value
            breakdown[cat] = breakdown.get(cat, 0) + 1
        return breakdown


class PatternStats(BaseModel):
    pattern_id: str
    pattern_text: str
    error_type: ErrorCategory
    uses: int = 0
    successes: int = 0
    last_used: datetime | None = None

    @property
    def success_rate(self) -> float:
        if self.uses == 0:
            return 0.0
        return self.successes / self.uses

    def record(self, success: bool) -> None:
        self.uses += 1
        if success:
            self.successes += 1
        self.last_used = datetime.utcnow()
