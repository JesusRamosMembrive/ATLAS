# SPDX-License-Identifier: MIT
"""
Rutas para exponer el estado de linters y reglas de calidad.
"""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, Query, status

from ..exceptions import ReportNotFoundError, NotificationNotFoundError, InternalError
from ..linters import (
    get_latest_linters_report_async,
    get_linters_report_async,
    get_notification_async,
    linters_discovery_payload,
    list_linters_reports_async,
    list_notifications_async,
    mark_notification_read_async,
    report_to_dict,
)
from ..state import AppState
from .deps import get_app_state
from .schemas import (
    LintersDiscoveryResponse,
    LintersReportListItemSchema,
    LintersReportRecordSchema,
    LintersReportSchema,
    NotificationEntrySchema,
)

router = APIRouter(prefix="/linters", tags=["linters"])


@router.get("/discovery", response_model=LintersDiscoveryResponse)
async def get_linters_discovery(
    state: AppState = Depends(get_app_state),
) -> LintersDiscoveryResponse:
    """Devuelve el resultado del proceso de discovery de herramientas de calidad."""
    payload = await linters_discovery_payload(state.settings.root_path)
    return LintersDiscoveryResponse(**payload)


def _to_report_item(stored) -> LintersReportListItemSchema:
    return LintersReportListItemSchema(
        id=stored.id,
        generated_at=stored.generated_at,
        root_path=stored.root_path,
        overall_status=stored.overall_status,
        issues_total=stored.issues_total,
        critical_issues=stored.critical_issues,
    )


def _to_report_record(stored) -> LintersReportRecordSchema:
    report_payload = report_to_dict(stored.report)
    return LintersReportRecordSchema(
        id=stored.id,
        generated_at=stored.generated_at,
        root_path=stored.root_path,
        overall_status=stored.overall_status,
        issues_total=stored.issues_total,
        critical_issues=stored.critical_issues,
        report=LintersReportSchema(**report_payload),
    )


def _to_notification_entry(entry) -> NotificationEntrySchema:
    return NotificationEntrySchema(
        id=entry.id,
        created_at=entry.created_at,
        channel=entry.channel,
        severity=entry.severity,
        title=entry.title,
        message=entry.message,
        payload=entry.payload,
        root_path=entry.root_path,
        read=entry.read,
    )


@router.get("/reports", response_model=List[LintersReportListItemSchema])
async def list_reports(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    state: AppState = Depends(get_app_state),
) -> List[LintersReportListItemSchema]:
    reports = await list_linters_reports_async(
        limit=limit,
        offset=offset,
        root_path=state.settings.root_path,
    )
    return [_to_report_item(report) for report in reports]


@router.get("/reports/latest", response_model=LintersReportRecordSchema)
async def get_latest_report(
    state: AppState = Depends(get_app_state),
) -> LintersReportRecordSchema:
    stored = await get_latest_linters_report_async(root_path=state.settings.root_path)
    if stored is None:
        raise ReportNotFoundError("No hay reportes disponibles")
    return _to_report_record(stored)


@router.get("/reports/{report_id}", response_model=LintersReportRecordSchema)
async def get_report(
    report_id: int, state: AppState = Depends(get_app_state)
) -> LintersReportRecordSchema:
    stored = await get_linters_report_async(report_id)
    if stored is None or stored.root_path != str(state.settings.root_path.resolve()):
        raise ReportNotFoundError(report_id=report_id)
    return _to_report_record(stored)


@router.get("/notifications", response_model=List[NotificationEntrySchema])
async def list_linters_notifications(
    limit: int = Query(50, ge=1, le=200),
    unread_only: bool = Query(False),
    state: AppState = Depends(get_app_state),
) -> List[NotificationEntrySchema]:
    notifications = await list_notifications_async(
        limit=limit,
        unread_only=unread_only,
        root_path=state.settings.root_path,
    )
    return [_to_notification_entry(item) for item in notifications]


@router.post(
    "/notifications/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT
)
async def mark_notification_as_read(
    notification_id: int,
    read: bool = True,
    state: AppState = Depends(get_app_state),
) -> None:
    notification = await get_notification_async(notification_id)
    normalized_root = str(state.settings.root_path.resolve())
    if notification is None or (
        notification.root_path and notification.root_path != normalized_root
    ):
        raise NotificationNotFoundError(notification_id=notification_id)

    updated = await mark_notification_read_async(notification_id, read=read)
    if not updated:
        raise NotificationNotFoundError(notification_id=notification_id)


@router.post("/run", response_model=LintersReportRecordSchema)
async def run_linters(
    state: AppState = Depends(get_app_state),
) -> LintersReportRecordSchema:
    """Ejecuta el pipeline de linters manualmente y retorna el nuevo reporte."""
    try:
        report_id = await state.run_linters_now()
    except RuntimeError as exc:
        raise InternalError(str(exc)) from exc

    stored = await get_linters_report_async(report_id)
    if stored is None or stored.root_path != str(state.settings.root_path.resolve()):
        raise InternalError("No se pudo generar el reporte")

    return _to_report_record(stored)
