"""V2 configuration system with TOML support, variable substitution, and precedence."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path


class VariableSubstitution:
    """Handle {env:VAR} and {file:path} variable substitution in config values."""

    ENV_PATTERN = re.compile(r'\{env:([^}]+)\}')
    FILE_PATTERN = re.compile(r'\{file:([^}]+)\}')

    @classmethod
    def substitute(cls, value: str) -> str:
        """Replace {env:VAR} with environment variable and {file:path} with file contents."""
        value = cls.ENV_PATTERN.sub(lambda m: os.environ.get(m.group(1), ""), value)
        value = cls.FILE_PATTERN.sub(lambda m: cls._read_file(m.group(1)), value)
        return value

    @classmethod
    def substitute_dict(cls, data: dict) -> dict:
        """Recursively substitute variables in all string values of a dict."""
        result = {}
        for key, val in data.items():
            if isinstance(val, str):
                result[key] = cls.substitute(val)
            elif isinstance(val, dict):
                result[key] = cls.substitute_dict(val)
            elif isinstance(val, list):
                result[key] = [cls.substitute(v) if isinstance(v, str) else v for v in val]
            else:
                result[key] = val
        return result

    @staticmethod
    def _read_file(path: str) -> str:
        try:
            return Path(path).read_text(encoding="utf-8").strip()
        except OSError:
            return ""


@dataclass
class AgentSection:
    default: str = "build"
    temperature: float = 0.2
    max_steps: int = 20
    models: dict[str, dict] = field(default_factory=dict)


@dataclass
class PermissionSection:
    default: str = "permissive"
    agents: dict[str, dict] = field(default_factory=dict)


@dataclass
class ToolsSection:
    available: list[str] = field(default_factory=lambda: [
        "bash", "read", "write", "edit", "grep", "glob", "ls",
        "apply_patch", "todowrite", "webfetch", "websearch", "question", "image",
    ])


@dataclass
class MCPSection:
    servers: list[dict] = field(default_factory=list)


@dataclass
class ModelSection:
    default: str = "local"
    temperature: float = 0.2
    max_tokens: int = 4096
    context_window: int = 8192


@dataclass
class ConfigV2:
    """V2 configuration with TOML, JSON, env, and directory loading.

    Loading precedence: env vars > project config > global config > defaults.
    """

    model: ModelSection = field(default_factory=ModelSection)
    agent: AgentSection = field(default_factory=AgentSection)
    permission: PermissionSection = field(default_factory=PermissionSection)
    tools: ToolsSection = field(default_factory=ToolsSection)
    mcp: MCPSection = field(default_factory=MCPSection)

    # Source tracking
    _sources: list[str] = field(default_factory=list)

    @classmethod
    def load(cls, project_root: str | None = None) -> ConfigV2:
        """Load config with precedence: env > project > global > defaults."""
        config = cls()
        roots = _find_config_roots(project_root)

        for root in roots:
            for loader in [_load_from_json, _load_from_toml]:
                loaded = loader(root)
                if loaded:
                    config._apply(loaded)
                    config._sources.append(str(root))

        env_overrides = _load_from_env()
        if env_overrides:
            config._apply(env_overrides)
        return config

    def _apply(self, data: dict) -> None:
        """Apply a dict of config values, overwriting existing ones."""
        data = VariableSubstitution.substitute_dict(data)
        if "model" in data:
            for k, v in data["model"].items():
                if hasattr(self.model, k):
                    setattr(self.model, k, type(getattr(self.model, k))(v))
        if "agent" in data:
            for k, v in data["agent"].items():
                if hasattr(self.agent, k):
                    setattr(self.agent, k, v)
        if "permission" in data:
            if "agents" in data["permission"]:
                self.permission.agents.update(data["permission"]["agents"])
        if "tools" in data:
            if "available" in data["tools"]:
                self.tools.available = data["tools"]["available"]
        if "mcp" in data:
            if "servers" in data["mcp"]:
                self.mcp.servers.extend(data["mcp"]["servers"])

    def to_opencode_json(self) -> dict:
        """Export config in opencode.json-compatible format."""
        return {
            "model": self.model.default,
            "temperature": self.model.temperature,
            "maxTokens": self.model.max_tokens,
            "contextWindow": self.model.context_window,
            "agents": {
                "default": self.agent.default,
                "temperature": self.agent.temperature,
                "maxSteps": self.agent.max_steps,
            },
            "permissions": {
                "default": self.permission.default,
                "agents": self.permission.agents,
            },
            "tools": self.tools.available,
            "mcpServers": self.mcp.servers,
        }

    def validate(self) -> list[str]:
        """Validate config values and return list of issues."""
        issues: list[str] = []
        if self.model.temperature < 0 or self.model.temperature > 2:
            issues.append(f"Temperature {self.model.temperature} out of range [0, 2]")
        if self.model.max_tokens < 1:
            issues.append(f"max_tokens must be >= 1, got {self.model.max_tokens}")
        if self.agent.max_steps < 1:
            issues.append(f"max_steps must be >= 1, got {self.agent.max_steps}")
        return issues


def _find_config_roots(project_root: str | None = None) -> list[Path]:
    """Find config file locations in precedence order."""
    roots = []
    cwd = Path(project_root) if project_root else Path.cwd()
    roots.append(cwd)
    roots.append(cwd / ".anvil")
    roots.append(Path.home() / ".config" / "anvil")
    return [r for r in roots if r.exists()]


def _load_from_json(root: Path) -> dict | None:
    """Load config from anvil.json or .anvil/config.json."""
    for name in ["anvil.json", ".anvil/config.json"]:
        path = root / name
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return None
    return None


def _load_from_toml(root: Path) -> dict | None:
    """Load config from anvil.toml."""
    path = root / "anvil.toml"
    if not path.exists():
        return None
    try:
        content = path.read_text(encoding="utf-8")
        return _parse_toml_simple(content)
    except OSError:
        return None


def _parse_toml_simple(content: str) -> dict:
    """Minimal TOML parser for flat and one-level-nested configs."""
    result: dict = {}
    current_section: str | None = None

    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            current_section = line[1:-1].strip()
            if current_section not in result:
                result[current_section] = {}
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()

        if value.startswith('"') and value.endswith('"'):
            value = value[1:-1]
        elif value.startswith("'") and value.endswith("'"):
            value = value[1:-1]
        elif value.lower() in ("true", "false"):
            value = value.lower() == "true"
        elif "." in value:
            try:
                value = float(value)
            except ValueError:
                pass
        else:
            try:
                value = int(value)
            except ValueError:
                pass

        if current_section:
            result[current_section][key] = value
        else:
            result[key] = value

    return result


def _load_from_env() -> dict:
    """Load config overrides from environment variables with ANVIL_ prefix."""
    result: dict = {}
    env_map = {
        "ANVIL_MODEL": ("model", "default"),
        "ANVIL_TEMPERATURE": ("model", "temperature"),
        "ANVIL_MAX_TOKENS": ("model", "max_tokens"),
        "ANVIL_AGENT": ("agent", "default"),
        "ANVIL_MAX_STEPS": ("agent", "max_steps"),
    }
    for env_key, (section, key) in env_map.items():
        val = os.environ.get(env_key)
        if val is not None:
            if section not in result:
                result[section] = {}
            result[section][key] = val
    return result
