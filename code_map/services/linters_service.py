# SPDX-License-Identifier: MIT
"""
Servicio responsable de ejecutar y programar el pipeline de linters.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from ..linters import (
    CheckStatus,
    Severity,
    record_linters_report,
    record_notification,
    run_linters_pipeline,
    LinterRunOptions,  # re-exported en state
)

logger = logging.getLogger(__name__)


@dataclass
class LintersConfig:
    """Configuración necesaria para ejecutar linters."""

    root_path: Path
    options: LinterRunOptions
    min_interval_seconds: int
    disabled: bool = False


class LintersService:
    """Gestiona ejecución y scheduling del pipeline de linters."""

    def __init__(self, config: LintersConfig) -> None:
        self.config = config
        self.last_run: Optional[datetime] = None
        self.last_report_id: Optional[int] = None

        self._pending = False
        self._task: Optional[asyncio.Task[None]] = None
        self._timer: Optional[asyncio.Task[None]] = None
        self._stop_event = asyncio.Event()

    async def shutdown(self) -> None:
        """Cancela timers y tareas en curso."""
        self._stop_event.set()
        await self._cancel_timer()
        await self._cancel_task()
        self._pending = False

    def schedule(self, *, pending_changes: int, force: bool = False) -> None:
        """Programa ejecución respetando intervalos y cambios pendientes."""
        if self.config.disabled:
            return

        if self._task and not self._task.done():
            self._pending = True
            return

        if not force:
            if pending_changes > 0:
                self._pending = True
                return

            if self.config.min_interval_seconds and self.last_run is not None:
                elapsed = (datetime.now(timezone.utc) - self.last_run).total_seconds()
                remaining = self.config.min_interval_seconds - elapsed
                if remaining > 0:
                    self._pending = True
                    if self._timer is None or self._timer.done():
                        self._timer = asyncio.create_task(
                            self._schedule_later(remaining)
                        )
                    return

        self._pending = False
        self._task = asyncio.create_task(self._run())

    async def run_now(self) -> int:
        """Ejecuta inmediatamente el pipeline y devuelve el ID del reporte."""
        await self._cancel_timer()
        await self._cancel_task()
        self._pending = False
        self._task = asyncio.create_task(self._run())
        await self._task
        if self.last_report_id is None:
            raise RuntimeError("No se pudo generar el reporte de linters.")
        return self.last_report_id

    async def _schedule_later(self, delay: float) -> None:
        try:
            await asyncio.sleep(max(delay, 0))
            if self._stop_event.is_set():
                return
            self._timer = None
            self.schedule(pending_changes=0, force=True)
        except asyncio.CancelledError:
            self._timer = None
            raise

    async def _run(self) -> None:
        """Ejecuta el pipeline y registra resultados/notificaciones."""
        try:
            report = await asyncio.to_thread(
                run_linters_pipeline,
                self.config.root_path,
                options=self.config.options,
            )
            report_id = record_linters_report(report)
            self.last_report_id = report_id
            summary = report.summary
            status = summary.overall_status
            self.last_run = datetime.now(timezone.utc)

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
                    root_path=self.config.root_path,
                    payload={
                        "report_id": report_id,
                        "status": status.value,
                        "issues_total": summary.issues_total,
                        "critical_issues": summary.critical_issues,
                    },
                )
        except Exception:  # pragma: no cover
            # Debe ser resiliente: nunca deja caer la app por un fallo de linters
            logger.exception("Error al ejecutar el pipeline de linters")
        finally:
            self._task = None
            if self._timer and self._timer.done():
                self._timer = None
            if self._stop_event.is_set():
                return
            if self._pending:
                self._pending = False
                self.schedule(pending_changes=0)

    async def _cancel_timer(self) -> None:
        if self._timer:
            self._timer.cancel()
            with suppress(asyncio.CancelledError):
                await self._timer
            self._timer = None

    async def _cancel_task(self) -> None:
        if self._task:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task
            self._task = None
            self.last_run = None
