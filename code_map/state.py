# SPDX-License-Identifier: MIT
"""
Estado compartido de la aplicación FastAPI.
"""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Mapping

from .cache import SnapshotStore
from .index import SymbolIndex
from .scanner import ProjectScanner
from .scheduler import ChangeScheduler
from .watcher import WatcherService
from .settings import AppSettings, save_settings, ENV_DISABLE_LINTERS, ENV_CACHE_DIR
from .linters import (
    CheckStatus,
    Severity,
    record_linters_report,
    record_notification,
    run_linters_pipeline,
    LinterRunOptions,
    get_latest_linters_report,
    LINTER_TIMEOUT_FAST,  # Re-export for consistency
)
from .stage_toolkit import stage_status as compute_stage_status
from .state_reporter import StateReporter
from .insights import (
    run_ollama_insights,
    VALID_INSIGHTS_FOCUS,
    OLLAMA_DEFAULT_TIMEOUT,
)
from .insights.storage import record_insight
from .integrations import OllamaChatError

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


@dataclass
class AppState:
    """Estado compartido de la aplicación FastAPI."""

    settings: AppSettings
    scheduler: ChangeScheduler
    scanner: ProjectScanner = field(init=False)
    index: SymbolIndex = field(init=False)
    snapshot_store: SnapshotStore = field(init=False)
    watcher: Optional[WatcherService] = field(init=False, default=None)
    last_full_scan: Optional[datetime] = field(init=False, default=None)
    last_event_batch: Optional[datetime] = field(init=False, default=None)
    reporter: StateReporter = field(init=False)

    def __post_init__(self) -> None:
        self.event_queue: "asyncio.Queue[Dict[str, Any]]" = asyncio.Queue()
        self._stop_event = asyncio.Event()
        self._scheduler_task: Optional[asyncio.Task[None]] = None
        self._linters_task: Optional[asyncio.Task[None]] = None
        self._linters_pending = False
        self._linters_disabled = os.environ.get(
            ENV_DISABLE_LINTERS, ""
        ).strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
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
        self._linters_min_interval = max(
            0, min_interval or LINTERS_MIN_INTERVAL_SECONDS
        )

        self._linters_options = LinterRunOptions(
            enabled_tools=enabled_tools,
            max_project_files=max_project_files,
            max_project_bytes=max_project_bytes,
        )
        self._linters_last_run: Optional[datetime] = None
        self._linters_timer: Optional[asyncio.Task[None]] = None
        self.last_linters_report_id: Optional[int] = None
        self._insights_task: Optional[asyncio.Task[None]] = None
        self._insights_timer: Optional[asyncio.Task[None]] = None
        self._insights_pending = False
        self._insights_last_attempt: Optional[datetime] = None
        self._insights_last_run: Optional[datetime] = None
        self._recent_changes: List[str] = []

        self._build_components()
        self._schedule_insights_pipeline()

    async def startup(self) -> None:
        """Inicializa el estado de la aplicación."""
        logger.info("Inicializando estado de la app para %s", self.settings.root_path)
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
        if self.watcher:
            started = await asyncio.to_thread(self.watcher.start)
            if not started:
                logger.warning("Watcher no iniciado (watchdog ausente o error).")
        self._schedule_linters_pipeline()
        self._schedule_insights_pipeline()
        self._scheduler_task = asyncio.create_task(self._scheduler_loop())

    async def shutdown(self) -> None:
        """Detiene el estado de la aplicación."""
        logger.info("Deteniendo estado de la app")
        self._stop_event.set()
        self._linters_pending = False
        if self._linters_timer:
            self._linters_timer.cancel()
            with suppress(asyncio.CancelledError):
                await self._linters_timer
            self._linters_timer = None
        if self._linters_task:
            await self._linters_task
        self._insights_pending = False
        if self._insights_timer:
            self._insights_timer.cancel()
            with suppress(asyncio.CancelledError):
                await self._insights_timer
            self._insights_timer = None
        if self._insights_task:
            with suppress(asyncio.CancelledError):
                await self._insights_task
        if self._scheduler_task:
            await self._scheduler_task
        if self.watcher:
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
                    self._schedule_linters_pipeline()
                    self._schedule_insights_pipeline()
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
        self._schedule_linters_pipeline()
        self._schedule_insights_pipeline()
        return len(summaries)

    def _schedule_linters_pipeline(self, *, force: bool = False) -> None:
        """Programa la ejecución del pipeline de linters."""
        if self._linters_disabled:
            return
        if self._linters_task and not self._linters_task.done():
            self._linters_pending = True
            return
        if not force:
            if self.scheduler.pending_count() > 0:
                self._linters_pending = True
                return

            if self._linters_min_interval and self._linters_last_run is not None:
                elapsed = (
                    datetime.now(timezone.utc) - self._linters_last_run
                ).total_seconds()
                remaining = self._linters_min_interval - elapsed
                if remaining > 0:
                    self._linters_pending = True
                    if self._linters_timer is None or self._linters_timer.done():
                        self._linters_timer = asyncio.create_task(
                            self._schedule_linters_pipeline_later(remaining)
                        )
                    return

        self._linters_pending = False
        self._linters_task = asyncio.create_task(self._run_linters_pipeline())

    async def _run_linters_pipeline(self) -> None:
        """Ejecuta el pipeline de linters y persiste el resultado."""
        try:
            report = await asyncio.to_thread(
                run_linters_pipeline,
                self.settings.root_path,
                options=self._linters_options,
            )
            report_id = record_linters_report(report)
            self.last_linters_report_id = report_id
            summary = report.summary
            status = summary.overall_status
            self._linters_last_run = datetime.now(timezone.utc)

            if status in {CheckStatus.FAIL, CheckStatus.WARN, CheckStatus.SKIPPED}:
                if status == CheckStatus.FAIL:
                    severity = (
                        Severity.CRITICAL if summary.critical_issues else Severity.HIGH
                    )
                    message = (
                        f"{summary.issues_total} incidencias detectadas (críticas: {summary.critical_issues})."
                        if summary.issues_total
                        else "El pipeline falló. Revisa la salida de las herramientas."
                    )
                elif status == CheckStatus.WARN:
                    severity = Severity.MEDIUM
                    message = (
                        f"{summary.issues_total} advertencias encontradas."
                        if summary.issues_total
                        else "El pipeline reportó advertencias."
                    )
                else:
                    severity = Severity.LOW
                    message = "No se pudieron ejecutar las herramientas configuradas."

                record_notification(
                    channel="linters",
                    severity=severity,
                    title=f"Pipeline de linters: {status.value.upper()}",
                    message=message,
                    root_path=self.settings.root_path,
                    payload={
                        "report_id": report_id,
                        "status": status.value,
                        "issues_total": summary.issues_total,
                        "critical_issues": summary.critical_issues,
                    },
                )
        except Exception:  # pragma: no cover
            # Intentional broad exception: background task must never crash the app
            # Logs error for debugging but allows service to continue
            logger.exception("Error al ejecutar el pipeline de linters")
        finally:
            self._linters_task = None
            if self._linters_timer and self._linters_timer.done():
                self._linters_timer = None
            if self._linters_pending:
                self._linters_pending = False
                self._schedule_linters_pipeline()

    async def _schedule_linters_pipeline_later(self, delay: float) -> None:
        try:
            await asyncio.sleep(max(delay, 0))
            if self._stop_event.is_set():
                return
            self._linters_timer = None
            self._schedule_linters_pipeline(force=True)
        except asyncio.CancelledError:
            self._linters_timer = None
            raise

    def _insights_settings_valid(self) -> bool:
        return bool(
            self.settings.ollama_insights_enabled
            and self.settings.ollama_insights_model
        )

    def _insights_interval_seconds(self) -> int:
        minutes = (
            self.settings.ollama_insights_frequency_minutes
            or DEFAULT_INSIGHTS_INTERVAL_MINUTES
        )
        return max(1, minutes) * 60

    def _compute_insights_next_run(self) -> Optional[datetime]:
        if not self._insights_settings_valid():
            return None
        reference = self._insights_last_attempt
        if reference is None:
            return datetime.now(timezone.utc)
        return reference + timedelta(seconds=self._insights_interval_seconds())

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

    def _schedule_insights_pipeline(self, *, force: bool = False) -> None:
        """Programa la ejecución del generador de insights de Ollama."""
        if not self._insights_settings_valid():
            if self._insights_timer and not self._insights_timer.done():
                self._insights_timer.cancel()
            self._insights_timer = None
            return

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # No event loop available yet (e.g. during import-time in tests).
            self._insights_pending = True
            return

        if self._insights_task and not self._insights_task.done():
            self._insights_pending = True
            return

        interval_seconds = self._insights_interval_seconds()
        reference = self._insights_last_attempt

        if not force and reference is not None:
            elapsed = (datetime.now(timezone.utc) - reference).total_seconds()
            remaining = interval_seconds - elapsed
            if remaining > 0:
                self._insights_pending = True
                if self._insights_timer is None or self._insights_timer.done():
                    self._insights_timer = loop.create_task(
                        self._schedule_insights_pipeline_later(remaining)
                    )
                return

        self._insights_pending = False
        self._insights_task = loop.create_task(self._run_insights_pipeline())

    async def _run_insights_pipeline(self) -> None:
        """Ejecuta el pipeline de insights basado en Ollama."""
        model = self.settings.ollama_insights_model
        if not model:
            return
        self._insights_last_attempt = datetime.now(timezone.utc)

        try:
            context = await self._build_insights_context()
            result = await asyncio.to_thread(
                run_ollama_insights,
                model=model,
                root_path=self.settings.root_path,
                endpoint=None,
                context=context,
                focus=self.settings.ollama_insights_focus,
            )
            record_insight(
                model=result.model,
                message=result.message,
                raw=result.raw.raw,
                root_path=self.settings.root_path,
            )
            self._insights_last_run = result.generated_at
        except OllamaChatError as exc:
            logger.warning(
                "Fallo generando insights (modelo=%s, endpoint=%s): %s",
                model,
                exc.endpoint,
                exc,
            )
            record_notification(
                channel="insights",
                severity=Severity.MEDIUM,
                title="Insights automáticos: error",
                message=str(exc),
                root_path=self.settings.root_path,
                payload={
                    "endpoint": exc.endpoint,
                    "reason_code": getattr(exc, "reason_code", None),
                    "original_error": exc.original_error,
                },
            )
        except Exception:  # pragma: no cover
            # Intentional broad exception: background task must never crash the app
            # Logs error for debugging but allows service to continue
            logger.exception(
                "Error inesperado al generar insights automáticos con Ollama"
            )
            record_notification(
                channel="insights",
                severity=Severity.MEDIUM,
                title="Insights automáticos: excepción inesperada",
                message="Consulta los logs del backend para más detalles.",
                root_path=self.settings.root_path,
                payload=None,
            )
        finally:
            self._insights_task = None
            if self._insights_timer and self._insights_timer.done():
                self._insights_timer = None
            if self._stop_event.is_set():
                return
            if self._insights_pending:
                self._insights_pending = False
                self._schedule_insights_pipeline(force=True)
            else:
                self._schedule_insights_pipeline()

    async def _schedule_insights_pipeline_later(self, delay: float) -> None:
        try:
            await asyncio.sleep(max(delay, 0))
            if self._stop_event.is_set():
                return
            self._insights_timer = None
            self._schedule_insights_pipeline(force=True)
        except asyncio.CancelledError:
            self._insights_timer = None
            raise

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
            insights_last_run=self._insights_last_run,
            insights_next_run=self._compute_insights_next_run(),
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
        self.watcher = WatcherService(
            self.settings.root_path,
            self.scheduler,
            exclude_dirs=self.settings.exclude_dirs,
            extensions=self.scanner.extensions,
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

        if self.watcher:
            started = await asyncio.to_thread(self.watcher.start)
            if not started:
                logger.warning(
                    "Watcher no iniciado tras actualizar settings para %s",
                    self.settings.root_path,
                )
        self._schedule_linters_pipeline()
        self._schedule_insights_pipeline()

    async def run_linters_now(self) -> int:
        """Ejecuta el pipeline de linters inmediatamente y devuelve el ID del reporte."""
        await self._cancel_linters_tasks()
        self._linters_task = asyncio.create_task(self._run_linters_pipeline())
        await self._linters_task
        if self.last_linters_report_id is None:
            raise RuntimeError("No se pudo generar el reporte de linters.")
        return self.last_linters_report_id

    async def run_insights_now(
        self,
        *,
        model: str,
        focus: Optional[str] = None,
        timeout: Optional[float] = None,
    ):
        """Genera insights inmediatamente usando la configuración actual."""
        context = await self._build_insights_context()
        result = await asyncio.to_thread(
            run_ollama_insights,
            model=model,
            root_path=self.settings.root_path,
            endpoint=None,
            context=context,
            focus=focus,
            timeout=timeout or OLLAMA_DEFAULT_TIMEOUT,
        )
        record_insight(
            model=result.model,
            message=result.message,
            raw=result.raw.raw,
            root_path=self.settings.root_path,
        )
        self._insights_last_run = result.generated_at
        self._schedule_insights_pipeline()
        return result

    async def build_insights_context(self) -> str:
        """Expone el contexto usado por el generador de insights."""
        return await self._build_insights_context()

    async def _cancel_background_tasks(self) -> None:
        """Cancela y limpia timers/tareas de linters e insights."""
        await self._cancel_linters_tasks()
        await self._cancel_insights_tasks()
        self._recent_changes = []

    async def _cancel_linters_tasks(self) -> None:
        if self._linters_timer:
            self._linters_timer.cancel()
            with suppress(asyncio.CancelledError):
                await self._linters_timer
            self._linters_timer = None
        if self._linters_task:
            self._linters_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._linters_task
            self._linters_task = None
        self._linters_pending = False
        self._linters_last_run = None

    async def _cancel_insights_tasks(self) -> None:
        if self._insights_timer:
            self._insights_timer.cancel()
            with suppress(asyncio.CancelledError):
                await self._insights_timer
            self._insights_timer = None
        if self._insights_task:
            self._insights_task.cancel()
            with suppress(asyncio.CancelledError):
                await self._insights_task
            self._insights_task = None
        self._insights_pending = False
        self._insights_last_attempt = None
        self._insights_last_run = None
