# SPDX-License-Identifier: MIT
"""
Persistencia de resultados generados por el pipeline de insights de Ollama.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping, Optional

from sqlmodel import Session, select, desc, or_
from sqlalchemy import select as sa_select

from ..database import get_engine, init_db
from ..database_async import get_async_session, init_async_db
from ..models import OllamaInsightDB


@dataclass(frozen=True)
class StoredInsight:
    id: int
    model: str
    message: str
    generated_at: datetime
    root_path: Optional[str]


def _normalize_root(root: Optional[Path | str]) -> Optional[str]:
    if root is None:
        return None
    value = Path(root).expanduser().resolve()
    return value.as_posix()


def _normalize_path_map(env: Optional[Mapping[str, str]]) -> Optional[Path]:
    """Convert env mapping to database path if ENV_DB_PATH is present."""
    if not env:
        return None
    from ..database import ENV_DB_PATH

    p = env.get(ENV_DB_PATH)
    return Path(p) if p else None


def record_insight(
    *,
    model: str,
    message: str,
    raw: Mapping[str, object] | None = None,
    root_path: Optional[Path | str] = None,
    env: Optional[Mapping[str, str]] = None,
) -> int:
    """Persiste un insight generado automáticamente."""
    engine = get_engine(_normalize_path_map(env))
    init_db(engine)

    normalized_root = _normalize_root(root_path)
    payload = (
        json.dumps(raw, ensure_ascii=False, separators=(",", ":")) if raw else None
    )

    with Session(engine) as session:
        insight = OllamaInsightDB(
            model=model,
            message=message,
            raw_payload=payload,
            generated_at=datetime.now(timezone.utc),
            root_path=normalized_root,
        )
        session.add(insight)
        session.commit()
        session.refresh(insight)
        return insight.id or 0


def list_insights(
    *,
    limit: int = 20,
    root_path: Optional[Path | str] = None,
    env: Optional[Mapping[str, str]] = None,
) -> list[StoredInsight]:
    """Recupera insights ordenados por fecha descendente."""
    engine = get_engine(_normalize_path_map(env))
    init_db(engine)

    normalized_root = _normalize_root(root_path)

    with Session(engine) as session:
        statement = select(OllamaInsightDB)
        if normalized_root:
            statement = statement.where(
                or_(
                    OllamaInsightDB.root_path.is_(None),  # type: ignore[union-attr]
                    OllamaInsightDB.root_path == normalized_root,
                )
            )

        statement = statement.order_by(desc(OllamaInsightDB.generated_at)).limit(limit)
        results = session.exec(statement).all()

        return [
            StoredInsight(
                id=item.id or 0,
                model=item.model,
                message=item.message,
                generated_at=item.generated_at,
                root_path=item.root_path,
            )
            for item in results
        ]


def clear_insights(
    *,
    root_path: Optional[Path | str] = None,
    env: Optional[Mapping[str, str]] = None,
) -> int:
    """Elimina insights almacenados. Si se indica root_path, borra sólo los asociados."""
    engine = get_engine(_normalize_path_map(env))
    init_db(engine)

    normalized_root = _normalize_root(root_path)

    with Session(engine) as session:
        if normalized_root:
            statement = select(OllamaInsightDB).where(
                or_(
                    OllamaInsightDB.root_path.is_(None),  # type: ignore[union-attr]
                    OllamaInsightDB.root_path == normalized_root,
                )
            )
        else:
            statement = select(OllamaInsightDB)

        results = session.exec(statement).all()
        count = len(results)

        for item in results:
            session.delete(item)

        session.commit()
        return count


# ============================================================================
# Async versions of storage functions (preferred for FastAPI endpoints)
# ============================================================================


async def record_insight_async(
    *,
    model: str,
    message: str,
    raw: Mapping[str, object] | None = None,
    root_path: Optional[Path | str] = None,
) -> int:
    """Persiste un insight generado automáticamente (async)."""
    await init_async_db()
    normalized_root = _normalize_root(root_path)
    payload = (
        json.dumps(raw, ensure_ascii=False, separators=(",", ":")) if raw else None
    )

    async with get_async_session() as session:
        insight = OllamaInsightDB(
            model=model,
            message=message,
            raw_payload=payload,
            generated_at=datetime.now(timezone.utc),
            root_path=normalized_root,
        )
        session.add(insight)
        await session.flush()
        await session.refresh(insight)
        return insight.id or 0


async def list_insights_async(
    *,
    limit: int = 20,
    root_path: Optional[Path | str] = None,
) -> list[StoredInsight]:
    """Recupera insights ordenados por fecha descendente (async)."""
    await init_async_db()
    normalized_root = _normalize_root(root_path)

    async with get_async_session() as session:
        statement = sa_select(OllamaInsightDB)
        if normalized_root:
            statement = statement.where(
                or_(
                    OllamaInsightDB.root_path.is_(None),  # type: ignore[union-attr]
                    OllamaInsightDB.root_path == normalized_root,
                )
            )

        statement = statement.order_by(desc(OllamaInsightDB.generated_at)).limit(limit)

        result = await session.execute(statement)
        items = result.scalars().all()

        return [
            StoredInsight(
                id=item.id or 0,
                model=item.model,
                message=item.message,
                generated_at=item.generated_at,
                root_path=item.root_path,
            )
            for item in items
        ]


async def clear_insights_async(
    *,
    root_path: Optional[Path | str] = None,
) -> int:
    """Elimina insights almacenados (async)."""
    await init_async_db()
    normalized_root = _normalize_root(root_path)

    async with get_async_session() as session:
        if normalized_root:
            statement = sa_select(OllamaInsightDB).where(
                or_(
                    OllamaInsightDB.root_path.is_(None),  # type: ignore[union-attr]
                    OllamaInsightDB.root_path == normalized_root,
                )
            )
        else:
            statement = sa_select(OllamaInsightDB)

        result = await session.execute(statement)
        items = result.scalars().all()
        count = len(items)

        for item in items:
            await session.delete(item)

        return count
