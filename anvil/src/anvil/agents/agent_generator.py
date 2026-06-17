"""Generate agent code and configuration from specifications."""

from __future__ import annotations

import ast
import json
import textwrap
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from anvil.agents.agent_base import AgentMode, BaseAgent
from anvil.permissions.permissions import PermissionConfig


@dataclass
class GeneratedAgent:
    """A fully generated agent with code, config, and tests."""

    agent: BaseAgent
    code: str
    config: dict[str, Any]
    test_code: str
    valid: bool = False
    validation_errors: list[str] = field(default_factory=list)


AGENT_TEMPLATE = '''\
"""Auto-generated agent: {name}.

Generated from Fable-5 pattern cluster: {cluster_id}
Task type: {task_type}
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class {class_name}Config:
    """Configuration for the {name} agent."""

    model: str = "{model}"
    temperature: float = {temperature}
    max_steps: int = {max_steps}
    tools_whitelist: list[str] = field(default_factory=lambda: {tools_list})
    verification_rules: list[str] = field(default_factory=lambda: {verify_rules})
    recovery_rules: list[str] = field(default_factory=lambda: {recovery_rules})


class {class_name}:
    """{description}

    Auto-generated from Fable-5 patterns.
    Source cluster: {cluster_id}
    """

    def __init__(self, config: {class_name}Config | None = None):
        self.config = config or {class_name}Config()
        self._execution_history: list[dict[str, Any]] = []

    async def execute(self, task: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
        """Execute a task using the agent's configured tools and rules.

        Parameters
        ----------
        task : str
            Description of the task to execute.
        context : dict, optional
            Additional context about the workspace and environment.

        Returns
        -------
        dict[str, Any]
            Execution result with status, output, and metadata.
        """
        result: dict[str, Any] = {{
            "task": task,
            "agent": "{name}",
            "status": "pending",
            "steps": [],
            "output": "",
        }}

        try:
            result["status"] = "running"
            result["steps"].append({{"action": "plan", "detail": "Analyzing task"}})

{plan_steps}

            result["status"] = "completed"
            result["output"] = "Task completed successfully"
        except Exception as e:
            result["status"] = "error"
            result["output"] = str(e)

        self._execution_history.append(result)
        return result

    def get_history(self) -> list[dict[str, Any]]:
        """Return execution history for learning and improvement."""
        return list(self._execution_history)
'''


class AgentGenerator:
    """Generate agent code, configuration, and tests from specifications.

    Takes agent specifications (from ``PatternExtractor`` or manual
    creation) and produces validated Python code, configuration dicts,
    and test suites.
    """

    def __init__(self) -> None:
        self._generated: dict[str, GeneratedAgent] = {}

    def generate_agent_code(self, spec: dict[str, Any]) -> str:
        """Generate Python code for an agent from a specification.

        Parameters
        ----------
        spec : dict[str, Any]
            Agent specification with name, description, tools, etc.

        Returns
        -------
        str
            Complete Python source code for the agent.
        """
        name = spec.get("name", "auto_agent")
        class_name = self._to_class_name(name)
        description = spec.get("description", f"Auto-generated agent: {name}")
        model = spec.get("model", "local")
        temperature = spec.get("temperature", 0.2)
        max_steps = spec.get("max_steps", 20)
        tools = spec.get("tools_whitelist", [])
        verify_rules = spec.get("verification_rules", [])
        recovery_rules = spec.get("recovery_rules", [])
        cluster_id = spec.get("source_cluster", "unknown")
        task_type = spec.get("task_type", "general")

        plan_steps = self._generate_plan_steps(tools, task_type)

        code = AGENT_TEMPLATE.format(
            name=name,
            class_name=class_name,
            cluster_id=cluster_id,
            task_type=task_type,
            description=description,
            model=model,
            temperature=temperature,
            max_steps=max_steps,
            tools_list=json.dumps(tools),
            verify_rules=json.dumps(verify_rules),
            recovery_rules=json.dumps(recovery_rules),
            plan_steps=plan_steps,
        )
        return code

    def generate_agent_config(self, spec: dict[str, Any]) -> dict[str, Any]:
        """Generate agent configuration dict.

        Parameters
        ----------
        spec : dict[str, Any]
            Agent specification.

        Returns
        -------
        dict[str, Any]
            Configuration dict compatible with ``AgentManager.create_agent_from_dict``.
        """
        config: dict[str, Any] = {
            "name": spec.get("name", "auto_agent"),
            "description": spec.get("description", "Auto-generated agent"),
            "mode": spec.get("mode", "subagent"),
            "model": spec.get("model", "local"),
            "temperature": spec.get("temperature", 0.2),
            "top_p": spec.get("top_p", 1.0),
            "max_steps": spec.get("max_steps", 20),
            "tools_whitelist": spec.get("tools_whitelist", []),
            "tools_blacklist": spec.get("tools_blacklist", []),
            "hidden": spec.get("hidden", False),
            "color": spec.get("color", "white"),
            "prompt_template": spec.get("prompt_template", ""),
            "extra": {
                "source_cluster": spec.get("source_cluster", ""),
                "task_type": spec.get("task_type", "general"),
                "auto_generated": True,
            },
        }
        return config

    def generate_agent_tests(self, spec: dict[str, Any]) -> str:
        """Generate test code for an agent.

        Creates unit tests covering instantiation, configuration,
        and basic execution flow.

        Parameters
        ----------
        spec : dict[str, Any]
            Agent specification.

        Returns
        -------
        str
            Python test source code.
        """
        name = spec.get("name", "auto_agent")
        class_name = self._to_class_name(name)
        tools = spec.get("tools_whitelist", [])
        max_steps = spec.get("max_steps", 20)

        test_code = textwrap.dedent(f'''\
            """Tests for auto-generated agent: {name}."""

            from __future__ import annotations

            import pytest


            class Test{class_name}:
                """Test suite for the {class_name} agent."""

                def test_agent_creation(self):
                    """Agent can be instantiated with default config."""
                    from anvil.agents.agent_base import BaseAgent

                    agent = BaseAgent(name="{name}")
                    assert agent.name == "{name}"

                def test_agent_config(self):
                    """Agent configuration matches specification."""
                    config = {json.dumps(self.generate_agent_config(spec), indent=4)}
                    assert config["name"] == "{name}"
                    assert config["max_steps"] == {max_steps}

                def test_tools_whitelist(self):
                    """Tools whitelist is correctly configured."""
                    expected_tools = {json.dumps(tools)}
                    assert isinstance(expected_tools, list)

                def test_agent_mode(self):
                    """Agent mode is set correctly."""
                    mode = "{spec.get("mode", "subagent")}"
                    assert mode in ("primary", "subagent")
            ''')
        return test_code

    def validate_agent(self, agent_code: str, config: dict[str, Any]) -> bool:
        """Validate generated agent code and configuration.

        Checks Python syntax, verifies imports are valid, and ensures
        configuration values are within acceptable ranges.

        Parameters
        ----------
        agent_code : str
            Generated Python source code.
        config : dict[str, Any]
            Generated configuration dict.

        Returns
        -------
        bool
            True if validation passes, False otherwise.
        """
        errors: list[str] = []

        try:
            ast.parse(agent_code)
        except SyntaxError as e:
            errors.append(f"Syntax error: {e}")

        if not config.get("name"):
            errors.append("Config missing 'name'")

        temp = config.get("temperature", 0.2)
        if not (0.0 <= temp <= 2.0):
            errors.append(f"Temperature out of range: {temp}")

        max_steps = config.get("max_steps", 20)
        if not (1 <= max_steps <= 200):
            errors.append(f"max_steps out of range: {max_steps}")

        mode = config.get("mode", "subagent")
        if mode not in ("primary", "subagent"):
            errors.append(f"Invalid mode: {mode}")

        if errors:
            return False
        return True

    def generate_full(self, spec: dict[str, Any]) -> GeneratedAgent:
        """Generate a complete agent with code, config, and tests.

        Parameters
        ----------
        spec : dict[str, Any]
            Agent specification.

        Returns
        -------
        GeneratedAgent
            Complete generated agent with validation results.
        """
        code = self.generate_agent_code(spec)
        config = self.generate_agent_config(spec)
        test_code = self.generate_agent_tests(spec)
        valid = self.validate_agent(code, config)

        agent = BaseAgent(
            name=config["name"],
            description=config["description"],
            mode=AgentMode(config["mode"]),
            model=config["model"],
            temperature=config["temperature"],
            top_p=config["top_p"],
            max_steps=config["max_steps"],
            tools_whitelist=config["tools_whitelist"],
            tools_blacklist=config["tools_blacklist"],
            hidden=config["hidden"],
            color=config["color"],
            prompt_template=config["prompt_template"],
        )

        generated = GeneratedAgent(
            agent=agent,
            code=code,
            config=config,
            test_code=test_code,
            valid=valid,
        )

        self._generated[config["name"]] = generated
        return generated

    def save_agent(self, generated: GeneratedAgent, output_dir: str | Path) -> list[Path]:
        """Save generated agent files to disk.

        Parameters
        ----------
        generated : GeneratedAgent
            The generated agent to save.
        output_dir : str or Path
            Directory to write files into.

        Returns
        -------
        list[Path]
            Paths of all files written.
        """
        out = Path(output_dir)
        out.mkdir(parents=True, exist_ok=True)

        name = generated.agent.name
        written: list[Path] = []

        agent_file = out / f"{name}.py"
        agent_file.write_text(generated.code, encoding="utf-8")
        written.append(agent_file)

        config_file = out / f"{name}_config.json"
        config_file.write_text(json.dumps(generated.config, indent=2), encoding="utf-8")
        written.append(config_file)

        test_file = out / f"test_{name}.py"
        test_file.write_text(generated.test_code, encoding="utf-8")
        written.append(test_file)

        return written

    # ── private helpers ────────────────────────────────────────────────

    def _to_class_name(self, name: str) -> str:
        parts = name.replace("-", "_").split("_")
        return "".join(p.capitalize() for p in parts if p) + "Agent"

    def _generate_plan_steps(self, tools: list[str], task_type: str) -> str:
        steps: list[str] = []
        indent = " " * 12

        steps.append(f'{indent}result["steps"].append({{"action": "analyze", "detail": "Scanning workspace"}})')
        steps.append("")

        if "bash" in tools:
            steps.append(f'{indent}result["steps"].append({{"action": "execute", "detail": "Running shell commands"}})')
        if "read" in tools:
            steps.append(f'{indent}result["steps"].append({{"action": "read", "detail": "Reading relevant files"}})')
        if "write" in tools or "edit" in tools:
            steps.append(f'{indent}result["steps"].append({{"action": "modify", "detail": "Making code changes"}})')
        if "grep" in tools:
            steps.append(f'{indent}result["steps"].append({{"action": "search", "detail": "Searching codebase"}})')

        steps.append("")
        steps.append(f'{indent}result["steps"].append({{"action": "verify", "detail": "Verifying changes"}})')

        return "\n".join(steps)
