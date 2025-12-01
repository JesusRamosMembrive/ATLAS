# SPDX-License-Identifier: MIT
"""
Persistencia y modelo de configuración de la aplicación.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
import sqlite3
from pathlib import Path
from typing import Iterable, Mapping, Optional, Tuple
import logging

from .constants import META_DIR_NAME
from .scanner import DEFAULT_EXCLUDED_DIRS

ENV_ROOT_PATH = "CODE_MAP_ROOT"
ENV_INCLUDE_DOCSTRINGS = "CODE_MAP_INCLUDE_DOCSTRINGS"
ENV_DB_PATH = "CODE_MAP_DB_PATH"
ENV_DISABLE_LINTERS = "CODE_MAP_DISABLE_LINTERS"
ENV_CACHE_DIR = "CODE_MAP_CACHE_DIR"
ENV_SKIP_INITIAL_SCAN = "CODE_MAP_SKIP_INITIAL_SCAN"
SETTINGS_VERSION = 2
DB_FILENAME = "state.db"


def _normalize_exclusions(additional: Iterable[str] | None = None) -> Tuple[str, ...]:
    """Combina las exclusiones por defecto con exclusiones adicionales."""
    base = set(DEFAULT_EXCLUDED_DIRS)
    if additional:
        for item in additional:
            if not item:
                continue
            normalized = item.strip()
            if not normalized:
                continue
            if normalized.startswith("/"):
                continue
            base.add(normalized)
    return tuple(sorted(base))


@dataclass(frozen=True)
class AppSettings:
    """Define la configuración de la aplicación."""

    root_path: Path
    exclude_dirs: Tuple[str, ...] = field(default_factory=tuple)
    include_docstrings: bool = True
    ollama_insights_enabled: bool = False
    ollama_insights_model: Optional[str] = None
    ollama_insights_frequency_minutes: Optional[int] = None
    ollama_insights_focus: Optional[str] = "general"
    backend_url: Optional[str] = None

    def to_payload(self) -> dict:
        """Convierte la configuración a un diccionario serializable."""
        return {
            "root_path": str(self.root_path),
            "exclude_dirs": list(self.exclude_dirs),
            "include_docstrings": self.include_docstrings,
            "ollama_insights_enabled": self.ollama_insights_enabled,
            "ollama_insights_model": self.ollama_insights_model,
            "ollama_insights_frequency_minutes": self.ollama_insights_frequency_minutes,
            "ollama_insights_focus": self.ollama_insights_focus or "general",
            "backend_url": self.backend_url,
            "version": SETTINGS_VERSION,
        }

    def with_updates(
        self,
        *,
        root_path: Path | None = None,
        include_docstrings: bool | None = None,
        exclude_dirs: Iterable[str] | None = None,
        ollama_insights_enabled: bool | None = None,
        ollama_insights_model: Optional[str] = None,
        ollama_insights_frequency_minutes: Optional[int] = None,
        ollama_insights_focus: Optional[str] = None,
        backend_url: Optional[str] = None,
    ) -> "AppSettings":
        """Crea una nueva instancia de AppSettings con actualizaciones."""

        def _normalize_focus(value: Optional[str]) -> Optional[str]:
            if value is None:
                return self.ollama_insights_focus
            if isinstance(value, str):
                stripped = value.strip()
                return stripped or None
            return None

        return AppSettings(
            root_path=(root_path or self.root_path).expanduser().resolve(),
            exclude_dirs=(
                _normalize_exclusions(exclude_dirs)
                if exclude_dirs is not None
                else self.exclude_dirs
            ),
            include_docstrings=(
                include_docstrings
                if include_docstrings is not None
                else self.include_docstrings
            ),
            ollama_insights_enabled=(
                ollama_insights_enabled
                if ollama_insights_enabled is not None
                else self.ollama_insights_enabled
            ),
            ollama_insights_model=(
                ollama_insights_model.strip()
                if isinstance(ollama_insights_model, str)
                and ollama_insights_model.strip()
                else (
                    self.ollama_insights_model
                    if ollama_insights_model is None
                    else None
                )
            ),
            ollama_insights_frequency_minutes=(
                ollama_insights_frequency_minutes
                if ollama_insights_frequency_minutes is not None
                else self.ollama_insights_frequency_minutes
            ),
            ollama_insights_focus=_normalize_focus(ollama_insights_focus),
            backend_url=(
                backend_url.strip()
                if isinstance(backend_url, str) and backend_url.strip()
                else (self.backend_url if backend_url is None else None)
            ),
        )


def _parse_env_flag(raw: Optional[str]) -> Optional[bool]:
    """Parsea una variable de entorno como un booleano."""
    if raw is None:
        return None
    value = raw.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    return None


def should_skip_initial_scan(env: Optional[Mapping[str, str]] = None) -> bool:
    """Determina si se debe saltar el escaneo inicial."""
    effective_env: Mapping[str, str] = env or os.environ
    flag = _parse_env_flag(effective_env.get(ENV_SKIP_INITIAL_SCAN))
    return flag is True


def _coerce_path(value: Optional[str | Path]) -> Optional[Path]:
    """Convierte un valor a una ruta absoluta."""
    if value is None:
        return None
    return Path(value).expanduser().resolve()


def database_path(env: Optional[Mapping[str, str]] = None) -> Path:
    """Obtiene la ruta del archivo SQLite para estado global."""
    effective_env: Mapping[str, str] = env or os.environ
    custom_path = effective_env.get(ENV_DB_PATH)
    if custom_path:
        return Path(custom_path).expanduser().resolve()
    return Path.home() / META_DIR_NAME / DB_FILENAME


def open_database(env: Optional[Mapping[str, str]] = None) -> sqlite3.Connection:
    """Abre una conexión a la base de datos y asegura el esquema."""
    path = database_path(env)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    _ensure_db_schema(connection)
    return connection


def _ensure_db_schema(connection: sqlite3.Connection) -> None:
    """Crea la tabla de configuración si no existe."""
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS app_settings (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            root_path TEXT NOT NULL,
            exclude_dirs TEXT NOT NULL,
            include_docstrings INTEGER NOT NULL,
            ollama_insights_enabled INTEGER NOT NULL DEFAULT 0,
            ollama_insights_model TEXT,
            ollama_insights_frequency_minutes INTEGER,
            ollama_insights_focus TEXT,
            updated_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
        )
        """
    )

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS linter_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            generated_at TEXT NOT NULL,
            root_path TEXT NOT NULL,
            overall_status TEXT NOT NULL,
            issues_total INTEGER NOT NULL DEFAULT 0,
            critical_issues INTEGER NOT NULL DEFAULT 0,
            payload TEXT NOT NULL
        )
        """
    )

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_linter_reports_generated_at
            ON linter_reports(generated_at DESC)
        """
    )

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT NOT NULL,
            channel TEXT NOT NULL,
            severity TEXT NOT NULL,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            payload TEXT,
            root_path TEXT,
            read INTEGER NOT NULL DEFAULT 0
        )
        """
    )

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_notifications_created_at
            ON notifications(created_at DESC)
        """
    )

    connection.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_notifications_root_path
            ON notifications(root_path)
        """
    )

    # Asegurar columna ollama_insights_enabled en instalaciones existentes.
    cursor = connection.execute("PRAGMA table_info(app_settings)")
    columns = {row["name"] for row in cursor.fetchall()}

    def _ensure_column(name: str, ddl: str) -> None:
        if name in columns:
            return
        try:
            connection.execute(ddl)
            connection.commit()
        except sqlite3.OperationalError:
            pass

    _ensure_column(
        "ollama_insights_enabled",
        "ALTER TABLE app_settings ADD COLUMN ollama_insights_enabled INTEGER NOT NULL DEFAULT 0",
    )
    _ensure_column(
        "ollama_insights_model",
        "ALTER TABLE app_settings ADD COLUMN ollama_insights_model TEXT",
    )
    _ensure_column(
        "ollama_insights_frequency_minutes",
        "ALTER TABLE app_settings ADD COLUMN ollama_insights_frequency_minutes INTEGER",
    )
    _ensure_column(
        "ollama_insights_focus",
        "ALTER TABLE app_settings ADD COLUMN ollama_insights_focus TEXT",
    )
    _ensure_column(
        "backend_url",
        "ALTER TABLE app_settings ADD COLUMN backend_url TEXT",
    )

    connection.commit()


def _load_settings_from_db(
    db_path: Path,
    default_root: Path,
    *,
    default_include_docstrings: bool = True,
) -> Optional[AppSettings]:
    """Carga la configuración desde la base de datos SQLite si existe."""
    with open_database(env={ENV_DB_PATH: str(db_path)}) as connection:
        insights_supported = True
        try:
            cursor = connection.execute(
                """
                SELECT
                    root_path,
                    exclude_dirs,
                    include_docstrings,
                    ollama_insights_enabled,
                    ollama_insights_model,
                    ollama_insights_frequency_minutes,
                    ollama_insights_focus,
                    backend_url
                FROM app_settings WHERE id = 1
                """
            )
        except sqlite3.OperationalError:
            insights_supported = False
            cursor = connection.execute(
                "SELECT root_path, exclude_dirs, include_docstrings FROM app_settings WHERE id = 1"
            )
        row = cursor.fetchone()
        if row is None:
            return None

        stored_root_raw = row["root_path"]
        stored_root = (
            Path(stored_root_raw).expanduser().resolve()
            if stored_root_raw
            else default_root
        )
        excludes_raw = row["exclude_dirs"] or "[]"
        try:
            data = json.loads(excludes_raw)
        except json.JSONDecodeError:
            data = []

        include_flag = (
            bool(row["include_docstrings"])
            if row["include_docstrings"] is not None
            else default_include_docstrings
        )
        if insights_supported and "ollama_insights_enabled" in row.keys():
            insights_raw = row["ollama_insights_enabled"]
            insights_flag = bool(insights_raw) if insights_raw is not None else False

            model_value_raw = (
                row["ollama_insights_model"]
                if "ollama_insights_model" in row.keys()
                else None
            )
            model_value = (
                model_value_raw.strip()
                if isinstance(model_value_raw, str) and model_value_raw.strip()
                else None
            )

            freq_raw = (
                row["ollama_insights_frequency_minutes"]
                if "ollama_insights_frequency_minutes" in row.keys()
                else None
            )
            try:
                freq_value = int(freq_raw) if freq_raw is not None else None
            except (TypeError, ValueError):
                freq_value = None
            focus_raw = (
                row["ollama_insights_focus"]
                if "ollama_insights_focus" in row.keys()
                else None
            )
            focus_value = (
                focus_raw.strip()
                if isinstance(focus_raw, str) and focus_raw.strip()
                else "general"
            )
        else:
            insights_flag = False
            model_value = None
            freq_value = None
            focus_value = "general"

        # Load backend_url if available
        backend_url_value = None
        if insights_supported and "backend_url" in row.keys():
            backend_url_raw = row["backend_url"]
            backend_url_value = (
                backend_url_raw.strip()
                if isinstance(backend_url_raw, str) and backend_url_raw.strip()
                else None
            )

        effective_root = stored_root if stored_root.exists() else default_root

        return AppSettings(
            root_path=effective_root,
            exclude_dirs=_normalize_exclusions(data),
            include_docstrings=include_flag,
            ollama_insights_enabled=insights_flag,
            ollama_insights_model=model_value,
            ollama_insights_frequency_minutes=freq_value,
            ollama_insights_focus=focus_value,
            backend_url=backend_url_value,
        )


def _save_settings_to_db(db_path: Path, settings: AppSettings) -> None:
    """Persiste la configuración actual en SQLite."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with open_database(env={ENV_DB_PATH: str(db_path)}) as connection:
        cursor = connection.execute("PRAGMA table_info(app_settings)")
        columns = {row["name"] for row in cursor.fetchall()}

        def ensure_column(name: str, ddl: str) -> bool:
            if name in columns:
                return True
            try:
                connection.execute(ddl)
                connection.commit()
                columns.add(name)
                return True
            except sqlite3.OperationalError:
                return False

        has_insights_column = ensure_column(
            "ollama_insights_enabled",
            "ALTER TABLE app_settings ADD COLUMN ollama_insights_enabled INTEGER NOT NULL DEFAULT 0",
        )
        has_model_column = ensure_column(
            "ollama_insights_model",
            "ALTER TABLE app_settings ADD COLUMN ollama_insights_model TEXT",
        )
        has_frequency_column = ensure_column(
            "ollama_insights_frequency_minutes",
            "ALTER TABLE app_settings ADD COLUMN ollama_insights_frequency_minutes INTEGER",
        )
        has_focus_column = ensure_column(
            "ollama_insights_focus",
            "ALTER TABLE app_settings ADD COLUMN ollama_insights_focus TEXT",
        )
        has_backend_url_column = ensure_column(
            "backend_url",
            "ALTER TABLE app_settings ADD COLUMN backend_url TEXT",
        )
        can_persist_insights = (
            has_insights_column
            and has_model_column
            and has_frequency_column
            and has_focus_column
        )
        can_persist_backend_url = has_backend_url_column

        if can_persist_insights and can_persist_backend_url:
            connection.execute(
                """
                INSERT INTO app_settings (
                    id,
                    root_path,
                    exclude_dirs,
                    include_docstrings,
                    ollama_insights_enabled,
                    ollama_insights_model,
                    ollama_insights_frequency_minutes,
                    ollama_insights_focus,
                    backend_url,
                    updated_at
                )
                VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, strftime('%Y-%m-%dT%H:%M:%fZ','now'))
                ON CONFLICT(id) DO UPDATE SET
                    root_path = excluded.root_path,
                    exclude_dirs = excluded.exclude_dirs,
                    include_docstrings = excluded.include_docstrings,
                    ollama_insights_enabled = excluded.ollama_insights_enabled,
                    ollama_insights_model = excluded.ollama_insights_model,
                    ollama_insights_frequency_minutes = excluded.ollama_insights_frequency_minutes,
                    ollama_insights_focus = excluded.ollama_insights_focus,
                    backend_url = excluded.backend_url,
                    updated_at = excluded.updated_at
                """,
                (
                    str(settings.root_path),
                    json.dumps(list(settings.exclude_dirs)),
                    1 if settings.include_docstrings else 0,
                    1 if settings.ollama_insights_enabled else 0,
                    settings.ollama_insights_model,
                    settings.ollama_insights_frequency_minutes,
                    settings.ollama_insights_focus,
                    settings.backend_url,
                ),
            )
        elif can_persist_insights:
            connection.execute(
                """
                INSERT INTO app_settings (
                    id,
                    root_path,
                    exclude_dirs,
                    include_docstrings,
                    ollama_insights_enabled,
                    ollama_insights_model,
                    ollama_insights_frequency_minutes,
                    ollama_insights_focus,
                    updated_at
                )
                VALUES (1, ?, ?, ?, ?, ?, ?, ?, strftime('%Y-%m-%dT%H:%M:%fZ','now'))
                ON CONFLICT(id) DO UPDATE SET
                    root_path = excluded.root_path,
                    exclude_dirs = excluded.exclude_dirs,
                    include_docstrings = excluded.include_docstrings,
                    ollama_insights_enabled = excluded.ollama_insights_enabled,
                    ollama_insights_model = excluded.ollama_insights_model,
                    ollama_insights_frequency_minutes = excluded.ollama_insights_frequency_minutes,
                    ollama_insights_focus = excluded.ollama_insights_focus,
                    updated_at = excluded.updated_at
                """,
                (
                    str(settings.root_path),
                    json.dumps(list(settings.exclude_dirs)),
                    1 if settings.include_docstrings else 0,
                    1 if settings.ollama_insights_enabled else 0,
                    settings.ollama_insights_model,
                    settings.ollama_insights_frequency_minutes,
                    settings.ollama_insights_focus,
                ),
            )
        else:
            connection.execute(
                """
                INSERT INTO app_settings (id, root_path, exclude_dirs, include_docstrings, updated_at)
                VALUES (1, ?, ?, ?, strftime('%Y-%m-%dT%H:%M:%fZ','now'))
                ON CONFLICT(id) DO UPDATE SET
                    root_path = excluded.root_path,
                    exclude_dirs = excluded.exclude_dirs,
                    include_docstrings = excluded.include_docstrings,
                    updated_at = excluded.updated_at
                """,
                (
                    str(settings.root_path),
                    json.dumps(list(settings.exclude_dirs)),
                    1 if settings.include_docstrings else 0,
                ),
            )
        connection.commit()


def load_settings(
    *,
    root_override: Optional[str | Path] = None,
    env: Optional[Mapping[str, str]] = None,
) -> AppSettings:
    """Carga la configuración de la aplicación desde el disco y el entorno."""
    effective_env: Mapping[str, str] = env or os.environ

    env_root = _coerce_path(effective_env.get(ENV_ROOT_PATH))
    override_path = _coerce_path(root_override)
    base_root = override_path or env_root or Path.cwd().expanduser().resolve()

    include_flag = _parse_env_flag(effective_env.get(ENV_INCLUDE_DOCSTRINGS))
    default_include = include_flag if include_flag is not None else True

    db_path = database_path(effective_env)
    settings = _load_settings_from_db(
        db_path,
        base_root,
        default_include_docstrings=default_include,
    )

    if settings is None:
        settings = AppSettings(
            root_path=base_root,
            exclude_dirs=_normalize_exclusions(),
            include_docstrings=default_include,
            ollama_insights_enabled=False,
            ollama_insights_focus="general",
        )
        _save_settings_to_db(db_path, settings)

    if not settings.root_path.exists() or not settings.root_path.is_dir():
        logger.warning(
            "La ruta almacenada %s no es válida; usando %s como nueva raíz",
            settings.root_path,
            base_root,
        )
        settings = settings.with_updates(root_path=base_root)

    if (override_path or env_root) and settings.root_path != base_root:
        settings = settings.with_updates(root_path=base_root)

    if include_flag is not None and settings.include_docstrings != include_flag:
        settings = settings.with_updates(include_docstrings=include_flag)

    return settings


def save_settings(
    settings: AppSettings, *, env: Optional[Mapping[str, str]] = None
) -> None:
    """Guarda la configuración en el disco."""
    db_path = database_path(env)
    try:
        _save_settings_to_db(db_path, settings)
    except sqlite3.OperationalError as exc:
        logger.warning("No se pudo guardar la configuración en %s: %s", db_path, exc)


logger = logging.getLogger(__name__)
