# SPDX-License-Identifier: MIT
"""
Rutas relacionadas con la integración con Ollama.
"""

from __future__ import annotations

import asyncio
from dataclasses import asdict
from typing import List

from fastapi import APIRouter, Depends

from ..exceptions import (
    OllamaStartError as OllamaStartException,
    OllamaChatError as OllamaChatException,
    ModelNotConfiguredError,
    InternalError,
)
from ..integrations import (
    OllamaChatError,
    OllamaChatMessage,
    OllamaStartError,
    chat_with_ollama,
    discover_ollama,
    start_ollama_server,
)
from ..insights import list_insights_async, clear_insights_async, OLLAMA_DEFAULT_TIMEOUT
from ..state import AppState
from .deps import get_app_state
from .schemas import (
    OllamaStartRequest,
    OllamaStartResponse,
    OllamaStatusResponse,
    OllamaStatusSchema,
    OllamaTestRequest,
    OllamaTestResponse,
    OllamaInsightsRequest,
    OllamaInsightsResponse,
    OllamaInsightEntry,
    OllamaInsightsClearResponse,
)

router = APIRouter(prefix="/integrations", tags=["integrations"])


@router.get("/ollama/status", response_model=OllamaStatusResponse)
async def get_ollama_status() -> OllamaStatusResponse:
    """Devuelve el estado actual de Ollama (instalación, servicio y modelos)."""
    discovery = await asyncio.to_thread(discover_ollama)
    status_payload = OllamaStatusSchema.model_validate(asdict(discovery.status))
    return OllamaStatusResponse(status=status_payload, checked_at=discovery.checked_at)


@router.post("/ollama/start", response_model=OllamaStartResponse)
async def start_ollama(payload: OllamaStartRequest) -> OllamaStartResponse:
    """Intenta iniciar el servidor Ollama y devuelve el estado actualizado."""
    timeout = payload.timeout_seconds if payload.timeout_seconds is not None else 5.0
    try:
        result = await asyncio.to_thread(start_ollama_server, timeout=timeout)
    except OllamaStartError as exc:
        raise OllamaStartException(
            str(exc),
            endpoint=exc.endpoint,
            original_error=exc.original_error,
        ) from exc

    status_payload = OllamaStatusSchema.model_validate(asdict(result.status))
    return OllamaStartResponse(
        started=result.started,
        already_running=result.already_running,
        endpoint=result.endpoint,
        process_id=result.process_id,
        status=status_payload,
        checked_at=result.checked_at,
    )


@router.post("/ollama/test", response_model=OllamaTestResponse)
async def test_ollama_chat(payload: OllamaTestRequest) -> OllamaTestResponse:
    """
    Ejecuta un chat breve contra el modelo indicado para verificar conectividad con Ollama.
    """
    messages: List[OllamaChatMessage] = []
    if payload.system_prompt:
        messages.append(OllamaChatMessage(role="system", content=payload.system_prompt))
    messages.append(OllamaChatMessage(role="user", content=payload.prompt))

    timeout = (
        payload.timeout_seconds
        if payload.timeout_seconds is not None
        else OLLAMA_DEFAULT_TIMEOUT
    )

    try:
        result = await asyncio.to_thread(
            chat_with_ollama,
            model=payload.model,
            messages=messages,
            endpoint=payload.endpoint,
            timeout=timeout,
        )
    except OllamaChatError as exc:
        raise OllamaChatException(
            str(exc),
            endpoint=exc.endpoint,
            original_error=exc.original_error,
            status_code_response=exc.status_code,
            reason_code=exc.reason_code,
            retry_after_seconds=exc.retry_after_seconds,
            loading_since=exc.loading_since.isoformat() if exc.loading_since else None,
        ) from exc

    return OllamaTestResponse(
        success=True,
        model=result.model,
        endpoint=result.endpoint,
        latency_ms=result.latency_ms,
        message=result.message,
        raw=result.raw,
    )


@router.post("/ollama/analyze", response_model=OllamaInsightsResponse)
async def generate_ollama_insights(
    payload: OllamaInsightsRequest,
    state: AppState = Depends(get_app_state),
) -> OllamaInsightsResponse:
    """Genera insights manualmente usando la configuración actual."""

    model = payload.model or state.settings.ollama_insights_model
    if not model:
        raise ModelNotConfiguredError(
            "No hay modelo configurado para ejecutar insights."
        )

    timeout = (
        payload.timeout_seconds
        if payload.timeout_seconds is not None
        else OLLAMA_DEFAULT_TIMEOUT
    )

    focus_value = (
        payload.focus.strip().lower()
        if isinstance(payload.focus, str)
        else state.settings.ollama_insights_focus
    )

    try:
        result = await state.run_insights_now(
            model=model,
            focus=focus_value,
            timeout=timeout,
        )
    except OllamaChatError as exc:
        raise OllamaChatException(
            str(exc),
            endpoint=exc.endpoint,
            original_error=exc.original_error,
            status_code_response=exc.status_code,
        ) from exc
    except RuntimeError as exc:
        raise InternalError(str(exc)) from exc

    return OllamaInsightsResponse(
        model=result.model,
        generated_at=result.generated_at,
        message=result.message,
    )


@router.get("/ollama/insights", response_model=List[OllamaInsightEntry])
async def list_ollama_insights_endpoint(
    limit: int = 20,
    state: AppState = Depends(get_app_state),
) -> List[OllamaInsightEntry]:
    entries = await list_insights_async(
        limit=max(1, min(limit, 100)),
        root_path=state.settings.root_path,
    )
    return [
        OllamaInsightEntry(
            id=entry.id,
            model=entry.model,
            message=entry.message,
            generated_at=entry.generated_at,
        )
        for entry in entries
    ]


@router.delete("/ollama/insights", response_model=OllamaInsightsClearResponse)
async def clear_ollama_insights_endpoint(
    state: AppState = Depends(get_app_state),
) -> OllamaInsightsClearResponse:
    deleted = await clear_insights_async(
        root_path=state.settings.root_path,
    )
    return OllamaInsightsClearResponse(deleted=deleted)
