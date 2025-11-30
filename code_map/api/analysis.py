# SPDX-License-Identifier: MIT
"""
Rutas de análisis y exploración del proyecto.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncIterator, Dict, Iterable, List, Optional

import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from ..state import AppState
from ..git_history import GitHistory, GitHistoryError
from ..models import ProjectTreeNode, FileSummary
from .deps import get_app_state
from .schemas import (
    ChangeNotification,
    ChangesResponse,
    DocFileSchema,
    DocsListResponse,
    FileDiffResponse,
    FileSummarySchema,
    HealthResponse,
    RescanResponse,
    SearchResultsSchema,
    TreeNodeSchema,
    WorkingTreeChangeSchema,
    serialize_search_results,
    serialize_summary,
    serialize_tree,
)

router = APIRouter()
logger = logging.getLogger(__name__)

KEEPALIVE_SECONDS = 10


def _get_git_history(state: AppState) -> Optional[GitHistory]:
    try:
        return GitHistory(state.settings.root_path)
    except GitHistoryError as exc:
        logger.warning("Git history no disponible: %s", exc)
        return None


def _build_change_map(
    state: AppState, history: Optional[GitHistory]
) -> Dict[str, Dict[str, str]]:
    if history is None:
        return {}

    try:
        mapping: Dict[str, Dict[str, str]] = {}
        for change in history.get_working_tree_changes():
            absolute_path = (history.repo_path / change.path).resolve()
            relative_path = state.to_relative(absolute_path)
            mapping[relative_path] = change.payload()
        return mapping
    except GitHistoryError as exc:
        logger.warning("Error obteniendo cambios del working tree: %s", exc)
        return {}


def _serialize_change_entries(
    change_map: Dict[str, Dict[str, str]]
) -> List[WorkingTreeChangeSchema]:
    entries: List[WorkingTreeChangeSchema] = []
    for path in sorted(change_map.keys()):
        payload = change_map[path]
        entries.append(
            WorkingTreeChangeSchema(
                path=path,
                status=payload.get("status") or "modified",
                summary=payload.get("summary"),
            )
        )
    return entries


def _attach_missing_change_nodes(
    tree: ProjectTreeNode,
    root_path: Path,
    change_paths: Iterable[str],
) -> None:
    """Inserta nodos sintéticos para archivos con cambios no presentes en el índice."""

    for rel_path in change_paths:
        if not rel_path:
            continue

        parts = [part for part in Path(rel_path).parts if part]
        if not parts:
            continue

        node = tree
        current_path = root_path
        for index, part in enumerate(parts):
            current_path = current_path / part
            is_last = index == len(parts) - 1

            child = node.children.get(part)
            if child is None:
                child = ProjectTreeNode(
                    name=part,
                    path=current_path,
                    is_dir=not is_last,
                )
                node.children[part] = child

            node = child


def _change_payload_for_path(
    history: Optional[GitHistory],
    relative_path: str,
) -> Optional[Dict[str, str]]:
    if history is None:
        return None
    try:
        change = history.get_working_tree_change_for_path(relative_path)
    except GitHistoryError:
        return None
    if change is None:
        return None
    return change.payload()


def _create_generic_summary_for_file(path: Path) -> FileSummary:
    """Construye un FileSummary sin símbolos para archivos no indexados."""
    modified_at: Optional[datetime] = None
    try:
        stat = path.stat()
    except OSError:
        pass
    else:
        modified_at = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
    return FileSummary(path=path, modified_at=modified_at)


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Comprueba el estado de la API."""
    return HealthResponse()


@router.get("/tree", response_model=TreeNodeSchema)
async def get_tree(
    refresh: bool = Query(
        False, description="Fuerza un escaneo completo antes de responder."
    ),
    state: AppState = Depends(get_app_state),
) -> TreeNodeSchema:
    """Obtiene el árbol de archivos del proyecto."""
    if refresh:
        await state.perform_full_scan()
    tree = state.index.get_tree()
    git_history = _get_git_history(state)
    change_map = _build_change_map(state, git_history)
    if change_map:
        _attach_missing_change_nodes(tree, state.settings.root_path, change_map.keys())
    return serialize_tree(tree, state, change_map=change_map or None)


@router.get("/files/{file_path:path}", response_model=FileSummarySchema)
async def get_file(
    file_path: str,
    state: AppState = Depends(get_app_state),
) -> FileSummarySchema:
    """Obtiene el resumen de un archivo específico."""
    try:
        target_path = state.resolve_path(file_path)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if not target_path.exists():
        raise HTTPException(status_code=404, detail="Archivo no encontrado.")

    summary = state.index.get_file(target_path)
    if summary is None:
        summary = _create_generic_summary_for_file(target_path)

    git_history = _get_git_history(state)
    relative_path = state.to_relative(target_path)
    change_payload = _change_payload_for_path(git_history, relative_path)

    return serialize_summary(summary, state, change_payload)


@router.get("/file-diff/{file_path:path}", response_model=FileDiffResponse)
async def get_working_tree_diff(
    file_path: str,
    state: AppState = Depends(get_app_state),
) -> FileDiffResponse:
    """Devuelve el diff del working tree frente al último commit para un archivo."""

    try:
        target_path = state.resolve_path(file_path)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    git_history = _get_git_history(state)
    if git_history is None:
        raise HTTPException(
            status_code=400,
            detail="Proyecto fuera de un repositorio git. Inicializa git para rastrear cambios.",
        )

    relative_path = state.to_relative(target_path)

    try:
        diff = git_history.get_working_tree_diff(relative_path)
        change_payload = _change_payload_for_path(git_history, relative_path)
    except GitHistoryError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    return FileDiffResponse(
        path=relative_path,
        diff=diff,
        has_changes=bool(diff.strip()),
        change_status=change_payload.get("status") if change_payload else None,
        change_summary=change_payload.get("summary") if change_payload else None,
    )


@router.get("/changes", response_model=ChangesResponse)
async def list_working_tree_changes(
    state: AppState = Depends(get_app_state),
) -> ChangesResponse:
    """Lista todos los archivos con cambios detectados desde el último commit."""

    git_history = _get_git_history(state)
    if git_history is None:
        return ChangesResponse()

    change_map = _build_change_map(state, git_history)
    entries = _serialize_change_entries(change_map)
    return ChangesResponse(changes=entries)


@router.get("/docs", response_model=DocsListResponse)
async def list_docs_directory(
    state: AppState = Depends(get_app_state),
) -> DocsListResponse:
    """Lista los archivos markdown en docs/."""

    docs_dir = (state.settings.root_path / "docs").resolve()
    docs_relative = state.to_relative(docs_dir)

    if not docs_dir.exists() or not docs_dir.is_dir():
        return DocsListResponse(
            docs_path=docs_relative,
            exists=False,
            file_count=0,
            files=[],
        )

    files: List[DocFileSchema] = []
    for path in sorted(docs_dir.rglob("*.md")):
        if not path.is_file():
            continue
        try:
            stat_info = path.stat()
        except OSError:
            continue
        modified = datetime.fromtimestamp(stat_info.st_mtime, tz=timezone.utc)
        files.append(
            DocFileSchema(
                name=path.name,
                path=state.to_relative(path),
                size_bytes=stat_info.st_size,
                modified_at=modified,
            )
        )

    return DocsListResponse(
        docs_path=docs_relative,
        exists=True,
        file_count=len(files),
        files=files,
    )


@router.get("/search", response_model=SearchResultsSchema)
async def search(
    q: str = Query(
        ..., min_length=1, description="Texto a buscar en nombres de símbolos."
    ),
    state: AppState = Depends(get_app_state),
) -> SearchResultsSchema:
    """Busca símbolos en el proyecto."""
    symbols = state.index.search(q)
    return serialize_search_results(symbols, state)


async def _event_stream(state: AppState) -> AsyncIterator[bytes]:
    """Genera un flujo de eventos de cambio."""
    while True:
        try:
            payload = await asyncio.wait_for(
                state.event_queue.get(), timeout=KEEPALIVE_SECONDS
            )
            data = ChangeNotification(**payload)
            yield f"event: update\ndata: {data.json()}\n\n".encode("utf-8")
        except asyncio.TimeoutError:
            yield b": keepalive\n\n"


@router.get("/events")
async def events(state: AppState = Depends(get_app_state)) -> StreamingResponse:
    """Suscribe al flujo de eventos de cambio."""
    return StreamingResponse(_event_stream(state), media_type="text/event-stream")


@router.post("/rescan", response_model=RescanResponse)
async def rescan(state: AppState = Depends(get_app_state)) -> RescanResponse:
    """Dispara un escaneo completo del proyecto."""
    count = await state.perform_full_scan()
    return RescanResponse(files=count)
