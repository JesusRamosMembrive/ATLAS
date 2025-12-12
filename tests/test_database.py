# SPDX-License-Identifier: MIT
"""
Tests for the database module and SQLModel integration.
"""

from pathlib import Path
import pytest
from sqlmodel import Session, select

from code_map.database import get_engine, init_db
from code_map.models import AppSettingsDB
from code_map.settings import AppSettings, _save_settings_to_db, _load_settings_from_db


@pytest.fixture(name="db_path")
def fixture_db_path(tmp_path: Path) -> Path:
    """Return a temporary database path."""
    return tmp_path / "test_state.db"


@pytest.fixture(name="engine")
def fixture_engine(db_path: Path):
    """Create a new engine and initialize the DB for testing."""
    engine = get_engine(db_path)
    init_db(engine)
    return engine


def test_init_db(engine):
    """Test that tables are expectedly created."""
    # Check if tables exist by querying sqlite_master
    with engine.connect() as conn:
        # Direct SQL query to check tables
        from sqlalchemy import text

        result = conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table';")
        )
        tables = result.fetchall()
        table_names = {t[0] for t in tables}
        assert "app_settings" in table_names
        assert "linter_reports" in table_names
        assert "notifications" in table_names


def test_save_and_load_settings(db_path: Path):
    """Test saving and loading settings via the settings module helpers."""

    # 1. Create a dummy AppSettings object
    initial_settings = AppSettings(
        root_path=Path("/tmp/test_root"),
        exclude_dirs=("node_modules", ".git"),
        include_docstrings=False,
        ollama_insights_enabled=True,
        ollama_insights_model="llama3",
        ollama_insights_frequency_minutes=45,
        ollama_insights_focus="security",
    )

    # 2. Save it
    _save_settings_to_db(db_path, initial_settings)

    # 3. Load it back
    loaded_settings = _load_settings_from_db(
        db_path, Path("/default"), default_include_docstrings=True
    )

    # 4. Verify match
    assert loaded_settings is not None
    assert str(loaded_settings.root_path) == "/tmp/test_root"
    assert "node_modules" in loaded_settings.exclude_dirs
    assert ".git" in loaded_settings.exclude_dirs
    assert loaded_settings.include_docstrings is False
    assert loaded_settings.ollama_insights_enabled is True
    assert loaded_settings.ollama_insights_model == "llama3"
    assert loaded_settings.ollama_insights_frequency_minutes == 45
    assert loaded_settings.ollama_insights_focus == "security"


def test_update_settings_preserves_id(db_path: Path):
    """Test that updating settings keeps the same row (ID=1)."""

    settings_v1 = AppSettings(root_path=Path("/tmp/v1"), include_docstrings=True)
    _save_settings_to_db(db_path, settings_v1)

    settings_v2 = AppSettings(root_path=Path("/tmp/v2"), include_docstrings=False)
    _save_settings_to_db(db_path, settings_v2)

    engine = get_engine(db_path)
    with Session(engine) as session:
        rows = session.exec(select(AppSettingsDB)).all()
        assert len(rows) == 1
        assert rows[0].id == 1
        assert rows[0].root_path == "/tmp/v2"
        assert rows[0].include_docstrings is False
