"""Tests for Anvil API."""

import pytest
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient
from anvil.api.server import app
from anvil.api.database import db, DBUser
from anvil.api.auth import hash_password
import uuid


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def test_user():
    """Create a test user."""
    user_id = str(uuid.uuid4())
    user = DBUser(
        id=user_id,
        email="test@example.com",
        username="testuser",
        hashed_password=hash_password("testpassword"),
        created_at="2026-01-01T00:00:00",
    )
    db.create_user(user)
    return user


@pytest.fixture
def auth_token(client, test_user):
    """Get authentication token."""
    response = client.post("/api/auth/login", json={
        "email": test_user.email,
        "password": "testpassword",
    })
    return response.json()["access_token"]


@pytest.fixture
def mock_engine():
    """Mock AnvilEngine to avoid loading models."""
    with patch('anvil.api.server.AnvilEngine') as MockEngine:
        mock_instance = Mock()
        
        # Mock run method
        mock_result = Mock()
        mock_result.success = True
        mock_result.output = "Task completed successfully"
        mock_result.error = None
        mock_instance.run.return_value = mock_result
        
        MockEngine.return_value = mock_instance
        yield mock_instance


class TestHealthEndpoints:
    """Test health and status endpoints."""
    
    def test_health_check(self, client):
        """Test health check endpoint."""
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data
        assert "timestamp" in data
        assert "uptime_seconds" in data
    
    def test_status(self, client):
        """Test status endpoint."""
        response = client.get("/api/status")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "operational"
        assert "endpoints" in data


class TestAuthentication:
    """Test authentication endpoints."""
    
    def test_register_success(self, client):
        """Test successful user registration."""
        import time
        unique_email = f"newuser_{int(time.time())}@example.com"
        response = client.post("/api/auth/register", json={
            "email": unique_email,
            "username": f"newuser_{int(time.time())}",
            "password": "newpassword",
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
    
    def test_register_duplicate_email(self, client, test_user):
        """Test registration with duplicate email."""
        response = client.post("/api/auth/register", json={
            "email": test_user.email,
            "username": "anotheruser",
            "password": "password",
        })
        assert response.status_code == 400
        assert "already registered" in response.json()["detail"]
    
    def test_login_success(self, client, test_user):
        """Test successful login."""
        response = client.post("/api/auth/login", json={
            "email": test_user.email,
            "password": "testpassword",
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
    
    def test_login_invalid_credentials(self, client, test_user):
        """Test login with invalid credentials."""
        response = client.post("/api/auth/login", json={
            "email": test_user.email,
            "password": "wrongpassword",
        })
        assert response.status_code == 401
        assert "Invalid credentials" in response.json()["detail"]
    
    def test_get_current_user(self, client, auth_token):
        """Test getting current user info."""
        response = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "email" in data
        assert "username" in data
    
    def test_get_current_user_unauthorized(self, client):
        """Test getting current user without auth."""
        response = client.get("/api/auth/me")
        assert response.status_code == 401


class TestTaskEndpoints:
    """Test task execution endpoints."""
    
    def test_run_task(self, client, auth_token, mock_engine):
        """Test running a task."""
        response = client.post(
            "/api/run",
            json={
                "task": "Create a hello world function",
                "model": "local",
                "max_iterations": 5,
            },
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "output" in data
        assert "session_id" in data
        assert "duration_ms" in data
        assert data["success"] is True
    
    def test_run_task_unauthorized(self, client):
        """Test running a task without auth."""
        response = client.post("/api/run", json={
            "task": "Test task",
        })
        assert response.status_code == 401


class TestVerifyEndpoints:
    """Test code verification endpoints."""
    
    def test_verify_code(self, client, auth_token):
        """Test verifying code."""
        response = client.post(
            "/api/verify",
            json={
                "code": "def hello():\n    print('Hello')\n",
                "file_path": "test.py",
                "language": "python",
            },
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "passed" in data
        assert "failures" in data
        assert "details" in data


class TestExplainEndpoints:
    """Test code explanation endpoints."""
    
    def test_explain_code(self, client, auth_token, mock_engine):
        """Test explaining code."""
        response = client.post(
            "/api/explain",
            json={
                "code": "def add(a, b):\n    return a + b\n",
            },
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "explanation" in data


class TestRefactorEndpoints:
    """Test code refactoring endpoints."""
    
    def test_refactor_code(self, client, auth_token, mock_engine):
        """Test refactoring code."""
        response = client.post(
            "/api/refactor",
            json={
                "code": "def add(a,b):\n    return a+b\n",
                "suggestion": "Add proper spacing and type hints",
            },
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "refactored_code" in data
        assert "changes" in data


class TestFixEndpoints:
    """Test error fixing endpoints."""
    
    def test_fix_errors(self, client, auth_token, mock_engine):
        """Test fixing errors."""
        response = client.post(
            "/api/fix",
            json={
                "code": "def hello()\n    print('Hello')\n",
                "errors": [
                    {"line": 1, "message": "Missing colon"},
                ],
            },
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "fixed_code" in data
        assert "fixes_applied" in data


class TestGenerateTestsEndpoints:
    """Test test generation endpoints."""
    
    def test_generate_tests(self, client, auth_token, mock_engine):
        """Test generating tests."""
        response = client.post(
            "/api/generate-tests",
            json={
                "code": "def add(a, b):\n    return a + b\n",
                "file_path": "math.py",
                "language": "python",
            },
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "tests" in data
        assert "test_file_path" in data


class TestSessionEndpoints:
    """Test session management endpoints."""
    
    def test_list_sessions(self, client, auth_token):
        """Test listing sessions."""
        response = client.get(
            "/api/sessions",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
    
    def test_get_session(self, client, auth_token, mock_engine):
        """Test getting a session."""
        # First create a session
        run_response = client.post(
            "/api/run",
            json={"task": "Test task"},
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        session_id = run_response.json()["session_id"]
        
        # Then get it
        response = client.get(
            f"/api/sessions/{session_id}",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == session_id
    
    def test_delete_session(self, client, auth_token, mock_engine):
        """Test deleting a session."""
        # First create a session
        run_response = client.post(
            "/api/run",
            json={"task": "Test task"},
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        session_id = run_response.json()["session_id"]
        
        # Then delete it
        response = client.delete(
            f"/api/sessions/{session_id}",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 200
        assert response.json()["status"] == "deleted"
    
    def test_get_nonexistent_session(self, client, auth_token):
        """Test getting a nonexistent session."""
        response = client.get(
            "/api/sessions/nonexistent",
            headers={"Authorization": f"Bearer {auth_token}"}
        )
        assert response.status_code == 404
