"""Agent manager — registration, switching, @mention, and lifecycle."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from anvil.agents.agent_base import BaseAgent
from anvil.agents.builtin_agents import BUILTIN_AGENTS
from anvil.models.registry import Message, ModelRegistry, ModelResponse


@dataclass
class AgentInvocation:
    """Record of a single subagent invocation and its result."""
    agent_name: str
    task: str
    response: str
    success: bool
    tool_calls: list[dict] = field(default_factory=list)
    duration_ms: float = 0.0


class AgentManager:
    """Central registry and lifecycle manager for Anvil agents.

    Responsibilities
    ----------------
    * Register and look up agents (builtins + user-defined)
    * Switch the active primary agent (Tab-key style)
    * Dispatch subagent invocations via ``@mention`` syntax
    * Load custom agents from ``~/.config/anvil/agents/`` and ``.anvil/agents/``
    * Create agents from JSON dicts or markdown front-matter
    """

    def __init__(
        self,
        config_dir: Path | None = None,
        project_dir: Path | None = None,
    ):
        self._agents: dict[str, BaseAgent] = {}
        self._active_agent: str = "build"
        self._invocation_history: list[AgentInvocation] = []
        self._config_dir = config_dir or Path.home() / ".config" / "anvil"
        self._project_dir = project_dir or Path.cwd()

        # Register builtins
        for name, agent in BUILTIN_AGENTS.items():
            self._agents[name] = agent

        # Load user-defined agents
        self._load_from_directory(self._config_dir / "agents")
        self._load_from_directory(self._project_dir / ".anvil" / "agents")

    # ── registration ───────────────────────────────────────────────────

    def register(self, agent: BaseAgent) -> None:
        """Register (or replace) an agent by name."""
        self._agents[agent.name] = agent

    def get(self, name: str) -> BaseAgent | None:
        """Look up an agent by name."""
        return self._agents.get(name)

    def list_agents(self, include_hidden: bool = False) -> list[BaseAgent]:
        """Return all registered agents, optionally including hidden ones."""
        return [
            a for a in self._agents.values()
            if include_hidden or not a.hidden
        ]

    @property
    def active_agent(self) -> BaseAgent:
        """The agent currently owning the primary loop."""
        return self._agents[self._active_agent]

    def switch(self, name: str) -> BaseAgent:
        """Switch the active primary agent.

        Raises ``KeyError`` if *name* is not registered or the agent
        is not a PRIMARY agent.
        """
        agent = self._agents.get(name)
        if agent is None:
            raise KeyError(f"Unknown agent: {name!r}. Available: {list(self._agents.keys())}")
        if not agent.is_primary:
            raise ValueError(f"Agent {name!r} is a subagent — use @mention, not switch")
        self._active_agent = name
        return agent

    # ── @mention dispatch ──────────────────────────────────────────────

    _MENTION_RE = re.compile(r"@(\w+)\s+(.*)", re.DOTALL)

    def parse_mention(self, text: str) -> tuple[str, str] | None:
        """Extract ``@agent task`` from *text*.

        Returns ``(agent_name, task)`` or ``None`` if no @mention found.
        """
        m = self._MENTION_RE.search(text.strip())
        if m:
            return m.group(1).lower(), m.group(2).strip()
        return None

    def invoke_subagent(
        self,
        name: str,
        task: str,
        model: Any = None,
        working_dir: str = ".",
    ) -> AgentInvocation:
        """Invoke a subagent and capture its response.

        Parameters
        ----------
        name : str
            The subagent's registered name.
        task : str
            Description of what the subagent should do.
        model : BaseModel, optional
            An already-constructed model backend. If ``None``, one is
            created from the agent's model setting.
        working_dir : str
            Working directory for tool execution.

        Returns
        -------
        AgentInvocation
            Summary of what the subagent did.
        """
        import time

        agent = self._agents.get(name)
        if agent is None:
            return AgentInvocation(
                agent_name=name, task=task,
                response=f"Error: unknown agent '{name}'",
                success=False,
            )
        if not agent.is_subagent:
            return AgentInvocation(
                agent_name=name, task=task,
                response=f"Error: '{name}' is a primary agent, not a subagent",
                success=False,
            )

        start = time.time()

        # Resolve or create the model backend.
        if model is None:
            from anvil.core.config import AnvilConfig
            cfg = AnvilConfig()
            cfg.model.model = agent.model
            model = ModelRegistry.create(
                agent.model,
                api_key=cfg.model.api_key,
                api_base=cfg.model.api_base,
            )

        # Build the tool list available to this agent.
        all_tool_names = [t["name"] for t in _all_tool_definitions()]
        available = agent.available_tools(all_tool_names)
        system_prompt = agent.get_system_prompt(available)

        messages = [
            Message(role="system", content=system_prompt),
            Message(role="user", content=task),
        ]

        response: ModelResponse = model.complete(
            messages,
            temperature=agent.temperature,
            max_tokens=agent.extra.get("max_tokens", 4096),
        )

        duration_ms = (time.time() - start) * 1000

        invocation = AgentInvocation(
            agent_name=name,
            task=task,
            response=response.content,
            success=True,
            tool_calls=response.tool_calls,
            duration_ms=duration_ms,
        )
        self._invocation_history.append(invocation)
        return invocation

    # ── custom agent creation ───────────────────────────────────────────

    def create_agent_from_dict(self, name: str, spec: dict[str, Any]) -> BaseAgent:
        """Create and register a custom agent from a plain dict.

        Example ``spec``::

            {
                "description": "Reviews code for quality",
                "mode": "subagent",
                "model": "claude-3.5-sonnet",
                "permission": {"edit": "deny", "bash": "ask"},
                "max_steps": 10
            }

        Missing keys default to sensible values.
        """
        spec_copy = dict(spec)
        spec_copy.setdefault("description", f"Custom agent: {name}")
        spec_copy.setdefault("mode", "subagent")
        spec_copy.setdefault("model", "local")
        spec_copy.setdefault("temperature", 0.2)
        spec_copy.setdefault("top_p", 1.0)
        spec_copy.setdefault("max_steps", 20)
        spec_copy.setdefault("tools_whitelist", [])
        spec_copy.setdefault("tools_blacklist", [])
        spec_copy.setdefault("hidden", False)
        spec_copy.setdefault("color", "white")
        spec_copy.setdefault("prompt_template", "")
        spec_copy.setdefault("extra", {})

        agent = BaseAgent(name=name, **{
            k: v for k, v in spec_copy.items()
            if k in BaseAgent.__dataclass_fields__
        })
        self.register(agent)
        return agent

    def create_agent_from_markdown(self, text: str, name: str | None = None) -> BaseAgent:
        """Parse an agent from markdown with YAML-like front matter.

        Format::

            ---
            name: code-reviewer
            description: Reviews code for quality
            mode: subagent
            model: anthropic/claude-sonnet-4
            permission:
              edit: deny
              bash: ask
            ---

            You are a code reviewer...
            (body becomes the prompt_template)

        """
        front_matter: dict[str, Any] = {}
        body = ""

        if text.strip().startswith("---"):
            parts = text.strip().split("---", 2)
            if len(parts) >= 3:
                fm_text = parts[1].strip()
                body = parts[2].strip()
                for line in fm_text.split("\n"):
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if ":" in line:
                        key, _, value = line.partition(":")
                        key = key.strip()
                        value = value.strip()
                        # Parse nested YAML (simple 2-space indent).
                        if value == "" and key == "permission":
                            # Will be handled in the next indented block.
                            continue
                        front_matter[key] = _parse_yaml_value(value)
            else:
                body = text
        else:
            body = text

        # Handle indented permission block inside front matter.
        permission_block: dict[str, str] = {}
        if "permission" not in front_matter:
            # Try to parse from raw front matter.
            fm_lines = text.strip().split("---")[1].strip().split("\n") if text.strip().startswith("---") else []
            in_permission = False
            for line in fm_lines:
                stripped = line.strip()
                if stripped.startswith("permission:"):
                    in_permission = True
                    continue
                if in_permission:
                    if line.startswith("  ") or line.startswith("\t"):
                        k, _, v = stripped.partition(":")
                        permission_block[k.strip()] = v.strip()
                    else:
                        in_permission = False
            if permission_block:
                front_matter["permission"] = permission_block

        if body and "prompt_template" not in front_matter:
            front_matter["prompt_template"] = body + "\n\nAvailable tools: {tools}"

        agent_name = name or front_matter.pop("name", "custom")
        front_matter.pop("name", None)
        return self.create_agent_from_dict(agent_name, front_matter)

    # ── directory loading ───────────────────────────────────────────────

    def _load_from_directory(self, directory: Path) -> None:
        """Load custom agents from *.json* and *.md* files in *directory*.

        JSON files should map agent-name → spec.
        Markdown files should use front-matter format.
        """
        if not directory.exists():
            return

        for filepath in sorted(directory.iterdir()):
            if filepath.suffix == ".json":
                try:
                    data = json.loads(filepath.read_text(encoding="utf-8"))
                    for agent_name, spec in data.items():
                        if isinstance(spec, dict):
                            self.create_agent_from_dict(agent_name, spec)
                except (json.JSONDecodeError, TypeError, KeyError):
                    # Silently skip malformed files — they'll be logged elsewhere.
                    pass

            elif filepath.suffix == ".md":
                try:
                    text = filepath.read_text(encoding="utf-8")
                    agent_name = filepath.stem
                    self.create_agent_from_markdown(text, name=agent_name)
                except Exception:
                    pass

    # ── lifecycle helpers ───────────────────────────────────────────────

    def agent_names(self) -> list[str]:
        """Return names of all non-hidden agents."""
        return [a.name for a in self.list_agents(include_hidden=False)]

    def all_agent_names(self) -> list[str]:
        """Return names of all agents including hidden."""
        return list(self._agents.keys())

    def invocation_history(self) -> list[AgentInvocation]:
        """Return the history of all subagent invocations."""
        return list(self._invocation_history)


def _all_tool_definitions() -> list[dict]:
    """Return the master list of built-in tool definitions."""
    return [
        {"name": "bash", "description": "Run a shell command", "args": ["command"]},
        {"name": "read", "description": "Read a file", "args": ["path", "offset", "limit"]},
        {"name": "write", "description": "Write a file", "args": ["path", "content"]},
        {"name": "edit", "description": "Edit a file by replacing text", "args": ["path", "old_string", "new_string"]},
        {"name": "grep", "description": "Search file contents", "args": ["pattern", "path", "include"]},
        {"name": "glob", "description": "Find files by pattern", "args": ["pattern", "path"]},
        {"name": "ls", "description": "List directory contents", "args": ["path"]},
    ]


def _parse_yaml_value(value: str) -> Any:
    """Minimal YAML value parser for front-matter scalars."""
    value = value.strip()
    if value.lower() in ("true", "yes"):
        return True
    if value.lower() in ("false", "no"):
        return False
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        pass
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    if value.startswith("'") and value.endswith("'"):
        return value[1:-1]
    return value
