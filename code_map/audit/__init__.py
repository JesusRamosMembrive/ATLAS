# SPDX-License-Identifier: MIT
"""
Audit log primitives for tracking agent sessions.
"""

from .storage import (
    AuditEvent,
    AuditRun,
    # Sync versions (for backwards compatibility)
    append_event,
    close_run,
    create_run,
    get_run,
    list_events,
    list_runs,
    # Async versions (preferred for FastAPI endpoints)
    append_event_async,
    close_run_async,
    create_run_async,
    get_run_async,
    list_events_async,
    list_runs_async,
)

__all__ = [
    "AuditEvent",
    "AuditRun",
    # Sync
    "append_event",
    "close_run",
    "create_run",
    "get_run",
    "list_events",
    "list_runs",
    # Async
    "append_event_async",
    "close_run_async",
    "create_run_async",
    "get_run_async",
    "list_events_async",
    "list_runs_async",
]
