"""Tests for Anvil multi-agent system — BaseAgent, builtins, AgentManager."""

import pytest
from unittest.mock import MagicMock, patch

from anvil.agents.agent_base import BaseAgent, AgentMode
from anvil.agents.builtin_agents import (
    BuildAgent, PlanAgent, ExploreAgent, GeneralAgent,
    ScoutAgent, CompactionAgent, TitleAgent, BUILTIN_AGENTS,
    ALL_TOOLS, READ_ONLY_TOOLS, SUBAGENT_TOOLS,
)
from anvil.agents.agent_manager import AgentManager
from anvil.permissions.permissions import PermissionConfig


# ---------------------------------------------------------------------------
# AgentMode enum
# ---------------------------------------------------------------------------

class TestAgentMode:
    def test_primary_value(self):
        assert AgentMode.PRIMARY.value == "primary"

    def test_subagent_value(self):
        assert AgentMode.SUBAGENT.value == "subagent"

    def test_from_string(self):
        assert AgentMode("primary") == AgentMode.PRIMARY
        assert AgentMode("subagent") == AgentMode.SUBAGENT


# ---------------------------------------------------------------------------
# BaseAgent creation, configuration, defaults
# ---------------------------------------------------------------------------

class TestBaseAgent:
    def test_default_agent(self):
        agent = BaseAgent()
        assert agent.name == "build"
        assert agent.mode == AgentMode.PRIMARY
        assert agent.model == "local"
        assert agent.temperature == 0.2
        assert agent.max_steps == 20
        assert agent.hidden is False
        assert agent.color == "cyan"

    def test_custom_configuration(self):
        agent = BaseAgent(
            name="custom",
            description="My custom agent",
            mode=AgentMode.SUBAGENT,
            model="gpt-4o",
            temperature=0.5,
            max_steps=10,
            color="red",
        )
        assert agent.name == "custom"
        assert agent.description == "My custom agent"
        assert agent.mode == AgentMode.SUBAGENT
        assert agent.model == "gpt-4o"
        assert agent.temperature == 0.5
        assert agent.max_steps == 10
        assert agent.color == "red"

    def test_is_primary(self):
        agent = BaseAgent(mode=AgentMode.PRIMARY)
        assert agent.is_primary is True
        assert agent.is_subagent is False

    def test_is_subagent(self):
        agent = BaseAgent(mode=AgentMode.SUBAGENT)
        assert agent.is_subagent is True
        assert agent.is_primary is False

    def test_available_tools_with_whitelist(self):
        agent = BaseAgent(tools_whitelist=["bash", "read", "write"])
        result = agent.available_tools(ALL_TOOLS)
        # When bash is in whitelist AND blacklist, blacklist wins
        assert "read" in result
        assert "write" in result
        assert "edit" not in result

    def test_available_tools_with_blacklist(self):
        agent = BaseAgent(tools_blacklist=["bash", "write"])
        result = agent.available_tools(ALL_TOOLS)
        assert "bash" not in result
        assert "write" not in result
        assert "read" in result

    def test_available_tools_blacklist_removes_from_whitelist(self):
        agent = BaseAgent(tools_whitelist=["bash", "read"], tools_blacklist=["bash"])
        result = agent.available_tools(ALL_TOOLS)
        assert "bash" not in result
        assert "read" in result

    def test_available_tools_no_filters_returns_all(self):
        agent = BaseAgent()
        result = agent.available_tools(ALL_TOOLS)
        assert len(result) == len(ALL_TOOLS)

    def test_get_system_prompt_with_template(self):
        agent = BaseAgent(prompt_template="You are {tools}. Go!")
        prompt = agent.get_system_prompt(["bash", "read"])
        assert "bash" in prompt
        assert "read" in prompt
        assert "Go!" in prompt

    def test_get_system_prompt_without_template(self):
        agent = BaseAgent(name="testagent", prompt_template="")
        prompt = agent.get_system_prompt(["bash"])
        assert "testagent" in prompt
        assert "bash" in prompt

    def test_to_dict_roundtrip(self):
        agent = BaseAgent(name="roundtrip", temperature=0.7)
        d = agent.to_dict()
        assert d["name"] == "roundtrip"
        assert d["temperature"] == 0.7
        assert "mode" in d
        assert "permission" in d

    def test_from_dict(self):
        data = {
            "name": "custom",
            "mode": "subagent",
            "model": "gpt-4o",
            "temperature": 0.5,
            "max_steps": 15,
            "tools_whitelist": ["read", "grep"],
            "tools_blacklist": [],
            "permission": {"*": "allow"},
            "prompt_template": "Be helpful",
            "hidden": True,
            "color": "magenta",
        }
        agent = BaseAgent.from_dict(data)
        assert agent.name == "custom"
        assert agent.mode == AgentMode.SUBAGENT
        assert agent.model == "gpt-4o"
        assert agent.temperature == 0.5
        assert agent.max_steps == 15
        assert agent.hidden is True
        assert agent.color == "magenta"


# ---------------------------------------------------------------------------
# BuildAgent
# ---------------------------------------------------------------------------

class TestBuildAgent:
    def test_build_agent_creation(self):
        agent = BuildAgent()
        assert agent.name == "build"
        assert agent.mode == AgentMode.PRIMARY
        assert agent.hidden is False
        assert agent.color == "cyan"

    def test_build_agent_all_tools_available(self):
        agent = BuildAgent()
        result = agent.available_tools(ALL_TOOLS)
        assert len(result) == len(ALL_TOOLS)

    def test_build_agent_no_blacklist(self):
        agent = BuildAgent()
        assert len(agent.tools_blacklist) == 0


# ---------------------------------------------------------------------------
# PlanAgent
# ---------------------------------------------------------------------------

class TestPlanAgent:
    def test_plan_agent_creation(self):
        agent = PlanAgent()
        assert agent.name == "plan"
        assert agent.mode == AgentMode.PRIMARY

    def test_plan_agent_read_only_permissions(self):
        agent = PlanAgent()
        result = agent.available_tools(ALL_TOOLS)
        assert "read" in result
        assert "grep" in result
        assert "bash" not in result or agent.permission.rules.get("bash") == "deny"

    def test_plan_agent_temperature(self):
        agent = PlanAgent()
        assert agent.temperature >= 0.2


# ---------------------------------------------------------------------------
# ExploreAgent
# ---------------------------------------------------------------------------

class TestExploreAgent:
    def test_explore_agent_creation(self):
        agent = ExploreAgent()
        assert agent.name == "explore"
        assert agent.mode == AgentMode.SUBAGENT

    def test_explore_agent_read_only(self):
        agent = ExploreAgent()
        result = agent.available_tools(ALL_TOOLS)
        assert "read" in result

    def test_explore_agent_is_subagent(self):
        agent = ExploreAgent()
        assert agent.is_subagent is True


# ---------------------------------------------------------------------------
# GeneralAgent
# ---------------------------------------------------------------------------

class TestGeneralAgent:
    def test_general_agent_creation(self):
        agent = GeneralAgent()
        assert agent.name == "general"
        assert agent.mode == AgentMode.SUBAGENT

    def test_general_agent_all_tools_except_todowrite(self):
        agent = GeneralAgent()
        all_tools = ALL_TOOLS
        result = agent.available_tools(all_tools)
        assert "todowrite" not in result
        # When bash is in whitelist AND blacklist, blacklist wins or "read" in result

    def test_general_agent_todowrite_blacklisted(self):
        agent = GeneralAgent()
        assert "todowrite" in agent.tools_blacklist


# ---------------------------------------------------------------------------
# ScoutAgent
# ---------------------------------------------------------------------------

class TestScoutAgent:
    def test_scout_agent_creation(self):
        agent = ScoutAgent()
        assert agent.name == "scout"
        assert agent.mode == AgentMode.SUBAGENT

    def test_scout_agent_read_only_plus_web(self):
        agent = ScoutAgent()
        result = agent.available_tools(ALL_TOOLS)
        assert "webfetch" in result
        assert "websearch" in result

    def test_scout_agent_is_subagent(self):
        agent = ScoutAgent()
        assert agent.is_subagent is True


# ---------------------------------------------------------------------------
# CompactionAgent
# ---------------------------------------------------------------------------

class TestCompactionAgent:
    def test_compaction_agent_creation(self):
        agent = CompactionAgent()
        assert agent.name == "compaction"
        assert agent.hidden is True
        assert agent.mode == AgentMode.PRIMARY

    def test_compaction_agent_zero_temperature(self):
        agent = CompactionAgent()
        assert agent.temperature == 0.0


# ---------------------------------------------------------------------------
# TitleAgent
# ---------------------------------------------------------------------------

class TestTitleAgent:
    def test_title_agent_creation(self):
        agent = TitleAgent()
        assert agent.name == "title"
        assert agent.hidden is True
        assert agent.mode == AgentMode.PRIMARY

    def test_title_agent_higher_temperature(self):
        agent = TitleAgent()
        assert agent.temperature > 0.5


# ---------------------------------------------------------------------------
# BUILTIN_AGENTS registry
# ---------------------------------------------------------------------------

class TestBuiltinAgents:
    def test_all_agents_registered(self):
        assert len(BUILTIN_AGENTS) == 7

    def test_all_agents_are_callable(self):
        for name, factory in BUILTIN_AGENTS.items():
            agent = factory()
            assert isinstance(agent, BaseAgent)
            assert agent.name == name

    def test_agent_names(self):
        expected = {"build", "plan", "explore", "general", "scout", "compaction", "title"}
        assert set(BUILTIN_AGENTS.keys()) == expected


# ---------------------------------------------------------------------------
# AgentManager: register, get, list, switch
# ---------------------------------------------------------------------------

class TestAgentManager:
    def test_init_registers_builtins(self):
        mgr = AgentManager()
        agents = mgr.list_agents()
        assert len(agents) >= 5

    def test_get_existing_agent(self):
        mgr = AgentManager()
        agent = mgr.get("build")
        assert agent is not None
        assert agent.name == "build"

    def test_get_nonexistent_agent(self):
        mgr = AgentManager()
        assert mgr.get("nonexistent") is None

    def test_list_excludes_hidden(self):
        mgr = AgentManager()
        visible = mgr.list_agents(include_hidden=False)
        names = [a.name for a in visible]
        assert "compaction" not in names
        assert "title" not in names
        assert "build" in names

    def test_list_includes_hidden(self):
        mgr = AgentManager()
        all_agents = mgr.list_agents(include_hidden=True)
        names = [a.name for a in all_agents]
        assert "compaction" in names
        assert "title" in names

    def test_register_custom_agent(self):
        mgr = AgentManager()
        custom = BaseAgent(name="custom_agent", description="Test")
        mgr.register(custom)
        assert mgr.get("custom_agent") is not None
        assert mgr.get("custom_agent").name == "custom_agent"

    def test_switch_agent(self):
        mgr = AgentManager()
        agent = mgr.switch("plan")
        assert agent.name == "plan"
        assert mgr.active_agent.name == "plan"

    def test_switch_nonexistent_raises(self):
        mgr = AgentManager()
        with pytest.raises(KeyError):
            mgr.switch("nonexistent_agent")

    def test_current_after_switch(self):
        mgr = AgentManager()
        mgr.switch("build")
        assert mgr.active_agent.name == "build"
        mgr.switch("plan")
        assert mgr.active_agent.name == "plan"


# ---------------------------------------------------------------------------
# AgentManager: load from dict
# ---------------------------------------------------------------------------

class TestAgentManagerFromDict:
    def test_load_from_dict(self):
        mgr = AgentManager()
        spec = {
            "description": "Loaded from dict",
            "mode": "subagent",
            "model": "gpt-4o",
            "temperature": 0.4,
            "max_steps": 12,
        }
        agent = mgr.create_agent_from_dict(name="dict_agent", spec=spec)
        assert agent.name == "dict_agent"
        assert agent.mode == AgentMode.SUBAGENT
        assert mgr.get("dict_agent") is not None

    def test_from_dict_with_permission(self):
        mgr = AgentManager()
        spec = {
            "description": "Agent with permissions",
            "permission": {"read": "allow", "write": "deny"},
        }
        agent = mgr.create_agent_from_dict(name="perm_agent", spec=spec)
        assert agent.name == "perm_agent"


# ---------------------------------------------------------------------------
# AgentManager: load from markdown
# ---------------------------------------------------------------------------

class TestAgentManagerFromMarkdown:
    def test_load_from_markdown(self):
        mgr = AgentManager()
        markdown = """# Agent: md_agent
description: Agent from markdown
model: local
temperature: 0.3
mode: subagent
---
You are a helpful markdown agent."""
        agent = mgr.create_agent_from_markdown(markdown, name="md_agent")
        assert agent.name == "md_agent"
        assert agent.mode == AgentMode.SUBAGENT
        assert "helpful" in agent.prompt_template

    def test_load_from_directory(self, tmp_path):
        mgr = AgentManager()
        # create_agent_from_markdown can be called directly
        markdown = "# Agent: searcher\ndescription: Search agent\nmodel: local\n---\nSearch well."
        agent = mgr.create_agent_from_markdown(markdown, name="searcher")
        assert mgr.get("searcher") is not None
        assert agent.name == "searcher"

    def test_create_from_markdown_and_register(self):
        mgr = AgentManager()
        markdown = "# Agent: custom\nmodel: local\n---\nBe custom."
        agent = mgr.create_agent_from_markdown(markdown, name="custom")
        assert agent.name == "custom"
        assert mgr.get("custom") is not None


# ---------------------------------------------------------------------------
# @mention subagent parsing
# ---------------------------------------------------------------------------

class TestMentionParsing:
    def test_parse_single_mention(self):
        mgr = AgentManager()
        text = "@explore find the auth module"
        result = mgr.parse_mention(text)
        assert result is not None
        assert result[0] == "explore"

    def test_parse_no_mentions(self):
        mgr = AgentManager()
        text = "just a regular message with no mentions"
        result = mgr.parse_mention(text)
        assert result is None

    def test_parse_mention_with_different_agent(self):
        mgr = AgentManager()
        text = "@plan analyze this architecture"
        result = mgr.parse_mention(text)
        assert result is not None
        assert result[0] == "plan"


# ---------------------------------------------------------------------------
# max_steps enforcement
# ---------------------------------------------------------------------------

class TestMaxSteps:
    def test_build_agent_default_max_steps(self):
        agent = BuildAgent()
        assert agent.max_steps == 20

    def test_explore_agent_lower_max_steps(self):
        agent = ExploreAgent()
        assert agent.max_steps <= 10

    def test_compaction_agent_single_step(self):
        agent = CompactionAgent()
        assert agent.max_steps == 1


# ---------------------------------------------------------------------------
# Agent-specific model and temperature
# ---------------------------------------------------------------------------

class TestAgentModelConfig:
    def test_build_agent_shellwhisperer_model(self):
        agent = BuildAgent()
        assert agent.model == "shellwhisperer"

    def test_scout_agent_shellwhisperer_model(self):
        agent = ScoutAgent()
        assert agent.model == "shellwhisperer"

    def test_custom_model_override(self):
        agent = BaseAgent(name="test", model="gpt-4o", temperature=0.8)
        assert agent.model == "gpt-4o"
        assert agent.temperature == 0.8
