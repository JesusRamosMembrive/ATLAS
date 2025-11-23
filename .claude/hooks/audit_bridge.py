#!/usr/bin/env python3
"""
Agent Audit Bridge for Claude Code

This module provides a simplified interface for Claude Code agents to log
their actions to the ATLAS audit system. It wraps the core audit hooks from
code_map.audit and provides easy-to-use functions that agents can call.

Usage Examples:
    # 1. Start an audit session for your work
    run_id = start_audit_session("Fix authentication bug", notes="User reported login issues")

    # 2. Log your thinking/planning
    log_thought(run_id, "Analyzing auth flow in auth.py:45-67", phase="plan")

    # 3. Log commands you run
    log_command(run_id, "pytest tests/test_auth.py", phase="validate")

    # 4. Log file changes
    log_file_change(run_id, "auth.py", "Fixed token validation logic")

    # 5. End the session when done
    end_audit_session(run_id, success=True)

Integration:
    This bridge automatically connects to the ATLAS audit database and emits
    events that appear in real-time on the Agent Monitoring Dashboard.

    The backend API serves these events via SSE at:
    http://localhost:8010/audit/runs/{run_id}/stream

    The frontend displays them live in the AuditSessionsView component.
"""

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

# Add project root to path to import code_map
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from code_map.audit import create_run, close_run, append_event
    from code_map.audit.hooks import AuditContext, audit_run_command
    AUDIT_AVAILABLE = True
except ImportError:
    # Graceful degradation if audit system not available
    AUDIT_AVAILABLE = False
    print("[Audit Bridge] Warning: code_map.audit not available. Audit logging disabled.", file=sys.stderr)


# ============================================================================
# Session Management
# ============================================================================

def start_audit_session(
    name: str,
    root_path: Optional[str] = None,
    notes: Optional[str] = None,
    actor: str = "claude_code"
) -> Optional[int]:
    """
    Start a new audit session for tracking agent work.

    Args:
        name: Short description of what you're working on
        root_path: Project directory (defaults to current directory)
        notes: Detailed notes about the task
        actor: Agent identifier (default: "claude_code")

    Returns:
        Run ID to use for subsequent audit calls, or None if audit unavailable

    Example:
        run_id = start_audit_session(
            name="Implement user authentication",
            notes="Adding JWT-based auth to API endpoints"
        )
    """
    if not AUDIT_AVAILABLE:
        return None

    if root_path is None:
        root_path = os.getcwd()

    run = create_run(
        name=name,
        root_path=root_path,
        notes=notes or ""
    )

    # Log session start event
    append_event(
        run_id=run.id,
        type="session",
        title=f"Session started: {name}",
        detail=notes,
        actor=actor,
        phase="init",
        status="running"
    )

    return run.id


def end_audit_session(
    run_id: Optional[int],
    success: bool = True,
    summary: Optional[str] = None,
    actor: str = "claude_code"
) -> None:
    """
    End an audit session and mark it as closed.

    Args:
        run_id: The run ID from start_audit_session()
        success: Whether the work completed successfully
        summary: Optional summary of what was accomplished
        actor: Agent identifier

    Example:
        end_audit_session(
            run_id=run_id,
            success=True,
            summary="Successfully implemented JWT auth with tests"
        )
    """
    if not AUDIT_AVAILABLE or run_id is None:
        return

    # Log session end event
    append_event(
        run_id=run_id,
        type="session",
        title="Session completed" if success else "Session ended with errors",
        detail=summary,
        actor=actor,
        phase="complete",
        status="ok" if success else "error"
    )

    # Close the run
    close_run(run_id)


# ============================================================================
# Event Logging Functions
# ============================================================================

def log_thought(
    run_id: Optional[int],
    thought: str,
    phase: str = "plan",
    actor: str = "claude_code"
) -> None:
    """
    Log a thought, analysis, or planning decision.

    Use this to document your reasoning process, design decisions,
    or analysis findings.

    Args:
        run_id: Active audit session ID
        thought: Your thought or analysis
        phase: Workflow phase (plan, apply, validate, explore)
        actor: Agent identifier

    Example:
        log_thought(
            run_id,
            "The authentication flow has a race condition in token refresh",
            phase="plan"
        )
    """
    if not AUDIT_AVAILABLE or run_id is None:
        return

    append_event(
        run_id=run_id,
        type="thought",
        title="Analysis",
        detail=thought,
        actor=actor,
        phase=phase,
        status="ok"
    )


def log_command(
    run_id: Optional[int],
    command: str,
    phase: str = "apply",
    actor: str = "claude_code",
    timeout: Optional[int] = None
) -> Optional[Any]:
    """
    Log a command execution (and actually run it).

    This wraps subprocess.run() and automatically logs the command
    execution, output, and result.

    Args:
        run_id: Active audit session ID
        command: Command to run (string)
        phase: Workflow phase
        actor: Agent identifier
        timeout: Command timeout in seconds

    Returns:
        CompletedProcess result, or None if audit unavailable

    Example:
        result = log_command(run_id, "pytest tests/test_auth.py -v")
        if result.returncode == 0:
            log_thought(run_id, "All tests passed!")
    """
    if not AUDIT_AVAILABLE or run_id is None:
        # Fallback: just run the command without audit
        import subprocess
        return subprocess.run(command, shell=True, capture_output=True, text=True)

    return audit_run_command(
        cmd=command,
        run_id=run_id,
        phase=phase,
        actor=actor,
        timeout=timeout,
        shell=True
    )


def log_file_change(
    run_id: Optional[int],
    file_path: str,
    description: str,
    change_type: str = "modify",
    phase: str = "apply",
    actor: str = "claude_code"
) -> None:
    """
    Log a file change (create, modify, delete).

    Use this to document when you create or modify files during
    your work.

    Args:
        run_id: Active audit session ID
        file_path: Path to the file that changed
        description: What changed and why
        change_type: Type of change (create, modify, delete)
        phase: Workflow phase
        actor: Agent identifier

    Example:
        log_file_change(
            run_id,
            "src/auth/middleware.py",
            "Added JWT validation middleware",
            change_type="create"
        )
    """
    if not AUDIT_AVAILABLE or run_id is None:
        return

    append_event(
        run_id=run_id,
        type="file_change",
        title=f"{change_type.capitalize()}: {file_path}",
        detail=description,
        actor=actor,
        phase=phase,
        ref=file_path,
        status="ok",
        payload={"change_type": change_type, "file_path": file_path}
    )


def log_git_operation(
    run_id: Optional[int],
    operation: str,
    description: str,
    phase: str = "apply",
    actor: str = "claude_code",
    payload: Optional[Dict[str, Any]] = None
) -> None:
    """
    Log a git operation (commit, push, branch, etc.).

    Args:
        run_id: Active audit session ID
        operation: Git operation type (commit, push, branch, merge)
        description: Description of what happened
        phase: Workflow phase
        actor: Agent identifier
        payload: Optional additional data (commit hash, branch name, etc.)

    Example:
        log_git_operation(
            run_id,
            operation="commit",
            description="Add JWT authentication middleware",
            payload={"hash": "a1b2c3d", "files_changed": 3}
        )
    """
    if not AUDIT_AVAILABLE or run_id is None:
        return

    append_event(
        run_id=run_id,
        type="git",
        title=f"Git {operation}",
        detail=description,
        actor=actor,
        phase=phase,
        status="ok",
        payload=payload or {}
    )


def log_error(
    run_id: Optional[int],
    error_message: str,
    error_type: Optional[str] = None,
    phase: Optional[str] = None,
    actor: str = "claude_code",
    traceback: Optional[str] = None
) -> None:
    """
    Log an error or exception that occurred.

    Args:
        run_id: Active audit session ID
        error_message: Error message
        error_type: Type of error (e.g., "ValueError", "RuntimeError")
        phase: Workflow phase where error occurred
        actor: Agent identifier
        traceback: Optional full traceback

    Example:
        try:
            # some operation
            pass
        except Exception as e:
            log_error(
                run_id,
                error_message=str(e),
                error_type=type(e).__name__,
                traceback=traceback.format_exc()
            )
    """
    if not AUDIT_AVAILABLE or run_id is None:
        return

    detail = error_message
    if traceback:
        detail = f"{error_message}\n\nTraceback:\n{traceback}"

    append_event(
        run_id=run_id,
        type="error",
        title=f"Error: {error_type or 'Exception'}",
        detail=detail,
        actor=actor,
        phase=phase,
        status="error",
        payload={"error_type": error_type, "error_message": error_message}
    )


def log_phase_start(
    run_id: Optional[int],
    phase_name: str,
    description: Optional[str] = None,
    actor: str = "claude_code"
) -> None:
    """
    Log the start of a workflow phase.

    Phases typically include: plan, apply, validate, explore

    Args:
        run_id: Active audit session ID
        phase_name: Name of the phase (plan, apply, validate, explore)
        description: Optional description of what this phase will do
        actor: Agent identifier

    Example:
        log_phase_start(run_id, "plan", "Analyzing authentication requirements")
        # ... do planning work ...
        log_phase_end(run_id, "plan")
    """
    if not AUDIT_AVAILABLE or run_id is None:
        return

    append_event(
        run_id=run_id,
        type="phase",
        title=f"Phase: {phase_name.upper()} started",
        detail=description,
        actor=actor,
        phase=phase_name,
        status="running",
        payload={"phase_name": phase_name}
    )


def log_phase_end(
    run_id: Optional[int],
    phase_name: str,
    success: bool = True,
    summary: Optional[str] = None,
    actor: str = "claude_code"
) -> None:
    """
    Log the end of a workflow phase.

    Args:
        run_id: Active audit session ID
        phase_name: Name of the phase that ended
        success: Whether phase completed successfully
        summary: Optional summary of phase results
        actor: Agent identifier

    Example:
        log_phase_end(
            run_id,
            "plan",
            success=True,
            summary="Identified 3 security issues to address"
        )
    """
    if not AUDIT_AVAILABLE or run_id is None:
        return

    append_event(
        run_id=run_id,
        type="phase",
        title=f"Phase: {phase_name.upper()} {'completed' if success else 'failed'}",
        detail=summary,
        actor=actor,
        phase=phase_name,
        status="ok" if success else "error",
        payload={"phase_name": phase_name}
    )


# ============================================================================
# Context Manager for Tracking Work Blocks
# ============================================================================

class audit_context:
    """
    Context manager for tracking a block of work.

    This is useful for wrapping larger operations with automatic
    start/end events and error capturing.

    Example:
        with audit_context(run_id, "Analyze authentication flow", phase="plan"):
            # Your analysis work here
            analyze_code()
            review_tests()
        # Automatically logs start, end, and any errors
    """

    def __init__(
        self,
        run_id: Optional[int],
        title: str,
        phase: str = "apply",
        actor: str = "claude_code",
        detail: Optional[str] = None
    ):
        self.run_id = run_id
        self.title = title
        self.phase = phase
        self.actor = actor
        self.detail = detail
        self._ctx: Optional[AuditContext] = None

    def __enter__(self):
        if AUDIT_AVAILABLE and self.run_id is not None:
            self._ctx = AuditContext(
                run_id=self.run_id,
                title=self.title,
                event_type="operation",
                phase=self.phase,
                actor=self.actor,
                detail=self.detail
            )
            self._ctx.__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._ctx is not None:
            return self._ctx.__exit__(exc_type, exc_val, exc_tb)
        return False


# ============================================================================
# Helper: Get current run ID from environment
# ============================================================================

def get_current_run_id() -> Optional[int]:
    """
    Get the current audit run ID from environment variable.

    Agents can set ATLAS_AUDIT_RUN_ID in their environment to automatically
    use the same run ID across all audit calls.

    Returns:
        Run ID from environment, or None if not set

    Example:
        # In your agent startup:
        run_id = start_audit_session("My work session")
        os.environ["ATLAS_AUDIT_RUN_ID"] = str(run_id)

        # Later, in any function:
        current_run = get_current_run_id()
        log_thought(current_run, "Some analysis...")
    """
    run_id_str = os.environ.get("ATLAS_AUDIT_RUN_ID")
    if run_id_str:
        try:
            return int(run_id_str)
        except ValueError:
            return None
    return None


# ============================================================================
# Quick Start Example
# ============================================================================

def example_usage():
    """
    Example of how to use the audit bridge in your agent code.
    """
    # Start a session
    run_id = start_audit_session(
        name="Example agent work",
        notes="Demonstrating audit bridge usage"
    )

    if run_id is None:
        print("Audit system not available, continuing without logging")
        return

    # Store in environment for convenience
    os.environ["ATLAS_AUDIT_RUN_ID"] = str(run_id)

    try:
        # Log planning phase
        log_phase_start(run_id, "plan", "Analyzing codebase")
        log_thought(run_id, "Need to understand authentication flow", phase="plan")
        log_phase_end(run_id, "plan", success=True)

        # Log implementation phase
        log_phase_start(run_id, "apply", "Implementing changes")

        with audit_context(run_id, "Create auth middleware", phase="apply"):
            # Simulated work
            log_file_change(
                run_id,
                "src/auth/middleware.py",
                "Created JWT validation middleware",
                change_type="create"
            )

        log_phase_end(run_id, "apply", success=True)

        # Log validation phase
        log_phase_start(run_id, "validate", "Running tests")
        result = log_command(run_id, "echo 'pytest tests/'", phase="validate")

        if result and result.returncode == 0:
            log_thought(run_id, "All tests passed!", phase="validate")
            log_phase_end(run_id, "validate", success=True)

        # End session successfully
        end_audit_session(
            run_id,
            success=True,
            summary="Successfully implemented and tested authentication"
        )

    except Exception as e:
        # Log error and end session
        import traceback
        log_error(
            run_id,
            error_message=str(e),
            error_type=type(e).__name__,
            traceback=traceback.format_exc()
        )
        end_audit_session(run_id, success=False, summary=f"Failed with error: {e}")
        raise


if __name__ == "__main__":
    # Run example if executed directly
    print("Running audit bridge example...")
    example_usage()
    print("\nExample completed! Check the audit dashboard at http://localhost:8010")