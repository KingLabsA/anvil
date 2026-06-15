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


BUILTIN_COMMANDS: dict[str, Command] = {
    "/help": Command(name="/help", description="Show available commands", hidden=False),
    "/init": Command(name="/init", description="Initialize anvil config and rules", hidden=False),
    "/undo": Command(name="/undo", description="Undo the last file change", hidden=False),
    "/redo": Command(name="/redo", description="Redo the last undone change", hidden=False),
    "/share": Command(name="/share", description="Generate a share link for current state", hidden=False),
    "/compact": Command(name="/compact", description="Compact conversation context", hidden=False),
    "/agents": Command(name="/agents", description="List available agents", hidden=False),
    "/models": Command(name="/models", description="List available models", hidden=False),
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
            return {"success": True, "output": rendered}

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
