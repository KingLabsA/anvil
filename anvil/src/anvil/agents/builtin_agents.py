"""Built-in agent personas for Anvil."""

from __future__ import annotations

from anvil.agents.agent_base import BaseAgent, AgentMode
from anvil.permissions.permissions import PermissionConfig


ALL_TOOLS = [
    "bash", "read", "write", "edit", "grep", "glob", "ls",
    "apply_patch", "todowrite", "webfetch", "websearch", "question", "image",
]

READ_ONLY_TOOLS = ["read", "grep", "glob", "ls"]

SUBAGENT_TOOLS = [
    "bash", "read", "write", "edit", "grep", "glob", "ls",
    "apply_patch", "webfetch", "websearch",
]


def BuildAgent() -> BaseAgent:
    """Primary coding agent with full tool access."""
    return BaseAgent(
        name="build",
        description="Primary coding agent with full tool access",
        mode=AgentMode.PRIMARY,
        model="shellwhisperer",
        temperature=0.2,
        max_steps=20,
        tools_whitelist=[],
        tools_blacklist=[],
        permission=PermissionConfig.permissive(),
        prompt_template="You are Anvil's Build agent. You have full access to all tools. Available tools: {tools}\n\nPlan carefully, execute precisely, verify always.",
        hidden=False,
        color="cyan",
    )


def PlanAgent() -> BaseAgent:
    """Read-only planning agent."""
    return BaseAgent(
        name="plan",
        description="Read-only planning agent that analyzes and suggests",
        mode=AgentMode.PRIMARY,
        model="shellwhisperer",
        temperature=0.3,
        max_steps=10,
        tools_whitelist=READ_ONLY_TOOLS,
        tools_blacklist=[],
        permission=PermissionConfig.readonly(),
        prompt_template="You are Anvil's Plan agent. You analyze code and suggest changes but never modify files directly. Available tools: {tools}",
        hidden=False,
        color="green",
    )


def ExploreAgent() -> BaseAgent:
    """Read-only exploration subagent."""
    return BaseAgent(
        name="explore",
        description="Fast, read-only codebase exploration subagent",
        mode=AgentMode.SUBAGENT,
        model="shellwhisperer",
        temperature=0.1,
        max_steps=8,
        tools_whitelist=READ_ONLY_TOOLS,
        tools_blacklist=[],
        permission=PermissionConfig.readonly(),
        prompt_template="You are Anvil's Explore agent. Quickly find and read relevant code. Available tools: {tools}",
        hidden=False,
        color="blue",
    )


def GeneralAgent() -> BaseAgent:
    """General-purpose subagent with full tools except todowrite."""
    return BaseAgent(
        name="general",
        description="General-purpose subagent for multi-step research and execution",
        mode=AgentMode.SUBAGENT,
        model="shellwhisperer",
        temperature=0.2,
        max_steps=15,
        tools_whitelist=[t for t in ALL_TOOLS if t != "todowrite"],
        tools_blacklist=["todowrite"],
        permission=PermissionConfig.permissive(),
        prompt_template="You are Anvil's General agent. Handle multi-step research and execution tasks. Available tools: {tools}",
        hidden=False,
        color="magenta",
    )


def ScoutAgent() -> BaseAgent:
    """Read-only external research subagent."""
    return BaseAgent(
        name="scout",
        description="Read-only external research subagent with web access",
        mode=AgentMode.SUBAGENT,
        model="shellwhisperer",
        temperature=0.1,
        max_steps=8,
        tools_whitelist=READ_ONLY_TOOLS + ["webfetch", "websearch"],
        tools_blacklist=[],
        permission=PermissionConfig.readonly(),
        prompt_template="You are Anvil's Scout agent. Research external documentation and dependencies. Available tools: {tools}",
        hidden=False,
        color="yellow",
    )


def CompactionAgent() -> BaseAgent:
    """Hidden agent for context compaction."""
    return BaseAgent(
        name="compaction",
        description="Hidden agent for compacting conversation context",
        mode=AgentMode.PRIMARY,
        model="shellwhisperer",
        temperature=0.0,
        max_steps=1,
        tools_whitelist=[],
        tools_blacklist=[],
        permission=PermissionConfig.permissive(),
        prompt_template="You are Anvil's Compaction agent. Summarize the conversation context. Available tools: {tools}",
        hidden=True,
        color="dim",
    )


def TitleAgent() -> BaseAgent:
    """Hidden agent for generating session titles."""
    return BaseAgent(
        name="title",
        description="Hidden agent for generating session titles",
        mode=AgentMode.PRIMARY,
        model="shellwhisperer",
        temperature=0.7,
        max_steps=1,
        tools_whitelist=[],
        tools_blacklist=[],
        permission=PermissionConfig.permissive(),
        prompt_template="You are Anvil's Title agent. Generate a concise session title. Available tools: {tools}",
        hidden=True,
        color="dim",
    )


BUILTIN_AGENTS = {
    "build": BuildAgent,
    "plan": PlanAgent,
    "explore": ExploreAgent,
    "general": GeneralAgent,
    "scout": ScoutAgent,
    "compaction": CompactionAgent,
    "title": TitleAgent,
}
