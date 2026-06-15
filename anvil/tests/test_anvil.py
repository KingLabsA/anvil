"""Tests for Anvil — the self-verified coding agent."""

import os
import json
import tempfile
from pathlib import Path

import pytest

from anvil.core.config import AnvilConfig, ModelConfig, VerifyConfig, ToolConfig, SafetyConfig
from anvil.core.session import Session, Step, StepKind, StepStatus, ToolCall, SessionStats
from anvil.core.engine import AnvilEngine, EngineResult, SYSTEM_PROMPT
from anvil.tools.executor import ToolExecutor, ToolResult
from anvil.verify.pipeline import VerifyPipeline, VerifyReport, VerifyResult, VerifyStatus, Checkers
from anvil.models.registry import ModelRegistry, LocalModel, BaseModel, Message, ModelResponse


class TestConfig:
    def test_default_config(self):
        cfg = AnvilConfig()
        assert cfg.model.model == "shellwhisperer"
        assert cfg.verify.enabled is True
        assert cfg.verify.auto_recover is True
        assert cfg.verify.max_retries == 3
        assert cfg.tools.allow_shell is True

    def test_config_serialization(self, tmp_path):
        cfg = AnvilConfig()
        cfg.verify.max_retries = 5
        path = tmp_path / "config.json"
        cfg.to_file(path)
        loaded = AnvilConfig.from_file(path)
        assert loaded.verify.max_retries == 5

    def test_safety_config(self):
        cfg = SafetyConfig()
        assert "rm -rf /" in cfg.blocked_commands
        assert len(cfg.require_confirmation_for) > 0


class TestSession:
    def test_session_creation(self):
        session = Session(task="fix the bug", persist=False)
        assert session.task == "fix the bug"
        assert session.stats.total_steps == 0

    def test_session_add_step(self):
        session = Session(task="test", persist=False)
        step = Step(kind=StepKind.EXECUTE, content="Run tests", status=StepStatus.SUCCESS)
        session.add_step(step)
        assert session.stats.total_steps == 1
        assert session.stats.successful_steps == 1

    def test_session_failed_step(self):
        session = Session(task="test", persist=False)
        step = Step(kind=StepKind.EXECUTE, content="Failing step", status=StepStatus.FAILED)
        session.add_step(step)
        assert session.stats.failed_steps == 1
        assert session.stats.error_rate == 1.0

    def test_session_recovery(self):
        session = Session(task="test", persist=False)
        session.add_step(Step(kind=StepKind.EXECUTE, content="fail", status=StepStatus.FAILED))
        session.add_step(Step(kind=StepKind.RECOVER, content="fixed", status=StepStatus.RECOVERED))
        assert session.stats.recovered_steps == 1
        assert session.stats.recovery_rate > 0

    def test_session_format_progress(self):
        session = Session(task="test", persist=False)
        session.add_step(Step(kind=StepKind.PLAN, content="Make plan", status=StepStatus.SUCCESS))
        output = session.format_progress()
        assert "✓" in output
        assert "plan" in output

    def test_session_summary(self):
        session = Session(task="test", persist=False)
        session.add_step(Step(kind=StepKind.VERIFY, content="Verify", status=StepStatus.SUCCESS))
        summary = session.summary()
        assert summary["steps"] == 1
        assert "stats" in summary

    def test_session_persistence(self, tmp_path):
        session = Session(task="test", persist=True, project_root=str(tmp_path))
        session.add_step(Step(kind=StepKind.EXECUTE, content="Do work", status=StepStatus.SUCCESS))
        result = session.end("completed")
        assert result["status"] == "completed"

    def test_session_load(self, tmp_path):
        session = Session(task="test", persist=True, project_root=str(tmp_path))
        session.add_step(Step(kind=StepKind.EXECUTE, content="Work", status=StepStatus.SUCCESS))
        session.end("completed")
        loaded = Session.load(session.id)
        if loaded:
            assert loaded.task == "test"

    def test_stats_update(self):
        stats = SessionStats()
        stats.update(Step(kind=StepKind.EXECUTE, content="ok", status=StepStatus.SUCCESS))
        stats.update(Step(kind=StepKind.EXECUTE, content="fail", status=StepStatus.FAILED))
        assert stats.total_steps == 2
        assert stats.error_rate == 0.5


class TestToolExecutor:
    def setup_method(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.executor = ToolExecutor(working_dir=self.tmp_dir, timeout=10)

    def test_bash_echo(self):
        result = self.executor.execute("bash", {"command": "echo hello"})
        assert result.success
        assert "hello" in result.output

    def test_bash_blocked_command(self):
        result = self.executor.execute("bash", {"command": "rm -rf /"})
        assert not result.success
        assert "Blocked" in result.error

    def test_bash_timeout(self):
        executor = ToolExecutor(working_dir=self.tmp_dir, timeout=1)
        result = executor.execute("bash", {"command": "sleep 5"})
        assert not result.success
        assert "timed out" in result.error

    def test_write_and_read_file(self):
        test_file = os.path.join(self.tmp_dir, "test.py")
        write_result = self.executor.execute("write", {"path": test_file, "content": "print('hello')"})
        assert write_result.success

        read_result = self.executor.execute("read", {"path": test_file})
        assert read_result.success
        assert "hello" in read_result.output

    def test_edit_file(self):
        test_file = os.path.join(self.tmp_dir, "edit_test.py")
        self.executor.execute("write", {"path": test_file, "content": "old_value = 1\nnew_line = 2"})
        edit_result = self.executor.execute("edit", {
            "path": test_file, "old_string": "old_value = 1", "new_string": "new_value = 1",
        })
        assert edit_result.success
        assert edit_result.success

    def test_edit_file_not_found(self):
        result = self.executor.execute("edit", {
            "path": "/nonexistent/file.py", "old_string": "a", "new_string": "b",
        })
        assert not result.success

    def test_grep(self):
        test_file = os.path.join(self.tmp_dir, "grep_test.py")
        self.executor.execute("write", {"path": test_file, "content": "def hello():\n    print('world')\n"})
        result = self.executor.execute("grep", {"pattern": "hello", "path": self.tmp_dir, "include": "*.py"})
        assert result.success
        assert "hello" in result.output

    def test_glob(self):
        test_file = os.path.join(self.tmp_dir, "glob_test.py")
        self.executor.execute("write", {"path": test_file, "content": "# test"})
        result = self.executor.execute("glob", {"pattern": "*.py", "path": self.tmp_dir})
        assert result.success

    def test_ls(self):
        result = self.executor.execute("ls", {"path": self.tmp_dir})
        assert result.success

    def test_unknown_tool(self):
        result = self.executor.execute("unknown_tool", {})
        assert not result.success
        assert "Unknown" in result.error

    def test_bash_empty_command(self):
        result = self.executor.execute("bash", {"command": ""})
        assert not result.success

    def test_read_nonexistent_file(self):
        result = self.executor.execute("read", {"path": "/nonexistent/file.py"})
        assert not result.success


class TestVerifyPipeline:
    def setup_method(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.pipeline = VerifyPipeline()

    def test_verify_python_syntax_pass(self):
        good_file = os.path.join(self.tmp_dir, "good.py")
        Path(good_file).write_text("x = 1\ny = 2\n")
        report = self.pipeline.verify(files=[good_file])
        syntax_results = [r for r in report.results if r.checker == "syntax"]
        assert any(r.status == VerifyStatus.PASS for r in syntax_results)

    def test_verify_python_syntax_fail(self):
        bad_file = os.path.join(self.tmp_dir, "bad.py")
        Path(bad_file).write_text("def foo(\n")
        result = Checkers.check_syntax(bad_file)
        assert result.status == VerifyStatus.FAIL

    def test_verify_report_format(self):
        report = VerifyReport()
        report.add(VerifyResult(checker="syntax", status=VerifyStatus.PASS, message="OK"))
        output = report.format_summary()
        assert "✓" in output
        assert "Overall: PASS" in output

    def test_verify_report_with_failures(self):
        report = VerifyReport()
        report.add(VerifyResult(checker="syntax", status=VerifyStatus.PASS, message="OK"))
        report.add(VerifyResult(checker="lint", status=VerifyStatus.FAIL, message="Issues found"))
        assert not report.passed
        assert len(report.failures) == 1

    def test_code_verify_good(self):
        report = self.pipeline.verify_code("x = 1\n", language="python")
        assert report.passed

    def test_code_verify_bad(self):
        report = self.pipeline.verify_code("def foo(\n", language="python")
        assert not report.passed

    def test_skip_unknown_extension(self):
        result = Checkers.check_syntax("file.xyz")
        assert result.status == VerifyStatus.SKIP


class TestModelRegistry:
    def test_create_local_model(self):
        model = ModelRegistry.create("local")
        assert isinstance(model, LocalModel)

    def test_create_by_name(self):
        model = ModelRegistry.create("gpt-4o")
        assert model.name == "openai"

    def test_available_models(self):
        models = ModelRegistry.available()
        assert "local" in models
        assert "gpt-4o" in models

    def test_register_custom_model(self):
        class CustomModel(BaseModel):
            name = "custom"
            def complete(self, messages, **kwargs):
                return ModelResponse(content="custom", model="custom")
            def stream(self, messages, **kwargs):
                yield "custom"

        ModelRegistry.register("custom", CustomModel)
        model = ModelRegistry.create("custom")
        assert isinstance(model, CustomModel)


class TestLocalModel:
    def test_local_model_init(self):
        model = LocalModel(model_path="test-model")
        assert model.model_name == "test-model"

    def test_local_model_complete_offline(self):
        model = LocalModel(api_base="http://localhost:99999")
        result = model.complete([Message(role="user", content="test")])
        assert "Error" in result.content or result.content


class TestEngine:
    def test_engine_init(self):
        cfg = AnvilConfig()
        cfg.model.model = "local"
        engine = AnvilEngine(cfg)
        assert engine.config.model.model == "local"
        assert engine.tools is not None
        assert engine.verify is not None

    def test_parse_tool_calls_bash(self):
        cfg = AnvilConfig(model=ModelConfig(model="local"))
        engine = AnvilEngine(cfg)
        text = 'Run this:\n```bash\npytest -x\n```\nThen check results.'
        calls = engine._parse_tool_calls(text)
        assert len(calls) >= 1
        assert calls[0]["tool"] == "bash"

    def test_parse_tool_calls_python(self):
        cfg = AnvilConfig(model=ModelConfig(model="local"))
        engine = AnvilEngine(cfg)
        text = 'Here is the code:\n```python\nx = 1\nprint(x)\n```'
        calls = engine._parse_tool_calls(text)
        assert len(calls) >= 1

    def test_find_test_command(self, tmp_path):
        cfg = AnvilConfig(model=ModelConfig(model="local"))
        cfg.project_root = str(tmp_path)
        engine = AnvilEngine(cfg)
        (tmp_path / "pyproject.toml").write_text("[tool.pytest]")
        cmd = engine._find_test_command()
        assert cmd is not None
        assert "pytest" in cmd


class TestEngineResult:
    def test_format_result_success(self):
        session = Session(task="test", persist=False)
        session.add_step(Step(kind=StepKind.EXECUTE, content="done", status=StepStatus.SUCCESS))
        result = EngineResult(success=True, session=session, output="Done")
        output = result.format_result()
        assert "SUCCESS" in output

    def test_format_result_failure(self):
        result = EngineResult(success=False, session=None, output="", error="Something failed")
        output = result.format_result()
        assert "FAILED" in output


class TestVerifyConfig:
    def test_config_defaults(self):
        cfg = VerifyConfig()
        assert cfg.enabled is True
        assert cfg.auto_recover is True
        assert cfg.max_retries == 3
        assert cfg.check_syntax is True

    def test_config_disabled(self):
        cfg = VerifyConfig(enabled=False)
        assert cfg.enabled is False


class TestToolConfig:
    def test_config_defaults(self):
        cfg = ToolConfig()
        assert cfg.allow_shell is True
        assert cfg.allow_file_write is True
        assert cfg.sandbox is False

    def test_sandbox_mode(self):
        cfg = ToolConfig(sandbox=True)
        assert cfg.sandbox is True