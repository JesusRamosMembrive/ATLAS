# SPDX-License-Identifier: MIT
"""
Router compuesto que agrupa las rutas por dominio.
"""

from __future__ import annotations

from fastapi import APIRouter

from .analysis import router as analysis_router
from .graph import router as graph_router
from .linters import router as linters_router
from .integrations import router as integrations_router
from .preview import router as preview_router
from .settings import router as settings_router
from .stage import router as stage_router
from .timeline import router as timeline_router
from .tracer import router as tracer_router
from .audit import router as audit_router
from .terminal import router as terminal_router

router = APIRouter()
router.include_router(analysis_router)
router.include_router(graph_router)
router.include_router(linters_router)
router.include_router(settings_router)
router.include_router(preview_router)
router.include_router(stage_router)
router.include_router(integrations_router)
router.include_router(timeline_router)
router.include_router(tracer_router)
router.include_router(audit_router)
router.include_router(terminal_router)
