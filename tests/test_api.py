import json
import os
from collections.abc import Generator
from datetime import datetime, timezone
from pathlib import Path

import pytest
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.testclient import TestClient

from code_map import ChangeScheduler
from code_map.api.preview import MAX_PREVIEW_BYTES
from code_map.api.routes import router
from code_map.linters import (
    ChartData,
    CheckStatus,
    CoverageSnapshot,
    CustomRuleResult,
    IssueDetail,
    LintersReport,
    ReportSummary,
    Severity,
    ToolRunResult,
    record_linters_report,
    record_notification,
)
from code_map.settings import load_settings, save_settings
from code_map.state import AppState
from code_map.integrations import OllamaChatResponse


def write_file(root: Path, relative: str, content: str) -> Path:
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content.strip() + "\n", encoding="utf-8")
    return target


def write_binary(root: Path, relative: str, data: bytes) -> Path:
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return target


def create_test_app(root: Path) -> tuple[FastAPI, AppState]:
    db_path = root / "state.db"
    os.environ["CODE_MAP_DB_PATH"] = str(db_path)
    os.environ["CODE_MAP_DISABLE_LINTERS"] = "1"

    test_env = dict(os.environ)
    settings = load_settings(root_override=root, env=test_env)
    scheduler = ChangeScheduler()
    state = AppState(settings=settings, scheduler=scheduler)
    save_settings(state.settings, env=test_env)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await state.startup()
        try:
            yield
        finally:
            await state.shutdown()

    app = FastAPI(lifespan=lifespan)
    app.include_router(router)
    app.state.app_state = state  # type: ignore[attr-defined]

    return app, state


def build_sample_report(root: Path) -> LintersReport:
    now = datetime.now(timezone.utc)
    summary = ReportSummary(
        overall_status=CheckStatus.WARN,
        total_checks=5,
        checks_passed=3,
        checks_warned=1,
        checks_failed=1,
        duration_ms=1200,
        files_scanned=10,
        lines_scanned=500,
        issues_total=4,
        critical_issues=1,
    )

    issues = [
        IssueDetail(
            message="Importación sin usar",
            file="pkg/module.py",
            line=12,
            code="F401",
            severity=Severity.LOW,
        )
    ]

    tools = [
        ToolRunResult(
            key="ruff",
            name="Ruff",
            status=CheckStatus.FAIL,
            issues_found=2,
            issues_sample=issues,
            version="0.0.0-test",
        )
    ]

    custom_rules = [
        CustomRuleResult(
            key="max_file_length",
            name="Longitud máxima",
            status=CheckStatus.WARN,
            description="Archivo supera el umbral",
            threshold=500,
            violations=[
                IssueDetail(
                    message="Archivo demasiado largo",
                    file="pkg/module.py",
                    line=None,
                    severity=Severity.HIGH,
                )
            ],
        )
    ]

    coverage = CoverageSnapshot(
        statement_coverage=82.5, branch_coverage=70.0, missing_lines=42
    )
    chart = ChartData(
        issues_by_tool={"ruff": 2},
        issues_by_severity={Severity.HIGH: 1, Severity.LOW: 2},
        top_offenders=["pkg/module.py"],
    )

    return LintersReport(
        root_path=str(root.resolve()),
        generated_at=now,
        summary=summary,
        tools=tools,
        custom_rules=custom_rules,
        coverage=coverage,
        metrics={"duration_ms": 1200.0},
        chart_data=chart,
        notes=["Reporte generado para pruebas"],
    )


@pytest.fixture()
def api_client(tmp_path: Path) -> Generator[TestClient, None, None]:
    write_file(
        tmp_path,
        "pkg/module.py",
        """
class Demo:
    def run(self):
        return True


def helper():
    return 123
""",
    )
    app, state = create_test_app(tmp_path)
    with TestClient(app) as client:
        yield client


def test_health_endpoint(api_client: TestClient) -> None:
    response = api_client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_tree_endpoint_returns_structure(api_client: TestClient) -> None:
    response = api_client.get("/tree")
    data = response.json()
    assert response.status_code == 200
    assert data["is_dir"] is True
    assert any(child["name"] == "pkg" for child in data["children"])


def test_files_endpoint_returns_summary(api_client: TestClient) -> None:
    response = api_client.get("/files/pkg/module.py")
    assert response.status_code == 200
    payload = response.json()
    assert payload["path"] == "pkg/module.py"
    symbol_names = {symbol["name"] for symbol in payload["symbols"]}
    assert {"Demo", "helper"} <= symbol_names


def test_search_endpoint_returns_results(api_client: TestClient) -> None:
    response = api_client.get("/search", params={"q": "demo"})
    assert response.status_code == 200
    results = response.json()["results"]
    assert any(item["name"] == "Demo" for item in results)


def test_rescan_endpoint_triggers_scan(api_client: TestClient, tmp_path: Path) -> None:
    response = api_client.post("/rescan")
    assert response.status_code == 200
    assert response.json()["files"] >= 1


def test_ollama_status_endpoint_returns_payload(
    api_client: TestClient, monkeypatch
) -> None:
    from code_map.api import integrations as integrations_module
    from code_map.integrations import OllamaDiscovery, OllamaStatus

    fake_timestamp = datetime(2024, 1, 1, tzinfo=timezone.utc)
    fake_status = OllamaStatus(
        installed=True,
        running=False,
        models=[],
        version="0.1.0",
        binary_path="/usr/bin/ollama",
        endpoint="http://127.0.0.1:11434",
        warning=None,
        error=None,
    )

    def fake_discover(*, timeout: float = 1.5) -> OllamaDiscovery:  # type: ignore[override]
        return OllamaDiscovery(status=fake_status, checked_at=fake_timestamp)

    monkeypatch.setattr(integrations_module, "discover_ollama", fake_discover)

    response = api_client.get("/integrations/ollama/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"]["installed"] is True
    assert payload["status"]["running"] is False
    returned_ts = payload["checked_at"]
    parsed = datetime.fromisoformat(returned_ts.replace("Z", "+00:00"))
    assert parsed == fake_timestamp


def test_ollama_start_endpoint_returns_payload(
    api_client: TestClient, monkeypatch
) -> None:
    from code_map.api import integrations as integrations_module
    from code_map.integrations import OllamaStartResult, OllamaStatus

    fake_status = OllamaStatus(
        installed=True,
        running=True,
        models=[],
        version="0.1.0",
        binary_path="/usr/bin/ollama",
        endpoint="http://127.0.0.1:11434",
        warning=None,
        error=None,
    )
    fake_result = OllamaStartResult(
        started=True,
        already_running=False,
        endpoint=fake_status.endpoint,
        process_id=1234,
        status=fake_status,
        checked_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
    )

    def fake_start(**kwargs):
        return fake_result

    monkeypatch.setattr(integrations_module, "start_ollama_server", fake_start)

    response = api_client.post("/integrations/ollama/start", json={})
    assert response.status_code == 200
    payload = response.json()
    assert payload["started"] is True
    assert payload["process_id"] == 1234
    assert payload["status"]["running"] is True


def test_ollama_start_endpoint_handles_error(
    api_client: TestClient, monkeypatch
) -> None:
    from code_map.api import integrations as integrations_module
    from code_map.integrations import OllamaStartError

    def fake_start(**kwargs):
        raise OllamaStartError(
            "fallo al iniciar",
            endpoint="http://127.0.0.1:11434",
            original_error="missing binary",
        )

    monkeypatch.setattr(integrations_module, "start_ollama_server", fake_start)

    response = api_client.post("/integrations/ollama/start", json={})
    assert response.status_code == 502
    detail = response.json()["detail"]
    assert detail["message"] == "fallo al iniciar"
    assert detail["endpoint"] == "http://127.0.0.1:11434"


def test_ollama_test_endpoint_returns_response(
    api_client: TestClient, monkeypatch
) -> None:
    from code_map.api import integrations as integrations_module
    from code_map.integrations.ollama_service import OllamaChatResponse

    def fake_chat_with_ollama(**kwargs) -> OllamaChatResponse:
        return OllamaChatResponse(
            model=kwargs["model"],
            message="Hola mundo",
            raw={"message": {"content": "Hola mundo"}},
            latency_ms=42.5,
            endpoint="http://127.0.0.1:11434",
        )

    monkeypatch.setattr(integrations_module, "chat_with_ollama", fake_chat_with_ollama)

    response = api_client.post(
        "/integrations/ollama/test",
        json={"model": "llama3", "prompt": "ping"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["model"] == "llama3"
    assert payload["message"] == "Hola mundo"
    assert "raw" in payload


def test_ollama_test_endpoint_handles_error(
    api_client: TestClient, monkeypatch
) -> None:
    from code_map.api import integrations as integrations_module
    from code_map.integrations import OllamaChatError

    def fake_chat_with_ollama(**kwargs):
        raise OllamaChatError(
            "fallo de red",
            endpoint="http://127.0.0.1:11434",
            original_error="connection refused",
            status_code=None,
        )

    monkeypatch.setattr(integrations_module, "chat_with_ollama", fake_chat_with_ollama)

    response = api_client.post(
        "/integrations/ollama/test",
        json={"model": "llama3", "prompt": "ping"},
    )
    assert response.status_code == 502
    detail = response.json()["detail"]
    assert detail["message"] == "fallo de red"
    assert detail["endpoint"] == "http://127.0.0.1:11434"


def test_ollama_test_endpoint_handles_timeout(
    api_client: TestClient, monkeypatch
) -> None:
    from code_map.api import integrations as integrations_module
    from code_map.integrations import OllamaChatError

    loading_since = datetime(2024, 1, 1, tzinfo=timezone.utc)

    def fake_chat_with_ollama(**kwargs):
        raise OllamaChatError(
            "Ollama tardó demasiado en responder. El modelo podría seguir cargándose. Intenta de nuevo en unos segundos.",
            endpoint="http://127.0.0.1:11434",
            original_error="timeout",
            reason_code="timeout",
            retry_after_seconds=10.0,
            loading_since=loading_since,
        )

    monkeypatch.setattr(integrations_module, "chat_with_ollama", fake_chat_with_ollama)

    response = api_client.post(
        "/integrations/ollama/test",
        json={"model": "llama3", "prompt": "ping"},
    )
    assert response.status_code == 502
    detail = response.json()["detail"]
    assert detail["reason_code"] == "timeout"
    assert detail["loading"] is True
    assert detail["message"].startswith("Ollama tardó demasiado en responder")


def test_ollama_test_endpoint_exposes_loading_hint(
    api_client: TestClient, monkeypatch
) -> None:
    from code_map.api import integrations as integrations_module
    from code_map.integrations import OllamaChatError

    loading_started = datetime(2024, 1, 1, tzinfo=timezone.utc)

    def fake_chat_with_ollama(**kwargs):
        raise OllamaChatError(
            "Ollama tardó demasiado en responder. El modelo podría seguir cargándose. Intenta de nuevo en unos segundos.",
            endpoint="http://127.0.0.1:11434",
            original_error="timeout",
            reason_code="timeout",
            retry_after_seconds=10.0,
            loading_since=loading_started,
        )

    monkeypatch.setattr(integrations_module, "chat_with_ollama", fake_chat_with_ollama)

    response = api_client.post(
        "/integrations/ollama/test",
        json={"model": "llama3", "prompt": "ping"},
    )
    assert response.status_code == 502
    detail = response.json()["detail"]
    assert detail["reason_code"] == "timeout"
    assert detail["loading"] is True
    assert detail["retry_after_seconds"] == pytest.approx(10.0)
    assert detail["loading_since"].startswith("2024-01-01T00:00:00")


def test_get_settings_endpoint(api_client: TestClient) -> None:
    response = api_client.get("/settings")
    assert response.status_code == 200
    payload = response.json()
    assert payload["root_path"]
    assert payload["absolute_root"].startswith("/")
    assert payload["include_docstrings"] is True
    assert payload["ollama_insights_enabled"] is False
    assert payload["ollama_insights_model"] is None
    assert payload["ollama_insights_frequency_minutes"] is None
    assert "exclude_dirs" in payload


def test_update_settings_toggle_docstrings(api_client: TestClient) -> None:
    response = api_client.put("/settings", json={"include_docstrings": False})
    assert response.status_code == 200
    body = response.json()
    assert "include_docstrings" in body["updated"]
    assert body["settings"]["include_docstrings"] is False


def test_update_settings_toggle_ollama_insights(api_client: TestClient) -> None:
    response = api_client.put("/settings", json={"ollama_insights_enabled": True})
    assert response.status_code == 200
    body = response.json()
    assert "ollama_insights_enabled" in body["updated"]
    assert body["settings"]["ollama_insights_enabled"] is True


def test_update_settings_updates_ollama_insights_details(
    api_client: TestClient,
) -> None:
    response = api_client.put(
        "/settings",
        json={
            "ollama_insights_model": "gpt-oss:latest",
            "ollama_insights_frequency_minutes": 45,
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert "ollama_insights_model" in body["updated"]
    assert "ollama_insights_frequency_minutes" in body["updated"]
    assert body["settings"]["ollama_insights_model"] == "gpt-oss:latest"
    assert body["settings"]["ollama_insights_frequency_minutes"] == 45


def test_ollama_analyze_endpoint_generates_insight(
    api_client: TestClient, monkeypatch
) -> None:
    from code_map.api import integrations as integrations_module
    from code_map.insights import OllamaInsightResult

    generated_at = datetime(2024, 1, 1, tzinfo=timezone.utc)

    def fake_run(**kwargs) -> OllamaInsightResult:
        model_name = kwargs.get("model", "default")
        return OllamaInsightResult(
            model=model_name,
            generated_at=generated_at,
            message="Acciones sugeridas",
            raw=OllamaChatResponse(
                model=model_name,
                message="Acciones sugeridas",
                raw={"ok": True},
                latency_ms=5.0,
                endpoint="http://localhost",
            ),
        )

    recorded = {}

    def fake_record(**kwargs):
        recorded.update(kwargs)
        return 1

    monkeypatch.setattr(integrations_module, "run_ollama_insights", fake_run)
    monkeypatch.setattr(integrations_module, "record_insight", fake_record)

    state: AppState = api_client.app.state.app_state  # type: ignore[attr-defined]
    original_scheduler = state._schedule_insights_pipeline
    original_context = state._build_insights_context

    from types import MethodType

    async def fake_context_method(self):  # type: ignore[no-untyped-def]
        return "Contexto de prueba"

    state._schedule_insights_pipeline = MethodType(lambda self, *args, **kwargs: None, state)  # type: ignore[assignment]
    state._build_insights_context = MethodType(fake_context_method, state)  # type: ignore[assignment]

    try:
        response = api_client.post(
            "/integrations/ollama/analyze",
            json={"model": "gpt-oss:test", "timeout_seconds": 30},
        )
    finally:
        state._schedule_insights_pipeline = original_scheduler  # type: ignore[assignment]
        state._build_insights_context = original_context  # type: ignore[assignment]

    assert response.status_code == 200
    payload = response.json()
    assert payload["model"] == "gpt-oss:test"
    assert payload["message"] == "Acciones sugeridas"
    assert recorded["model"] == "gpt-oss:test"


def test_ollama_insights_history_endpoint(api_client: TestClient, monkeypatch) -> None:
    from code_map.api import integrations as integrations_module
    from code_map.insights import StoredInsight

    items = [
        StoredInsight(
            id=1,
            model="gpt-oss:latest",
            message="abc",
            generated_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
            root_path=None,
        ),
        StoredInsight(
            id=2,
            model="gpt-mini",
            message="def",
            generated_at=datetime(2024, 1, 2, tzinfo=timezone.utc),
            root_path=None,
        ),
    ]

    monkeypatch.setattr(
        integrations_module, "list_insights", lambda limit, root_path: items[:limit]
    )

    response = api_client.get("/integrations/ollama/insights", params={"limit": 1})
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["model"] == "gpt-oss:latest"


def test_ollama_insights_clear_endpoint(api_client: TestClient, monkeypatch) -> None:
    from code_map.api import integrations as integrations_module

    monkeypatch.setattr(integrations_module, "clear_insights", lambda **kwargs: 5)

    state: AppState = api_client.app.state.app_state  # type: ignore[attr-defined]
    original_changes = state._recent_changes
    state._recent_changes = ["foo.py"]

    response = api_client.delete("/integrations/ollama/insights")
    assert response.status_code == 200
    payload = response.json()
    assert payload["deleted"] == 5
    assert state._recent_changes == []

    state._recent_changes = original_changes


def test_update_settings_updates_exclude_dirs(api_client: TestClient) -> None:
    response = api_client.put("/settings", json={"exclude_dirs": ["build", "dist"]})
    assert response.status_code == 200
    body = response.json()
    assert "exclude_dirs" in body["updated"]
    excludes = body["settings"]["exclude_dirs"]
    assert "build" in excludes
    assert "dist" in excludes


def test_update_settings_invalid_root_returns_400(api_client: TestClient) -> None:
    response = api_client.put(
        "/settings", json={"root_path": "/path/that/does/not/exist"}
    )
    assert response.status_code == 400


def test_status_endpoint_returns_metrics(api_client: TestClient) -> None:
    response = api_client.get("/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["files_indexed"] >= 1
    assert "symbols_indexed" in payload
    assert payload["watcher_active"] in {True, False}
    assert payload["ollama_insights_enabled"] in {True, False}
    assert "ollama_insights_model" in payload
    assert "ollama_insights_frequency_minutes" in payload
    assert "ollama_insights_last_run" in payload
    assert "ollama_insights_next_run" in payload
    assert isinstance(payload["capabilities"], list)


def test_preview_endpoint_returns_html(tmp_path: Path) -> None:
    app, _state = create_test_app(tmp_path)
    write_file(tmp_path, "page/index.html", "<html><body>Hi</body></html>")
    with TestClient(app) as client:
        response = client.get("/preview", params={"path": "page/index.html"})
        assert response.status_code == 200
        assert response.text.strip() == "<html><body>Hi</body></html>"
        assert "text/html" in response.headers.get("content-type", "")


def test_preview_endpoint_returns_plain_text(tmp_path: Path) -> None:
    app, _state = create_test_app(tmp_path)
    write_file(tmp_path, "notes/info.txt", "Just text content")
    with TestClient(app) as client:
        response = client.get("/preview", params={"path": "notes/info.txt"})
        assert response.status_code == 200
        assert response.text.strip() == "Just text content"
        assert response.headers.get("content-type") == "text/plain; charset=utf-8"


def test_preview_endpoint_missing_file_returns_404(tmp_path: Path) -> None:
    app, _state = create_test_app(tmp_path)
    with TestClient(app) as client:
        response = client.get("/preview", params={"path": "unknown/file.md"})
        assert response.status_code == 404


def test_preview_endpoint_handles_json(tmp_path: Path) -> None:
    app, _state = create_test_app(tmp_path)
    write_file(tmp_path, "data/sample.json", '{"hello": "world"}')
    with TestClient(app) as client:
        response = client.get("/preview", params={"path": "data/sample.json"})
        assert response.status_code == 200
        assert response.headers.get("content-type") == "application/json; charset=utf-8"
        payload = json.loads(response.text)
        assert payload == {"hello": "world"}


def test_preview_endpoint_rejects_large_file(tmp_path: Path) -> None:
    app, _state = create_test_app(tmp_path)
    large_content = "x" * (MAX_PREVIEW_BYTES + 10)
    write_file(tmp_path, "logs/big.log", large_content)
    with TestClient(app) as client:
        response = client.get("/preview", params={"path": "logs/big.log"})
        assert response.status_code == 413
        assert "demasiado grande" in response.json()["detail"].lower()


def test_preview_endpoint_rejects_binary_file(tmp_path: Path) -> None:
    app, _state = create_test_app(tmp_path)
    write_binary(tmp_path, "images/logo.png", b"\x89PNG\r\n\x1a\n" + b"0" * 100)
    with TestClient(app) as client:
        response = client.get("/preview", params={"path": "images/logo.png"})
        assert response.status_code == 415
        assert "no compatible" in response.json()["detail"].lower()


def test_audit_run_flow(api_client: TestClient) -> None:
    create_resp = api_client.post(
        "/audit/runs",
        json={"name": "Demo run", "notes": "Pair programming audit"},
    )
    assert create_resp.status_code == 200
    run = create_resp.json()
    run_id = run["id"]
    assert run["status"] == "open"

    list_resp = api_client.get("/audit/runs")
    assert list_resp.status_code == 200
    runs_payload = list_resp.json()
    assert any(item["id"] == run_id for item in runs_payload["runs"])

    event_resp = api_client.post(
        f"/audit/runs/{run_id}/events",
        json={"type": "command", "title": "Run tests", "actor": "agent"},
    )
    assert event_resp.status_code == 200
    event_payload = event_resp.json()
    assert event_payload["run_id"] == run_id
    assert event_payload["type"] == "command"

    events_resp = api_client.get(f"/audit/runs/{run_id}/events")
    assert events_resp.status_code == 200
    events = events_resp.json()["events"]
    assert len(events) == 1
    assert events[0]["title"] == "Run tests"

    close_resp = api_client.post(f"/audit/runs/{run_id}/close", json={"status": "closed"})
    assert close_resp.status_code == 200
    closed_run = close_resp.json()
    assert closed_run["status"] == "closed"


def test_linters_discovery_endpoint(api_client: TestClient) -> None:
    response = api_client.get("/linters/discovery")
    assert response.status_code == 200
    payload = response.json()
    assert payload["root_path"]
    expected = {"ruff", "black", "mypy", "bandit", "pytest", "pytest_cov", "pre_commit"}
    tool_keys = {tool["key"] for tool in payload["tools"]}
    assert expected <= tool_keys
    assert all(isinstance(tool["installed"], bool) for tool in payload["tools"])
    assert any(rule["key"] == "max_file_length" for rule in payload["custom_rules"])
    assert isinstance(payload["notifications"], list)


def test_linters_reports_endpoints(api_client: TestClient, tmp_path: Path) -> None:
    report = build_sample_report(tmp_path)
    report_id = record_linters_report(report)

    list_response = api_client.get("/linters/reports")
    assert list_response.status_code == 200
    items = list_response.json()
    assert any(item["id"] == report_id for item in items)

    latest_response = api_client.get("/linters/reports/latest")
    assert latest_response.status_code == 200
    latest = latest_response.json()
    assert latest["report"]["summary"]["overall_status"] == "warn"
    assert latest["report"]["chart_data"]["issues_by_tool"]["ruff"] == 2

    detail_response = api_client.get(f"/linters/reports/{report_id}")
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["id"] == report_id
    assert detail["report"]["custom_rules"][0]["violations"][0]["severity"] == "high"

    missing_response = api_client.get("/linters/reports/9999")
    assert missing_response.status_code == 404


def test_linters_notifications_flow(api_client: TestClient, tmp_path: Path) -> None:
    notification_id = record_notification(
        channel="linters",
        severity=Severity.CRITICAL,
        title="Fallo crítico",
        message="Se detectó un fallo grave",
        root_path=tmp_path,
        payload={"report_id": 1},
    )

    list_response = api_client.get("/linters/notifications")
    assert list_response.status_code == 200
    notifications = list_response.json()
    assert any(item["id"] == notification_id for item in notifications)

    mark_response = api_client.post(f"/linters/notifications/{notification_id}/read")
    assert mark_response.status_code == 204

    after_mark = api_client.get("/linters/notifications")
    assert after_mark.status_code == 200
    assert any(
        item["id"] == notification_id and item["read"] is True
        for item in after_mark.json()
    )

    unread_response = api_client.get(
        "/linters/notifications", params={"unread_only": "true"}
    )
    assert unread_response.status_code == 200
    assert unread_response.json() == []

    missing_mark = api_client.post("/linters/notifications/9999/read")
    assert missing_mark.status_code == 404
