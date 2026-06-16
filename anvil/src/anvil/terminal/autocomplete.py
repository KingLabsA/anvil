"""Terminal autocomplete for Anvil - suggest shell commands."""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from typing import Optional


@dataclass
class CommandSuggestion:
    """A command suggestion for autocomplete."""
    command: str
    description: str
    category: str


class TerminalAutocomplete:
    """Autocomplete for shell commands and file paths."""
    
    # Common commands with descriptions
    COMMON_COMMANDS = {
        "ls": "List directory contents",
        "cd": "Change directory",
        "pwd": "Print working directory",
        "mkdir": "Create directory",
        "rm": "Remove file or directory",
        "cp": "Copy file or directory",
        "mv": "Move/rename file",
        "cat": "Display file contents",
        "grep": "Search file contents",
        "find": "Find files by pattern",
        "echo": "Display text",
        "export": "Set environment variable",
        "python": "Run Python script",
        "pip": "Python package manager",
        "node": "Run Node.js script",
        "npm": "Node package manager",
        "git": "Version control",
        "docker": "Container management",
        "curl": "HTTP client",
        "wget": "Download files",
        "tar": "Archive files",
        "zip": "Create zip archive",
        "unzip": "Extract zip archive",
        "chmod": "Change file permissions",
        "chown": "Change file ownership",
        "ps": "List processes",
        "kill": "Kill process",
        "top": "System monitor",
        "df": "Disk space usage",
        "du": "Directory size",
        "which": "Locate command",
        "type": "Display command type",
        "history": "Command history",
        "clear": "Clear terminal",
        "exit": "Exit shell",
    }
    
    def __init__(self, working_dir: str = "."):
        self.working_dir = working_dir
    
    def get_suggestions(self, partial: str, limit: int = 10) -> list[CommandSuggestion]:
        """Get command suggestions for partial input."""
        suggestions = []
        
        # Split into command and args
        parts = partial.split()
        if not parts:
            return []
        
        command = parts[0]
        
        # If we're completing a command name
        if len(parts) == 1:
            for cmd, desc in self.COMMON_COMMANDS.items():
                if cmd.startswith(command):
                    suggestions.append(CommandSuggestion(
                        command=cmd,
                        description=desc,
                        category="command",
                    ))
        else:
            # If we're completing arguments, suggest files/directories
            suggestions.extend(self._get_path_suggestions(parts[-1]))
        
        return suggestions[:limit]
    
    def _get_path_suggestions(self, partial: str) -> list[CommandSuggestion]:
        """Get file/directory path suggestions."""
        suggestions = []
        
        try:
            # Determine directory and prefix
            if "/" in partial:
                directory = str(Path(partial).parent)
                prefix = Path(partial).name
            else:
                directory = "."
                prefix = partial
            
            # List directory contents
            dir_path = Path(self.working_dir) / directory
            if dir_path.exists():
                for item in dir_path.iterdir():
                    name = item.name
                    if name.startswith(prefix):
                        if item.is_dir():
                            suggestions.append(CommandSuggestion(
                                command=f"{directory}/{name}/",
                                description="Directory",
                                category="directory",
                            ))
                        else:
                            suggestions.append(CommandSuggestion(
                                command=f"{directory}/{name}",
                                description="File",
                                category="file",
                            ))
        except Exception:
            pass
        
        return suggestions
    
    def get_command_help(self, command: str) -> str:
        """Get help for a command."""
        if command in self.COMMON_COMMANDS:
            return self.COMMON_COMMANDS[command]
        
        # Try to get help from the command itself
        try:
            result = subprocess.run(
                [command, "--help"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            return result.stdout[:500] if result.stdout else "No help available"
        except Exception:
            return "No help available"
