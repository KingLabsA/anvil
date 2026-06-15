"""Unit tests for StateSerializer."""

from pathlib import Path

import pytest

from agent_runtime.models import Message, SessionState, SessionStatus, ToolCall
from agent_runtime.state_serializer import StateSerializer


@pytest.fixture
def serializer(tmp_path: Path) -> StateSerializer:
    db_path = tmp_path / "test_state.db"
    return StateSerializer(db_path=db_path)


@pytest.fixture
def sample_state() -> SessionState:
    return SessionState(
        session_id="test-session-1",
        name="test-agent",
        model="fableforge-14b",
        system_prompt="You are a helpful assistant.",
        tools=["search", "calculator"],
        status=SessionStatus.CREATED,
        memory={"goal": "help users"},
        messages=[
            Message(role="system", content="You are a helpful assistant."),
            Message(role="user", content="Hello!"),
            Message(role="assistant", content="Hi there!"),
        ],
        tool_history=[
            ToolCall(name="search", arguments={"query": "python"}, result="found"),
        ],
    )


class TestStateSerializer:
    def test_save_and_load_session(self, serializer: StateSerializer, sample_state: SessionState):
        serializer.save_session(sample_state)
        loaded = serializer.load_session(sample_state.session_id)
        assert loaded is not None
        assert loaded.session_id == sample_state.session_id
        assert loaded.name == sample_state.name
        assert loaded.model == sample_state.model
        assert loaded.system_prompt == sample_state.system_prompt
        assert loaded.tools == sample_state.tools
        assert loaded.status == SessionStatus.CREATED
        assert loaded.memory == sample_state.memory

    def test_load_nonexistent_session(self, serializer: StateSerializer):
        result = serializer.load_session("nonexistent")
        assert result is None

    def test_update_session(self, serializer: StateSerializer, sample_state: SessionState):
        serializer.save_session(sample_state)
        sample_state.status = SessionStatus.RUNNING
        sample_state.name = "updated-agent"
        serializer.save_session(sample_state)

        loaded = serializer.load_session(sample_state.session_id)
        assert loaded is not None
        assert loaded.status == SessionStatus.RUNNING
        assert loaded.name == "updated-agent"

    def test_delete_session(self, serializer: StateSerializer, sample_state: SessionState):
        serializer.save_session(sample_state)
        assert serializer.delete_session(sample_state.session_id) is True
        assert serializer.load_session(sample_state.session_id) is None

    def test_delete_nonexistent_session(self, serializer: StateSerializer):
        assert serializer.delete_session("nonexistent") is False

    def test_list_sessions(self, serializer: StateSerializer):
        for i in range(3):
            state = SessionState(
                session_id=f"session-{i}",
                name=f"agent-{i}",
                model="test-model",
            )
            serializer.save_session(state)
        sessions = serializer.list_sessions()
        assert len(sessions) == 3

    def test_messages_round_trip(self, serializer: StateSerializer, sample_state: SessionState):
        serializer.save_session(sample_state)
        loaded = serializer.load_session(sample_state.session_id)
        assert loaded is not None
        assert len(loaded.messages) == 3
        assert loaded.messages[0].role == "system"
        assert loaded.messages[1].role == "user"
        assert loaded.messages[2].role == "assistant"
        assert loaded.messages[1].content == "Hello!"

    def test_tool_history_round_trip(self, serializer: StateSerializer, sample_state: SessionState):
        serializer.save_session(sample_state)
        loaded = serializer.load_session(sample_state.session_id)
        assert loaded is not None
        assert len(loaded.tool_history) == 1
        assert loaded.tool_history[0].name == "search"
        assert loaded.tool_history[0].arguments == {"query": "python"}
        assert loaded.tool_history[0].result == "found"


class TestCheckpoints:
    def test_create_checkpoint(self, serializer: StateSerializer, sample_state: SessionState):
        serializer.save_session(sample_state)
        cp = serializer.create_checkpoint(sample_state.session_id, label="test-cp")
        assert cp.session_id == sample_state.session_id
        assert cp.label == "test-cp"
        assert cp.checkpoint_id is not None

    def test_list_checkpoints(self, serializer: StateSerializer, sample_state: SessionState):
        serializer.save_session(sample_state)
        serializer.create_checkpoint(sample_state.session_id, label="cp1")
        serializer.create_checkpoint(sample_state.session_id, label="cp2")
        cps = serializer.list_checkpoints(sample_state.session_id)
        assert len(cps) == 2

    def test_resume_from_checkpoint(self, serializer: StateSerializer, sample_state: SessionState):
        serializer.save_session(sample_state)
        sample_state.status = SessionStatus.RUNNING
        serializer.save_session(sample_state)
        cp = serializer.create_checkpoint(sample_state.session_id, label="before-pause")

        sample_state.status = SessionStatus.PAUSED
        serializer.save_session(sample_state)

        resumed = serializer.resume_from_checkpoint(sample_state.session_id, cp.checkpoint_id)
        assert resumed.status == SessionStatus.PAUSED

    def test_resume_from_nonexistent_checkpoint(self, serializer: StateSerializer, sample_state: SessionState):
        serializer.save_session(sample_state)
        with pytest.raises(ValueError):
            serializer.resume_from_checkpoint(sample_state.session_id, "nonexistent")

    def test_prune_checkpoints(self, serializer: StateSerializer, sample_state: SessionState):
        serializer.save_session(sample_state)
        for i in range(15):
            serializer.create_checkpoint(sample_state.session_id, label=f"cp-{i}")
        pruned = serializer.prune_checkpoints(sample_state.session_id, keep_last=5)
        assert pruned == 10
        remaining = serializer.list_checkpoints(sample_state.session_id)
        assert len(remaining) == 5

    def test_prune_preserves_recent(self, serializer: StateSerializer, sample_state: SessionState):
        serializer.save_session(sample_state)
        import time
        serializer.create_checkpoint(sample_state.session_id, label="old-1")
        time.sleep(0.05)
        cp_keep = serializer.create_checkpoint(sample_state.session_id, label="keep-this")
        serializer.prune_checkpoints(sample_state.session_id, keep_last=1)
        remaining = serializer.list_checkpoints(sample_state.session_id)
        assert len(remaining) == 1
        assert remaining[0].checkpoint_id == cp_keep.checkpoint_id


class TestEdgeCases:
    def test_empty_messages(self, serializer: StateSerializer):
        state = SessionState(session_id="empty-msg", name="test", model="test")
        assert state.messages == []
        assert state.tool_history == []
        serializer.save_session(state)
        loaded = serializer.load_session(state.session_id)
        assert loaded is not None
        assert loaded.messages == []
        assert loaded.tool_history == []

    def test_complex_memory_values(self, serializer: StateSerializer):
        state = SessionState(
            session_id="complex-mem",
            name="test",
            model="test",
            memory={
                "nested": {"deep": {"value": 42}},
                "list": [1, 2, 3],
                "null": None,
                "bool": True,
            },
        )
        serializer.save_session(state)
        loaded = serializer.load_session(state.session_id)
        assert loaded is not None
        assert loaded.memory["nested"]["deep"]["value"] == 42
        assert loaded.memory["list"] == [1, 2, 3]

    def test_special_characters_in_prompt(self, serializer: StateSerializer):
        state = SessionState(
            session_id="special-chars",
            name="test",
            model="test",
            system_prompt='You are "helpful" & <safe>',
        )
        serializer.save_session(state)
        loaded = serializer.load_session(state.session_id)
        assert loaded is not None
        assert loaded.system_prompt == 'You are "helpful" & <safe>'
