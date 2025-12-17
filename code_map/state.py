# SPDX-License-Identifier: MIT
"""
Application State Module for Code Map FastAPI Backend.

This module provides the central shared state container (AppState) that manages
the lifecycle and coordination of all major application components including:

- Project scanning and symbol indexing
- File watching and change detection
- Linter pipeline execution
- AI-powered insights generation (via Ollama)
- Event queue for real-time updates

The AppState dataclass is the backbone of the FastAPI application, instantiated
once at startup and shared across all API endpoints via dependency injection.

Architecture Overview::

    ┌─────────────────────────────────────────────────────────────────┐
    │                        AppState                                  │
    │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
    │  │ ProjectScanner│  │ SymbolIndex  │  │ ChangeScheduler      │  │
    │  │ (file parsing)│  │ (symbol DB)  │  │ (debounced changes)  │  │
    │  └──────────────┘  └──────────────┘  └──────────────────────┘  │
    │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
    │  │WatcherManager│  │LintersService│  │ InsightsService      │  │
    │  │ (file events)│  │ (quality)    │  │ (AI analysis)        │  │
    │  └──────────────┘  └──────────────┘  └──────────────────────┘  │
    └─────────────────────────────────────────────────────────────────┘

Example Usage::

    from code_map.state import AppState
    from code_map.settings import AppSettings
    from code_map.scheduler import ChangeScheduler

    settings = AppSettings(root_path=Path("/my/project"))
    scheduler = ChangeScheduler()
    state = AppState(settings=settings, scheduler=scheduler)

    # In FastAPI lifespan:
    await state.startup()
    # ... application runs ...
    await state.shutdown()

Environment Variables:
    CODE_MAP_DISABLE_LINTERS: Set to "1" to disable linter execution
    CODE_MAP_LINTERS_TOOLS: Comma-separated list of enabled tools (e.g., "ruff,mypy")
    CODE_MAP_LINTERS_MAX_PROJECT_FILES: Skip linters if project exceeds this file count
    CODE_MAP_LINTERS_MAX_PROJECT_SIZE_MB: Skip linters if project exceeds this size
    CODE_MAP_LINTERS_MIN_INTERVAL_SECONDS: Minimum seconds between linter runs
    CODE_MAP_CACHE_DIR: Alternative cache directory for Docker/read-only mounts

See Also:
    - code_map.server: FastAPI application factory using this state
    - code_map.settings: Configuration management
    - code_map.services: Individual service implementations
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
from .settings import (
    AppSettings,
    save_settings,
    ENV_DISABLE_LINTERS,
    ENV_CACHE_DIR,
    should_skip_initial_scan,
)
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
    """
    Central shared state container for the FastAPI Code Map application.

    This dataclass manages the complete lifecycle of all application components,
    coordinating scanning, indexing, file watching, linting, and AI insights.
    It is designed to be instantiated once and shared across all API endpoints.

    Attributes:
        settings (AppSettings): Application configuration including root path,
            exclude directories, and feature flags.
        scheduler (ChangeScheduler): Debounced change scheduler that batches
            file system events before processing.
        scanner (ProjectScanner): Multi-language code parser that extracts
            symbols from source files. Built automatically from settings.
        index (SymbolIndex): In-memory symbol database containing all parsed
            symbols (functions, classes, variables) with their metadata.
        snapshot_store (SnapshotStore): Persistent cache for index snapshots,
            enabling fast startup by avoiding full re-scans.
        watcher (WatcherManager): File system observer that detects changes
            and feeds them to the scheduler.
        last_full_scan (datetime | None): Timestamp of the most recent
            complete project scan, or None if never scanned.
        last_event_batch (datetime | None): Timestamp of the most recent
            processed change batch, or None if no changes processed.
        reporter (StateReporter): Helper that serializes state for API responses.
        linters (LintersService): Background service managing automated linter
            execution (ruff, mypy, bandit, pytest).
        insights (InsightsService): Background service managing AI-powered
            code analysis via Ollama.

    Lifecycle:
        1. **Instantiation**: Create with settings and scheduler. Components
           are built in ``__post_init__``.
        2. **Startup**: Call ``await startup()`` to initialize scanning,
           watching, and background tasks.
        3. **Operation**: The scheduler loop processes file changes, triggers
           re-indexing, and schedules linters/insights.
        4. **Shutdown**: Call ``await shutdown()`` to cleanly stop all
           background tasks and release resources.

    Thread Safety:
        - Most operations are async and should be called from the event loop
        - Blocking operations (scanning, file I/O) are wrapped in ``asyncio.to_thread``
        - The event_queue is safe for concurrent producers/consumers

    Example:
        >>> settings = AppSettings(root_path=Path("/project"))
        >>> scheduler = ChangeScheduler(debounce_seconds=1.0)
        >>> state = AppState(settings=settings, scheduler=scheduler)
        >>> await state.startup()
        >>> # Application runs, handling requests...
        >>> await state.shutdown()
    """

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
        """
        Initialize internal state after dataclass field assignment.

        Creates the async event queue, stop event, and builds all application
        components. This is called automatically by the dataclass machinery
        after ``settings`` and ``scheduler`` are assigned.

        Internal State Created:
            - event_queue: Async queue for broadcasting change events to SSE clients
            - _stop_event: Signal to gracefully terminate the scheduler loop
            - _scheduler_task: Handle to the background scheduler coroutine
            - _recent_changes: Rolling buffer of recently changed file paths

        Note:
            After __post_init__ completes, you must still call ``startup()``
            to begin scanning and watching. This separation allows for
            pre-startup configuration if needed.
        """
        self.event_queue: "asyncio.Queue[Dict[str, Any]]" = asyncio.Queue()
        self._stop_event = asyncio.Event()
        self._scheduler_task: Optional[asyncio.Task[None]] = None
        self._recent_changes: List[str] = []

        self._build_components()
        self.insights.schedule()

    async def startup(self) -> None:
        """
        Initialize the application state and start all background services.

        This async method performs the complete startup sequence:

        1. **Snapshot Hydration**: Loads cached symbol index from disk if available,
           avoiding a full re-scan on subsequent startups.
        2. **Initial Scan**: Performs a full project scan to discover and parse
           all source files, updating the symbol index.
        3. **Watcher Start**: Begins monitoring the file system for changes.
        4. **Service Scheduling**: Schedules initial runs of linters and insights.
        5. **Scheduler Loop**: Starts the background task that processes
           file change batches.

        The startup can be skipped by setting ``CODE_MAP_SKIP_INITIAL_SCAN=1``,
        which is useful when the project path will be configured later via the UI.

        Raises:
            No exceptions are raised directly; errors are logged and may result
            in degraded functionality (e.g., watcher not starting).

        Note:
            This method must be awaited before the application can serve requests.
            In FastAPI, call this in the lifespan context manager's startup phase.
        """
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
        """
        Gracefully stop all background services and release resources.

        This async method performs the complete shutdown sequence:

        1. **Signal Stop**: Sets the stop event to terminate the scheduler loop.
        2. **Linters Shutdown**: Cancels any pending/running linter tasks.
        3. **Insights Shutdown**: Cancels any pending/running insights tasks.
        4. **Scheduler Wait**: Awaits completion of the scheduler task.
        5. **Watcher Stop**: Stops file system monitoring.

        This method should be called during application shutdown to ensure
        clean termination of all background tasks and proper resource cleanup.

        Note:
            This method is idempotent - calling it multiple times is safe.
            In FastAPI, call this in the lifespan context manager's shutdown phase.
        """
        logger.info("Deteniendo estado de la app")
        self._stop_event.set()
        await self.linters.shutdown()
        await self.insights.shutdown()
        if self._scheduler_task:
            await self._scheduler_task
        await asyncio.to_thread(self.watcher.stop)

    async def _scheduler_loop(self) -> None:
        """
        Main background loop that processes batched file changes.

        This coroutine runs continuously until shutdown, performing:

        1. **Drain Changes**: Retrieves accumulated file changes from the scheduler.
        2. **Apply Batch**: Updates the symbol index with changed/deleted files.
        3. **Serialize**: Converts changes to relative paths for event notification.
        4. **Broadcast**: Puts change events on the queue for SSE consumers.
        5. **Reschedule**: Triggers linter and insights runs if changes occurred.
        6. **Sleep**: Waits for the debounce interval before next iteration.

        The loop respects the ``_stop_event`` for graceful shutdown.

        Note:
            This is an internal method started by ``startup()`` and should
            not be called directly.
        """
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
        """
        Convert file change paths to a serializable format for event broadcasting.

        Args:
            changes: Dictionary with "updated" and "deleted" keys containing
                iterables of absolute Path objects.

        Returns:
            Dictionary with "updated" and "deleted" keys containing lists
            of relative POSIX-style path strings (e.g., "src/main.py").

        Side Effects:
            Updates ``_recent_changes`` with the combined list of changed paths,
            limited to ``MAX_RECENT_CHANGES_TRACKED`` entries.
        """
        updated = [self.to_relative(path) for path in changes.get("updated", [])]
        deleted = [self.to_relative(path) for path in changes.get("deleted", [])]
        if updated or deleted:
            combined = (updated + deleted)[:MAX_RECENT_CHANGES_TRACKED]
            self._recent_changes = combined
        return {"updated": updated, "deleted": deleted}

    async def perform_full_scan(self) -> int:
        """
        Trigger a complete rescan of the entire project.

        This method forces a full scan of all source files in the project,
        regardless of the cached state. Use this when:

        - The index may be out of sync with the file system
        - Files were modified outside the watched scope
        - Manual refresh is requested via the API

        Returns:
            int: Number of files that were scanned and updated.

        Side Effects:
            - Updates the symbol index with all discovered symbols
            - Persists the updated index to the snapshot store
            - Broadcasts change events to SSE consumers
            - Updates ``last_full_scan`` timestamp
            - Schedules linter and insights runs
        """
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
        """
        Convert an absolute path to a project-relative POSIX path string.

        Args:
            path: Absolute path to convert.

        Returns:
            POSIX-style relative path string (e.g., "src/module/file.py").
            If the path is outside the project root, returns the absolute
            path as a POSIX string instead.

        Example:
            >>> state.to_relative(Path("/project/src/main.py"))
            "src/main.py"
        """
        try:
            rel = path.resolve().relative_to(self.settings.root_path)
            return rel.as_posix()
        except ValueError:
            return path.resolve().as_posix()

    def resolve_path(self, relative: str) -> Path:
        """
        Resolve a relative path to an absolute path within the project root.

        This method provides safe path resolution with security validation
        to prevent path traversal attacks.

        Args:
            relative: Relative path string (e.g., "src/main.py").

        Returns:
            Resolved absolute Path object.

        Raises:
            ValueError: If the resolved path escapes the project root
                (e.g., "../../../etc/passwd").

        Example:
            >>> state.resolve_path("src/main.py")
            Path("/project/src/main.py")

        Security:
            This method validates that the resolved path stays within
            the project root, preventing directory traversal attacks.
        """
        candidate = (self.settings.root_path / relative).resolve()
        if not self._within_root(candidate):
            raise ValueError(f"Ruta fuera del root configurado: {relative}")
        return candidate

    def _within_root(self, path: Path) -> bool:
        """
        Check if a path is within the project root directory.

        Args:
            path: Absolute path to check.

        Returns:
            True if the path is within the project root, False otherwise.
        """
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
        """
        Update application settings and reinitialize affected components.

        This method allows runtime modification of settings. When settings change,
        it gracefully stops affected services, rebuilds components with new config,
        and restarts them.

        Args:
            root_path: New project root directory. Must exist and be a directory.
            include_docstrings: Whether to extract docstrings during scanning.
            exclude_dirs: Directory names to exclude from scanning (e.g., ["node_modules"]).
            ollama_insights_enabled: Enable/disable AI insights generation.
            ollama_insights_model: Ollama model name for insights (e.g., "llama3.2").
            ollama_insights_frequency_minutes: Minutes between automatic insights runs.
                Must be positive and <= 1440 (24 hours).
            ollama_insights_focus: Analysis focus area. Valid values are defined in
                ``VALID_INSIGHTS_FOCUS``. Empty string resets to default.
            backend_url: Base URL for the Ollama backend.

        Returns:
            List of field names that were actually updated (empty if no changes).

        Raises:
            ValueError: If validation fails for any parameter:
                - root_path doesn't exist or isn't a directory
                - frequency_minutes is <= 0 or > 1440
                - focus is not a valid option

        Side Effects:
            - Stops and restarts the file watcher
            - Clears pending changes from the scheduler
            - Performs a full project rescan with new settings
            - Persists settings to disk
            - Reschedules linters and insights

        Example:
            >>> updated = await state.update_settings(
            ...     exclude_dirs=["node_modules", ".venv"],
            ...     ollama_insights_enabled=True
            ... )
            >>> print(updated)
            ["exclude_dirs", "ollama_insights_enabled"]
        """
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
        """
        Build or rebuild all application components from current settings.

        This method creates fresh instances of all major services based on
        the current ``self.settings``. It is called during initialization
        and whenever settings are updated.

        Components Built:
            - scanner: ProjectScanner for parsing source files
            - index: SymbolIndex for storing parsed symbols
            - snapshot_store: SnapshotStore for persistent caching
            - reporter: StateReporter for API response formatting
            - watcher: WatcherManager for file system monitoring
            - linters: LintersService for code quality checks
            - insights: InsightsService for AI-powered analysis

        Note:
            This method does not start any services; it only creates the
            instances. Call ``startup()`` to begin active monitoring.
        """
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
        """
        Build configuration for the linters service from environment and settings.

        Reads environment variables to configure the linter pipeline:
            - CODE_MAP_LINTERS_TOOLS: Comma-separated list of enabled tools
            - CODE_MAP_LINTERS_MAX_PROJECT_FILES: Skip if too many files
            - CODE_MAP_LINTERS_MAX_PROJECT_SIZE_MB: Skip if project too large
            - CODE_MAP_LINTERS_MIN_INTERVAL_SECONDS: Minimum time between runs

        Returns:
            LintersConfig instance ready for LintersService initialization.
        """
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
        """
        Build configuration for the insights service from current settings.

        Returns:
            InsightsConfig instance with settings for Ollama-powered analysis,
            including enabled state, model name, frequency, and focus area.
        """
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
        """
        Execute the linter pipeline immediately, bypassing the schedule.

        Runs all configured linters (ruff, mypy, bandit, pytest) on the
        current project and generates a quality report.

        Returns:
            int: Report ID that can be used to retrieve the results
                via the linters API endpoint.

        Note:
            This may take significant time for large projects. The linter
            pipeline respects size limits configured via environment variables.
        """
        return await self.linters.run_now()

    async def run_insights_now(
        self,
        *,
        model: str,
        focus: Optional[str] = None,
        timeout: Optional[float] = None,
    ):
        """
        Generate AI-powered code insights immediately.

        Sends the current project context to Ollama for analysis and returns
        AI-generated insights about code quality, architecture, or other
        focus areas.

        Args:
            model: Ollama model name to use (e.g., "llama3.2", "codellama").
            focus: Optional analysis focus area. If not provided, uses the
                configured default focus.
            timeout: Optional timeout in seconds for the Ollama request.

        Returns:
            InsightsResult with the generated analysis, or raises on error.

        Note:
            Requires Ollama to be running and accessible at the configured
            backend URL.
        """
        return await self.insights.run_now(model=model, focus=focus, timeout=timeout)

    async def build_insights_context(self) -> str:
        """
        Build and return the context string used for AI insights generation.

        This method assembles contextual information about the project that
        is sent to Ollama for analysis, including:

        - Latest linter report summary (status, issue counts)
        - Detected project stage and confidence
        - Pending change events in queue
        - Recently modified files

        Returns:
            str: Formatted context string for the AI model, or a default
                message if no relevant context is available.

        Note:
            This is primarily for debugging/inspection. The same context
            is automatically provided to ``run_insights_now()``.
        """
        return await self._build_insights_context()

    async def _cancel_background_tasks(self) -> None:
        """
        Cancel all background tasks and timers for settings updates.

        Called when settings change to ensure clean state before rebuilding
        components. Shuts down linters, insights, and clears recent changes.
        """
        await self.linters.shutdown()
        await self._cancel_insights_tasks()
        self._recent_changes = []

    async def _cancel_insights_tasks(self) -> None:
        """Cancel pending insights tasks during shutdown or settings update."""
        await self.insights.shutdown()
