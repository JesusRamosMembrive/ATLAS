# SPDX-License-Identifier: MIT
"""
Servicio para gestionar la generación periódica de insights con Ollama.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Optional
from pathlib import Path

from ..insights import run_ollama_insights, OLLAMA_DEFAULT_TIMEOUT, OllamaInsightResult
from ..insights.storage import record_insight
from ..linters import Severity
from ..linters import record_notification
from ..integrations import OllamaChatError

logger = logging.getLogger(__name__)


@dataclass
class InsightsConfig:
    root_path: Path
    enabled: bool
    model: Optional[str]
    frequency_minutes: Optional[int]
    focus: Optional[str]
    notify: bool = True
    timeout: float = OLLAMA_DEFAULT_TIMEOUT


class InsightsService:
    """Programa y ejecuta insights automáticos contra Ollama."""

    def __init__(self, config: InsightsConfig, context_builder) -> None:
        self.config = config
        self._context_builder = context_builder
        self.last_attempt: Optional[datetime] = None
        self.last_run: Optional[datetime] = None
        self.next_run: Optional[datetime] = None
        self.last_result: Optional[OllamaInsightResult] = None
        self.last_error: Optional[str] = None

        self._pending = False
        self._task: Optional[asyncio.Task[None]] = None
        self._timer: Optional[asyncio.Task[None]] = None
        self._stop_event = asyncio.Event()

    async def shutdown(self) -> None:
        """Cancela tareas y timers activos."""
        self._stop_event.set()
        await self._cancel_timer()
        await self._cancel_task()
        self._pending = False

    def schedule(self, *, force: bool = False) -> None:
        """Programa ejecución respetando el intervalo configurado."""
        if not self._settings_valid():
            self.next_run = None
            self._clear_timer()
            return

        if self._task and not self._task.done():
            self._pending = True
            return

        interval_seconds = self._interval_seconds()
        reference = self.last_attempt

        if not force and reference is not None:
            elapsed = (datetime.now(timezone.utc) - reference).total_seconds()
            remaining = interval_seconds - elapsed
            if remaining > 0:
                self._pending = True
                if self._timer is None or self._timer.done():
                    try:
                        loop = asyncio.get_running_loop()
                    except RuntimeError:
                        self._pending = True
                        return
                    self._timer = loop.create_task(self._schedule_later(remaining))
                return

        self._pending = False
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            self._pending = True
            return
        self._task = loop.create_task(self._run())

    async def run_now(
        self,
        *,
        model: Optional[str] = None,
        focus: Optional[str] = None,
        timeout: Optional[float] = None,
    ):
        """Ejecuta insights inmediatamente y devuelve el resultado."""
        await self._cancel_timer()
        await self._cancel_task()
        self._pending = False
        result = await self._run_once(
            model_override=model,
            focus_override=focus,
            timeout=timeout,
        )
        self.last_result = result
        return result

    async def _schedule_later(self, delay: float) -> None:
        try:
            await asyncio.sleep(max(delay, 0))
            if self._stop_event.is_set():
                return
            self._timer = None
            self.schedule(force=True)
        except asyncio.CancelledError:
            self._timer = None
            raise

    def _settings_valid(self) -> bool:
        return bool(self.config.enabled and self.config.model)

    def _interval_seconds(self) -> int:
        minutes = self.config.frequency_minutes or 60
        return max(1, minutes) * 60

    async def _run(self) -> None:
        try:
            await self._run_once()
        finally:
            self._task = None
            if self._timer and self._timer.done():
                self._timer = None
            if self._stop_event.is_set():
                return
            if self._pending:
                self._pending = False
                self.schedule(force=True)
            else:
                self.schedule()

    async def _run_once(
        self,
        *,
        model_override: Optional[str] = None,
        focus_override: Optional[str] = None,
        timeout: Optional[float] = None,
    ):
        model = model_override or self.config.model
        if not model:
            raise RuntimeError("No hay modelo configurado para ejecutar insights.")

        self.last_attempt = datetime.now(timezone.utc)
        try:
            context = await self._context_builder()
            result = await asyncio.to_thread(
                run_ollama_insights,
                model=model,
                root_path=self.config.root_path,
                endpoint=None,
                context=context,
                timeout=timeout or self.config.timeout,
                focus=focus_override or self.config.focus,
            )
            record_insight(
                model=result.model,
                message=result.message,
                raw=result.raw.raw,
                root_path=self.config.root_path,
            )
            self.last_run = result.generated_at
            self.last_error = None
            self.next_run = self.last_attempt + timedelta(
                seconds=self._interval_seconds()
            )
            return result
        except OllamaChatError as exc:
            logger.warning(
                "Fallo generando insights (modelo=%s, endpoint=%s): %s",
                model,
                exc.endpoint,
                exc,
            )
            self.last_error = str(exc)
            if self.config.notify:
                record_notification(
                    channel="insights",
                    severity=Severity.MEDIUM,
                    title="Insights automáticos: error",
                    message=str(exc),
                    root_path=self.config.root_path,
                    payload={
                        "endpoint": exc.endpoint,
                        "reason_code": getattr(exc, "reason_code", None),
                        "original_error": exc.original_error,
                    },
                )
            raise
        except Exception:  # pragma: no cover
            logger.exception(
                "Error inesperado al generar insights automáticos con Ollama"
            )
            self.last_error = "Error inesperado al generar insights; revisar logs."
            if self.config.notify:
                record_notification(
                    channel="insights",
                    severity=Severity.MEDIUM,
                    title="Insights automáticos: excepción inesperada",
                    message="Consulta los logs del backend para más detalles.",
                    root_path=self.config.root_path,
                    payload=None,
                )
            raise

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

    def _clear_timer(self) -> None:
        if self._timer and not self._timer.done():
            self._timer.cancel()
        self._timer = None
