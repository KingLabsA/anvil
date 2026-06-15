"""Tests for the Anvil web server."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from anvil.web.server import create_app


@pytest.fixture
def client():
    """Create a test client."""
    # Clear session store between tests
    from anvil.web.server import _sessions
    _sessions.clear()
    app = create_app()
    return TestClient(app)


class TestHealthEndpoint:
    def test_health_returns_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "version" in data


class TestIndexEndpoint:
    def test_index_returns_html(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "Anvil" in resp.text


class TestRunEndpoint:
    def test_run_task_success(self, client):
        """Test /run endpoint with mocked engine."""
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.output = "Task completed"
        mock_result.error = None
        mock_result.session = MagicMock()
        mock_result.session.steps = [MagicMock(), MagicMock()]

        with patch("anvil.web.server.AnvilEngine") as MockEngine:
            mock_engine = MagicMock()
            mock_engine.run.return_value = mock_result
            MockEngine.return_value = mock_engine

            resp = client.post("/run", json={
                "task": "Fix the bug",
                "model": "local",
                "max_iterations": 10,
                "verify": True,
            })

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["output"] == "Task completed"
        assert data["steps"] == 2
        assert "session_id" in data

    def test_run_task_failure(self, client):
        """Test /run endpoint with failed task."""
        mock_result = MagicMock()
        mock_result.success = False
        mock_result.output = ""
        mock_result.error = "Verification failed"
        mock_result.session = MagicMock()
        mock_result.session.steps = []

        with patch("anvil.web.server.AnvilEngine") as MockEngine:
            mock_engine = MagicMock()
            mock_engine.run.return_value = mock_result
            MockEngine.return_value = mock_engine

            resp = client.post("/run", json={"task": "Do something impossible"})

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False
        assert data["error"] == "Verification failed"

    def test_run_task_missing_task(self, client):
        """Test /run endpoint with missing task field."""
        resp = client.post("/run", json={"model": "local"})
        assert resp.status_code == 422  # Validation error


class TestSessionsEndpoint:
    def test_sessions_empty_initially(self, client):
        resp = client.get("/sessions")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_sessions_after_run(self, client):
        """Test that sessions are stored after /run."""
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.output = "Done"
        mock_result.error = None
        mock_result.session = MagicMock()
        mock_result.session.steps = []
        mock_result.session.task = "Test task"
        mock_result.session.stats.successful_steps = 1
        mock_result.session.created_at = "2026-06-15T12:00:00"

        with patch("anvil.web.server.AnvilEngine") as MockEngine:
            mock_engine = MagicMock()
            mock_engine.run.return_value = mock_result
            MockEngine.return_value = mock_engine

            client.post("/run", json={"task": "Test task"})

        resp = client.get("/sessions")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        assert data[-1]["task"] == "Test task"


class TestWebSocketEndpoint:
    def test_webstream_basic(self, client):
        """Test WebSocket /stream endpoint."""
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.output = "Streamed task done"
        mock_result.error = None
        mock_result.session = MagicMock()
        mock_result.session.steps = []

        with patch("anvil.web.server.AnvilEngine") as MockEngine:
            mock_engine = MagicMock()
            mock_engine.run.return_value = mock_result
            MockEngine.return_value = mock_engine

            with client.websocket_connect("/stream") as ws:
                ws.send_json({"task": "Stream test", "model": "local"})

                # Should receive status message
                msg1 = ws.receive_json()
                assert msg1["type"] == "status"

                # Should receive result
                msg2 = ws.receive_json()
                assert msg2["type"] == "result"
                assert msg2["success"] is True
                assert msg2["output"] == "Streamed task done"
