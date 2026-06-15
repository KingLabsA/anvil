"""Snapshot manager for undo/redo operations."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Snapshot:
    """A snapshot of file state at a point in time."""

    id: str = ""
    timestamp: float = field(default_factory=time.time)
    description: str = ""
    files: dict[str, str] = field(default_factory=dict)
    tool_name: str = ""
    tool_args: dict = field(default_factory=dict)

    def hash_content(self) -> str:
        combined = "".join(sorted(self.files.values()))
        return hashlib.sha256(combined.encode()).hexdigest()[:12]


class SnapshotManager:
    """Create, list, and restore snapshots for undo/redo."""

    def __init__(self, project_root: str = ".", max_snapshots: int = 50) -> None:
        self.project_root = Path(project_root).resolve()
        self.max_snapshots = max_snapshots
        self._undo_stack: list[Snapshot] = []
        self._redo_stack: list[Snapshot] = []
        self._snapshot_id_counter = 0

    def create_snapshot(
        self,
        description: str = "",
        files: dict[str, str] | None = None,
        tool_name: str = "",
        tool_args: dict | None = None,
    ) -> Snapshot:
        """Create a new snapshot of file state."""
        self._snapshot_id_counter += 1
        snapshot_files = files if files is not None else {}
        snapshot = Snapshot(
            id=f"snap_{self._snapshot_id_counter:04d}",
            description=description,
            files=snapshot_files,
            tool_name=tool_name,
            tool_args=tool_args or {},
        )
        self._undo_stack.append(snapshot)
        self._redo_stack.clear()

        if len(self._undo_stack) > self.max_snapshots:
            self._undo_stack.pop(0)

        return snapshot

    def auto_snapshot(self, tool_name: str, tool_args: dict, files: dict[str, str] | None = None) -> Snapshot:
        """Auto-create a snapshot before a tool execution."""
        return self.create_snapshot(
            description=f"Auto-snapshot before {tool_name}",
            files=files or {},
            tool_name=tool_name,
            tool_args=tool_args,
        )

    def undo(self) -> Snapshot | None:
        """Pop the last snapshot from the undo stack and push to redo."""
        if not self._undo_stack:
            return None
        snapshot = self._undo_stack.pop()
        self._redo_stack.append(snapshot)
        return snapshot

    def redo(self) -> Snapshot | None:
        """Pop the last snapshot from the redo stack and push to undo."""
        if not self._redo_stack:
            return None
        snapshot = self._redo_stack.pop()
        self._undo_stack.append(snapshot)
        return snapshot

    def list_snapshots(self) -> list[Snapshot]:
        """Return all snapshots in the undo stack (most recent last)."""
        return list(self._undo_stack)

    def get_snapshot(self, snapshot_id: str) -> Snapshot | None:
        """Get a snapshot by ID."""
        for snapshot in self._undo_stack:
            if snapshot.id == snapshot_id:
                return snapshot
        for snapshot in self._redo_stack:
            if snapshot.id == snapshot_id:
                return snapshot
        return None

    def apply_snapshot(self, snapshot: Snapshot, project_root: Path | None = None) -> dict:
        """Apply a snapshot, restoring files. Returns a dict with restored file info."""
        root = project_root or self.project_root
        restored = {}
        for path, content in snapshot.files.items():
            file_path = root / path
            if content is not None:
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text(content, encoding="utf-8")
                restored[path] = {"status": "restored", "size": len(content)}
            else:
                if file_path.exists():
                    file_path.unlink()
                    restored[path] = {"status": "deleted"}
                else:
                    restored[path] = {"status": "already_absent"}
        return restored

    def can_undo(self) -> bool:
        return len(self._undo_stack) > 0

    def can_redo(self) -> bool:
        return len(self._redo_stack) > 0

    @property
    def undo_count(self) -> int:
        return len(self._undo_stack)

    @property
    def redo_count(self) -> int:
        return len(self._redo_stack)

    def share(self, snapshot: Snapshot | None = None) -> str:
        """Generate a shareable link/token for a snapshot."""
        target = snapshot or (self._undo_stack[-1] if self._undo_stack else None)
        if not target:
            return ""
        data = {
            "id": target.id,
            "description": target.description,
            "files": target.files,
            "timestamp": target.timestamp,
        }
        encoded = json.dumps(data, sort_keys=True)
        token = hashlib.sha256(encoded.encode()).hexdigest()[:16]
        return f"anvil://share/{token}"
