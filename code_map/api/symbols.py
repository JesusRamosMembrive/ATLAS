# SPDX-License-Identifier: MIT
"""
API endpoints for symbol queries and resolution.

Provides endpoints to query symbols by location, search by name,
and retrieve symbol details with their members.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from ..models import SymbolInfo, SymbolKind
from ..state import AppState
from .deps import get_app_state

router = APIRouter(prefix="/symbols", tags=["symbols"])
logger = logging.getLogger(__name__)


# =============================================================================
# Response Schemas
# =============================================================================


class SymbolMember(BaseModel):
    """A member (method/attribute) of a class symbol."""

    name: str
    kind: str  # "method" | "function" | "class"
    lineno: int
    docstring: Optional[str] = None


class SymbolDetailsResponse(BaseModel):
    """Detailed information about a symbol at a specific location."""

    # Core symbol info
    name: str
    kind: str  # "class" | "function" | "method"
    lineno: int
    file_path: str
    docstring: Optional[str] = None

    # Parent class (for methods)
    parent: Optional[str] = None

    # Members (for classes)
    members: List[SymbolMember] = []

    # Metrics if available
    metrics: Optional[Dict[str, Any]] = None


class SymbolSearchResult(BaseModel):
    """A single symbol search result."""

    name: str
    kind: str
    lineno: int
    file_path: str
    parent: Optional[str] = None


class SymbolSearchResponse(BaseModel):
    """Response for symbol search queries."""

    results: List[SymbolSearchResult]
    total: int


# =============================================================================
# Helper Functions
# =============================================================================


def _find_symbol_at_line(
    state: AppState, file_path: Path, line: int
) -> Optional[SymbolInfo]:
    """
    Find the symbol defined at or closest to the given line.

    For classes, we want the class definition.
    For methods, we want the method but also know the parent class.
    """
    summary = state.index.get_file(file_path)
    if summary is None:
        return None

    # Find exact match first
    for symbol in summary.symbols:
        if symbol.lineno == line:
            return symbol

    # Find closest symbol before the line (for cases where line is inside a definition)
    closest: Optional[SymbolInfo] = None
    closest_distance = float("inf")

    for symbol in summary.symbols:
        if symbol.lineno <= line:
            distance = line - symbol.lineno
            if distance < closest_distance:
                closest = symbol
                closest_distance = distance

    return closest


def _get_class_members(
    state: AppState, file_path: Path, class_name: str
) -> List[SymbolMember]:
    """Get all methods/members of a class."""
    summary = state.index.get_file(file_path)
    if summary is None:
        return []

    members: List[SymbolMember] = []
    for symbol in summary.symbols:
        if symbol.parent == class_name:
            members.append(
                SymbolMember(
                    name=symbol.name,
                    kind=symbol.kind.value,
                    lineno=symbol.lineno,
                    docstring=symbol.docstring,
                )
            )

    # Sort by line number
    members.sort(key=lambda m: m.lineno)
    return members


# =============================================================================
# Endpoints
# =============================================================================


@router.get("/at-location", response_model=SymbolDetailsResponse)
async def get_symbol_at_location(
    file_path: str = Query(..., description="Path to the source file"),
    line: int = Query(..., description="Line number (1-indexed)"),
    state: AppState = Depends(get_app_state),
) -> SymbolDetailsResponse:
    """
    Get detailed symbol information at a specific file:line location.

    This endpoint resolves a location (file + line number) to the symbol
    defined there, including:
    - Symbol name and kind (class/function/method)
    - Docstring if available
    - For classes: list of member methods
    - For methods: parent class name

    Args:
        file_path: Path to the source file (relative or absolute)
        line: Line number where the symbol is defined (1-indexed)

    Returns:
        SymbolDetailsResponse with full symbol details

    Raises:
        404: If no symbol found at the specified location
    """
    # Resolve path
    path = Path(file_path)
    if not path.is_absolute():
        path = state.settings.root_path / path
    path = path.resolve()

    logger.debug("Looking up symbol at %s:%d", path, line)

    # Find the symbol
    symbol = _find_symbol_at_line(state, path, line)

    if symbol is None:
        # Return a minimal response if no symbol found
        # This can happen if the file hasn't been indexed yet
        logger.warning("No symbol found at %s:%d", path, line)
        return SymbolDetailsResponse(
            name="<unknown>",
            kind="unknown",
            lineno=line,
            file_path=str(path),
            docstring=None,
            parent=None,
            members=[],
        )

    # Build response
    response = SymbolDetailsResponse(
        name=symbol.name,
        kind=symbol.kind.value,
        lineno=symbol.lineno,
        file_path=str(symbol.path),
        docstring=symbol.docstring,
        parent=symbol.parent,
        metrics=symbol.metrics if symbol.metrics else None,
    )

    # If it's a class, get its members
    if symbol.kind == SymbolKind.CLASS:
        response.members = _get_class_members(state, path, symbol.name)

    logger.debug(
        "Found symbol: %s (%s) with %d members",
        symbol.name,
        symbol.kind.value,
        len(response.members),
    )

    return response


@router.get("/search", response_model=SymbolSearchResponse)
async def search_symbols(
    query: str = Query(..., min_length=1, description="Search term"),
    limit: int = Query(50, ge=1, le=200, description="Maximum results"),
    state: AppState = Depends(get_app_state),
) -> SymbolSearchResponse:
    """
    Search for symbols by name.

    Performs a case-insensitive substring search across all indexed symbols.

    Args:
        query: Search term (minimum 1 character)
        limit: Maximum number of results to return (1-200)

    Returns:
        SymbolSearchResponse with matching symbols
    """
    results = state.index.search(query)

    # Convert to response format and limit
    search_results = [
        SymbolSearchResult(
            name=s.name,
            kind=s.kind.value,
            lineno=s.lineno,
            file_path=str(s.path),
            parent=s.parent,
        )
        for s in results[:limit]
    ]

    return SymbolSearchResponse(
        results=search_results,
        total=len(results),
    )


@router.get("/file/{file_path:path}", response_model=List[SymbolSearchResult])
async def get_symbols_in_file(
    file_path: str,
    state: AppState = Depends(get_app_state),
) -> List[SymbolSearchResult]:
    """
    Get all symbols defined in a specific file.

    Args:
        file_path: Path to the source file (relative or absolute)

    Returns:
        List of symbols defined in the file, sorted by line number
    """
    # Resolve path
    path = Path(file_path)
    if not path.is_absolute():
        path = state.settings.root_path / path
    path = path.resolve()

    summary = state.index.get_file(path)
    if summary is None:
        return []

    results = [
        SymbolSearchResult(
            name=s.name,
            kind=s.kind.value,
            lineno=s.lineno,
            file_path=str(s.path),
            parent=s.parent,
        )
        for s in sorted(summary.symbols, key=lambda x: x.lineno)
    ]

    return results
