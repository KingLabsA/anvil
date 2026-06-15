"""OpenCode-compatible configuration system for Anvil.

Supports opencode.json, anvil.json, and legacy anvil.toml.
Precedence: env vars > project config > global config > defaults.
Supports variable substitution: {env:VAR} and {file:path}.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


def _substitute_vars(value: Any) -> Any:
    """Substitute {env:VAR} and {file:path} patterns in string values."""
    if not isinstance(value, str):
        return value

    def _replace_env(match: re.Match) -> str:
        var_name = match.group(1)
        result = os.environ.get(var_name, "")
        return result

    def _replace_file(match: re.Match) -> str:
        file_path = match.group(1)
        try:
            return Path(file_path).read_text(encoding="utf-8").strip()
        except (FileNotFoundError, OSError):
            return ""

    result = re.sub(r"\{env:([^}]+)\}", _replace_env, value)
    result = re.sub(r"\{file:([^}]+)\}", _replace_file, result)
    return result


def _deep_substitute(data: Any) -> Any:
    """Recursively substitute variables in a nested dict/list structure."""
    if isinstance(data, dict):
        return {k: _deep_substitute(_substitute_vars(v) if isinstance(v, str) else _deep_substitute(v)) for k, v in data.items()}
    if isinstance(data, list):
        return [_deep_substitute(_substitute_vars(item) if isinstance(item, str) else _deep_substitute(item)) for item in data]
    if isinstance(data, str):
        return _substitute_vars(data)
    return data


@dataclass
class ModelConfigV2:
    name: str = "local"
    api_key: str | None = None
    api_base: str | None = None
    max_tokens: int = 4096
    temperature: float = 0.2
    context_window: int = 128000
    system_prompt: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ModelConfigV2:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class AgentConfig:
    name: str = "anvil"
    description: str = ""
    model: str = ""
    system_prompt: str | None = None
    tools: list[str] = field(default_factory=list)
    max_iterations: int = 20
    auto_snapshot: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentConfig:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class PermissionConfig:
    allow_shell: bool = True
    allow_file_write: bool = True
    allow_file_read: bool = True
    allow_web: bool = False
    sandbox: bool = False
    max_file_size_mb: int = 10
    confirm_dangerous: bool = True
    blocked_commands: list[str] = field(default_factory=lambda: [
        "rm -rf /", "mkfs", "dd if=", ":(){ :|:&", "fork bomb",
    ])
    confirm_patterns: list[str] = field(default_factory=lambda: [
        "git push", "git reset --hard", "DROP TABLE", "DELETE FROM",
    ])

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ToolsConfig:
    working_dir: str = ""
    timeout: int = 30
    max_concurrent: int = 1
    enabled: list[str] = field(default_factory=lambda: [
        "bash", "read", "write", "edit", "grep", "glob", "ls",
        "apply_patch", "todowrite", "webfetch", "websearch", "question", "image",
    ])

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class MCPConfig:
    servers: dict[str, dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ServerConfig:
    port: int = 8765
    host: str = "localhost"
    persist_state: bool = True
    state_dir: str = ""
    cors_origins: list[str] = field(default_factory=lambda: ["*"])

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ServerConfig:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class SnapshotConfig:
    enabled: bool = True
    auto_snapshot: bool = True
    use_git: bool = True
    max_undo_levels: int = 50
    state_dir: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CompactionConfigV2:
    auto: bool = True
    prune: bool = True
    reserved: int = 8000
    max_context: int = 128000

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class WatcherConfig:
    enabled: bool = False
    patterns: list[str] = field(default_factory=lambda: ["**/*.py", "**/*.js", "**/*.ts"])
    ignore_patterns: list[str] = field(default_factory=lambda: ["**/node_modules/**", "**/.git/**", "**/__pycache__/**"])
    debounce_ms: int = 300

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class FormatterConfig:
    python: str = "ruff format"
    javascript: str = "prettier --write"
    typescript: str = "prettier --write"
    go: str = "gofmt"
    rust: str = "rustfmt"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class LSPConfig:
    enabled: bool = False
    servers: dict[str, dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SharingConfig:
    enabled: bool = True
    base_url: str = "https://anvil.sh/s"
    export_format: str = "json"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CommandConfig:
    builtin_commands: list[str] = field(default_factory=lambda: [
        "help", "init", "undo", "redo", "share", "compact", "agents", "models",
    ])
    custom_commands: dict[str, dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CostConfigV2:
    max_cost_per_session_usd: float = 5.0
    max_cost_per_task_usd: float = 1.0
    warn_at_percent: int = 80
    route_by_complexity: bool = True
    simple_model: str = "local"
    complex_model: str = "local"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class VerifyConfigV2:
    enabled: bool = True
    auto_recover: bool = True
    max_retries: int = 3
    check_syntax: bool = True
    check_tests: bool = True
    check_lint: bool = True
    check_types: bool = True
    timeout_seconds: int = 30

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AnvilConfigV2:
    """Full OpenCode-compatible configuration with all sections."""
    model: ModelConfigV2 = field(default_factory=ModelConfigV2)
    agent: AgentConfig = field(default_factory=AgentConfig)
    permission: PermissionConfig = field(default_factory=PermissionConfig)
    tools: ToolsConfig = field(default_factory=ToolsConfig)
    mcp: MCPConfig = field(default_factory=MCPConfig)
    server: ServerConfig = field(default_factory=ServerConfig)
    snapshot: SnapshotConfig = field(default_factory=SnapshotConfig)
    compaction: CompactionConfigV2 = field(default_factory=CompactionConfigV2)
    watcher: WatcherConfig = field(default_factory=WatcherConfig)
    formatter: FormatterConfig = field(default_factory=FormatterConfig)
    lsp: LSPConfig = field(default_factory=LSPConfig)
    sharing: SharingConfig = field(default_factory=SharingConfig)
    command: CommandConfig = field(default_factory=CommandConfig)
    cost: CostConfigV2 = field(default_factory=CostConfigV2)
    verify: VerifyConfigV2 = field(default_factory=VerifyConfigV2)
    project_root: str = ""
    verbose: bool = False
    quiet: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, default=str)

    def to_opencode_json(self) -> str:
        """Export to opencode.json-compatible format."""
        data = self.to_dict()
        opencode_data = {
            "model": data["model"],
            "agent": data["agent"],
            "permission": data["permission"],
            "tools": data["tools"],
            "mcp": data["mcp"],
            "server": data["server"],
            "snapshot": data["snapshot"],
            "compaction": data["compaction"],
            "watcher": data["watcher"],
            "formatter": data["formatter"],
            "lsp": data["lsp"],
            "sharing": data["sharing"],
            "command": data["command"],
        }
        return json.dumps(opencode_data, indent=2, default=str)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AnvilConfigV2:
        config = cls()
        if "model" in data:
            config.model = ModelConfigV2.from_dict(data["model"])
        if "agent" in data:
            config.agent = AgentConfig.from_dict(data["agent"])
        if "permission" in data:
            config.permission = PermissionConfig(**{k: v for k, v in data["permission"].items() if k in PermissionConfig.__dataclass_fields__})
        if "tools" in data:
            config.tools = ToolsConfig(**{k: v for k, v in data["tools"].items() if k in ToolsConfig.__dataclass_fields__})
        if "mcp" in data:
            config.mcp = MCPConfig(servers=data["mcp"].get("servers", {}))
        if "server" in data:
            config.server = ServerConfig.from_dict(data["server"])
        if "snapshot" in data:
            config.snapshot = SnapshotConfig(**{k: v for k, v in data["snapshot"].items() if k in SnapshotConfig.__dataclass_fields__})
        if "compaction" in data:
            config.compaction = CompactionConfigV2(**{k: v for k, v in data["compaction"].items() if k in CompactionConfigV2.__dataclass_fields__})
        if "watcher" in data:
            config.watcher = WatcherConfig(**{k: v for k, v in data["watcher"].items() if k in WatcherConfig.__dataclass_fields__})
        if "formatter" in data:
            config.formatter = FormatterConfig(**{k: v for k, v in data["formatter"].items() if k in FormatterConfig.__dataclass_fields__})
        if "lsp" in data:
            config.lsp = LSPConfig(**{k: v for k, v in data["lsp"].items() if k in LSPConfig.__dataclass_fields__})
        if "sharing" in data:
            config.sharing = SharingConfig(**{k: v for k, v in data["sharing"].items() if k in SharingConfig.__dataclass_fields__})
        if "command" in data:
            config.command = CommandConfig(**{k: v for k, v in data["command"].items() if k in CommandConfig.__dataclass_fields__})
        if "cost" in data:
            config.cost = CostConfigV2(**{k: v for k, v in data["cost"].items() if k in CostConfigV2.__dataclass_fields__})
        if "verify" in data:
            config.verify = VerifyConfigV2(**{k: v for k, v in data["verify"].items() if k in VerifyConfigV2.__dataclass_fields__})
        config.project_root = data.get("project_root", "")
        config.verbose = data.get("verbose", False)
        config.quiet = data.get("quiet", False)
        return config

    @classmethod
    def load(cls, project_dir: str | None = None) -> AnvilConfigV2:
        """Load config from multiple sources with precedence.

        Precedence: env vars > project config > global config > defaults
        Config files (in order): opencode.json, anvil.json, .anvil/config.json
        """
        config = cls()
        project_root = Path(project_dir) if project_dir else Path.cwd()

        global_config = cls._load_global_config()
        if global_config:
            config = cls._merge_configs(config, global_config)

        project_config = cls._load_project_config(project_root)
        if project_config:
            config = cls._merge_configs(config, project_config)

        config = cls._apply_env_overrides(config)
        config = cls._apply_variable_substitution(config)
        config.project_root = str(project_root)

        if not config.tools.working_dir:
            config.tools.working_dir = str(project_root)
        if not config.server.state_dir:
            config.server.state_dir = str(Path.home() / ".anvil" / "state")
        if not config.snapshot.state_dir:
            config.snapshot.state_dir = str(project_root / ".anvil" / "snapshots")

        return config

    @classmethod
    def _load_global_config(cls) -> dict[str, Any] | None:
        """Load global config from ~/.config/anvil/config.json."""
        global_path = Path.home() / ".config" / "anvil" / "config.json"
        if global_path.exists():
            try:
                return json.loads(global_path.read_text())
            except (json.JSONDecodeError, OSError):
                pass
        return None

    @classmethod
    def _load_project_config(cls, project_root: Path) -> dict[str, Any] | None:
        """Load project config from opencode.json, anvil.json, or .anvil/config.json."""
        candidates = [
            project_root / "opencode.json",
            project_root / "opencode.jsonc",
            project_root / "anvil.json",
            project_root / ".anvil" / "config.json",
        ]
        for path in candidates:
            if path.exists():
                try:
                    content = path.read_text()
                    return json.loads(content)
                except (json.JSONDecodeError, OSError):
                    continue

        toml_path = project_root / "anvil.toml"
        if toml_path.exists():
            return cls._load_toml(toml_path)

        return None

    @classmethod
    def _load_toml(cls, path: Path) -> dict[str, Any] | None:
        """Load legacy anvil.toml format (simple key=value parser)."""
        try:
            import tomllib
            return tomllib.loads(path.read_text())
        except ImportError:
            pass
        except Exception:
            pass

        data: dict[str, Any] = {}
        current_section: str | None = None
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("[") and line.endswith("]"):
                current_section = line[1:-1].strip()
                if current_section not in data:
                    data[current_section] = {}
                continue
            if "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if current_section:
                    data[current_section][key] = value
                else:
                    data[key] = value
        return data

    @classmethod
    def _apply_env_overrides(cls, config: AnvilConfigV2) -> AnvilConfigV2:
        """Apply environment variable overrides."""
        env_map = {
            "ANVIL_MODEL": ("model", "name"),
            "ANVIL_API_KEY": ("model", "api_key"),
            "ANVIL_API_BASE": ("model", "api_base"),
            "ANVIL_MAX_TOKENS": ("model", "max_tokens"),
            "ANVIL_TEMPERATURE": ("model", "temperature"),
            "ANVIL_VERBOSE": ("verbose", None),
            "ANVIL_QUIET": ("quiet", None),
            "ANVIL_SANDBOX": ("permission", "sandbox"),
        }
        for env_var, (section, key) in env_map.items():
            value = os.environ.get(env_var)
            if value is None:
                continue
            if section == "verbose":
                config.verbose = value.lower() in ("1", "true", "yes")
            elif section == "quiet":
                config.quiet = value.lower() in ("1", "true", "yes")
            elif section == "model" and key:
                setattr(config.model, key, value)
            elif section == "permission" and key:
                setattr(config.permission, key, value.lower() in ("1", "true", "yes"))
        return config

    @classmethod
    def _apply_variable_substitution(cls, config: AnvilConfigV2) -> AnvilConfigV2:
        """Apply {env:VAR} and {file:path} substitution to all string fields."""
        data = config.to_dict()
        substituted = _deep_substitute(data)
        return cls.from_dict(substituted)

    @classmethod
    def _merge_configs(cls, base: AnvilConfigV2, override: dict[str, Any]) -> AnvilConfigV2:
        """Merge a base config with an override dict."""
        base_dict = base.to_dict()
        merged = cls._deep_merge(base_dict, override)
        return cls.from_dict(merged)

    @staticmethod
    def _deep_merge(base: dict, override: dict) -> dict:
        """Deep merge two dicts, override takes precedence."""
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = AnvilConfigV2._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    def save(self, path: str | None = None) -> None:
        """Save config to a file."""
        target = Path(path) if path else Path(self.project_root) / "anvil.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(self.to_json())

    def migrate_from_v1(self, v1_config: Any) -> None:
        """Migrate from legacy AnvilConfig (v1) to V2."""
        from anvil.core.config import AnvilConfig as V1Config
        if isinstance(v1_config, V1Config):
            self.model.name = v1_config.model.model
            self.model.api_key = v1_config.model.api_key
            self.model.api_base = v1_config.model.api_base
            self.model.max_tokens = v1_config.model.max_tokens
            self.model.temperature = v1_config.model.temperature
            self.model.context_window = v1_config.model.context_window
            self.model.system_prompt = v1_config.model.system_prompt
            self.permission.allow_shell = v1_config.tools.allow_shell
            self.permission.allow_file_write = v1_config.tools.allow_file_write
            self.permission.allow_file_read = v1_config.tools.allow_file_read
            self.permission.allow_web = v1_config.tools.allow_web
            self.permission.sandbox = v1_config.tools.sandbox
            self.permission.max_file_size_mb = v1_config.tools.max_file_size_mb
            self.tools.working_dir = v1_config.tools.working_dir
            self.server.port = v1_config.daemon.port
            self.server.persist_state = v1_config.daemon.persist_state
            self.server.state_dir = v1_config.daemon.state_dir
            self.verify.enabled = v1_config.verify.enabled
            self.verify.auto_recover = v1_config.verify.auto_recover
            self.verify.max_retries = v1_config.verify.max_retries
            self.verify.timeout_seconds = v1_config.verify.timeout_seconds
            self.cost.max_cost_per_session_usd = v1_config.cost.max_cost_per_session_usd
            self.cost.max_cost_per_task_usd = v1_config.cost.max_cost_per_task_usd
            self.project_root = v1_config.project_root
            self.verbose = v1_config.verbose
            self.quiet = v1_config.quiet
