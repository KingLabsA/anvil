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

Python SDK usage::

    import anvil

    result = anvil.run("fix the failing tests")
    print(result.output)

    session = anvil.Session()
    session.ask("explain this code")
    session.ask("now refactor it")

    for chunk in anvil.stream("write a function"):
        print(chunk, end="")

    report = anvil.verify(["src/app.py"])

    anvil.create_agent(
        name="reviewer", mode="subagent",
        permission={"edit": "deny", "bash": "deny"},
    )

    agents = anvil.list_agents()
    anvil.switch_agent("plan")
"""

from anvil.core.engine import AnvilEngine, EngineResult
from anvil.core.config import AnvilConfig
from anvil.core.session import Session
from anvil.verify.pipeline import VerifyPipeline
from anvil.models.registry import ModelRegistry
from anvil.agents.agent_base import BaseAgent, AgentMode
from anvil.agents.agent_manager import AgentManager
from anvil.agents.builtin_agents import BUILTIN_AGENTS
from anvil.permissions.permissions import PermissionAction, PermissionConfig, PermissionManager
from anvil.sdk import (
    run,
    stream,
    arun,
    astream,
    verify,
    Session as SDKSession,
    configure,
    SDKResult,
    SDKVerifyResult,
    SDKAgentManager,
    _AgentsProxy,
)

__version__ = "0.1.0"

# ── Agent management via SDK ──────────────────────────────────────────────
# anvil._agents is the SDK proxy for agent operations.
# It's accessed via anvil.list_agents(), anvil.create_agent(), etc.
# This avoids conflicting with the anvil.agents subpackage.
_agents_proxy = _AgentsProxy()


def list_agents() -> list:
    """List all available agents."""
    return _agents_proxy.list()


def switch_agent(name: str) -> dict:
    """Switch to a different agent."""
    return _agents_proxy.switch(name)


def create_agent(
    name: str,
    description: str = "",
    mode: str = "subagent",
    model: str = "local",
    temperature: float = 0.2,
    max_steps: int = 20,
    tools_whitelist: list = None,
    tools_blacklist: list = None,
    permission: dict = None,
    prompt_template: str = "",
    hidden: bool = False,
    color: str = "white",
) -> dict:
    """Create a custom agent."""
    return _agents_proxy.create(
        name=name,
        description=description,
        mode=mode,
        model=model,
        temperature=temperature,
        max_steps=max_steps,
        tools_whitelist=tools_whitelist or [],
        tools_blacklist=tools_blacklist or [],
        permission=permission or {},
        prompt_template=prompt_template,
        hidden=hidden,
        color=color,
    )


def invoke_agent(name: str, task: str, **kwargs) -> dict:
    """Invoke a subagent directly."""
    return _agents_proxy.invoke(name, task, **kwargs)


__all__ = [
    # Core
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
    # SDK
    "run",
    "stream",
    "arun",
    "astream",
    "verify",
    "SDKSession",
    "configure",
    "SDKResult",
    "SDKVerifyResult",
    "SDKAgentManager",
    # Agent management
    "list_agents",
    "switch_agent",
    "create_agent",
    "invoke_agent",
]