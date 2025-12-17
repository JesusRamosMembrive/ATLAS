# SPDX-License-Identifier: MIT
"""
Rutas para gestionar settings y estado de la aplicación.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import asyncio

from fastapi import APIRouter, Depends

from ..exceptions import (
    FileNotFoundError,
    InvalidPathError,
    InvalidConfigError,
    PermissionDeniedError,
    ValidationError,
)
from ..state import AppState
from .deps import get_app_state
from .schemas import (
    BrowseDirectoryResponse,
    DirectoryItem,
    FileItem,
    ListDirectoriesResponse,
    ListFilesResponse,
    SettingsResponse,
    SettingsUpdateRequest,
    SettingsUpdateResponse,
    StatusResponse,
    serialize_settings,
    serialize_status,
)

router = APIRouter()


@router.get("/settings", response_model=SettingsResponse)
async def get_settings(state: AppState = Depends(get_app_state)) -> SettingsResponse:
    """Obtiene la configuración actual de la aplicación."""
    return serialize_settings(state)


@router.put("/settings", response_model=SettingsUpdateResponse)
async def update_settings(
    payload: SettingsUpdateRequest,
    state: AppState = Depends(get_app_state),
) -> SettingsUpdateResponse:
    """Actualiza la configuración de la aplicación."""
    root_path: Optional[Path] = None
    if payload.root_path is not None:
        candidate = Path(payload.root_path).expanduser()
        if not candidate.is_absolute():
            candidate = (state.settings.root_path / candidate).resolve()
        else:
            candidate = candidate.resolve()
        root_path = candidate

    model_value: Optional[str] = None
    if payload.ollama_insights_model is not None:
        trimmed = payload.ollama_insights_model.strip()
        model_value = trimmed or None

    frequency_value = payload.ollama_insights_frequency_minutes
    focus_value: Optional[str] = None
    if payload.ollama_insights_focus is not None:
        focus_value = payload.ollama_insights_focus.strip()

    backend_url_value: Optional[str] = None
    if payload.backend_url is not None:
        trimmed_url = payload.backend_url.strip()
        backend_url_value = trimmed_url or None

    try:
        updated = await state.update_settings(
            root_path=root_path,
            include_docstrings=payload.include_docstrings,
            exclude_dirs=payload.exclude_dirs,
            ollama_insights_enabled=payload.ollama_insights_enabled,
            ollama_insights_model=model_value,
            ollama_insights_frequency_minutes=frequency_value,
            ollama_insights_focus=focus_value,
            backend_url=backend_url_value,
        )
    except ValueError as exc:
        raise InvalidConfigError(reason=str(exc)) from exc

    return SettingsUpdateResponse(
        updated=updated,
        settings=serialize_settings(state),
    )


@router.get("/status", response_model=StatusResponse)
async def get_status(state: AppState = Depends(get_app_state)) -> StatusResponse:
    """Obtiene el estado actual de la aplicación."""
    return serialize_status(state)


@router.post("/settings/browse", response_model=BrowseDirectoryResponse)
async def browse_directory(
    state: AppState = Depends(get_app_state),
) -> BrowseDirectoryResponse:
    """Abre un diálogo nativo para seleccionar un directorio."""

    def _select_directory(initial: Path) -> str:
        try:
            import tkinter as tk
            from tkinter import filedialog
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("tkinter no está disponible en este entorno") from exc

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        selected = filedialog.askdirectory(initialdir=str(initial))
        root.destroy()
        if not selected:
            raise RuntimeError("Selección cancelada")
        return selected

    try:
        path = await asyncio.to_thread(_select_directory, state.settings.root_path)
    except RuntimeError as exc:
        raise ValidationError(str(exc)) from exc

    return BrowseDirectoryResponse(path=path)


@router.get("/settings/list-directories", response_model=ListDirectoriesResponse)
async def list_directories(
    path: Optional[str] = None,
    state: AppState = Depends(get_app_state),
) -> ListDirectoriesResponse:
    """Lista directorios disponibles en el path especificado.

    Si no se especifica path, usa el root_path actual.
    Útil para Docker donde tkinter no está disponible.
    """
    # Determinar el directorio base
    if path:
        base_path = Path(path).expanduser().resolve()
    else:
        base_path = state.settings.root_path

    # Verificar que el path existe y es un directorio
    if not base_path.exists():
        raise FileNotFoundError(path=str(base_path))

    if not base_path.is_dir():
        raise InvalidPathError(
            path=str(base_path), reason="El path no es un directorio"
        )

    # Listar subdirectorios
    directories: list[DirectoryItem] = []

    # Agregar directorio padre si no estamos en la raíz
    if base_path.parent != base_path:
        directories.append(
            DirectoryItem(
                name="..",
                path=str(base_path.parent),
                is_parent=True,
            )
        )

    # Listar subdirectorios
    try:
        for item in sorted(base_path.iterdir()):
            if item.is_dir():
                # Excluir directorios ocultos y comunes que no son útiles
                if item.name.startswith("."):
                    continue
                if item.name in ("__pycache__", "node_modules", ".git"):
                    continue

                directories.append(
                    DirectoryItem(
                        name=item.name,
                        path=str(item),
                        is_parent=False,
                    )
                )
    except PermissionError:
        raise PermissionDeniedError(path=str(base_path), operation="read")

    return ListDirectoriesResponse(
        current_path=str(base_path),
        directories=directories,
    )


@router.get("/settings/list-files", response_model=ListFilesResponse)
async def list_files(
    path: Optional[str] = None,
    extensions: str = ".py",
    state: AppState = Depends(get_app_state),
) -> ListFilesResponse:
    """Lista directorios y archivos con extensiones específicas.

    Args:
        path: Directorio a explorar. Si no se especifica, usa root_path.
        extensions: Extensiones a filtrar, separadas por coma. Ej: ".py,.pyi"

    Útil para el browser de archivos de Call Flow y otras herramientas.
    """
    # Determinar el directorio base
    if path:
        base_path = Path(path).expanduser().resolve()
    else:
        base_path = state.settings.root_path

    # Verificar que el path existe y es un directorio
    if not base_path.exists():
        raise FileNotFoundError(path=str(base_path))

    if not base_path.is_dir():
        raise InvalidPathError(
            path=str(base_path), reason="El path no es un directorio"
        )

    # Parsear extensiones
    ext_list = [e.strip().lower() for e in extensions.split(",") if e.strip()]
    if not ext_list:
        ext_list = [".py"]

    directories: list[DirectoryItem] = []
    files: list[FileItem] = []

    # Agregar directorio padre si no estamos en la raíz
    if base_path.parent != base_path:
        directories.append(
            DirectoryItem(
                name="..",
                path=str(base_path.parent),
                is_parent=True,
            )
        )

    # Listar contenido
    try:
        for item in sorted(base_path.iterdir()):
            # Excluir ocultos y directorios comunes no útiles
            if item.name.startswith("."):
                continue
            if item.name in ("__pycache__", "node_modules", ".git", "venv", ".venv"):
                continue

            if item.is_dir():
                directories.append(
                    DirectoryItem(
                        name=item.name,
                        path=str(item),
                        is_parent=False,
                    )
                )
            elif item.is_file():
                # Filtrar por extensiones
                ext = item.suffix.lower()
                if ext in ext_list:
                    try:
                        size = item.stat().st_size
                    except OSError:
                        size = 0
                    files.append(
                        FileItem(
                            name=item.name,
                            path=str(item),
                            extension=ext,
                            size_bytes=size,
                        )
                    )
    except PermissionError:
        raise PermissionDeniedError(path=str(base_path), operation="read")

    return ListFilesResponse(
        current_path=str(base_path),
        directories=directories,
        files=files,
    )
