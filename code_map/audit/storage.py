# SPDX-License-Identifier: MIT
"""
Persistence helpers for auditable pair-programming sessions.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional

from ..settings import open_database

DEFAULT_EVENTS_LIMIT = 200


@dataclass(frozen=True, slots=True)
class AuditRun:
    """Represents a tracked agent session."""

    id: int
    name: Optional[str]
    status: str
    root_path: Optional[str]
    created_at: datetime
    closed_at: Optional[datetime]
    notes: Optional[str]
    event_count: int = 0


@dataclass(frozen=True, slots=True)
class AuditEvent:
    """Represents a granular auditable event inside a run."""

    id: int
    run_id: int
    type: str
    title: str
    detail: Optional[str]
    actor: Optional[str]
    phase: Optional[str]
    status: Optional[str]
    ref: Optional[str]
    payload: Optional[dict[str, Any]]
    created_at: datetime


def _ensure_tables() -> None:
    with open_database() as connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                status TEXT NOT NULL,
                root_path TEXT,
                created_at TEXT NOT NULL,
                closed_at TEXT,
                notes TEXT
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS audit_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_id INTEGER NOT NULL,
                type TEXT NOT NULL,
                title TEXT NOT NULL,
                detail TEXT,
                actor TEXT,
                phase TEXT,
                status TEXT,
                ref TEXT,
                payload TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(run_id) REFERENCES audit_runs(id) ON DELETE CASCADE
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_audit_runs_created_at
            ON audit_runs(created_at DESC)
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_audit_events_run_id_created_at
            ON audit_events(run_id, created_at)
            """
        )
        connection.commit()


def _normalize_root(root: Optional[Path | str]) -> Optional[str]:
    if root is None:
        return None
    return Path(root).expanduser().resolve().as_posix()


def _parse_timestamp(raw: str | None) -> Optional[datetime]:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def _parse_payload(raw: str | None) -> Optional[dict[str, Any]]:
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def _row_to_run(row: Mapping[str, Any]) -> AuditRun:
    return AuditRun(
        id=int(row["id"]),
        name=row["name"],
        status=row["status"],
        root_path=row["root_path"],
        created_at=_parse_timestamp(row["created_at"]) or datetime.now(timezone.utc),
        closed_at=(
            _parse_timestamp(row["closed_at"]) if "closed_at" in row.keys() else None
        ),
        notes=row["notes"] if "notes" in row.keys() else None,
        event_count=int(row["event_count"]) if "event_count" in row.keys() else 0,
    )


def _row_to_event(row: Mapping[str, Any]) -> AuditEvent:
    return AuditEvent(
        id=int(row["id"]),
        run_id=int(row["run_id"]),
        type=row["type"],
        title=row["title"],
        detail=row["detail"] if "detail" in row.keys() else None,
        actor=row["actor"] if "actor" in row.keys() else None,
        phase=row["phase"] if "phase" in row.keys() else None,
        status=row["status"] if "status" in row.keys() else None,
        ref=row["ref"] if "ref" in row.keys() else None,
        payload=_parse_payload(row["payload"]) if "payload" in row.keys() else None,
        created_at=_parse_timestamp(row["created_at"]) or datetime.now(timezone.utc),
    )


def create_run(
    *,
    name: Optional[str] = None,
    root_path: Optional[Path | str] = None,
    notes: Optional[str] = None,
) -> AuditRun:
    """Creates a new audit run entry."""
    _ensure_tables()
    created_at = datetime.now(timezone.utc).isoformat()
    normalized_root = _normalize_root(root_path)

    with open_database() as connection:
        cursor = connection.execute(
            """
            INSERT INTO audit_runs (name, status, root_path, created_at, notes)
            VALUES (?, ?, ?, ?, ?)
            """,
            (name, "open", normalized_root, created_at, notes),
        )
        connection.commit()
        run_id = cursor.lastrowid or 0

    run = get_run(int(run_id))
    if run is None:
        raise RuntimeError("Failed to create audit run")
    return run


def close_run(
    run_id: int,
    *,
    status: str = "closed",
    notes: Optional[str] = None,
) -> Optional[AuditRun]:
    """Marks a run as finished."""
    _ensure_tables()
    closed_at = datetime.now(timezone.utc).isoformat()
    with open_database() as connection:
        connection.execute(
            """
            UPDATE audit_runs
            SET status = ?, closed_at = ?, notes = COALESCE(?, notes)
            WHERE id = ?
            """,
            (status, closed_at, notes, run_id),
        )
        connection.commit()
    return get_run(run_id)


def get_run(run_id: int) -> Optional[AuditRun]:
    """Fetches a single run including event count."""
    _ensure_tables()
    with open_database() as connection:
        row = connection.execute(
            """
            SELECT
                r.id,
                r.name,
                r.status,
                r.root_path,
                r.created_at,
                r.closed_at,
                r.notes,
                COUNT(e.id) AS event_count
            FROM audit_runs r
            LEFT JOIN audit_events e ON e.run_id = r.id
            WHERE r.id = ?
            GROUP BY r.id
            """,
            (run_id,),
        ).fetchone()

    if row is None:
        return None
    return _row_to_run(row)


def list_runs(
    *,
    limit: int = 20,
    root_path: Optional[Path | str] = None,
) -> list[AuditRun]:
    """Lists recent runs, optionally filtered by root."""
    _ensure_tables()
    normalized_root = _normalize_root(root_path)
    params: list[object] = []
    clauses: list[str] = []

    if normalized_root:
        clauses.append("(r.root_path IS NULL OR r.root_path = ?)")
        params.append(normalized_root)

    query_parts = [
        """
        SELECT
            r.id,
            r.name,
            r.status,
            r.root_path,
            r.created_at,
            r.closed_at,
            r.notes,
            COUNT(e.id) AS event_count
        FROM audit_runs r
        LEFT JOIN audit_events e ON e.run_id = r.id
        """
    ]
    if clauses:
        query_parts.append("WHERE " + " AND ".join(clauses))
    query_parts.append("GROUP BY r.id")
    query_parts.append("ORDER BY r.created_at DESC")
    query_parts.append("LIMIT ?")
    params.append(max(1, limit))

    sql = "\n".join(query_parts)

    with open_database() as connection:
        rows = connection.execute(sql, params).fetchall()

    return [_row_to_run(row) for row in rows]


def append_event(
    run_id: int,
    *,
    type: str,
    title: str,
    detail: Optional[str] = None,
    actor: Optional[str] = None,
    phase: Optional[str] = None,
    status: Optional[str] = None,
    ref: Optional[str] = None,
    payload: Optional[Mapping[str, Any]] = None,
) -> AuditEvent:
    """Adds a new event to a run."""
    _ensure_tables()
    if get_run(run_id) is None:
        raise LookupError(f"Run {run_id} not found")

    created_at = datetime.now(timezone.utc).isoformat()
    payload_json = (
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        if payload
        else None
    )

    with open_database() as connection:
        cursor = connection.execute(
            """
            INSERT INTO audit_events (
                run_id, type, title, detail, actor, phase, status, ref, payload, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                run_id,
                type,
                title,
                detail,
                actor,
                phase,
                status,
                ref,
                payload_json,
                created_at,
            ),
        )
        connection.commit()
        event_id = cursor.lastrowid or 0

    event = get_event(run_id, int(event_id))
    if event is None:
        raise RuntimeError("Failed to persist audit event")
    return event


def get_event(run_id: int, event_id: int) -> Optional[AuditEvent]:
    """Fetches a single event by id."""
    _ensure_tables()
    with open_database() as connection:
        row = connection.execute(
            """
            SELECT
                id, run_id, type, title, detail, actor, phase, status, ref, payload, created_at
            FROM audit_events
            WHERE id = ? AND run_id = ?
            """,
            (event_id, run_id),
        ).fetchone()

    if row is None:
        return None
    return _row_to_event(row)


def list_events(
    run_id: int,
    *,
    limit: int = DEFAULT_EVENTS_LIMIT,
    after_id: Optional[int] = None,
) -> list[AuditEvent]:
    """Lists events for a run, ordered chronologically."""
    _ensure_tables()
    params: list[object] = [run_id]
    clauses: list[str] = ["run_id = ?"]

    if after_id is not None:
        clauses.append("id > ?")
        params.append(after_id)

    sql = "\n".join(
        [
            """
            SELECT
                id, run_id, type, title, detail, actor, phase, status, ref, payload, created_at
            FROM audit_events
            WHERE {where}
            ORDER BY created_at ASC, id ASC
            LIMIT ?
            """.format(
                where=" AND ".join(clauses)
            )
        ]
    )
    params.append(max(1, limit))

    with open_database() as connection:
        rows = connection.execute(sql, params).fetchall()

    return [_row_to_event(row) for row in rows]
