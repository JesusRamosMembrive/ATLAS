# SPDX-License-Identifier: MIT
"""
Endpoint para notificar cambios externos de archivos.

Este endpoint permite a editores externos (como Claude Code) notificar
cambios que no fueron detectados por el watcher de archivos.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends

from .deps import get_app_state
from .schemas import (
    FileChangeType,
    NotifyChangesRequest,
    NotifyChangesResponse,
    ProcessedChangeItem,
)
from ..state import AppState

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notify", tags=["notify"])


@router.post("/changes", response_model=NotifyChangesResponse)
async def notify_changes(
    request: NotifyChangesRequest,
    state: Annotated[AppState, Depends(get_app_state)],
) -> NotifyChangesResponse:
    """
    Notifica cambios externos de archivos para re-análisis.

    Este endpoint procesa cambios de archivos que no fueron detectados
    por el watcher (por ejemplo, cambios realizados por Claude Code).

    Los cambios se procesan inmediatamente (sin debounce) y se ejecutan
    los handlers registrados:
    - SSE broadcast: notifica a clientes conectados
    - Linters schedule: agenda ejecución de linters
    - Insights schedule: agenda generación de insights

    **Ejemplo de uso:**
    ```bash
    curl -X POST http://localhost:8010/api/notify/changes \\
      -H "Content-Type: application/json" \\
      -d '{
        "changes": [
          {"path": "src/main.py", "change_type": "modified"},
          {"path": "src/new.py", "change_type": "created"}
        ]
      }'
    ```

    **Respuesta:**
    ```json
    {
      "processed": 2,
      "skipped": 0,
      "errors": 0,
      "details": [...],
      "handlers_triggered": ["sse_broadcast", "linters_schedule", "insights_schedule"]
    }
    ```
    """
    logger.info("Received notify request with %d changes", len(request.changes))

    # Convert Pydantic models to dicts for state method
    changes_data = [
        {"path": change.path, "change_type": change.change_type.value}
        for change in request.changes
    ]

    result = await state.apply_external_changes(changes_data)

    # Convert details back to Pydantic models
    details = [
        ProcessedChangeItem(
            path=d["path"],
            change_type=FileChangeType(d["change_type"]),
            status=d["status"],
            reason=d.get("reason"),
        )
        for d in result["details"]
    ]

    response = NotifyChangesResponse(
        processed=result["processed"],
        skipped=result["skipped"],
        errors=result["errors"],
        details=details,
        handlers_triggered=result["handlers_triggered"],
    )

    logger.info(
        "Notify complete: processed=%d, skipped=%d, errors=%d, handlers=%s",
        response.processed,
        response.skipped,
        response.errors,
        response.handlers_triggered,
    )

    return response
