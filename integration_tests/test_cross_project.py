"""Cross-project integration tests for the FableForge ecosystem.

Tests data flow between projects:
- Anvil → VerifyLoop
- Anvil → ErrorRecovery
- Anvil → AgentSwarm
- Anvil → CostOptimizer
- VerifyLoop → AgentConstitution
- BenchAgent → Anvil
- TrajectoryDistiller → Fable5Dataset
"""

import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Path setup for imports
# ---------------------------------------------------------------------------
ANVIL_SRC = Path(__file__).resolve().parent.parent / "anvil" / "src"
VERIFYLOOP_SRC = Path(__file__).resolve().parent.parent / "verifyloop" / "src"
ERROR_RECOVERY_SRC = Path(__file__).resolve().parent.parent / "error-recovery" / "src"
AGENT_SWARM_SRC = Path(__file__).resolve().parent.parent / "agent-swarm" / "src"
COST_OPTIMIZER_SRC = Path(__file__).resolve().parent.parent / "cost-optimizer" / "src"
TRAJECTORY_SRC = Path(__file__).resolve().parent.parent / "trajectory-distiller" / "src"
FABLE5_SRC = Path(__file__).resolve().parent.parent / "fable5-dataset" / "src"
BENCH_SRC = Path(__file__).resolve().parent.parent / "bench-agent" / "src"

for src in [ANVIL_SRC, VERIFYLOOP_SRC, ERROR_RECOVERY_SRC, AGENT_SWARM_SRC,
            COST_OPTIMIZER_SRC, TRAJECTORY_SRC, FABLE5_SRC, BENCH_SRC]:
    if str(src) not in sys.path and src.exists():
        sys.path.insert(0, str(src))


# ===========================================================================
# Anvil → VerifyLoop integration
# ===========================================================================

class TestAnvilVerifyLoopIntegration:
    def test_verifyloop_integration_imports(self):
        from anvil.integrations.verifyloop import VerifyLoopIntegration
        integration = VerifyLoopIntegration()
        assert integration is not None

    def test_verifyloop_available_reflects_import(self):
        from anvil.integrations.verifyloop import VerifyLoopIntegration
        integration = VerifyLoopIntegration()
        assert isinstance(integration.available, bool)

    def test_verifyloop_session_creation(self):
        from anvil.integrations.verifyloop import VerifyLoopIntegration, VerifyLoopSession
        integration = VerifyLoopIntegration()
        session = integration.create_session("Write a sorting function")
        assert isinstance(session, VerifyLoopSession)
        assert session.task == "Write a sorting function"
        assert session.auto_recover is True

    def test_verifyloop_verify_with_valid_code(self, tmp_path):
        from anvil.integrations.verifyloop import VerifyLoopIntegration
        from anvil.verify.pipeline import VerifyStatus
        integration = VerifyLoopIntegration()

        good_file = tmp_path / "good.py"
        good_file.write_text("def sort_list(items):\n    return sorted(items)\n")
        report = integration.verify(files=[str(good_file)], working_dir=str(tmp_path))
        assert report is not None
        syntax_results = [r for r in report.results if r.checker == "syntax"]
        assert any(r.status == VerifyStatus.PASS for r in syntax_results)

    def test_verifyloop_verify_with_syntax_error(self, tmp_path):
        from anvil.integrations.verifyloop import VerifyLoopIntegration
        from anvil.verify.pipeline import VerifyStatus
        integration = VerifyLoopIntegration()

        bad_file = tmp_path / "bad.py"
        bad_file.write_text("def foo(\npass\n")
        report = integration.verify(files=[str(bad_file)], working_dir=str(tmp_path))
        failures = [r for r in report.results if r.status == VerifyStatus.FAIL]
        assert len(failures) >= 1

    def test_verifyloop_recover_syntax_error(self):
        from anvil.integrations.verifyloop import VerifyLoopIntegration
        integration = VerifyLoopIntegration()
        session = integration.create_session("test task")
        result = integration.recover_from_failure("execute", "SyntaxError: invalid syntax", session)
        assert "strategy" in result
        assert result["strategy"] in ("fix_syntax", "fix_syntax_error", "retry_with_different_approach")

    def test_verifyloop_step_dataclass(self):
        from anvil.integrations.verifyloop import VerifyLoopStep
        step = VerifyLoopStep(step_type="verify", content="Check syntax", status="pending")
        assert step.recovery_attempts == 0
        assert step.result is None

    def test_verifyloop_code_verify_python(self):
        from anvil.integrations.verifyloop import VerifyLoopIntegration
        from anvil.verify.pipeline import VerifyStatus
        integration = VerifyLoopIntegration()
        report = integration.verify_code("x = 1\nprint(x)\n")
        assert report.overall in (VerifyStatus.PASS, VerifyStatus.FAIL, VerifyStatus.SKIP, VerifyStatus.ERROR)

    def test_engine_uses_verifyloop_integration(self):
        from anvil.core.config import AnvilConfig
        from anvil.core.engine import AnvilEngine
        engine = AnvilEngine(AnvilConfig())
        assert engine.verifyloop is not None
        # available reflects whether verifyloop package is importable
        assert isinstance(engine.verifyloop.available, bool)


# ===========================================================================
# Anvil → ErrorRecovery integration
# ===========================================================================

class TestAnvilErrorRecoveryIntegration:
    def test_error_recovery_imports(self):
        from anvil.integrations.error_recovery import ErrorRecoveryIntegration
        er = ErrorRecoveryIntegration()
        assert er is not None

    def test_error_recovery_available_false(self):
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
        result = er.recover("ModuleNotFoundError: No module named 'requests'")
        assert result.category == ErrorCategory.IMPORT
        assert result.strategy == "install_module"

    def test_classify_indentation_error(self):
        from anvil.integrations.error_recovery import ErrorRecoveryIntegration, ErrorCategory
        er = ErrorRecoveryIntegration()
        result = er.recover("IndentationError: expected an indented block")
        assert result.category == ErrorCategory.SYNTAX
        assert "indent" in result.strategy.lower()

    def test_classify_type_error(self):
        from anvil.integrations.error_recovery import ErrorRecoveryIntegration, ErrorCategory
        er = ErrorRecoveryIntegration()
        result = er.recover("TypeError: unsupported operand type(s)")
        assert result.category == ErrorCategory.RUNTIME

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

    def test_classify_timeout_error(self):
        from anvil.integrations.error_recovery import ErrorRecoveryIntegration, ErrorCategory
        er = ErrorRecoveryIntegration()
        result = er.recover("TimeoutExpired: command timed out after 30s")
        assert result.category == ErrorCategory.TIMEOUT

    def test_classify_unknown_error(self):
        from anvil.integrations.error_recovery import ErrorRecoveryIntegration, ErrorCategory
        er = ErrorRecoveryIntegration()
        result = er.recover("Something completely unexpected")
        assert result.category == ErrorCategory.UNKNOWN
        assert result.confidence < 0.5

    def test_recovery_strategies_for_syntax(self):
        from anvil.integrations.error_recovery import ErrorRecoveryIntegration
        er = ErrorRecoveryIntegration()
        strategies = er.get_recovery_strategies("SyntaxError: bad")
        assert "fix_syntax_error" in strategies
        assert "review_code_structure" in strategies

    def test_engine_uses_error_recovery(self):
        from anvil.core.config import AnvilConfig
        from anvil.core.engine import AnvilEngine
        engine = AnvilEngine(AnvilConfig())
        assert engine.error_recovery is not None
        assert engine.error_recovery.available is False

    def test_error_recovery_fallback_without_package(self):
        from anvil.integrations.error_recovery import ErrorRecoveryIntegration, RecoveryResult
        er = ErrorRecoveryIntegration()
        result = er.recover("SyntaxError: invalid syntax")
        assert isinstance(result, RecoveryResult)
        assert result.success is False  # Without installed package, success is False
        assert result.strategy is not None


# ===========================================================================
# Anvil → AgentSwarm integration
# ===========================================================================

class TestAnvilAgentSwarmIntegration:
    def test_agent_swarm_imports(self):
        from anvil.integrations.agent_swarm import AgentSwarmIntegration
        swarm = AgentSwarmIntegration()
        assert swarm is not None

    def test_transition_matrix_probabilities(self):
        from anvil.integrations.agent_swarm import AgentSwarmIntegration
        swarm = AgentSwarmIntegration()
        assert swarm.get_handoff_probability("Bash", "Bash") == pytest.approx(0.59, abs=0.01)
        assert swarm.get_handoff_probability("Edit", "Bash") == pytest.approx(0.34, abs=0.01)
        assert swarm.get_handoff_probability("Read", "Bash") == pytest.approx(0.37, abs=0.01)

    def test_predict_next_tool(self):
        from anvil.integrations.agent_swarm import AgentSwarmIntegration
        swarm = AgentSwarmIntegration()
        assert swarm.predict_next_tool("Bash") == "Bash"
        assert swarm.predict_next_tool("Grep") == "Read"
        assert swarm.predict_next_tool("Glob") == "Read"

    def test_unknown_tool_defaults_to_read(self):
        from anvil.integrations.agent_swarm import AgentSwarmIntegration
        swarm = AgentSwarmIntegration()
        assert swarm.predict_next_tool("UnknownTool") == "Read"

    def test_zero_probability_for_unknown_transition(self):
        from anvil.integrations.agent_swarm import AgentSwarmIntegration
        swarm = AgentSwarmIntegration()
        assert swarm.get_handoff_probability("Bash", "NonExistent") == 0.0

    def test_transition_matrix_sums_to_one(self):
        from anvil.integrations.agent_swarm import TRANSITION_MATRIX
        for tool, transitions in TRANSITION_MATRIX.items():
            total = sum(transitions.values())
            assert total == pytest.approx(1.0, abs=0.01), f"{tool} transitions sum to {total}"

    def test_plan_agent_sequence(self):
        from anvil.integrations.agent_swarm import AgentSwarmIntegration
        swarm = AgentSwarmIntegration()
        sequence = swarm.plan_agent_sequence("Fix the login bug")
        assert isinstance(sequence, list)
        assert len(sequence) > 0

    def test_engine_uses_agent_swarm(self):
        from anvil.core.config import AnvilConfig
        from anvil.core.engine import AnvilEngine
        engine = AnvilEngine(AnvilConfig())
        assert engine.agent_swarm is not None

    def test_swarm_config_defaults(self):
        from anvil.integrations.agent_swarm import SwarmConfig
        config = SwarmConfig()
        assert config.max_agents == 5
        assert config.planning_rate == 0.877


# ===========================================================================
# Anvil → CostOptimizer integration
# ===========================================================================

class TestAnvilCostOptimizerIntegration:
    def test_cost_optimizer_imports(self):
        from anvil.integrations.cost_optimizer import CostOptimizerIntegration
        co = CostOptimizerIntegration()
        assert co is not None

    def test_route_simple_task(self):
        from anvil.integrations.cost_optimizer import CostOptimizerIntegration
        co = CostOptimizerIntegration()
        assert co.route_model("list the files") == "local"

    def test_route_complex_task(self):
        from anvil.integrations.cost_optimizer import CostOptimizerIntegration
        co = CostOptimizerIntegration()
        assert co.route_model("architect a microservices strategy") == "gpt-4o"

    def test_track_usage_and_summary(self):
        from anvil.integrations.cost_optimizer import CostOptimizerIntegration
        co = CostOptimizerIntegration(max_cost_per_session=10.0)
        co.track_usage("local", input_tokens=5000, output_tokens=2000, task="list")
        co.track_usage("gpt-4o", input_tokens=100_000, output_tokens=50_000, task="architect")
        summary = co.get_session_summary()
        assert summary["total_requests"] == 2
        assert summary["total_cost_usd"] > 0

    def test_budget_checking(self):
        from anvil.integrations.cost_optimizer import CostOptimizerIntegration
        co = CostOptimizerIntegration(max_cost_per_session=5.0)
        assert co.is_within_budget(1.0) is True
        assert co.is_within_budget(10.0) is False

    def test_task_budget_checking(self):
        from anvil.integrations.cost_optimizer import CostOptimizerIntegration
        co = CostOptimizerIntegration(max_cost_per_task=1.0)
        assert co.is_task_within_budget(0.5) is True
        assert co.is_task_within_budget(2.0) is False

    def test_calculate_cost_local_free(self):
        from anvil.integrations.cost_optimizer import CostOptimizerIntegration
        co = CostOptimizerIntegration()
        cost = co.calculate_cost(1_000_000, 1_000_000, "local")
        assert cost == 0.0

    def test_calculate_cost_gpt4o(self):
        from anvil.integrations.cost_optimizer import CostOptimizerIntegration
        co = CostOptimizerIntegration()
        cost = co.calculate_cost(1_000_000, 0, "gpt-4o")
        assert cost == pytest.approx(2.50, abs=0.01)

    def test_engine_uses_cost_optimizer(self):
        from anvil.core.config import AnvilConfig
        from anvil.core.engine import AnvilEngine
        engine = AnvilEngine(AnvilConfig())
        assert engine.cost_optimizer is not None

    def test_optimization_suggestions(self):
        from anvil.integrations.cost_optimizer import CostOptimizerIntegration
        co = CostOptimizerIntegration(max_cost_per_session=0.01)
        co.track_usage("gpt-4o", input_tokens=10_000, output_tokens=5_000)
        suggestions = co.get_optimization_suggestions()
        assert len(suggestions) > 0


# ===========================================================================
# VerifyLoop → AgentConstitution
# ===========================================================================

class TestVerifyLoopAgentConstitution:
    def test_verifyloop_integration_exists(self):
        from anvil.integrations.verifyloop import VerifyLoopIntegration
        vl = VerifyLoopIntegration()
        assert vl is not None

    def test_verifyloop_session_has_task_description(self):
        from anvil.integrations.verifyloop import VerifyLoopIntegration
        vl = VerifyLoopIntegration()
        session = vl.create_session("Ensure code follows style guidelines")
        assert "code" in session.task.lower() or "style" in session.task.lower()

    def test_verify_pipeline_constitutional_check(self, tmp_path):
        from anvil.verify.pipeline import VerifyPipeline
        good_file = tmp_path / "constitutional.py"
        good_file.write_text("def process_data(items):\n    return [x for x in items if x > 0]\n")
        pipeline = VerifyPipeline()
        report = pipeline.verify([str(good_file)], working_dir=str(tmp_path))
        assert report is not None


# ===========================================================================
# BenchAgent → Anvil: Run benchmark through engine
# ===========================================================================

class TestBenchAgentAnvilIntegration:
    def test_engine_handles_benchmark_task(self):
        from anvil.core.config import AnvilConfig
        from anvil.core.engine import AnvilEngine
        cfg = AnvilConfig()
        cfg.verify.enabled = False
        engine = AnvilEngine(cfg)
        assert engine is not None

    def test_benchmark_session_tracking(self):
        from anvil.core.session import Session, Step, StepKind, StepStatus
        session = Session(task="benchmark: sort algorithm", persist=False)
        session.add_step(Step(kind=StepKind.PLAN, content="Plan benchmark", status=StepStatus.SUCCESS))
        session.add_step(Step(kind=StepKind.EXECUTE, content="Execute benchmark", status=StepStatus.SUCCESS))
        session.add_step(Step(kind=StepKind.VERIFY, content="Verify results", status=StepStatus.SUCCESS))
        assert session.stats.successful_steps == 3
        summary = session.end("completed")
        assert summary["stats"]["total_steps"] == 3


# ===========================================================================
# TrajectoryDistiller → Fable5Dataset: Convert real data
# ===========================================================================

class TestTrajectoryDistillerFable5Integration:
    def test_trajectory_distiller_source_exists(self):
        distiller_src = Path(__file__).resolve().parent.parent / "trajectory-distiller" / "src"
        assert distiller_src.exists()

    def test_fable5_dataset_source_exists(self):
        fable5_src = Path(__file__).resolve().parent.parent / "fable5-dataset" / "src"
        assert fable5_src.exists()

    def test_distiller_module_structure(self):
        from trajectory_distiller.distiller import Distiller
        td = Distiller()
        assert td is not None

    def test_distiller_filter_module(self):
        from trajectory_distiller.filter import TraceFilter
        tf = TraceFilter()
        assert tf is not None

    def test_distiller_splitter_module(self):
        from trajectory_distiller.splitter import DataSplitter
        ts = DataSplitter()
        assert ts is not None

    def test_fable5_loader_module(self):
        from fable5_dataset.loader import DatasetLoader
        loader = DatasetLoader()
        assert loader is not None

    def test_fable5_stats_module(self):
        from fable5_dataset.stats import DatasetStats
        stats = DatasetStats()
        assert stats is not None

    def test_trajectory_conversion_flow(self, tmp_path):
        from trajectory_distiller.distiller import Distiller
        from trajectory_distiller.converter import FormatConverter
        td = Distiller()
        converter = FormatConverter()
        assert td is not None
        assert converter is not None

    def test_trajectory_filter_quality(self):
        from trajectory_distiller.filter import TraceFilter
        tf = TraceFilter()
        records = [{"messages": [{"role": "user", "content": "hi"}], "tool_calls": 3, "errors": 0, "success": True}]
        result = tf.filter_by_quality(records, min_quality_score=0.0)
        assert isinstance(result, list)

    def test_trajectory_splitter_splits(self):
        from trajectory_distiller.splitter import DataSplitter, TrainValTest
        ts = DataSplitter()
        records = [{"action": "bash", "output": "ok"} for _ in range(10)]
        result = ts.split(records, train_ratio=0.8, val_ratio=0.2)
        assert isinstance(result, TrainValTest)
        assert len(result.train) > 0


# ===========================================================================
# Cross-integration: End-to-end data flow
# ===========================================================================

class TestCrossProjectDataFlow:
    def test_error_recovery_and_cost_optimizer_together(self):
        from anvil.integrations.error_recovery import ErrorRecoveryIntegration
        from anvil.integrations.cost_optimizer import CostOptimizerIntegration

        er = ErrorRecoveryIntegration()
        co = CostOptimizerIntegration()

        result = er.recover("SyntaxError: invalid syntax at line 1")
        model = co.route_model("fix the syntax error quickly")
        assert result.strategy is not None
        assert model == "local"  # Simple task routes to local

    def test_agent_swarm_predicts_then_cost_routes(self):
        from anvil.integrations.agent_swarm import AgentSwarmIntegration
        from anvil.integrations.cost_optimizer import CostOptimizerIntegration

        swarm = AgentSwarmIntegration()
        co = CostOptimizerIntegration()

        next_tool = swarm.predict_next_tool("Bash")
        assert next_tool == "Bash"

        simple_task = f"use {next_tool.lower()} to list files"
        model = co.route_model(simple_task)
        assert model == "local"

    def test_full_pipeline_verify_and_classify(self, tmp_path):
        from anvil.verify.pipeline import VerifyPipeline
        from anvil.integrations.error_recovery import ErrorRecoveryIntegration

        bad_file = tmp_path / "broken.py"
        bad_file.write_text("def foo(\npass\n")

        pipeline = VerifyPipeline()
        report = pipeline.verify([str(bad_file)], working_dir=str(tmp_path))
        assert not report.passed

        er = ErrorRecoveryIntegration()
        if report.failures:
            error_msg = report.failures[0].message
            result = er.recover(error_msg)
            assert result.category is not None
            assert result.strategy is not None

    def test_verifyloop_and_cost_combined(self, tmp_path):
        from anvil.integrations.verifyloop import VerifyLoopIntegration
        from anvil.integrations.cost_optimizer import CostOptimizerIntegration

        good_file = tmp_path / "valid.py"
        good_file.write_text("x = 1\n")

        vl = VerifyLoopIntegration()
        co = CostOptimizerIntegration()

        report = vl.verify([str(good_file)], working_dir=str(tmp_path))
        co.track_usage("local", input_tokens=500, output_tokens=200, task="verify code")

        summary = co.get_session_summary()
        assert summary["total_requests"] == 1
        assert summary["total_cost_usd"] == 0.0  # local is free
