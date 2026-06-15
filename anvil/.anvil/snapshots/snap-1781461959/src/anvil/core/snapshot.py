"""Snapshot and share management — undo/redo via git + session sharing."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Snapshot:
    name: str
    timestamp: float = field(default_factory=time.time)
    commit_hash: str = ""
    description: str = ""
    files_changed: list[str] = field(default_factory=list)
    backed_up: dict[str, str] = field(default_factory=dict)  # filepath -> backup_path

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Snapshot:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


class SnapshotManager:
    """Track file changes for undo/redo. Uses git if available, falls back to file copies."""

    def __init__(self, working_dir: str, state_dir: str | None = None):
        self.working_dir = Path(working_dir).resolve()
        self.state_dir = Path(state_dir) if state_dir else self.working_dir / ".anvil" / "snapshots"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._undo_stack: list[Snapshot] = []
        self._redo_stack: list[Snapshot] = []
        self._has_git = self._detect_git()
        self._load_history()

    def _detect_git(self) -> bool:
        """Check if the working directory is a git repo."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "--git-dir"],
                capture_output=True, text=True, cwd=str(self.working_dir),
            )
            return result.returncode == 0
        except (FileNotFoundError, OSError):
            return False

    def _run_git(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", *args],
            capture_output=True, text=True, cwd=str(self.working_dir),
        )

    def snapshot(self, description: str = "", files: list[str] | None = None) -> Snapshot:
        """Create a named snapshot of current state."""
        with self._lock:
            snap = Snapshot(name=f"snap-{int(time.time())}", description=description)
            snap.files_changed = files or []

            if self._has_git:
                self._git_snapshot(snap)
            else:
                self._file_copy_snapshot(snap, files)

            self._undo_stack.append(snap)
            self._redo_stack.clear()
            self._save_history()
            return snap

    def auto_snapshot(self, description: str = "") -> Snapshot:
        """Auto-snapshot before a tool execution."""
        return self.snapshot(description=f"auto: {description}" if description else "auto")

    def undo(self) -> Snapshot | None:
        """Revert to previous snapshot."""
        with self._lock:
            if not self._undo_stack:
                return None

            snap = self._undo_stack.pop()

            if self._has_git and snap.commit_hash:
                result = self._run_git("reset", "--hard", snap.commit_hash)
                if result.returncode != 0:
                    self._undo_stack.append(snap)
                    return None
            else:
                self._restore_file_copies(snap)

            self._redo_stack.append(snap)
            self._save_history()
            return snap

    def redo(self) -> Snapshot | None:
        """Re-apply a reverted change."""
        with self._lock:
            if not self._redo_stack:
                return None

            snap = self._redo_stack.pop()

            if self._has_git and snap.commit_hash:
                result = self._run_git("cherry-pick", snap.commit_hash)
                if result.returncode != 0:
                    self._run_git("cherry-pick", "--abort")
                    self._redo_stack.append(snap)
                    return None
            else:
                self._restore_file_copies(snap)

            self._undo_stack.append(snap)
            self._save_history()
            return snap

    def list_snapshots(self) -> list[Snapshot]:
        """Show all snapshots."""
        return list(self._undo_stack)

    def _git_snapshot(self, snap: Snapshot) -> None:
        """Create a git-based snapshot."""
        self._run_git("add", "-A")
        self._run_git("add", "-A", "--force")
        commit_msg = f"anvil: {snap.description or snap.name}"
        result = self._run_git("commit", "-m", commit_msg, "--allow-empty")
        if result.returncode == 0:
            rev_result = self._run_git("rev-parse", "HEAD")
            snap.commit_hash = rev_result.stdout.strip()
        else:
            rev_result = self._run_git("rev-parse", "HEAD")
            snap.commit_hash = rev_result.stdout.strip()

    def _file_copy_snapshot(self, snap: Snapshot, files: list[str] | None = None) -> None:
        """Create a file-copy-based snapshot as fallback."""
        snap_dir = self.state_dir / snap.name
        snap_dir.mkdir(parents=True, exist_ok=True)

        target_files = []
        if files:
            target_files = [Path(f) for f in files]
        else:
            target_files = [
                p for p in self.working_dir.rglob("*")
                if p.is_file() and not any(
                    seg in str(p) for seg in [".git", ".anvil", "node_modules", "__pycache__", ".venv"]
                )
            ]

        for src in target_files:
            if not src.is_file():
                continue
            try:
                rel = src.relative_to(self.working_dir)
                dst = snap_dir / rel
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
                snap.backed_up[str(rel)] = str(dst)
            except (ValueError, OSError):
                continue

        (snap_dir / ".manifest.json").write_text(json.dumps(snap.to_dict(), indent=2))

    def _restore_file_copies(self, snap: Snapshot) -> None:
        """Restore files from a file-copy snapshot."""
        snap_dir = self.state_dir / snap.name
        manifest_file = snap_dir / ".manifest.json"
        if not manifest_file.exists():
            return

        manifest_data = json.loads(manifest_file.read_text())
        backed_up = manifest_data.get("backed_up", {})

        for rel_path, backup_path in backed_up.items():
            src = Path(backup_path)
            dst = self.working_dir / rel_path
            if src.exists():
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)

    def _save_history(self) -> None:
        """Persist undo/redo stacks to disk."""
        history = {
            "undo_stack": [s.to_dict() for s in self._undo_stack],
            "redo_stack": [s.to_dict() for s in self._redo_stack],
        }
        (self.state_dir / "history.json").write_text(json.dumps(history, indent=2))

    def _load_history(self) -> None:
        """Load undo/redo stacks from disk."""
        history_file = self.state_dir / "history.json"
        if not history_file.exists():
            return
        try:
            data = json.loads(history_file.read_text())
            self._undo_stack = [Snapshot.from_dict(s) for s in data.get("undo_stack", [])]
            self._redo_stack = [Snapshot.from_dict(s) for s in data.get("redo_stack", [])]
        except (json.JSONDecodeError, KeyError):
            self._undo_stack = []
            self._redo_stack = []


@dataclass
class ShareLink:
    id: str
    session_id: str
    url: str
    created_at: float = field(default_factory=time.time)
    expires_at: float | None = None


class ShareManager:
    """Share session links — generates a local JSON export and a shareable URL."""

    def __init__(self, state_dir: str | None = None):
        self.state_dir = Path(state_dir) if state_dir else Path.home() / ".anvil" / "shares"
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.base_url = "https://anvil.sh/s"

    def share(self, session_id: str, session_data: dict | None = None) -> ShareLink:
        """Generate a shareable link for a session."""
        link_id = hashlib.sha256(f"{session_id}:{time.time()}".encode()).hexdigest()[:12]
        url = f"{self.base_url}/{link_id}"

        share_data = {
            "id": link_id,
            "session_id": session_id,
            "url": url,
            "created_at": time.time(),
            "session_data": session_data or {},
        }

        share_file = self.state_dir / f"{link_id}.json"
        share_file.write_text(json.dumps(share_data, indent=2, default=str))

        return ShareLink(
            id=link_id,
            session_id=session_id,
            url=url,
            created_at=share_data["created_at"],
        )

    def get_share(self, link_id: str) -> dict | None:
        """Retrieve shared session data."""
        share_file = self.state_dir / f"{link_id}.json"
        if not share_file.exists():
            return None
        try:
            return json.loads(share_file.read_text())
        except json.JSONDecodeError:
            return None

    def list_shares(self) -> list[ShareLink]:
        """List all shared links."""
        shares = []
        for share_file in self.state_dir.glob("*.json"):
            try:
                data = json.loads(share_file.read_text())
                shares.append(ShareLink(
                    id=data["id"],
                    session_id=data["session_id"],
                    url=data["url"],
                    created_at=data["created_at"],
                ))
            except (json.JSONDecodeError, KeyError):
                continue
        return sorted(shares, key=lambda s: s.created_at, reverse=True)

    def revoke(self, link_id: str) -> bool:
        """Revoke a shared link."""
        share_file = self.state_dir / f"{link_id}.json"
        if share_file.exists():
            share_file.unlink()
            return True
        return False

    def export_session(self, session_id: str, export_path: str | None = None) -> Path:
        """Export a session as a portable JSON file."""
        sessions_dir = Path.home() / ".anvil" / "sessions" / session_id
        if not sessions_dir.exists():
            raise FileNotFoundError(f"Session {session_id} not found")

        export_data: dict[str, Any] = {
            "session_id": session_id,
            "exported_at": time.time(),
            "anvil_version": "0.1.0",
            "steps": [],
        }

        summary_file = sessions_dir / "summary.json"
        if summary_file.exists():
            export_data["summary"] = json.loads(summary_file.read_text())

        for step_file in sorted(sessions_dir.glob("step_*.json")):
            try:
                export_data["steps"].append(json.loads(step_file.read_text()))
            except json.JSONDecodeError:
                continue

        out_path = Path(export_path) if export_path else self.state_dir / f"{session_id}_export.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(export_data, indent=2, default=str))
        return out_path
