"""Regression tests for the verification correctness fixes.

Covers three real bugs found during live E2E testing:
1. check_imports used bare 'python' (missing on some systems) -> false ERROR.
2. The structured ```tool JSON protocol must parse reliably.
3. The engine must not claim "verified" when nothing was verified, and must
   gate success on real verification when files changed.
"""

import sys

from anvil.core.config import AnvilConfig, ModelConfig
from anvil.core.engine import AnvilEngine
from anvil.verify.pipeline import Checkers, VerifyPipeline, VerifyStatus


def _engine(tmp_path):
    cfg = AnvilConfig(model=ModelConfig(model="local"))
    cfg.project_root = str(tmp_path)
    cfg.tools.working_dir = str(tmp_path)
    return AnvilEngine(cfg)


class TestImportCheckerInterpreter:
    def test_imports_uses_current_interpreter(self, tmp_path):
        f = tmp_path / "ok.py"
        f.write_text("def add(a, b):\n    return a + b\n")
        result = Checkers.check_imports(str(f))
        # Must not ERROR due to a missing 'python' binary.
        assert result.status != VerifyStatus.ERROR
        assert result.status == VerifyStatus.PASS

    def test_valid_file_verify_passes(self, tmp_path):
        f = tmp_path / "ok.py"
        f.write_text("x = 1\n")
        report = VerifyPipeline().verify([str(f)])
        assert report.passed is True
        assert report.overall == VerifyStatus.PASS


class TestStructuredToolProtocol:
    def test_parses_tool_fence(self, tmp_path):
        eng = _engine(tmp_path)
        text = (
            "Here is the edit:\n"
            '```tool\n{"tool": "edit", "args": {"path": "a.py", '
            '"old_string": "x", "new_string": "y"}}\n```'
        )
        calls = eng._parse_tool_calls(text)
        assert len(calls) == 1
        assert calls[0]["tool"] == "edit"
        assert calls[0]["args"]["path"] == "a.py"

    def test_parses_multiple_and_arrays(self, tmp_path):
        eng = _engine(tmp_path)
        text = (
            '```tool\n[{"tool": "read", "args": {"path": "a.py"}}, '
            '{"tool": "bash", "args": {"command": "ls"}}]\n```'
        )
        calls = eng._parse_tool_calls(text)
        assert [c["tool"] for c in calls] == ["read", "bash"]

    def test_ignores_unknown_tool(self, tmp_path):
        eng = _engine(tmp_path)
        text = '```tool\n{"tool": "definitely_not_a_tool", "args": {}}\n```'
        # Falls back to legacy parser, which yields nothing meaningful here.
        calls = eng._parse_structured_tool_calls(text)
        assert calls == []

    def test_structured_takes_priority_over_legacy(self, tmp_path):
        eng = _engine(tmp_path)
        text = '```tool\n{"tool": "bash", "args": {"command": "echo hi"}}\n```'
        calls = eng._parse_tool_calls(text)
        assert calls == [{"tool": "bash", "args": {"command": "echo hi"}}]


class TestFileContext:
    def test_gathers_referenced_file(self, tmp_path):
        f = tmp_path / "mod.py"
        f.write_text("VALUE = 42\n")
        eng = _engine(tmp_path)
        ctx = eng._gather_file_context("please update mod.py", [])
        assert "mod.py" in ctx
        assert "VALUE = 42" in ctx

    def test_empty_when_no_files(self, tmp_path):
        eng = _engine(tmp_path)
        assert eng._gather_file_context("do something abstract", []) == ""


class TestNoFalseVerified:
    def test_no_changes_is_honest(self, tmp_path, monkeypatch):
        """When the agent makes no file changes, output must not claim verified."""
        eng = _engine(tmp_path)

        # Force the plan/execute to do nothing (no tool calls, no changes).
        monkeypatch.setattr(eng, "_plan", lambda task, session: ["do nothing"])
        monkeypatch.setattr(
            eng, "_execute",
            lambda step, fc, vr, session: {"success": True, "tool_calls": [], "files_changed": []},
        )
        result = eng.run("a task that changes nothing", max_iterations=1)
        # Must not falsely claim the work was verified.
        assert "completed and verified" not in result.output.lower()
        assert "no file changes" in result.output.lower()
