"""Anvil SDK - Embed Anvil AI agent in your applications."""

from .client import AnvilClient
from .events import Event, EventManager
from .types import AgentConfig, TaskResult, StreamChunk

__all__ = [
    "AnvilClient",
    "Event",
    "EventManager",
    "AgentConfig",
    "TaskResult",
    "StreamChunk",
]

__version__ = "0.3.0"
