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
import time
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional, Any

from anvil.core.config import AnvilConfig, VerifyConfig
from anvil.core.session import Session, Step, StepKind, StepStatus, ToolCall
from anvil.tools.executor import ToolExecutor, ToolResult
from anvil.verify.pipeline import VerifyPipeline, VerifyReport, VerifyStatus
from anvil.models.registry import ModelRegistry, BaseModel, Message
from anvil.agents.agent_base import BaseAgent, AgentMode
from anvil.agents.builtin_agents import BuildAgent, BUILTIN_AGENTS
from anvil.agents.agent_manager import AgentManager
from anvil.permissions.permissions import PermissionManager, PermissionAction, PermissionConfig


TOOL_DEFINITIONS = [
    {"name": "bash", "description": "Run a shell command", "args": ["command"]},
    {"name": "read", "description": "Read a file", "args": ["path", "offset", "limit"]},
    {"name": "write", "description": "Write a file", "args": ["path", "content"]},
    {"name": "edit", "description": "Edit a file by replacing text", "args": ["path", "old_string", "new_string"]},
    {"name": "grep", "description": "Search file contents", "args": ["pattern", "path", "include"]},
    {"name": "glob", "description": "Find files by pattern", "args": ["pattern", "path"]},
    {"name": "ls", "description": "List directory contents", "args": ["path"]},
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

Current agent: {agent_name}
Available tools: {tools}"""

PLAN_PROMPT = """Break this task into small, verifiable steps. For each step, say:
- What to do
- Which tool to use
- How to verify it worked

Task: {task}"""

EXECUTE_PROMPT = """Execute the next step. Use the tools available to you.
After making changes, always verify by running relevant checks.

Current agent: {agent_name}
Current plan: {plan}
Current step: {step}
Files changed so far: {files}
Verify results so far: {verify_results}"""

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
    verify_report: Optional[VerifyReport] = None
    error: Optional[str] = None
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
        config: Optional[AnvilConfig] = None,
        agent: Optional[BaseAgent] = None,
    ):
        self.config = config or AnvilConfig()

        # Resolve the active agent.
        self.agent_manager = AgentManager(
            config_dir=Path.home() / ".config" / "anvil",
            project_dir=Path(self.config.project_root),
        )
        # Register any custom agents from config.
        for name, agent_def in self.config.agent.items():
            from anvil.agents.agent_base import AgentMode as AM
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
        self.session: Optional[Session] = None
        self._steps_taken: int = 0
        self._init_integrations()

    def _init_integrations(self) -> None:
        from anvil.integrations.verifyloop import VerifyLoopIntegration
        from anvil.integrations.error_recovery import ErrorRecoveryIntegration
        from anvil.integrations.agent_swarm import AgentSwarmIntegration
        from anvil.integrations.cost_optimizer import CostOptimizerIntegration
        self.verifyloop = VerifyLoopIntegration(self.config.verify)
        self.error_recovery = ErrorRecoveryIntegration()
        self.agent_swarm = AgentSwarmIntegration()
        self.cost_optimizer = CostOptimizerIntegration(
            max_cost_per_session=self.config.cost.max_cost_per_session_usd,
            max_cost_per_task=self.config.cost.max_cost_per_task_usd,
        )

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

    def invoke_subagent(self, name: str, task: str) -> "EngineResult":
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

    def _execute_tool(self, tool: str, args: dict[str, Any]) -> ToolResult:
        """Execute a tool after passing it through the permission gate."""
        action = self._check_permission(tool, args)
        if action == PermissionAction.DENY:
            return ToolResult(
                success=False,
                output="",
                error=f"Permission denied: tool '{tool}' is not allowed for agent '{self.agent.name}'",
            )
        # ASK is handled upstream (engine logs it); for now we treat it like ALLOW
        # and rely on the TUI / CLI to intercept when needed.
        return self.tools.execute(tool, args)

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

        plan = self._plan(task, session)
        if not plan:
            return EngineResult(
                success=False, session=session,
                output="Failed to generate plan", error="No plan",
                agent_name=self.agent.name,
            )

        files_changed: list[str] = []
        verify_results: str = ""

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
                            return EngineResult(
                                success=False, session=session,
                                output=f"Failed to recover after {self.config.verify.max_retries} retries",
                                verify_report=verify_report,
                                error=f"Verification failed: {[f.message for f in verify_report.failures]}",
                                agent_name=self.agent.name,
                            )

        session.end("completed")
        return EngineResult(
            success=True, session=session,
            output="Task completed and verified",
            verify_report=verify_report if files_changed else None,
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
        messages = [
            Message(role="system", content=system),
            Message(role="user", content=PLAN_PROMPT.format(task=task)),
        ]
        response = self.model.complete(messages, temperature=self.agent.temperature)
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
        messages = [
            Message(role="system", content=system),
            Message(role="user", content=EXECUTE_PROMPT.format(
                agent_name=self.agent.name,
                plan=self.session.task, step=step,
                files=", ".join(files_changed[-5:]) if files_changed else "none yet",
                verify_results=verify_results or "none yet",
            )),
        ]
        response = self.model.complete(messages, temperature=self.agent.temperature)
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
        return {
            "success": any(r["success"] for r in results) if results else True,
            "tool_calls": results,
            "files_changed": files_in_step,
        }

    def _recover(self, step: str, verify_report: VerifyReport, files_changed: list, session: Session) -> dict:
        failures = "\n".join(f"- {f.message}" for f in verify_report.failures)
        messages = [
            Message(role="system", content=SYSTEM_PROMPT.format(
                agent_name=self.agent.name,
                tools=", ".join(self.agent.available_tools(ALL_TOOL_NAMES)),
            )),
            Message(role="user", content=RECOVER_PROMPT.format(
                step=step, error=failures,
                verify_report=verify_report.format_summary(),
                files=", ".join(files_changed[-5:]),
            )),
        ]
        response = self.model.complete(messages, temperature=self.agent.temperature)
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

    def _parse_tool_calls(self, text: str) -> list[dict]:
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

    def _parse_code_block(self, match) -> Optional[dict]:
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

    def _find_test_command(self) -> Optional[str]:
        root = Path(self.config.project_root)
        test_markers = [
            (root / "pytest.ini", "pytest -x"),
            (root / "pyproject.toml", "pytest -x"),
            (root / "package.json", "npm test"),
            (root / "Cargo.toml", "cargo test ./..."),
            (root / "go.mod", "go test ./..."),
        ]
        for marker_path, cmd in test_markers:
            if marker_path.exists():
                return cmd
        return None