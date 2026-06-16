"""Backend API for Anvil - RESTful API endpoints."""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Depends, status, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field, EmailStr

from anvil.core.engine import AnvilEngine
from anvil.core.config import AnvilConfig
from anvil.verify.pipeline import VerifyPipeline
from anvil.api.auth import (
    UserCreate, UserLogin, Token, hash_password, verify_password,
    create_access_token, create_refresh_token, get_current_user,
    check_rate_limit, generate_api_key, TokenData
)
from anvil.api.database import db, DBUser, DBSession
from anvil.api.websocket import connection_manager, websocket_handler
from anvil.monitoring import get_metrics
from anvil.onboarding import onboarding_manager


# ============================================================================
# Models
# ============================================================================

class TaskRequest(BaseModel):
    """Request to run a task."""
    task: str = Field(..., description="Task description")
    model: str = Field(default="local", description="Model to use")
    max_iterations: int = Field(default=20, description="Maximum iterations")


class TaskResponse(BaseModel):
    """Response from running a task."""
    success: bool
    output: str
    error: str | None = None
    session_id: str
    duration_ms: float


class VerifyRequest(BaseModel):
    """Request to verify code."""
    code: str = Field(..., description="Code to verify")
    file_path: str = Field(..., description="File path")
    language: str = Field(default="python", description="Programming language")


class VerifyResponse(BaseModel):
    """Response from verifying code."""
    passed: bool
    failures: list[str]
    details: dict[str, Any] = Field(default_factory=dict)


class ExplainRequest(BaseModel):
    """Request to explain code."""
    code: str = Field(..., description="Code to explain")


class ExplainResponse(BaseModel):
    """Response from explaining code."""
    explanation: str


class RefactorRequest(BaseModel):
    """Request to refactor code."""
    code: str = Field(..., description="Code to refactor")
    suggestion: str = Field(..., description="Refactoring suggestion")


class RefactorResponse(BaseModel):
    """Response from refactoring code."""
    refactored_code: str
    changes: list[str] = Field(default_factory=list)


class FixRequest(BaseModel):
    """Request to fix errors."""
    code: str = Field(..., description="Code to fix")
    errors: list[dict[str, Any]] = Field(..., description="List of errors")


class FixResponse(BaseModel):
    """Response from fixing errors."""
    fixed_code: str
    fixes_applied: list[str] = Field(default_factory=list)


class GenerateTestsRequest(BaseModel):
    """Request to generate tests."""
    code: str = Field(..., description="Code to test")
    file_path: str = Field(..., description="File path")
    language: str = Field(default="python", description="Programming language")


class GenerateTestsResponse(BaseModel):
    """Response from generating tests."""
    tests: str
    test_file_path: str


class SessionInfo(BaseModel):
    """Session information."""
    id: str
    task: str
    success: bool
    created_at: str
    duration_ms: float


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
    timestamp: str
    uptime_seconds: float


# ============================================================================
# API Application
# ============================================================================

app = FastAPI(
    title="Anvil API",
    description="Backend API for Anvil - The Self-Verified Coding Agent",
    version="0.3.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure properly in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global state
start_time = datetime.now()


# ============================================================================
# Dependencies
# ============================================================================

def get_engine() -> AnvilEngine:
    """Get Anvil engine instance."""
    config = AnvilConfig()
    return AnvilEngine(config)


# ============================================================================
# Health & Status
# ============================================================================

@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    uptime = (datetime.now() - start_time).total_seconds()
    return HealthResponse(
        status="healthy",
        version="0.3.0",
        timestamp=datetime.now().isoformat(),
        uptime_seconds=uptime,
    )


@app.get("/api/status")
async def get_status():
    """Get API status."""
    return {
        "status": "operational",
        "version": "0.3.0",
        "endpoints": [
            "/api/health",
            "/api/auth/register",
            "/api/auth/login",
            "/api/auth/refresh",
            "/api/run",
            "/api/verify",
            "/api/explain",
            "/api/refactor",
            "/api/fix",
            "/api/generate-tests",
            "/api/sessions",
            "/api/metrics",
            "/ws",
        ],
    }


@app.get("/api/metrics")
async def get_prometheus_metrics():
    """Get Prometheus metrics."""
    from fastapi.responses import Response
    metrics_data, content_type = get_metrics()
    return Response(content=metrics_data, media_type=content_type)


# ============================================================================
# Onboarding
# ============================================================================

@app.get("/api/onboarding/tours")
async def list_onboarding_tours():
    """List all available onboarding tours."""
    tours = onboarding_manager.list_tours()
    return {
        "tours": [
            {
                "id": tour.id,
                "name": tour.name,
                "description": tour.description,
                "steps_count": len(tour.steps),
                "completed": onboarding_manager.is_tour_completed(tour.id),
            }
            for tour in tours
        ]
    }


@app.get("/api/onboarding/tours/{tour_id}")
async def get_onboarding_tour(tour_id: str):
    """Get a specific onboarding tour."""
    tour = onboarding_manager.get_tour(tour_id)
    if not tour:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tour {tour_id} not found",
        )
    
    return {
        "id": tour.id,
        "name": tour.name,
        "description": tour.description,
        "steps": [
            {
                "id": step.id,
                "title": step.title,
                "description": step.description,
                "action": step.action,
                "target": step.target,
                "content": step.content,
                "completed": step.completed,
                "skippable": step.skippable,
            }
            for step in tour.steps
        ],
        "completed": onboarding_manager.is_tour_completed(tour_id),
    }


@app.post("/api/onboarding/tours/{tour_id}/start")
async def start_onboarding_tour(tour_id: str):
    """Start an onboarding tour."""
    tour = onboarding_manager.start_tour(tour_id)
    if not tour:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tour {tour_id} not found",
        )
    
    step = tour.next_step()
    return {
        "tour_id": tour.id,
        "current_step": tour.current_step,
        "step": {
            "id": step.id,
            "title": step.title,
            "description": step.description,
            "action": step.action,
            "target": step.target,
            "content": step.content,
        } if step else None,
    }


@app.post("/api/onboarding/tours/{tour_id}/complete")
async def complete_onboarding_tour(tour_id: str):
    """Mark an onboarding tour as completed."""
    success = onboarding_manager.complete_tour(tour_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Tour {tour_id} not found",
        )
    
    return {"status": "completed", "tour_id": tour_id}


@app.get("/api/onboarding/status")
async def get_onboarding_status():
    """Get onboarding status for the current user."""
    return {
        "should_show_onboarding": onboarding_manager.should_show_onboarding(),
        "completed_tours": onboarding_manager.get_completed_tours(),
        "recommended_tour": onboarding_manager.get_recommended_tour().id if onboarding_manager.get_recommended_tour() else None,
    }


# ============================================================================
# Authentication
# ============================================================================

@app.post("/api/auth/register", response_model=Token)
async def register(user_data: UserCreate):
    """Register a new user."""
    # Check if user already exists
    if db.get_user_by_email(user_data.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )
    
    # Create user
    user_id = str(uuid.uuid4())
    hashed_password = hash_password(user_data.password)
    
    user = DBUser(
        id=user_id,
        email=user_data.email,
        username=user_data.username,
        hashed_password=hashed_password,
        created_at=datetime.now().isoformat(),
    )
    
    if not db.create_user(user):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user",
        )
    
    # Generate tokens
    access_token = create_access_token(data={"user_id": user_id, "email": user_data.email})
    refresh_token = create_refresh_token(data={"user_id": user_id, "email": user_data.email})
    
    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=86400,  # 24 hours
    )


@app.post("/api/auth/login", response_model=Token)
async def login(user_data: UserLogin):
    """Login and get access token."""
    # Get user
    user = db.get_user_by_email(user_data.email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    
    # Verify password
    if not verify_password(user_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    
    # Update last login
    db.update_user_last_login(user.id)
    
    # Generate tokens
    access_token = create_access_token(data={"user_id": user.id, "email": user.email})
    refresh_token = create_refresh_token(data={"user_id": user.id, "email": user.email})
    
    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=86400,  # 24 hours
    )


@app.post("/api/auth/refresh", response_model=Token)
async def refresh_token(refresh_token: str):
    """Refresh access token."""
    try:
        from anvil.api.auth import verify_token
        token_data = verify_token(refresh_token)
        
        # Generate new tokens
        new_access_token = create_access_token(data={"user_id": token_data.user_id, "email": token_data.email})
        new_refresh_token = create_refresh_token(data={"user_id": token_data.user_id, "email": token_data.email})
        
        return Token(
            access_token=new_access_token,
            refresh_token=new_refresh_token,
            expires_in=86400,  # 24 hours
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )


@app.get("/api/auth/me")
async def get_current_user_info(current_user: TokenData = Depends(get_current_user)):
    """Get current user information."""
    user = db.get_user_by_id(current_user.user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    
    return {
        "id": user.id,
        "email": user.email,
        "username": user.username,
        "is_active": user.is_active,
        "is_admin": user.is_admin,
        "created_at": user.created_at,
        "last_login": user.last_login,
    }


# ============================================================================
# WebSocket
# ============================================================================

@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str, username: str = "Anonymous"):
    """WebSocket endpoint for real-time collaboration."""
    await websocket_handler.handle_connection(websocket, user_id, username)


# ============================================================================
# Task Execution
# ============================================================================

@app.post("/api/run", response_model=TaskResponse)
async def run_task(
    request: TaskRequest,
    current_user: TokenData = Depends(check_rate_limit)
):
    """Run a coding task with Anvil."""
    try:
        engine = get_engine()
        
        # Update config
        engine.config.model.model = request.model
        
        # Run task
        start = datetime.now()
        result = engine.run(request.task, max_iterations=request.max_iterations)
        duration = (datetime.now() - start).total_seconds() * 1000
        
        # Store session in database
        session_id = str(uuid.uuid4())
        session = DBSession(
            id=session_id,
            user_id=current_user.user_id,
            task=request.task,
            success=result.success,
            created_at=datetime.now().isoformat(),
            duration_ms=duration,
            output=result.output,
            error=result.error,
        )
        db.create_session(session)
        
        return TaskResponse(
            success=result.success,
            output=result.output or "",
            error=result.error,
            session_id=session_id,
            duration_ms=duration,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to run task: {str(e)}",
        )


# ============================================================================
# Code Verification
# ============================================================================

@app.post("/api/verify", response_model=VerifyResponse)
async def verify_code(
    request: VerifyRequest,
    current_user: TokenData = Depends(check_rate_limit)
):
    """Verify code for syntax, lint, and type errors."""
    try:
        # Create temporary file
        temp_dir = Path("/tmp/anvil-verify")
        temp_dir.mkdir(exist_ok=True)
        temp_file = temp_dir / Path(request.file_path).name
        temp_file.write_text(request.code)
        
        # Run verification
        config = AnvilConfig()
        pipeline = VerifyPipeline(config.verify)
        report = pipeline.verify([str(temp_file)])
        
        # Clean up
        temp_file.unlink()
        
        return VerifyResponse(
            passed=report.passed,
            failures=[f.message for f in report.failures],
            details={
                "total_checks": len(report.results),
                "passed_checks": sum(1 for r in report.results if r.status.value == "pass"),
                "failed_checks": sum(1 for r in report.results if r.status.value == "fail"),
            },
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to verify code: {str(e)}",
        )


# ============================================================================
# Code Explanation
# ============================================================================

@app.post("/api/explain", response_model=ExplainResponse)
async def explain_code(
    request: ExplainRequest,
    current_user: TokenData = Depends(check_rate_limit)
):
    """Explain what code does."""
    try:
        engine = get_engine()
        
        # Create explanation task
        task = f"Explain what this code does in detail:\n\n```\n{request.code}\n```"
        
        result = engine.run(task, max_iterations=1)
        
        return ExplainResponse(
            explanation=result.output or "Unable to generate explanation",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to explain code: {str(e)}",
        )


# ============================================================================
# Code Refactoring
# ============================================================================

@app.post("/api/refactor", response_model=RefactorResponse)
async def refactor_code(
    request: RefactorRequest,
    current_user: TokenData = Depends(check_rate_limit)
):
    """Refactor code based on suggestion."""
    try:
        engine = get_engine()
        
        # Create refactoring task
        task = f"""Refactor this code according to the suggestion:

Suggestion: {request.suggestion}

Code:
```
{request.code}
```

Return only the refactored code, no explanations."""
        
        result = engine.run(task, max_iterations=3)
        
        # Extract refactored code from output
        refactored = result.output
        if "```" in refactored:
            # Extract code from markdown
            lines = refactored.split("\n")
            in_code = False
            code_lines = []
            for line in lines:
                if line.strip().startswith("```"):
                    in_code = not in_code
                elif in_code:
                    code_lines.append(line)
            refactored = "\n".join(code_lines)
        
        return RefactorResponse(
            refactored_code=refactored,
            changes=[request.suggestion],
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to refactor code: {str(e)}",
        )


# ============================================================================
# Error Fixing
# ============================================================================

@app.post("/api/fix", response_model=FixResponse)
async def fix_errors(
    request: FixRequest,
    current_user: TokenData = Depends(check_rate_limit)
):
    """Fix errors in code."""
    try:
        engine = get_engine()
        
        # Format errors
        errors_text = "\n".join([
            f"Line {e.get('line', '?')}: {e.get('message', 'Unknown error')}"
            for e in request.errors
        ])
        
        # Create fix task
        task = f"""Fix these errors in the code:

Errors:
{errors_text}

Code:
```
{request.code}
```

Return only the fixed code, no explanations."""
        
        result = engine.run(task, max_iterations=3)
        
        # Extract fixed code from output
        fixed = result.output
        if "```" in fixed:
            lines = fixed.split("\n")
            in_code = False
            code_lines = []
            for line in lines:
                if line.strip().startswith("```"):
                    in_code = not in_code
                elif in_code:
                    code_lines.append(line)
            fixed = "\n".join(code_lines)
        
        return FixResponse(
            fixed_code=fixed,
            fixes_applied=[f"Fixed {len(request.errors)} error(s)"],
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fix errors: {str(e)}",
        )


# ============================================================================
# Test Generation
# ============================================================================

@app.post("/api/generate-tests", response_model=GenerateTestsResponse)
async def generate_tests(
    request: GenerateTestsRequest,
    current_user: TokenData = Depends(check_rate_limit)
):
    """Generate tests for code."""
    try:
        engine = get_engine()
        
        # Create test generation task
        task = f"""Generate comprehensive tests for this code:

Code:
```
{request.code}
```

File: {request.file_path}
Language: {request.language}

Generate tests that cover:
- Happy path scenarios
- Edge cases
- Error conditions
- Boundary conditions

Return only the test code, no explanations."""
        
        result = engine.run(task, max_iterations=3)
        
        # Extract test code from output
        tests = result.output
        if "```" in tests:
            lines = tests.split("\n")
            in_code = False
            code_lines = []
            for line in lines:
                if line.strip().startswith("```"):
                    in_code = not in_code
                elif in_code:
                    code_lines.append(line)
            tests = "\n".join(code_lines)
        
        # Generate test file path
        test_file_path = request.file_path.replace(".py", "_test.py")
        
        return GenerateTestsResponse(
            tests=tests,
            test_file_path=test_file_path,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate tests: {str(e)}",
        )


# ============================================================================
# Session Management
# ============================================================================

@app.get("/api/sessions", response_model=list[SessionInfo])
async def list_sessions(current_user: TokenData = Depends(get_current_user)):
    """List all sessions for current user."""
    db_sessions = db.get_user_sessions(current_user.user_id)
    return [
        SessionInfo(
            id=s.id,
            task=s.task,
            success=s.success,
            created_at=s.created_at,
            duration_ms=s.duration_ms,
        )
        for s in db_sessions
    ]


@app.get("/api/sessions/{session_id}")
async def get_session(
    session_id: str,
    current_user: TokenData = Depends(get_current_user)
):
    """Get session details."""
    session = db.get_session(session_id)
    if not session or session.user_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )
    return {
        "id": session.id,
        "task": session.task,
        "success": session.success,
        "created_at": session.created_at,
        "duration_ms": session.duration_ms,
        "output": session.output,
        "error": session.error,
    }


@app.delete("/api/sessions/{session_id}")
async def delete_session(
    session_id: str,
    current_user: TokenData = Depends(get_current_user)
):
    """Delete a session."""
    if not db.delete_session(session_id, current_user.user_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session {session_id} not found",
        )
    return {"status": "deleted", "session_id": session_id}


# ============================================================================
# Main
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
