"""
Audit Hooks System

Provides decorators, context managers, and wrappers to automatically
capture agent actions (commands, file changes, git operations) and
emit audit events.

Usage:
    # Decorator for automatic function tracking
    @audit_tracked(event_type="command", phase="apply")
    def run_tests():
        subprocess.run(["pytest", "tests/"])

    # Context manager for tracking blocks of work
    with AuditContext(run_id=123, phase="plan", event_type="analysis"):
        # analyze codebase
        pass

    # Subprocess wrapper
    result = audit_run_command(["pytest", "tests/"], run_id=123, phase="validate")
"""

import functools
import subprocess
import time
from contextlib import contextmanager
from typing import Any, Callable, Dict, List, Optional, TypeVar, Union

from code_map.audit import storage

# Type variable for decorator
F = TypeVar('F', bound=Callable[..., Any])


class AuditContext:
    """
    Context manager for tracking a block of work with automatic
    start/end events and error capturing.

    Example:
        with AuditContext(run_id=123, title="Analyze codebase", phase="plan"):
            # work here
            result = analyze()
        # Automatically creates start event, end event, and captures errors
    """

    def __init__(
        self,
        run_id: int,
        title: str,
        event_type: str = "operation",
        phase: Optional[str] = None,
        actor: str = "agent",
        detail: Optional[str] = None,
        ref: Optional[str] = None,
    ):
        self.run_id = run_id
        self.title = title
        self.event_type = event_type
        self.phase = phase
        self.actor = actor
        self.detail = detail
        self.ref = ref
        self.start_time: Optional[float] = None
        self.start_event_id: Optional[int] = None

    def __enter__(self):
        """Start tracking - emit 'running' status event"""
        self.start_time = time.time()

        event = storage.append_event(
            run_id=self.run_id,
            event_type=self.event_type,
            title=f"{self.title} (started)",
            detail=self.detail,
            actor=self.actor,
            phase=self.phase,
            status="running",
            ref=self.ref,
            payload={"started_at": self.start_time}
        )
        self.start_event_id = event.id
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """End tracking - emit 'ok' or 'error' status event"""
        duration_ms = int((time.time() - self.start_time) * 1000) if self.start_time else 0

        if exc_type is None:
            # Success case
            storage.append_event(
                run_id=self.run_id,
                event_type=self.event_type,
                title=f"{self.title} (completed)",
                detail=self.detail,
                actor=self.actor,
                phase=self.phase,
                status="ok",
                ref=self.ref,
                payload={"duration_ms": duration_ms, "start_event_id": self.start_event_id}
            )
        else:
            # Error case
            error_detail = f"{self.detail}\n\nError: {exc_type.__name__}: {exc_val}" if self.detail else f"Error: {exc_type.__name__}: {exc_val}"
            storage.append_event(
                run_id=self.run_id,
                event_type=self.event_type,
                title=f"{self.title} (failed)",
                detail=error_detail,
                actor=self.actor,
                phase=self.phase,
                status="error",
                ref=self.ref,
                payload={
                    "duration_ms": duration_ms,
                    "start_event_id": self.start_event_id,
                    "error_type": exc_type.__name__,
                    "error_message": str(exc_val)
                }
            )

        # Don't suppress exceptions
        return False


def audit_tracked(
    event_type: str = "operation",
    phase: Optional[str] = None,
    actor: str = "agent",
    title_from_func: bool = True,
    capture_return: bool = False,
) -> Callable[[F], F]:
    """
    Decorator to automatically track function execution as audit events.

    Args:
        event_type: Type of event (command, analysis, etc.)
        phase: Workflow phase (plan, apply, validate, explore)
        actor: Who is performing the action (agent, human)
        title_from_func: Use function name as event title
        capture_return: Include return value in payload

    Example:
        @audit_tracked(event_type="command", phase="validate")
        def run_tests():
            return subprocess.run(["pytest", "tests/"])

        # When called, automatically creates audit events
        run_tests()  # -> emits "run_tests (started)" and "run_tests (completed)"

    Note: Requires `run_id` to be passed as kwarg or set in environment.
    """
    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Try to get run_id from kwargs or environment
            run_id = kwargs.pop('audit_run_id', None)
            if run_id is None:
                # No run_id, skip audit tracking
                return func(*args, **kwargs)

            title = func.__name__ if title_from_func else "operation"
            start_time = time.time()

            # Emit start event
            start_event = storage.append_event(
                run_id=run_id,
                event_type=event_type,
                title=f"{title} (started)",
                actor=actor,
                phase=phase,
                status="running",
                payload={"args": str(args)[:200], "started_at": start_time}
            )

            try:
                result = func(*args, **kwargs)
                duration_ms = int((time.time() - start_time) * 1000)

                # Success - emit completion event
                payload = {"duration_ms": duration_ms, "start_event_id": start_event.id}
                if capture_return and result is not None:
                    payload["return_value"] = str(result)[:500]

                storage.append_event(
                    run_id=run_id,
                    event_type=event_type,
                    title=f"{title} (completed)",
                    actor=actor,
                    phase=phase,
                    status="ok",
                    payload=payload
                )

                return result

            except Exception as e:
                duration_ms = int((time.time() - start_time) * 1000)

                # Error - emit failure event
                storage.append_event(
                    run_id=run_id,
                    event_type=event_type,
                    title=f"{title} (failed)",
                    detail=f"Error: {type(e).__name__}: {e}",
                    actor=actor,
                    phase=phase,
                    status="error",
                    payload={
                        "duration_ms": duration_ms,
                        "start_event_id": start_event.id,
                        "error_type": type(e).__name__,
                        "error_message": str(e)
                    }
                )
                raise

        return wrapper  # type: ignore
    return decorator


def audit_run_command(
    cmd: Union[str, List[str]],
    run_id: int,
    phase: Optional[str] = None,
    actor: str = "agent",
    capture_output: bool = True,
    timeout: Optional[int] = None,
    **subprocess_kwargs
) -> subprocess.CompletedProcess:
    """
    Wrapper around subprocess.run() that automatically logs command
    execution as audit events.

    Args:
        cmd: Command to execute (string or list)
        run_id: Audit run ID to attach events to
        phase: Workflow phase (validate, apply, etc.)
        actor: Who is running the command
        capture_output: Capture stdout/stderr for audit log
        timeout: Command timeout in seconds
        **subprocess_kwargs: Additional args passed to subprocess.run()

    Returns:
        CompletedProcess with returncode, stdout, stderr

    Example:
        result = audit_run_command(
            ["pytest", "tests/"],
            run_id=123,
            phase="validate"
        )
        # Creates events: "$ pytest tests/" (running) -> (ok/error)
    """
    # Format command for display
    cmd_str = cmd if isinstance(cmd, str) else " ".join(cmd)

    # Emit start event
    start_time = time.time()
    start_event = storage.append_event(
        run_id=run_id,
        event_type="command",
        title=f"$ {cmd_str}",
        actor=actor,
        phase=phase,
        status="running",
        payload={"command": cmd_str, "started_at": start_time}
    )

    try:
        # Run command
        result = subprocess.run(
            cmd,
            capture_output=capture_output,
            text=True,
            timeout=timeout,
            **subprocess_kwargs
        )

        duration_ms = int((time.time() - start_time) * 1000)

        # Format output for detail field (truncate if too long)
        output_parts = []
        if result.stdout:
            stdout_excerpt = result.stdout[:2000] + ("..." if len(result.stdout) > 2000 else "")
            output_parts.append(f"STDOUT:\n{stdout_excerpt}")
        if result.stderr:
            stderr_excerpt = result.stderr[:2000] + ("..." if len(result.stderr) > 2000 else "")
            output_parts.append(f"STDERR:\n{stderr_excerpt}")
        detail = "\n\n".join(output_parts) if output_parts else None

        # Emit result event
        status = "ok" if result.returncode == 0 else "error"
        storage.append_event(
            run_id=run_id,
            event_type="command_result",
            title=f"$ {cmd_str} (exit {result.returncode})",
            detail=detail,
            actor=actor,
            phase=phase,
            status=status,
            payload={
                "command": cmd_str,
                "exit_code": result.returncode,
                "duration_ms": duration_ms,
                "start_event_id": start_event.id,
                "stdout_lines": len(result.stdout.splitlines()) if result.stdout else 0,
                "stderr_lines": len(result.stderr.splitlines()) if result.stderr else 0,
            }
        )

        return result

    except subprocess.TimeoutExpired as e:
        duration_ms = int((time.time() - start_time) * 1000)

        storage.append_event(
            run_id=run_id,
            event_type="command_result",
            title=f"$ {cmd_str} (timeout)",
            detail=f"Command timed out after {timeout}s",
            actor=actor,
            phase=phase,
            status="error",
            payload={
                "command": cmd_str,
                "error_type": "TimeoutExpired",
                "timeout_seconds": timeout,
                "duration_ms": duration_ms,
                "start_event_id": start_event.id,
            }
        )
        raise

    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)

        storage.append_event(
            run_id=run_id,
            event_type="command_result",
            title=f"$ {cmd_str} (error)",
            detail=f"Error: {type(e).__name__}: {e}",
            actor=actor,
            phase=phase,
            status="error",
            payload={
                "command": cmd_str,
                "error_type": type(e).__name__,
                "error_message": str(e),
                "duration_ms": duration_ms,
                "start_event_id": start_event.id,
            }
        )
        raise


@contextmanager
def audit_phase(run_id: int, phase_name: str, actor: str = "agent"):
    """
    Context manager for tracking workflow phases (plan, apply, validate).

    Emits phase_start and phase_end events with duration tracking.

    Example:
        with audit_phase(run_id=123, phase_name="plan"):
            # Planning work here
            architect_design()

        with audit_phase(run_id=123, phase_name="apply"):
            # Implementation work here
            implementer_code()
    """
    start_time = time.time()

    # Emit phase start
    start_event = storage.append_event(
        run_id=run_id,
        event_type="phase",
        title=f"Phase: {phase_name.upper()} started",
        actor=actor,
        phase=phase_name,
        status="running",
        payload={"phase_name": phase_name, "started_at": start_time}
    )

    try:
        yield

        duration_ms = int((time.time() - start_time) * 1000)

        # Success - emit phase completion
        storage.append_event(
            run_id=run_id,
            event_type="phase",
            title=f"Phase: {phase_name.upper()} completed",
            actor=actor,
            phase=phase_name,
            status="ok",
            payload={
                "phase_name": phase_name,
                "duration_ms": duration_ms,
                "start_event_id": start_event.id
            }
        )

    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)

        # Error - emit phase failure
        storage.append_event(
            run_id=run_id,
            event_type="phase",
            title=f"Phase: {phase_name.upper()} failed",
            detail=f"Error: {type(e).__name__}: {e}",
            actor=actor,
            phase=phase_name,
            status="error",
            payload={
                "phase_name": phase_name,
                "duration_ms": duration_ms,
                "start_event_id": start_event.id,
                "error_type": type(e).__name__,
                "error_message": str(e)
            }
        )
        raise
