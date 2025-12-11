"""Tests for file watcher audit hook (code_map/audit/file_watcher_hook.py)."""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from code_map.audit import create_run, list_events
from code_map.audit.file_watcher_hook import AuditFileWatcher

if TYPE_CHECKING:
    from code_map.audit import AuditRun


@pytest.fixture
def temp_root(tmp_path: Path) -> Path:
    """Create a temporary directory for tests."""
    return tmp_path


@pytest.fixture
def test_run(temp_root: Path) -> AuditRun:
    """Create a test audit run."""
    db_path = temp_root / "audit_test.db"
    os.environ["CODE_MAP_DB_PATH"] = str(db_path)

    run = create_run(
        name="Test File Watcher Run",
        root_path=str(temp_root),
        notes="Testing file watcher hook",
    )
    yield run

    # Cleanup
    if "CODE_MAP_DB_PATH" in os.environ:
        del os.environ["CODE_MAP_DB_PATH"]


class TestFileWatcherBasics:
    """Tests for basic file watcher functionality."""

    def test_file_watcher_start_stop(self, test_run: AuditRun, temp_root: Path):
        """Test starting and stopping the file watcher."""
        watcher = AuditFileWatcher(
            run_id=test_run.id, root_path=str(temp_root), actor="test"
        )

        # Should not be running initially
        assert not watcher._running

        # Start watching
        watcher.start()
        assert watcher._running

        # Stop watching
        watcher.stop()
        assert not watcher._running

    def test_snapshot_current_state(self, test_run: AuditRun, temp_root: Path):
        """Test snapshotting current file state."""
        # Create some test files
        (temp_root / "test1.py").write_text("def hello(): pass")
        (temp_root / "test2.js").write_text("function hello() {}")
        (temp_root / "ignored.pyc").write_text("binary")

        watcher = AuditFileWatcher(run_id=test_run.id, root_path=str(temp_root))

        watcher.snapshot_current_state()

        # Should have snapshots of tracked files only
        assert "test1.py" in watcher._file_snapshots
        assert "test2.js" in watcher._file_snapshots
        assert "ignored.pyc" not in watcher._file_snapshots

        # Content should match
        assert "def hello()" in watcher._file_snapshots["test1.py"]
        assert "function hello()" in watcher._file_snapshots["test2.js"]


class TestFileCreation:
    """Tests for file creation events."""

    def test_create_tracked_file(self, test_run: AuditRun, temp_root: Path):
        """Test creating a tracked file generates an event."""
        watcher = AuditFileWatcher(
            run_id=test_run.id, root_path=str(temp_root), phase="apply"
        )
        watcher.snapshot_current_state()
        watcher.start()

        try:
            # Create a new Python file
            test_file = temp_root / "new_file.py"
            test_file.write_text("def new_function():\n    return 42\n")

            # Give watcher time to detect change
            time.sleep(0.5)

            # Check events
            events = list_events(test_run.id, limit=10)
            file_events = [e for e in events if e.type == "file_change"]

            assert len(file_events) >= 1

            # Find the creation event
            creation_event = next(
                (e for e in file_events if "new_file.py" in e.title), None
            )
            assert creation_event is not None
            assert creation_event.phase == "apply"
            assert creation_event.payload["change_type"] == "create"
            assert creation_event.payload["lines_added"] >= 2

            # Should have diff in detail
            assert "def new_function()" in creation_event.detail

        finally:
            watcher.stop()

    def test_create_ignored_file(self, test_run: AuditRun, temp_root: Path):
        """Test creating an ignored file does not generate an event."""
        watcher = AuditFileWatcher(run_id=test_run.id, root_path=str(temp_root))
        watcher.start()

        try:
            # Create an ignored file type
            test_file = temp_root / "binary.pyc"
            test_file.write_text("binary content")

            time.sleep(0.5)

            events = list_events(test_run.id, limit=10)
            file_events = [e for e in events if "binary.pyc" in e.title]

            assert len(file_events) == 0

        finally:
            watcher.stop()


class TestFileModification:
    """Tests for file modification events."""

    def test_modify_tracked_file(self, test_run: AuditRun, temp_root: Path):
        """Test modifying a file generates a diff event."""
        # Create initial file
        test_file = temp_root / "existing.py"
        test_file.write_text("def old_function():\n    return 1\n")

        watcher = AuditFileWatcher(
            run_id=test_run.id, root_path=str(temp_root), phase="apply"
        )
        watcher.snapshot_current_state()
        watcher.start()

        try:
            # Modify the file
            test_file.write_text("def new_function():\n    return 2\n")

            time.sleep(0.5)

            events = list_events(test_run.id, limit=10)
            modify_events = [
                e for e in events if e.type == "file_change" and "Modified" in e.title
            ]

            assert len(modify_events) >= 1

            # Check the event has a proper diff
            modify_event = modify_events[0]
            assert "existing.py" in modify_event.title
            assert modify_event.payload["change_type"] == "modify"

            # Diff should show old and new
            diff = modify_event.detail
            assert "-def old_function()" in diff or "-    return 1" in diff
            assert "+def new_function()" in diff or "+    return 2" in diff

        finally:
            watcher.stop()

    def test_no_event_if_content_unchanged(self, test_run: AuditRun, temp_root: Path):
        """Test that no event is generated if content doesn't actually change."""
        test_file = temp_root / "unchanged.py"
        content = "def func(): pass\n"
        test_file.write_text(content)

        watcher = AuditFileWatcher(run_id=test_run.id, root_path=str(temp_root))
        watcher.snapshot_current_state()
        watcher.start()

        try:
            # "Modify" file with same content
            test_file.write_text(content)

            time.sleep(0.5)

            events = list_events(test_run.id, limit=10)
            # Should not have created a modify event
            modify_events = [
                e for e in events if "unchanged.py" in e.title and "Modified" in e.title
            ]
            assert len(modify_events) == 0

        finally:
            watcher.stop()


class TestFileDeletion:
    """Tests for file deletion events."""

    def test_delete_tracked_file(self, test_run: AuditRun, temp_root: Path):
        """Test deleting a file generates an event."""
        # Create file
        test_file = temp_root / "to_delete.py"
        original_content = "def to_be_removed():\n    pass\n"
        test_file.write_text(original_content)

        watcher = AuditFileWatcher(
            run_id=test_run.id, root_path=str(temp_root), phase="apply"
        )
        watcher.snapshot_current_state()
        watcher.start()

        try:
            # Delete the file
            test_file.unlink()

            time.sleep(0.5)

            events = list_events(test_run.id, limit=10)
            delete_events = [
                e for e in events if e.type == "file_change" and "Deleted" in e.title
            ]

            assert len(delete_events) >= 1

            delete_event = delete_events[0]
            assert "to_delete.py" in delete_event.title
            assert delete_event.payload["change_type"] == "delete"
            assert delete_event.payload["lines_removed"] >= 2

            # Diff should show deletions
            assert "-def to_be_removed()" in delete_event.detail

        finally:
            watcher.stop()


class TestExclusionFiltering:
    """Tests for directory and file exclusion."""

    def test_exclude_node_modules(self, test_run: AuditRun, temp_root: Path):
        """Test that node_modules is excluded."""
        node_modules = temp_root / "node_modules"
        node_modules.mkdir()

        test_file = node_modules / "package.js"
        test_file.write_text("module.exports = {}")

        watcher = AuditFileWatcher(run_id=test_run.id, root_path=str(temp_root))
        watcher.start()

        try:
            # Modify file in node_modules
            test_file.write_text("module.exports = {updated: true}")

            time.sleep(0.5)

            events = list_events(test_run.id, limit=10)
            node_events = [e for e in events if "node_modules" in e.title]

            # Should not have generated any events
            assert len(node_events) == 0

        finally:
            watcher.stop()

    def test_custom_exclusions(self, test_run: AuditRun, temp_root: Path):
        """Test custom directory exclusions."""
        custom_dir = temp_root / "custom_ignore"
        custom_dir.mkdir()

        watcher = AuditFileWatcher(
            run_id=test_run.id, root_path=str(temp_root), exclude_dirs={"custom_ignore"}
        )
        watcher.start()

        try:
            test_file = custom_dir / "test.py"
            test_file.write_text("ignored content")

            time.sleep(0.5)

            events = list_events(test_run.id, limit=10)
            custom_events = [e for e in events if "custom_ignore" in e.title]

            assert len(custom_events) == 0

        finally:
            watcher.stop()


class TestDiffGeneration:
    """Tests for diff generation."""

    def test_diff_truncation(self, test_run: AuditRun, temp_root: Path):
        """Test that very large diffs are truncated."""
        test_file = temp_root / "large.py"
        # Create file with many lines
        large_content = "\n".join([f"line_{i} = {i}" for i in range(200)])
        test_file.write_text(large_content)

        watcher = AuditFileWatcher(run_id=test_run.id, root_path=str(temp_root))
        watcher.snapshot_current_state()
        watcher.start()

        try:
            # Make large change
            new_content = "\n".join([f"modified_{i} = {i}" for i in range(200)])
            test_file.write_text(new_content)

            time.sleep(0.5)

            events = list_events(test_run.id, limit=10)
            modify_events = [
                e for e in events if e.type == "file_change" and "Modified" in e.title
            ]

            assert len(modify_events) >= 1

            # Detail should be truncated if too long
            detail = modify_events[0].detail
            if len(detail) > 5000:
                assert "truncated" in detail.lower()

        finally:
            watcher.stop()
