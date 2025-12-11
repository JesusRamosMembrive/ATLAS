# SPDX-License-Identifier: MIT
"""
Persistencia y modelo de configuración de la aplicación.
"""

from __future__ import annotations

import os
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Mapping, Optional, Tuple
import logging

from sqlmodel import Session

from .scanner import DEFAULT_EXCLUDED_DIRS
from .database import get_engine, init_db, get_db_path
from .models import AppSettingsDB

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


def _load_settings_from_db(
    db_path: Path,
    default_root: Path,
    *,
    default_include_docstrings: bool = True,
) -> Optional[AppSettings]:
    """Carga la configuración desde la base de datos SQLite si existe."""
    engine = get_engine(db_path)
    init_db(engine)  # Asegura que las tablas existan

    with Session(engine) as session:
        db_settings = session.get(AppSettingsDB, 1)

        if not db_settings:
            return None

        # Convertir JSON a lista
        exclude_dirs = db_settings.exclude_dirs or []

        return AppSettings(
            root_path=Path(db_settings.root_path),
            exclude_dirs=_normalize_exclusions(exclude_dirs),
            include_docstrings=db_settings.include_docstrings,
            ollama_insights_enabled=db_settings.ollama_insights_enabled,
            ollama_insights_model=db_settings.ollama_insights_model,
            ollama_insights_frequency_minutes=db_settings.ollama_insights_frequency_minutes,
            ollama_insights_focus=db_settings.ollama_insights_focus or "general",
            backend_url=db_settings.backend_url,
        )


def _save_settings_to_db(db_path: Path, settings: AppSettings) -> None:
    """Persiste la configuración actual en SQLite usando SQLModel."""
    engine = get_engine(db_path)
    init_db(engine)

    with Session(engine) as session:
        db_settings = session.get(AppSettingsDB, 1)
        if not db_settings:
            db_settings = AppSettingsDB(id=1)
            session.add(db_settings)

        db_settings.root_path = str(settings.root_path)
        db_settings.exclude_dirs = list(settings.exclude_dirs)
        db_settings.include_docstrings = settings.include_docstrings
        db_settings.ollama_insights_enabled = settings.ollama_insights_enabled
        db_settings.ollama_insights_model = settings.ollama_insights_model
        db_settings.ollama_insights_frequency_minutes = (
            settings.ollama_insights_frequency_minutes
        )
        db_settings.ollama_insights_focus = settings.ollama_insights_focus
        db_settings.backend_url = settings.backend_url

        session.commit()


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

    db_path = get_db_path()
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
    db_path = get_db_path()
    try:
        _save_settings_to_db(db_path, settings)
    except sqlite3.OperationalError as exc:
        logger.warning("No se pudo guardar la configuración en %s: %s", db_path, exc)


logger = logging.getLogger(__name__)
