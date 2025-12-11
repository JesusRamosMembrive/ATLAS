# SPDX-License-Identifier: MIT
"""
Persistence helpers for auditable pair-programming sessions.

This module provides both sync and async versions of storage functions.
The async versions are preferred for use in FastAPI endpoints.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Optional

from sqlmodel import select, desc, func, or_
from sqlalchemy import select as sa_select

from ..database import get_engine, init_db, Session
from ..database_async import get_async_session, init_async_db
from ..models import AuditRunDB, AuditEventDB

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


def _normalize_root(root: Optional[Path | str]) -> Optional[str]:
    if root is None:
        return None
    return Path(root).expanduser().resolve().as_posix()


def _parse_payload(raw: str | None) -> Optional[dict[str, Any]]:
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def create_run(
    *,
    name: Optional[str] = None,
    root_path: Optional[Path | str] = None,
    notes: Optional[str] = None,
) -> AuditRun:
    """Creates a new audit run entry."""
    engine = get_engine()
    init_db(engine)

    normalized_root = _normalize_root(root_path)

    with Session(engine) as session:
        run = AuditRunDB(
            name=name,
            status="open",
            root_path=normalized_root,
            created_at=datetime.now(timezone.utc),
            notes=notes,
        )
        session.add(run)
        session.commit()
        session.refresh(run)

        result = get_run(run.id or 0)
        if result is None:
            raise RuntimeError("Failed to create audit run")
        return result


def close_run(
    run_id: int,
    *,
    status: str = "closed",
    notes: Optional[str] = None,
) -> Optional[AuditRun]:
    """Marks a run as finished."""
    engine = get_engine()
    init_db(engine)

    with Session(engine) as session:
        run = session.get(AuditRunDB, run_id)
        if not run:
            return None

        run.status = status
        run.closed_at = datetime.now(timezone.utc)
        if notes:
            run.notes = notes

        session.add(run)
        session.commit()

    return get_run(run_id)


def get_run(run_id: int) -> Optional[AuditRun]:
    """Fetches a single run including event count."""
    engine = get_engine()
    init_db(engine)

    with Session(engine) as session:
        run = session.get(AuditRunDB, run_id)
        if not run:
            return None

        # Count events
        event_count = session.exec(
            select(func.count(AuditEventDB.id)).where(AuditEventDB.run_id == run_id)
        ).one()

        return AuditRun(
            id=run.id or 0,
            name=run.name,
            status=run.status,
            root_path=run.root_path,
            created_at=run.created_at,
            closed_at=run.closed_at,
            notes=run.notes,
            event_count=event_count or 0,
        )


def list_runs(
    *,
    limit: int = 20,
    root_path: Optional[Path | str] = None,
) -> list[AuditRun]:
    """Lists recent runs, optionally filtered by root."""
    engine = get_engine()
    init_db(engine)

    normalized_root = _normalize_root(root_path)

    with Session(engine) as session:
        statement = select(AuditRunDB)

        if normalized_root:
            statement = statement.where(
                or_(
                    AuditRunDB.root_path.is_(None),  # type: ignore[union-attr]
                    AuditRunDB.root_path == normalized_root,
                )
            )

        statement = statement.order_by(desc(AuditRunDB.created_at)).limit(max(1, limit))
        runs = session.exec(statement).all()

        results = []
        for run in runs:
            event_count = session.exec(
                select(func.count(AuditEventDB.id)).where(AuditEventDB.run_id == run.id)
            ).one()

            results.append(
                AuditRun(
                    id=run.id or 0,
                    name=run.name,
                    status=run.status,
                    root_path=run.root_path,
                    created_at=run.created_at,
                    closed_at=run.closed_at,
                    notes=run.notes,
                    event_count=event_count or 0,
                )
            )

        return results


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
    engine = get_engine()
    init_db(engine)

    if get_run(run_id) is None:
        raise LookupError(f"Run {run_id} not found")

    payload_json = (
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        if payload
        else None
    )

    with Session(engine) as session:
        event = AuditEventDB(
            run_id=run_id,
            type=type,
            title=title,
            detail=detail,
            actor=actor,
            phase=phase,
            status=status,
            ref=ref,
            payload=payload_json,
            created_at=datetime.now(timezone.utc),
        )
        session.add(event)
        session.commit()
        session.refresh(event)

        result = get_event(run_id, event.id or 0)
        if result is None:
            raise RuntimeError("Failed to persist audit event")
        return result


def get_event(run_id: int, event_id: int) -> Optional[AuditEvent]:
    """Fetches a single event by id."""
    engine = get_engine()
    init_db(engine)

    with Session(engine) as session:
        event = session.exec(
            select(AuditEventDB).where(
                AuditEventDB.id == event_id, AuditEventDB.run_id == run_id
            )
        ).first()

        if not event:
            return None

        return AuditEvent(
            id=event.id or 0,
            run_id=event.run_id,
            type=event.type,
            title=event.title,
            detail=event.detail,
            actor=event.actor,
            phase=event.phase,
            status=event.status,
            ref=event.ref,
            payload=_parse_payload(event.payload),
            created_at=event.created_at,
        )


def list_events(
    run_id: int,
    *,
    limit: int = DEFAULT_EVENTS_LIMIT,
    after_id: Optional[int] = None,
) -> list[AuditEvent]:
    """Lists events for a run, ordered chronologically."""
    engine = get_engine()
    init_db(engine)

    with Session(engine) as session:
        statement = select(AuditEventDB).where(AuditEventDB.run_id == run_id)

        if after_id is not None:
            statement = statement.where(AuditEventDB.id > after_id)

        statement = statement.order_by(AuditEventDB.created_at, AuditEventDB.id).limit(
            max(1, limit)
        )
        events = session.exec(statement).all()

        return [
            AuditEvent(
                id=event.id or 0,
                run_id=event.run_id,
                type=event.type,
                title=event.title,
                detail=event.detail,
                actor=event.actor,
                phase=event.phase,
                status=event.status,
                ref=event.ref,
                payload=_parse_payload(event.payload),
                created_at=event.created_at,
            )
            for event in events
        ]


# ============================================================================
# Async versions of storage functions (preferred for FastAPI endpoints)
# ============================================================================


async def create_run_async(
    *,
    name: Optional[str] = None,
    root_path: Optional[Path | str] = None,
    notes: Optional[str] = None,
) -> AuditRun:
    """Creates a new audit run entry (async version)."""
    await init_async_db()
    normalized_root = _normalize_root(root_path)

    async with get_async_session() as session:
        run = AuditRunDB(
            name=name,
            status="open",
            root_path=normalized_root,
            created_at=datetime.now(timezone.utc),
            notes=notes,
        )
        session.add(run)
        await session.flush()
        await session.refresh(run)

        run_id = run.id or 0

    # Fetch outside transaction to get event count
    result = await get_run_async(run_id)
    if result is None:
        raise RuntimeError("Failed to create audit run")
    return result


async def close_run_async(
    run_id: int,
    *,
    status: str = "closed",
    notes: Optional[str] = None,
) -> Optional[AuditRun]:
    """Marks a run as finished (async version)."""
    await init_async_db()

    async with get_async_session() as session:
        run = await session.get(AuditRunDB, run_id)
        if not run:
            return None

        run.status = status
        run.closed_at = datetime.now(timezone.utc)
        if notes:
            run.notes = notes

        session.add(run)

    return await get_run_async(run_id)


async def get_run_async(run_id: int) -> Optional[AuditRun]:
    """Fetches a single run including event count (async version)."""
    await init_async_db()

    async with get_async_session() as session:
        run = await session.get(AuditRunDB, run_id)
        if not run:
            return None

        # Count events using SQLAlchemy select
        result = await session.execute(
            sa_select(func.count(AuditEventDB.id)).where(AuditEventDB.run_id == run_id)
        )
        event_count = result.scalar() or 0

        return AuditRun(
            id=run.id or 0,
            name=run.name,
            status=run.status,
            root_path=run.root_path,
            created_at=run.created_at,
            closed_at=run.closed_at,
            notes=run.notes,
            event_count=event_count,
        )


async def list_runs_async(
    *,
    limit: int = 20,
    root_path: Optional[Path | str] = None,
) -> list[AuditRun]:
    """Lists recent runs, optionally filtered by root (async version)."""
    await init_async_db()
    normalized_root = _normalize_root(root_path)

    async with get_async_session() as session:
        statement = sa_select(AuditRunDB)

        if normalized_root:
            statement = statement.where(
                or_(
                    AuditRunDB.root_path.is_(None),  # type: ignore[union-attr]
                    AuditRunDB.root_path == normalized_root,
                )
            )

        statement = statement.order_by(desc(AuditRunDB.created_at)).limit(max(1, limit))
        result = await session.execute(statement)
        runs = result.scalars().all()

        results = []
        for run in runs:
            # Count events for each run
            count_result = await session.execute(
                sa_select(func.count(AuditEventDB.id)).where(
                    AuditEventDB.run_id == run.id
                )
            )
            event_count = count_result.scalar() or 0

            results.append(
                AuditRun(
                    id=run.id or 0,
                    name=run.name,
                    status=run.status,
                    root_path=run.root_path,
                    created_at=run.created_at,
                    closed_at=run.closed_at,
                    notes=run.notes,
                    event_count=event_count,
                )
            )

        return results


async def append_event_async(
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
    """Adds a new event to a run (async version)."""
    await init_async_db()

    # Check run exists
    run = await get_run_async(run_id)
    if run is None:
        raise LookupError(f"Run {run_id} not found")

    payload_json = (
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        if payload
        else None
    )

    async with get_async_session() as session:
        event = AuditEventDB(
            run_id=run_id,
            type=type,
            title=title,
            detail=detail,
            actor=actor,
            phase=phase,
            status=status,
            ref=ref,
            payload=payload_json,
            created_at=datetime.now(timezone.utc),
        )
        session.add(event)
        await session.flush()
        await session.refresh(event)

        event_id = event.id or 0

    result = await get_event_async(run_id, event_id)
    if result is None:
        raise RuntimeError("Failed to persist audit event")
    return result


async def get_event_async(run_id: int, event_id: int) -> Optional[AuditEvent]:
    """Fetches a single event by id (async version)."""
    await init_async_db()

    async with get_async_session() as session:
        result = await session.execute(
            sa_select(AuditEventDB).where(
                AuditEventDB.id == event_id,
                AuditEventDB.run_id == run_id,
            )
        )
        event = result.scalar_one_or_none()

        if not event:
            return None

        return AuditEvent(
            id=event.id or 0,
            run_id=event.run_id,
            type=event.type,
            title=event.title,
            detail=event.detail,
            actor=event.actor,
            phase=event.phase,
            status=event.status,
            ref=event.ref,
            payload=_parse_payload(event.payload),
            created_at=event.created_at,
        )


async def list_events_async(
    run_id: int,
    *,
    limit: int = DEFAULT_EVENTS_LIMIT,
    after_id: Optional[int] = None,
) -> list[AuditEvent]:
    """Lists events for a run, ordered chronologically (async version)."""
    await init_async_db()

    async with get_async_session() as session:
        statement = sa_select(AuditEventDB).where(AuditEventDB.run_id == run_id)

        if after_id is not None:
            statement = statement.where(AuditEventDB.id > after_id)

        statement = statement.order_by(AuditEventDB.created_at, AuditEventDB.id).limit(
            max(1, limit)
        )

        result = await session.execute(statement)
        events = result.scalars().all()

        return [
            AuditEvent(
                id=event.id or 0,
                run_id=event.run_id,
                type=event.type,
                title=event.title,
                detail=event.detail,
                actor=event.actor,
                phase=event.phase,
                status=event.status,
                ref=event.ref,
                payload=_parse_payload(event.payload),
                created_at=event.created_at,
            )
            for event in events
        ]
