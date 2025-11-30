# SPDX-License-Identifier: MIT
import types
from datetime import datetime, timezone
from pathlib import Path

import pytest

from code_map.services.linters_service import LintersConfig, LintersService
from code_map.services.insights_service import (
    InsightsConfig,
    InsightsService,
    OllamaInsightResult,
)
from code_map.services.watcher_manager import WatcherConfig, WatcherManager
from code_map.linters.report_schema import ReportSummary, CheckStatus


class _DummyReport:
    def __init__(self, status: CheckStatus, issues_total: int = 0, critical: int = 0):
        self.summary = ReportSummary(
            overall_status=status,
            total_checks=1,
            checks_passed=0,
            checks_warned=1 if status is CheckStatus.WARN else 0,
            checks_failed=1 if status is CheckStatus.FAIL else 0,
            duration_ms=10,
            files_scanned=1,
            lines_scanned=10,
            issues_total=issues_total,
            critical_issues=critical,
        )


@pytest.mark.asyncio
async def test_linters_service_run_now(monkeypatch, tmp_path: Path):
    """LintersService.run_now debe devolver el id de reporte y registrar last_run."""
    calls = {}

    def _fake_run(root_path, options):
        calls["run"] = True
        return _DummyReport(CheckStatus.WARN, issues_total=1)

    def _fake_record(report):
        calls["record_report"] = True
        return 42

    def _fake_notify(**kwargs):
        calls.setdefault("notify", []).append(kwargs)

    monkeypatch.setattr("code_map.services.linters_service.run_linters_pipeline", _fake_run)
    monkeypatch.setattr("code_map.services.linters_service.record_linters_report", _fake_record)
    monkeypatch.setattr("code_map.services.linters_service.record_notification", _fake_notify)

    svc = LintersService(
        LintersConfig(
            root_path=tmp_path,
            options=types.SimpleNamespace(),  # options no se usan en stub
            min_interval_seconds=0,
            disabled=False,
        )
    )

    report_id = await svc.run_now()

    assert report_id == 42
    assert calls.get("run") is True
    assert calls.get("record_report") is True
    assert svc.last_run is not None
    assert calls.get("notify"), "Debe notificar cuando WARN/FAIL/ SKIPPED"


@pytest.mark.asyncio
async def test_insights_service_run_now(monkeypatch, tmp_path: Path):
    """InsightsService.run_now debe registrar last_result y limpiar errores previos."""
    notifications = []
    insights_recorded = []

    now = datetime.now(timezone.utc)

    def _fake_run_ollama(**kwargs):
        return OllamaInsightResult(
            model=kwargs.get("model") or "test-model",
            generated_at=now,
            message="ok",
            raw=types.SimpleNamespace(raw={"data": "x"}),
        )

    def _fake_record_insight(**kwargs):
        insights_recorded.append(kwargs)

    def _fake_record_notification(**kwargs):
        notifications.append(kwargs)

    monkeypatch.setattr("code_map.services.insights_service.run_ollama_insights", _fake_run_ollama)
    monkeypatch.setattr("code_map.services.insights_service.record_insight", _fake_record_insight)
    monkeypatch.setattr("code_map.services.insights_service.record_notification", _fake_record_notification)

    async def _ctx():
        return "ctx"

    svc = InsightsService(
        InsightsConfig(
            root_path=tmp_path,
            enabled=True,
            model="test-model",
            frequency_minutes=60,
            focus="general",
        ),
        context_builder=_ctx,
    )

    result = await svc.run_now()

    assert result.model == "test-model"
    assert svc.last_result is not None
    assert svc.last_result.message == "ok"
    assert svc.last_error is None
    assert insights_recorded, "Debe registrar el insight generado"
    assert notifications == [], "No debe notificar en éxito"


class DummyWatcher:
    def __init__(self):
        self.started = False
        self.stopped = False

    def start(self):
        self.started = True
        return True

    def stop(self):
        self.stopped = True

    @property
    def is_running(self):
        return self.started and not self.stopped


def test_watcher_manager_start_stop_rebuild(monkeypatch, tmp_path: Path):
    """WatcherManager debe poder iniciar, detener y reconstruir el watcher."""
    dummy_instances = []

    def _fake_watcher(root, scheduler, exclude_dirs, extensions):
        watcher = DummyWatcher()
        dummy_instances.append(watcher)
        return watcher

    monkeypatch.setattr("code_map.services.watcher_manager.WatcherService", _fake_watcher)

    cfg = WatcherConfig(
        root_path=tmp_path,
        scheduler=types.SimpleNamespace(),
        exclude_dirs=[],
        extensions=[".py"],
    )
    manager = WatcherManager(cfg)

    assert manager.start() is True
    assert manager.is_running is True
    manager.stop()
    assert manager.is_running is False

    new_cfg = WatcherConfig(
        root_path=tmp_path,
        scheduler=types.SimpleNamespace(),
        exclude_dirs=[".venv"],
        extensions=[".py", ".js"],
    )
    manager.rebuild(new_cfg)
    assert len(dummy_instances) == 2
    assert manager.start() is True
