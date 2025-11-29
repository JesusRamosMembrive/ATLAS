# SPDX-License-Identifier: MIT
"""
Servicio de watcher basado en watchdog para detectar cambios en proyectos Python.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Iterable, Optional, Set, TYPE_CHECKING

from .events import ChangeEventType
from .constants import DEFAULT_EXCLUDED_DIRS
from .scheduler import ChangeScheduler

if TYPE_CHECKING:  # pragma: no cover - solo para tipado
    from watchdog.events import FileMovedEvent, FileSystemEvent, FileSystemEventHandler
    from watchdog.observers import Observer
else:  # pragma: no cover - en tiempo de ejecución permitimos fallback
    try:
        from watchdog.events import (
            FileSystemEventHandler,
            FileSystemEvent,
            FileMovedEvent,
        )
        from watchdog.observers import Observer
    except ImportError:

        class FileSystemEvent:  # type: ignore[too-few-public-methods]
            src_path: str = ""
            dest_path: Optional[str] = None
            is_directory: bool = False

        class FileMovedEvent(FileSystemEvent):  # type: ignore[too-few-public-methods]
            pass

        class FileSystemEventHandler:  # type: ignore[too-few-public-methods]
            pass

        Observer = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

EXCLUDED_DEFAULT: Set[str] = set(DEFAULT_EXCLUDED_DIRS)


class _EventHandler(FileSystemEventHandler):
    """Encapsula la conversión de eventos watchdog a ChangeEventType."""

    def __init__(
        self,
        root: Path,
        scheduler: ChangeScheduler,
        exclude_dirs: Set[str],
        extensions: Set[str],
    ) -> None:
        """Configura el manejador con la raíz monitoreada y filtros activos."""
        self.root = root
        self.scheduler = scheduler
        self.exclude_dirs = exclude_dirs
        self.extensions = extensions

    def on_created(self, event: FileSystemEvent) -> None:
        """Registra la creación de un archivo con extensión soportada."""
        self._dispatch(ChangeEventType.CREATED, event)

    def on_modified(self, event: FileSystemEvent) -> None:
        """Registra la modificación de un archivo con extensión soportada."""
        self._dispatch(ChangeEventType.MODIFIED, event)

    def on_deleted(self, event: FileSystemEvent) -> None:
        """Registra la eliminación de un archivo con extensión soportada."""
        self._dispatch(ChangeEventType.DELETED, event)

    def on_moved(self, event: FileSystemEvent) -> None:
        """Registra el movimiento o renombrado de un archivo."""
        self._dispatch(ChangeEventType.MOVED, event)

    def _dispatch(
        self,
        event_type: ChangeEventType,
        event: FileSystemEvent,
    ) -> None:
        """Filtra y transforma el evento recibido antes de encolarlo."""
        if getattr(event, "is_directory", False):
            return

        src_path = Path(getattr(event, "src_path", "")).resolve()
        if not self._should_track(src_path):
            return

        if event_type is ChangeEventType.MOVED:
            dest_path_raw = getattr(event, "dest_path", None)
            dest_path = Path(dest_path_raw).resolve() if dest_path_raw else None
            if dest_path and not self._should_track(dest_path):
                dest_path = None
            self.scheduler.enqueue(
                ChangeEventType.MOVED,
                src_path,
                dest_path=dest_path,
            )
            return

        self.scheduler.enqueue(event_type, src_path)

    def _should_track(self, path: Path) -> bool:
        """Determina si la ruta debe generar eventos de cambio."""
        if not path.exists():
            return path.suffix.lower() in self.extensions

        if not self._within_root(path):
            return False

        if self._is_excluded(path):
            return False

        if path.suffix.lower() not in self.extensions:
            return False

        return True

    def _within_root(self, path: Path) -> bool:
        """Comprueba si la ruta pertenece al árbol monitoreado."""
        try:
            path.resolve().relative_to(self.root)
            return True
        except ValueError:
            return False

    def _is_excluded(self, path: Path) -> bool:
        """Verifica si alguna parte de la ruta está excluida."""
        for part in path.parts:
            if part in self.exclude_dirs:
                return True
            if part.startswith(".") and part != self.root.name:
                return True
        return False


class WatcherService:
    """Servicio que gestiona el ciclo de vida de watchdog para un proyecto."""

    def __init__(
        self,
        root: Path,
        scheduler: ChangeScheduler,
        *,
        exclude_dirs: Optional[Iterable[str]] = None,
        extensions: Optional[Iterable[str]] = None,
    ) -> None:
        """Inicializa el servicio con los filtros y extensiones relevantes."""
        self.root = Path(root).expanduser().resolve()
        self.scheduler = scheduler
        self.exclude_dirs: Set[str] = set(EXCLUDED_DEFAULT)
        if exclude_dirs:
            self.exclude_dirs.update(exclude_dirs)
        self.extensions: Set[str] = {
            ext if ext.startswith(".") else f".{ext}" for ext in (extensions or [".py"])
        }
        self._observer: Optional[Any] = None

    @property
    def is_running(self) -> bool:
        """Indica si el observador de archivos está activo."""
        return self._observer is not None

    def start(self) -> bool:
        """Inicia el observador si watchdog está disponible."""
        if Observer is None:
            logger.warning("watchdog no está disponible; watcher deshabilitado")
            return False

        if self.is_running:
            return True

        handler = _EventHandler(
            self.root, self.scheduler, self.exclude_dirs, self.extensions
        )
        observer = Observer()
        observer.schedule(handler, str(self.root), recursive=True)
        observer.start()
        self._observer = observer
        logger.info("Watcher iniciado en %s", self.root)
        return True

    def stop(self) -> None:
        """Detiene el observador y espera a que finalice."""
        observer = self._observer
        if not observer:
            return
        observer.stop()
        observer.join()
        self._observer = None
        logger.info("Watcher detenido en %s", self.root)
