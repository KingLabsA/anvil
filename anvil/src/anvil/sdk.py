"""Anvil SDK — programmatic Python API for the self-verified coding agent.

Usage:

    import anvil

    # Simple task execution
    result = anvil.run("fix the failing tests in src/app.py")
    print(result.output)

    # With agent selection
    result = anvil.run("analyze the codebase", agent="plan")

    # With model selection
    result = anvil.run("add OAuth2 auth", model="gpt-4o")

    # With verification
    result = anvil.run("refactor auth module", verify=True, max_iterations=5)

    # Streaming
    for chunk in anvil.stream("write a new endpoint"):
        print(chunk, end="")

    # Session management
    session = anvil.Session()
    session.ask("explain the auth module")
    session.ask("now add 2FA to it")
    session.save("my-session.json")

    # Undo/Redo
    session.undo()
    session.redo()

    # Verify without changes
    report = anvil.verify(["src/app.py", "src/auth.py"])
    for r in report.results:
        print(f"{r.file_path}: {r.status}")

    # Cost tracking
    print(f"Tokens: {session.tokens}")
    print(f"Cost: ${session.cost:.4f}")

    # Agent management
    agents = anvil.agents.list()
    anvil.agents.switch("plan")

    # Custom agent creation
    anvil.agents.create(
        name="security-reviewer",
        description="Reviews code for security vulnerabilities",
        mode="subagent",
        permission={"edit": "deny", "bash": "deny"},
    )
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from collections.abc import AsyncGenerator, Generator
from dataclasses import dataclass, field
from pathlib import Path

from anvil.agents.agent_base import BaseAgent
from anvil.agents.agent_manager import AgentManager
from anvil.agents.builtin_agents import BUILTIN_AGENTS
from anvil.core.config import AnvilConfig
from anvil.core.engine import AnvilEngine
from anvil.core.session import Session
from anvil.core.snapshot import SnapshotManager
from anvil.models.registry import BaseModel, Message, ModelRegistry
from anvil.verify.pipeline import VerifyPipeline, VerifyReport

# ── Result types ──────────────────────────────────────────────────────────

@dataclass
class SDKResult:
    """Result of an anvil.run() call."""
    output: str
    success: bool
    error: str | None = None
    verify_report: VerifyReport | None = None
    agent_name: str = "build"
    session_id: str = ""
    tokens_used: int = 0
    cost_usd: float = 0.0
    duration_ms: float = 0.0
    file_changes: list[dict] = field(default_factory=list)

    def __str__(self) -> str:
        status = "✓" if self.success else "✗"
        return f"{status} {self.output[:200]}"

    def __repr__(self) -> str:
        return f"SDKResult(success={self.success}, output={self.output[:100]!r})"

    def __bool__(self) -> bool:
        return self.success


@dataclass
class SDKVerifyResult:
    """Result of an anvil.verify() call."""
    results: list[dict] = field(default_factory=list)
    passed: bool = True
    overall: str = "pass"

    def __str__(self) -> str:
        icon = "✓" if self.passed else "✗"
        return f"{icon} {self.overall.upper()}: {len(self.results)} checks"


# ── Session class ─────────────────────────────────────────────────────────

class SDKSession:
    """Persistent conversation session with history, undo/redo, and cost tracking."""

    def __init__(
        self,
        config: AnvilConfig | None = None,
        agent: str | None = None,
        model: str | None = None,
        session_id: str | None = None,
    ):
        self.config = config or AnvilConfig()
        if model:
            self.config.model.model = model
        if agent:
            self.config.default_agent = agent

        self._session_id = session_id or str(uuid.uuid4())[:8]
        self._engine: AnvilEngine | None = None
        self._interactions: list[dict] = []
        self._total_tokens = 0
        self._total_cost = 0.0
        self._start_time = time.time()
        self._snapshot_manager: SnapshotManager | None = None

    @property
    def engine(self) -> AnvilEngine:
        if self._engine is None:
            agent_obj = BUILTIN_AGENTS.get(self.config.default_agent, BUILTIN_AGENTS["build"])
            if callable(agent_obj) and not isinstance(agent_obj, BaseAgent):
                agent_obj = agent_obj()
            self._engine = AnvilEngine(self.config, agent=agent_obj)
        return self._engine

    @property
    def id(self) -> str:
        return self._session_id

    @property
    def tokens(self) -> int:
        return self._total_tokens

    @property
    def cost(self) -> float:
        return self._total_cost

    @property
    def duration(self) -> float:
        return time.time() - self._start_time

    @property
    def history(self) -> list[dict]:
        return list(self._interactions)

    def ask(self, task: str, **kwargs) -> SDKResult:
        """Execute a task within this session."""
        result = self.engine.run(task, max_iterations=kwargs.get("max_iterations", 20))

        self._interactions.append({
            "task": task,
            "output": result.output,
            "success": result.success,
            "agent": result.agent_name,
            "timestamp": time.time(),
        })

        if result.session:
            self._total_tokens += result.session.stats.total_tokens
            self._total_cost += result.session.stats.total_cost_usd

        return SDKResult(
            output=result.output,
            success=result.success,
            error=result.error,
            verify_report=result.verify_report,
            agent_name=result.agent_name,
            session_id=self._session_id,
            tokens_used=self._total_tokens,
            cost_usd=self._total_cost,
            duration_ms=(time.time() - self._start_time) * 1000,
        )

    def switch_agent(self, agent_name: str) -> None:
        """Switch to a different agent."""
        self.engine.switch_agent(agent_name)
        self.config.default_agent = agent_name

    def undo(self) -> None:
        """Undo the last change using snapshots."""
        if self._snapshot_manager is None:
            self._snapshot_manager = SnapshotManager(self.config.project_root)
        snap = self._snapshot_manager.undo()
        if snap:
            self._interactions.append({
                "task": f"undo: {snap.description}",
                "output": f"Reverted to {snap.name}",
                "success": True,
                "agent": "system",
                "timestamp": time.time(),
            })

    def redo(self) -> None:
        """Redo the last undone change."""
        if self._snapshot_manager is None:
            self._snapshot_manager = SnapshotManager(self.config.project_root)
        snap = self._snapshot_manager.redo()
        if snap:
            self._interactions.append({
                "task": f"redo: {snap.description}",
                "output": f"Re-applied {snap.name}",
                "success": True,
                "agent": "system",
                "timestamp": time.time(),
            })

    def save(self, path: str | None = None) -> str:
        """Save session to a JSON file."""
        save_path = Path(path) if path else Path.home() / ".anvil" / "sessions" / f"{self._session_id}.json"
        save_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "session_id": self._session_id,
            "start_time": self._start_time,
            "total_tokens": self._total_tokens,
            "total_cost": self._total_cost,
            "config": self.config.to_dict(),
            "interactions": self._interactions,
        }
        save_path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        return str(save_path)

    @classmethod
    def load(cls, path: str) -> SDKSession:
        """Load a session from a JSON file."""
        filepath = Path(path)
        data = json.loads(filepath.read_text(encoding="utf-8"))

        config = AnvilConfig._from_dict(data.get("config", {}))
        session = cls(config=config, session_id=data.get("session_id"))
        session._start_time = data.get("start_time", time.time())
        session._total_tokens = data.get("total_tokens", 0)
        session._total_cost = data.get("total_cost", 0.0)
        session._interactions = data.get("interactions", [])
        return session

    def verify(self, files: list[str], **kwargs) -> SDKVerifyResult:
        """Verify files within this session context."""
        pipeline = VerifyPipeline(self.config.verify)
        report = pipeline.verify(
            files=files,
            test_command=kwargs.get("test_command"),
            working_dir=self.config.project_root,
            checks=kwargs.get("checks"),
        )
        return SDKVerifyResult(
            results=[
                {
                    "checker": r.checker,
                    "status": r.status.value,
                    "message": r.message,
                    "file_path": r.file_path,
                }
                for r in report.results
            ],
            passed=report.passed,
            overall=report.overall.value,
        )


# ── Agent management ──────────────────────────────────────────────────────

class SDKAgentManager:
    """Manage agents through the SDK."""

    def __init__(self, config: AnvilConfig | None = None):
        self.config = config or AnvilConfig()
        self._manager = AgentManager(
            config_dir=Path.home() / ".config" / "anvil",
            project_dir=Path(self.config.project_root),
        )

    def list(self) -> list[dict]:
        """List all available agents."""
        return [
            {
                "name": a.name,
                "mode": a.mode.value,
                "model": a.model,
                "description": a.description,
                "max_steps": a.max_steps,
                "color": a.color,
                "is_primary": a.is_primary,
                "is_subagent": a.is_subagent,
            }
            for a in self._manager.list_agents(include_hidden=False)
        ]

    def switch(self, name: str) -> dict:
        """Switch to a different agent."""
        agent = self._manager.switch(name)
        self.config.default_agent = name
        return {
            "name": agent.name,
            "mode": agent.mode.value,
            "description": agent.description,
            "model": agent.model,
        }

    def get(self, name: str) -> dict | None:
        """Get details for a specific agent."""
        agent = self._manager.get(name)
        if agent is None:
            return None
        return {
            "name": agent.name,
            "mode": agent.mode.value,
            "model": agent.model,
            "description": agent.description,
            "max_steps": agent.max_steps,
            "color": agent.color,
        }

    def create(
        self,
        name: str,
        description: str = "",
        mode: str = "subagent",
        model: str = "local",
        temperature: float = 0.2,
        max_steps: int = 20,
        tools_whitelist: list[str] | None = None,
        tools_blacklist: list[str] | None = None,
        permission: dict[str, str] | None = None,
        prompt_template: str = "",
        hidden: bool = False,
        color: str = "white",
    ) -> dict:
        """Create a custom agent."""
        perm_config = {}
        if permission:
            perm_config = permission

        spec = {
            "description": description or f"Custom agent: {name}",
            "mode": mode,
            "model": model,
            "temperature": temperature,
            "top_p": 1.0,
            "max_steps": max_steps,
            "tools_whitelist": tools_whitelist or [],
            "tools_blacklist": tools_blacklist or [],
            "permission": perm_config,
            "prompt_template": prompt_template,
            "hidden": hidden,
            "color": color,
        }

        agent = self._manager.create_agent_from_dict(name, spec)

        agents_dir = Path(self.config.project_root) / ".anvil" / "agents"
        agents_dir.mkdir(parents=True, exist_ok=True)
        spec_file = agents_dir / f"{name}.json"
        spec_file.write_text(json.dumps({name: spec}, indent=2), encoding="utf-8")

        return {
            "name": agent.name,
            "mode": agent.mode.value,
            "description": agent.description,
            "model": agent.model,
            "max_steps": agent.max_steps,
        }

    def invoke(self, name: str, task: str, model: BaseModel | None = None) -> dict:
        """Invoke a subagent directly."""
        invocation = self._manager.invoke_subagent(
            name=name,
            task=task,
            model=model,
            working_dir=self.config.project_root,
        )
        return {
            "agent_name": invocation.agent_name,
            "task": invocation.task,
            "response": invocation.response,
            "success": invocation.success,
            "duration_ms": invocation.duration_ms,
        }


# ── Top-level API ─────────────────────────────────────────────────────────

_default_config: AnvilConfig | None = None
_default_agents: SDKAgentManager | None = None


def _get_config(**kwargs) -> AnvilConfig:
    global _default_config
    if _default_config is None:
        _default_config = AnvilConfig()
    config = AnvilConfig._from_dict(_default_config.to_dict())
    if "model" in kwargs:
        config.model.model = kwargs["model"]
    if "agent" in kwargs:
        config.default_agent = kwargs["agent"]
    if "project_root" in kwargs:
        config.project_root = kwargs["project_root"]
    if "verify" in kwargs:
        config.verify.enabled = kwargs["verify"]
    if "max_iterations" in kwargs:
        config.verify.max_retries = kwargs["max_iterations"]
    if "api_key" in kwargs:
        config.model.api_key = kwargs["api_key"]
    if "api_base" in kwargs:
        config.model.api_base = kwargs["api_base"]
    return config


def run(
    task: str,
    agent: str | None = None,
    model: str | None = None,
    verify: bool = True,
    max_iterations: int = 20,
    auto_recover: bool = True,
    project_root: str | None = None,
    api_key: str | None = None,
    api_base: str | None = None,
    **kwargs,
) -> SDKResult:
    """Execute a task with self-verification.

    Args:
        task: The task to execute.
        agent: Agent to use (e.g., "build", "plan", "explore", "scout").
        model: Model to use (e.g., "local", "gpt-4o", "claude-3.5-sonnet").
        verify: Whether to verify the output.
        max_iterations: Maximum verify-recover cycles.
        auto_recover: Whether to automatically recover from errors.
        project_root: Project root directory.
        api_key: API key for the model.
        api_base: API base URL for the model.

    Returns:
        SDKResult with output, success status, and verification report.
    """
    config = _get_config(
        model=model,
        agent=agent,
        project_root=project_root or os.getcwd(),
        verify=verify,
        max_iterations=max_iterations,
        api_key=api_key,
        api_base=api_base,
        **{k: v for k, v in kwargs.items() if k in ("project_root",)},
    )
    config.verify.auto_recover = auto_recover

    agent_name = agent or config.default_agent
    agent_obj = BUILTIN_AGENTS.get(agent_name)
    if agent_obj is None:
        mgr = AgentManager()
        agent_obj = mgr.get(agent_name)
    if callable(agent_obj) and not isinstance(agent_obj, BaseAgent):
        agent_obj = agent_obj()

    engine = AnvilEngine(config, agent=agent_obj)
    result = engine.run(task, max_iterations=max_iterations)

    tokens = result.session.stats.total_tokens if result.session else 0
    cost = result.session.stats.total_cost_usd if result.session else 0.0
    duration = result.session.stats.duration_seconds * 1000 if result.session else 0.0

    return SDKResult(
        output=result.output,
        success=result.success,
        error=result.error,
        verify_report=result.verify_report,
        agent_name=result.agent_name,
        session_id=result.session.id if result.session else "",
        tokens_used=tokens,
        cost_usd=cost,
        duration_ms=duration,
    )


def stream(
    task: str,
    agent: str | None = None,
    model: str | None = None,
    **kwargs,
) -> Generator[str, None, None]:
    """Stream output from a task execution.

    Args:
        task: The task to execute.
        agent: Agent to use.
        model: Model to use.

    Yields:
        Chunks of output text as they are generated.
    """
    config = _get_config(model=model, agent=agent, **kwargs)

    agent_name = agent or config.default_agent
    agent_obj = BUILTIN_AGENTS.get(agent_name)
    if agent_obj is None:
        mgr = AgentManager()
        agent_obj = mgr.get(agent_name)
    if callable(agent_obj) and not isinstance(agent_obj, BaseAgent):
        agent_obj = agent_obj()

    model_backend = ModelRegistry.create(
        agent_obj.model,
        api_key=config.model.api_key,
        api_base=config.model.api_base,
    )

    from anvil.core.engine import ALL_TOOL_NAMES, SYSTEM_PROMPT
    available_tools = agent_obj.available_tools(ALL_TOOL_NAMES)
    messages = [
        Message(role="system", content=SYSTEM_PROMPT.format(
            agent_name=agent_obj.name,
            tools=", ".join(available_tools),
        )),
        Message(role="user", content=task),
    ]

    for chunk in model_backend.stream(messages, temperature=agent_obj.temperature):
        yield chunk


async def arun(
    task: str,
    agent: str | None = None,
    model: str | None = None,
    verify: bool = True,
    max_iterations: int = 20,
    **kwargs,
) -> SDKResult:
    """Async version of run().

    Currently executes synchronously in a thread pool.
    """
    import concurrent.futures
    loop = asyncio.get_event_loop()
    with concurrent.futures.ThreadPoolExecutor() as pool:
        result = await loop.run_in_executor(
            pool,
            lambda: run(task, agent=agent, model=model, verify=verify,
                        max_iterations=max_iterations, **kwargs),
        )
    return result


async def astream(
    task: str,
    agent: str | None = None,
    model: str | None = None,
    **kwargs,
) -> AsyncGenerator[str, None]:
    """Async version of stream().

    Yields chunks as they become available.
    """
    import concurrent.futures
    gen = stream(task, agent=agent, model=model, **kwargs)
    loop = asyncio.get_event_loop()
    with concurrent.futures.ThreadPoolExecutor() as pool:
        while True:
            try:
                chunk = await loop.run_in_executor(pool, next, gen)
                yield chunk
            except StopIteration:
                break


def verify(
    files: list[str],
    checks: list[str] | None = None,
    test_command: str | None = None,
    working_dir: str | None = None,
    **kwargs,
) -> SDKVerifyResult:
    """Verify files without making changes.

    Args:
        files: List of file paths to verify.
        checks: Checks to run (syntax, lint, tests, imports).
        test_command: Test command to run.
        working_dir: Working directory.

    Returns:
        SDKVerifyResult with verification results.
    """
    config = _get_config(project_root=working_dir or os.getcwd(), **kwargs)
    pipeline = VerifyPipeline(config.verify)
    report = pipeline.verify(
        files=files,
        test_command=test_command,
        working_dir=config.project_root,
        checks=checks,
    )
    return SDKVerifyResult(
        results=[
            {
                "checker": r.checker,
                "status": r.status.value,
                "message": r.message,
                "file_path": r.file_path,
                "details": r.details,
            }
            for r in report.results
        ],
        passed=report.passed,
        overall=report.overall.value,
    )


def create_session(
    config: AnvilConfig | None = None,
    agent: str | None = None,
    model: str | None = None,
    session_id: str | None = None,
) -> SDKSession:
    """Create a new session for multi-turn interaction.

    Args:
        config: Optional AnvilConfig to use.
        agent: Default agent name.
        model: Default model name.
        session_id: Optional session ID.

    Returns:
        SDKSession instance.
    """
    return SDKSession(config=config, agent=agent, model=model, session_id=session_id)


def configure(**kwargs) -> None:
    """Set global configuration defaults.

    Accepted keyword arguments:
        model, api_key, api_base, verify, max_iterations, project_root, etc.
    """
    global _default_config
    if _default_config is None:
        _default_config = AnvilConfig()

    if "model" in kwargs:
        _default_config.model.model = kwargs["model"]
    if "api_key" in kwargs:
        _default_config.model.api_key = kwargs["api_key"]
    if "api_base" in kwargs:
        _default_config.model.api_base = kwargs["api_base"]
    if "project_root" in kwargs:
        _default_config.project_root = kwargs["project_root"]
    if "verify" in kwargs:
        _default_config.verify.enabled = kwargs["verify"]
    if "default_agent" in kwargs:
        _default_config.default_agent = kwargs["default_agent"]
    if "max_iterations" in kwargs:
        _default_config.verify.max_retries = kwargs["max_iterations"]


class _AgentsProxy:
    """Proxy object for anvil.agents that delegates to SDKAgentManager."""

    def __init__(self):
        self._manager: SDKAgentManager | None = None

    @property
    def manager(self) -> SDKAgentManager:
        if self._manager is None:
            self._manager = SDKAgentManager()
        return self._manager

    def list(self) -> list[dict]:
        return self.manager.list()

    def switch(self, name: str) -> dict:
        return self.manager.switch(name)

    def get(self, name: str) -> dict | None:
        return self.manager.get(name)

    def create(self, **kwargs) -> dict:
        return self.manager.create(**kwargs)

    def invoke(self, name: str, task: str, **kwargs) -> dict:
        return self.manager.invoke(name, task, **kwargs)


agents = _AgentsProxy()

import os
