# SPDX-License-Identifier: MIT
"""
Rutas para gestionar la inicialización y verificación Stage-Aware.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends

from ..exceptions import InternalError
from ..stage_toolkit import (
    AgentSelection,
    install_superclaude_framework,
    run_initializer,
    stage_status,
)
from ..state import AppState
from .deps import get_app_state
from .schemas import (
    StageInitRequest,
    StageInitResponse,
    StageStatusResponse,
    SuperClaudeInstallResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/stage", tags=["stage"])


@router.get("/status", response_model=StageStatusResponse)
async def get_stage_status(
    state: AppState = Depends(get_app_state),
) -> StageStatusResponse:
    """Devuelve el estado actual de los archivos Stage-Aware del proyecto."""
    payload = await stage_status(state.settings.root_path, index=state.index)
    return StageStatusResponse.model_validate(payload)


@router.post("/init", response_model=StageInitResponse)
async def initialize_stage_assets(
    request: StageInitRequest,
    state: AppState = Depends(get_app_state),
) -> StageInitResponse:
    """
    Ejecuta init_project.py sobre el root actual para instalar instrucciones.

    Soporta:
    - agents: "claude", "codex", "gemini", "both" (claude+codex), "all" (los tres)
    - force: Si True, fuerza reinstalación limpia
    """
    try:
        agents: AgentSelection = request.agents  # type: ignore[assignment]
        force: bool = getattr(request, "force", False)
        result = await run_initializer(state.settings.root_path, agents, force=force)
        return StageInitResponse.model_validate(result)
    except Exception as exc:
        logger.exception("Error initializing stage assets: %s", exc)
        raise InternalError(f"Error initializing stage assets: {exc}") from exc


@router.post("/superclaude/install", response_model=SuperClaudeInstallResponse)
async def install_superclaude(
    state: AppState = Depends(get_app_state),
) -> SuperClaudeInstallResponse:
    """Sincroniza los activos del framework SuperClaude en el workspace."""
    payload = await install_superclaude_framework(state.settings.root_path)
    return SuperClaudeInstallResponse.model_validate(payload)
