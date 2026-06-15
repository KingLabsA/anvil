"""Tests for session sharing functionality."""

import json
from pathlib import Path

import pytest

from anvil.core.session import Session, Step, StepKind, StepStatus, ToolCall


@pytest.fixture
def sample_session():
    """Create a sample session for testing."""
    session = Session(task="Test task", session_id="test-session-123", persist=False)
    
    # Add some steps
    step1 = Step(
        kind=StepKind.PLAN,
        content="Plan the implementation",
        status=StepStatus.SUCCESS,
        duration_ms=100.0,
    )
    session.add_step(step1)
    
    step2 = Step(
        kind=StepKind.EXECUTE,
        content="Write the code",
        status=StepStatus.SUCCESS,
        tool_calls=[
            ToolCall(
                tool="write",
                args={"path": "test.py", "content": "print('hello')"},
                result="File written",
                duration_ms=50.0,
            )
        ],
        duration_ms=150.0,
    )
    session.add_step(step2)
    
    step3 = Step(
        kind=StepKind.VERIFY,
        content="Verify the output",
        status=StepStatus.SUCCESS,
        duration_ms=80.0,
    )
    session.add_step(step3)
    
    session.end("completed")
    return session


class TestSessionExport:
    """Test session export functionality."""
    
    def test_export_returns_dict(self, sample_session):
        """Test that export returns a dictionary."""
        data = sample_session.export()
        assert isinstance(data, dict)
        assert "id" in data
        assert "task" in data
        assert "steps" in data
        assert "stats" in data
    
    def test_export_contains_all_fields(self, sample_session):
        """Test that export contains all necessary fields."""
        data = sample_session.export()
        assert data["id"] == "test-session-123"
        assert data["task"] == "Test task"
        assert len(data["steps"]) == 3
        assert data["stats"]["total_steps"] == 3
        assert data["stats"]["successful_steps"] == 3
    
    def test_export_steps_are_dicts(self, sample_session):
        """Test that steps are exported as dictionaries."""
        data = sample_session.export()
        for step in data["steps"]:
            assert isinstance(step, dict)
            assert "kind" in step
            assert "content" in step
            assert "status" in step
    
    def test_to_json_returns_string(self, sample_session):
        """Test that to_json returns a JSON string."""
        json_str = sample_session.to_json()
        assert isinstance(json_str, str)
        # Should be valid JSON
        data = json.loads(json_str)
        assert data["id"] == "test-session-123"
    
    def test_to_json_is_valid_json(self, sample_session):
        """Test that to_json produces valid JSON."""
        json_str = sample_session.to_json()
        # Should not raise
        data = json.loads(json_str)
        assert isinstance(data, dict)


class TestSessionImport:
    """Test session import functionality."""
    
    def test_from_dict_creates_session(self, sample_session):
        """Test that from_dict creates a Session object."""
        data = sample_session.export()
        imported = Session.from_dict(data)
        assert isinstance(imported, Session)
        assert imported.id == sample_session.id
        assert imported.task == sample_session.task
    
    def test_from_dict_restores_steps(self, sample_session):
        """Test that from_dict restores steps."""
        data = sample_session.export()
        imported = Session.from_dict(data)
        assert len(imported.steps) == len(sample_session.steps)
        for orig, imp in zip(sample_session.steps, imported.steps):
            assert orig.kind == imp.kind
            assert orig.content == imp.content
            assert orig.status == imp.status
    
    def test_from_dict_restores_tool_calls(self, sample_session):
        """Test that from_dict restores tool calls."""
        data = sample_session.export()
        imported = Session.from_dict(data)
        # Check that tool calls are restored
        step_with_tools = imported.steps[1]
        assert len(step_with_tools.tool_calls) == 1
        assert step_with_tools.tool_calls[0].tool == "write"
    
    def test_from_dict_restores_stats(self, sample_session):
        """Test that from_dict restores stats."""
        data = sample_session.export()
        imported = Session.from_dict(data)
        assert imported.stats.total_steps == sample_session.stats.total_steps
        assert imported.stats.successful_steps == sample_session.stats.successful_steps
    
    def test_from_json_creates_session(self, sample_session):
        """Test that from_json creates a Session object."""
        json_str = sample_session.to_json()
        imported = Session.from_json(json_str)
        assert isinstance(imported, Session)
        assert imported.id == sample_session.id
    
    def test_roundtrip_preserves_data(self, sample_session):
        """Test that export -> import preserves all data."""
        # Export
        data = sample_session.export()
        # Import
        imported = Session.from_dict(data)
        # Re-export
        data2 = imported.export()
        # Should be identical
        assert data["id"] == data2["id"]
        assert data["task"] == data2["task"]
        assert len(data["steps"]) == len(data2["steps"])
        assert data["stats"] == data2["stats"]


class TestShareableLinks:
    """Test shareable link functionality."""
    
    def test_to_shareable_link_format(self, sample_session):
        """Test that shareable link has correct format."""
        link = sample_session.to_shareable_link()
        assert link.startswith("anvil://")
        assert len(link) > 10
    
    def test_from_shareable_link_creates_session(self, sample_session):
        """Test that from_shareable_link creates a Session object."""
        link = sample_session.to_shareable_link()
        imported = Session.from_shareable_link(link)
        assert isinstance(imported, Session)
        assert imported.id == sample_session.id
        assert imported.task == sample_session.task
    
    def test_from_shareable_link_restores_steps(self, sample_session):
        """Test that from_shareable_link restores steps."""
        link = sample_session.to_shareable_link()
        imported = Session.from_shareable_link(link)
        assert len(imported.steps) == len(sample_session.steps)
    
    def test_from_shareable_link_invalid_format(self):
        """Test that from_shareable_link rejects invalid format."""
        with pytest.raises(ValueError, match="Invalid shareable link"):
            Session.from_shareable_link("invalid://link")
    
    def test_shareable_link_roundtrip(self, sample_session):
        """Test that shareable link roundtrip preserves data."""
        # Create link
        link = sample_session.to_shareable_link()
        # Import from link
        imported = Session.from_shareable_link(link)
        # Re-create link
        link2 = imported.to_shareable_link()
        # Should be identical
        assert link == link2
    
    def test_shareable_link_is_url_safe(self, sample_session):
        """Test that shareable link is URL-safe."""
        link = sample_session.to_shareable_link()
        # Should not contain characters that need URL encoding
        # (base64 urlsafe uses - and _ instead of + and /)
        assert "+" not in link
        assert "/" not in link[8:]  # Skip "anvil://" prefix
    
    def test_shareable_link_compact(self, sample_session):
        """Test that shareable link is reasonably compact."""
        link = sample_session.to_shareable_link()
        # Should be shorter than raw JSON
        json_str = sample_session.to_json()
        # Base64 encoding adds ~33% overhead, but should still be reasonable
        assert len(link) < len(json_str) * 2


class TestSessionList:
    """Test session listing functionality."""
    
    def test_list_sessions_empty(self, tmp_path, monkeypatch):
        """Test list_sessions when no sessions exist."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        sessions = Session.list_sessions()
        assert sessions == []
    
    def test_list_sessions_with_sessions(self, tmp_path, monkeypatch):
        """Test list_sessions returns saved sessions."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        
        # Create some session directories
        sessions_dir = tmp_path / ".anvil" / "sessions"
        sessions_dir.mkdir(parents=True)
        
        # Create a session
        session1 = Session(task="Task 1", session_id="session-1", persist=True)
        session1.end("completed")
        
        session2 = Session(task="Task 2", session_id="session-2", persist=True)
        session2.end("completed")
        
        # List sessions
        sessions = Session.list_sessions()
        assert len(sessions) == 2
        ids = [s["id"] for s in sessions]
        assert "session-1" in ids
        assert "session-2" in ids
    
    def test_list_sessions_sorted(self, tmp_path, monkeypatch):
        """Test that list_sessions returns sorted results."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path)
        
        sessions_dir = tmp_path / ".anvil" / "sessions"
        sessions_dir.mkdir(parents=True)
        
        # Create sessions in random order
        for sid in ["c", "a", "b"]:
            session = Session(task=f"Task {sid}", session_id=sid, persist=True)
            session.end("completed")
        
        # List sessions
        sessions = Session.list_sessions()
        ids = [s["id"] for s in sessions]
        assert ids == ["a", "b", "c"]
