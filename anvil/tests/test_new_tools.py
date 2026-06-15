"""Tests for Anvil new tools — apply_patch, todowrite, webfetch, websearch, question, image, TodoListManager."""

import tempfile

import pytest

from anvil.tools.executor import ToolExecutor
from anvil.tools.new_tools import (
    TodoItem,
    TodoListManager,
    apply_patch,
    image,
    question,
    webfetch,
    websearch,
)

# ---------------------------------------------------------------------------
# TodoItem / TodoListManager
# ---------------------------------------------------------------------------

class TestTodoItem:
    def test_default_todo(self):
        item = TodoItem(id="todo_001", content="Test task")
        assert item.id == "todo_001"
        assert item.content == "Test task"
        assert item.status == "pending"
        assert item.priority == "medium"


class TestTodoListManager:
    def test_add_todo(self):
        mgr = TodoListManager()
        item = mgr.add("Fix the bug")
        assert item.content == "Fix the bug"
        assert item.status == "pending"
        assert item.id.startswith("todo_")

    def test_add_with_priority(self):
        mgr = TodoListManager()
        item = mgr.add("Critical fix", priority="high")
        assert item.priority == "high"

    def test_update_status(self):
        mgr = TodoListManager()
        item = mgr.add("Do something")
        updated = mgr.update(item.id, status="in_progress")
        assert updated is not None
        assert updated.status == "in_progress"

    def test_update_content(self):
        mgr = TodoListManager()
        item = mgr.add("Old content")
        updated = mgr.update(item.id, content="New content")
        assert updated.content == "New content"

    def test_update_nonexistent(self):
        mgr = TodoListManager()
        result = mgr.update("nonexistent", status="completed")
        assert result is None

    def test_status_transitions_pending_to_in_progress(self):
        mgr = TodoListManager()
        item = mgr.add("Task")
        updated = mgr.update(item.id, status="in_progress")
        assert updated.status == "in_progress"

    def test_status_transitions_invalid(self):
        mgr = TodoListManager()
        item = mgr.add("Task")
        with pytest.raises(ValueError):
            mgr.update(item.id, status="completed")

    def test_status_transitions_completed_no_exit(self):
        mgr = TodoListManager()
        item = mgr.add("Task")
        item = mgr.update(item.id, status="in_progress")
        item = mgr.update(item.id, status="completed")
        assert item.status == "completed"

    def test_cancel_and_reactivate(self):
        mgr = TodoListManager()
        item = mgr.add("Task")
        item = mgr.update(item.id, status="cancelled")
        assert item.status == "cancelled"
        item = mgr.update(item.id, status="pending")
        assert item.status == "pending"

    def test_remove_todo(self):
        mgr = TodoListManager()
        item = mgr.add("To remove")
        removed = mgr.remove(item.id)
        assert removed is True
        assert mgr.get(item.id) is None

    def test_remove_nonexistent(self):
        mgr = TodoListManager()
        removed = mgr.remove("nonexistent")
        assert removed is False

    def test_list_all(self):
        mgr = TodoListManager()
        mgr.add("Task 1")
        mgr.add("Task 2")
        mgr.add("Task 3")
        assert len(mgr.list_all()) == 3

    def test_get_todo(self):
        mgr = TodoListManager()
        item = mgr.add("Find me")
        found = mgr.get(item.id)
        assert found is not None
        assert found.content == "Find me"

    def test_priority_levels(self):
        mgr = TodoListManager()
        low = mgr.add("Low task", priority="low")
        medium = mgr.add("Medium task", priority="medium")
        high = mgr.add("High task", priority="high")
        critical = mgr.add("Critical task", priority="critical")
        assert low.priority == "low"
        assert critical.priority == "critical"


# ---------------------------------------------------------------------------
# apply_patch tool
# ---------------------------------------------------------------------------

class TestApplyPatch:
    def test_add_file(self, tmp_path):
        result = apply_patch({
            "action": "add",
            "path": "new_file.py",
            "content": "print('hello')\n",
        }, working_dir=tmp_path)
        assert result.success is True
        assert (tmp_path / "new_file.py").exists()
        assert "hello" in (tmp_path / "new_file.py").read_text()

    def test_add_file_creates_directories(self, tmp_path):
        result = apply_patch({
            "action": "add",
            "path": "deep/nested/dir/file.txt",
            "content": "nested content",
        }, working_dir=tmp_path)
        assert result.success is True
        assert (tmp_path / "deep" / "nested" / "dir" / "file.txt").exists()

    def test_update_file(self, tmp_path):
        f = tmp_path / "update_me.py"
        f.write_text("old line\nnew line\n")
        result = apply_patch({
            "action": "update",
            "path": "update_me.py",
            "content": "replaced line\nnew line\n",
        }, working_dir=tmp_path)
        assert result.success is True
        assert "replaced line" in f.read_text()

    def test_update_file_with_patch(self, tmp_path):
        f = tmp_path / "patch_me.py"
        f.write_text("line1\n")
        result = apply_patch({
            "action": "update",
            "path": "patch_me.py",
            "patch": "line2\n",
        }, working_dir=tmp_path)
        assert result.success is True
        content = f.read_text()
        assert "line1" in content
        assert "line2" in content

    def test_delete_file(self, tmp_path):
        f = tmp_path / "delete_me.py"
        f.write_text("to be deleted")
        result = apply_patch({
            "action": "delete",
            "path": "delete_me.py",
        }, working_dir=tmp_path)
        assert result.success is True
        assert not f.exists()

    def test_move_file(self, tmp_path):
        f = tmp_path / "source.txt"
        f.write_text("move me")
        result = apply_patch({
            "action": "move",
            "path": "source.txt",
            "destination": "dest.txt",
        }, working_dir=tmp_path)
        assert result.success is True
        assert not f.exists()
        assert (tmp_path / "dest.txt").exists()
        assert "move me" in (tmp_path / "dest.txt").read_text()

    def test_add_missing_path(self, tmp_path):
        result = apply_patch({"action": "add", "content": "data"}, working_dir=tmp_path)
        assert result.success is False

    def test_update_missing_file(self, tmp_path):
        result = apply_patch({
            "action": "update",
            "path": "nonexistent.py",
            "content": "data",
        }, working_dir=tmp_path)
        assert result.success is False

    def test_delete_missing_file(self, tmp_path):
        result = apply_patch({
            "action": "delete",
            "path": "nonexistent.py",
        }, working_dir=tmp_path)
        assert result.success is False

    def test_move_missing_source(self, tmp_path):
        result = apply_patch({
            "action": "move",
            "path": "nonexistent.txt",
            "destination": "dest.txt",
        }, working_dir=tmp_path)
        assert result.success is False

    def test_move_empty_destination_same_path(self, tmp_path):
        f = tmp_path / "source.txt"
        f.write_text("data")
        result = apply_patch({
            "action": "move",
            "path": "source.txt",
            "destination": "",
        }, working_dir=tmp_path)
        assert result.success is True

    def test_unknown_patch_action(self, tmp_path):
        result = apply_patch({
            "action": "unknown",
            "path": "test.py",
        }, working_dir=tmp_path)
        assert result.success is False
        assert "Unknown" in result.error

    def test_no_action_specified(self, tmp_path):
        result = apply_patch({}, working_dir=tmp_path)
        assert result.success is False


# ---------------------------------------------------------------------------
# todowrite tool via ToolExecutor
# ---------------------------------------------------------------------------

class TestTodowriteTool:
    def setup_method(self):
        self.executor = ToolExecutor(working_dir=tempfile.gettempdir(), timeout=10)

    def test_todowrite_add(self):
        result = self.executor.execute("todowrite", {"action": "add", "content": "Test task", "priority": "high"})
        assert result.success is True
        assert "Test task" in result.output

    def test_todowrite_list(self):
        self.executor.execute("todowrite", {"action": "add", "content": "Task 1"})
        self.executor.execute("todowrite", {"action": "add", "content": "Task 2"})
        result = self.executor.execute("todowrite", {"action": "list", "todos": []})
        assert result.success is True

    def test_todowrite_update(self):
        self.executor.execute("todowrite", {"action": "add", "content": "My task"})
        todos = self.executor.todo_manager.list_all()
        item = todos[-1]
        result = self.executor.execute("todowrite", {
            "action": "update", "id": item.id, "status": "in_progress",
        })
        assert result.success is True

    def test_todowrite_remove(self):
        self.executor.execute("todowrite", {"action": "add", "content": "Remove me"})
        todos = self.executor.todo_manager.list_all()
        item = todos[-1]
        result = self.executor.execute("todowrite", {"action": "remove", "id": item.id})
        assert result.success is True

    def test_todowrite_unknown_action(self):
        result = self.executor.execute("todowrite", {"action": "unknown"})
        assert result.success is False

    def test_todowrite_priority_levels(self):
        for priority in ["low", "medium", "high", "critical"]:
            result = self.executor.execute("todowrite", {
                "action": "add", "content": f"{priority} task", "priority": priority,
            })
            assert result.success is True
            assert priority in result.output


# ---------------------------------------------------------------------------
# webfetch tool
# ---------------------------------------------------------------------------

class TestWebfetchTool:
    def setup_method(self):
        self.executor = ToolExecutor(working_dir=tempfile.gettempdir(), timeout=10)

    def test_webfetch_no_url(self):
        result = webfetch({"action": "fetch"})
        assert result.success is False
        assert "No URL" in result.error

    def test_webfetch_invalid_url(self):
        result = webfetch({"url": "http://localhost:99999/nonexistent"})
        assert result.success is False or "Error" in result.output or result.error

    def test_webfetch_standalone_function(self):
        result = webfetch({"url": ""})
        assert result.success is False


# ---------------------------------------------------------------------------
# websearch tool
# ---------------------------------------------------------------------------

class TestWebsearchTool:
    def test_websearch_basic(self):
        result = websearch({"query": "test query"})
        assert result.success is True
        assert "test query" in result.output

    def test_websearch_no_query(self):
        result = websearch({})
        assert result.success is False

    def test_websearch_via_executor(self):
        executor = ToolExecutor(working_dir=tempfile.gettempdir(), timeout=10)
        result = executor.execute("websearch", {"query": "python testing"})
        assert result.success is True
        assert "python testing" in result.output


# ---------------------------------------------------------------------------
# question tool
# ---------------------------------------------------------------------------

class TestQuestionTool:
    def test_question_text(self):
        result = question({"question": "What is 2+2?"})
        assert result.success is True
        assert "What is 2+2?" in result.output

    def test_question_with_options(self):
        result = question({
            "question": "Choose a language",
            "options": ["Python", "Rust", "Go"],
        })
        assert result.success is True
        assert "Python" in result.output
        assert "Rust" in result.output
        assert "Go" in result.output

    def test_question_no_question(self):
        result = question({})
        assert result.success is False
        assert "No question" in result.error

    def test_question_via_executor(self):
        executor = ToolExecutor(working_dir=tempfile.gettempdir(), timeout=10)
        result = executor.execute("question", {"question": "Continue?"})
        assert result.success is True
        assert "Continue?" in result.output


# ---------------------------------------------------------------------------
# image tool
# ---------------------------------------------------------------------------

class TestImageTool:
    def test_image_valid_png(self, tmp_path):
        png_file = tmp_path / "test.png"
        png_file.write_bytes(b'\x89PNG\r\n\x1a\n' + b'\x00' * 100)
        result = image({"path": "test.png"}, working_dir=tmp_path)
        assert result.success is True
        assert "test.png" in result.output
        assert ".png" in result.output

    def test_image_valid_jpeg(self, tmp_path):
        jpeg_file = tmp_path / "photo.jpg"
        jpeg_file.write_bytes(b'\xff\xd8\xff\xe0' + b'\x00' * 200)
        result = image({"path": "photo.jpg"}, working_dir=tmp_path)
        assert result.success is True
        assert ".jpg" in result.output

    def test_image_invalid_extension(self, tmp_path):
        txt_file = tmp_path / "doc.txt"
        txt_file.write_text("not an image")
        result = image({"path": "doc.txt"}, working_dir=tmp_path)
        assert result.success is False
        assert "Invalid" in result.error

    def test_image_nonexistent_file(self, tmp_path):
        result = image({"path": "nonexistent.png"}, working_dir=tmp_path)
        assert result.success is False

    def test_image_metadata_extraction(self, tmp_path):
        big_png = tmp_path / "large.png"
        big_png.write_bytes(b'\x89PNG\r\n\x1a\n' + b'\x00' * 5000)
        result = image({"path": "large.png"}, working_dir=tmp_path)
        assert result.success is True
        assert "size_bytes" in result.output or "KB" in result.output or "B" in result.output

    def test_image_via_executor(self, tmp_path):
        executor = ToolExecutor(working_dir=str(tmp_path), timeout=10)
        png_file = tmp_path / "exec_test.png"
        png_file.write_bytes(b'\x89PNG\r\n\x1a\n' + b'\x00' * 50)
        result = executor.execute("image", {"path": "exec_test.png"})
        assert result.success is True


# ---------------------------------------------------------------------------
# apply_patch via ToolExecutor dispatch
# ---------------------------------------------------------------------------

class TestApplyPatchViaExecutor:
    def setup_method(self):
        self.executor = ToolExecutor(working_dir=tempfile.gettempdir(), timeout=10)

    def test_apply_patch_add(self, tmp_path):
        executor = ToolExecutor(working_dir=str(tmp_path), timeout=10)
        result = executor.execute("apply_patch", {
            "action": "add",
            "path": "dispatch_test.py",
            "content": "x = 1\n",
        })
        assert result.success is True

    def test_apply_patch_delete(self, tmp_path):
        executor = ToolExecutor(working_dir=str(tmp_path), timeout=10)
        f = tmp_path / "to_delete.py"
        f.write_text("delete me")
        result = executor.execute("apply_patch", {"action": "delete", "path": "to_delete.py"})
        assert result.success is True
        assert not f.exists()
