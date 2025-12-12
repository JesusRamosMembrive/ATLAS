# SPDX-License-Identifier: MIT
"""
Utilidades relacionadas con linters y verificaciones de calidad.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from .discovery import discover_linters
from .report_schema import (
    ChartData,
    CheckStatus,
    CoverageSnapshot,
    CustomRuleResult,
    IssueDetail,
    LintersReport,
    ReportSummary,
    Severity,
    ToolRunResult,
    report_from_dict,
    report_to_dict,
)
from .pipeline import (
    LinterRunOptions,
    run_linters_pipeline,
    LINTER_TIMEOUT_FAST,
    LINTER_TIMEOUT_STANDARD,
    LINTER_TIMEOUT_TESTS,
)
from .storage import (
    StoredLintersReport,
    StoredNotification,
    # Sync versions
    get_latest_linters_report,
    get_linters_report,
    list_linters_reports,
    list_notifications,
    mark_notification_read,
    get_notification,
    record_linters_report,
    record_notification,
    # Async versions
    get_latest_linters_report_async,
    get_linters_report_async,
    list_linters_reports_async,
    list_notifications_async,
    mark_notification_read_async,
    get_notification_async,
    record_linters_report_async,
    record_notification_async,
)

__all__ = [
    "discover_linters",
    "linters_discovery_payload",
    "LintersReport",
    "ReportSummary",
    "ToolRunResult",
    "CustomRuleResult",
    "CoverageSnapshot",
    "ChartData",
    "IssueDetail",
    "CheckStatus",
    "Severity",
    "report_to_dict",
    "report_from_dict",
    "run_linters_pipeline",
    "LinterRunOptions",
    # Sync storage
    "record_linters_report",
    "get_linters_report",
    "get_latest_linters_report",
    "list_linters_reports",
    "StoredLintersReport",
    "record_notification",
    "list_notifications",
    "mark_notification_read",
    "StoredNotification",
    "get_notification",
    # Async storage
    "record_linters_report_async",
    "get_linters_report_async",
    "get_latest_linters_report_async",
    "list_linters_reports_async",
    "record_notification_async",
    "list_notifications_async",
    "mark_notification_read_async",
    "get_notification_async",
    "LINTER_TIMEOUT_FAST",
    "LINTER_TIMEOUT_STANDARD",
    "LINTER_TIMEOUT_TESTS",
]


async def linters_discovery_payload(root: Path) -> Dict[str, Any]:
    """
    Obtiene el payload listo para consumir por la API con información de linters.
    """
    return await discover_linters(root)
