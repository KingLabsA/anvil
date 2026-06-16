"""Integrated debugging support for Anvil."""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


# ============================================================================
# Debug Models
# ============================================================================

@dataclass
class Breakpoint:
    """Breakpoint information."""
    id: str
    file_path: str
    line: int
    condition: Optional[str] = None
    enabled: bool = True
    hit_count: int = 0


@dataclass
class StackFrame:
    """Stack frame information."""
    frame_id: int
    function_name: str
    file_path: str
    line: int
    column: int
    locals: dict[str, Any] = field(default_factory=dict)


@dataclass
class Variable:
    """Variable information."""
    name: str
    value: Any
    type: str
    scope: str  # "local", "global"


@dataclass
class DebugSession:
    """Debug session information."""
    id: str
    file_path: str
    breakpoints: list[Breakpoint] = field(default_factory=list)
    stack_frames: list[StackFrame] = field(default_factory=list)
    variables: list[Variable] = field(default_factory=list)
    is_running: bool = False
    is_paused: bool = False
    output: list[str] = field(default_factory=list)


# ============================================================================
# Debug Adapter Protocol (DAP) Client
# ============================================================================

class DebugAdapter:
    """Debug adapter for integrated debugging."""
    
    def __init__(self):
        self.sessions: dict[str, DebugSession] = {}
        self.process: Optional[subprocess.Popen] = None
    
    def start_debug_session(self, file_path: str, session_id: str) -> DebugSession:
        """Start a new debug session."""
        session = DebugSession(
            id=session_id,
            file_path=file_path,
            is_running=True,
        )
        self.sessions[session_id] = session
        
        # Start Python debugger
        self.process = subprocess.Popen(
            [sys.executable, "-m", "debugpy", "--listen", "5678", file_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        
        return session
    
    def stop_debug_session(self, session_id: str) -> bool:
        """Stop a debug session."""
        if session_id not in self.sessions:
            return False
        
        session = self.sessions[session_id]
        session.is_running = False
        session.is_paused = False
        
        if self.process:
            self.process.terminate()
            self.process = None
        
        return True
    
    def add_breakpoint(self, session_id: str, file_path: str, line: int, condition: Optional[str] = None) -> Optional[Breakpoint]:
        """Add a breakpoint."""
        if session_id not in self.sessions:
            return None
        
        session = self.sessions[session_id]
        breakpoint_id = f"bp_{len(session.breakpoints) + 1}"
        
        breakpoint = Breakpoint(
            id=breakpoint_id,
            file_path=file_path,
            line=line,
            condition=condition,
        )
        
        session.breakpoints.append(breakpoint)
        return breakpoint
    
    def remove_breakpoint(self, session_id: str, breakpoint_id: str) -> bool:
        """Remove a breakpoint."""
        if session_id not in self.sessions:
            return False
        
        session = self.sessions[session_id]
        session.breakpoints = [bp for bp in session.breakpoints if bp.id != breakpoint_id]
        return True
    
    def get_stack_trace(self, session_id: str) -> list[StackFrame]:
        """Get current stack trace."""
        if session_id not in self.sessions:
            return []
        
        # TODO: Implement actual stack trace retrieval via DAP
        return self.sessions[session_id].stack_frames
    
    def get_variables(self, session_id: str, frame_id: int) -> list[Variable]:
        """Get variables for a stack frame."""
        if session_id not in self.sessions:
            return []
        
        # TODO: Implement actual variable retrieval via DAP
        return self.sessions[session_id].variables
    
    def continue_execution(self, session_id: str) -> bool:
        """Continue execution."""
        if session_id not in self.sessions:
            return False
        
        session = self.sessions[session_id]
        session.is_paused = False
        # TODO: Send continue command via DAP
        return True
    
    def step_over(self, session_id: str) -> bool:
        """Step over to next line."""
        if session_id not in self.sessions:
            return False
        
        session = self.sessions[session_id]
        # TODO: Send step over command via DAP
        return True
    
    def step_into(self, session_id: str) -> bool:
        """Step into function."""
        if session_id not in self.sessions:
            return False
        
        session = self.sessions[session_id]
        # TODO: Send step into command via DAP
        return True
    
    def step_out(self, session_id: str) -> bool:
        """Step out of function."""
        if session_id not in self.sessions:
            return False
        
        session = self.sessions[session_id]
        # TODO: Send step out command via DAP
        return True
    
    def get_output(self, session_id: str) -> list[str]:
        """Get debug output."""
        if session_id not in self.sessions:
            return []
        
        session = self.sessions[session_id]
        
        # Read output from process
        if self.process and self.process.stdout:
            try:
                line = self.process.stdout.readline()
                if line:
                    session.output.append(line.strip())
            except Exception:
                pass
        
        return session.output


# ============================================================================
# Error Analysis
# ============================================================================

class ErrorAnalyzer:
    """Analyzes errors and provides suggestions."""
    
    def analyze_error(self, error_message: str, file_path: str, line: int) -> dict[str, Any]:
        """Analyze an error and provide suggestions."""
        analysis = {
            "error_message": error_message,
            "file_path": file_path,
            "line": line,
            "error_type": self._classify_error(error_message),
            "suggestions": [],
            "related_docs": [],
        }
        
        # Add suggestions based on error type
        if "SyntaxError" in error_message:
            analysis["suggestions"].append("Check for missing colons, parentheses, or brackets")
            analysis["suggestions"].append("Verify indentation is consistent")
            analysis["related_docs"].append("https://docs.python.org/3/reference/lexical_analysis.html")
        
        elif "NameError" in error_message:
            analysis["suggestions"].append("Check if the variable is defined before use")
            analysis["suggestions"].append("Verify variable name spelling")
            analysis["suggestions"].append("Check if the variable is in the correct scope")
            analysis["related_docs"].append("https://docs.python.org/3/tutorial/errors.html")
        
        elif "TypeError" in error_message:
            analysis["suggestions"].append("Check function argument types")
            analysis["suggestions"].append("Verify you're not mixing incompatible types")
            analysis["related_docs"].append("https://docs.python.org/3/library/stdtypes.html")
        
        elif "ImportError" in error_message or "ModuleNotFoundError" in error_message:
            analysis["suggestions"].append("Check if the module is installed: pip install <module>")
            analysis["suggestions"].append("Verify the import path is correct")
            analysis["suggestions"].append("Check for circular imports")
            analysis["related_docs"].append("https://docs.python.org/3/tutorial/modules.html")
        
        elif "IndexError" in error_message:
            analysis["suggestions"].append("Check array/list bounds before accessing")
            analysis["suggestions"].append("Verify the index is within valid range")
            analysis["related_docs"].append("https://docs.python.org/3/tutorial/introduction.html#lists")
        
        elif "KeyError" in error_message:
            analysis["suggestions"].append("Check if the key exists in the dictionary")
            analysis["suggestions"].append("Use dict.get() with a default value")
            analysis["related_docs"].append("https://docs.python.org/3/tutorial/datastructures.html#dictionaries")
        
        elif "AttributeError" in error_message:
            analysis["suggestions"].append("Check if the object has the attribute")
            analysis["suggestions"].append("Verify the object type is correct")
            analysis["related_docs"].append("https://docs.python.org/3/tutorial/classes.html")
        
        elif "ValueError" in error_message:
            analysis["suggestions"].append("Check if the value is valid for the operation")
            analysis["suggestions"].append("Verify input data format")
            analysis["related_docs"].append("https://docs.python.org/3/library/exceptions.html")
        
        else:
            analysis["suggestions"].append("Check the Python documentation for this error type")
            analysis["suggestions"].append("Search for the error message online")
            analysis["related_docs"].append("https://docs.python.org/3/tutorial/errors.html")
        
        return analysis
    
    def _classify_error(self, error_message: str) -> str:
        """Classify the error type."""
        error_types = [
            "SyntaxError", "NameError", "TypeError", "ImportError",
            "ModuleNotFoundError", "IndexError", "KeyError", "AttributeError",
            "ValueError", "RuntimeError", "FileNotFoundError", "PermissionError",
        ]
        
        for error_type in error_types:
            if error_type in error_message:
                return error_type
        
        return "UnknownError"


# ============================================================================
# Global Instances
# ============================================================================

debug_adapter = DebugAdapter()
error_analyzer = ErrorAnalyzer()
