# SPDX-License-Identifier: MIT
"""
Estado compartido de la aplicación FastAPI.
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Mapping

from .cache import SnapshotStore
from .index import SymbolIndex
from .scanner import ProjectScanner
from .scheduler import ChangeScheduler
from .settings import AppSettings, save_settings, ENV_DISABLE_LINTERS, ENV_CACHE_DIR, should_skip_initial_scan
from .linters import (
    LinterRunOptions,
    get_latest_linters_report,
    LINTER_TIMEOUT_FAST,  # Re-export for consistency
)
from .stage_toolkit import stage_status as compute_stage_status
from .state_reporter import StateReporter
from .insights import VALID_INSIGHTS_FOCUS
from .services.linters_service import LintersService, LintersConfig
from .services.insights_service import InsightsService, InsightsConfig
from .services.watcher_manager import WatcherManager, WatcherConfig

logger = logging.getLogger(__name__)

# Application timing constants
DEFAULT_INSIGHTS_INTERVAL_MINUTES = 60
LINTERS_MIN_INTERVAL_SECONDS = (
    LINTER_TIMEOUT_FAST  # Default minimum interval between linter runs
)
MAX_RECENT_CHANGES_TRACKED = 50  # Limit event notifications to avoid memory bloat

VALID_INSIGHTS_FOCUS_SET = {focus.lower() for focus in VALID_INSIGHTS_FOCUS}


def _parse_enabled_tools_env(raw: Optional[str]) -> Optional[Set[str]]:
    if not raw:
        return None
    tokens = {token.strip().lower() for token in raw.split(",") if token.strip()}
    return tokens or None


def _parse_int_env(raw: Optional[str]) -> Optional[int]:
    if raw is None:
        return None
    try:
        value = int(raw.strip())
    except ValueError:
        return None
    return value if value >= 0 else None


def _linters_disabled_from_env() -> bool:
    return os.environ.get(ENV_DISABLE_LINTERS, "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


@dataclass
class AppState:
    """Estado compartido de la aplicación FastAPI."""

    settings: AppSettings
    scheduler: ChangeScheduler
    scanner: ProjectScanner = field(init=False)
    index: SymbolIndex = field(init=False)
    snapshot_store: SnapshotStore = field(init=False)
    watcher: WatcherManager = field(init=False)
    last_full_scan: Optional[datetime] = field(init=False, default=None)
    last_event_batch: Optional[datetime] = field(init=False, default=None)
    reporter: StateReporter = field(init=False)
    linters: LintersService = field(init=False)
    insights: InsightsService = field(init=False)

    def __post_init__(self) -> None:
        self.event_queue: "asyncio.Queue[Dict[str, Any]]" = asyncio.Queue()
        self._stop_event = asyncio.Event()
        self._scheduler_task: Optional[asyncio.Task[None]] = None
        self._recent_changes: List[str] = []

        self._build_components()
        self.insights.schedule()

    async def startup(self) -> None:
        """Inicializa el estado de la aplicación."""
        logger.info("Inicializando estado de la app para %s", self.settings.root_path)

        skip_scan = should_skip_initial_scan()
        if skip_scan:
            logger.info(
                "Saltando escaneo inicial (CODE_MAP_SKIP_INITIAL_SCAN=1). "
                "Configure la ruta del proyecto desde la UI."
            )
        else:
            await asyncio.to_thread(
                self.scanner.hydrate_index_from_snapshot,
                self.index,
                store=self.snapshot_store,
            )
            summaries = await asyncio.to_thread(
                self.scanner.scan_and_update_index,
                self.index,
                persist=True,
                store=self.snapshot_store,
            )
            if summaries:
                self.last_full_scan = datetime.now(timezone.utc)

            # Solo iniciar watcher si no estamos en modo skip
            started = await asyncio.to_thread(self.watcher.start)
            if not started:
                logger.warning("Watcher no iniciado (watchdog ausente o error).")

        self.linters.schedule(pending_changes=self.scheduler.pending_count())
        self.insights.schedule()
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())

    async def shutdown(self) -> None:
        """Detiene el estado de la aplicación."""
        logger.info("Deteniendo estado de la app")
        self._stop_event.set()
        await self.linters.shutdown()
        await self.insights.shutdown()
        if self._scheduler_task:
            await self._scheduler_task
        await asyncio.to_thread(self.watcher.stop)

    async def _scheduler_loop(self) -> None:
        """Bucle principal del programador de cambios."""
        while not self._stop_event.is_set():
            batch = await asyncio.to_thread(self.scheduler.drain, force=True)
            if batch:
                changes = await asyncio.to_thread(
                    self.scanner.apply_change_batch,
                    batch,
                    self.index,
                    persist=True,
                    store=self.snapshot_store,
                )
                payload = self._serialize_changes(changes)
                if payload["updated"] or payload["deleted"]:
                    self.last_event_batch = datetime.now(timezone.utc)
                    await self.event_queue.put(payload)
                    self.linters.schedule(
                        pending_changes=self.scheduler.pending_count()
                    )
                    self.insights.schedule()
            await asyncio.sleep(self.scheduler.debounce_seconds)

    def _serialize_changes(
        self, changes: Dict[str, Iterable[Path]]
    ) -> Dict[str, List[str]]:
        """Serializa los cambios para la notificación de eventos."""
        updated = [self.to_relative(path) for path in changes.get("updated", [])]
        deleted = [self.to_relative(path) for path in changes.get("deleted", [])]
        if updated or deleted:
            combined = (updated + deleted)[:MAX_RECENT_CHANGES_TRACKED]
            self._recent_changes = combined
        return {"updated": updated, "deleted": deleted}

    async def perform_full_scan(self) -> int:
        """Realiza un escaneo completo del proyecto."""
        summaries = await asyncio.to_thread(
            self.scanner.scan_and_update_index,
            self.index,
            persist=True,
            store=self.snapshot_store,
        )
        updated = [self.to_relative(summary.path) for summary in summaries]
        payload = {
            "updated": updated,
            "deleted": [],
        }
        if payload["updated"]:
            self.last_event_batch = datetime.now(timezone.utc)
            await self.event_queue.put(payload)
            self._recent_changes = updated[:MAX_RECENT_CHANGES_TRACKED]
        self.last_full_scan = datetime.now(timezone.utc)
        self.linters.schedule(pending_changes=self.scheduler.pending_count())
        self.insights.schedule()
        return len(summaries)

    def _compute_insights_next_run(self) -> Optional[datetime]:
        return self.insights.next_run

    async def _build_insights_context(self) -> str:
        parts: List[str] = []

        # Último reporte de linters
        report = await asyncio.to_thread(
            get_latest_linters_report,
            root_path=self.settings.root_path,
        )
        if report:
            summary = report.report.summary
            parts.append(
                (
                    "Reporte de linters más reciente "
                    f"({report.generated_at.isoformat()}): estado {summary.overall_status.value.upper()}, "
                    f"incidencias totales {summary.issues_total}, críticas {summary.critical_issues}."
                )
            )

        # Estado detectado del proyecto (stage)
        try:
            stage_payload = await compute_stage_status(
                self.settings.root_path, index=self.index
            )
        except Exception:  # pragma: no cover
            # Intentional broad exception: stage detection is optional, shouldn't break insights
            stage_payload = None

        detection_raw: Any = (
            stage_payload.get("detection") if isinstance(stage_payload, dict) else None
        )
        detection: Optional[Mapping[str, Any]] = (
            detection_raw if isinstance(detection_raw, Mapping) else None
        )
        if detection and detection.get("available"):
            recommended = detection.get("recommended_stage")
            confidence = detection.get("confidence")
            reasons = detection.get("reasons") or []
            formatted_reasons = (
                ", ".join(reasons[:3]) if reasons else "sin motivos destacados"
            )
            parts.append(
                (
                    f"Detección de etapa: Stage {recommended} (confianza {confidence}). "
                    f"Motivos: {formatted_reasons}."
                )
            )

        pending_events = self.event_queue.qsize()
        if pending_events:
            parts.append(f"Eventos de cambios pendientes en cola: {pending_events}.")

        if self._recent_changes:
            preview = ", ".join(self._recent_changes[:10])
            parts.append(f"Archivos recientes: {preview}.")

        if parts:
            return "\n".join(parts)
        return "Sin contexto adicional relevante disponible en linters o stage."

    def to_relative(self, path: Path) -> str:
        """Convierte una ruta absoluta en una ruta relativa al root del proyecto."""
        try:
            rel = path.resolve().relative_to(self.settings.root_path)
            return rel.as_posix()
        except ValueError:
            return path.resolve().as_posix()

    def resolve_path(self, relative: str) -> Path:
        """Resuelve una ruta relativa en una ruta absoluta dentro del root del proyecto."""
        candidate = (self.settings.root_path / relative).resolve()
        if not self._within_root(candidate):
            raise ValueError(f"Ruta fuera del root configurado: {relative}")
        return candidate

    def _within_root(self, path: Path) -> bool:
        """Comprueba si una ruta está dentro del root del proyecto."""
        try:
            path.resolve().relative_to(self.settings.root_path)
            return True
        except ValueError:
            return False

    def is_watcher_running(self) -> bool:
        """Comprueba si el observador de archivos está en ejecución."""
        return bool(self.watcher and self.watcher.is_running)

    def get_settings_payload(self) -> Dict[str, Any]:
        """Obtiene el payload de configuración para la API."""
        return self.reporter.settings_payload(watcher_active=self.is_watcher_running())

    def get_status_payload(self) -> Dict[str, Any]:
        """Obtiene el payload de estado para la API."""
        return self.reporter.status_payload(
            watcher_active=self.is_watcher_running(),
            last_full_scan=self.last_full_scan,
            last_event_batch=self.last_event_batch,
            pending_events=self.event_queue.qsize(),
            insights_last_run=self.insights.last_run,
            insights_next_run=self._compute_insights_next_run(),
            insights_last_model=(
                self.insights.last_result.model if self.insights.last_result else None
            ),
            insights_last_message=(
                self.insights.last_result.message if self.insights.last_result else None
            ),
            insights_last_error=self.insights.last_error,
        )

    async def update_settings(
        self,
        *,
        root_path: Optional[Path] = None,
        include_docstrings: Optional[bool] = None,
        exclude_dirs: Optional[Iterable[str]] = None,
        ollama_insights_enabled: Optional[bool] = None,
        ollama_insights_model: Optional[str] = None,
        ollama_insights_frequency_minutes: Optional[int] = None,
        ollama_insights_focus: Optional[str] = None,
        backend_url: Optional[str] = None,
    ) -> List[str]:
        """Actualiza la configuración de la aplicación."""
        if ollama_insights_frequency_minutes is not None:
            if ollama_insights_frequency_minutes <= 0:
                raise ValueError(
                    "La frecuencia de insights debe ser un entero positivo."
                )
            if ollama_insights_frequency_minutes > 24 * 60:
                raise ValueError(
                    "La frecuencia de insights no puede superar 1440 minutos."
                )

        focus_kwargs: Dict[str, Optional[str]] = {}
        if ollama_insights_focus is not None:
            normalized_focus = ollama_insights_focus.strip().lower()
            if not normalized_focus:
                # Permite restablecer a predeterminado
                focus_kwargs["ollama_insights_focus"] = ""
            elif normalized_focus not in VALID_INSIGHTS_FOCUS_SET:
                raise ValueError(
                    f"El enfoque de insights '{ollama_insights_focus}' no es válido. "
                    f"Opciones disponibles: {', '.join(sorted(VALID_INSIGHTS_FOCUS_SET))}."
                )
            else:
                focus_kwargs["ollama_insights_focus"] = normalized_focus

        new_settings = self.settings.with_updates(
            root_path=root_path,
            include_docstrings=include_docstrings,
            exclude_dirs=exclude_dirs,
            ollama_insights_enabled=ollama_insights_enabled,
            ollama_insights_model=ollama_insights_model,
            ollama_insights_frequency_minutes=ollama_insights_frequency_minutes,
            backend_url=backend_url,
            **focus_kwargs,
        )
        updated_fields: List[str] = []
        if new_settings.root_path != self.settings.root_path:
            if (
                not new_settings.root_path.exists()
                or not new_settings.root_path.is_dir()
            ):
                raise ValueError("La nueva ruta raíz no es válida o no existe.")
            updated_fields.append("root_path")
        if new_settings.include_docstrings != self.settings.include_docstrings:
            updated_fields.append("include_docstrings")
        if new_settings.exclude_dirs != self.settings.exclude_dirs:
            updated_fields.append("exclude_dirs")
        if (
            new_settings.ollama_insights_enabled
            != self.settings.ollama_insights_enabled
        ):
            updated_fields.append("ollama_insights_enabled")
        if new_settings.ollama_insights_model != self.settings.ollama_insights_model:
            updated_fields.append("ollama_insights_model")
        if (
            new_settings.ollama_insights_frequency_minutes
            != self.settings.ollama_insights_frequency_minutes
        ):
            updated_fields.append("ollama_insights_frequency_minutes")
        if new_settings.ollama_insights_focus != self.settings.ollama_insights_focus:
            updated_fields.append("ollama_insights_focus")
        if new_settings.backend_url != self.settings.backend_url:
            updated_fields.append("backend_url")

        if not updated_fields:
            return []

        await self._cancel_background_tasks()
        await self._apply_settings(new_settings)
        save_settings(self.settings)
        return updated_fields

    def _build_components(self) -> None:
        """(Re)construye los componentes de la aplicación a partir de la configuración."""
        self.scanner = ProjectScanner(
            self.settings.root_path,
            include_docstrings=self.settings.include_docstrings,
            exclude_dirs=self.settings.exclude_dirs,
        )
        self.index = SymbolIndex(self.settings.root_path)
        # Use alternative cache directory if specified (for Docker with read-only mounts)
        cache_dir = os.getenv(ENV_CACHE_DIR)
        cache_dir_path = Path(cache_dir) if cache_dir else None
        self.snapshot_store = SnapshotStore(
            self.settings.root_path, cache_dir=cache_dir_path
        )
        self.reporter = StateReporter(
            settings=self.settings,
            scanner=self.scanner,
            index=self.index,
        )
        self.watcher = WatcherManager(
            WatcherConfig(
                root_path=self.settings.root_path,
                scheduler=self.scheduler,
                exclude_dirs=self.settings.exclude_dirs,
                extensions=self.scanner.extensions,
            )
        )
        self.linters = LintersService(self._build_linters_config())
        self.insights = InsightsService(
            self._build_insights_config(), context_builder=self._build_insights_context
        )

    def _build_linters_config(self) -> LintersConfig:
        """Construye la configuración para el servicio de linters."""
        tools_env = os.environ.get("CODE_MAP_LINTERS_TOOLS")
        enabled_tools = _parse_enabled_tools_env(tools_env)
        max_files_env = os.environ.get("CODE_MAP_LINTERS_MAX_PROJECT_FILES")
        max_size_env = os.environ.get("CODE_MAP_LINTERS_MAX_PROJECT_SIZE_MB")
        min_interval_env = os.environ.get("CODE_MAP_LINTERS_MIN_INTERVAL_SECONDS")

        max_project_files = _parse_int_env(max_files_env)
        max_project_size_mb = _parse_int_env(max_size_env)
        max_project_bytes = (
            max_project_size_mb * 1024 * 1024 if max_project_size_mb else None
        )

        min_interval = _parse_int_env(min_interval_env)
        min_interval_seconds = max(0, min_interval or LINTERS_MIN_INTERVAL_SECONDS)

        options = LinterRunOptions(
            enabled_tools=enabled_tools,
            max_project_files=max_project_files,
            max_project_bytes=max_project_bytes,
        )
        return LintersConfig(
            root_path=self.settings.root_path,
            options=options,
            min_interval_seconds=min_interval_seconds,
            disabled=_linters_disabled_from_env(),
        )

    def _build_insights_config(self) -> InsightsConfig:
        """Construye la configuración para el servicio de insights."""
        return InsightsConfig(
            root_path=self.settings.root_path,
            enabled=bool(self.settings.ollama_insights_enabled),
            model=self.settings.ollama_insights_model,
            frequency_minutes=self.settings.ollama_insights_frequency_minutes,
            focus=self.settings.ollama_insights_focus,
        )

    async def _apply_settings(self, new_settings: AppSettings) -> None:
        """Aplica la nueva configuración a la aplicación."""
        if self.watcher and self.watcher.is_running:
            await asyncio.to_thread(self.watcher.stop)

        self.scheduler.clear()

        self.settings = new_settings
        self._build_components()

        # Vaciar cola de eventos para evitar notificaciones obsoletas
        try:
            while True:
                self.event_queue.get_nowait()
        except asyncio.QueueEmpty:
            pass

        await asyncio.to_thread(
            self.scanner.hydrate_index_from_snapshot,
            self.index,
            store=self.snapshot_store,
        )
        summaries = await asyncio.to_thread(
            self.scanner.scan_and_update_index,
            self.index,
            persist=True,
            store=self.snapshot_store,
        )

        self.last_full_scan = datetime.now(timezone.utc)

        if summaries:
            payload = {
                "updated": [self.to_relative(summary.path) for summary in summaries],
                "deleted": [],
            }
            self.last_event_batch = datetime.now(timezone.utc)
            await self.event_queue.put(payload)

        started = await asyncio.to_thread(self.watcher.start)
        if not started:
            logger.warning(
                "Watcher no iniciado tras actualizar settings para %s",
                self.settings.root_path,
            )
        self.linters.schedule(pending_changes=self.scheduler.pending_count())
        self.insights.schedule()

    async def run_linters_now(self) -> int:
        """Ejecuta el pipeline de linters inmediatamente y devuelve el ID del reporte."""
        return await self.linters.run_now()

    async def run_insights_now(
        self,
        *,
        model: str,
        focus: Optional[str] = None,
        timeout: Optional[float] = None,
    ):
        """Genera insights inmediatamente usando la configuración actual."""
        return await self.insights.run_now(model=model, focus=focus, timeout=timeout)

    async def build_insights_context(self) -> str:
        """Expone el contexto usado por el generador de insights."""
        return await self._build_insights_context()

    async def _cancel_background_tasks(self) -> None:
        """Cancela y limpia timers/tareas de linters e insights."""
        await self.linters.shutdown()
        await self._cancel_insights_tasks()
        self._recent_changes = []

    async def _cancel_insights_tasks(self) -> None:
        await self.insights.shutdown()
