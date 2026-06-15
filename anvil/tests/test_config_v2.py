"""Tests for Anvil V2 config system — TOML, JSON, env, precedence, variable substitution, validation."""

import json
import os
from pathlib import Path
from unittest.mock import patch

from anvil.config_v2.config_v2 import (
    AgentSection,
    ConfigV2,
    MCPSection,
    ModelSection,
    PermissionSection,
    ToolsSection,
    VariableSubstitution,
    _load_from_env,
    _load_from_json,
    _load_from_toml,
    _parse_toml_simple,
)

# ---------------------------------------------------------------------------
# VariableSubstitution
# ---------------------------------------------------------------------------

class TestVariableSubstitution:
    def test_env_var_substitution(self):
        with patch.dict(os.environ, {"ANVIL_TEST_VAR": "hello"}):
            result = VariableSubstitution.substitute("{env:ANVIL_TEST_VAR}")
            assert result == "hello"

    def test_env_var_missing_returns_empty(self):
        result = VariableSubstitution.substitute("{env:NONEXISTENT_VAR_12345}")
        assert result == ""

    def test_file_substitution(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("file content")
        result = VariableSubstitution.substitute(f"{{file:{f}}}")
        assert result == "file content"

    def test_file_substitution_missing_returns_empty(self):
        result = VariableSubstitution.substitute("{file:/nonexistent/path/file.txt}")
        assert result == ""

    def test_substitute_dict(self):
        data = {
            "model": "{env:MODEL}",
            "nested": {"key": "{env:NESTED_KEY}"},
            "list": ["{env:LIST_ITEM}", "plain"],
        }
        with patch.dict(os.environ, {"MODEL": "gpt-4o", "NESTED_KEY": "nested_val", "LIST_ITEM": "item_val"}):
            result = VariableSubstitution.substitute_dict(data)
            assert result["model"] == "gpt-4o"
            assert result["nested"]["key"] == "nested_val"
            assert result["list"][0] == "item_val"

    def test_substitute_dict_no_variables(self):
        data = {"key": "plain_value", "num": 42}
        result = VariableSubstitution.substitute_dict(data)
        assert result == data


# ---------------------------------------------------------------------------
# Config sections
# ---------------------------------------------------------------------------

class TestModelSection:
    def test_defaults(self):
        section = ModelSection()
        assert section.default == "local"
        assert section.temperature == 0.2
        assert section.max_tokens == 4096
        assert section.context_window == 8192

    def test_custom(self):
        section = ModelSection(default="gpt-4o", temperature=0.5, max_tokens=8192)
        assert section.default == "gpt-4o"
        assert section.temperature == 0.5
        assert section.max_tokens == 8192


class TestAgentSection:
    def test_defaults(self):
        section = AgentSection()
        assert section.default == "build"
        assert section.temperature == 0.2
        assert section.max_steps == 20

    def test_models_dict(self):
        section = AgentSection(models={"build": {"model": "gpt-4o"}})
        assert "build" in section.models


class TestPermissionSection:
    def test_defaults(self):
        section = PermissionSection()
        assert section.default == "permissive"
        assert section.agents == {}


class TestToolsSection:
    def test_defaults(self):
        section = ToolsSection()
        assert "bash" in section.available
        assert "read" in section.available
        assert "apply_patch" in section.available

    def test_custom(self):
        section = ToolsSection(available=["bash", "read"])
        assert len(section.available) == 2


class TestMCPSection:
    def test_defaults(self):
        section = MCPSection()
        assert section.servers == []

    def test_with_servers(self):
        section = MCPSection(servers=[{"name": "test", "command": "node app.js"}])
        assert len(section.servers) == 1


# ---------------------------------------------------------------------------
# ConfigV2 loading
# ---------------------------------------------------------------------------

class TestConfigV2Load:
    def test_load_defaults(self):
        config = ConfigV2()
        assert config.model.default == "local"
        assert config.agent.default == "build"
        assert config.permission.default == "permissive"

    def test_load_from_json(self, tmp_path):
        config_data = {
            "model": {"default": "gpt-4o", "temperature": 0.5},
            "agent": {"default": "plan", "max_steps": 10},
            "tools": {"available": ["bash", "read"]},
        }
        config_file = tmp_path / "anvil.json"
        config_file.write_text(json.dumps(config_data))
        loaded = _load_from_json(tmp_path)
        assert loaded is not None
        assert loaded["model"]["default"] == "gpt-4o"

    def test_load_from_json_config_dir(self, tmp_path):
        config_data = {"model": {"default": "claude"}}
        config_dir = tmp_path / ".anvil"
        config_dir.mkdir()
        (config_dir / "config.json").write_text(json.dumps(config_data))
        loaded = _load_from_json(tmp_path)
        assert loaded is not None
        assert loaded["model"]["default"] == "claude"

    def test_load_from_toml(self, tmp_path):
        toml_content = """[model]
default = "gpt-4o"
temperature = 0.7

[agent]
default = "build"
max_steps = 15
"""
        (tmp_path / "anvil.toml").write_text(toml_content)
        loaded = _load_from_toml(tmp_path)
        assert loaded is not None
        assert loaded["model"]["default"] == "gpt-4o"
        assert loaded["model"]["temperature"] == 0.7
        assert loaded["agent"]["max_steps"] == 15

    def test_load_from_nonexistent_path(self):
        loaded = _load_from_json(Path("/nonexistent/path"))
        assert loaded is None


# ---------------------------------------------------------------------------
# Precedence: env > project > global > defaults
# ---------------------------------------------------------------------------

class TestConfigPrecedence:
    def test_env_overrides_project(self, tmp_path):
        config_file = tmp_path / "anvil.json"
        config_file.write_text(json.dumps({"model": {"default": "gpt-4o"}}))
        with patch.dict(os.environ, {"ANVIL_MODEL": "claude-3-opus"}):
            config = ConfigV2.load(project_root=str(tmp_path))
            assert config.model.default == "claude-3-opus"

    def test_project_overrides_defaults(self, tmp_path):
        config_file = tmp_path / "anvil.json"
        config_file.write_text(json.dumps({"model": {"default": "gpt-4o-mini"}}))
        config = ConfigV2.load(project_root=str(tmp_path))
        assert config.model.default == "gpt-4o-mini"

    def test_defaults_when_no_config(self, tmp_path):
        config = ConfigV2.load(project_root=str(tmp_path))
        assert config.model.default == "local"


# ---------------------------------------------------------------------------
# Variable substitution {env:VAR} and {file:path}
# ---------------------------------------------------------------------------

class TestConfigVariableSubstitution:
    def test_env_var_in_config(self, tmp_path):
        config_data = {"model": {"default": "{env:ANVIL_CUSTOM_MODEL}"}}
        config_file = tmp_path / "anvil.json"
        config_file.write_text(json.dumps(config_data))
        with patch.dict(os.environ, {"ANVIL_CUSTOM_MODEL": "claude-3-haiku"}):
            loaded = _load_from_json(tmp_path)
            assert loaded is not None
            vs = VariableSubstitution()
            substituted = vs.substitute_dict(loaded)
            assert substituted["model"]["default"] == "claude-3-haiku"


# ---------------------------------------------------------------------------
# TOML parsing
# ---------------------------------------------------------------------------

class TestTomlParsing:
    def test_simple_key_value(self):
        result = _parse_toml_simple("key = \"value\"")
        assert result["key"] == "value"

    def test_integer_value(self):
        result = _parse_toml_simple("max_steps = 20")
        assert result["max_steps"] == 20

    def test_float_value(self):
        result = _parse_toml_simple("temperature = 0.7")
        assert result["temperature"] == 0.7

    def test_boolean_value(self):
        result = _parse_toml_simple("enabled = true")
        assert result["enabled"] is True

    def test_section_header(self):
        result = _parse_toml_simple("[model]\ndefault = \"gpt-4o\"")
        assert result["model"]["default"] == "gpt-4o"

    def test_single_quoted_value(self):
        result = _parse_toml_simple("name = 'test'")
        assert result["name"] == "test"

    def test_comments_ignored(self):
        result = _parse_toml_simple("# comment\nkey = \"value\"")
        assert result["key"] == "value"
        assert "# comment" not in str(result)

    def test_empty_lines_ignored(self):
        result = _parse_toml_simple("\n\nkey = \"value\"\n\n")
        assert result["key"] == "value"


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------

class TestConfigValidation:
    def test_valid_config(self):
        config = ConfigV2()
        issues = config.validate()
        assert len(issues) == 0

    def test_invalid_temperature(self):
        config = ConfigV2(model=ModelSection(temperature=3.0))
        issues = config.validate()
        assert any("temperature" in issue.lower() for issue in issues)

    def test_negative_temperature(self):
        config = ConfigV2(model=ModelSection(temperature=-0.5))
        issues = config.validate()
        assert any("temperature" in issue.lower() for issue in issues)

    def test_invalid_max_tokens(self):
        config = ConfigV2(model=ModelSection(max_tokens=0))
        issues = config.validate()
        assert any("max_tokens" in issue for issue in issues)

    def test_invalid_max_steps(self):
        config = ConfigV2(agent=AgentSection(max_steps=0))
        issues = config.validate()
        assert any("max_steps" in issue for issue in issues)


# ---------------------------------------------------------------------------
# Export to opencode.json format
# ---------------------------------------------------------------------------

class TestConfigExport:
    def test_to_opencode_json(self):
        config = ConfigV2()
        exported = config.to_opencode_json()
        assert "model" in exported
        assert "agents" in exported
        assert "permissions" in exported
        assert "tools" in exported
        assert "mcpServers" in exported

    def test_opencode_json_preserves_values(self):
        config = ConfigV2(
            model=ModelSection(default="gpt-4o", temperature=0.5),
        )
        exported = config.to_opencode_json()
        assert exported["model"] == "gpt-4o"
        assert exported["temperature"] == 0.5


# ---------------------------------------------------------------------------
# ConfigV2 apply
# ---------------------------------------------------------------------------

class TestConfigApply:
    def test_apply_model_config(self):
        config = ConfigV2()
        config._apply({"model": {"default": "gpt-4o", "temperature": 0.8}})
        assert config.model.default == "gpt-4o"
        assert config.model.temperature == 0.8

    def test_apply_agent_config(self):
        config = ConfigV2()
        config._apply({"agent": {"default": "plan", "max_steps": 5}})
        assert config.agent.default == "plan"
        assert config.agent.max_steps == 5

    def test_apply_permission_agents(self):
        config = ConfigV2()
        config._apply({"permission": {"agents": {"build": {"bash": "allow", "write": "ask"}}}})
        assert "build" in config.permission.agents

    def test_apply_tools_available(self):
        config = ConfigV2()
        config._apply({"tools": {"available": ["bash", "read"]}})
        assert config.tools.available == ["bash", "read"]

    def test_apply_mcp_servers(self):
        config = ConfigV2()
        config._apply({"mcp": {"servers": [{"name": "test", "command": "node"}]}})
        assert len(config.mcp.servers) == 1


# ---------------------------------------------------------------------------
# .anvil/ directory loading
# ---------------------------------------------------------------------------

class TestAnvilDirectory:
    def test_load_from_anvil_config_json(self, tmp_path):
        config_dir = tmp_path / ".anvil"
        config_dir.mkdir()
        config_data = {"model": {"default": "local", "temperature": 0.3}}
        (config_dir / "config.json").write_text(json.dumps(config_data))
        loaded = _load_from_json(tmp_path)
        assert loaded is not None
        assert loaded["model"]["default"] == "local"


class TestEnvLoading:
    def test_env_overrides(self):
        with patch.dict(os.environ, {"ANVIL_MODEL": "gpt-4o", "ANVIL_TEMPERATURE": "0.5"}):
            result = _load_from_env()
            assert result["model"]["default"] == "gpt-4o"
            assert result["model"]["temperature"] == "0.5"

    def test_env_empty_when_no_vars(self):
        with patch.dict(os.environ, {}, clear=True):
            result = _load_from_env()
            assert result == {}
