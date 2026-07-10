"""Tool execution layer — Bash, Read, Write, Edit, Grep, Glob, Ls, + OpenCode tools."""

from __future__ import annotations

import difflib
import fnmatch
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from anvil.tools.new_tools import (
    TodoListManager,
    apply_patch,
    image,
    question,
    todowrite,
    webfetch,
    websearch,
)


@dataclass
class ToolResult:
    success: bool
    output: str
    error: str | None = None
    exit_code: int = 0
    file_path: str | None = None
    diff: str | None = None
    duration_ms: float = 0.0


class ToolExecutor:
    def __init__(self, working_dir: str, timeout: int = 30, sandbox: bool = False):
        self.working_dir = Path(working_dir).resolve()
        self.timeout = timeout
        self.sandbox = sandbox
        self.todo_manager = TodoListManager()
        self.blocked_patterns = [
            re.compile(r'\brm\s+-rf\s+/[ /\t]*$'),
            re.compile(r'\bmkfs\b'),
            re.compile(r'\bdd\s+if='),
            re.compile(r':\(\)\{'),
            re.compile(r'fork\s+bomb'),
            re.compile(r'>\s*/dev/sd[a-z]'),
            re.compile(r'chmod\s+-R\s+777\s+/'),
        ]
        self.confirm_patterns = [
            re.compile(r'\bgit push\b'),
            re.compile(r'\bgit reset --hard\b'),
            re.compile(r'\bDROP\s+TABLE\b', re.IGNORECASE),
            re.compile(r'\bDELETE\s+FROM\b', re.IGNORECASE),
        ]

    def execute(self, tool: str, args: dict[str, Any]) -> ToolResult:
        dispatch = {
            "bash": self.run_bash,
            "read": self.read_file,
            "write": self.write_file,
            "edit": self.edit_file,
            "grep": self.search_content,
            "glob": self.search_files,
            "ls": self.list_directory,
            "apply_patch": self._run_apply_patch,
            "todowrite": self._run_todowrite,
            "webfetch": self._run_webfetch,
            "websearch": self._run_websearch,
            "question": self._run_question,
            "image": self._run_image,
        }
        handler = dispatch.get(tool)
        if not handler:
            return ToolResult(success=False, output="", error=f"Unknown tool: {tool}")
        try:
            return handler(args)
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))

    def run_bash(self, args: dict[str, Any]) -> ToolResult:
        command = args.get("command", "")
        if not command:
            return ToolResult(success=False, output="", error="No command provided")
        for pattern in self.blocked_patterns:
            if pattern.search(command):
                return ToolResult(
                    success=False, output="",
                    error=f"Blocked: command matches dangerous pattern '{pattern.pattern}'",
                )
        import time
        start = time.time()
        try:
            result = subprocess.run(
                command, shell=True, capture_output=True, text=True,
                timeout=self.timeout, cwd=str(self.working_dir),
            )
            duration = (time.time() - start) * 1000
            output = result.stdout
            if result.stderr:
                output += f"\n[stderr]\n{result.stderr}" if output else result.stderr
            return ToolResult(
                success=result.returncode == 0,
                output=output[:50000],
                exit_code=result.returncode,
                duration_ms=duration,
            )
        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False, output="",
                error=f"Command timed out after {self.timeout}s",
                duration_ms=self.timeout * 1000,
            )

    def read_file(self, args: dict[str, Any]) -> ToolResult:
        path = self._resolve_path(args.get("path", ""))
        if not path:
            return ToolResult(success=False, output="", error="No path provided")
        if not path.exists():
            return ToolResult(success=False, output="", error=f"File not found: {path}")
        if path.is_dir():
            return self.list_directory({"path": str(path)})
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
            start = args.get("offset", 0)
            limit = args.get("limit", len(content.split("\n")))
            lines = content.split("\n")
            selected = lines[start:start + limit]
            numbered = [f"{i + start + 1:6d}: {line}" for i, line in enumerate(selected)]
            return ToolResult(
                success=True, output="\n".join(numbered), file_path=str(path),
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))

    def write_file(self, args: dict[str, Any]) -> ToolResult:
        path = self._resolve_path(args.get("path", ""))
        content = args.get("content", "")
        if not path:
            return ToolResult(success=False, output="", error="No path provided")
        path.parent.mkdir(parents=True, exist_ok=True)
        old_content = ""
        if path.exists():
            old_content = path.read_text(encoding="utf-8", errors="replace")
        diff = difflib.unified_diff(
            old_content.splitlines(keepends=True),
            content.splitlines(keepends=True),
            fromfile=f"a/{path.name}", tofile=f"b/{path.name}",
        )
        path.write_text(content, encoding="utf-8")
        return ToolResult(
            success=True, output=f"Wrote {len(content)} chars to {path}",
            file_path=str(path), diff="".join(diff) if diff else None,
        )

    def edit_file(self, args: dict[str, Any]) -> ToolResult:
        path = self._resolve_path(args.get("path", ""))
        if not path or not path.exists():
            return ToolResult(success=False, output="", error=f"File not found: {path}")
        old = args.get("old_string", "")
        new = args.get("new_string", "")
        content = path.read_text(encoding="utf-8", errors="replace")
        if old not in content:
            return ToolResult(
                success=False, output="",
                error=f"old_string not found in {path}",
            )
        occurrences = content.count(old)
        replace_all = args.get("replace_all", False)
        if occurrences > 1 and not replace_all:
            return ToolResult(
                success=False, output="",
                error=f"Found {occurrences} matches. Use replace_all=True or provide more context.",
            )
        new_content = content.replace(old, new) if replace_all else content.replace(old, new, 1)
        diff = difflib.unified_diff(
            content.splitlines(keepends=True),
            new_content.splitlines(keepends=True),
            fromfile=f"a/{path.name}", tofile=f"b/{path.name}",
        )
        path.write_text(new_content, encoding="utf-8")
        return ToolResult(
            success=True, output=f"Edited {path}: replaced {occurrences} occurrence(s)",
            file_path=str(path), diff="".join(diff),
        )

    def search_content(self, args: dict[str, Any]) -> ToolResult:
        pattern = args.get("pattern", "")
        path = self._resolve_path(args.get("path", str(self.working_dir)))
        include = args.get("include", "*")
        if not pattern:
            return ToolResult(success=False, output="", error="No pattern provided")
        results = []
        regex = re.compile(pattern, re.MULTILINE)
        search_dir = path if path.is_dir() else path.parent
        for filepath in search_dir.rglob("*"):
            if filepath.is_file() and fnmatch.fnmatch(filepath.name, include):
                if any(p in str(filepath) for p in [".git", "node_modules", "__pycache__", ".venv"]):
                    continue
                try:
                    for i, line in enumerate(filepath.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                        if regex.search(line):
                            results.append(f"{filepath}:{i}: {line.strip()}")
                except Exception:
                    continue
                if len(results) >= 200:
                    break
        return ToolResult(
            success=True,
            output="\n".join(results) if results else "No matches found",
        )

    def search_files(self, args: dict[str, Any]) -> ToolResult:
        pattern = args.get("pattern", "*")
        path = self._resolve_path(args.get("path", str(self.working_dir)))
        if not path.is_dir():
            path = path.parent
        matches = sorted(str(p) for p in path.rglob(pattern) if not any(
            x in str(p) for x in [".git", "node_modules", "__pycache__", ".venv"]
        ))
        return ToolResult(
            success=True,
            output="\n".join(matches[:500]) if matches else "No files found",
        )

    def list_directory(self, args: dict[str, Any]) -> ToolResult:
        path = self._resolve_path(args.get("path", str(self.working_dir)))
        if not path.is_dir():
            return ToolResult(success=False, output="", error=f"Not a directory: {path}")
        entries = []
        for item in sorted(path.iterdir()):
            prefix = "[DIR]" if item.is_dir() else "[FILE]"
            size = item.stat().st_size if item.is_file() else 0
            entries.append(f"{prefix} {item.name}" + (f" ({size}b)" if size else ""))
        return ToolResult(success=True, output="\n".join(entries))

    # --- New tool adapters delegating to new_tools module ---

    def _run_apply_patch(self, args: dict[str, Any]) -> ToolResult:
        return apply_patch(args, self.working_dir)

    def _run_todowrite(self, args: dict[str, Any]) -> ToolResult:
        return todowrite(args, self.todo_manager)

    def _run_webfetch(self, args: dict[str, Any]) -> ToolResult:
        return webfetch(args)

    def _run_websearch(self, args: dict[str, Any]) -> ToolResult:
        return websearch(args)

    def _run_question(self, args: dict[str, Any]) -> ToolResult:
        return question(args)

    def _run_image(self, args: dict[str, Any]) -> ToolResult:
        return image(args, self.working_dir)

    def _resolve_path(self, path: str) -> Path:
        if not path:
            return self.working_dir
        p = Path(path)
        if not p.is_absolute():
            p = self.working_dir / p
        resolved = p.resolve()
        wd = self.working_dir.resolve()
        if self.sandbox and not str(resolved).startswith(str(wd)):
            raise PermissionError(f"Path traversal blocked: {path} resolves outside working directory {wd}")
        return resolved


TOOL_DEFINITIONS = [
    {"name": "bash", "description": "Run a shell command", "args": ["command"]},
    {"name": "read", "description": "Read a file", "args": ["path", "offset", "limit"]},
    {"name": "write", "description": "Write a file", "args": ["path", "content"]},
    {"name": "edit", "description": "Edit a file by replacing text", "args": ["path", "old_string", "new_string"]},
    {"name": "grep", "description": "Search file contents", "args": ["pattern", "path", "include"]},
    {"name": "glob", "description": "Find files by pattern", "args": ["pattern", "path"]},
    {"name": "ls", "description": "List directory contents", "args": ["path"]},
    {"name": "apply_patch", "description": "Apply unified diffs/patches to files", "args": ["action", "path", "content", "patch", "destination"]},
    {"name": "todowrite", "description": "Manage todo/task lists", "args": ["action", "content", "priority", "id", "status"]},
    {"name": "webfetch", "description": "Fetch web content by URL", "args": ["url", "max_length"]},
    {"name": "websearch", "description": "Search the web", "args": ["query"]},
    {"name": "question", "description": "Ask the user a question", "args": ["question", "options"]},
    {"name": "image", "description": "Load and inspect an image file", "args": ["path"]},
]

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

Available tools: {tools}"""
