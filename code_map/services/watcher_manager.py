# SPDX-License-Identifier: MIT
"""
Wrapper para gestionar el ciclo de vida del WatcherService.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from ..watcher import WatcherService
from ..scheduler import ChangeScheduler


@dataclass(frozen=True)
class WatcherConfig:
    root_path: Path
    scheduler: ChangeScheduler
    exclude_dirs: Iterable[str]
    extensions: Iterable[str]


class WatcherManager:
    """Gestiona start/stop/rebuild del watcher subyacente."""

    def __init__(self, config: WatcherConfig) -> None:
        self._config = config
        self._service = self._build_service(config)

    def start(self) -> bool:
        return self._service.start() if self._service else False

    def stop(self) -> None:
        if self._service:
            self._service.stop()

    @property
    def is_running(self) -> bool:
        return bool(self._service and self._service.is_running)

    def rebuild(self, config: WatcherConfig) -> None:
        """Detiene el watcher actual y crea uno nuevo con la nueva config."""
        self.stop()
        self._config = config
        self._service = self._build_service(config)

    def _build_service(self, config: WatcherConfig) -> WatcherService:
        return WatcherService(
            config.root_path,
            config.scheduler,
            exclude_dirs=set(config.exclude_dirs),
            extensions=set(config.extensions),
        )
