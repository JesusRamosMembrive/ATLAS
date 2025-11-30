"""
File Watcher Hook for Audit Trail

Integrates the file watcher system with audit trail to automatically
capture file changes and generate diff events.

Usage:
    from code_map.audit.file_watcher_hook import AuditFileWatcher

    # Start watching with audit integration
    watcher = AuditFileWatcher(
        run_id=123,
        root_path="/path/to/project",
        actor="agent"
    )
    watcher.start()

    # Stop watching
    watcher.stop()
"""

from __future__ import annotations

import difflib
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional, Set

from code_map.audit import append_event

logger = logging.getLogger(__name__)

# File extensions to track
TRACKED_EXTENSIONS = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".html",
    ".css",
    ".scss",
    ".json",
    ".md",
    ".yaml",
    ".yml",
    ".toml",
    ".sh",
    ".bash",
    ".sql",
}

# Directories to exclude
EXCLUDED_DIRS = {
    "__pycache__",
    ".git",
    ".hg",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".svn",
    ".tox",
    ".venv",
    "env",
    "node_modules",
    "venv",
    "dist",
    "build",
    ".next",
    ".nuxt",
}


class AuditFileWatcher:
    """
    File watcher that automatically generates audit events for file changes.

    Monitors a directory tree and creates diff events whenever files are
    created, modified, or deleted.

    Features:
    - Automatic diff generation using git
    - Filtering by file extension
    - Exclusion of build/cache directories
    - Debouncing to avoid duplicate events
    - Integration with audit trail system
    """

    def __init__(
        self,
        run_id: int,
        root_path: str,
        actor: str = "agent",
        phase: Optional[str] = None,
        extensions: Optional[Set[str]] = None,
        exclude_dirs: Optional[Set[str]] = None,
    ):
        """
        Initialize the audit file watcher.

        Args:
            run_id: Audit run ID to attach events to
            root_path: Root directory to watch
            actor: Actor performing the changes (agent, human)
            phase: Current workflow phase (plan, apply, validate)
            extensions: File extensions to track (default: TRACKED_EXTENSIONS)
            exclude_dirs: Directories to exclude (default: EXCLUDED_DIRS)
        """
        self.run_id = run_id
        self.root_path = Path(root_path).resolve()
        self.actor = actor
        self.phase = phase
        self.extensions = extensions or TRACKED_EXTENSIONS
        self.exclude_dirs = exclude_dirs or EXCLUDED_DIRS

        # Track file contents for diff generation
        self._file_snapshots: Dict[str, str] = {}

        # Watchdog observer (lazy loaded)
        self._observer: Optional[Any] = None
        self._handler: Optional[Any] = None

        # Flag to track if watcher is running
        self._running = False

    def start(self) -> None:
        """Start watching for file changes."""
        if self._running:
            logger.warning("AuditFileWatcher already running")
            return

        try:
            from watchdog.observers import Observer
            from watchdog.events import FileSystemEventHandler, FileSystemEvent
        except ImportError:
            logger.error("watchdog not installed, file watching disabled")
            return

        # Create event handler
        class AuditEventHandler(FileSystemEventHandler):
            def __init__(self, watcher: AuditFileWatcher):
                self.watcher = watcher

            def on_created(self, event: FileSystemEvent) -> None:
                if not event.is_directory:
                    self.watcher._handle_file_created(event.src_path)

            def on_modified(self, event: FileSystemEvent) -> None:
                if not event.is_directory:
                    self.watcher._handle_file_modified(event.src_path)

            def on_deleted(self, event: FileSystemEvent) -> None:
                if not event.is_directory:
                    self.watcher._handle_file_deleted(event.src_path)

        self._handler = AuditEventHandler(self)
        self._observer = Observer()
        self._observer.schedule(self._handler, str(self.root_path), recursive=True)
        self._observer.start()
        self._running = True

        logger.info(
            f"AuditFileWatcher started for run {self.run_id} at {self.root_path}"
        )

    def stop(self) -> None:
        """Stop watching for file changes."""
        if not self._running:
            return

        if self._observer:
            self._observer.stop()
            self._observer.join()

        self._running = False
        logger.info(f"AuditFileWatcher stopped for run {self.run_id}")

    def _should_track(self, file_path: str) -> bool:
        """Check if file should be tracked based on extension and exclusions."""
        path = Path(file_path)

        # Check if in excluded directory
        try:
            rel_path = path.relative_to(self.root_path)
            for part in rel_path.parts:
                if part in self.exclude_dirs:
                    return False
        except ValueError:
            # File is outside root_path
            return False

        # Check extension
        return path.suffix in self.extensions

    def _handle_file_created(self, file_path: str) -> None:
        """Handle file creation event."""
        if not self._should_track(file_path):
            return

        try:
            path = Path(file_path)
            rel_path = path.relative_to(self.root_path)

            # Read new file content
            try:
                content = path.read_text(encoding="utf-8", errors="ignore")
                self._file_snapshots[str(rel_path)] = content
            except Exception as e:
                logger.warning(f"Failed to read created file {rel_path}: {e}")
                content = ""

            # Generate diff (from nothing to new content)
            diff = self._generate_creation_diff(str(rel_path), content)

            # Create audit event
            append_event(
                run_id=self.run_id,
                type="file_change",
                title=f"Created: {rel_path}",
                detail=diff,
                actor=self.actor,
                phase=self.phase,
                ref=str(rel_path),
                status="ok",
                payload={
                    "change_type": "create",
                    "file_path": str(rel_path),
                    "lines_added": len(content.splitlines()),
                },
            )

            logger.debug(f"Audit event created for new file: {rel_path}")

        except Exception as e:
            logger.error(f"Error handling file creation {file_path}: {e}")

    def _handle_file_modified(self, file_path: str) -> None:
        """Handle file modification event."""
        if not self._should_track(file_path):
            return

        try:
            path = Path(file_path)
            rel_path = path.relative_to(self.root_path)
            rel_path_str = str(rel_path)

            # Read new content
            try:
                new_content = path.read_text(encoding="utf-8", errors="ignore")
            except Exception as e:
                logger.warning(f"Failed to read modified file {rel_path}: {e}")
                return

            # Get old content from snapshot
            old_content = self._file_snapshots.get(rel_path_str, "")

            # Skip if content hasn't actually changed
            if old_content == new_content:
                return

            # Generate diff
            diff = self._generate_diff(str(rel_path), old_content, new_content)

            # Update snapshot
            self._file_snapshots[rel_path_str] = new_content

            # Calculate stats
            old_lines = old_content.splitlines()
            new_lines = new_content.splitlines()
            lines_added = len(new_lines) - len(old_lines)

            # Create audit event
            append_event(
                run_id=self.run_id,
                type="file_change",
                title=f"Modified: {rel_path}",
                detail=diff,
                actor=self.actor,
                phase=self.phase,
                ref=str(rel_path),
                status="ok",
                payload={
                    "change_type": "modify",
                    "file_path": str(rel_path),
                    "lines_added": max(0, lines_added),
                    "lines_removed": max(0, -lines_added),
                },
            )

            logger.debug(f"Audit event created for modified file: {rel_path}")

        except Exception as e:
            logger.error(f"Error handling file modification {file_path}: {e}")

    def _handle_file_deleted(self, file_path: str) -> None:
        """Handle file deletion event."""
        if not self._should_track(file_path):
            return

        try:
            path = Path(file_path)
            rel_path = path.relative_to(self.root_path)
            rel_path_str = str(rel_path)

            # Get old content from snapshot
            old_content = self._file_snapshots.pop(rel_path_str, "")

            # Generate deletion diff
            diff = self._generate_deletion_diff(str(rel_path), old_content)

            # Create audit event
            append_event(
                run_id=self.run_id,
                type="file_change",
                title=f"Deleted: {rel_path}",
                detail=diff,
                actor=self.actor,
                phase=self.phase,
                ref=str(rel_path),
                status="ok",
                payload={
                    "change_type": "delete",
                    "file_path": str(rel_path),
                    "lines_removed": (
                        len(old_content.splitlines()) if old_content else 0
                    ),
                },
            )

            logger.debug(f"Audit event created for deleted file: {rel_path}")

        except Exception as e:
            logger.error(f"Error handling file deletion {file_path}: {e}")

    def _generate_diff(self, file_path: str, old_content: str, new_content: str) -> str:
        """Generate unified diff between old and new content."""
        old_lines = old_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)

        diff_lines = difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=f"a/{file_path}",
            tofile=f"b/{file_path}",
            lineterm="",
        )

        diff = "".join(diff_lines)

        # Truncate if too long (max 5000 chars for detail field)
        if len(diff) > 5000:
            diff = diff[:5000] + "\n\n... (diff truncated)"

        return diff

    def _generate_creation_diff(self, file_path: str, content: str) -> str:
        """Generate diff for file creation."""
        return self._generate_diff(file_path, "", content)

    def _generate_deletion_diff(self, file_path: str, content: str) -> str:
        """Generate diff for file deletion."""
        return self._generate_diff(file_path, content, "")

    def snapshot_current_state(self) -> None:
        """
        Snapshot current state of all tracked files.

        Call this before starting to watch to establish a baseline.
        """
        logger.info(f"Snapshotting current state of {self.root_path}")

        for root, dirs, files in os.walk(self.root_path):
            # Filter out excluded directories
            dirs[:] = [d for d in dirs if d not in self.exclude_dirs]

            for file in files:
                file_path = Path(root) / file

                if not self._should_track(str(file_path)):
                    continue

                try:
                    rel_path = file_path.relative_to(self.root_path)
                    content = file_path.read_text(encoding="utf-8", errors="ignore")
                    self._file_snapshots[str(rel_path)] = content
                except Exception as e:
                    logger.warning(f"Failed to snapshot {file_path}: {e}")

        logger.info(f"Snapshotted {len(self._file_snapshots)} files")
