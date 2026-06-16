"""Multi-file editing API for Anvil."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Optional
import os
from pathlib import Path

router = APIRouter()


class FileEdit(BaseModel):
    """Single file edit operation."""
    path: str
    action: str  # "create", "update", "delete"
    content: Optional[str] = None
    old_content: Optional[str] = None  # For undo


class MultiFileEditRequest(BaseModel):
    """Multi-file edit request."""
    edits: List[FileEdit]
    description: str
    auto_verify: bool = True


class MultiFileEditResponse(BaseModel):
    """Multi-file edit response."""
    success: bool
    files_changed: List[str]
    errors: List[str]
    verification_results: Optional[Dict] = None


class DebugBreakpoint(BaseModel):
    """Debug breakpoint."""
    file: str
    line: int
    condition: Optional[str] = None
    enabled: bool = True


class DebugSession(BaseModel):
    """Debug session."""
    session_id: str
    file: str
    breakpoints: List[DebugBreakpoint] = []
    current_line: Optional[int] = None
    variables: Dict = {}
    call_stack: List[Dict] = []


# In-memory storage for debug sessions (in production, use Redis)
debug_sessions: Dict[str, DebugSession] = {}


@router.post("/api/multi-edit", response_model=MultiFileEditResponse)
async def multi_file_edit(request: MultiFileEditRequest):
    """Edit multiple files at once."""
    files_changed = []
    errors = []
    
    for edit in request.edits:
        try:
            file_path = Path(edit.path)
            
            if edit.action == "create":
                if file_path.exists():
                    errors.append(f"File already exists: {edit.path}")
                    continue
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text(edit.content or "")
                files_changed.append(edit.path)
            
            elif edit.action == "update":
                if not file_path.exists():
                    errors.append(f"File does not exist: {edit.path}")
                    continue
                file_path.write_text(edit.content or "")
                files_changed.append(edit.path)
            
            elif edit.action == "delete":
                if not file_path.exists():
                    errors.append(f"File does not exist: {edit.path}")
                    continue
                file_path.unlink()
                files_changed.append(edit.path)
            
            else:
                errors.append(f"Unknown action: {edit.action}")
        
        except Exception as e:
            errors.append(f"Error editing {edit.path}: {str(e)}")
    
    # Auto-verify if requested
    verification_results = None
    if request.auto_verify and files_changed:
        try:
            # Run verification on changed files
            from anvil.verify.pipeline import VerifyPipeline
            pipeline = VerifyPipeline()
            verification_results = pipeline.verify_files(files_changed)
        except Exception as e:
            errors.append(f"Verification error: {str(e)}")
    
    return MultiFileEditResponse(
        success=len(errors) == 0,
        files_changed=files_changed,
        errors=errors,
        verification_results=verification_results
    )


@router.post("/api/debug/start", response_model=DebugSession)
async def start_debug_session(file: str):
    """Start a debug session for a file."""
    import uuid
    
    if not Path(file).exists():
        raise HTTPException(status_code=404, detail=f"File not found: {file}")
    
    session_id = str(uuid.uuid4())
    session = DebugSession(
        session_id=session_id,
        file=file,
        breakpoints=[],
        current_line=1,
        variables={},
        call_stack=[]
    )
    
    debug_sessions[session_id] = session
    return session


@router.post("/api/debug/breakpoint")
async def add_breakpoint(session_id: str, breakpoint: DebugBreakpoint):
    """Add a breakpoint to a debug session."""
    if session_id not in debug_sessions:
        raise HTTPException(status_code=404, detail="Debug session not found")
    
    session = debug_sessions[session_id]
    session.breakpoints.append(breakpoint)
    
    return {"success": True, "breakpoint": breakpoint}


@router.post("/api/debug/continue")
async def continue_debug(session_id: str):
    """Continue execution in a debug session."""
    if session_id not in debug_sessions:
        raise HTTPException(status_code=404, detail="Debug session not found")
    
    session = debug_sessions[session_id]
    
    # Simulate execution until next breakpoint
    # In a real implementation, this would use Python's debugger (pdb)
    # or a more sophisticated debugging framework
    
    # For now, just simulate moving to the next line
    if session.current_line:
        session.current_line += 1
    
    # Check if we hit a breakpoint
    for bp in session.breakpoints:
        if bp.enabled and bp.line == session.current_line:
            return {
                "success": True,
                "status": "paused",
                "current_line": session.current_line,
                "breakpoint": bp,
                "variables": session.variables,
                "call_stack": session.call_stack
            }
    
    return {
        "success": True,
        "status": "running",
        "current_line": session.current_line
    }


@router.post("/api/debug/step-over")
async def step_over(session_id: str):
    """Step over the current line."""
    if session_id not in debug_sessions:
        raise HTTPException(status_code=404, detail="Debug session not found")
    
    session = debug_sessions[session_id]
    if session.current_line:
        session.current_line += 1
    
    return {
        "success": True,
        "current_line": session.current_line,
        "variables": session.variables
    }


@router.post("/api/debug/step-into")
async def step_into(session_id: str):
    """Step into the current function."""
    if session_id not in debug_sessions:
        raise HTTPException(status_code=404, detail="Debug session not found")
    
    session = debug_sessions[session_id]
    
    # In a real implementation, this would step into function calls
    # For now, just simulate it
    if session.current_line:
        session.current_line += 1
        session.call_stack.append({
            "file": session.file,
            "line": session.current_line,
            "function": "unknown"
        })
    
    return {
        "success": True,
        "current_line": session.current_line,
        "variables": session.variables,
        "call_stack": session.call_stack
    }


@router.post("/api/debug/step-out")
async def step_out(session_id: str):
    """Step out of the current function."""
    if session_id not in debug_sessions:
        raise HTTPException(status_code=404, detail="Debug session not found")
    
    session = debug_sessions[session_id]
    
    # In a real implementation, this would step out of the current function
    # For now, just simulate it
    if session.call_stack:
        session.call_stack.pop()
        if session.call_stack:
            session.current_line = session.call_stack[-1]["line"]
    
    return {
        "success": True,
        "current_line": session.current_line,
        "variables": session.variables,
        "call_stack": session.call_stack
    }


@router.get("/api/debug/variables/{session_id}")
async def get_variables(session_id: str):
    """Get current variables in a debug session."""
    if session_id not in debug_sessions:
        raise HTTPException(status_code=404, detail="Debug session not found")
    
    session = debug_sessions[session_id]
    
    # In a real implementation, this would inspect the actual variables
    # For now, return simulated variables
    return {
        "success": True,
        "variables": session.variables or {
            "x": 10,
            "y": 20,
            "result": 30
        }
    }


@router.get("/api/debug/call-stack/{session_id}")
async def get_call_stack(session_id: str):
    """Get the call stack in a debug session."""
    if session_id not in debug_sessions:
        raise HTTPException(status_code=404, detail="Debug session not found")
    
    session = debug_sessions[session_id]
    
    return {
        "success": True,
        "call_stack": session.call_stack or [
            {"file": session.file, "line": session.current_line, "function": "main"}
        ]
    }


@router.delete("/api/debug/{session_id}")
async def stop_debug_session(session_id: str):
    """Stop a debug session."""
    if session_id not in debug_sessions:
        raise HTTPException(status_code=404, detail="Debug session not found")
    
    del debug_sessions[session_id]
    return {"success": True}
