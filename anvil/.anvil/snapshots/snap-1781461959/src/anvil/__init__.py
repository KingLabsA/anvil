"""Anvil — The open-source, self-verified coding agent.

Generate → Execute → Verify → Recover.

Every other open agent generates and hopes. Anvil generates, runs,
checks, and fixes — because it was trained on 210,000 examples of
real agents doing exactly that.

The core loop:
    1. PLAN     — Decompose task into atomic steps
    2. EXECUTE  — Run each step with real tools
    3. VERIFY   — Check the output actually works (syntax, tests, lint, type)
    4. RECOVER  — If verification fails, diagnose and fix automatically

This isn't prompt engineering. This is behavior engineering.

v2 adds multi-agent support (switching, @mention, custom agents)
and a fine-grained permissions system.
"""

from anvil.agents.agent_base import AgentMode, BaseAgent
from anvil.agents.agent_manager import AgentManager
from anvil.agents.builtin_agents import BUILTIN_AGENTS
from anvil.core.config import AnvilConfig
from anvil.core.engine import AnvilEngine, EngineResult
from anvil.core.session import Session
from anvil.models.registry import ModelRegistry
from anvil.permissions.permissions import PermissionAction, PermissionConfig, PermissionManager
from anvil.verify.pipeline import VerifyPipeline

__version__ = "0.2.0"
__all__ = [
    "AnvilEngine",
    "AnvilConfig",
    "EngineResult",
    "Session",
    "VerifyPipeline",
    "ModelRegistry",
    "BaseAgent",
    "AgentMode",
    "AgentManager",
    "BUILTIN_AGENTS",
    "PermissionAction",
    "PermissionConfig",
    "PermissionManager",
]
