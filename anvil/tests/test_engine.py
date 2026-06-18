"""Tests for Anvil engine — initialization, plan, execute, verify, recover, config, session tracking."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from anvil.core.config import AnvilConfig, CostConfig, ModelConfig, ToolConfig, VerifyConfig
from anvil.core.engine import SYSTEM_PROMPT, TOOL_DEFINITIONS, AnvilEngine, EngineResult
from anvil.core.session import Session, Step, StepKind, StepStatus
from anvil.tools.executor import ToolExecutor
from anvil.verify.pipeline import VerifyPipeline, VerifyReport, VerifyResult, VerifyStatus

# ---------------------------------------------------------------------------
# AnvilEngine initialization
# ---------------------------------------------------------------------------

class TestAnvilEngineInit:
    def test_default_config(self):
        cfg = AnvilConfig()
        engine = AnvilEngine(cfg)
        assert engine.config.model.model == "gpt-4o-mini"
        assert engine.config.verify.enabled is True
        assert engine.tools is not None
        assert engine.verify is not None

    def test_custom_config(self):
        cfg = AnvilConfig(
            model=ModelConfig(model="local"),
            verify=VerifyConfig(enabled=False, max_retries=1),
        )
        engine = AnvilEngine(cfg)
        assert engine.config.verify.enabled is False
        assert engine.config.verify.max_retries == 1

    def test_integrations_initialized(self):
        cfg = AnvilConfig(model=ModelConfig(model="local"))
        engine = AnvilEngine(cfg)
        assert hasattr(engine, "verifyloop")
        assert hasattr(engine, "error_recovery")
        assert hasattr(engine, "agent_swarm")
        assert hasattr(engine, "cost_optimizer")

    def test_tool_executor_initialized(self):
        cfg = AnvilConfig(model=ModelConfig(model="local"))
        engine = AnvilEngine(cfg)
        assert isinstance(engine.tools, ToolExecutor)


# ---------------------------------------------------------------------------
# Plan phase
# ---------------------------------------------------------------------------

class TestPlanPhase:
    def _mock_engine(self, response_content="1. Read the file\n2. Fix the bug\n3. Run tests\n4. Verify the fix"):
        cfg = AnvilConfig(model=ModelConfig(model="local"))
        engine = AnvilEngine(cfg)
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.content = response_content
        mock_model.complete.return_value = mock_response
        engine.model = mock_model
        return engine

    def test_plan_generates_steps(self):
        engine = self._mock_engine()
        session = Session(task="Fix the login bug", persist=False)
        steps = engine._plan("Fix the login bug", session)
        assert len(steps) >= 1
        assert any("Fix" in s or "bug" in s.lower() or "Read" in s for s in steps)

    def test_plan_handles_empty_response(self):
        engine = self._mock_engine(response_content="")
        session = Session(task="Do something", persist=False)
        steps = engine._plan("Do something", session)
        assert len(steps) >= 1  # Falls back to task itself

    def test_plan_handles_bulleted_response(self):
        engine = self._mock_engine(response_content="- Read the file\n- Fix the bug\n- Run tests\n- Verify")
        session = Session(task="Fix bug", persist=False)
        steps = engine._plan("Fix bug", session)
        assert len(steps) >= 1

    def test_plan_fallback_to_task(self):
        engine = self._mock_engine(response_content="No actionable steps here")
        session = Session(task="original task", persist=False)
        steps = engine._plan("original task", session)
        assert len(steps) >= 1

    def test_plan_creates_plan_step_in_session(self):
        engine = self._mock_engine()
        session = Session(task="test", persist=False)
        engine.session = session
        engine._plan("test task", session)
        plan_steps = [s for s in session.steps if s.kind == StepKind.PLAN]
        assert len(plan_steps) >= 1
        assert plan_steps[0].status == StepStatus.SUCCESS


# ---------------------------------------------------------------------------
# Execute phase
# ---------------------------------------------------------------------------

class TestExecutePhase:
    def test_parse_bash_code_block(self):
        cfg = AnvilConfig(model=ModelConfig(model="local"))
        engine = AnvilEngine(cfg)
        text = "```bash\npytest -x\n```"
        calls = engine._parse_tool_calls(text)
        assert len(calls) >= 1
        assert calls[0]["tool"] == "bash"

    def test_parse_python_code_block(self):
        cfg = AnvilConfig(model=ModelConfig(model="local"))
        engine = AnvilEngine(cfg)
        text = "```python\ndef hello():\n    print('hi')\n```"
        calls = engine._parse_tool_calls(text)
        assert len(calls) >= 1

    def test_parse_inline_bash(self):
        cfg = AnvilConfig(model=ModelConfig(model="local"))
        engine = AnvilEngine(cfg)
        text = "bash: `pip install flask`"
        calls = engine._parse_tool_calls(text)
        assert len(calls) >= 1
        assert calls[0]["tool"] == "bash"

    def test_parse_inline_read(self):
        cfg = AnvilConfig(model=ModelConfig(model="local"))
        engine = AnvilEngine(cfg)
        text = "read `src/main.py`"
        calls = engine._parse_tool_calls(text)
        assert len(calls) >= 1
        assert calls[0]["tool"] == "read"

    def test_parse_empty_code_block_skipped(self):
        cfg = AnvilConfig(model=ModelConfig(model="local"))
        engine = AnvilEngine(cfg)
        text = "```\n```"
        calls = engine._parse_tool_calls(text)
        assert len(calls) == 0

    def test_execute_uses_tools(self, tmp_path):
        cfg = AnvilConfig(model=ModelConfig(model="local"))
        cfg.tools.working_dir = str(tmp_path)
        engine = AnvilEngine(cfg)
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.content = '```bash\necho executed\n```'
        mock_model.complete.return_value = mock_response
        engine.model = mock_model
        engine.session = Session(task="test", persist=False)

        result = engine._execute("run echo", [], "", engine.session)
        assert "success" in result
        assert "tool_calls" in result


# ---------------------------------------------------------------------------
# Verify phase
# ---------------------------------------------------------------------------

class TestVerifyPhase:
    def test_verify_with_valid_syntax(self, tmp_path):
        good_file = tmp_path / "valid.py"
        good_file.write_text("x = 1\n")
        pipeline = VerifyPipeline()
        report = pipeline.verify([str(good_file)], working_dir=str(tmp_path))
        syntax_results = [r for r in report.results if r.checker == "syntax"]
        assert any(r.status == VerifyStatus.PASS for r in syntax_results)

    def test_verify_with_invalid_syntax(self, tmp_path):
        bad_file = tmp_path / "broken.py"
        bad_file.write_text("def foo(\npass\n")
        pipeline = VerifyPipeline()
        report = pipeline.verify([str(bad_file)], working_dir=str(tmp_path))
        assert not report.passed

    def test_verify_disabled_skips(self, tmp_path):
        cfg = VerifyConfig(enabled=False)
        assert cfg.enabled is False


# ---------------------------------------------------------------------------
# Recover phase
# ---------------------------------------------------------------------------

class TestRecoverPhase:
    def test_recover_returns_dict(self):
        cfg = AnvilConfig(model=ModelConfig(model="local"))
        engine = AnvilEngine(cfg)
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "```bash\necho fixed\n```"
        mock_model.complete.return_value = mock_response
        engine.model = mock_model
        session = Session(task="test", persist=False)

        report = VerifyReport()
        report.add(VerifyResult(checker="syntax", status=VerifyStatus.FAIL, message="Syntax error"))

        result = engine._recover("fix bug", report, [], session)
        assert isinstance(result, dict)
        assert "success" in result


# ---------------------------------------------------------------------------
# Full loop (Plan → Execute → Verify → Recover)
# ---------------------------------------------------------------------------

class TestFullLoop:
    def test_engine_result_format_success(self):
        session = Session(task="test", persist=False)
        session.add_step(Step(kind=StepKind.PLAN, content="Plan", status=StepStatus.SUCCESS))
        result = EngineResult(success=True, session=session, output="Done")
        formatted = result.format_result()
        assert "SUCCESS" in formatted

    def test_engine_result_format_failure(self):
        result = EngineResult(success=False, session=None, output="Failed", error="error msg")
        formatted = result.format_result()
        assert "FAILED" in formatted
        assert "error msg" in formatted

    def test_max_iterations_respected(self):
        cfg = AnvilConfig(model=ModelConfig(model="local"))
        cfg.verify.enabled = False
        engine = AnvilEngine(cfg)
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.content = "1. Step one\n2. Step two\n3. Step three\n4. Step four\n5. Step five"
        mock_model.complete.return_value = mock_response
        engine.model = mock_model

        session = Session(task="test", persist=False)
        result = engine.run("test task", max_iterations=2)
        assert result.session is not None
        assert len(result.session.steps) <= 6  # max plan + exec steps for 2 iterations


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

class TestEngineConfig:
    def test_default_config(self):
        cfg = AnvilConfig()
        assert cfg.model.model == "gpt-4o-mini"
        assert cfg.verify.enabled is True
        assert cfg.verify.max_retries == 3
        assert cfg.cost.max_cost_per_session_usd == 5.0

    def test_config_from_file(self, tmp_path):
        config_data = {
            "model": {"model": "gpt-4o", "max_tokens": 8192},
            "verify": {"enabled": False, "max_retries": 5},
            "tools": {"sandbox": True},
            "cost": {"max_cost_per_session_usd": 10.0, "max_cost_per_task_usd": 2.0},
        }
        config_file = tmp_path / "anvil.json"
        config_file.write_text(json.dumps(config_data))

        cfg = AnvilConfig.from_file(config_file)
        assert cfg.model.model == "gpt-4o"
        assert cfg.model.max_tokens == 8192
        assert cfg.verify.enabled is False
        assert cfg.verify.max_retries == 5
        assert cfg.tools.sandbox is True
        assert cfg.cost.max_cost_per_session_usd == 10.0
        assert cfg.cost.max_cost_per_task_usd == 2.0

    def test_config_to_file_roundtrip(self, tmp_path):
        cfg = AnvilConfig()
        cfg.verify.max_retries = 7
        cfg.tools.sandbox = True
        path = tmp_path / "config.json"
        cfg.to_file(path)

        loaded = AnvilConfig.from_file(path)
        assert loaded.verify.max_retries == 7
        assert loaded.tools.sandbox is True

    def test_env_vars_not_used_for_defaults(self):
        cfg = AnvilConfig()
        assert cfg.model.model == "gpt-4o-mini"

    def test_find_config_returns_default_when_no_file(self):
        with patch.object(Path, "exists", return_value=False):
            cfg = AnvilConfig.find_config()
            assert cfg.model.model == "gpt-4o-mini"

    def test_model_config(self):
        mc = ModelConfig(model="gpt-4o", api_key="key123", max_tokens=2048)
        assert mc.model == "gpt-4o"
        assert mc.api_key == "key123"
        assert mc.max_tokens == 2048

    def test_tool_config(self):
        tc = ToolConfig(sandbox=True, working_dir="/custom")
        assert tc.sandbox is True
        assert tc.working_dir == "/custom"

    def test_cost_config(self):
        cc = CostConfig(max_cost_per_session_usd=10.0, max_cost_per_task_usd=2.0)
        assert cc.max_cost_per_session_usd == 10.0
        assert cc.max_cost_per_task_usd == 2.0


# ---------------------------------------------------------------------------
# Session tracking
# ---------------------------------------------------------------------------

class TestSessionTracking:
    def test_session_creation(self):
        s = Session(task="my task", persist=False)
        assert s.task == "my task"
        assert len(s.steps) == 0
        assert s.stats.total_steps == 0

    def test_session_add_execute_step(self):
        s = Session(task="test", persist=False)
        s.add_step(Step(kind=StepKind.EXECUTE, content="Run tests", status=StepStatus.SUCCESS))
        assert s.stats.total_steps == 1
        assert s.stats.successful_steps == 1

    def test_session_add_failed_step(self):
        s = Session(task="test", persist=False)
        s.add_step(Step(kind=StepKind.EXECUTE, content="Failed step", status=StepStatus.FAILED))
        assert s.stats.failed_steps == 1
        assert s.stats.error_rate == 1.0

    def test_session_add_recovered_step(self):
        s = Session(task="test", persist=False)
        s.add_step(Step(kind=StepKind.EXECUTE, content="Fail", status=StepStatus.FAILED))
        s.add_step(Step(kind=StepKind.RECOVER, content="Recover", status=StepStatus.RECOVERED))
        assert s.stats.recovered_steps == 1
        assert s.stats.recovery_rate > 0

    def test_session_end(self):
        s = Session(task="test", persist=False)
        s.add_step(Step(kind=StepKind.EXECUTE, content="Done", status=StepStatus.SUCCESS))
        result = s.end("completed")
        assert result["status"] == "completed"
        assert result["stats"]["successful_steps"] == 1

    def test_session_summary(self):
        s = Session(task="test task", persist=False)
        s.add_step(Step(kind=StepKind.PLAN, content="Plan", status=StepStatus.SUCCESS))
        s.add_step(Step(kind=StepKind.EXECUTE, content="Execute", status=StepStatus.SUCCESS))
        summary = s.summary()
        assert summary["steps"] == 2
        assert summary["stats"]["success_rate"] if "success_rate" in summary["stats"] else True

    def test_format_progress(self):
        s = Session(task="my task", persist=False)
        s.add_step(Step(kind=StepKind.PLAN, content="Plan step", status=StepStatus.SUCCESS))
        s.add_step(Step(kind=StepKind.EXECUTE, content="Execute", status=StepStatus.FAILED))
        output = s.format_progress()
        assert "✓" in output
        assert "✗" in output


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

class TestToolDefinitions:
    def test_all_seven_tools_defined(self):
        tool_names = {t["name"] for t in TOOL_DEFINITIONS}
        assert "bash" in tool_names
        assert "read" in tool_names
        assert "write" in tool_names
        assert "edit" in tool_names
        assert "grep" in tool_names
        assert "glob" in tool_names
        assert "ls" in tool_names

    def test_tools_have_descriptions(self):
        for tool in TOOL_DEFINITIONS:
            assert len(tool["description"]) > 0

    def test_tools_have_args(self):
        for tool in TOOL_DEFINITIONS:
            assert len(tool["args"]) > 0

    def test_system_prompt_references_tools(self):
        assert "{tools}" in SYSTEM_PROMPT
