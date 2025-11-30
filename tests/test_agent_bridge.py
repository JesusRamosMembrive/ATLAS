"""Tests for agent audit bridge (.claude/hooks/audit_bridge.py)."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

# Add .claude/hooks to path
claude_hooks = Path(__file__).parent.parent / ".claude" / "hooks"
sys.path.insert(0, str(claude_hooks))

from code_map.audit import list_events, get_run  # noqa: E402

if TYPE_CHECKING:
    pass


# Import audit_bridge after path setup
import audit_bridge  # noqa: E402


@pytest.fixture
def temp_root(tmp_path: Path) -> Path:
    """Create a temporary directory for tests."""
    return tmp_path


@pytest.fixture
def test_db(temp_root: Path) -> Path:
    """Setup test database path."""
    db_path = temp_root / "audit_test.db"
    os.environ["CODE_MAP_DB_PATH"] = str(db_path)
    yield db_path
    if "CODE_MAP_DB_PATH" in os.environ:
        del os.environ["CODE_MAP_DB_PATH"]


class TestSessionManagement:
    """Tests for session start/end functions."""

    def test_start_audit_session(self, test_db: Path):
        """Test starting an audit session."""
        run_id = audit_bridge.start_audit_session(
            name="Test Session",
            notes="Testing audit bridge"
        )

        assert run_id is not None
        assert isinstance(run_id, int)

        # Verify run was created
        run = get_run(run_id)
        assert run.name == "Test Session"
        assert run.notes == "Testing audit bridge"
        assert run.closed_at is None

        # Verify session start event was created
        events = list_events(run_id, limit=10)
        assert len(events) >= 1
        assert events[0].type == "session"
        assert "started" in events[0].title.lower()

    def test_end_audit_session(self, test_db: Path):
        """Test ending an audit session."""
        run_id = audit_bridge.start_audit_session(name="Test Session")

        audit_bridge.end_audit_session(
            run_id,
            success=True,
            summary="Test completed"
        )

        # Verify run was closed
        run = get_run(run_id)
        assert run.closed_at is not None

        # Verify session end event was created
        events = list_events(run_id, limit=10)
        end_events = [e for e in events if "completed" in e.title.lower()]
        assert len(end_events) >= 1
        assert end_events[0].type == "session"

    def test_end_session_with_failure(self, test_db: Path):
        """Test ending session with failure status."""
        run_id = audit_bridge.start_audit_session(name="Test Session")

        audit_bridge.end_audit_session(
            run_id,
            success=False,
            summary="Test failed"
        )

        events = list_events(run_id, limit=10)
        end_events = [e for e in events if e.type == "session" and "ended" in e.title.lower()]
        assert len(end_events) >= 1


class TestEventLogging:
    """Tests for event logging functions."""

    def test_log_thought(self, test_db: Path):
        """Test logging thoughts/analysis."""
        run_id = audit_bridge.start_audit_session(name="Test Session")

        audit_bridge.log_thought(
            run_id,
            "This is a test thought",
            phase="plan"
        )

        events = list_events(run_id, limit=10)
        thought_events = [e for e in events if e.type == "thought"]
        assert len(thought_events) >= 1
        assert "test thought" in thought_events[0].detail.lower()
        assert thought_events[0].phase == "plan"

    def test_log_command(self, test_db: Path):
        """Test logging command execution."""
        run_id = audit_bridge.start_audit_session(name="Test Session")

        result = audit_bridge.log_command(
            run_id,
            "echo 'test output'",
            phase="apply"
        )

        assert result is not None
        assert result.returncode == 0
        assert "test output" in result.stdout

        events = list_events(run_id, limit=10)
        cmd_events = [e for e in events if e.type in ("command", "command_result")]
        assert len(cmd_events) >= 2  # start + result

    def test_log_file_change(self, test_db: Path):
        """Test logging file changes."""
        run_id = audit_bridge.start_audit_session(name="Test Session")

        audit_bridge.log_file_change(
            run_id,
            "test.py",
            "Created test file",
            change_type="create",
            phase="apply"
        )

        events = list_events(run_id, limit=10)
        file_events = [e for e in events if e.type == "file_change"]
        assert len(file_events) >= 1
        assert file_events[0].ref == "test.py"
        assert file_events[0].payload["change_type"] == "create"

    def test_log_git_operation(self, test_db: Path):
        """Test logging git operations."""
        run_id = audit_bridge.start_audit_session(name="Test Session")

        audit_bridge.log_git_operation(
            run_id,
            operation="commit",
            description="Test commit",
            payload={"hash": "abc123", "files": 2}
        )

        events = list_events(run_id, limit=10)
        git_events = [e for e in events if e.type == "git"]
        assert len(git_events) >= 1
        assert "commit" in git_events[0].title.lower()
        assert git_events[0].payload["hash"] == "abc123"

    def test_log_error(self, test_db: Path):
        """Test logging errors."""
        run_id = audit_bridge.start_audit_session(name="Test Session")

        audit_bridge.log_error(
            run_id,
            error_message="Test error occurred",
            error_type="TestError",
            phase="apply"
        )

        events = list_events(run_id, limit=10)
        error_events = [e for e in events if e.type == "error"]
        assert len(error_events) >= 1
        assert error_events[0].status == "error"
        assert "Test error" in error_events[0].detail


class TestPhaseLogging:
    """Tests for phase start/end logging."""

    def test_log_phase_start_end(self, test_db: Path):
        """Test phase boundary logging."""
        run_id = audit_bridge.start_audit_session(name="Test Session")

        audit_bridge.log_phase_start(run_id, "plan", "Planning test work")
        audit_bridge.log_phase_end(run_id, "plan", success=True, summary="Plan complete")

        events = list_events(run_id, limit=10)
        phase_events = [e for e in events if e.type == "phase"]
        assert len(phase_events) >= 2  # start + end

        start_event = phase_events[0]
        end_event = phase_events[1]

        assert start_event.status == "running"
        assert "started" in start_event.title.lower()
        assert end_event.status == "ok"
        assert "completed" in end_event.title.lower()


class TestContextManager:
    """Tests for audit_context context manager."""

    def test_audit_context_success(self, test_db: Path):
        """Test successful context manager usage."""
        run_id = audit_bridge.start_audit_session(name="Test Session")

        with audit_bridge.audit_context(run_id, "Test operation", phase="apply"):
            # Simulated work
            pass

        events = list_events(run_id, limit=10)
        operation_events = [e for e in events if e.type == "operation"]
        assert len(operation_events) >= 2  # start + end

    def test_audit_context_with_exception(self, test_db: Path):
        """Test context manager with exception."""
        run_id = audit_bridge.start_audit_session(name="Test Session")

        with pytest.raises(ValueError):
            with audit_bridge.audit_context(run_id, "Failing operation", phase="apply"):
                raise ValueError("Test error")

        events = list_events(run_id, limit=10)
        operation_events = [e for e in events if e.type == "operation"]
        assert len(operation_events) >= 2

        # Check error event
        error_event = operation_events[-1]
        assert error_event.status == "error"
        assert "ValueError" in error_event.detail


class TestHelpers:
    """Tests for helper functions."""

    def test_get_current_run_id_from_env(self, test_db: Path):
        """Test getting run ID from environment."""
        run_id = audit_bridge.start_audit_session(name="Test Session")

        os.environ["ATLAS_AUDIT_RUN_ID"] = str(run_id)

        retrieved_run_id = audit_bridge.get_current_run_id()
        assert retrieved_run_id == run_id

        del os.environ["ATLAS_AUDIT_RUN_ID"]

    def test_get_current_run_id_not_set(self):
        """Test getting run ID when not set."""
        if "ATLAS_AUDIT_RUN_ID" in os.environ:
            del os.environ["ATLAS_AUDIT_RUN_ID"]

        run_id = audit_bridge.get_current_run_id()
        assert run_id is None


class TestGracefulDegradation:
    """Tests for graceful degradation when audit unavailable."""

    def test_none_run_id_handling(self, test_db: Path):
        """Test that None run_id is handled gracefully."""
        # These should not raise exceptions
        audit_bridge.log_thought(None, "test")
        audit_bridge.log_file_change(None, "test.py", "test")
        audit_bridge.log_phase_start(None, "plan")
        audit_bridge.end_audit_session(None)

        # Context manager should also handle None
        with audit_bridge.audit_context(None, "test"):
            pass


class TestCompleteWorkflow:
    """Integration test for complete workflow."""

    def test_full_agent_workflow(self, test_db: Path):
        """Test a complete agent workflow with all features."""
        # Start session
        run_id = audit_bridge.start_audit_session(
            name="Complete Workflow Test",
            notes="Testing full workflow"
        )

        # Plan phase
        audit_bridge.log_phase_start(run_id, "plan")
        audit_bridge.log_thought(run_id, "Analyzing requirements", phase="plan")
        audit_bridge.log_phase_end(run_id, "plan", success=True)

        # Apply phase
        audit_bridge.log_phase_start(run_id, "apply")

        with audit_bridge.audit_context(run_id, "Create files", phase="apply"):
            audit_bridge.log_file_change(
                run_id,
                "test.py",
                "Created test file",
                change_type="create"
            )

        audit_bridge.log_git_operation(
            run_id,
            "commit",
            "Initial commit",
            payload={"files": 1}
        )
        audit_bridge.log_phase_end(run_id, "apply", success=True)

        # Validate phase
        audit_bridge.log_phase_start(run_id, "validate")
        result = audit_bridge.log_command(run_id, "echo 'test'", phase="validate")
        assert result.returncode == 0
        audit_bridge.log_phase_end(run_id, "validate", success=True)

        # End session
        audit_bridge.end_audit_session(run_id, success=True, summary="All done")

        # Verify all events were created
        events = list_events(run_id, limit=50)
        assert len(events) >= 10  # Should have many events

        # Verify run is closed
        run = get_run(run_id)
        assert run.closed_at is not None

        # Verify phases are present
        phase_events = [e for e in events if e.type == "phase"]
        phases = {e.phase for e in phase_events}
        assert "plan" in phases
        assert "apply" in phases
        assert "validate" in phases
