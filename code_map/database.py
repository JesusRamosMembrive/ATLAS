# SPDX-License-Identifier: MIT
"""
Database connection and session handling using SQLModel.
"""

import os
from pathlib import Path
from typing import Generator

from sqlmodel import Session, SQLModel, create_engine
from sqlalchemy import Engine

from .constants import META_DIR_NAME

# Default database filename
DB_FILENAME = "state.db"
ENV_DB_PATH = "CODE_MAP_DB_PATH"


def get_db_path() -> Path:
    """Get the path to the SQLite database from environment or default."""
    custom_path = os.environ.get(ENV_DB_PATH)
    if custom_path:
        return Path(custom_path).expanduser().resolve()
    return Path.home() / META_DIR_NAME / DB_FILENAME


def get_engine(db_path: Path | None = None) -> Engine:
    """Create and return a database engine."""
    path = db_path or get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    sqlite_url = f"sqlite:///{path}"
    # check_same_thread=False is needed if sharing connection across threads (FastAPI)
    return create_engine(sqlite_url, connect_args={"check_same_thread": False})


def init_db(engine: Engine) -> None:
    """Initialize the database schema."""
    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    """Dependency for getting a database session."""
    engine = get_engine()
    with Session(engine) as session:
        yield session
