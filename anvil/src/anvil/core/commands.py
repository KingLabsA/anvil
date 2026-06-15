"""Custom commands system — built-in and user-defined slash commands."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class CommandScope(Enum):
    BUILTIN = "builtin"
    PROJECT = "project"
    USER = "user"


@dataclass
class Command:
    """A slash command definition."""
    name: str
    description: str = ""
    template: str = ""
    agent: str | None = None
    model: str | None = None
    scope: CommandScope = CommandScope.BUILTIN
    source: str = ""
    examples: list[str] = field(default_factory=list)

    def format_template(self, arguments: str = "") -> str:
        """Format the command template with provided arguments."""
        if not self.template:
            return arguments
        result = self.template.replace("$ARGUMENTS", arguments)
        result = result.replace("$ARGS", arguments)
        result = result.replace("$1", arguments)
        return result

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "template": self.template,
            "agent": self.agent,
            "model": self.model,
            "scope": self.scope.value,
            "source": self.source,
            "examples": self.examples,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Command:
        scope = data.get("scope", "builtin")
        if isinstance(scope, str):
            scope = CommandScope(scope)
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            template=data.get("template", ""),
            agent=data.get("agent"),
            model=data.get("model"),
            scope=scope,
            source=data.get("source", ""),
            examples=data.get("examples", []),
        )

    @classmethod
    def from_markdown(cls, content: str, source: str = "") -> list[Command]:
        """Parse commands from markdown with frontmatter.

        Format:
        ---
        name: /command-name
        description: What it does
        agent: optional-agent
        model: optional-model
        ---

        Template body with $ARGUMENTS placeholder.
        """
        commands = []
        frontmatter_match = re.match(r'^---\s*\n(.*?)\n---\s*\n(.*)', content, re.DOTALL)
        if frontmatter_match:
            meta_section = frontmatter_match.group(1)
            body = frontmatter_match.group(2).strip()

            meta: dict[str, Any] = {}
            for line in meta_section.split("\n"):
                if ":" in line:
                    key, _, value = line.partition(":")
                    key = key.strip().lower()
                    value = value.strip()
                    if key in ("name", "description", "agent", "model"):
                        meta[key] = value
                    elif key == "template":
                        meta["template"] = value

            name = meta.get("name", "")
            if name and not name.startswith("/"):
                name = "/" + name

            if body and not meta.get("template"):
                meta["template"] = body

            if name:
                cmd = cls(
                    name=name,
                    description=meta.get("description", ""),
                    template=meta.get("template", body),
                    agent=meta.get("agent"),
                    model=meta.get("model"),
                    scope=CommandScope.USER,
                    source=source,
                )
                commands.append(cmd)
        else:
            lines = content.strip().split("\n")
            if lines:
                first_line = lines[0].strip()
                name_match = re.match(r'^(/\w+)', first_line)
                if name_match:
                    name = name_match.group(1)
                    desc = first_line[len(name):].strip().lstrip("-").strip()
                    template = "\n".join(lines[1:]).strip() if len(lines) > 1 else ""
                    cmd = cls(
                        name=name,
                        description=desc,
                        template=template,
                        scope=CommandScope.USER,
                        source=source,
                    )
                    commands.append(cmd)

        return commands


class CommandManager:
    """Manage built-in and custom slash commands."""

    def __init__(self, project_root: str | None = None):
        self.project_root = Path(project_root) if project_root else Path.cwd()
        self._commands: dict[str, Command] = {}
        self._load_builtin_commands()
        self._load_config_commands()
        self._load_directory_commands()

    def _load_builtin_commands(self) -> None:
        """Register built-in commands."""
        builtins = [
            Command(name="/help", description="Show available commands", template="List all available commands and their descriptions.", scope=CommandScope.BUILTIN),
            Command(name="/init", description="Initialize an Anvil project", template="Initialize a new Anvil project in the current directory. Set up configuration, create .anvil/ directory structure.", scope=CommandScope.BUILTIN),
            Command(name="/undo", description="Undo the last change", template="Revert the most recent change using the snapshot system.", scope=CommandScope.BUILTIN),
            Command(name="/redo", description="Redo a reverted change", template="Re-apply the most recently undone change using the snapshot system.", scope=CommandScope.BUILTIN),
            Command(name="/share", description="Share the current session", template="Generate a shareable link for the current session.", scope=CommandScope.BUILTIN),
            Command(name="/compact", description="Compact the context window", template="Summarize old messages and prune tool outputs to free up context space.", scope=CommandScope.BUILTIN),
            Command(name="/agents", description="List available agents", template="List all registered MCP agents and their capabilities.", scope=CommandScope.BUILTIN),
            Command(name="/models", description="List available models", template="List all configured models and their capabilities.", scope=CommandScope.BUILTIN),
        ]
        for cmd in builtins:
            self._commands[cmd.name] = cmd

    def _load_config_commands(self) -> None:
        """Load custom commands from config file (opencode.json / anvil.json)."""
        config_paths = [
            self.project_root / "opencode.json",
            self.project_root / "anvil.json",
        ]
        for config_path in config_paths:
            if not config_path.exists():
                continue
            try:
                import json
                data = json.loads(config_path.read_text())
                custom_cmds = data.get("command", {}).get("custom_commands", {})
                for name, cmd_data in custom_cmds.items():
                    if not name.startswith("/"):
                        name = "/" + name
                    cmd_data["name"] = name
                    cmd_data["scope"] = "project"
                    cmd_data["source"] = str(config_path)
                    cmd = Command.from_dict(cmd_data)
                    self._commands[cmd.name] = cmd
            except (json.JSONDecodeError, KeyError, TypeError):
                continue

    def _load_directory_commands(self) -> None:
        """Load command files from .anvil/commands/ directory."""
        commands_dir = self.project_root / ".anvil" / "commands"
        if not commands_dir.exists():
            return

        for cmd_file in sorted(commands_dir.glob("*.md")):
            try:
                content = cmd_file.read_text(encoding="utf-8")
                commands = Command.from_markdown(content, source=str(cmd_file))
                for cmd in commands:
                    self._commands[cmd.name] = cmd
            except OSError:
                continue

    def get(self, name: str) -> Command | None:
        """Get a command by name."""
        if not name.startswith("/"):
            name = "/" + name
        return self._commands.get(name)

    def list_commands(self) -> list[Command]:
        """List all registered commands."""
        return sorted(self._commands.values(), key=lambda c: (c.scope.value, c.name))

    def register(self, command: Command) -> None:
        """Register a new command."""
        if not command.name.startswith("/"):
            command.name = "/" + command.name
        self._commands[command.name] = command

    def unregister(self, name: str) -> bool:
        """Remove a command. Cannot remove builtins."""
        if not name.startswith("/"):
            name = "/" + name
        cmd = self._commands.get(name)
        if cmd and cmd.scope == CommandScope.BUILTIN:
            return False
        return self._commands.pop(name, None) is not None

    def parse(self, input_str: str) -> tuple[Command | None, str]:
        """Parse a slash command from user input.

        Returns (command, arguments) or (None, original_input) if not a command.
        """
        input_str = input_str.strip()
        if not input_str.startswith("/"):
            return None, input_str

        parts = input_str.split(maxsplit=1)
        cmd_name = parts[0]
        arguments = parts[1] if len(parts) > 1 else ""

        command = self.get(cmd_name)
        return command, arguments

    def format_help(self) -> str:
        """Format help text for all commands."""
        lines = ["Available commands:"]
        current_scope = ""
        for cmd in self.list_commands():
            scope_label = {
                CommandScope.BUILTIN: "Built-in",
                CommandScope.PROJECT: "Project",
                CommandScope.USER: "User",
            }.get(cmd.scope, cmd.scope.value)

            if scope_label != current_scope:
                current_scope = scope_label
                lines.append(f"\n  {scope_label}:")

            desc = f" — {cmd.description}" if cmd.description else ""
            lines.append(f"    {cmd.name}{desc}")

        return "\n".join(lines)

    def tab_complete(self, partial: str) -> list[str]:
        """Return command names that start with the partial input."""
        if not partial.startswith("/"):
            prefix = "/" + partial
        else:
            prefix = partial

        return sorted(
            name for name in self._commands
            if name.startswith(prefix)
        )
