"""New tools for Anvil — apply_patch, todowrite, webfetch, websearch, question, image."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class TodoItem:
    id: str
    content: str
    status: str = "pending"
    priority: str = "medium"


class TodoListManager:
    """Manage a list of todo items."""

    PRIORITY_LEVELS = ["low", "medium", "high", "critical"]
    STATUS_TRANSITIONS = {
        "pending": ["in_progress", "cancelled"],
        "in_progress": ["completed", "cancelled"],
        "completed": [],
        "cancelled": ["pending"],
    }

    def __init__(self) -> None:
        self._todos: list[TodoItem] = []
        self._id_counter = 0

    def add(self, content: str, priority: str = "medium") -> TodoItem:
        self._id_counter += 1
        item = TodoItem(id=f"todo_{self._id_counter:03d}", content=content, priority=priority)
        self._todos.append(item)
        return item

    def update(self, item_id: str, status: str | None = None, content: str | None = None, priority: str | None = None) -> TodoItem | None:
        for item in self._todos:
            if item.id == item_id:
                if status:
                    allowed = self.STATUS_TRANSITIONS.get(item.status, [])
                    if allowed and status not in allowed:
                        raise ValueError(f"Cannot transition from {item.status} to {status}")
                    item.status = status
                if content:
                    item.content = content
                if priority:
                    item.priority = priority
                return item
        return None

    def remove(self, item_id: str) -> bool:
        before = len(self._todos)
        self._todos = [t for t in self._todos if t.id != item_id]
        return len(self._todos) < before

    def list_all(self) -> list[TodoItem]:
        return list(self._todos)

    def get(self, item_id: str) -> TodoItem | None:
        for item in self._todos:
            if item.id == item_id:
                return item
        return None


def apply_patch(args: dict[str, Any], working_dir: Path) -> ToolResult:
    """Apply a patch: add, update, delete, or move a file."""
    from anvil.tools.executor import ToolResult

    action = args.get("action", "")
    path_str = args.get("path", "")
    path = working_dir / path_str if path_str else working_dir

    if not action:
        return ToolResult(success=False, output="", error="No action specified")

    if action == "add":
        content = args.get("content", "")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return ToolResult(success=True, output=f"Added file: {path}", file_path=str(path))

    elif action == "update":
        if not path.exists():
            return ToolResult(success=False, output="", error=f"File not found: {path}")
        old_content = path.read_text(encoding="utf-8", errors="replace")
        patch_content = args.get("patch", "")
        new_content = (old_content + "\n" + patch_content) if patch_content else args.get("content", old_content)
        import difflib
        diff = difflib.unified_diff(
            old_content.splitlines(keepends=True),
            new_content.splitlines(keepends=True),
            fromfile=f"a/{path.name}", tofile=f"b/{path.name}",
        )
        path.write_text(new_content, encoding="utf-8")
        return ToolResult(success=True, output=f"Updated: {path}", file_path=str(path), diff="".join(diff) if diff else None)

    elif action == "delete":
        if not path.exists():
            return ToolResult(success=False, output="", error=f"File not found: {path}")
        path.unlink()
        return ToolResult(success=True, output=f"Deleted: {path}")

    elif action == "move":
        dest_str = args.get("destination", "")
        dest = working_dir / dest_str if dest_str else path
        if not path.exists():
            return ToolResult(success=False, output="", error=f"Source not found: {path}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        content_to_move = path.read_text(encoding="utf-8", errors="replace")
        dest.write_text(content_to_move, encoding="utf-8")
        path.unlink()
        return ToolResult(success=True, output=f"Moved {path} -> {dest}", file_path=str(dest))

    else:
        return ToolResult(success=False, output="", error=f"Unknown patch action: {action}")


def todowrite(args: dict[str, Any], manager: TodoListManager | None = None) -> ToolResult:
    """Manage a todo list."""
    from anvil.tools.executor import ToolResult

    if manager is None:
        manager = TodoListManager()

    action = args.get("action", "")

    if action == "list":
        todos = manager.list_all()
        lines = [f"  [{t.status}] {t.id}: {t.content} (priority: {t.priority})" for t in todos]
        return ToolResult(success=True, output="Todos:\n" + "\n".join(lines) if lines else "No todos")

    elif action == "add":
        content = args.get("content", "")
        priority = args.get("priority", "medium")
        item = manager.add(content=content, priority=priority)
        return ToolResult(success=True, output=f"Added: {item.id} - {item.content} (priority: {item.priority})")

    elif action == "update":
        item_id = args.get("id", "")
        status = args.get("status")
        content = args.get("content")
        priority = args.get("priority")
        try:
            item = manager.update(item_id, status=status, content=content, priority=priority)
            if item:
                return ToolResult(success=True, output=f"Updated: {item.id} - status={item.status}")
            return ToolResult(success=False, output="", error=f"Todo {item_id} not found")
        except ValueError as e:
            return ToolResult(success=False, output="", error=str(e))

    elif action == "remove":
        item_id = args.get("id", "")
        removed = manager.remove(item_id)
        if removed:
            return ToolResult(success=True, output=f"Removed: {item_id}")
        return ToolResult(success=False, output="", error=f"Todo {item_id} not found")

    else:
        return ToolResult(success=False, output="", error=f"Unknown todowrite action: {action}")


def webfetch(args: dict[str, Any]) -> ToolResult:
    """Fetch content from a URL."""
    from anvil.tools.executor import ToolResult

    url = args.get("url", "")
    if not url:
        return ToolResult(success=False, output="", error="No URL provided")

    max_length = args.get("max_length", 50000)

    try:
        result = subprocess.run(
            ["curl", "-sL", "--max-time", "10", url],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode != 0:
            return ToolResult(success=False, output="", error=f"Fetch failed: {result.stderr[:500]}")
        content = result.stdout
        if len(content) > max_length:
            content = content[:max_length] + f"\n... [truncated at {max_length} chars]"
        return ToolResult(success=True, output=content)
    except subprocess.TimeoutExpired:
        return ToolResult(success=False, output="", error=f"Fetch timed out for {url}")
    except FileNotFoundError:
        return ToolResult(success=False, output="", error="curl not available")


def websearch(args: dict[str, Any]) -> ToolResult:
    """Search the web."""
    from anvil.tools.executor import ToolResult

    query = args.get("query", "")
    if not query:
        return ToolResult(success=False, output="", error="No query provided")

    return ToolResult(
        success=True,
        output=f"Search results for: {query}\n(Requires API key for live results)",
    )


def question(args: dict[str, Any]) -> ToolResult:
    """Ask the user a question."""
    from anvil.tools.executor import ToolResult

    question_text = args.get("question", "")
    options = args.get("options", [])

    if not question_text:
        return ToolResult(success=False, output="", error="No question provided")

    if options:
        formatted = "\n".join(f"  {i + 1}. {opt}" for i, opt in enumerate(options))
        return ToolResult(success=True, output=f"Question: {question_text}\nOptions:\n{formatted}")
    return ToolResult(success=True, output=f"Question: {question_text}")


def image(args: dict[str, Any], working_dir: Path = Path(".")) -> ToolResult:
    """Load and inspect an image file."""
    from anvil.tools.executor import ToolResult

    path_str = args.get("path", "")
    path = working_dir / path_str if path_str else Path("")

    if not path_str or not path.exists():
        return ToolResult(success=False, output="", error=f"Image not found: {path}")

    suffix = path.suffix.lower()
    valid_extensions = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".svg"}
    if suffix not in valid_extensions:
        return ToolResult(
            success=False, output="",
            error=f"Invalid image format: {suffix}. Supported: {', '.join(sorted(valid_extensions))}",
        )

    size = path.stat().st_size
    metadata = {
        "path": str(path),
        "format": suffix,
        "size_bytes": size,
        "size_human": f"{size / 1024:.1f}KB" if size < 1024 * 1024 else f"{size / (1024 * 1024):.1f}MB",
    }

    output_lines = [f"Image: {path.name}"]
    for key, val in metadata.items():
        output_lines.append(f"  {key}: {val}")

    return ToolResult(success=True, output="\n".join(output_lines), file_path=str(path))
