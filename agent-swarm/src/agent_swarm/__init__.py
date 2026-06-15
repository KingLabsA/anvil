"""AgentSwarm — Orchestrate micro-agent swarms using Markov transition matrices."""

from agent_swarm.orchestrator import SwarmOrchestrator, SwarmResult, SwarmStatus
from agent_swarm.transition_matrix import TransitionMatrix, ToolCall, HandoffPattern
from agent_swarm.agents import (
    ReaderAgent,
    EditorAgent,
    BashAgent,
    VerifierAgent,
    PlannerAgent,
    BaseAgent,
    AgentRole,
    create_agent,
)
from agent_swarm.models import (
    AgentConfig,
    SwarmResult as SwarmResultPydantic,
    HandoffEvent,
    AgentMessage as AgentMessagePydantic,
)

__version__ = "0.1.0"
__all__ = [
    "SwarmOrchestrator",
    "SwarmResult",
    "SwarmStatus",
    "TransitionMatrix",
    "ToolCall",
    "HandoffPattern",
    "ReaderAgent",
    "EditorAgent",
    "BashAgent",
    "VerifierAgent",
    "PlannerAgent",
    "BaseAgent",
    "AgentRole",
    "create_agent",
    "AgentConfig",
    "HandoffEvent",
    "AgentMessagePydantic",
]
