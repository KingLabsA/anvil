"""Checkpoint system — git-based undo/redo for all file changes."""

from __future__ import annotations

import subprocess
import time
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Checkpoint:
    id: str
    message: str
    files_changed: list[str]
    timestamp: float
    hash: str  # git commit hash
    parent: str | None = None


class CheckpointManager:
    """Git-based checkpoint/undo/redo system."""

    def __init__(self, workspace: str = "."):
        self.workspace = Path(workspace).resolve()
        self._checkpoints: list[Checkpoint] = []
        self._current_idx: int = -1

    def _run_git(self, *args: str) -> str:
        result = subprocess.run(
            ["git"] + list(args),
            cwd=self.workspace,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.stdout.strip()

    def is_git_repo(self) -> bool:
        try:
            self._run_git("rev-parse", "--is-inside-work-tree")
            return True
        except Exception:
            return False

    def init_if_needed(self):
        if not self.is_git_repo():
            self._run_git("init")
            self._run_git("config", "user.email", "anvil@fableforge.ai")
            self._run_git("config", "user.name", "Anvil")

    def create_checkpoint(self, message: str) -> Checkpoint:
        """Create a checkpoint from current state."""
        self.init_if_needed()

        # Stage all changes
        self._run_git("add", "-A")

        # Get changed files
        status = self._run_git("status", "--porcelain")
        files = [line[3:] for line in status.split("\n") if line.strip()]

        # Commit
        self._run_git("commit", "-m", f"[anvil] {message}", "--allow-empty")

        # Get hash
        commit_hash = self._run_git("rev-parse", "HEAD")

        parent = self._checkpoints[-1].hash if self._checkpoints else None
        checkpoint = Checkpoint(
            id=str(len(self._checkpoints)),
            message=message,
            files_changed=files,
            timestamp=time.time(),
            hash=commit_hash,
            parent=parent,
        )
        self._checkpoints.append(checkpoint)
        self._current_idx = len(self._checkpoints) - 1
        return checkpoint

    def undo(self) -> Checkpoint | None:
        """Undo to previous checkpoint."""
        if self._current_idx <= 0:
            return None
        self._current_idx -= 1
        target = self._checkpoints[self._current_idx]
        self._run_git("reset", "--hard", target.hash)
        return target

    def redo(self) -> Checkpoint | None:
        """Redo to next checkpoint."""
        if self._current_idx >= len(self._checkpoints) - 1:
            return None
        self._current_idx += 1
        target = self._checkpoints[self._current_idx]
        self._run_git("reset", "--hard", target.hash)
        return target

    def get_diff(self, checkpoint_id: str | None = None) -> str:
        """Get diff for a checkpoint or current changes."""
        if checkpoint_id:
            cp = next((c for c in self._checkpoints if c.id == checkpoint_id), None)
            if cp and cp.parent:
                return self._run_git("diff", cp.parent, cp.hash)
            return ""
        return self._run_git("diff", "HEAD")

    def get_file_diff(self, filepath: str) -> str:
        """Get diff for a specific file."""
        return self._run_git("diff", "--", filepath)

    def get_log(self, n: int = 20) -> list[dict]:
        """Get git log."""
        log = self._run_git("log", f"-{n}", "--pretty=format:%H|%s|%ai")
        entries = []
        for line in log.split("\n"):
            if "|" in line:
                parts = line.split("|", 2)
                entries.append({
                    "hash": parts[0],
                    "message": parts[1],
                    "date": parts[2] if len(parts) > 2 else "",
                })
        return entries

    def get_checkpoints(self) -> list[dict]:
        """Return list of Anvil checkpoints."""
        return [
            {
                "id": cp.id,
                "message": cp.message,
                "files_changed": cp.files_changed,
                "timestamp": cp.timestamp,
                "hash": cp.hash,
                "is_current": i == self._current_idx,
            }
            for i, cp in enumerate(self._checkpoints)
        ]

    def get_file_content(self, filepath: str, checkpoint_hash: str | None = None) -> str:
        """Get file content at a checkpoint."""
        ref = checkpoint_hash or "HEAD"
        try:
            return self._run_git("show", f"{ref}:{filepath}")
        except Exception:
            return ""

    def snapshot_files(self, files: list[str], message: str) -> Checkpoint:
        """Snapshot specific files."""
        self.init_if_needed()
        for f in files:
            self._run_git("add", f)
        self._run_git("commit", "-m", f"[anvil] {message}")
        commit_hash = self._run_git("rev-parse", "HEAD")
        parent = self._checkpoints[-1].hash if self._checkpoints else None
        checkpoint = Checkpoint(
            id=str(len(self._checkpoints)),
            message=message,
            files_changed=files,
            timestamp=time.time(),
            hash=commit_hash,
            parent=parent,
        )
        self._checkpoints.append(checkpoint)
        self._current_idx = len(self._checkpoints) - 1
        return checkpoint
