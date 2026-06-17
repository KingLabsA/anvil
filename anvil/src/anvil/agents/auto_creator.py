"""Auto-create agents and skills based on user context and Fable-5 patterns."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from anvil.agents.agent_base import BaseAgent
from anvil.agents.agent_generator import AgentGenerator, GeneratedAgent
from anvil.agents.context_analyzer import ContextAnalyzer, WorkspaceContext
from anvil.agents.fable5_integrator import Fable5Integrator
from anvil.agents.pattern_extractor import PatternExtractor
from anvil.agents.skill_generator import GeneratedSkill, SkillGenerator

logger = logging.getLogger(__name__)


@dataclass
class AgentSuggestion:
    """A suggested agent to create based on context analysis."""

    name: str
    description: str
    reason: str
    spec: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    source: str = "fable5"


@dataclass
class AutoInvocationResult:
    """Result of an automatic agent/skill invocation."""

    success: bool
    agent_name: str
    output: str
    created_new: bool = False
    skill_name: str = ""
    duration_ms: float = 0.0


class AutoAgentCreator:
    """Automatically create agents and skills based on workspace context.

    Analyzes the workspace, matches patterns from the Fable-5 dataset,
    and generates agents and skills tailored to the project's needs.
    Supports automatic invocation when tasks match known patterns.

    Parameters
    ----------
    fable5_dataset_path : str
        Path to the Fable-5 dataset directory or file.
    workspace_path : str, optional
        Path to the workspace to analyze. Defaults to cwd.
    """

    def __init__(
        self,
        fable5_dataset_path: str,
        workspace_path: str | None = None,
    ):
        self._workspace_path = workspace_path or str(Path.cwd())
        self._context_analyzer = ContextAnalyzer()
        self._pattern_extractor = PatternExtractor()
        self._agent_generator = AgentGenerator()
        self._skill_generator = SkillGenerator()
        self._fable5: Fable5Integrator | None = None
        self._fable5_path = fable5_dataset_path
        self._context: WorkspaceContext | None = None
        self._created_agents: dict[str, GeneratedAgent] = {}
        self._created_skills: dict[str, GeneratedSkill] = {}
        self._suggestions: list[AgentSuggestion] = []

    @property
    def fable5(self) -> Fable5Integrator:
        """Lazy-load the Fable-5 integrator."""
        if self._fable5 is None:
            self._fable5 = Fable5Integrator(self._fable5_path)
            count = self._fable5.load()
            logger.info("Loaded %d Fable-5 traces from %s", count, self._fable5_path)
        return self._fable5

    def analyze_context(self, workspace_path: str | None = None) -> WorkspaceContext:
        """Analyze workspace to understand what agents are needed.

        Scans the codebase for tech stack, common tasks, code patterns,
        dependencies, and test coverage.

        Parameters
        ----------
        workspace_path : str, optional
            Override workspace path. Uses the path from init if not provided.

        Returns
        -------
        WorkspaceContext
            Comprehensive workspace context.
        """
        path = workspace_path or self._workspace_path
        self._context = self._context_analyzer.analyze_workspace(path)
        return self._context

    def suggest_agents(self, context: WorkspaceContext | None = None) -> list[AgentSuggestion]:
        """Suggest agents based on context analysis and Fable-5 patterns.

        Matches workspace patterns against the Fable-5 dataset to find
        agent configurations that have proven effective for similar tasks.

        Parameters
        ----------
        context : WorkspaceContext, optional
            Pre-computed context. Analyzes automatically if not provided.

        Returns
        -------
        list[AgentSuggestion]
            Suggested agents sorted by confidence descending.
        """
        ctx = context or self._context
        if ctx is None:
            ctx = self.analyze_context()

        suggestions: list[AgentSuggestion] = []

        similar = self.fable5.find_similar_patterns(
            f"{ctx.project_type} {' '.join(ctx.tech_stack.frameworks)}",
            top_k=10,
        )

        for trace in similar:
            blueprint = self.fable5.extract_agent_blueprint(trace)
            if blueprint.confidence < 0.3:
                continue

            spec = {
                "name": f"auto_{blueprint.name}",
                "description": blueprint.description,
                "mode": "subagent",
                "model": "local",
                "temperature": 0.2,
                "max_steps": 20,
                "tools_whitelist": blueprint.tools,
                "tools_blacklist": [],
                "hidden": False,
                "color": "white",
                "prompt_template": "",
                "task_type": self.fable5._classify_task(trace.task),
                "source_cluster": blueprint.name,
            }

            suggestion = AgentSuggestion(
                name=spec["name"],
                description=blueprint.description,
                reason=f"Fable-5 pattern match (confidence: {blueprint.confidence:.2f})",
                spec=spec,
                confidence=blueprint.confidence,
                source="fable5",
            )
            suggestions.append(suggestion)

        task_type_suggestions = self._suggest_from_task_types(ctx)
        suggestions.extend(task_type_suggestions)

        suggestions.sort(key=lambda s: s.confidence, reverse=True)
        self._suggestions = suggestions
        return suggestions

    def create_agent(self, spec: dict[str, Any]) -> GeneratedAgent:
        """Create an agent from specification.

        Generates code, configuration, and tests. Registers the agent
        if it passes validation.

        Parameters
        ----------
        spec : dict[str, Any]
            Agent specification.

        Returns
        -------
        GeneratedAgent
            The generated agent with validation results.

        Raises
        ------
        ValueError
            If the generated agent fails validation.
        """
        generated = self._agent_generator.generate_full(spec)

        if not generated.valid:
            logger.warning(
                "Generated agent '%s' failed validation: %s",
                spec.get("name", "unknown"),
                generated.validation_errors,
            )

        self._created_agents[generated.agent.name] = generated

        output_dir = Path(self._workspace_path) / ".anvil" / "agents"
        self._agent_generator.save_agent(generated, output_dir)
        logger.info("Saved agent '%s' to %s", generated.agent.name, output_dir)

        return generated

    def create_skill(
        self,
        name: str,
        description: str,
        examples: list[str],
        **kwargs: Any,
    ) -> GeneratedSkill:
        """Create a skill from examples.

        Generates SKILL.md, implementation hints, and metadata.
        Registers the skill in the skills directory.

        Parameters
        ----------
        name : str
            Skill name.
        description : str
            Skill description.
        examples : list[str]
            Example task descriptions.
        **kwargs
            Additional metadata (tags, task_type).

        Returns
        -------
        GeneratedSkill
            The generated skill.
        """
        skill = self._skill_generator.generate_skill(name, examples, description=description, **kwargs)
        skill_dir = self._skill_generator.register_skill(skill)
        self._created_skills[name] = skill
        logger.info("Created skill '%s' at %s", name, skill_dir)
        return skill

    def auto_invoke(self, task: str, context: WorkspaceContext | None = None) -> AutoInvocationResult:
        """Automatically invoke the appropriate agent or skill for a task.

        Matches the task against existing agents and Fable-5 patterns.
        Creates a new agent if no match is found. Executes and returns
        the result.

        Parameters
        ----------
        task : str
            Task description.
        context : WorkspaceContext, optional
            Pre-computed workspace context.

        Returns
        -------
        AutoInvocationResult
            Result of the invocation.
        """
        import time

        start = time.time()
        ctx = context or self._context
        if ctx is None:
            ctx = self.analyze_context()

        existing_match = self._find_existing_agent(task)
        if existing_match:
            duration = (time.time() - start) * 1000
            return AutoInvocationResult(
                success=True,
                agent_name=existing_match,
                output=f"Matched existing agent: {existing_match}",
                created_new=False,
                duration_ms=duration,
            )

        similar = self.fable5.find_similar_patterns(task, top_k=3)
        if similar and similar[0].success:
            blueprint = self.fable5.extract_agent_blueprint(similar[0])
            spec = self._blueprint_to_spec(blueprint, task)
            generated = self.create_agent(spec)
            duration = (time.time() - start) * 1000
            return AutoInvocationResult(
                success=generated.valid,
                agent_name=generated.agent.name,
                output=f"Created agent '{generated.agent.name}' from Fable-5 pattern",
                created_new=True,
                duration_ms=duration,
            )

        task_type = self.fable5._classify_task(task)
        skill = self.create_skill(
            name=f"auto_{task_type}",
            description=f"Auto-generated skill for {task_type}",
            examples=[task],
            task_type=task_type,
        )
        duration = (time.time() - start) * 1000
        return AutoInvocationResult(
            success=True,
            agent_name=f"auto_{task_type}",
            output=f"Created skill '{skill.name}' for task",
            created_new=True,
            skill_name=skill.name,
            duration_ms=duration,
        )

    def get_created_agents(self) -> dict[str, GeneratedAgent]:
        """Return all agents created in this session."""
        return dict(self._created_agents)

    def get_created_skills(self) -> dict[str, GeneratedSkill]:
        """Return all skills created in this session."""
        return dict(self._created_skills)

    # ── private helpers ────────────────────────────────────────────────

    def _find_existing_agent(self, task: str) -> str | None:
        task_lower = task.lower()
        for name, generated in self._created_agents.items():
            desc_lower = generated.agent.description.lower()
            if any(word in desc_lower for word in task_lower.split() if len(word) > 3):
                return name
        return None

    def _blueprint_to_spec(self, blueprint: Any, task: str) -> dict[str, Any]:
        task_type = self.fable5._classify_task(task)
        return {
            "name": f"auto_{task_type}_{blueprint.name[:8]}",
            "description": blueprint.description,
            "mode": "subagent",
            "model": "local",
            "temperature": 0.2,
            "max_steps": 20,
            "tools_whitelist": blueprint.tools,
            "tools_blacklist": [],
            "hidden": False,
            "color": "white",
            "prompt_template": "",
            "task_type": task_type,
            "source_cluster": blueprint.name,
            "verification_rules": blueprint.verification_steps,
        }

    def _suggest_from_task_types(self, ctx: WorkspaceContext) -> list[AgentSuggestion]:
        suggestions: list[AgentSuggestion] = []
        stack = ctx.tech_stack

        if "Next.js" in stack.frameworks and not any("auth" in t for t in ctx.common_tasks):
            suggestions.append(AgentSuggestion(
                name="auto_nextjs_auth",
                description="Next.js authentication agent",
                reason="Next.js project detected without authentication patterns",
                spec={
                    "name": "auto_nextjs_auth",
                    "description": "Next.js authentication agent",
                    "mode": "subagent",
                    "model": "local",
                    "temperature": 0.2,
                    "max_steps": 25,
                    "tools_whitelist": ["bash", "read", "write", "edit", "grep", "glob"],
                    "task_type": "auth",
                },
                confidence=0.7,
                source="context",
            ))

        if ctx.test_coverage < 0.2:
            suggestions.append(AgentSuggestion(
                name="auto_test_writer",
                description="Test generation agent",
                reason=f"Low test coverage detected: {ctx.test_coverage:.0%}",
                spec={
                    "name": "auto_test_writer",
                    "description": "Test generation agent",
                    "mode": "subagent",
                    "model": "local",
                    "temperature": 0.2,
                    "max_steps": 30,
                    "tools_whitelist": ["bash", "read", "write", "edit", "grep", "glob"],
                    "task_type": "testing",
                },
                confidence=0.8,
                source="context",
            ))

        if "PostgreSQL" in stack.databases or "MySQL" in stack.databases:
            suggestions.append(AgentSuggestion(
                name="auto_db_migration",
                description="Database migration agent",
                reason="Database detected in tech stack",
                spec={
                    "name": "auto_db_migration",
                    "description": "Database migration agent",
                    "mode": "subagent",
                    "model": "local",
                    "temperature": 0.1,
                    "max_steps": 15,
                    "tools_whitelist": ["bash", "read", "write", "edit", "grep"],
                    "task_type": "database",
                },
                confidence=0.6,
                source="context",
            ))

        if ctx.code_patterns:
            for pattern in ctx.code_patterns[:2]:
                if pattern.get("type") == "boilerplate" and pattern.get("occurrences", 0) >= 5:
                    pname = pattern.get("pattern", "unknown")
                    suggestions.append(AgentSuggestion(
                        name=f"auto_{pname}_helper",
                        description=f"Agent to handle {pname} boilerplate",
                        reason=f"Found {pattern['occurrences']} occurrences of {pname} boilerplate",
                        spec={
                            "name": f"auto_{pname}_helper",
                            "description": f"Agent to handle {pname} boilerplate",
                            "mode": "subagent",
                            "model": "local",
                            "temperature": 0.2,
                            "max_steps": 10,
                            "tools_whitelist": ["bash", "read", "write", "edit", "grep"],
                            "task_type": "refactoring",
                        },
                        confidence=0.5,
                        source="context",
                    ))

        return suggestions
