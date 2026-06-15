"""Tests for Anvil undo/redo snapshot system."""



from anvil.snapshot.snapshot_manager import Snapshot, SnapshotManager


class TestSnapshot:
    def test_snapshot_creation(self):
        snap = Snapshot(id="snap_0001", description="test", files={"a.py": "content"})
        assert snap.id == "snap_0001"
        assert snap.description == "test"
        assert snap.files == {"a.py": "content"}

    def test_snapshot_defaults(self):
        snap = Snapshot()
        assert snap.id == ""
        assert snap.description == ""
        assert snap.files == {}
        assert snap.tool_name == ""
        assert snap.timestamp > 0

    def test_snapshot_hash_content(self):
        snap1 = Snapshot(id="1", files={"a.py": "hello", "b.py": "world"})
        snap2 = Snapshot(id="2", files={"a.py": "hello", "b.py": "world"})
        assert snap1.hash_content() == snap2.hash_content()

    def test_snapshot_hash_different_content(self):
        snap1 = Snapshot(id="1", files={"a.py": "hello"})
        snap2 = Snapshot(id="2", files={"a.py": "different"})
        assert snap1.hash_content() != snap2.hash_content()


class TestSnapshotManager:
    def test_create_snapshot(self):
        mgr = SnapshotManager()
        snap = mgr.create_snapshot(description="initial", files={"main.py": "print('hello')"})
        assert snap.id.startswith("snap_")
        assert snap.description == "initial"
        assert "main.py" in snap.files

    def test_create_snapshot_empty_files(self):
        mgr = SnapshotManager()
        snap = mgr.create_snapshot(description="empty")
        assert snap.files == {}

    def test_create_snapshot_with_tool_info(self):
        mgr = SnapshotManager()
        snap = mgr.create_snapshot(
            description="before edit",
            files={"app.py": "old code"},
            tool_name="edit",
            tool_args={"path": "app.py", "old_string": "old", "new_string": "new"},
        )
        assert snap.tool_name == "edit"
        assert snap.tool_args["path"] == "app.py"

    def test_list_snapshots(self):
        mgr = SnapshotManager()
        mgr.create_snapshot(description="snap1")
        mgr.create_snapshot(description="snap2")
        mgr.create_snapshot(description="snap3")
        snaps = mgr.list_snapshots()
        assert len(snaps) == 3

    def test_undo(self):
        mgr = SnapshotManager()
        mgr.create_snapshot(description="first")
        mgr.create_snapshot(description="second")
        snap = mgr.undo()
        assert snap is not None
        assert snap.description == "second"
        assert mgr.undo_count == 1

    def test_undo_empty_stack(self):
        mgr = SnapshotManager()
        result = mgr.undo()
        assert result is None

    def test_redo(self):
        mgr = SnapshotManager()
        mgr.create_snapshot(description="first")
        mgr.create_snapshot(description="second")
        mgr.undo()
        result = mgr.redo()
        assert result is not None
        assert result.description == "second"

    def test_redo_empty_stack(self):
        mgr = SnapshotManager()
        result = mgr.redo()
        assert result is None

    def test_undo_then_redo(self):
        mgr = SnapshotManager()
        mgr.create_snapshot(description="s1")
        mgr.create_snapshot(description="s2")
        mgr.undo()
        redo_snap = mgr.redo()
        assert redo_snap.description == "s2"

    def test_create_clears_redo_stack(self):
        mgr = SnapshotManager()
        mgr.create_snapshot(description="s1")
        mgr.create_snapshot(description="s2")
        mgr.undo()
        mgr.create_snapshot(description="s3")
        assert mgr.redo_count == 0

    def test_multiple_undo_levels(self):
        mgr = SnapshotManager()
        for i in range(5):
            mgr.create_snapshot(description=f"snap_{i}")
        for _ in range(3):
            mgr.undo()
        assert mgr.undo_count == 2
        assert mgr.redo_count == 3

    def test_can_undo_and_can_redo(self):
        mgr = SnapshotManager()
        assert mgr.can_undo() is False
        assert mgr.can_redo() is False
        mgr.create_snapshot(description="s1")
        assert mgr.can_undo() is True
        mgr.undo()
        assert mgr.can_redo() is True

    def test_get_snapshot_by_id(self):
        mgr = SnapshotManager()
        snap = mgr.create_snapshot(description="test_snap")
        found = mgr.get_snapshot(snap.id)
        assert found is not None
        assert found.id == snap.id

    def test_get_snapshot_nonexistent(self):
        mgr = SnapshotManager()
        result = mgr.get_snapshot("nonexistent")
        assert result is None

    def test_auto_snapshot(self):
        mgr = SnapshotManager()
        snap = mgr.auto_snapshot("edit", {"path": "app.py"}, {"app.py": "code"})
        assert snap.tool_name == "edit"
        assert "Auto-snapshot" in snap.description

    def test_apply_snapshot(self, tmp_path):
        mgr = SnapshotManager(project_root=str(tmp_path))
        snap = Snapshot(
            id="snap_restore",
            description="restore test",
            files={
                "app.py": "restored content",
                "sub/dir.py": "nested content",
            },
        )
        result = mgr.apply_snapshot(snap)
        assert "app.py" in result
        assert result["app.py"]["status"] == "restored"
        assert (tmp_path / "app.py").read_text() == "restored content"
        assert (tmp_path / "sub" / "dir.py").read_text() == "nested content"

    def test_apply_snapshot_delete_files(self, tmp_path):
        mgr = SnapshotManager(project_root=str(tmp_path))
        snap = Snapshot(
            id="snap_delete",
            description="delete test",
            files={"old.py": None},
        )
        old_file = tmp_path / "old.py"
        old_file.write_text("to be deleted")
        result = mgr.apply_snapshot(snap)
        assert "old.py" in result
        assert result["old.py"]["status"] == "deleted"
        assert not old_file.exists()

    def test_max_snapshots(self):
        mgr = SnapshotManager(max_snapshots=3)
        for i in range(5):
            mgr.create_snapshot(description=f"snap_{i}")
        assert mgr.undo_count <= 3

    def test_share_generates_link(self):
        mgr = SnapshotManager()
        snap = mgr.create_snapshot(description="share me", files={"a.py": "code"})
        link = mgr.share(snap)
        assert "anvil://share/" in link

    def test_share_empty_stack(self):
        mgr = SnapshotManager()
        link = mgr.share()
        assert link == ""

    def test_share_latest_by_default(self):
        mgr = SnapshotManager()
        mgr.create_snapshot(description="latest")
        link = mgr.share()
        assert "anvil://share/" in link
