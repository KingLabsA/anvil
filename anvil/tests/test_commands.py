"""Tests for Anvil command system — built-in commands, custom commands, parsing, tab completion."""

from pathlib import Path

from anvil.commands.command_manager import BUILTIN_COMMANDS, Command, CommandManager

# ---------------------------------------------------------------------------
# Command dataclass
# ---------------------------------------------------------------------------

class TestCommand:
    def test_command_creation(self):
        cmd = Command(name="/test", description="Test command")
        assert cmd.name == "/test"
        assert cmd.description == "Test command"
        assert cmd.handler is None
        assert cmd.template == ""
        assert cmd.hidden is False

    def test_command_with_handler(self):
        handler = lambda args: {"success": True, "output": f"Handled: {args}"}
        cmd = Command(name="/handler", description="With handler", handler=handler)
        result = cmd.handler("test args")
        assert result["success"] is True
        assert "test args" in result["output"]

    def test_command_with_template(self):
        cmd = Command(name="/templated", description="Templated", template="Hello $ARGUMENTS!")
        assert cmd.template == "Hello $ARGUMENTS!"

    def test_command_hidden(self):
        cmd = Command(name="/hidden", description="Hidden", hidden=True)
        assert cmd.hidden is True


# ---------------------------------------------------------------------------
# Built-in commands
# ---------------------------------------------------------------------------

class TestBuiltinCommands:
    def test_all_builtin_commands_defined(self):
        expected = {"/help", "/init", "/undo", "/redo", "/share", "/compact", "/agents", "/models"}
        assert set(BUILTIN_COMMANDS.keys()) == expected

    def test_builtin_commands_have_descriptions(self):
        for name, cmd in BUILTIN_COMMANDS.items():
            assert len(cmd.description) > 0

    def test_builtin_command_names_start_with_slash(self):
        for name in BUILTIN_COMMANDS:
            assert name.startswith("/")


# ---------------------------------------------------------------------------
# CommandManager: register, get, list
# ---------------------------------------------------------------------------

class TestCommandManager:
    def test_init_registers_builtins(self):
        mgr = CommandManager()
        for name in BUILTIN_COMMANDS:
            assert mgr.get(name) is not None

    def test_register_custom_command(self):
        mgr = CommandManager()
        custom = Command(name="/custom", description="My custom command")
        mgr.register(custom)
        assert mgr.get("/custom") is not None

    def test_get_existing_command(self):
        mgr = CommandManager()
        cmd = mgr.get("/help")
        assert cmd is not None
        assert cmd.name == "/help"

    def test_get_nonexistent_command(self):
        mgr = CommandManager()
        assert mgr.get("/nonexistent") is None

    def test_list_commands_excludes_hidden(self):
        mgr = CommandManager()
        hidden_cmd = Command(name="/hidden", description="Hidden", hidden=True)
        mgr.register(hidden_cmd)
        visible = mgr.list(hidden=False)
        names = [c.name for c in visible]
        assert "/hidden" not in names

    def test_list_commands_includes_hidden(self):
        mgr = CommandManager()
        hidden_cmd = Command(name="/hidden", description="Hidden", hidden=True)
        mgr.register(hidden_cmd)
        all_cmds = mgr.list(hidden=True)
        names = [c.name for c in all_cmds]
        assert "/hidden" in names

    def test_list_commands_sorted(self):
        mgr = CommandManager()
        names = [c.name for c in mgr.list()]
        assert names == sorted(names)


# ---------------------------------------------------------------------------
# Command execution
# ---------------------------------------------------------------------------

class TestCommandExecution:
    def test_execute_builtin_command(self):
        mgr = CommandManager()
        result = mgr.execute("/help")
        assert result["success"] is True

    def test_execute_unknown_command(self):
        mgr = CommandManager()
        result = mgr.execute("/nonexistent")
        assert result["success"] is False
        assert "Unknown command" in result["error"]

    def test_execute_with_handler(self):
        handler = lambda args: {"success": True, "output": f"Args: {args}"}
        mgr = CommandManager()
        mgr.register(Command(name="/test", description="Test", handler=handler))
        result = mgr.execute("/test", "hello world")
        assert result["success"] is True
        assert "hello world" in result["output"]

    def test_execute_with_template(self, tmp_path):
        commands_dir = tmp_path / "commands"
        commands_dir.mkdir()
        (commands_dir / "greet.md").write_text("description: Greet someone\n---\nHello, $ARGUMENTS!")
        mgr = CommandManager()
        mgr.load_from_directory(commands_dir)
        result = mgr.execute("/greet", "World")
        assert result["success"] is True
        assert "World" in result["output"]


# ---------------------------------------------------------------------------
# Custom commands from markdown
# ---------------------------------------------------------------------------

class TestCustomCommandsFromMarkdown:
    def test_parse_command_markdown(self):
        mgr = CommandManager()
        markdown = """description: Run all tests
---
Run pytest with verbose output: $ARGUMENTS"""
        cmd = mgr._parse_command_markdown("/test", markdown)
        assert cmd.name == "/test"
        assert "Run all tests" in cmd.description
        assert "pytest" in cmd.template

    def test_parse_command_with_all_fields(self):
        mgr = CommandManager()
        markdown = """description: Generate a component
model: local
temperature: 0.4
---
Create a new component named $ARGUMENTS"""
        cmd = mgr._parse_command_markdown("/component", markdown)
        assert cmd.name == "/component"

    def test_template_variable_substitution(self):
        result = CommandManager._render_template("Hello, $ARGUMENTS!", "World")
        assert result == "Hello, World!"

    def test_template_variable_empty_args(self):
        result = CommandManager._render_template("Hello, $ARGUMENTS!", "")
        assert result == "Hello, !"

    def test_load_from_directory(self, tmp_path):
        commands_dir = tmp_path / "commands"
        commands_dir.mkdir()
        (commands_dir / "test.md").write_text("description: Run tests\n---\npytest -x $ARGUMENTS")
        (commands_dir / "lint.md").write_text("description: Run linter\n---\nruff check $ARGUMENTS")
        mgr = CommandManager()
        cmds = mgr.load_from_directory(commands_dir)
        assert len(cmds) == 2
        assert mgr.get("/test") is not None
        assert mgr.get("/lint") is not None

    def test_load_from_nonexistent_directory(self):
        mgr = CommandManager()
        cmds = mgr.load_from_directory(Path("/nonexistent/path"))
        assert cmds == []


# ---------------------------------------------------------------------------
# Slash command parsing
# ---------------------------------------------------------------------------

class TestSlashCommandParsing:
    def test_parse_simple_command(self):
        cmd, args = CommandManager.parse_slash_command("/help")
        assert cmd == "/help"
        assert args == ""

    def test_parse_command_with_args(self):
        cmd, args = CommandManager.parse_slash_command("/compact now")
        assert cmd == "/compact"
        assert args == "now"

    def test_parse_command_with_multiword_args(self):
        cmd, args = CommandManager.parse_slash_command("/undo 3")
        assert cmd == "/undo"
        assert args == "3"

    def test_parse_non_slash_input(self):
        cmd, args = CommandManager.parse_slash_command("just regular text")
        assert cmd == ""
        assert args == "just regular text"

    def test_parse_empty_input(self):
        cmd, args = CommandManager.parse_slash_command("")
        assert cmd == ""
        assert args == ""


# ---------------------------------------------------------------------------
# Tab completion
# ---------------------------------------------------------------------------

class TestTabCompletion:
    def test_complete_help(self):
        mgr = CommandManager()
        suggestions = mgr.tab_complete("/h")
        assert "/help" in suggestions

    def test_complete_all_commands(self):
        mgr = CommandManager()
        suggestions = mgr.tab_complete("/")
        assert len(suggestions) >= 8  # 8 built-in commands

    def test_complete_no_match(self):
        mgr = CommandManager()
        suggestions = mgr.tab_complete("/xyz")
        assert len(suggestions) == 0

    def test_complete_case_insensitive(self):
        mgr = CommandManager()
        suggestions = mgr.tab_complete("/H")
        assert any("/help" in s for s in suggestions)

    def test_complete_excludes_hidden(self):
        mgr = CommandManager()
        hidden_cmd = Command(name="/hidden_cmd", description="Hidden", hidden=True)
        mgr.register(hidden_cmd)
        suggestions = mgr.tab_complete("/")
        assert "/hidden_cmd" not in suggestions

    def test_complete_requires_slash_prefix(self):
        mgr = CommandManager()
        suggestions = mgr.tab_complete("help")
        assert len(suggestions) == 0

    def test_complete_partial_match(self):
        mgr = CommandManager()
        suggestions = mgr.tab_complete("/co")
        assert "/compact" in suggestions
