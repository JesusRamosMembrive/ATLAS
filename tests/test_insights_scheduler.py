# SPDX-License-Identifier: MIT
import asyncio
from contextlib import suppress
from datetime import datetime, timezone
from pathlib import Path

import pytest

from code_map.scheduler import ChangeScheduler
from code_map.settings import AppSettings
from code_map.state import AppState
from code_map.insights import OllamaInsightResult
from code_map.integrations import OllamaChatError, OllamaChatResponse


class _DummyWatcher:
    def __init__(self, *_, **__):
        self._running = False

    def start(self) -> bool:  # pragma: no cover - no side effects
        self._running = True
        return True

    def stop(self) -> None:  # pragma: no cover - no side effects
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running


async def _cleanup_state(state: AppState) -> None:
    """Limpia los timers y tareas de insights del estado."""
    await state.insights.shutdown()


@pytest.mark.asyncio
async def test_insights_scheduler_runs_when_enabled(
    monkeypatch, tmp_path: Path
) -> None:
    called: dict[str, object] = {}

    def fake_run_ollama_insights(
        *,
        model: str,
        root_path: Path,
        endpoint=None,
        timeout: float = 0.0,
        context: str | None = None,
        **_: object,
    ) -> OllamaInsightResult:
        called["model"] = model
        called["context"] = context
        return OllamaInsightResult(
            model=model,
            generated_at=datetime.now(timezone.utc),
            message="ok",
            raw=OllamaChatResponse(
                model=model,
                message="ok",
                raw={"ok": True},
                latency_ms=1.0,
                endpoint="http://localhost",
            ),
        )

    monkeypatch.setattr(
        "code_map.services.insights_service.run_ollama_insights",
        fake_run_ollama_insights,
    )
    monkeypatch.setattr(
        "code_map.services.insights_service.record_insight", lambda **kwargs: 1
    )
    monkeypatch.setattr(
        "code_map.services.watcher_manager.WatcherService", _DummyWatcher
    )

    async def fake_context(self):
        return "context"

    monkeypatch.setattr(AppState, "_build_insights_context", fake_context)

    settings = AppSettings(
        root_path=tmp_path,
        exclude_dirs=(),
        include_docstrings=True,
        ollama_insights_enabled=True,
        ollama_insights_model="test-model",
        ollama_insights_frequency_minutes=1,
    )
    state = AppState(settings=settings, scheduler=ChangeScheduler())

    await asyncio.sleep(0)
    if state.insights._task:
        await asyncio.wait_for(state.insights._task, timeout=1)

    assert called.get("model") == "test-model"
    await _cleanup_state(state)


@pytest.mark.asyncio
async def test_insights_scheduler_skips_when_disabled(
    monkeypatch, tmp_path: Path
) -> None:
    def fake_run_ollama_insights(**kwargs):  # pragma: no cover - no ejecución esperada
        raise AssertionError(
            "Insights no deberían ejecutarse cuando están deshabilitados"
        )

    monkeypatch.setattr(
        "code_map.services.insights_service.run_ollama_insights",
        fake_run_ollama_insights,
    )
    monkeypatch.setattr(
        "code_map.services.insights_service.record_insight", lambda **kwargs: 1
    )
    monkeypatch.setattr(
        "code_map.services.watcher_manager.WatcherService", _DummyWatcher
    )

    async def fake_context(self):
        return "context"

    monkeypatch.setattr(AppState, "_build_insights_context", fake_context)

    settings = AppSettings(
        root_path=tmp_path,
        exclude_dirs=(),
        include_docstrings=True,
        ollama_insights_enabled=False,
        ollama_insights_model="test-model",
        ollama_insights_frequency_minutes=1,
    )
    state = AppState(settings=settings, scheduler=ChangeScheduler())

    await asyncio.sleep(0.05)

    assert state.insights._task is None
    await _cleanup_state(state)


@pytest.mark.asyncio
async def test_insights_scheduler_records_error_notification(
    monkeypatch, tmp_path: Path
) -> None:
    notifications: list[dict] = []

    def fake_run(**kwargs):
        raise OllamaChatError(
            "fallo de prueba", endpoint="http://localhost", original_error="timeout"
        )

    async def fake_context(self):
        return "context"

    def fake_record_notification(**kwargs):
        notifications.append(kwargs)
        return 1

    monkeypatch.setattr(
        "code_map.services.insights_service.run_ollama_insights", fake_run
    )
    monkeypatch.setattr(
        "code_map.services.insights_service.record_insight", lambda **kwargs: 1
    )
    monkeypatch.setattr(
        "code_map.services.watcher_manager.WatcherService", _DummyWatcher
    )
    monkeypatch.setattr(AppState, "_build_insights_context", fake_context)
    monkeypatch.setattr(
        "code_map.services.insights_service.record_notification",
        fake_record_notification,
    )

    settings = AppSettings(
        root_path=tmp_path,
        exclude_dirs=(),
        include_docstrings=True,
        ollama_insights_enabled=True,
        ollama_insights_model="test-model",
        ollama_insights_frequency_minutes=1,
    )
    state = AppState(settings=settings, scheduler=ChangeScheduler())

    await asyncio.sleep(0)
    if state.insights._task:
        with suppress(asyncio.CancelledError, OllamaChatError):
            await asyncio.wait_for(state.insights._task, timeout=1)

    assert notifications
    payload = notifications[0]
    assert payload["channel"] == "insights"
    assert "fallo de prueba" in payload["message"]
    await _cleanup_state(state)
