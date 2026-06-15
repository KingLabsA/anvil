"""Tests for the agent swarm orchestrator."""

import json
import tempfile

import numpy as np
import pytest

from agent_swarm import (
    AgentRole,
    EditorAgent,
    HandoffEvent,
    ReaderAgent,
    SwarmOrchestrator,
    SwarmResult,
    SwarmStatus,
    TransitionMatrix,
    create_agent,
)
from agent_swarm.models import AgentConfig


# ---------------------------------------------------------------------------
# TransitionMatrix tests
# ---------------------------------------------------------------------------


class TestTransitionMatrix:
    """Tests for the TransitionMatrix class."""

    def test_default_matrix_loads(self):
        tm = TransitionMatrix()
        assert len(tm.tools) == 7
        assert tm.matrix.shape == (7, 7)

    def test_rows_sum_to_one(self):
        tm = TransitionMatrix()
        for i, row in enumerate(tm.matrix):
            assert np.isclose(row.sum(), 1.0, atol=1e-6), f"Row {i} ({tm.tools[i]}) doesn't sum to 1.0"

    def test_known_transitions_fable5(self):
        """Verify the hardcoded Fable5 transition probabilities."""
        tm = TransitionMatrix()
        # Bash→Bash = 0.59
        assert np.isclose(tm.get_transition_prob("bash", "bash"), 0.59, atol=0.01)
        # Bash→Edit = 0.18
        assert np.isclose(tm.get_transition_prob("bash", "edit"), 0.18, atol=0.01)
        # Read→Bash = 0.37
        assert np.isclose(tm.get_transition_prob("read", "bash"), 0.37, atol=0.01)
        # Read→Edit = 0.22
        assert np.isclose(tm.get_transition_prob("read", "edit"), 0.22, atol=0.01)
        # Edit→Bash = 0.34
        assert np.isclose(tm.get_transition_prob("edit", "bash"), 0.34, atol=0.01)
        # Edit→Read = 0.28
        assert np.isclose(tm.get_transition_prob("edit", "read"), 0.28, atol=0.01)

    def test_next_tool_returns_sorted_predictions(self):
        tm = TransitionMatrix()
        predictions = tm.next_tool("bash", top_k=3)
        assert len(predictions) >= 2
        # After bash, the top prediction should be bash itself (0.59)
        assert predictions[0].name == "bash"
        assert predictions[0].confidence > 0.5

    def test_next_tool_unknown_tool(self):
        tm = TransitionMatrix()
        predictions = tm.next_tool("unknown_tool", top_k=3)
        # Should return uniform distribution
        assert len(predictions) > 0

    def test_get_handoff_probability(self):
        tm = TransitionMatrix()
        # Reader → Editor should be 0.35
        assert np.isclose(tm.get_handoff_probability("reader", "editor"), 0.35)
        # Editor → Verifier should be 0.30
        assert np.isclose(tm.get_handoff_probability("editor", "verifier"), 0.30)

    def test_get_all_handoff_probabilities(self):
        tm = TransitionMatrix()
        probs = tm.get_all_handoff_probabilities("planner")
        assert "reader" in probs
        assert "editor" in probs
        # Probabilities should sum to ~1.0
        total = sum(probs.values())
        assert np.isclose(total, 1.0, atol=1e-6)

    def test_get_handoff_pattern(self):
        tm = TransitionMatrix()
        pattern = tm.get_handoff_pattern("reader", "editor")
        assert len(pattern) >= 1
        # First tool in reader→editor should be "read"
        assert pattern[0].name == "read"

    def test_get_handoff_pattern_unknown(self):
        tm = TransitionMatrix()
        pattern = tm.get_handoff_pattern("reader", "bash")
        # Should return a default pattern based on role's primary tool
        assert len(pattern) >= 1

    def test_to_json_and_from_json(self):
        tm = TransitionMatrix()
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            tm.to_json(f.name)
            loaded = TransitionMatrix.from_json(f.name)
            assert loaded.tools == tm.tools
            assert np.allclose(loaded.matrix, tm.matrix)

    def test_from_traces(self, tmp_path):
        """Test building a transition matrix from trace data."""
        traces = [
            {"tool_calls": [{"name": "read"}, {"name": "edit"}, {"name": "bash"}]},
            {"tool_calls": [{"name": "read"}, {"name": "edit"}, {"name": "read"}]},
            {"tool_calls": [{"name": "bash"}, {"name": "bash"}, {"name": "edit"}]},
            {"tool_calls": [{"name": "edit"}, {"name": "bash"}, {"name": "edit"}]},
            {"tool_calls": [{"name": "read"}, {"name": "bash"}, {"name": "edit"}]},
        ]
        trace_file = tmp_path / "traces.jsonl"
        with open(trace_file, "w") as f:
            for trace in traces:
                f.write(json.dumps(trace) + "\n")

        tm = TransitionMatrix.from_traces(str(trace_file), min_occurrences=1)
        assert "read" in tm.tools
        assert "edit" in tm.tools
        assert "bash" in tm.tools
        # Rows should sum to 1
        for row in tm.matrix:
            assert np.isclose(row.sum(), 1.0, atol=1e-6)

    def test_custom_matrix_validation(self):
        """Test that invalid matrices are rejected."""
        bad_matrix = np.array([[0.5, 0.3], [0.2, 0.9]])  # Rows don't sum to 1
        with pytest.raises(ValueError, match="sums to"):
            TransitionMatrix(matrix=bad_matrix, tools=["a", "b"])


# ---------------------------------------------------------------------------
# Agent tests
# ---------------------------------------------------------------------------


class TestAgents:
    """Tests for agent creation and functionality."""

    def test_create_reader_agent(self):
        agent = create_agent("reader")
        assert agent.role == AgentRole.READER
        assert "read" in agent.tool_names()
        assert "grep" in agent.tool_names()

    def test_create_editor_agent(self):
        agent = create_agent("editor")
        assert agent.role == AgentRole.EDITOR
        assert "edit" in agent.tool_names()
        assert "write" in agent.tool_names()

    def test_create_bash_agent(self):
        agent = create_agent("bash")
        assert agent.role == AgentRole.BASH
        assert "bash" in agent.tool_names()

    def test_create_verifier_agent(self):
        agent = create_agent("verifier")
        assert agent.role == AgentRole.VERIFIER
        assert "bash" in agent.tool_names()
        assert "read" in agent.tool_names()

    def test_create_planner_agent(self):
        agent = create_agent("planner")
        assert agent.role == AgentRole.PLANNER
        assert "question" in agent.tool_names()

    def test_create_unknown_agent_raises(self):
        with pytest.raises(ValueError):
            create_agent("unknown_role")

    def test_agent_handoff_targets(self):
        reader = ReaderAgent()
        assert AgentRole.EDITOR in reader.can_handoff_to
        assert AgentRole.VERIFIER in reader.can_handoff_to

    def test_agent_can_handle(self):
        reader = ReaderAgent()
        assert reader.can_handle("read")
        assert reader.can_handle("grep")
        assert not reader.can_handle("edit")

    def test_agent_add_and_get_context(self):
        agent = ReaderAgent()
        from agent_swarm.agents import AgentMessage
        msg = AgentMessage(role="user", content="Test message")
        agent.add_message(msg)
        context = agent.get_context()
        assert len(context) == 1
        assert context[0].content == "Test message"

    def test_agent_clear_context(self):
        agent = ReaderAgent()
        from agent_swarm.agents import AgentMessage
        agent.add_message(AgentMessage(role="user", content="msg"))
        agent.clear_context()
        assert len(agent.get_context()) == 0

    def test_agent_to_dict(self):
        agent = ReaderAgent()
        d = agent.to_dict()
        assert d["role"] == "reader"
        assert "read" in d["tools"]
        assert d["system_prompt"] != ""

    def test_agent_execute(self):
        agent = ReaderAgent()
        result = agent.execute("Find the authentication module")
        assert result["role"] == "reader"
        assert result["task"] == "Find the authentication module"
        assert result["status"] == "completed"
        assert len(result["plan"]) >= 1
        assert result["plan"][0]["name"] == "read"
        assert result["recommended_handoff"] is not None

    def test_agent_execute_with_context(self):
        agent = EditorAgent()
        result = agent.execute("Fix the bug", context={"previous_findings": "Bug is in auth.py"})
        assert result["role"] == "editor"
        assert result["context"]["previous_findings"] == "Bug is in auth.py"
        assert result["context"]["executed_by"] == "editor"


# ---------------------------------------------------------------------------
# Orchestrator tests
# ---------------------------------------------------------------------------


class TestSwarmOrchestrator:
    """Tests for the SwarmOrchestrator class."""

    def test_create_orchestrator(self):
        orch = SwarmOrchestrator()
        assert orch.transition_matrix is not None
        assert len(orch.agents) == 0
        assert len(orch.tasks) == 0

    def test_spawn_agent(self):
        orch = SwarmOrchestrator()
        agent = orch.spawn_agent("reader")
        assert agent.role == AgentRole.READER
        assert "reader" in orch.agents

    def test_spawn_all_agents(self):
        orch = SwarmOrchestrator()
        orch._ensure_agents()
        assert len(orch.agents) == 5
        for role in AgentRole:
            assert role.value in orch.agents

    def test_coordinate_creates_task(self):
        orch = SwarmOrchestrator()
        task = orch.coordinate("Fix the login bug")
        assert task.id in orch.tasks
        assert task.status == SwarmStatus.RUNNING
        assert task.current_agent == "planner"

    def test_handoff_records(self):
        orch = SwarmOrchestrator()
        orch._ensure_agents()
        orch.coordinate("Test task")
        record = orch.handoff("planner", "reader", {"context": "test"})
        assert record.from_role == "planner"
        assert record.to_role == "reader"
        assert len(orch.handoff_log) == 1

    def test_handoff_includes_transition_data(self):
        orch = SwarmOrchestrator()
        orch._ensure_agents()
        orch.coordinate("Test task")
        record = orch.handoff("reader", "editor", {"task": "test"})
        assert "handoff_probability" in record.context
        assert record.context["handoff_probability"] > 0

    def test_handoff_invalid_role_raises(self):
        orch = SwarmOrchestrator()
        with pytest.raises(ValueError, match="Unknown"):
            orch.handoff("reader", "invalid_role", {})

    def test_predict_next_agent(self):
        orch = SwarmOrchestrator()
        # After bash, the next agent should likely not be bash
        next_agent = orch.predict_next_agent("bash", current_tool="bash")
        # The transition matrix says bash→bash=0.59, but handoff probabilities
        # favor moving to a different agent
        assert next_agent in [r.value for r in AgentRole]

    def test_predict_next_agent_without_tool(self):
        orch = SwarmOrchestrator()
        next_agent = orch.predict_next_agent("reader")
        # Reader handoff should prefer editor or verifier
        assert next_agent in [r.value for r in AgentRole]

    def test_run_returns_swarm_result(self):
        orch = SwarmOrchestrator()
        result = orch.run("Fix the authentication bug")
        assert isinstance(result, SwarmResult)
        assert result.status == "completed"
        assert result.total_handoffs >= 3  # At least planner→reader→editor→verifier
        assert result.final_output != ""

    def test_run_result_has_handoff_history(self):
        orch = SwarmOrchestrator()
        result = orch.run("Implement feature X")
        assert len(result.handoffs) >= 3
        # First handoff should be planner → reader
        assert result.handoffs[0].from_role == AgentRole.PLANNER
        assert result.handoffs[0].to_role == AgentRole.READER

    def test_run_result_has_agent_history(self):
        orch = SwarmOrchestrator()
        result = orch.run("Write tests for module Y")
        assert len(result.agent_history) >= 3
        agents_seen = {h["agent"] for h in result.agent_history}
        assert "planner" in agents_seen
        assert "reader" in agents_seen

    def test_get_status(self):
        orch = SwarmOrchestrator()
        orch.run("Test task")
        status = orch.get_status()
        assert "total_tasks" in status
        assert "active_agents" in status
        assert status["total_tasks"] == 1

    def test_get_status_specific_task(self):
        orch = SwarmOrchestrator()
        task = orch.coordinate("Specific task")
        status = orch.get_status(task.id)
        assert "task" in status
        assert status["task"]["id"] == task.id

    def test_visualize(self):
        orch = SwarmOrchestrator()
        orch._ensure_agents()
        viz = orch.visualize()
        assert "AgentSwarm Visualization" in viz
        assert "Active Agents:" in viz
        assert "Transition Matrix" in viz

    def test_save_and_load_state(self, tmp_path):
        orch = SwarmOrchestrator()
        orch.run("Test task for save/load")
        state_path = tmp_path / "swarm_state.json"
        orch.save_state(str(state_path))

        assert state_path.exists()

        loaded_orch = SwarmOrchestrator()
        loaded_orch.load_state(str(state_path))
        assert len(loaded_orch.agents) == 5
        assert len(loaded_orch.tasks) == 1
        assert len(loaded_orch.handoff_log) >= 1

    def test_max_handoffs_parameter(self):
        orch = SwarmOrchestrator(max_handoffs=5)
        assert orch.max_handoffs == 5

    def test_custom_transition_matrix(self):
        custom = TransitionMatrix()  # uses defaults
        orch = SwarmOrchestrator(transition_matrix=custom)
        assert orch.transition_matrix is custom


# ---------------------------------------------------------------------------
# Models tests
# ---------------------------------------------------------------------------


class TestModels:
    """Tests for Pydantic models."""

    def test_agent_config_for_role(self):
        config = AgentConfig.for_role("reader")
        assert config.role == "reader"
        assert len(config.tools) == 3
        assert config.tools[0].name == "read"

    def test_agent_config_all_roles(self):
        for role in AgentRole:
            config = AgentConfig.for_role(role.value)
            assert config.role.value == role.value
            assert len(config.tools) > 0

    def test_swarm_result_creation(self):
        result = SwarmResult(task_description="Test task")
        assert result.task_description == "Test task"
        assert result.status == "completed"
        assert result.total_handoffs == 0

    def test_swarm_result_success(self):
        result = SwarmResult(
            task_description="Test",
            status="completed",
            final_output="Done",
        )
        assert result.success is True

    def test_swarm_result_failure(self):
        result = SwarmResult(
            task_description="Test",
            status="failed",
            final_output="",
        )
        assert result.success is False

    def test_swarm_result_summary(self):
        result = SwarmResult(
            task_description="Fix the bug",
            status="completed",
            final_agent="verifier",
            total_handoffs=3,
        )
        summary = result.summary()
        assert "Fix the bug" in summary
        assert "completed" in summary
        assert "verifier" in summary

    def test_handoff_event(self):
        event = HandoffEvent(
            from_role=AgentRole.PLANNER,
            to_role=AgentRole.READER,
            context={"task": "test"},
            probability=0.25,
        )
        assert event.from_role == AgentRole.PLANNER
        assert event.to_role == AgentRole.READER
        assert event.probability == 0.25

    def test_agent_message(self):
        from agent_swarm.models import AgentMessage as AM
        msg = AM(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"
        assert msg.timestamp is not None


# ---------------------------------------------------------------------------
# Integration test
# ---------------------------------------------------------------------------


class TestIntegration:
    """End-to-end integration tests."""

    def test_full_swarm_pipeline(self):
        """Test a complete swarm run from task creation to result."""
        orch = SwarmOrchestrator()

        # 1. Spawn agents
        reader = orch.spawn_agent("reader")
        editor = orch.spawn_agent("editor")
        assert len(orch.agents) >= 2

        # 2. Coordinate a task
        task = orch.coordinate("Refactor the database module")
        assert task.status == SwarmStatus.RUNNING

        # 3. Run the swarm
        result = orch.run("Refactor the database module")
        assert result.status == "completed"
        assert result.total_handoffs >= 3

        # 4. Verify handoff pattern: planner → reader → editor → verifier
        handoff_roles = [(h.from_role.value, h.to_role.value) for h in result.handoffs]
        assert ("planner", "reader") in handoff_roles
        assert ("reader", "editor") in handoff_roles
        assert ("editor", "verifier") in handoff_roles

        # 5. Check transition matrix predictions
        next_agent = orch.predict_next_agent("reader", current_tool="read")
        assert next_agent in [r.value for r in AgentRole]

    def test_transition_matrix_predictions_are_consistent(self):
        """Verify that transition matrix predictions match hardcoded values."""
        tm = TransitionMatrix()

        # After read, the most likely next tools should match Fable5 data
        predictions = tm.next_tool("read", top_k=3)
        pred_names = [p.name for p in predictions]
        assert "bash" in pred_names  # Read→Bash = 0.37 (highest)
        assert "edit" in pred_names  # Read→Edit = 0.22

        # After bash, bash should be the top prediction (0.59)
        bash_preds = tm.next_tool("bash", top_k=1)
        assert bash_preds[0].name == "bash"
        assert bash_preds[0].confidence > 0.5

    def test_multiple_tasks(self):
        """Test coordinating and running multiple tasks."""
        orch = SwarmOrchestrator()
        result1 = orch.run("Task one")
        result2 = orch.run("Task two")
        assert result1.task_id != result2.task_id
        assert len(orch.tasks) == 2
