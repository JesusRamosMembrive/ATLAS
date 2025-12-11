# SPDX-License-Identifier: MIT
"""
Rutas relacionadas con la previsualización de archivos.
"""

from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Iterator

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from ..exceptions import (
    FileNotFoundError,
    InvalidPathError,
    FileTooLargeError,
    BinaryFileError,
    EncodingError,
    InternalError,
)
from ..state import AppState
from .deps import get_app_state

router = APIRouter()

MAX_PREVIEW_BYTES = 512 * 1024  # 512 KiB
STREAM_CHUNK_SIZE = 16 * 1024
ADDITIONAL_TEXT_MIME_TYPES = {
    "application/javascript",
    "application/json",
    "application/xml",
    "application/yaml",
    "application/x-yaml",
    "text/yaml",
    "application/toml",
    "application/x-toml",
    "text/toml",
    "application/json5",
}

CUSTOM_TEXT_MEDIA_TYPES = {
    ".yml": "application/yaml",
    ".yaml": "application/yaml",
    ".toml": "application/toml",
    ".ini": "text/plain",
    ".env": "text/plain",
    ".cfg": "text/plain",
    ".json5": "application/json5",
    ".jsonc": "application/json",
}


@router.get("/preview")
async def preview_file(
    path: str = Query(..., description="Ruta relativa al root configurado."),
    state: AppState = Depends(get_app_state),
) -> StreamingResponse:
    """Obtiene el contenido de un archivo para previsualización."""
    try:
        target_path = state.resolve_path(path)
    except ValueError as exc:
        raise InvalidPathError(path=path, reason=str(exc)) from exc

    if not target_path.exists() or not target_path.is_file():
        raise FileNotFoundError(path=path)

    try:
        file_stat = target_path.stat()
    except OSError as exc:
        raise InternalError() from exc

    if file_stat.st_size > MAX_PREVIEW_BYTES:
        raise FileTooLargeError(
            path=path,
            size=file_stat.st_size,
            max_size=MAX_PREVIEW_BYTES,
        )

    media_type = _guess_media_type(target_path)
    if not _is_previewable_media(media_type):
        raise BinaryFileError(path=path)

    try:
        stream = _stream_text_file(target_path)
    except UnicodeDecodeError as exc:
        raise EncodingError("El archivo no contiene texto UTF-8 válido.") from exc
    except OSError as exc:
        raise InternalError() from exc

    media_type_with_charset = f"{media_type}; charset=utf-8"
    return StreamingResponse(stream, media_type=media_type_with_charset)


def _guess_media_type(path: Path) -> str:
    custom_type = CUSTOM_TEXT_MEDIA_TYPES.get(path.suffix.lower())
    if custom_type:
        return custom_type

    mime_type, _encoding = mimetypes.guess_type(path.name)
    if not mime_type:
        return "text/plain"
    return mime_type


def _is_previewable_media(media_type: str) -> bool:
    if media_type.startswith("text/"):
        return True
    return media_type in ADDITIONAL_TEXT_MIME_TYPES


def _stream_text_file(path: Path) -> Iterator[str]:
    with path.open("r", encoding="utf-8") as handle:
        while True:
            chunk = handle.read(STREAM_CHUNK_SIZE)
            if not chunk:
                break
            yield chunk
