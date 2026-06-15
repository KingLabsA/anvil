"""Command manager — built-in slash commands, custom commands, and tab completion."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Command:
    """A slash command definition."""
    name: str
    description: str
    handler: Callable | None = None
    template: str = ""
    hidden: bool = False


# ── Compound Engineering flows ────────────────────────────────────────────
# Structured agentic workflows (inspired by Matt Van Horn's compound-engineering
# skills) mapped onto Anvil's Plan → Execute → Verify → Recover loop. Each is a
# prompt template rendered with $ARGUMENTS and fed to the active agent.

_BRAINSTORM_TEMPLATE = """You are in BRAINSTORM mode. Do NOT write code yet.

Goal: $ARGUMENTS

Steps:
1. Use `read`, `grep`, `glob` to explore the relevant parts of the codebase.
2. Identify constraints, existing patterns, and edge cases.
3. Ask clarifying questions only if truly blocking.
4. Produce a concise requirements document with:
   - Problem statement
   - Proposed approach (2-3 options with trade-offs, then a recommendation)
   - Affected files/modules
   - Edge cases and risks
   - Open questions

Output the requirements doc as markdown. End by suggesting `/plan` as the next step."""

_PLAN_TEMPLATE = """You are in PLAN mode. Do NOT modify files yet.

Task: $ARGUMENTS

Steps:
1. Research the codebase (`read`, `grep`, `glob`) to understand current behavior.
2. Map the exact implementation path: which files change and how.
3. Enumerate edge cases and how each will be handled.
4. Define the verification strategy (tests, lint, type checks) for each step.

Produce a numbered, verifiable implementation plan. Each step must state:
- What to do
- Which tool(s) to use
- How to verify it worked

End by suggesting `/work` to execute the plan."""

_WORK_TEMPLATE = """You are in WORK mode. Execute the plan with the full verify-loop.

Plan / task: $ARGUMENTS

Rules:
- Follow the project's existing patterns and conventions.
- Implement one step at a time.
- After each change, VERIFY (syntax, tests, lint). If verification fails,
  diagnose and RECOVER automatically before moving on.
- Never claim done without verifying.
- When finished, summarize what changed and how it was verified."""

_LFG_TEMPLATE = """You are running the FULL compound-engineering loop end to end.

Objective: $ARGUMENTS

Run all phases in order, without stopping for confirmation unless truly blocked:
1. BRAINSTORM — explore the codebase and write a short requirements doc.
2. PLAN — produce a numbered, verifiable implementation plan.
3. WORK — implement the plan step by step, verifying and recovering after each change.
4. WRAP-UP — run the full test/lint suite, summarize all changes, and prepare a
   conventional-commit message and PR description.

Use the `task` tool to delegate independent sub-tasks to subagents when helpful.
Use the `skill` tool if a loaded skill matches the work. Verify everything."""


BUILTIN_COMMANDS: dict[str, Command] = {
    "/help": Command(name="/help", description="Show available commands", hidden=False),
    "/init": Command(name="/init", description="Initialize anvil config and rules", hidden=False),
    "/undo": Command(name="/undo", description="Undo the last file change", hidden=False),
    "/redo": Command(name="/redo", description="Redo the last undone change", hidden=False),
    "/share": Command(name="/share", description="Generate a share link for current state", hidden=False),
    "/compact": Command(name="/compact", description="Compact conversation context", hidden=False),
    "/agents": Command(name="/agents", description="List available agents", hidden=False),
    "/models": Command(name="/models", description="List available models", hidden=False),
    # Compound Engineering flows
    "/brainstorm": Command(
        name="/brainstorm",
        description="Explore the codebase and produce a requirements doc (no code)",
        template=_BRAINSTORM_TEMPLATE,
    ),
    "/plan": Command(
        name="/plan",
        description="Research and produce a numbered, verifiable implementation plan",
        template=_PLAN_TEMPLATE,
    ),
    "/work": Command(
        name="/work",
        description="Execute a plan with the full Plan→Execute→Verify→Recover loop",
        template=_WORK_TEMPLATE,
    ),
    "/lfg": Command(
        name="/lfg",
        description="Run the full loop: brainstorm → plan → work → wrap-up/PR",
        template=_LFG_TEMPLATE,
    ),
}


class CommandManager:
    """Manage built-in and custom slash commands."""

    def __init__(self, project_root: str | None = None) -> None:
        self.project_root = Path(project_root) if project_root else Path.cwd()
        self._commands: dict[str, Command] = dict(BUILTIN_COMMANDS)
        self._custom_templates: dict[str, str] = {}

    def register(self, command: Command) -> None:
        """Register a command (built-in or custom)."""
        self._commands[command.name] = command

    def get(self, name: str) -> Command | None:
        """Get a command by name."""
        return self._commands.get(name)

    def list(self, hidden: bool = False) -> list[Command]:
        """List available commands. If hidden=False, exclude hidden commands."""
        commands = list(self._commands.values())
        if not hidden:
            commands = [c for c in commands if not c.hidden]
        return sorted(commands, key=lambda c: c.name)

    def execute(self, name: str, args: str = "") -> dict:
        """Execute a command by name with arguments.

        Returns a dict with 'success', 'output', and optionally 'error'.
        """
        cmd = self._commands.get(name)
        if not cmd:
            return {"success": False, "output": "", "error": f"Unknown command: {name}"}

        if cmd.handler:
            return cmd.handler(args)

        if name in self._custom_templates:
            rendered = self._render_template(self._custom_templates[name], args)
            return {"success": True, "output": rendered, "prompt": rendered}

        if cmd.template:
            rendered = self._render_template(cmd.template, args)
            return {"success": True, "output": rendered, "prompt": rendered}

        return {"success": True, "output": f"Executed {name}"}

    def load_from_directory(self, path: Path) -> list[Command]:
        """Load custom commands from markdown files in a directory."""
        if not path.exists():
            return []
        commands: list[Command] = []
        for f in sorted(path.glob("*.md")):
            text = f.read_text(encoding="utf-8").strip()
            name = f"/{f.stem}"
            cmd = self._parse_command_markdown(name, text)
            self.register(cmd)
            commands.append(cmd)
        return commands

    def _parse_command_markdown(self, name: str, text: str) -> Command:
        """Parse a command definition from markdown."""
        lines = text.strip().split("\n")
        description = ""
        template_lines: list[str] = []
        in_template = False

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("description:") or stripped.startswith("Description:"):
                description = stripped.split(":", 1)[1].strip()
            elif stripped == "---":
                in_template = True
                continue
            elif in_template:
                template_lines.append(line)

        template = "\n".join(template_lines).strip()
        cmd = Command(name=name, description=description, template=template)

        if template:
            self._custom_templates[name] = template

        return cmd

    @staticmethod
    def _render_template(template: str, args: str) -> str:
        """Render a command template, substituting $ARGUMENTS."""
        return template.replace("$ARGUMENTS", args)

    @staticmethod
    def parse_slash_command(text: str) -> tuple[str, str]:
        """Parse a slash command from text input.

        Returns (command_name, arguments) tuple.

        Examples::

            "/help" → ("/help", "")
            "/compact now" → ("/compact", "now")
            "/undo 3" → ("/undo", "3")
        """
        text = text.strip()
        if not text.startswith("/"):
            return ("", text)
        parts = text.split(None, 1)
        if not parts:
            return ("", "")
        command = parts[0]
        args = parts[1] if len(parts) > 1 else ""
        return (command, args)

    def tab_complete(self, partial: str) -> list[str]:
        """Return command names matching a partial input."""
        if not partial.startswith("/"):
            return []
        partial = partial.lower()
        return [
            cmd.name for cmd in self._commands.values()
            if not cmd.hidden and cmd.name.lower().startswith(partial)
        ]
