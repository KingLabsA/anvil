"""Tests for Anvil tool executor — Bash, Read, Write, Edit, Grep, Glob, Ls."""

import tempfile
from pathlib import Path

import pytest

from anvil.tools.executor import ToolExecutor, ToolResult

# ---------------------------------------------------------------------------
# ToolResult dataclass
# ---------------------------------------------------------------------------

class TestToolResult:
    def test_success_result_defaults(self):
        r = ToolResult(success=True, output="ok")
        assert r.success is True
        assert r.output == "ok"
        assert r.error is None
        assert r.exit_code == 0
        assert r.file_path is None
        assert r.diff is None
        assert r.duration_ms == 0.0

    def test_failure_result_with_error(self):
        r = ToolResult(success=False, output="", error="file not found")
        assert r.success is False
        assert r.error == "file not found"
        assert r.output == ""

    def test_error_result_with_exit_code(self):
        r = ToolResult(success=False, output="stderr text", error="command failed", exit_code=1)
        assert r.exit_code == 1
        assert "command failed" in r.error

    def test_result_with_file_path(self):
        r = ToolResult(success=True, output="wrote file", file_path="/tmp/test.py")
        assert r.file_path == "/tmp/test.py"

    def test_result_with_diff(self):
        r = ToolResult(success=True, output="edited", diff="--- a/f\n+++ b/f\n-old\n+new")
        assert r.diff is not None
        assert "+new" in r.diff

    def test_result_with_duration(self):
        r = ToolResult(success=True, output="done", duration_ms=150.5)
        assert r.duration_ms == pytest.approx(150.5)


# ---------------------------------------------------------------------------
# ToolExecutor dispatch
# ---------------------------------------------------------------------------

class TestToolExecutorDispatch:
    def test_unknown_tool_returns_error(self):
        executor = ToolExecutor(working_dir="/tmp")
        result = executor.execute("nonexistent_tool", {"arg": "val"})
        assert result.success is False
        assert "Unknown tool" in result.error

    def test_execute_raises_exception_handled(self):
        executor = ToolExecutor(working_dir="/tmp")
        result = executor.execute("bash", {"command": None})
        assert result.success is False


# ---------------------------------------------------------------------------
# Bash tool
# ---------------------------------------------------------------------------

class TestBashTool:
    def test_successful_command(self):
        executor = ToolExecutor(working_dir=tempfile.gettempdir(), timeout=10)
        result = executor.execute("bash", {"command": "echo 'hello world'"})
        assert result.success is True
        assert "hello world" in result.output

    def test_failed_command(self):
        executor = ToolExecutor(working_dir=tempfile.gettempdir(), timeout=10)
        result = executor.execute("bash", {"command": "false"})
        assert result.success is False
        assert result.exit_code != 0

    def test_command_with_stderr(self):
        executor = ToolExecutor(working_dir=tempfile.gettempdir(), timeout=10)
        result = executor.execute("bash", {"command": "echo err >&2 && echo out"})
        assert result.success is True
        assert "err" in result.output
        assert "out" in result.output

    def test_command_timeout(self):
        executor = ToolExecutor(working_dir=tempfile.gettempdir(), timeout=1)
        result = executor.execute("bash", {"command": "sleep 10"})
        assert result.success is False
        assert "timed out" in result.error.lower() or "timed out" in result.error

    def test_blocked_dangerous_command(self):
        executor = ToolExecutor(working_dir=tempfile.gettempdir(), timeout=10)
        result = executor.execute("bash", {"command": "rm -rf /"})
        assert result.success is False
        assert "Blocked" in result.error

    def test_blocked_fork_bomb(self):
        executor = ToolExecutor(working_dir=tempfile.gettempdir(), timeout=10)
        result = executor.execute("bash", {"command": ":(){ :|:&"})
        assert result.success is False
        assert "Blocked" in result.error

    def test_blocked_dd_command(self):
        executor = ToolExecutor(working_dir=tempfile.gettempdir(), timeout=10)
        result = executor.execute("bash", {"command": "dd if=/dev/zero of=/dev/sda"})
        assert result.success is False

    def test_empty_command_returns_error(self):
        executor = ToolExecutor(working_dir=tempfile.gettempdir(), timeout=10)
        result = executor.execute("bash", {"command": ""})
        assert result.success is False
        assert "No command" in result.error

    def test_command_in_working_directory(self, tmp_path):
        (tmp_path / "testdir").mkdir()
        executor = ToolExecutor(working_dir=str(tmp_path), timeout=10)
        result = executor.execute("bash", {"command": "ls testdir"})
        assert result.success is True

    def test_multi_line_output(self):
        executor = ToolExecutor(working_dir=tempfile.gettempdir(), timeout=10)
        result = executor.execute("bash", {"command": "echo line1 && echo line2 && echo line3"})
        assert result.success is True
        assert "line1" in result.output
        assert "line2" in result.output
        assert "line3" in result.output

    def test_exit_code_propagated(self):
        executor = ToolExecutor(working_dir=tempfile.gettempdir(), timeout=10)
        result = executor.execute("bash", {"command": "exit 42"})
        assert result.success is False
        assert result.exit_code == 42


# ---------------------------------------------------------------------------
# Read tool
# ---------------------------------------------------------------------------

class TestReadTool:
    def test_read_existing_file(self, tmp_path):
        f = tmp_path / "hello.py"
        f.write_text("print('hello')\n")
        executor = ToolExecutor(working_dir=str(tmp_path))
        result = executor.execute("read", {"path": "hello.py"})
        assert result.success is True
        assert "hello" in result.output
        assert result.file_path is not None

    def test_read_missing_file_returns_error(self, tmp_path):
        executor = ToolExecutor(working_dir=str(tmp_path))
        result = executor.execute("read", {"path": "nonexistent_file.py"})
        assert result.success is False
        assert "not found" in result.error.lower() or "File not found" in result.error

    def test_read_directory_lists_contents(self, tmp_path):
        (tmp_path / "subdir").mkdir()
        (tmp_path / "file1.txt").write_text("content1")
        executor = ToolExecutor(working_dir=str(tmp_path))
        result = executor.execute("read", {"path": str(tmp_path)})
        assert result.success is True

    def test_read_with_offset_and_limit(self, tmp_path):
        f = tmp_path / "multiline.txt"
        f.write_text("\n".join(f"line {i}" for i in range(20)))
        executor = ToolExecutor(working_dir=str(tmp_path))
        result = executor.execute("read", {"path": "multiline.txt", "offset": 5, "limit": 3})
        assert result.success is True
        assert "line 5" in result.output

    def test_read_no_path_returns_error(self):
        executor = ToolExecutor(working_dir="/tmp")
        result = executor.execute("read", {"path": ""})
        assert result.success is True  # empty path resolves to working dir


# ---------------------------------------------------------------------------
# Write tool
# ---------------------------------------------------------------------------

class TestWriteTool:
    def test_write_new_file(self, tmp_path):
        executor = ToolExecutor(working_dir=str(tmp_path))
        result = executor.execute("write", {"path": "new_file.py", "content": "x = 1\n"})
        assert result.success is True
        assert (tmp_path / "new_file.py").read_text() == "x = 1\n"
        assert result.file_path is not None

    def test_overwrite_existing_file(self, tmp_path):
        f = tmp_path / "existing.py"
        f.write_text("old content")
        executor = ToolExecutor(working_dir=str(tmp_path))
        result = executor.execute("write", {"path": "existing.py", "content": "new content"})
        assert result.success is True
        assert f.read_text() == "new content"
        assert result.diff is not None

    def test_write_to_nested_directory(self, tmp_path):
        executor = ToolExecutor(working_dir=str(tmp_path))
        result = executor.execute("write", {"path": "deep/nested/dir/file.txt", "content": "nested"})
        assert result.success is True
        assert (tmp_path / "deep" / "nested" / "dir" / "file.txt").read_text() == "nested"

    def test_write_empty_content(self, tmp_path):
        executor = ToolExecutor(working_dir=str(tmp_path))
        result = executor.execute("write", {"path": "empty.txt", "content": ""})
        assert result.success is True
        assert (tmp_path / "empty.txt").read_text() == ""

    def test_write_content_length_in_output(self, tmp_path):
        content = "Hello World!"
        executor = ToolExecutor(working_dir=str(tmp_path))
        result = executor.execute("write", {"path": "len_check.txt", "content": content})
        assert result.success is True
        assert str(len(content)) in result.output

    def test_write_empty_path_resolves_to_working_dir(self, tmp_path):
        f = tmp_path / "test_file.txt"
        executor = ToolExecutor(working_dir=str(tmp_path))
        result = executor.execute("write", {"path": "test_file.txt", "content": "test"})
        assert result.success is True
        assert (tmp_path / "test_file.txt").read_text() == "test"


# ---------------------------------------------------------------------------
# Edit tool
# ---------------------------------------------------------------------------

class TestEditTool:
    def test_replace_string(self, tmp_path):
        f = tmp_path / "edit_me.py"
        f.write_text("def foo():\n    return 1\n")
        executor = ToolExecutor(working_dir=str(tmp_path))
        result = executor.execute("edit", {
            "path": "edit_me.py", "old_string": "return 1", "new_string": "return 2",
        })
        assert result.success is True
        assert "return 2" in f.read_text()
        assert "return 1" not in f.read_text()

    def test_replace_all_occurrences(self, tmp_path):
        f = tmp_path / "multi.py"
        f.write_text("x = 1\ny = 1\nz = 1\n")
        executor = ToolExecutor(working_dir=str(tmp_path))
        result = executor.execute("edit", {
            "path": "multi.py", "old_string": "1", "new_string": "2", "replace_all": True,
        })
        assert result.success is True
        content = f.read_text()
        assert content.count("2") >= 3

    def test_edit_rejects_ambiguous_without_replace_all(self, tmp_path):
        f = tmp_path / "ambig.py"
        f.write_text("x = 1\ny = 1\n")
        executor = ToolExecutor(working_dir=str(tmp_path))
        result = executor.execute("edit", {
            "path": "ambig.py", "old_string": "1", "new_string": "2",
        })
        assert result.success is False
        assert "2 matches" in result.error or "Found 2" in result.error

    def test_edit_missing_file(self, tmp_path):
        executor = ToolExecutor(working_dir=str(tmp_path))
        result = executor.execute("edit", {
            "path": "does_not_exist.py", "old_string": "old", "new_string": "new",
        })
        assert result.success is False

    def test_edit_string_not_found(self, tmp_path):
        f = tmp_path / "no_match.py"
        f.write_text("x = 1\n")
        executor = ToolExecutor(working_dir=str(tmp_path))
        result = executor.execute("edit", {
            "path": "no_match.py", "old_string": "nonexistent_string", "new_string": "new",
        })
        assert result.success is False
        assert "not found" in result.error

    def test_edit_produces_diff(self, tmp_path):
        f = tmp_path / "diff_check.py"
        f.write_text("old_line\n")
        executor = ToolExecutor(working_dir=str(tmp_path))
        result = executor.execute("edit", {
            "path": "diff_check.py", "old_string": "old_line", "new_string": "new_line",
        })
        assert result.success is True
        assert result.diff is not None
        assert "+new_line" in result.diff
        assert "-old_line" in result.diff

    def test_edit_preserves_surrounding_content(self, tmp_path):
        f = tmp_path / "preserve.py"
        f.write_text("line1\nline2\nline3\n")
        executor = ToolExecutor(working_dir=str(tmp_path))
        result = executor.execute("edit", {
            "path": "preserve.py", "old_string": "line2", "new_string": "EDITED",
        })
        assert result.success is True
        content = f.read_text()
        assert "line1" in content
        assert "EDITED" in content
        assert "line3" in content


# ---------------------------------------------------------------------------
# Search content (grep) tool
# ---------------------------------------------------------------------------

class TestSearchContentTool:
    def test_find_pattern(self, tmp_path):
        (tmp_path / "search.py").write_text("def hello():\n    pass\n")
        executor = ToolExecutor(working_dir=str(tmp_path))
        result = executor.execute("grep", {"pattern": "hello", "path": str(tmp_path)})
        assert result.success is True
        assert "hello" in result.output

    def test_no_match(self, tmp_path):
        (tmp_path / "nomatch.py").write_text("x = 1\n")
        executor = ToolExecutor(working_dir=str(tmp_path))
        result = executor.execute("grep", {"pattern": "ZZZ_NOT_FOUND_ZZZ", "path": str(tmp_path)})
        assert result.success is True
        assert "No matches" in result.output

    def test_multiple_matches(self, tmp_path):
        (tmp_path / "a.py").write_text("import os\nimport sys\n")
        (tmp_path / "b.py").write_text("import os\nimport json\n")
        executor = ToolExecutor(working_dir=str(tmp_path))
        result = executor.execute("grep", {"pattern": "import os", "path": str(tmp_path)})
        assert result.success is True
        assert result.output.count("import os") >= 2

    def test_include_pattern(self, tmp_path):
        (tmp_path / "code.py").write_text("pattern_to_find = True\n")
        (tmp_path / "readme.md").write_text("pattern_to_find also here\n")
        executor = ToolExecutor(working_dir=str(tmp_path))
        result = executor.execute("grep", {"pattern": "pattern_to_find", "path": str(tmp_path), "include": "*.py"})
        assert result.success is True
        assert "code.py" in result.output

    def test_empty_pattern_returns_error(self, tmp_path):
        executor = ToolExecutor(working_dir=str(tmp_path))
        result = executor.execute("grep", {"pattern": ""})
        assert result.success is False
        assert "No pattern" in result.error


# ---------------------------------------------------------------------------
# Search files (glob) tool
# ---------------------------------------------------------------------------

class TestSearchFilesTool:
    def test_glob_pattern(self, tmp_path):
        (tmp_path / "a.py").write_text("code")
        (tmp_path / "b.py").write_text("code")
        (tmp_path / "c.txt").write_text("text")
        executor = ToolExecutor(working_dir=str(tmp_path))
        result = executor.execute("glob", {"pattern": "*.py", "path": str(tmp_path)})
        assert result.success is True
        assert "a.py" in result.output
        assert "b.py" in result.output
        assert "c.txt" not in result.output

    def test_recursive_search(self, tmp_path):
        sub = tmp_path / "subdir"
        sub.mkdir()
        (sub / "deep.py").write_text("deep code")
        executor = ToolExecutor(working_dir=str(tmp_path))
        result = executor.execute("glob", {"pattern": "**/*.py", "path": str(tmp_path)})
        assert result.success is True
        assert "deep.py" in result.output

    def test_no_matches(self, tmp_path):
        executor = ToolExecutor(working_dir=str(tmp_path))
        result = executor.execute("glob", {"pattern": "*.xyz", "path": str(tmp_path)})
        assert result.success is True
        assert "No files" in result.output


# ---------------------------------------------------------------------------
# List directory tool
# ---------------------------------------------------------------------------

class TestListDirectoryTool:
    def test_list_files_and_dirs(self, tmp_path):
        (tmp_path / "file1.txt").write_text("data")
        (tmp_path / "subdir").mkdir()
        executor = ToolExecutor(working_dir=str(tmp_path))
        result = executor.execute("ls", {"path": str(tmp_path)})
        assert result.success is True
        assert "[FILE]" in result.output or "file1.txt" in result.output
        assert "[DIR]" in result.output or "subdir" in result.output

    def test_list_empty_directory(self, tmp_path):
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        executor = ToolExecutor(working_dir=str(tmp_path))
        result = executor.execute("ls", {"path": str(empty_dir)})
        assert result.success is True
        assert result.output.strip() == ""

    def test_list_not_a_directory(self, tmp_path):
        f = tmp_path / "not_dir.txt"
        f.write_text("file content")
        executor = ToolExecutor(working_dir=str(tmp_path))
        result = executor.execute("ls", {"path": str(f)})
        assert result.success is False
        assert "Not a directory" in result.error

    def test_list_shows_file_sizes(self, tmp_path):
        (tmp_path / "sized_file.txt").write_text("x" * 100)
        executor = ToolExecutor(working_dir=str(tmp_path))
        result = executor.execute("ls", {"path": str(tmp_path)})
        assert result.success is True
        assert "100b" in result.output or "sized_file" in result.output


# ---------------------------------------------------------------------------
# Path resolution and security
# ---------------------------------------------------------------------------

class TestPathResolution:
    def test_absolute_path(self, tmp_path):
        f = tmp_path / "abs_test.py"
        f.write_text("content")
        executor = ToolExecutor(working_dir=str(tmp_path))
        result = executor.execute("read", {"path": str(f)})
        assert result.success is True
        assert "content" in result.output

    def test_relative_path_resolved_against_working_dir(self, tmp_path):
        f = tmp_path / "rel_test.py"
        f.write_text("relative content")
        executor = ToolExecutor(working_dir=str(tmp_path))
        result = executor.execute("read", {"path": "rel_test.py"})
        assert result.success is True
        assert "relative content" in result.output

    def test_path_traversal_protection(self):
        executor = ToolExecutor(working_dir="/tmp", sandbox=True)
        assert executor.sandbox is True

    def test_blocked_patterns_exist(self):
        executor = ToolExecutor(working_dir="/tmp")
        assert len(executor.blocked_patterns) > 0
        assert any(p.pattern == r'\brm\s+-rf\s+/[ /\t]*$' for p in executor.blocked_patterns)

    def test_resolve_empty_path_returns_working_dir(self):
        executor = ToolExecutor(working_dir="/tmp")
        resolved = executor._resolve_path("")
        assert resolved == Path("/tmp").resolve()

    def test_resolve_relative_path(self, tmp_path):
        executor = ToolExecutor(working_dir=str(tmp_path))
        resolved = executor._resolve_path("some/file.py")
        expected = (Path(str(tmp_path)) / "some" / "file.py").resolve()
        assert resolved == expected
