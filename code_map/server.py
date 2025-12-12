# SPDX-License-Identifier: MIT
"""
Aplicación FastAPI principal.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Optional, Any

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from .scheduler import ChangeScheduler
from .state import AppState
from .settings import load_settings, save_settings
from .api.routes import router as api_router
from .api.error_handlers import register_exception_handlers

# Socket.IO PTY server (Unix only for now)
_IS_WINDOWS = sys.platform == "win32"
_pty_server: Optional[Any] = None

logger = logging.getLogger(__name__)


def _parse_allowed_origins() -> list[str]:
    raw = os.getenv("CODE_MAP_CORS_ALLOWED_ORIGINS")
    if not raw:
        # Default origins for local development
        return [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:3000",
            "http://127.0.0.1:3000",
        ]
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

    # Register centralized exception handlers
    register_exception_handlers(app)

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


def create_app_with_socketio(root: Optional[str | Path] = None) -> Any:
    """
    Create FastAPI app combined with Socket.IO PTY server.

    On Unix: Returns combined ASGI app with Socket.IO at /pty namespace
    On Windows: Returns combined ASGI app but PTY sessions will be rejected

    Args:
        root: Project root path

    Returns:
        Combined ASGI application
    """
    global _pty_server

    fastapi_app = create_app(root)

    try:
        from .terminal.socketio_pty import SocketIOPTYServer

        cors_origins = _parse_allowed_origins()
        _pty_server = SocketIOPTYServer(cors_allowed_origins=cors_origins)

        # Combine Socket.IO with FastAPI
        combined_app = _pty_server.get_asgi_app(fastapi_app)

        if _IS_WINDOWS:
            logger.info(
                "Socket.IO server initialized (Windows mode - PTY sessions not available)"
            )
        else:
            logger.info("Socket.IO PTY server initialized at /pty namespace")

        return combined_app

    except ImportError as e:
        logger.warning(f"Socket.IO PTY not available: {e}. Using WebSocket fallback.")
        return fastapi_app
    except Exception as e:
        logger.error(
            f"Failed to initialize Socket.IO PTY: {e}. Using WebSocket fallback."
        )
        return fastapi_app


# Default app without Socket.IO (for backwards compatibility)
app = create_app()

# Combined app with Socket.IO PTY support
app_with_socketio = create_app_with_socketio()
