"""Tests for multi-file editing and debugging API."""

import pytest
from fastapi.testclient import TestClient
from pathlib import Path
import tempfile
import shutil

from anvil.api.server import app
from anvil.api.auth import create_access_token


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def auth_token():
    """Create auth token for testing."""
    return create_access_token(data={"user_id": "test-user", "email": "test@example.com"})


@pytest.fixture
def temp_dir():
    """Create temporary directory for testing."""
    temp_path = Path(tempfile.mkdtemp())
    yield temp_path
    shutil.rmtree(temp_path)


class TestMultiFileEdit:
    """Tests for multi-file editing API."""

    def test_multi_edit_create_files(self, client, auth_token, temp_dir):
        """Test creating multiple files."""
        file1 = temp_dir / "file1.py"
        file2 = temp_dir / "file2.py"
        
        response = client.post(
            "/api/multi-edit",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "edits": [
                    {
                        "path": str(file1),
                        "action": "create",
                        "content": "print('Hello from file 1')"
                    },
                    {
                        "path": str(file2),
                        "action": "create",
                        "content": "print('Hello from file 2')"
                    }
                ],
                "description": "Create two test files",
                "auto_verify": False
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["files_changed"]) == 2
        assert file1.exists()
        assert file2.exists()
        assert file1.read_text() == "print('Hello from file 1')"
        assert file2.read_text() == "print('Hello from file 2')"

    def test_multi_edit_update_files(self, client, auth_token, temp_dir):
        """Test updating multiple files."""
        file1 = temp_dir / "file1.py"
        file1.write_text("print('Original')")
        
        response = client.post(
            "/api/multi-edit",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "edits": [
                    {
                        "path": str(file1),
                        "action": "update",
                        "content": "print('Updated')"
                    }
                ],
                "description": "Update file",
                "auto_verify": False
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert file1.read_text() == "print('Updated')"

    def test_multi_edit_delete_files(self, client, auth_token, temp_dir):
        """Test deleting multiple files."""
        file1 = temp_dir / "file1.py"
        file1.write_text("print('To delete')")
        
        response = client.post(
            "/api/multi-edit",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "edits": [
                    {
                        "path": str(file1),
                        "action": "delete"
                    }
                ],
                "description": "Delete file",
                "auto_verify": False
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert not file1.exists()

    def test_multi_edit_mixed_operations(self, client, auth_token, temp_dir):
        """Test mixed create, update, and delete operations."""
        file1 = temp_dir / "file1.py"
        file2 = temp_dir / "file2.py"
        file3 = temp_dir / "file3.py"
        
        file1.write_text("print('Original')")
        file3.write_text("print('To delete')")
        
        response = client.post(
            "/api/multi-edit",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "edits": [
                    {
                        "path": str(file1),
                        "action": "update",
                        "content": "print('Updated')"
                    },
                    {
                        "path": str(file2),
                        "action": "create",
                        "content": "print('New file')"
                    },
                    {
                        "path": str(file3),
                        "action": "delete"
                    }
                ],
                "description": "Mixed operations",
                "auto_verify": False
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["files_changed"]) == 3
        assert file1.read_text() == "print('Updated')"
        assert file2.exists()
        assert not file3.exists()

    def test_multi_edit_with_verification(self, client, auth_token, temp_dir):
        """Test multi-file editing with automatic verification."""
        file1 = temp_dir / "valid.py"
        
        response = client.post(
            "/api/multi-edit",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "edits": [
                    {
                        "path": str(file1),
                        "action": "create",
                        "content": "def valid_function():\n    return 42"
                    }
                ],
                "description": "Create valid Python file",
                "auto_verify": True
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["verification_results"] is not None

    def test_multi_edit_error_handling(self, client, auth_token, temp_dir):
        """Test error handling for invalid operations."""
        file1 = temp_dir / "nonexistent.py"
        
        response = client.post(
            "/api/multi-edit",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "edits": [
                    {
                        "path": str(file1),
                        "action": "update",
                        "content": "print('This will fail')"
                    }
                ],
                "description": "Update non-existent file",
                "auto_verify": False
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert len(data["errors"]) > 0

    def test_multi_edit_invalid_action(self, client, auth_token, temp_dir):
        """Test error handling for invalid action."""
        file1 = temp_dir / "file1.py"
        
        response = client.post(
            "/api/multi-edit",
            headers={"Authorization": f"Bearer {auth_token}"},
            json={
                "edits": [
                    {
                        "path": str(file1),
                        "action": "invalid_action",
                        "content": "print('test')"
                    }
                ],
                "description": "Invalid action",
                "auto_verify": False
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is False
        assert "Unknown action" in data["errors"][0]

    def test_multi_edit_requires_auth(self, client, temp_dir):
        """Test that multi-edit requires authentication."""
        file1 = temp_dir / "file1.py"
        
        response = client.post(
            "/api/multi-edit",
            json={
                "edits": [
                    {
                        "path": str(file1),
                        "action": "create",
                        "content": "print('test')"
                    }
                ],
                "description": "Test",
                "auto_verify": False
            }
        )
        
        assert response.status_code == 401


class TestDebugAPI:
    """Tests for debugging API."""

    def test_start_debug_session(self, client, auth_token, temp_dir):
        """Test starting a debug session."""
        file1 = temp_dir / "test.py"
        file1.write_text("x = 10\ny = 20\nprint(x + y)")
        
        response = client.post(
            "/api/debug/start",
            headers={"Authorization": f"Bearer {auth_token}"},
            params={"file": str(file1)}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data
        assert data["file"] == str(file1)
        assert data["current_line"] == 1
        assert data["breakpoints"] == []

    def test_start_debug_session_file_not_found(self, client, auth_token, temp_dir):
        """Test starting debug session with non-existent file."""
        file1 = temp_dir / "nonexistent.py"
        
        response = client.post(
            "/api/debug/start",
            headers={"Authorization": f"Bearer {auth_token}"},
            params={"file": str(file1)}
        )
        
        assert response.status_code == 404

    def test_add_breakpoint(self, client, auth_token, temp_dir):
        """Test adding a breakpoint."""
        file1 = temp_dir / "test.py"
        file1.write_text("x = 10\ny = 20\nprint(x + y)")
        
        # Start session
        start_response = client.post(
            "/api/debug/start",
            headers={"Authorization": f"Bearer {auth_token}"},
            params={"file": str(file1)}
        )
        session_id = start_response.json()["session_id"]
        
        # Add breakpoint
        response = client.post(
            "/api/debug/breakpoint",
            headers={"Authorization": f"Bearer {auth_token}"},
            params={"session_id": session_id},
            json={
                "file": str(file1),
                "line": 2,
                "condition": "x > 5",
                "enabled": True
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["breakpoint"]["line"] == 2

    def test_add_breakpoint_invalid_session(self, client, auth_token):
        """Test adding breakpoint to invalid session."""
        response = client.post(
            "/api/debug/breakpoint",
            headers={"Authorization": f"Bearer {auth_token}"},
            params={"session_id": "invalid-session"},
            json={
                "file": "test.py",
                "line": 1,
                "enabled": True
            }
        )
        
        assert response.status_code == 404

    def test_continue_execution(self, client, auth_token, temp_dir):
        """Test continuing execution."""
        file1 = temp_dir / "test.py"
        file1.write_text("x = 10\ny = 20\nprint(x + y)")
        
        # Start session
        start_response = client.post(
            "/api/debug/start",
            headers={"Authorization": f"Bearer {auth_token}"},
            params={"file": str(file1)}
        )
        session_id = start_response.json()["session_id"]
        
        # Continue execution
        response = client.post(
            "/api/debug/continue",
            headers={"Authorization": f"Bearer {auth_token}"},
            params={"session_id": session_id}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "current_line" in data

    def test_step_over(self, client, auth_token, temp_dir):
        """Test step over operation."""
        file1 = temp_dir / "test.py"
        file1.write_text("x = 10\ny = 20\nprint(x + y)")
        
        # Start session
        start_response = client.post(
            "/api/debug/start",
            headers={"Authorization": f"Bearer {auth_token}"},
            params={"file": str(file1)}
        )
        session_id = start_response.json()["session_id"]
        
        # Step over
        response = client.post(
            "/api/debug/step-over",
            headers={"Authorization": f"Bearer {auth_token}"},
            params={"session_id": session_id}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["current_line"] == 2

    def test_step_into(self, client, auth_token, temp_dir):
        """Test step into operation."""
        file1 = temp_dir / "test.py"
        file1.write_text("def func():\n    return 42\n\nresult = func()")
        
        # Start session
        start_response = client.post(
            "/api/debug/start",
            headers={"Authorization": f"Bearer {auth_token}"},
            params={"file": str(file1)}
        )
        session_id = start_response.json()["session_id"]
        
        # Step into
        response = client.post(
            "/api/debug/step-into",
            headers={"Authorization": f"Bearer {auth_token}"},
            params={"session_id": session_id}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_step_out(self, client, auth_token, temp_dir):
        """Test step out operation."""
        file1 = temp_dir / "test.py"
        file1.write_text("def func():\n    return 42\n\nresult = func()")
        
        # Start session
        start_response = client.post(
            "/api/debug/start",
            headers={"Authorization": f"Bearer {auth_token}"},
            params={"file": str(file1)}
        )
        session_id = start_response.json()["session_id"]
        
        # Step out
        response = client.post(
            "/api/debug/step-out",
            headers={"Authorization": f"Bearer {auth_token}"},
            params={"session_id": session_id}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_get_variables(self, client, auth_token, temp_dir):
        """Test getting variables."""
        file1 = temp_dir / "test.py"
        file1.write_text("x = 10\ny = 20\nprint(x + y)")
        
        # Start session
        start_response = client.post(
            "/api/debug/start",
            headers={"Authorization": f"Bearer {auth_token}"},
            params={"file": str(file1)}
        )
        session_id = start_response.json()["session_id"]
        
        # Get variables
        response = client.get(
            f"/api/debug/variables/{session_id}",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "variables" in data

    def test_get_call_stack(self, client, auth_token, temp_dir):
        """Test getting call stack."""
        file1 = temp_dir / "test.py"
        file1.write_text("x = 10\ny = 20\nprint(x + y)")
        
        # Start session
        start_response = client.post(
            "/api/debug/start",
            headers={"Authorization": f"Bearer {auth_token}"},
            params={"file": str(file1)}
        )
        session_id = start_response.json()["session_id"]
        
        # Get call stack
        response = client.get(
            f"/api/debug/call-stack/{session_id}",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "call_stack" in data

    def test_stop_debug_session(self, client, auth_token, temp_dir):
        """Test stopping a debug session."""
        file1 = temp_dir / "test.py"
        file1.write_text("x = 10\ny = 20\nprint(x + y)")
        
        # Start session
        start_response = client.post(
            "/api/debug/start",
            headers={"Authorization": f"Bearer {auth_token}"},
            params={"file": str(file1)}
        )
        session_id = start_response.json()["session_id"]
        
        # Stop session
        response = client.delete(
            f"/api/debug/{session_id}",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_stop_invalid_session(self, client, auth_token):
        """Test stopping invalid session."""
        response = client.delete(
            "/api/debug/invalid-session",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        
        assert response.status_code == 404

    def test_debug_requires_auth(self, client, temp_dir):
        """Test that debug endpoints require authentication."""
        file1 = temp_dir / "test.py"
        file1.write_text("x = 10")
        
        response = client.post(
            "/api/debug/start",
            params={"file": str(file1)}
        )
        
        assert response.status_code == 401
