"""Base agent definition — the contract every Anvil agent satisfies."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from anvil.permissions.permissions import PermissionConfig


class AgentMode(str, Enum):
    """Whether this agent runs as the primary loop or is invoked as a subagent."""
    PRIMARY = "primary"
    SUBAGENT = "subagent"


@dataclass
class BaseAgent:
    """A fully-specified agent persona that the engine can switch to.

    Attributes
    ----------
    name : str
        Human-readable identifier, used with ``--agent build`` or ``@explore``.
    description : str
        One-line summary shown in ``anvil agents list``.
    mode : AgentMode
        PRIMARY agents own the main loop; SUBAGENT agents are invoked on-demand.
    model : str
        Model identifier forwarded to the model registry.
    temperature : float
        Sampling temperature for this agent.
    top_p : float
        Nucleus sampling parameter.
    max_steps : int
        Hard cap on tool-call iterations this agent may take per task.
    tools_whitelist : list[str]
        If non-empty, **only** these tools are available to the agent.
    tools_blacklist : list[str]
        Tools explicitly excluded even if they appear in the whitelist.
    permission : PermissionConfig
        Fine-grained per-tool permission overrides.
    prompt_template : str
        System-prompt template. May contain ``{tools}`` placeholder.
    hidden : bool
        Hidden agents don't appear in ``anvil agents list`` output
        (but are still functional).
    color : str
        Rich colour name used in the TUI to distinguish this agent's output.
    extra : dict
        Additional model-level kwargs forwarded to the backend.
    """

    name: str = "build"
    description: str = "Primary coding agent with full tool access"
    mode: AgentMode = AgentMode.PRIMARY
    model: str = "local"
    temperature: float = 0.2
    top_p: float = 1.0
    max_steps: int = 20
    tools_whitelist: list[str] = field(default_factory=list)
    tools_blacklist: list[str] = field(default_factory=list)
    permission: PermissionConfig = field(default_factory=PermissionConfig.permissive)
    prompt_template: str = ""
    hidden: bool = False
    color: str = "cyan"
    extra: dict = field(default_factory=dict)

    # ── derived helpers ────────────────────────────────────────────────

    @property
    def is_primary(self) -> bool:
        return self.mode == AgentMode.PRIMARY

    @property
    def is_subagent(self) -> bool:
        return self.mode == AgentMode.SUBAGENT

    def available_tools(self, all_tools: list[str]) -> list[str]:
        """Return the tools this agent is allowed to see.

        Whitelist wins over blacklist.  If no whitelist is given, all
        tools except blacklisted ones are available.
        """
        if self.tools_whitelist:
            allowed = [t for t in all_tools if t in self.tools_whitelist]
        else:
            allowed = list(all_tools)
        return [t for t in allowed if t not in self.tools_blacklist]

    def get_system_prompt(self, tools: list[str]) -> str:
        """Render the system-prompt template with available tools."""
        tool_str = ", ".join(tools)
        if self.prompt_template:
            return self.prompt_template.format(tools=tool_str)
        return f"You are the {self.name} agent. Available tools: {tool_str}"

    # ── serialisation ──────────────────────────────────────────────────

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "mode": self.mode.value,
            "model": self.model,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "max_steps": self.max_steps,
            "tools_whitelist": self.tools_whitelist,
            "tools_blacklist": self.tools_blacklist,
            "permission": self.permission.to_dict(),
            "prompt_template": self.prompt_template,
            "hidden": self.hidden,
            "color": self.color,
            "extra": self.extra,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BaseAgent:
        perm_data = data.pop("permission", {})
        mode_val = data.pop("mode", "primary")
        return cls(
            mode=AgentMode(mode_val),
            permission=PermissionConfig.from_dict(perm_data) if perm_data else PermissionConfig.permissive(),
            **{k: v for k, v in data.items() if k in cls.__dataclass_fields__},
        )
