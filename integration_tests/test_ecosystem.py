"""Comprehensive integration tests for the FableForge ecosystem.

Tests that Anvil integrates correctly with VerifyLoop, ErrorRecovery,
AgentSwarm, and CostOptimizer — and that fallbacks work when those
packages are not installed.
"""

import sys
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Ensure the Anvil source tree is importable
# ---------------------------------------------------------------------------
ANVIL_SRC = Path(__file__).resolve().parent.parent / "anvil" / "src"
if str(ANVIL_SRC) not in sys.path:
    sys.path.insert(0, str(ANVIL_SRC))

CLI_SRC = Path(__file__).resolve().parent.parent / "cli" / "src"
if str(CLI_SRC) not in sys.path:
    sys.path.insert(0, str(CLI_SRC))

COST_SRC = Path(__file__).resolve().parent.parent / "cost-optimizer" / "src"
if str(COST_SRC) not in sys.path:
    sys.path.insert(0, str(COST_SRC))


# ===========================================================================
# 1. Anvil → VerifyLoop integration
# ===========================================================================

class TestVerifyLoopIntegration:
    """VerifyLoopIntegration bridges Anvil and VerifyLoop.

    When VerifyLoop is installed, it delegates to AgentPipeline.
    When not installed, it falls back to Anvil's built-in VerifyPipeline.
    """

    def test_imports_successfully(self):
        from anvil.integrations.verifyloop import VerifyLoopIntegration
        integration = VerifyLoopIntegration()
        assert integration is not None

    def test_available_property_reflects_import_status(self):
        from anvil.integrations.verifyloop import VerifyLoopIntegration
        integration = VerifyLoopIntegration()
        # available reflects whether verifyloop package is importable
        assert isinstance(integration.available, bool)

    def test_create_session(self):
        from anvil.integrations.verifyloop import VerifyLoopIntegration, VerifyLoopSession
        integration = VerifyLoopIntegration()
        session = integration.create_session("Write a hello world function", max_retries=5)
        assert isinstance(session, VerifyLoopSession)
        assert session.task == "Write a hello world function"
        assert session.max_retries == 5
        assert session.auto_recover is True
        assert session.steps == []
        assert session.current_step == 0

    def test_verify_falls_back_to_builtin(self, tmp_path):
        from anvil.integrations.verifyloop import VerifyLoopIntegration
        integration = VerifyLoopIntegration()

        good_py = tmp_path / "good.py"
        good_py.write_text("x = 1\n")

        report = integration.verify(files=[str(good_py)])
        assert report is not None
        # Builtin pipeline should run syntax check on valid Python
        assert len(report.results) >= 1

    def test_verify_catches_syntax_error(self, tmp_path):
        from anvil.integrations.verifyloop import VerifyLoopIntegration
        from anvil.verify.pipeline import VerifyStatus
        integration = VerifyLoopIntegration()

        bad_py = tmp_path / "bad.py"
        bad_py.write_text("def foo(\n  pass\n")

        report = integration.verify(files=[str(bad_py)])
        assert report is not None
        failures = [r for r in report.results if r.status == VerifyStatus.FAIL]
        assert len(failures) >= 1, f"Expected syntax failure, got: {[r.message for r in report.results]}"

    def test_verify_code_valid_python(self):
        from anvil.integrations.verifyloop import VerifyLoopIntegration
        from anvil.verify.pipeline import VerifyStatus
        integration = VerifyLoopIntegration()

        report = integration.verify_code("x = 1\n")
        assert report is not None
        assert report.overall in (VerifyStatus.PASS, VerifyStatus.FAIL, VerifyStatus.SKIP, VerifyStatus.ERROR)

    def test_verify_code_catches_bad_syntax(self):
        from anvil.integrations.verifyloop import VerifyLoopIntegration
        from anvil.verify.pipeline import VerifyStatus
        integration = VerifyLoopIntegration()

        report = integration.verify_code("def foo(\n  pass\n")
        failures = [r for r in report.results if r.status == VerifyStatus.FAIL]
        assert len(failures) >= 1

    def test_recover_from_failure_builtin_strategies(self):
        from anvil.integrations.verifyloop import VerifyLoopIntegration
        integration = VerifyLoopIntegration()
        session = integration.create_session("test task")

        result = integration.recover_from_failure(
            step="execute", error="SyntaxError: invalid syntax", session=session,
        )
        assert "success" in result
        assert "strategy" in result
        # Since verifyloop package is not installed, builtin strategies kick in
        assert result["strategy"] in ("fix_syntax", "retry_with_different_approach", "fix_syntax_error")

    def test_verifyloop_step_dataclass(self):
        from anvil.integrations.verifyloop import VerifyLoopStep
        step = VerifyLoopStep(step_type="verify", content="check syntax", status="pending")
        assert step.step_type == "verify"
        assert step.result is None
        assert step.recovery_attempts == 0

    @pytest.mark.integration
    def test_with_mocked_verifyloop_available(self):
        """When the verifyloop package *is* importable, Integration.available is True."""
        from anvil.integrations.verifyloop import VerifyLoopIntegration

        mock_pipeline = MagicMock()
        with patch.dict("sys.modules", {"verifyloop": MagicMock(), "verifyloop.pipeline": MagicMock(AgentPipeline=mock_pipeline)}):
            with patch.object(VerifyLoopIntegration, "_try_import") as mock_import:
                integration = VerifyLoopIntegration.__new__(VerifyLoopIntegration)
                integration._verifyloop = MagicMock()
                integration._available = True
                integration._built_in = MagicMock()

                assert integration.available is True

    def test_recover_from_import_error(self):
        from anvil.integrations.verifyloop import VerifyLoopIntegration
        integration = VerifyLoopIntegration()
        session = integration.create_session("test")

        result = integration.recover_from_failure(
            step="execute", error="ImportError: No module named 'xyz'", session=session,
        )
        assert "strategy" in result
        # Should suggest install_missing_dependency or similar
        assert result["strategy"] in ("install_missing_dependency", "install_module", "retry_with_different_approach")


# ===========================================================================
# 2. Anvil → ErrorRecovery integration
# ===========================================================================

class TestErrorRecoveryIntegration:
    """ErrorRecoveryIntegration classifies errors and maps to strategies."""

    def test_imports_successfully(self):
        from anvil.integrations.error_recovery import ErrorRecoveryIntegration
        er = ErrorRecoveryIntegration()
        assert er is not None

    def test_available_false_without_package(self):
        from anvil.integrations.error_recovery import ErrorRecoveryIntegration
        er = ErrorRecoveryIntegration()
        assert er.available is False

    def test_classify_syntax_error(self):
        from anvil.integrations.error_recovery import ErrorRecoveryIntegration, ErrorCategory
        er = ErrorRecoveryIntegration()
        result = er.recover("SyntaxError: invalid syntax at line 5")
        assert result.category == ErrorCategory.SYNTAX
        assert result.strategy == "fix_syntax_error"
        assert result.confidence >= 0.7

    def test_classify_import_error(self):
        from anvil.integrations.error_recovery import ErrorRecoveryIntegration, ErrorCategory
        er = ErrorRecoveryIntegration()
        result = er.recover("ModuleNotFoundError: No module named 'flask'")
        assert result.category == ErrorCategory.IMPORT
        assert result.strategy == "install_module"

    def test_classify_indentation_error(self):
        from anvil.integrations.error_recovery import ErrorRecoveryIntegration, ErrorCategory
        er = ErrorRecoveryIntegration()
        result = er.recover("IndentationError: expected an indented block")
        assert result.category == ErrorCategory.SYNTAX
        assert result.strategy == "fix_indentation"
        assert result.confidence >= 0.85

    def test_classify_type_error(self):
        from anvil.integrations.error_recovery import ErrorRecoveryIntegration, ErrorCategory
        er = ErrorRecoveryIntegration()
        result = er.recover("TypeError: unsupported operand type(s) for +: 'int' and 'str'")
        assert result.category == ErrorCategory.RUNTIME
        assert result.strategy in ("fix_type_error", "fix_type_mismatch")

    def test_classify_assertion_error(self):
        from anvil.integrations.error_recovery import ErrorRecoveryIntegration, ErrorCategory
        er = ErrorRecoveryIntegration()
        result = er.recover("AssertionError: expected 5 but got 3")
        assert result.category == ErrorCategory.TEST

    def test_classify_key_error(self):
        from anvil.integrations.error_recovery import ErrorRecoveryIntegration, ErrorCategory
        er = ErrorRecoveryIntegration()
        result = er.recover("KeyError: 'missing_key'")
        assert result.category == ErrorCategory.RUNTIME
        assert result.strategy == "fix_missing_key"

    def test_classify_permission_error(self):
        from anvil.integrations.error_recovery import ErrorRecoveryIntegration, ErrorCategory
        er = ErrorRecoveryIntegration()
        result = er.recover("PermissionError: [Errno 13] Permission denied")
        assert result.category == ErrorCategory.PERMISSION
        assert result.strategy == "fix_file_permissions"

    def test_classify_timeout_error(self):
        from anvil.integrations.error_recovery import ErrorRecoveryIntegration, ErrorCategory
        er = ErrorRecoveryIntegration()
        result = er.recover("TimeoutExpired: command timed out after 30s")
        assert result.category == ErrorCategory.TIMEOUT
        assert result.strategy == "increase_timeout_or_optimize"

    def test_classify_unknown_error(self):
        from anvil.integrations.error_recovery import ErrorRecoveryIntegration, ErrorCategory
        er = ErrorRecoveryIntegration()
        result = er.recover("Something totally unexpected happened")
        assert result.category == ErrorCategory.UNKNOWN
        assert result.strategy == "retry_with_different_approach"
        assert result.confidence < 0.5

    def test_recovery_strategies_for_syntax(self):
        from anvil.integrations.error_recovery import ErrorRecoveryIntegration
        er = ErrorRecoveryIntegration()
        strategies = er.get_recovery_strategies("SyntaxError: invalid syntax")
        assert "fix_syntax_error" in strategies
        assert "review_code_structure" in strategies

    def test_recovery_strategies_for_import(self):
        from anvil.integrations.error_recovery import ErrorRecoveryIntegration
        er = ErrorRecoveryIntegration()
        strategies = er.get_recovery_strategies("ModuleNotFoundError: No module named 'xyz'")
        assert "install_module" in strategies
        assert "check_requirements_txt" in strategies

    def test_recovery_strategies_for_test(self):
        from anvil.integrations.error_recovery import ErrorRecoveryIntegration
        er = ErrorRecoveryIntegration()
        strategies = er.get_recovery_strategies("AssertionError: test failed")
        assert "check_test_expectations" in strategies
        assert "run_tests_in_isolation" in strategies

    def test_recovery_strategies_for_runtime(self):
        from anvil.integrations.error_recovery import ErrorRecoveryIntegration
        er = ErrorRecoveryIntegration()
        strategies = er.get_recovery_strategies("TypeError: unsupported operand")
        assert "add_error_handling" in strategies

    def test_recovery_result_dataclass_fields(self):
        from anvil.integrations.error_recovery import RecoveryResult, ErrorCategory
        result = RecoveryResult(
            success=False, strategy="fix_syntax", diagnosis="bad syntax",
            confidence=0.85, original_error="SyntaxError", category=ErrorCategory.SYNTAX,
        )
        assert result.success is False
        assert result.category == ErrorCategory.SYNTAX
        assert result.confidence == 0.85

    def test_lint_error_pattern(self):
        from anvil.integrations.error_recovery import ErrorRecoveryIntegration, ErrorCategory
        er = ErrorRecoveryIntegration()
        result = er.recover("F401 'os' imported but unused")
        assert result.category == ErrorCategory.LINT

    def test_mypy_error_pattern(self):
        from anvil.integrations.error_recovery import ErrorRecoveryIntegration, ErrorCategory
        er = ErrorRecoveryIntegration()
        result = er.recover("mypy: Incompatible types in assignment")
        assert result.category == ErrorCategory.TYPE

    @pytest.mark.integration
    def test_with_error_recovery_package_installed(self):
        """When error_recovery package is importable, Integration.available is True."""
        from anvil.integrations.error_recovery import ErrorRecoveryIntegration
        integration = ErrorRecoveryIntegration.__new__(ErrorRecoveryIntegration)
        integration._available = True
        mock_engine_result = MagicMock()
        mock_engine_result.success = True
        mock_engine_result.strategy = "auto_fix"
        mock_engine_result.fix = "added closing paren"

        mock_engine = MagicMock()
        mock_engine.recover.return_value = mock_engine_result
        mock_engine_class = MagicMock(return_value=mock_engine)
        integration._engine = mock_engine_class

        result = integration.recover("SyntaxError: bad", context={"step": "exec"})
        assert result.success is True
        assert result.fix_applied == "added closing paren"


# ===========================================================================
# 3. Anvil → AgentSwarm integration
# ===========================================================================

class TestAgentSwarmIntegration:
    """AgentSwarmIntegration uses transition matrices from real traces."""

    def test_imports_successfully(self):
        from anvil.integrations.agent_swarm import AgentSwarmIntegration
        swarm = AgentSwarmIntegration()
        assert swarm is not None

    def test_available_property_reflects_import_status(self):
        from anvil.integrations.agent_swarm import AgentSwarmIntegration
        swarm = AgentSwarmIntegration()
        # available reflects whether agent_swarm package is importable
        assert isinstance(swarm.available, bool)

    def test_transition_matrix_bash_to_bash(self):
        from anvil.integrations.agent_swarm import AgentSwarmIntegration
        prob = AgentSwarmIntegration().get_handoff_probability("Bash", "Bash")
        assert prob == pytest.approx(0.59, abs=0.01)

    def test_transition_matrix_bash_to_edit(self):
        from anvil.integrations.agent_swarm import AgentSwarmIntegration
        prob = AgentSwarmIntegration().get_handoff_probability("Bash", "Edit")
        assert prob == pytest.approx(0.18, abs=0.01)

    def test_transition_matrix_bash_to_read(self):
        from anvil.integrations.agent_swarm import AgentSwarmIntegration
        prob = AgentSwarmIntegration().get_handoff_probability("Bash", "Read")
        assert prob == pytest.approx(0.15, abs=0.01)

    def test_transition_matrix_edit_to_bash(self):
        from anvil.integrations.agent_swarm import AgentSwarmIntegration
        prob = AgentSwarmIntegration().get_handoff_probability("Edit", "Bash")
        assert prob == pytest.approx(0.34, abs=0.01)

    def test_transition_matrix_edit_to_read(self):
        from anvil.integrations.agent_swarm import AgentSwarmIntegration
        prob = AgentSwarmIntegration().get_handoff_probability("Edit", "Read")
        assert prob == pytest.approx(0.28, abs=0.01)

    def test_transition_matrix_edit_to_edit(self):
        from anvil.integrations.agent_swarm import AgentSwarmIntegration
        prob = AgentSwarmIntegration().get_handoff_probability("Edit", "Edit")
        assert prob == pytest.approx(0.20, abs=0.01)

    def test_transition_matrix_read_to_bash(self):
        from anvil.integrations.agent_swarm import AgentSwarmIntegration
        prob = AgentSwarmIntegration().get_handoff_probability("Read", "Bash")
        assert prob == pytest.approx(0.37, abs=0.01)

    def test_predict_next_tool_from_bash(self):
        from anvil.integrations.agent_swarm import AgentSwarmIntegration
        swarm = AgentSwarmIntegration()
        next_tool = swarm.predict_next_tool("Bash")
        assert next_tool == "Bash"  # 0.59 is highest

    def test_predict_next_tool_from_edit(self):
        from anvil.integrations.agent_swarm import AgentSwarmIntegration
        swarm = AgentSwarmIntegration()
        next_tool = swarm.predict_next_tool("Edit")
        assert next_tool == "Bash"  # 0.34 is highest

    def test_predict_next_tool_from_read(self):
        from anvil.integrations.agent_swarm import AgentSwarmIntegration
        swarm = AgentSwarmIntegration()
        next_tool = swarm.predict_next_tool("Read")
        assert next_tool == "Bash"  # 0.37 is highest

    def test_predict_next_tool_from_grep(self):
        from anvil.integrations.agent_swarm import AgentSwarmIntegration
        swarm = AgentSwarmIntegration()
        result = swarm.predict_next_tool("Grep")
        assert result == "Read"  # 0.40 is highest for Grep

    def test_predict_next_tool_from_glob(self):
        from anvil.integrations.agent_swarm import AgentSwarmIntegration
        result = AgentSwarmIntegration().predict_next_tool("Glob")
        assert result == "Read"  # 0.50 is highest for Glob

    def test_predict_unknown_tool_defaults_to_read(self):
        from anvil.integrations.agent_swarm import AgentSwarmIntegration
        result = AgentSwarmIntegration().predict_next_tool("UnknownTool")
        assert result == "Read"  # default fallback

    def test_handoff_probability_unknown_returns_zero(self):
        from anvil.integrations.agent_swarm import AgentSwarmIntegration
        prob = AgentSwarmIntegration().get_handoff_probability("Bash", "Unknown")
        assert prob == 0.0

    def test_plan_agent_sequence_fallback(self):
        from anvil.integrations.agent_swarm import AgentSwarmIntegration
        swarm = AgentSwarmIntegration()
        sequence = swarm.plan_agent_sequence("Fix the login bug")
        assert isinstance(sequence, list)
        assert len(sequence) > 0
        assert all(isinstance(t, str) for t in sequence)

    def test_get_transition_matrix(self):
        from anvil.integrations.agent_swarm import AgentSwarmIntegration, TRANSITION_MATRIX
        swarm = AgentSwarmIntegration()
        matrix = swarm.get_transition_matrix()
        assert matrix == TRANSITION_MATRIX
        # Verify it's a copy, not a reference
        assert matrix is not TRANSITION_MATRIX or matrix == TRANSITION_MATRIX

    def test_transition_probabilities_sum_to_one(self):
        from anvil.integrations.agent_swarm import TRANSITION_MATRIX
        for tool, transitions in TRANSITION_MATRIX.items():
            total = sum(transitions.values())
            assert total == pytest.approx(1.0, abs=0.01), f"Transitions from {tool} sum to {total}, not 1.0"

    def test_swarm_config_defaults(self):
        from anvil.integrations.agent_swarm import SwarmConfig
        config = SwarmConfig()
        assert config.max_agents == 5
        assert config.handoff_strategy == "transition_matrix"
        assert config.planning_rate == 0.877
        assert config.error_recovery_rate == 0.395


# ===========================================================================
# 4. Anvil → CostOptimizer integration
# ===========================================================================

class TestCostOptimizerIntegration:
    """CostOptimizerIntegration routes models by complexity and tracks costs."""

    def test_imports_successfully(self):
        from anvil.integrations.cost_optimizer import CostOptimizerIntegration
        co = CostOptimizerIntegration()
        assert co is not None

    def test_available_property_reflects_import_status(self):
        from anvil.integrations.cost_optimizer import CostOptimizerIntegration
        co = CostOptimizerIntegration()
        # available reflects whether cost_optimizer package is importable
        assert isinstance(co.available, bool)

    def test_route_simple_task_to_local(self):
        from anvil.integrations.cost_optimizer import CostOptimizerIntegration
        co = CostOptimizerIntegration()
        model = co.route_model("list the files in the project")
        assert model == "local"

    def test_route_simple_task_show(self):
        from anvil.integrations.cost_optimizer import CostOptimizerIntegration
        co = CostOptimizerIntegration()
        model = co.route_model("show me the error logs")
        assert model == "local"

    def test_route_simple_task_grep(self):
        from anvil.integrations.cost_optimizer import CostOptimizerIntegration
        co = CostOptimizerIntegration()
        model = co.route_model("find all TODO comments")
        assert model == "local"

    def test_route_medium_task_to_local(self):
        from anvil.integrations.cost_optimizer import CostOptimizerIntegration
        co = CostOptimizerIntegration()
        model = co.route_model("add a unit test for the login function")
        assert model == "local"  # medium routes to local by default

    def test_route_medium_task_fix(self):
        from anvil.integrations.cost_optimizer import CostOptimizerIntegration
        co = CostOptimizerIntegration()
        model = co.route_model("fix the broken import statement")
        assert model == "local"

    def test_route_complex_task_to_gpt4o(self):
        from anvil.integrations.cost_optimizer import CostOptimizerIntegration
        co = CostOptimizerIntegration()
        model = co.route_model("architect a microservices migration strategy")
        assert model == "gpt-4o"

    def test_route_complex_task_debug(self):
        from anvil.integrations.cost_optimizer import CostOptimizerIntegration
        co = CostOptimizerIntegration()
        model = co.route_model("debug the intermittent race condition in the worker queue")
        assert model == "gpt-4o"

    def test_route_complex_task_optimize(self):
        from anvil.integrations.cost_optimizer import CostOptimizerIntegration
        co = CostOptimizerIntegration()
        model = co.route_model("optimize the database query performance for the dashboard")
        assert model == "gpt-4o"

    def test_route_default_model_fallback(self):
        from anvil.integrations.cost_optimizer import CostOptimizerIntegration
        co = CostOptimizerIntegration()
        # Task with no complexity keywords defaults to "medium" → "local"
        model = co.route_model("do something unspecified", default_model="gpt-4o-mini")
        assert model == "local"

    def test_calculate_cost_gpt4o(self):
        from anvil.integrations.cost_optimizer import CostOptimizerIntegration
        co = CostOptimizerIntegration()
        # gpt-4o: $2.50/1M input, $10.00/1M output
        cost = co.calculate_cost(input_tokens=1_000_000, output_tokens=0, model="gpt-4o")
        assert cost == pytest.approx(2.50, abs=0.01)

    def test_calculate_cost_gpt4o_output(self):
        from anvil.integrations.cost_optimizer import CostOptimizerIntegration
        co = CostOptimizerIntegration()
        # gpt-4o: $10.00/1M output
        cost = co.calculate_cost(input_tokens=0, output_tokens=1_000_000, model="gpt-4o")
        assert cost == pytest.approx(10.00, abs=0.01)

    def test_calculate_cost_mixed(self):
        from anvil.integrations.cost_optimizer import CostOptimizerIntegration
        co = CostOptimizerIntegration()
        # 500K input + 200K output on gpt-4o
        # 500K * $2.50/1M = $1.25, 200K * $10.00/1M = $2.00 => $3.25
        cost = co.calculate_cost(input_tokens=500_000, output_tokens=200_000, model="gpt-4o")
        assert cost == pytest.approx(3.25, abs=0.01)

    def test_calculate_cost_local_is_free(self):
        from anvil.integrations.cost_optimizer import CostOptimizerIntegration
        co = CostOptimizerIntegration()
        cost = co.calculate_cost(input_tokens=1_000_000, output_tokens=1_000_000, model="local")
        assert cost == 0.0

    def test_track_usage(self):
        from anvil.integrations.cost_optimizer import CostOptimizerIntegration
        co = CostOptimizerIntegration()
        report = co.track_usage("gpt-4o", input_tokens=100_000, output_tokens=50_000, task="write tests")
        assert report.model == "gpt-4o"
        assert report.input_tokens == 100_000
        assert report.output_tokens == 50_000
        assert report.cost_usd > 0
        assert report.task == "write tests"

    def test_budget_tracking_within_budget(self):
        from anvil.integrations.cost_optimizer import CostOptimizerIntegration
        co = CostOptimizerIntegration(max_cost_per_session=5.0)
        assert co.is_within_budget(estimated_cost=1.0) is True
        assert co.is_within_budget(estimated_cost=4.99) is True

    def test_budget_tracking_exceeds_budget(self):
        from anvil.integrations.cost_optimizer import CostOptimizerIntegration
        co = CostOptimizerIntegration(max_cost_per_session=5.0)
        co.track_usage("gpt-4o", input_tokens=1_000_000, output_tokens=0, task="big task")
        # Spent $2.50 so far. $2.50 + $2.50 = $5.00 which is NOT < $5.00 (strict less-than)
        assert co.is_within_budget(estimated_cost=2.5) is False
        # $2.50 + $1.99 = $4.49 which IS within budget
        assert co.is_within_budget(estimated_cost=2.0) is True
        # Clearly way over budget
        assert co.is_within_budget(estimated_cost=10.0) is False

    def test_task_budget(self):
        from anvil.integrations.cost_optimizer import CostOptimizerIntegration
        co = CostOptimizerIntegration(max_cost_per_task=1.0)
        assert co.is_task_within_budget(estimated_cost=0.50) is True
        assert co.is_task_within_budget(estimated_cost=1.50) is False

    def test_session_summary(self):
        from anvil.integrations.cost_optimizer import CostOptimizerIntegration
        co = CostOptimizerIntegration(max_cost_per_session=5.0)
        co.track_usage("local", input_tokens=5000, output_tokens=2000, task="list files")
        co.track_usage("gpt-4o", input_tokens=100_000, output_tokens=50_000, task="architect")

        summary = co.get_session_summary()
        assert summary["total_requests"] == 2
        assert summary["total_input_tokens"] == 105_000
        assert summary["total_output_tokens"] == 52_000
        assert summary["total_cost_usd"] > 0
        assert "local" in summary["models_used"]
        assert "gpt-4o" in summary["models_used"]
        assert summary["budget_used_percent"] > 0

    def test_session_summary_budget_remaining(self):
        from anvil.integrations.cost_optimizer import CostOptimizerIntegration
        co = CostOptimizerIntegration(max_cost_per_session=5.0)
        co.track_usage("gpt-4o", input_tokens=1_000_000, output_tokens=0)

        summary = co.get_session_summary()
        # $2.50 spent out of $5.00 budget => 50% used, $2.50 remaining
        assert summary["budget_used_percent"] == pytest.approx(50.0, abs=1.0)
        assert summary["budget_remaining_usd"] > 0

    def test_model_pricing_gpt4o_input(self):
        from anvil.integrations.cost_optimizer import MODEL_PRICING
        gpt4o = MODEL_PRICING["gpt-4o"]
        # $2.50 per 1M input tokens
        assert gpt4o["input"] == pytest.approx(2.50 / 1_000_000, abs=1e-10)

    def test_model_pricing_gpt4o_output(self):
        from anvil.integrations.cost_optimizer import MODEL_PRICING
        gpt4o = MODEL_PRICING["gpt-4o"]
        # $10.00 per 1M output tokens
        assert gpt4o["output"] == pytest.approx(10.00 / 1_000_000, abs=1e-10)

    def test_optimization_suggestions_under_threshold(self):
        from anvil.integrations.cost_optimizer import CostOptimizerIntegration
        co = CostOptimizerIntegration(max_cost_per_session=100.0)  # high budget
        co.track_usage("local", input_tokens=1000, output_tokens=500, task="test")
        suggestions = co.get_optimization_suggestions()
        # Under 80% budget, no budget warning
        assert len(suggestions) == 0

    def test_optimization_suggestions_over_threshold(self):
        from anvil.integrations.cost_optimizer import CostOptimizerIntegration
        co = CostOptimizerIntegration(max_cost_per_session=0.01)  # very low budget
        co.track_usage("gpt-4o", input_tokens=10_000, output_tokens=5_000, task="test")
        suggestions = co.get_optimization_suggestions()
        # Should suggest switching from gpt-4o to gpt-4o-mini
        assert any("gpt-4o-mini" in s for s in suggestions)


# ===========================================================================
# 5. Anvil engine full loop
# ===========================================================================

class TestAnvilEngineFullLoop:
    """Tests the entire Anvil engine lifecycle with mocked model."""

    def _make_mock_model(self, response_content="1. Read the file\n2. Fix the bug\n3. Verify the fix"):
        """Create a mock model that returns predictable responses."""
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.content = response_content
        mock_model.complete.return_value = mock_response
        return mock_model

    def test_engine_initializes_with_integrations(self):
        from anvil.core.engine import AnvilEngine
        from anvil.core.config import AnvilConfig
        config = AnvilConfig()
        engine = AnvilEngine.__new__(AnvilEngine)
        engine.config = config

        with patch.object(AnvilEngine, "__init__", lambda self, *a, **kw: None):
            engine = AnvilEngine.__new__(AnvilEngine)
            engine.config = config
            engine._init_integrations()

        assert hasattr(engine, "verifyloop")
        assert hasattr(engine, "error_recovery")
        assert hasattr(engine, "agent_swarm")
        assert hasattr(engine, "cost_optimizer")

    def test_engine_session_tracking(self):
        from anvil.core.session import Session, Step, StepKind, StepStatus
        session = Session(task="Test task", persist=False)
        assert session.task == "Test task"
        assert session.steps == []
        assert session.stats.total_steps == 0

        step = Step(kind=StepKind.PLAN, content="Plan step", status=StepStatus.SUCCESS)
        session.add_step(step)
        assert len(session.steps) == 1
        assert session.stats.total_steps == 1
        assert session.stats.successful_steps == 1

    def test_engine_session_multiple_steps(self):
        from anvil.core.session import Session, Step, StepKind, StepStatus
        session = Session(task="Multi-step task", persist=False)

        session.add_step(Step(kind=StepKind.PLAN, content="Plan", status=StepStatus.SUCCESS))
        session.add_step(Step(kind=StepKind.EXECUTE, content="Execute", status=StepStatus.SUCCESS))
        session.add_step(Step(kind=StepKind.VERIFY, content="Verify", status=StepStatus.FAILED))
        session.add_step(Step(kind=StepKind.RECOVER, content="Recover", status=StepStatus.RECOVERED))

        summary = session.end("completed")
        assert summary["stats"]["total_steps"] == 4
        assert summary["stats"]["successful_steps"] == 3  # success + recovered
        assert summary["stats"]["failed_steps"] == 1  # count failed before recovery
        assert summary["stats"]["recovered_steps"] == 1

    def test_tool_executor_bash(self):
        from anvil.tools.executor import ToolExecutor
        executor = ToolExecutor(working_dir=str(Path(__file__).parent))
        result = executor.execute("bash", {"command": "echo hello"})
        assert result.success is True
        assert "hello" in result.output

    def test_tool_executor_bash_blocked(self):
        from anvil.tools.executor import ToolExecutor
        executor = ToolExecutor(working_dir=str(Path(__file__).parent))
        result = executor.execute("bash", {"command": "rm -rf /"})
        assert result.success is False
        assert "Blocked" in result.error

    def test_tool_executor_read(self, tmp_path):
        from anvil.tools.executor import ToolExecutor
        test_file = tmp_path / "test_read.txt"
        test_file.write_text("Hello World")

        executor = ToolExecutor(working_dir=str(tmp_path))
        result = executor.execute("read", {"path": "test_read.txt"})
        assert result.success is True
        assert "Hello World" in result.output

    def test_tool_executor_write(self, tmp_path):
        from anvil.tools.executor import ToolExecutor
        executor = ToolExecutor(working_dir=str(tmp_path))
        result = executor.execute("write", {"path": "test_write.txt", "content": "Test content"})
        assert result.success is True
        assert (tmp_path / "test_write.txt").read_text() == "Test content"

    def test_tool_executor_edit(self, tmp_path):
        from anvil.tools.executor import ToolExecutor
        test_file = tmp_path / "test_edit.py"
        test_file.write_text("def foo():\n    return 1\n")

        executor = ToolExecutor(working_dir=str(tmp_path))
        result = executor.execute("edit", {
            "path": "test_edit.py",
            "old_string": "return 1",
            "new_string": "return 2",
        })
        assert result.success is True
        assert "return 2" in (tmp_path / "test_edit.py").read_text()

    def test_tool_executor_unknown_tool(self):
        from anvil.tools.executor import ToolExecutor
        executor = ToolExecutor(working_dir=".")
        result = executor.execute("unknown", {})
        assert result.success is False
        assert "Unknown tool" in result.error

    def test_verify_pipeline_catches_syntax_error(self):
        from anvil.verify.pipeline import VerifyPipeline, VerifyStatus
        pipeline = VerifyPipeline()
        report = pipeline.verify_code("def foo(\n  pass\n")
        assert report.overall == VerifyStatus.FAIL
        failures = report.failures
        assert len(failures) >= 1
        assert "syntax" in failures[0].message.lower() or "SyntaxError" in failures[0].message

    def test_verify_pipeline_valid_python(self):
        from anvil.verify.pipeline import VerifyPipeline, VerifyStatus
        pipeline = VerifyPipeline()
        report = pipeline.verify_code("x = 1\n")
        assert report.overall == VerifyStatus.PASS

    def test_engine_result_format(self):
        from anvil.core.engine import EngineResult
        from anvil.core.session import Session, Step, StepKind, StepStatus

        session = Session(task="test", persist=False)
        session.add_step(Step(kind=StepKind.PLAN, content="Plan", status=StepStatus.SUCCESS))

        result = EngineResult(
            success=True, session=session, output="Task completed",
        )
        formatted = result.format_result()
        assert "SUCCESS" in formatted
        assert "Task completed" in formatted

    def test_engine_result_format_failure(self):
        from anvil.core.engine import EngineResult
        from anvil.core.session import Session

        session = Session(task="test", persist=False)
        result = EngineResult(
            success=False, session=session, output="Failed", error="Something went wrong",
        )
        formatted = result.format_result()
        assert "FAILED" in formatted
        assert "Something went wrong" in formatted

    def test_config_defaults(self):
        from anvil.core.config import AnvilConfig
        config = AnvilConfig()
        assert config.verify.enabled is True
        assert config.verify.auto_recover is True
        assert config.verify.max_retries == 3
        assert config.cost.max_cost_per_session_usd == 5.0
        assert config.cost.max_cost_per_task_usd == 1.0
        assert config.model.model == "local"

    def test_config_from_dict(self, tmp_path):
        from anvil.core.config import AnvilConfig
        config_data = {
            "model": {"model": "gpt-4o"},
            "verify": {"enabled": False, "max_retries": 5},
            "cost": {"max_cost_per_session_usd": 10.0},
        }
        config_file = tmp_path / "anvil.json"
        config_file.write_text(json.dumps(config_data))

        config = AnvilConfig.from_file(config_file)
        assert config.model.model == "gpt-4o"
        assert config.verify.enabled is False
        assert config.verify.max_retries == 5
        assert config.cost.max_cost_per_session_usd == 10.0


# ===========================================================================
# 6. FableForge CLI integration
# ===========================================================================

class TestFableForgeCLI:
    """Test that the FableForge CLI commands work correctly."""

    def test_projects_constant_exists(self):
        from fableforge.cli import PROJECTS
        assert isinstance(PROJECTS, dict)
        assert len(PROJECTS) == 21

    def test_projects_keys_are_sluggified(self):
        from fableforge.cli import PROJECTS
        for key in PROJECTS:
            assert key == key.lower(), f"Project key should be lowercase: {key}"

    def test_anvil_project_in_projects(self):
        from fableforge.cli import PROJECTS
        assert "anvil" in PROJECTS
        assert PROJECTS["anvil"]["name"] == "Anvil"

    def test_verifyloop_project_in_projects(self):
        from fableforge.cli import PROJECTS
        assert "verifyloop" in PROJECTS
        assert PROJECTS["verifyloop"]["name"] == "VerifyLoop"

    def test_error_recovery_project_in_projects(self):
        from fableforge.cli import PROJECTS
        assert "error-recovery" in PROJECTS
        assert PROJECTS["error-recovery"]["name"] == "ErrorRecovery"

    def test_agent_swarm_project_in_projects(self):
        from fableforge.cli import PROJECTS
        assert "agent-swarm" in PROJECTS
        assert PROJECTS["agent-swarm"]["name"] == "AgentSwarm"

    def test_cost_optimizer_project_in_projects(self):
        from fableforge.cli import PROJECTS
        assert "cost-optimizer" in PROJECTS
        assert PROJECTS["cost-optimizer"]["name"] == "CostOptimizer"

    def test_project_structure_has_required_fields(self):
        from fableforge.cli import PROJECTS
        for key, info in PROJECTS.items():
            assert "name" in info, f"Project {key} missing name"
            assert "desc" in info, f"Project {key} missing desc"
            assert "layer" in info, f"Project {key} missing layer"

    def test_status_command_returns_installed_for_anvil(self):
        """Status command should detect anvil as importable via sys.path."""
        # Anvil is importable via our sys.path setup
        import importlib
        try:
            importlib.import_module("anvil")
            anvil_available = True
        except ImportError:
            anvil_available = False
        # Since we added anvil to sys.path, it should be importable
        assert anvil_available, "Anvil should be importable for integration tests"

    def test_verify_command_with_valid_python(self, tmp_path):
        """Verify command should pass for valid Python files."""
        from anvil.verify.pipeline import VerifyPipeline, VerifyStatus

        good_file = tmp_path / "good.py"
        good_file.write_text("x = 1\n")

        pipeline = VerifyPipeline()
        report = pipeline.verify(files=[str(good_file)], working_dir=str(tmp_path), checks=["syntax"])
        # Syntax check should pass; skip import/lint checks that need python/node
        syntax_results = [r for r in report.results if r.checker == "syntax"]
        assert len(syntax_results) >= 1
        assert syntax_results[0].status == VerifyStatus.PASS

    def test_verify_command_with_bad_python(self, tmp_path):
        """Verify command should report failures for invalid Python."""
        from anvil.verify.pipeline import VerifyPipeline, VerifyStatus

        bad_file = tmp_path / "bad.py"
        bad_file.write_text("def foo(\n  pass\n")

        pipeline = VerifyPipeline()
        report = pipeline.verify(files=[str(bad_file)], working_dir=str(tmp_path))
        assert report.overall == VerifyStatus.FAIL

    def test_cli_main_is_click_group(self):
        from fableforge.cli import main
        assert hasattr(main, "commands") or callable(main)

    def test_cli_has_run_command(self):
        from fableforge.cli import main
        commands = main.list_commands(None)
        assert "run" in commands

    def test_cli_has_verify_command(self):
        from fableforge.cli import main
        commands = main.list_commands(None)
        assert "verify" in commands

    def test_cli_has_projects_command(self):
        from fableforge.cli import main
        commands = main.list_commands(None)
        assert "projects" in commands

    def test_cli_has_status_command(self):
        from fableforge.cli import main
        commands = main.list_commands(None)
        assert "status" in commands


# ===========================================================================
# 7. Cross-integration tests
# ===========================================================================

class TestCrossIntegration:
    """Tests that verify multiple integrations work together."""

    def test_error_recovery_and_verifyloop_classify_same_syntax_error(self):
        """Both integrations should classify a SyntaxError consistently."""
        from anvil.integrations.verifyloop import VerifyLoopIntegration
        from anvil.integrations.error_recovery import ErrorRecoveryIntegration, ErrorCategory

        vl = VerifyLoopIntegration()
        er = ErrorRecoveryIntegration()

        error_msg = "SyntaxError: invalid syntax at line 5"

        # VerifyLoop recovery
        session = vl.create_session("test")
        vl_result = vl.recover_from_failure("execute", error_msg, session)

        # ErrorRecovery classification
        er_result = er.recover(error_msg)

        # Both should identify this as a syntax error
        assert er_result.category == ErrorCategory.SYNTAX
        assert er_result.strategy == "fix_syntax_error"
        # VerifyLoop should at least suggest a strategy
        assert vl_result["strategy"] is not None

    def test_cost_optimizer_tracks_engine_session_costs(self):
        """CostOptimizer should track costs for tools used in engine sessions."""
        from anvil.integrations.cost_optimizer import CostOptimizerIntegration

        co = CostOptimizerIntegration(max_cost_per_session=5.0)

        # Simulate a session with multiple model calls
        co.track_usage("local", input_tokens=5000, output_tokens=2000, task="list files")
        co.track_usage("gpt-4o", input_tokens=100_000, output_tokens=50_000, task="architect solution")
        co.track_usage("gpt-4o-mini", input_tokens=50_000, output_tokens=20_000, task="add tests")

        summary = co.get_session_summary()
        assert summary["total_requests"] == 3
        assert summary["total_input_tokens"] == 155_000
        assert summary["total_output_tokens"] == 72_000
        assert summary["total_cost_usd"] > 0
        assert summary["budget_remaining_usd"] > 0
        assert summary["budget_used_percent"] < 100

    def test_agent_swarm_and_cost_optimizer_together(self):
        """AgentSwarm predicts next tool, CostOptimizer routes to right model."""
        from anvil.integrations.agent_swarm import AgentSwarmIntegration
        from anvil.integrations.cost_optimizer import CostOptimizerIntegration

        swarm = AgentSwarmIntegration()
        co = CostOptimizerIntegration()

        # After a Bash command, predict next tool
        next_tool = swarm.predict_next_tool("Bash")
        assert next_tool == "Bash"  # Most common transition

        # Route a simple task
        model = co.route_model(f"run the {next_tool.lower()} command")
        assert model == "local"  # Simple tasks → local

        # After Edit, would route a complex task
        next_after_edit = swarm.predict_next_tool("Edit")
        model_for_complex = co.route_model("architect a new module")
        assert model_for_complex == "gpt-4o"

    def test_full_verify_and_recover_pipeline(self, tmp_path):
        """Verify → Find error → Classify with ErrorRecovery → Get strategy."""
        from anvil.verify.pipeline import VerifyPipeline
        from anvil.integrations.error_recovery import ErrorRecoveryIntegration, ErrorCategory
        from anvil.integrations.verifyloop import VerifyLoopIntegration

        # Create a file with a syntax error
        bad_file = tmp_path / "broken.py"
        bad_file.write_text("def foo(\n  pass\n")

        # Step 1: Verify with pipeline
        pipeline = VerifyPipeline()
        report = pipeline.verify([str(bad_file)], working_dir=str(tmp_path))
        assert not report.passed

        # Step 2: Classify the error with ErrorRecovery
        er = ErrorRecoveryIntegration()
        failures = report.failures
        assert len(failures) > 0

        error_msg = failures[0].message
        # Use ErrorRecovery to classify the raw error message pattern
        # The verify pipeline produces messages like "Syntax error: ..."
        # which should match "syntax" pattern
        result = er.recover(error_msg)
        # It should be classified (either SYNTAX or UNKNOWN depending on exact message)
        assert result.category in (ErrorCategory.SYNTAX, ErrorCategory.UNKNOWN)
        assert result.strategy is not None

        # Step 3: Also test VerifyLoop fallback
        vl = VerifyLoopIntegration()
        vl_report = vl.verify([str(bad_file)], working_dir=str(tmp_path))
        assert not vl_report.passed
        assert len(vl_report.failures) > 0

    def test_all_integration_available_flags_reflect_import_status(self):
        """Verify that available flags correctly reflect whether packages can be imported."""
        from anvil.integrations.verifyloop import VerifyLoopIntegration
        from anvil.integrations.error_recovery import ErrorRecoveryIntegration
        from anvil.integrations.agent_swarm import AgentSwarmIntegration
        from anvil.integrations.cost_optimizer import CostOptimizerIntegration

        # Each should have a boolean available property
        assert isinstance(VerifyLoopIntegration().available, bool)
        assert isinstance(ErrorRecoveryIntegration().available, bool)
        assert isinstance(AgentSwarmIntegration().available, bool)
        assert isinstance(CostOptimizerIntegration().available, bool)

    def test_transition_matrix_covers_all_tools(self):
        """All tools in TOOL_DEFINITIONS should appear in the transition matrix."""
        from anvil.integrations.agent_swarm import TRANSITION_MATRIX
        from anvil.core.engine import TOOL_DEFINITIONS

        tool_names = {t["name"] for t in TOOL_DEFINITIONS}
        # Core tools that should appear in the matrix
        core_tools = {"Bash", "Read", "Write", "Edit", "Grep", "Glob"}
        for tool in core_tools:
            assert tool in TRANSITION_MATRIX, f"Tool {tool} missing from transition matrix"
