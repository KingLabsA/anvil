"""Tests for terminal autocomplete."""

import pytest
from anvil.terminal.autocomplete import TerminalAutocomplete, CommandSuggestion


class TestTerminalAutocomplete:
    """Test terminal autocomplete."""
    
    def test_init(self):
        ac = TerminalAutocomplete()
        assert ac.working_dir == "."
    
    def test_get_suggestions_empty(self):
        ac = TerminalAutocomplete()
        suggestions = ac.get_suggestions("")
        assert suggestions == []
    
    def test_get_suggestions_command(self):
        ac = TerminalAutocomplete()
        suggestions = ac.get_suggestions("ls")
        assert len(suggestions) > 0
        assert any(s.command == "ls" for s in suggestions)
    
    def test_get_suggestions_partial(self):
        ac = TerminalAutocomplete()
        suggestions = ac.get_suggestions("py")
        assert len(suggestions) > 0
        assert any("python" in s.command for s in suggestions)
    
    def test_get_suggestions_limit(self):
        ac = TerminalAutocomplete()
        suggestions = ac.get_suggestions("a", limit=3)
        assert len(suggestions) <= 3
    
    def test_get_command_help(self):
        ac = TerminalAutocomplete()
        help_text = ac.get_command_help("ls")
        assert "List" in help_text or "directory" in help_text.lower()
    
    def test_path_suggestions(self):
        ac = TerminalAutocomplete()
        suggestions = ac.get_suggestions("./")
        assert isinstance(suggestions, list)


class TestCommandSuggestion:
    """Test command suggestion dataclass."""
    
    def test_create_suggestion(self):
        suggestion = CommandSuggestion(
            command="ls",
            description="List directory contents",
            category="command",
        )
        assert suggestion.command == "ls"
        assert suggestion.description == "List directory contents"
        assert suggestion.category == "command"
