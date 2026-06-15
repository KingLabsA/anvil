"""Anvil configuration — with agent, permission, and compaction sections."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from anvil.permissions.permissions import PermissionConfig


@dataclass
class ModelConfig:
    model: str = "shellwhisperer"
    api_base: str | None = None
    api_key: str | None = None
    max_tokens: int = 4096
    temperature: float = 0.2
    context_window: int = 8192
    system_prompt: str | None = None


@dataclass
class VerifyConfig:
    enabled: bool = True
    auto_recover: bool = True
    max_retries: int = 3
    check_syntax: bool = True
    check_tests: bool = True
    check_lint: bool = True
    check_types: bool = False
    timeout_seconds: int = 30


@dataclass
class ToolConfig:
    allow_shell: bool = True
    allow_file_write: bool = True
    allow_file_read: bool = True
    allow_web: bool = False
    sandbox: bool = False
    max_file_size_mb: int = 10
    working_dir: str = field(default_factory=lambda: os.getcwd())


@dataclass
class DaemonConfig:
    enabled: bool = False
    port: int = 8765
    persist_state: bool = True
    state_dir: str = field(default_factory=lambda: str(Path.home() / ".anvil" / "state"))


@dataclass
class TelemetryConfig:
    enabled: bool = True
    track_tokens: bool = True
    track_errors: bool = True
    track_recoveries: bool = True
    export_path: str | None = None


@dataclass
class SafetyConfig:
    constitution_enabled: bool = True
    max_edit_lines: int = 500
    blocked_commands: list = field(default_factory=lambda: [
        "rm -rf /", "mkfs", "dd if=", ":(){ :|:&", "fork bomb",
    ])
    require_confirmation_for: list = field(default_factory=lambda: [
        "git push", "git reset --hard", "DROP TABLE", "DELETE FROM",
    ])


@dataclass
class CostConfig:
    max_cost_per_session_usd: float = 5.0
    max_cost_per_task_usd: float = 1.0
    warn_at_percent: int = 80
    route_by_complexity: bool = True
    simple_model: str = "local"
    complex_model: str = "local"


@dataclass
class AgentDefinition:
    """Inline agent definition that lives in the config file.

    This is the config-file representation; AgentManager converts them
    into :class:`BaseAgent` instances at runtime.
    """
    description: str = ""
    mode: str = "subagent"
    model: str = "local"
    temperature: float = 0.2
    top_p: float = 1.0
    max_steps: int = 20
    tools_whitelist: list[str] = field(default_factory=list)
    tools_blacklist: list[str] = field(default_factory=list)
    permission: dict[str, str] = field(default_factory=dict)
    prompt_template: str = ""
    hidden: bool = False
    color: str = "white"
    extra: dict = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentDefinition:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def to_dict(self) -> dict[str, Any]:
        from dataclasses import asdict
        return asdict(self)


@dataclass
class CompactionConfig:
    """Context-window compaction settings.

    Modes
    -----
    auto : str
        "prune" — drop old messages beyond a threshold.
        "summarise" — run the compaction agent to compress history.
        "off" — never compact (risk running out of context).
    reserved_tokens : int
        Number of tokens to keep free for model output / tool responses.
    prune_threshold : float
        Fraction of context_window at which compaction triggers (0.0–1.0).
    """
    mode: str = "summarise"
    reserved_tokens: int = 2048
    prune_threshold: float = 0.75


@dataclass
class AnvilConfig:
    model: ModelConfig = field(default_factory=ModelConfig)
    verify: VerifyConfig = field(default_factory=VerifyConfig)
    tools: ToolConfig = field(default_factory=ToolConfig)
    daemon: DaemonConfig = field(default_factory=DaemonConfig)
    telemetry: TelemetryConfig = field(default_factory=TelemetryConfig)
    safety: SafetyConfig = field(default_factory=SafetyConfig)
    cost: CostConfig = field(default_factory=CostConfig)
    agent: dict[str, AgentDefinition] = field(default_factory=dict)
    permission: dict[str, str] = field(default_factory=lambda: {"*": "allow"})
    default_agent: str = "build"
    compaction: CompactionConfig = field(default_factory=CompactionConfig)
    verbose: bool = False
    quiet: bool = False
    project_root: str = field(default_factory=lambda: os.getcwd())
    skills_dir: str | None = None

    @classmethod
    def from_file(cls, path: Path) -> AnvilConfig:
        import json
        data = json.loads(path.read_text())
        return cls._from_dict(data)

    @classmethod
    def _from_dict(cls, data: dict[str, Any]) -> AnvilConfig:
        agents_raw = data.pop("agent", {})
        agents = {
            name: AgentDefinition.from_dict(spec) if isinstance(spec, dict) else spec
            for name, spec in agents_raw.items()
        }
        permission_raw = data.pop("permission", {"*": "allow"})
        compaction_raw = data.pop("compaction", {})

        return cls(
            model=ModelConfig(**data.get("model", {})),
            verify=VerifyConfig(**data.get("verify", {})),
            tools=ToolConfig(**data.get("tools", {})),
            daemon=DaemonConfig(**data.get("daemon", {})),
            telemetry=TelemetryConfig(**data.get("telemetry", {})),
            safety=SafetyConfig(**data.get("safety", {})),
            cost=CostConfig(**data.get("cost", {})),
            agent=agents,
            permission=permission_raw,
            default_agent=data.get("default_agent", "build"),
            compaction=CompactionConfig(**compaction_raw) if isinstance(compaction_raw, dict) else CompactionConfig(),
            verbose=data.get("verbose", False),
            quiet=data.get("quiet", False),
            project_root=data.get("project_root", os.getcwd()),
        )

    def to_dict(self) -> dict[str, Any]:
        from dataclasses import asdict
        d = {
            "model": asdict(self.model),
            "verify": asdict(self.verify),
            "tools": asdict(self.tools),
            "daemon": asdict(self.daemon),
            "telemetry": asdict(self.telemetry),
            "safety": asdict(self.safety),
            "cost": asdict(self.cost),
            "agent": {name: spec.to_dict() for name, spec in self.agent.items()},
            "permission": dict(self.permission),
            "default_agent": self.default_agent,
            "compaction": asdict(self.compaction),
            "verbose": self.verbose,
            "quiet": self.quiet,
            "project_root": self.project_root,
        }
        return d

    def to_file(self, path: Path) -> None:
        import json
        path.write_text(json.dumps(self.to_dict(), indent=2))

    @classmethod
    def find_config(cls) -> AnvilConfig:
        candidates = [
            Path(".anvil.json"),
            Path("anvil.json"),
            Path.home() / ".anvil" / "config.json",
        ]
        for p in candidates:
            if p.exists():
                return cls.from_file(p)
        return cls()

    def get_global_permission_config(self) -> PermissionConfig:
        """Convert the config-level permission dict into a PermissionConfig."""
        return PermissionConfig.from_dict(self.permission)

    def get_agent_definitions(self) -> dict[str, AgentDefinition]:
        """Return all agent definitions from config (not builtins)."""
        return dict(self.agent)
