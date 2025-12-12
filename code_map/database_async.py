# SPDX-License-Identifier: MIT
"""
Async database connection and session handling using SQLAlchemy async.

This module provides async database operations for FastAPI endpoints,
using aiosqlite as the async driver for SQLite.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlmodel import SQLModel

from .constants import META_DIR_NAME
from .database import DB_FILENAME, ENV_DB_PATH

# Singleton instances for connection pooling
_async_engine: AsyncEngine | None = None
_async_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_db_path() -> Path:
    """Get the path to the SQLite database from environment or default."""
    custom_path = os.environ.get(ENV_DB_PATH)
    if custom_path:
        return Path(custom_path).expanduser().resolve()
    return Path.home() / META_DIR_NAME / DB_FILENAME


def get_async_engine(db_path: Path | None = None) -> AsyncEngine:
    """Get or create the async database engine (singleton).

    Args:
        db_path: Optional custom database path. If not provided, uses default.

    Returns:
        AsyncEngine instance for the SQLite database.
    """
    global _async_engine

    if _async_engine is not None:
        return _async_engine

    path = db_path or get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)

    sqlite_url = f"sqlite+aiosqlite:///{path}"
    _async_engine = create_async_engine(
        sqlite_url,
        echo=False,
        future=True,
    )
    return _async_engine


async def init_async_db(engine: AsyncEngine | None = None) -> None:
    """Initialize the database schema asynchronously.

    Args:
        engine: Optional engine to use. If not provided, uses the singleton.
    """
    eng = engine or get_async_engine()
    async with eng.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


def get_async_session_factory(
    engine: AsyncEngine | None = None,
) -> async_sessionmaker[AsyncSession]:
    """Get or create the async session factory (singleton).

    Args:
        engine: Optional engine to use. If not provided, uses the singleton.

    Returns:
        Async session factory configured for the engine.
    """
    global _async_session_factory

    if _async_session_factory is not None:
        return _async_session_factory

    eng = engine or get_async_engine()
    _async_session_factory = async_sessionmaker(
        eng,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    return _async_session_factory


@asynccontextmanager
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Context manager for getting an async database session.

    Automatically commits on success and rolls back on error.

    Usage:
        async with get_async_session() as session:
            result = await session.execute(select(Model))
            ...
    """
    factory = get_async_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def close_async_engine() -> None:
    """Close the async engine and release all connections.

    Call this during application shutdown to clean up resources.
    """
    global _async_engine, _async_session_factory

    if _async_engine is not None:
        await _async_engine.dispose()
        _async_engine = None
        _async_session_factory = None


def reset_async_engine() -> None:
    """Reset the singleton engine (useful for testing).

    This synchronously clears the engine reference without disposing.
    Use close_async_engine() for proper cleanup.
    """
    global _async_engine, _async_session_factory
    _async_engine = None
    _async_session_factory = None
