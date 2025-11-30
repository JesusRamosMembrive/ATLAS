# SPDX-License-Identifier: MIT
"""
Aplicación FastAPI principal.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from .scheduler import ChangeScheduler
from .state import AppState
from .settings import load_settings, save_settings
from .api.routes import router as api_router


def _parse_allowed_origins() -> list[str]:
    raw = os.getenv("CODE_MAP_CORS_ALLOWED_ORIGINS")
    if not raw:
        return ["*"]
    origins = [origin.strip() for origin in raw.split(",")]
    cleaned = [origin for origin in origins if origin]
    return cleaned or ["*"]


def create_app(root: Optional[str | Path] = None) -> FastAPI:
    """
    Crea y configura la aplicación FastAPI.

    Args:
        root: La ruta raíz del proyecto a escanear.

    Returns:
        La instancia de la aplicación FastAPI.
    """
    settings = load_settings(root_override=root)
    scheduler = ChangeScheduler()

    state = AppState(
        settings=settings,
        scheduler=scheduler,
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await state.startup()
        try:
            yield
        finally:
            await state.shutdown()

    # Guardar settings al arranque por si se generaron con valores por defecto.
    save_settings(state.settings)

    app = FastAPI(title="Code Map API", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_parse_allowed_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router, prefix="/api")
    app.state.app_state = state  # type: ignore[attr-defined]

    # Serve frontend static files in production mode
    # The frontend is built into frontend/dist/ during Docker build
    frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
    if frontend_dist.exists() and frontend_dist.is_dir():
        # Mount static files at root path
        # html=True enables SPA fallback routing (all routes -> index.html)
        app.mount(
            "/", StaticFiles(directory=str(frontend_dist), html=True), name="static"
        )

    return app


app = create_app()
