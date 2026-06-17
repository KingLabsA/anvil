"""Anvil Agents — multi-agent orchestration for the self-verified coding agent."""

from anvil.agents.agent_base import AgentMode, BaseAgent
from anvil.agents.agent_generator import AgentGenerator, GeneratedAgent
from anvil.agents.agent_manager import AgentManager
from anvil.agents.auto_creator import AgentSuggestion, AutoAgentCreator, AutoInvocationResult
from anvil.agents.builtin_agents import (
    BUILTIN_AGENTS,
    BuildAgent,
    CompactionAgent,
    ExploreAgent,
    GeneralAgent,
    PlanAgent,
    ScoutAgent,
    TitleAgent,
)
from anvil.agents.context_analyzer import ContextAnalyzer, TechStackInfo, WorkspaceContext
from anvil.agents.fable5_integrator import Fable5Blueprint, Fable5Integrator, Fable5Trace
from anvil.agents.pattern_extractor import PatternCluster, PatternExtractor, TaskPattern
from anvil.agents.skill_generator import GeneratedSkill, SkillGenerator

__all__ = [
    "BaseAgent",
    "AgentMode",
    "BuildAgent",
    "PlanAgent",
    "ExploreAgent",
    "GeneralAgent",
    "ScoutAgent",
    "CompactionAgent",
    "TitleAgent",
    "BUILTIN_AGENTS",
    "AgentManager",
    "AutoAgentCreator",
    "AgentSuggestion",
    "AutoInvocationResult",
    "AgentGenerator",
    "GeneratedAgent",
    "ContextAnalyzer",
    "TechStackInfo",
    "WorkspaceContext",
    "Fable5Integrator",
    "Fable5Trace",
    "Fable5Blueprint",
    "PatternExtractor",
    "TaskPattern",
    "PatternCluster",
    "SkillGenerator",
    "GeneratedSkill",
]
