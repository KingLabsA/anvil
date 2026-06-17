"""Type definitions for Anvil SDK."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class TaskStatus(str, Enum):
    """Status of a task execution."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StreamChunkType(str, Enum):
    """Type of a streaming chunk."""

    TOKEN = "token"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    RESULT = "result"
    ERROR = "error"


@dataclass
class AgentConfig:
    """Configuration for creating an agent."""

    name: str
    description: str
    model: str = "local"
    system_prompt: Optional[str] = None
    tools: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for API requests."""
        config: dict[str, Any] = {
            "name": self.name,
            "description": self.description,
            "model": self.model,
        }
        if self.system_prompt is not None:
            config["system_prompt"] = self.system_prompt
        if self.tools:
            config["tools"] = self.tools
        if self.metadata:
            config["metadata"] = self.metadata
        return config


@dataclass
class TaskResult:
    """Result from a task execution."""

    task_id: str
    status: TaskStatus
    result: Optional[str] = None
    error: Optional[str] = None
    tokens_used: Optional[int] = None
    duration_ms: Optional[float] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TaskResult:
        """Create from API response dictionary."""
        return cls(
            task_id=data.get("task_id", ""),
            status=TaskStatus(data.get("status", "completed")),
            result=data.get("result"),
            error=data.get("error"),
            tokens_used=data.get("tokens_used"),
            duration_ms=data.get("duration_ms"),
            metadata=data.get("metadata", {}),
        )


@dataclass
class StreamChunk:
    """A chunk from a streaming task response."""

    type: StreamChunkType
    content: str = ""
    data: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StreamChunk:
        """Create from WebSocket message dictionary."""
        return cls(
            type=StreamChunkType(data.get("type", "token")),
            content=data.get("content", ""),
            data=data,
        )

    @property
    def is_final(self) -> bool:
        """Whether this is the final chunk in a stream."""
        return self.type in (StreamChunkType.RESULT, StreamChunkType.ERROR)
