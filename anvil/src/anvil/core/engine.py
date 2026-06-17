"""Anvil Engine — Generate → Execute → Verify → Recover.

The core loop that separates Anvil from every other open agent.
We don't just generate and hope. We verify. And when verification fails,
we diagnose, recover, and try again.

This is behavior engineering, not prompt engineering.
Trained on 210K real agent traces that demonstrate exactly this pattern.

v2 adds multi-agent support and permission-checked tool dispatch.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from anvil.agents.agent_base import BaseAgent
from anvil.agents.agent_manager import AgentManager
from anvil.agents.auto_creator import AutoAgentCreator
from anvil.agents.builtin_agents import BuildAgent
from anvil.core.config import AnvilConfig
from anvil.core.instructions import InstructionsLoader, InstructionsWatcher
from anvil.core.session import Session, Step, StepKind, StepStatus, ToolCall
from anvil.memory.manager import MemoryManager
from anvil.models.registry import Message, ModelRegistry
from anvil.permissions.permissions import PermissionAction, PermissionConfig, PermissionManager
from anvil.tools.executor import ToolExecutor, ToolResult
from anvil.verify.pipeline import VerifyPipeline, VerifyReport

TOOL_DEFINITIONS = [
    {"name": "bash", "description": "Run a shell command", "args": ["command"]},
    {"name": "read", "description": "Read a file", "args": ["path", "offset", "limit"]},
    {"name": "write", "description": "Write a file", "args": ["path", "content"]},
    {"name": "edit", "description": "Edit a file by replacing text", "args": ["path", "old_string", "new_string"]},
    {"name": "grep", "description": "Search file contents", "args": ["pattern", "path", "include"]},
    {"name": "glob", "description": "Find files by pattern", "args": ["pattern", "path"]},
    {"name": "ls", "description": "List directory contents", "args": ["path"]},
    {"name": "task", "description": "Dispatch a specialized subagent to autonomously handle a multi-step task. Args: subagent_type, description, prompt", "args": ["subagent_type", "description", "prompt", "task_id"]},
    {"name": "skill", "description": "Load a specialized skill's instructions when the task matches it. Args: name", "args": ["name"]},
    {"name": "press", "description": "Printing Press: generate a runnable CLI + skill wrapper for an API. Args: service, base_url, spec_url", "args": ["service", "base_url", "spec_url"]},
]

ALL_TOOL_NAMES = [t["name"] for t in TOOL_DEFINITIONS]

SYSTEM_PROMPT = """You are Anvil, a self-verified coding agent. You don't just generate code — you verify it works.

Your workflow:
1. PLAN — Break the task into small, verifiable steps
2. EXECUTE — Use tools to implement each step
3. VERIFY — After each change, verify: syntax, tests, lint
4. RECOVER — If verification fails, diagnose and fix automatically

Rules:
- Always verify your work after making changes
- Use `bash` to run tests, linters, type checkers
- Use `read` to confirm files look correct
- If a test fails, read the error, fix it, and re-verify
- Never claim "done" without verifying
- When you're done, summarize what was changed and how it was verified

Delegation & skills:
- Use `task` to dispatch a specialized subagent (e.g. explore, scout, general) for
  independent multi-step work. Provide `subagent_type`, a short `description`, and a
  detailed `prompt`. The subagent runs its own verify-loop and returns its result.
- Use `skill` to load a specialized skill's instructions when the task matches one of
  the available skills. Provide the skill `name`.
- Use `press` (Printing Press) to generate a runnable CLI + skill wrapper for an
  external API. Provide `service` and either `base_url` or `spec_url` (an OpenAPI
  spec URL). After pressing, load the new skill with `skill` and call its CLI via `bash`.

TOOL-CALL PROTOCOL (STRICTLY REQUIRED):
To use a tool, you MUST emit a fenced block tagged `tool` containing a JSON object
with `tool` and `args`. You may emit multiple blocks.

DO NOT describe what you would do. DO NOT write pseudocode. You MUST emit actual
```tool blocks. If you don't emit tool blocks, no action will be taken.

Examples:

```tool
{{"tool": "edit", "args": {{"path": "src/app.py", "old_string": "return a - b", "new_string": "return a + b"}}}}
```

```tool
{{"tool": "write", "args": {{"path": "hello.py", "content": "print('hi')\\n"}}}}
```

```tool
{{"tool": "bash", "args": {{"command": "python -m pytest -x"}}}}
```

```tool
{{"tool": "read", "args": {{"path": "src/app.py"}}}}
```

Rules:
- ALWAYS use the ```tool JSON format above for ANY file change or command.
- NEVER just describe actions in plain text — emit a ```tool block instead.
- To modify an existing file, use `edit` with `old_string` and `new_string`.
- Use relative file paths (not absolute paths).

Current agent: {agent_name}
Available tools: {tools}"""

PLAN_PROMPT = """Break this task into small, verifiable steps. For each step, say:
- What to do
- Which tool to use
- How to verify it worked

Task: {task}"""

EXECUTE_PROMPT = """Execute the next step by emitting ```tool blocks. Do NOT describe what you would do — actually do it.

Current agent: {agent_name}
Current plan: {plan}
Current step: {step}
Files changed so far: {files}
Verify results so far: {verify_results}

REMINDER: You MUST emit ```tool JSON blocks to take action. Plain text descriptions do nothing."""

RECOVER_PROMPT = """The last step failed verification. Here's what happened:

Step: {step}
Error: {error}
Verify report: {verify_report}

Diagnose the issue and fix it. Then verify again."""

VERIFY_PROMPT = """Verify the recent changes. Run appropriate checks:
- Syntax check the changed files
- Run tests if they exist
- Check lint/style if applicable

Changed files: {files}
What to verify: {verify_checks}"""


@dataclass
class EngineResult:
    success: bool
    session: Session
    output: str
    verify_report: VerifyReport | None = None
    error: str | None = None
    agent_name: str = "build"

    def format_result(self) -> str:
        lines = [
            f"{'✓ SUCCESS' if self.success else '✗ FAILED'} (agent: {self.agent_name})",
            f"Output: {self.output[:500]}",
        ]
        if self.verify_report:
            lines.append(f"\nVerification:\n{self.verify_report.format_summary()}")
        if self.session:
            lines.append(f"\n{self.session.format_progress()}")
        if self.error:
            lines.append(f"Error: {self.error}")
        return "\n".join(lines)


class AnvilEngine:
    """The Plan → Execute → Verify → Recover loop, now agent-aware."""

    def __init__(
        self,
        config: AnvilConfig | None = None,
        agent: BaseAgent | None = None,
    ):
        self.config = config or AnvilConfig()

        # Resolve the active agent.
        self.agent_manager = AgentManager(
            config_dir=Path.home() / ".config" / "anvil",
            project_dir=Path(self.config.project_root),
        )
        # Register any custom agents from config.
        for name, agent_def in self.config.agent.items():
            spec = {
                "description": agent_def.description,
                "mode": agent_def.mode,
                "model": agent_def.model,
                "temperature": agent_def.temperature,
                "top_p": agent_def.top_p,
                "max_steps": agent_def.max_steps,
                "tools_whitelist": agent_def.tools_whitelist,
                "tools_blacklist": agent_def.tools_blacklist,
                "hidden": agent_def.hidden,
                "color": agent_def.color,
                "prompt_template": agent_def.prompt_template,
            }
            if agent_def.permission:
                spec["permission"] = PermissionConfig.from_dict(agent_def.permission)
            self.agent_manager.create_agent_from_dict(name, spec)

        # Set the active agent.
        self.agent: BaseAgent = agent or self.agent_manager.get(self.config.default_agent) or BuildAgent
        self.agent_manager.switch(self.agent.name) if self.agent.is_primary else None

        # Model backend — derived from config; agent model is decorative unless config omits it.
        active_model = self.config.model.model or self.agent.model
        self.model = ModelRegistry.create(
            active_model,
            api_key=self.config.model.api_key,
            api_base=self.config.model.api_base,
        )

        # Tools and verification pipeline.
        self.tools = ToolExecutor(
            working_dir=self.config.tools.working_dir,
            timeout=self.config.verify.timeout_seconds,
            sandbox=self.config.tools.sandbox,
        )

        # Permission manager with global config.
        self.permissions = PermissionManager(self.config.get_global_permission_config())

        self.verify = VerifyPipeline(self.config.verify)
        self.memory = MemoryManager()
        self.session: Session | None = None
        self._steps_taken: int = 0
        self._is_subagent: bool = False
        self._instructions_prompt: str = ""
        self._init_integrations()
        self._init_instructions()
        self._init_auto_creator()
        self._init_mcp_registry()

    def _init_integrations(self) -> None:
        # Lazy initialization - only load when accessed
        self._verifyloop = None
        self._error_recovery = None
        self._agent_swarm = None
        self._cost_optimizer = None
        self._remote_control = None
        self._teleport_manager = None
    
    @property
    def verifyloop(self):
        if self._verifyloop is None:
            from anvil.integrations.verifyloop import VerifyLoopIntegration
            self._verifyloop = VerifyLoopIntegration(self.config.verify)
        return self._verifyloop
    
    @property
    def error_recovery(self):
        if self._error_recovery is None:
            from anvil.integrations.error_recovery import ErrorRecoveryIntegration
            self._error_recovery = ErrorRecoveryIntegration()
        return self._error_recovery
    
    @property
    def agent_swarm(self):
        if self._agent_swarm is None:
            from anvil.integrations.agent_swarm import AgentSwarmIntegration
            self._agent_swarm = AgentSwarmIntegration()
        return self._agent_swarm
    
    @property
    def cost_optimizer(self):
        if self._cost_optimizer is None:
            from anvil.integrations.cost_optimizer import CostOptimizerIntegration
            self._cost_optimizer = CostOptimizerIntegration(
                max_cost_per_session=self.config.cost.max_cost_per_session_usd,
                max_cost_per_task=self.config.cost.max_cost_per_task_usd,
            )
        return self._cost_optimizer
    
    @property
    def remote_control(self):
        if self._remote_control is None:
            from anvil.remote.control import RemoteControl
            self._remote_control = RemoteControl(anvil_engine=self)
        return self._remote_control
    
    @property
    def teleport_manager(self):
        if self._teleport_manager is None:
            from anvil.remote.control import TeleportManager
            self._teleport_manager = TeleportManager(remote_control=self.remote_control)
        return self._teleport_manager

    def _init_instructions(self) -> None:
        workspace = Path(self.config.project_root or self.config.tools.working_dir or ".")
        self._instructions_loader = InstructionsLoader(workspace)
        self._instructions_watcher = InstructionsWatcher(workspace, self._instructions_loader)
        self._instructions_prompt = self._instructions_loader.get_system_prompt_addition()

    def _refresh_instructions(self) -> str:
        cached = self._instructions_prompt
        reloaded = self._instructions_watcher.reload_if_changed()
        if reloaded is not None:
            if reloaded.strip():
                self._instructions_prompt = (
                    "\n## Project-Specific Instructions\n\n"
                    "The following are project-specific instructions from ANVIL.md files. "
                    "Follow these strictly:\n\n"
                    f"{reloaded}\n\n"
                    "## End Project Instructions\n"
                )
            else:
                self._instructions_prompt = ""
        return self._instructions_prompt

    def _init_auto_creator(self) -> None:
        fable5_path = str(Path.home() / ".anvil" / "fable5")
        workspace = self.config.project_root or str(Path.cwd())
        self.auto_creator = AutoAgentCreator(
            fable5_dataset_path=fable5_path,
            workspace_path=workspace,
        )

    def _init_mcp_registry(self) -> None:
        self._mcp_registry = None
    
    @property
    def mcp_registry(self):
        if self._mcp_registry is None:
            from anvil.mcp.registry import MCPToolRegistry
            self._mcp_registry = MCPToolRegistry(anvil_engine=self)
            mcp_config_path = Path.home() / ".anvil" / "mcp_servers.json"
            if mcp_config_path.exists():
                self._mcp_registry.register_mcp_server_from_file(mcp_config_path)
                self._mcp_registry.discover_tools()
        return self._mcp_registry

    # ── agent switching ────────────────────────────────────────────────

    def switch_agent(self, name: str) -> BaseAgent:
        """Switch the active primary agent mid-session.

        Creates a new model backend if the agent uses a different model.
        """
        agent = self.agent_manager.switch(name)
        self.agent = agent
        if agent.model != self.model.name:
            self.model = ModelRegistry.create(
                agent.model,
                api_key=self.config.model.api_key,
                api_base=self.config.model.api_base,
            )
        return agent

    def invoke_subagent(self, name: str, task: str) -> EngineResult:
        """Invoke a subagent via @mention-style dispatch.

        Returns an EngineResult wrapping the subagent's output.
        """
        invocation = self.agent_manager.invoke_subagent(
            name=name,
            task=task,
            model=self.model,
            working_dir=self.config.tools.working_dir,
        )
        return EngineResult(
            success=invocation.success,
            session=self.session or Session(task=task, project_root=self.config.project_root),
            output=invocation.response[:2000],
            agent_name=invocation.agent_name,
            error=None if invocation.success else invocation.response,
        )

    def _try_auto_invoke(self, task: str) -> EngineResult | None:
        """Attempt automatic agent/skill creation and invocation.

        Returns an ``EngineResult`` if auto-invocation handled the task,
        or ``None`` to fall through to the normal plan-execute loop.
        """
        try:
            result = self.auto_creator.auto_invoke(task)
        except Exception:
            return None

        if not result.success and not result.created_new:
            return None

        if not result.created_new:
            existing = self.agent_manager.get(result.agent_name)
            if existing and existing.is_subagent:
                return self.invoke_subagent(result.agent_name, task)
            return None

        if result.agent_name:
            new_agent = self.agent_manager.get(result.agent_name)
            if new_agent is None:
                created = self.auto_creator.get_created_agents().get(result.agent_name)
                if created:
                    self.agent_manager.register(created.agent)
                    new_agent = created.agent

            if new_agent and new_agent.is_subagent:
                return self.invoke_subagent(result.agent_name, task)

        return None

    # ── permission-checked tool dispatch ────────────────────────────────

    def _check_permission(self, tool: str, args: dict[str, Any]) -> PermissionAction:
        """Check whether *tool* with *args* is allowed under current permissions.

        Returns the effective action. ``ALLOW`` means proceed, ``ASK`` means
        the caller should prompt for user confirmation, and ``DENY`` means
        the tool call must be rejected.
        """
        return self.permissions.check_permission(
            tool, args, agent_config=self.agent.permission,
        )

    def _normalize_tool_args(self, tool: str, args: dict[str, Any]) -> dict[str, Any]:
        """Normalize file paths in tool args so hallucinated absolute paths
        resolve against the working directory.

        Models frequently emit paths like ``/home/user/.../calculator.py``
        when the file is actually at ``calculator.py`` in the workspace.
        """
        working = Path(self.config.tools.working_dir or self.config.project_root or ".")
        path_keys = {"path", "file_path"}
        out = dict(args)
        for key in path_keys:
            val = out.get(key)
            if not val or not isinstance(val, str):
                continue
            p = Path(val)
            # Already relative or exists — leave it alone.
            if not p.is_absolute():
                continue
            if p.exists():
                continue
            # Try basename first, then tail components.
            candidate = working / p.name
            if candidate.exists():
                out[key] = str(candidate)
                continue
            # Walk the parts looking for a match.
            parts = p.parts
            for i in range(len(parts)):
                sub = Path(*parts[i:]) if i < len(parts) - 1 else Path(parts[-1])
                candidate = working / sub
                if candidate.exists():
                    out[key] = str(candidate)
                    break
        return out

    def _execute_tool(self, tool: str, args: dict[str, Any]) -> ToolResult:
        """Execute a tool after passing it through the permission gate."""
        args = self._normalize_tool_args(tool, args)
        action = self._check_permission(tool, args)
        if action == PermissionAction.DENY:
            return ToolResult(
                success=False,
                output="",
                error=f"Permission denied: tool '{tool}' is not allowed for agent '{self.agent.name}'",
            )
        # Check MCP registry for external tools
        if hasattr(self, 'mcp_registry') and tool in self.mcp_registry.get_tool_names():
            from anvil.mcp.protocol import CallResult
            result: CallResult = self.mcp_registry.call_tool(tool, args)
            return ToolResult(
                success=not result.is_error,
                output=result.text,
                error=result.text if result.is_error else None,
            )
        # ASK is handled upstream (engine logs it); for now we treat it like ALLOW
        # and rely on the TUI / CLI to intercept when needed.
        if tool == "task":
            return self._run_task(args)
        if tool == "skill":
            return self._run_skill(args)
        if tool == "press":
            return self._run_press(args)
        return self.tools.execute(tool, args)

    def _run_press(self, args: dict[str, Any]) -> ToolResult:
        """Printing Press: generate a CLI + skill wrapper for an API service."""
        service = args.get("service", "")
        base_url = args.get("base_url", "")
        spec_url = args.get("spec_url", "")
        if not service:
            return ToolResult(success=False, output="", error="press: 'service' is required")
        if not base_url and not spec_url:
            return ToolResult(success=False, output="", error="press: provide 'base_url' or 'spec_url'")

        spec = None
        if spec_url:
            try:
                import json as _json
                import urllib.request

                with urllib.request.urlopen(spec_url, timeout=30) as resp:
                    spec = _json.loads(resp.read().decode())
            except Exception as e:  # noqa: BLE001
                return ToolResult(success=False, output="", error=f"press: failed to fetch spec_url: {e}")

        from anvil.printing_press import press as _press

        search = self._skill_search_paths()
        out_dir = search[0] if search else Path(self.config.project_root or ".") / ".anvil" / "skills"
        try:
            result = _press(service, base_url=base_url, spec=spec, output_dir=out_dir)
        except Exception as e:  # noqa: BLE001
            return ToolResult(success=False, output="", error=f"press: {e}")

        rendered = (
            f"Generated Printing Press wrapper for '{service}'\n"
            f"- Base URL: {result.base_url}\n"
            f"- Endpoints: {len(result.endpoints)}\n"
            f"- CLI: {result.cli_path}\n"
            f"- Skill: {result.skill_path} (load with the `skill` tool: name='{result.cli_path.parent.name}')\n"
            f"Run `python {result.cli_path} --list` to see commands."
        )
        return ToolResult(success=True, output=rendered)

    def _run_task(self, args: dict[str, Any]) -> ToolResult:
        """Dispatch a subagent via a nested verify-loop engine (OpenCode-style task tool)."""
        subagent_type = args.get("subagent_type") or args.get("agent") or ""
        prompt = args.get("prompt") or args.get("task") or ""
        description = args.get("description", subagent_type)

        if not subagent_type:
            return ToolResult(success=False, output="", error="task: 'subagent_type' is required")
        if not prompt:
            return ToolResult(success=False, output="", error="task: 'prompt' is required")

        # Recursion guard: subagents may not themselves dispatch tasks.
        if getattr(self, "_is_subagent", False):
            return ToolResult(
                success=False, output="",
                error="task: nested subagent dispatch is not allowed (recursion guard)",
            )

        subagent = self.agent_manager.get(subagent_type)
        if subagent is None:
            available = ", ".join(self.agent_manager.all_agent_names())
            return ToolResult(
                success=False, output="",
                error=f"task: unknown subagent_type '{subagent_type}'. Available: {available}",
            )

        # Build a child config inheriting the parent's settings but bound to the
        # subagent's model, with the verify-loop intact.
        from copy import deepcopy

        child_config = deepcopy(self.config)
        child_config.model.model = subagent.model or self.config.model.model

        child_engine = AnvilEngine(child_config, agent=subagent)
        child_engine._is_subagent = True

        result = child_engine.run(prompt, max_iterations=subagent.max_steps or 10)
        state = "completed" if result.success else "error"
        body = result.output or (result.error or "")
        rendered = (
            f'<task agent="{subagent.name}" state="{state}">\n'
            f"<description>{description}</description>\n"
            f"<task_result>\n{body}\n</task_result>\n"
            f"</task>"
        )
        return ToolResult(success=result.success, output=rendered, error=None if result.success else result.error)

    def _run_skill(self, args: dict[str, Any]) -> ToolResult:
        """Load a skill's SKILL.md content by name (OpenCode-style skill tool)."""
        name = args.get("name", "")
        if not name:
            return ToolResult(success=False, output="", error="skill: 'name' is required")

        skill = self._find_skill(name)
        if skill is None:
            available = ", ".join(self._available_skill_names()) or "(none found)"
            return ToolResult(
                success=False, output="",
                error=f"skill: unknown skill '{name}'. Available: {available}",
            )

        location, content = skill
        base_dir = location.parent
        rendered = (
            f'<skill_content name="{name}">\n'
            f"# Skill: {name}\n\n"
            f"{content.strip()}\n\n"
            f"Base directory for this skill: {base_dir}\n"
            "Relative paths in this skill (e.g., scripts/, reference/) are relative to this base directory.\n"
            f"</skill_content>"
        )
        return ToolResult(success=True, output=rendered)

    def _skill_search_paths(self) -> list[Path]:
        """Directories scanned for SKILL.md files."""
        paths: list[Path] = []
        configured = getattr(self.config, "skills_dir", None)
        if configured:
            paths.append(Path(configured))
        root = Path(self.config.project_root or ".")
        paths.append(root / ".anvil" / "skills")
        paths.append(root / "skills")
        paths.append(Path.home() / ".anvil" / "skills")
        return [p for p in paths if p.exists()]

    def _find_skill(self, name: str) -> tuple[Path, str] | None:
        for base in self._skill_search_paths():
            candidate = base / name / "SKILL.md"
            if candidate.exists():
                return candidate, candidate.read_text(encoding="utf-8")
        return None

    def _available_skill_names(self) -> list[str]:
        names: list[str] = []
        for base in self._skill_search_paths():
            for child in base.iterdir():
                if (child / "SKILL.md").exists():
                    names.append(child.name)
        return sorted(set(names))

    # ── main loop ───────────────────────────────────────────────────────

    def run(self, task: str, max_iterations: int = 20) -> EngineResult:
        session = Session(task=task, project_root=self.config.project_root)
        self.session = session
        self._steps_taken = 0

        effective_max = min(max_iterations, self.agent.max_steps) if self.agent.max_steps > 0 else max_iterations

        # Check for @mention subagent dispatch.
        mention = self.agent_manager.parse_mention(task)
        if mention:
            agent_name, sub_task = mention
            sub_agent = self.agent_manager.get(agent_name)
            if sub_agent and sub_agent.is_subagent:
                return self.invoke_subagent(agent_name, sub_task)

        # Auto-invoke: check if a matching agent/skill should be created.
        auto_result = self._try_auto_invoke(task)
        if auto_result is not None:
            return auto_result

        plan = self._plan(task, session)
        if not plan:
            return EngineResult(
                success=False, session=session,
                output="Failed to generate plan", error="No plan",
                agent_name=self.agent.name,
            )

        files_changed: list[str] = []
        verify_results: str = ""
        verify_report = None

        for i in range(min(len(plan), effective_max)):
            if self._steps_taken >= effective_max:
                session.end("completed_max_steps")
                return EngineResult(
                    success=True, session=session,
                    output=f"Reached max_steps limit ({effective_max}) for agent '{self.agent.name}'",
                    agent_name=self.agent.name,
                )
            self._steps_taken += 1

            step_desc = plan[i]
            step = Step(kind=StepKind.EXECUTE, content=step_desc, status=StepStatus.RUNNING)

            execute_result = self._execute(step_desc, files_changed, verify_results, session)
            files_changed.extend(execute_result.get("files_changed", []))

            step_status = StepStatus.SUCCESS if execute_result["success"] else StepStatus.FAILED
            step_step = Step(
                kind=StepKind.EXECUTE, content=step_desc,
                status=step_status,
                tool_calls=[
                    ToolCall(tool=t["tool"], args=t["args"], result=t.get("output", ""))
                    for t in execute_result.get("tool_calls", [])
                ],
            )
            session.add_step(step_step)

            if self.config.verify.enabled and files_changed:
                verify_step = Step(kind=StepKind.VERIFY, content=f"Verify: {', '.join(files_changed[-3:])}")
                verify_report = self.verify.verify(
                    files=files_changed,
                    test_command=self._find_test_command(),
                    working_dir=self.config.tools.working_dir,
                )
                verify_step.verify_result = {
                    "passed": verify_report.passed,
                    "failures": [f.message for f in verify_report.failures],
                }
                verify_results = f"Passed: {verify_report.passed}, Failures: {[f.message for f in verify_report.failures]}"

                if verify_report.passed:
                    verify_step.status = StepStatus.SUCCESS
                    session.add_step(verify_step)
                else:
                    verify_step.status = StepStatus.FAILED
                    session.add_step(verify_step)

                    if self.config.verify.auto_recover:
                        recovered = False
                        for retry in range(self.config.verify.max_retries):
                            recover_step = Step(
                                kind=StepKind.RECOVER, content=f"Recover attempt {retry + 1}",
                                status=StepStatus.RECOVERING,
                            )
                            session.add_step(recover_step)
                            recovery = self._recover(
                                step_desc, verify_report, files_changed, session,
                            )
                            if recovery.get("success"):
                                re_verify = self.verify.verify(
                                    files=files_changed,
                                    test_command=self._find_test_command(),
                                    working_dir=self.config.tools.working_dir,
                                )
                                if re_verify.passed:
                                    recover_step.status = StepStatus.RECOVERED
                                    session.add_step(Step(
                                        kind=StepKind.VERIFY, content="Re-verify after recovery",
                                        status=StepStatus.SUCCESS, verify_result={"passed": True},
                                    ))
                                    recovered = True
                                    break
                                verify_report = re_verify

                        if not recovered:
                            session.end("failed")
                            # Extract memories from the failed task
                            self.memory.extract_from_task(
                                task,
                                f"Failed to recover after {self.config.verify.max_retries} retries",
                                success=False,
                            )
                            return EngineResult(
                                success=False, session=session,
                                output=f"Failed to recover after {self.config.verify.max_retries} retries",
                                verify_report=verify_report,
                                error=f"Verification failed: {[f.message for f in verify_report.failures]}",
                                agent_name=self.agent.name,
                            )

        # ── Final verification gate ──────────────────────────────────────
        # The agent claiming "done" is not enough. Only run when the agent
        # actually changed files (avoids spawning the project's full test suite
        # when nothing was done), and gate success on the real result.
        final_report = verify_report or None
        if self.config.verify.enabled and files_changed:
            test_command = self._find_test_command()
            final_report = self.verify.verify(
                files=files_changed,
                test_command=test_command,
                working_dir=self.config.tools.working_dir,
            )
            session.add_step(Step(
                kind=StepKind.VERIFY,
                content="Final verification",
                status=StepStatus.SUCCESS if final_report.passed else StepStatus.FAILED,
                verify_result={
                    "passed": final_report.passed,
                    "failures": [f.message for f in final_report.failures],
                },
            ))
            if not final_report.passed:
                session.end("failed")
                # Extract memories from the failed task
                self.memory.extract_from_task(
                    task,
                    "Final verification failed",
                    success=False,
                )
                return EngineResult(
                    success=False, session=session,
                    output="Final verification failed",
                    verify_report=final_report,
                    error="Final verification failed: "
                          + "; ".join(f.message for f in final_report.failures),
                    agent_name=self.agent.name,
                )

        session.end("completed")
        if final_report is not None:
            output = "Task completed and verified"
        elif files_changed:
            output = "Task completed (no test command found; changes not test-verified)"
        else:
            output = "Task completed but no file changes were made and nothing was verified"
        
        # Extract memories from the completed task
        self.memory.extract_from_task(task, output, success=True)
        
        return EngineResult(
            success=True, session=session,
            output=output,
            verify_report=final_report,
            agent_name=self.agent.name,
        )

    # ── plan / execute / recover ───────────────────────────────────────

    def _plan(self, task: str, session: Session) -> list[str]:
        step_obj = Step(kind=StepKind.PLAN, content=f"Plan: {task}", status=StepStatus.RUNNING)
        session.add_step(step_obj)

        available_tools = self.agent.available_tools(ALL_TOOL_NAMES)
        system = SYSTEM_PROMPT.format(
            agent_name=self.agent.name,
            tools=", ".join(available_tools),
        )
        # Inject relevant memories
        memory_context = self.memory.get_context_prompt(task, limit=5)
        if memory_context:
            system += f"\n\n{memory_context}"
        instructions_ctx = self._refresh_instructions()
        if instructions_ctx:
            system += f"\n\n{instructions_ctx}"
        messages = [
            Message(role="system", content=system),
            Message(role="user", content=PLAN_PROMPT.format(task=task)),
        ]
        response = self.model.complete(
            messages,
            temperature=self.agent.temperature,
            max_tokens=self.config.model.max_tokens,
            context_window=self.config.model.context_window,
        )
        plan_text = response.content

        steps: list[str] = []
        for line in plan_text.split("\n"):
            line = line.strip()
            if re.match(r'^\d+[\.\)]\s', line) or line.startswith("- "):
                cleaned = re.sub(r'^\d+[\.\)]\s*', '', line).lstrip("- ")
                if cleaned and len(cleaned) > 5:
                    steps.append(cleaned)

        if not steps:
            steps = [task]

        step_obj.status = StepStatus.SUCCESS
        return steps

    def _execute(self, step: str, files_changed: list, verify_results: str, session: Session) -> dict:
        available_tools = self.agent.available_tools(ALL_TOOL_NAMES)
        system = SYSTEM_PROMPT.format(
            agent_name=self.agent.name,
            tools=", ".join(available_tools),
        )
        # Inject relevant memories
        memory_context = self.memory.get_context_prompt(step, limit=3)
        if memory_context:
            system += f"\n\n{memory_context}"
        instructions_ctx = self._refresh_instructions()
        if instructions_ctx:
            system += f"\n\n{instructions_ctx}"
        context = self._gather_file_context(step, files_changed)
        user_content = EXECUTE_PROMPT.format(
            agent_name=self.agent.name,
            plan=self.session.task, step=step,
            files=", ".join(files_changed[-5:]) if files_changed else "none yet",
            verify_results=verify_results or "none yet",
        )
        if context:
            user_content += "\n\n" + context
        messages = [
            Message(role="system", content=system),
            Message(role="user", content=user_content),
        ]
        response = self.model.complete(
            messages,
            temperature=self.agent.temperature,
            max_tokens=self.config.model.max_tokens,
            context_window=self.config.model.context_window,
        )
        tool_calls = self._parse_tool_calls(response.content)
        results: list[dict] = []
        files_in_step: list[str] = []
        for tc in tool_calls:
            # Permission-aware tool execution.
            result = self._execute_tool(tc["tool"], tc["args"])
            results.append({
                "tool": tc["tool"], "args": tc["args"],
                "output": result.output[:500], "success": result.success,
            })
            if result.file_path and result.success:
                files_in_step.append(result.file_path)
        # No tool calls parsed means the model failed to follow the protocol.
        # Retry once with a stronger prompt before giving up.
        if not results:
            retry_messages = [
                Message(role="system", content=system),
                Message(role="user", content=user_content),
                Message(role="assistant", content=response.content[:2000]),
                Message(role="user", content=(
                    "You did NOT emit any ```tool JSON blocks. Your text response does nothing. "
                    "You MUST respond with ```tool blocks to take action. Here is your response:\n\n"
                    f"{response.content[:1000]}\n\n"
                    "Now re-emit your response using ```tool JSON blocks. No prose, just tool blocks."
                )),
            ]
            retry = self.model.complete(
                retry_messages,
                temperature=0.1,
                max_tokens=self.config.model.max_tokens,
                context_window=self.config.model.context_window,
            )
            tool_calls = self._parse_tool_calls(retry.content)
            for tc in tool_calls:
                result = self._execute_tool(tc["tool"], tc["args"])
                results.append({
                    "tool": tc["tool"], "args": tc["args"],
                    "output": result.output[:500], "success": result.success,
                })
                if result.file_path and result.success:
                    files_in_step.append(result.file_path)
            if not results:
                return {
                    "success": False,
                    "tool_calls": [],
                    "files_changed": [],
                    "error": "Model did not emit any valid tool calls (retry also failed)",
                }
        return {
            "success": any(r["success"] for r in results),
            "tool_calls": results,
            "files_changed": files_in_step,
        }

    def _gather_file_context(self, step: str, files_changed: list, max_files: int = 4, max_bytes: int = 4000) -> str:
        """Read files referenced in the step/task plus recently changed files and
        return their current contents so the model can craft exact edits.
        """
        candidates: list[str] = []
        # Files explicitly referenced in the task or step text.
        text = f"{getattr(self.session, 'task', '')} {step}"
        for m in re.findall(r"[\w./\-]+\.[A-Za-z0-9]{1,6}", text):
            candidates.append(m)
        # Recently changed files take priority.
        candidates = list(dict.fromkeys(list(files_changed)[-max_files:] + candidates))

        root = Path(self.config.tools.working_dir or self.config.project_root or ".")
        blocks: list[str] = []
        seen: set[str] = set()
        for ref in candidates:
            if len(blocks) >= max_files:
                break
            path = Path(ref)
            if not path.is_absolute():
                path = root / ref
            try:
                rp = path.resolve()
            except OSError:
                continue
            key = str(rp)
            if key in seen or not rp.is_file():
                continue
            seen.add(key)
            try:
                content = rp.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if len(content) > max_bytes:
                content = content[:max_bytes] + "\n... (truncated)"
            blocks.append(f"### Current contents of {ref}\n```\n{content}\n```")
        if not blocks:
            return ""
        return (
            "Relevant file contents (use exact text for edit old_string):\n\n"
            + "\n\n".join(blocks)
        )

    def _recover(self, step: str, verify_report: VerifyReport, files_changed: list, session: Session) -> dict:
        failures = "\n".join(f"- {f.message}" for f in verify_report.failures)
        context = self._gather_file_context(step, files_changed)
        user_content = RECOVER_PROMPT.format(
            step=step, error=failures,
            verify_report=verify_report.format_summary(),
            files=", ".join(files_changed[-5:]),
        )
        if context:
            user_content += "\n\n" + context
        messages = [
            Message(role="system", content=SYSTEM_PROMPT.format(
                agent_name=self.agent.name,
                tools=", ".join(self.agent.available_tools(ALL_TOOL_NAMES)),
            )),
            Message(role="user", content=user_content),
        ]
        response = self.model.complete(
            messages,
            temperature=self.agent.temperature,
            max_tokens=self.config.model.max_tokens,
            context_window=self.config.model.context_window,
        )
        tool_calls = self._parse_tool_calls(response.content)
        results: list[dict] = []
        fix_files: list[str] = []
        for tc in tool_calls:
            result = self._execute_tool(tc["tool"], tc["args"])
            results.append({
                "tool": tc["tool"], "args": tc["args"],
                "output": result.output[:200], "success": result.success,
            })
            if result.file_path and result.success:
                fix_files.append(result.file_path)
            if result.success:
                files_changed.extend(fix_files)
        return {
            "success": any(r["success"] for r in results) if results else False,
            "tool_calls": results,
        }

    # ── tool-call parser ────────────────────────────────────────────────

    @staticmethod
    def _strip_thinking(text: str) -> str:
        """Remove thinking blocks from model output."""
        text = re.sub(r"<\|begin of thinking\|>.*?<\|end of thinking\|>", "", text, flags=re.DOTALL)
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
        return text

    def _parse_tool_calls(self, text: str) -> list[dict]:
        text = self._strip_thinking(text)

        # 1. Preferred: structured JSON tool calls in ```tool fences.
        structured = self._parse_structured_tool_calls(text)
        if structured:
            return structured

        # 2. Fallback: legacy freeform heuristics (best-effort for weak models).
        calls: list[dict] = []
        patterns = [
            (r'```(\w+)?\n(.*?)```', self._parse_code_block),
            (r'(?:bash|shell|run):\s*`([^`]+)`', lambda m: [{"tool": "bash", "args": {"command": m.group(1)}}]),
            (r'(?:read|cat|view)\s+`([^`]+)`', lambda m: [{"tool": "read", "args": {"path": m.group(1)}}]),
            (r'(?:write|create)\s+`([^`]+)`\s*:\n', lambda m: [{"tool": "write", "args": {"path": m.group(1)}}]),
        ]
        for pattern, handler in patterns:
            for match in re.finditer(pattern, text, re.DOTALL):
                result = handler(match)
                if isinstance(result, list):
                    calls.extend(result)
                elif result:
                    calls.append(result)
        return calls

    def _parse_structured_tool_calls(self, text: str) -> list[dict]:
        """Parse explicit ```tool / ```tool_call / ```json fenced JSON tool calls.

        Each block may contain a single object ``{"tool": ..., "args": {...}}``
        or a JSON array of such objects.  Also handles:
        - double-brace escaping (``{{`` → ``{``) from weak models
        - bare JSON objects outside fences
        """
        import json as _json

        calls: list[dict] = []
        valid_tools = set(ALL_TOOL_NAMES)

        def _try_parse_json(blob: str) -> dict | list | None:
            """Try to parse JSON, with double-brace fixup."""
            try:
                return _json.loads(blob)
            except (ValueError, TypeError):
                pass
            # Weak models emit {{ }} instead of { }
            fixed = blob.replace("{{", "{").replace("}}", "}")
            if fixed != blob:
                try:
                    return _json.loads(fixed)
                except (ValueError, TypeError):
                    pass
            # Try extracting the first JSON object from the blob.
            for start_ch, end_ch in [("{", "}"), ("[", "]")]:
                idx = blob.find(start_ch)
                if idx < 0:
                    continue
                depth = 0
                in_str = False
                escape = False
                for i in range(idx, len(blob)):
                    c = blob[i]
                    if escape:
                        escape = False
                        continue
                    if c == "\\":
                        escape = True
                        continue
                    if c == '"':
                        in_str = not in_str
                        continue
                    if in_str:
                        continue
                    if c == start_ch:
                        depth += 1
                    elif c == end_ch:
                        depth -= 1
                        if depth == 0:
                            try:
                                return _json.loads(blob[idx : i + 1])
                            except (ValueError, TypeError):
                                break
                            break
            return None

        def _extract_calls(parsed) -> list[dict]:
            items = parsed if isinstance(parsed, list) else [parsed]
            result = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                tool = item.get("tool") or item.get("name")
                if tool not in valid_tools:
                    continue
                args = item.get("args") or item.get("arguments") or {}
                if not isinstance(args, dict):
                    continue
                result.append({"tool": tool, "args": args})
            return result

        # A. Fenced tool blocks
        fence = re.compile(r"```(?:tool|tool_call|tool_calls|json)\s*\n(.*?)```", re.DOTALL)
        for match in fence.finditer(text):
            blob = match.group(1).strip()
            if not blob:
                continue
            parsed = _try_parse_json(blob)
            if parsed is not None:
                calls.extend(_extract_calls(parsed))

        if calls:
            return calls

        # B. Bare JSON objects outside fences (some models skip the fences)
        # Use a brace-depth tracker to find balanced JSON objects.
        for m in re.finditer(r'(?<!\w)(\{)', text):
            start = m.start()
            depth = 0
            in_str = False
            esc = False
            end = -1
            for i in range(start, len(text)):
                c = text[i]
                if esc:
                    esc = False
                    continue
                if c == "\\":
                    esc = True
                    continue
                if c == '"':
                    in_str = not in_str
                    continue
                if in_str:
                    continue
                if c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1
                    if depth == 0:
                        end = i
                        break
            if end < 0:
                continue
            blob = text[start : end + 1]
            parsed = _try_parse_json(blob)
            if parsed is not None:
                calls.extend(_extract_calls(parsed))

        if calls:
            return calls

        # C. Natural language fallback — models that describe actions instead of
        #    emitting ```tool blocks.  Only triggers when nothing else matched.
        calls = self._parse_natural_language_tool_calls(text)
        return calls

    def _parse_natural_language_tool_calls(self, text: str) -> list[dict]:
        """Fallback parser for models that describe actions in natural language.

        Detects patterns like:
        - "edit calculator.py to change X to Y"
        - "run pytest -v"
        - "I'll use the edit tool on..."
        """
        calls: list[dict] = []

        # Pattern: "edit <file>" or "modify <file>" with old/new strings
        edit_pats = [
            re.compile(
                r'(?:edit|modify|change|replace|fix)\s+[`"\']?([^\s`"\']+\.py)[`"\']?\s+'
                r'(?:to\s+)?(?:replace|change|fix)\s+[`"\'](.+?)[`"\']\s+(?:with|to)\s+[`"\'](.+?)[`"\']',
                re.IGNORECASE,
            ),
            re.compile(
                r'(?:edit|modify|change|replace|fix)\s+[`"\']?([^\s`"\']+\.py)[`"\']?\s*'
                r'(?:,?\s*(?:where|line)\s+[`"\'](.+?)[`"\']\s+(?:becomes?|→|->|to)\s+[`"\'](.+?)[`"\'])',
                re.IGNORECASE,
            ),
        ]
        for pat in edit_pats:
            for m in pat.finditer(text):
                calls.append({
                    "tool": "edit",
                    "args": {"path": m.group(1), "old_string": m.group(2), "new_string": m.group(3)},
                })

        # Pattern: "run <command>" or "execute <command>"
        cmd_pats = [
            re.compile(r'(?:run|execute|perform)\s+[`"\']?(python[^`"\n]*|pytest[^`"\n]*|npm\s+\w+[^`"\n]*|git\s+\w+[^`"\n]*|pip\s+\w+[^`"\n]*)[`"\']?', re.IGNORECASE),
            re.compile(r'(?:bash|shell|terminal):\s*[`"\']([^`"\']+)[`"\']', re.IGNORECASE),
        ]
        for pat in cmd_pats:
            for m in pat.finditer(text):
                cmd = m.group(1).strip()
                if cmd:
                    calls.append({"tool": "bash", "args": {"command": cmd}})

        # Pattern: "read <file>"
        read_pats = [
            re.compile(r'(?:read|open|view|cat|show)\s+[`"\']?([^\s`"\']+)[`"\']?', re.IGNORECASE),
        ]
        for pat in read_pats:
            for m in pat.finditer(text):
                path = m.group(1)
                if "." in path and not path.startswith("-"):
                    calls.append({"tool": "read", "args": {"path": path}})

        return calls

    def _parse_code_block(self, match) -> dict | None:
        lang = (match.group(1) or "").lower()
        code = match.group(2).strip()
        if not code:
            return None
        if lang in ("bash", "shell", "sh") or code.startswith(("cd ", "ls", "pytest", "python", "pip", "npm", "git")):
            return {"tool": "bash", "args": {"command": code}}
        if lang in ("python", "py", "javascript", "js", "typescript", "ts", "rust", "go"):
            filename = f"solution.{lang[:2]}"
            return {"tool": "write", "args": {"path": filename, "content": code}}
        return {"tool": "bash", "args": {"command": code}}

    def _find_test_command(self) -> str | None:
        import sys

        root = Path(self.config.project_root)
        pytest_cmd = f"{sys.executable} -m pytest -x"
        test_markers = [
            (root / "pytest.ini", pytest_cmd),
            (root / "pyproject.toml", pytest_cmd),
            (root / "setup.cfg", pytest_cmd),
            (root / "tox.ini", pytest_cmd),
            (root / "package.json", "npm test"),
            (root / "Cargo.toml", "cargo test"),
            (root / "go.mod", "go test ./..."),
        ]
        for marker_path, cmd in test_markers:
            if marker_path.exists():
                return cmd
        # Heuristic: detect Python test files even without config markers.
        try:
            for pattern in ("test_*.py", "*_test.py"):
                if any(root.rglob(pattern)):
                    return pytest_cmd
        except OSError:
            pass
        return None
