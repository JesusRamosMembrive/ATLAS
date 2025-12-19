# SPDX-License-Identifier: MIT
"""
API routes for code similarity analysis.
"""

from __future__ import annotations

import logging
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from ..exceptions import (
    InvalidConfigError,
    ServiceUnavailableError,
    SimilarityServiceError as SimilarityException,
)
from ..similarity_service import (
    DEFAULT_EXCLUDE_PATTERNS,
    SimilarityServiceError,
    is_available,
)
from ..state import AppState
from .deps import get_app_state

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/similarity", tags=["similarity"])


# In-memory cache for the latest report
# _latest_report: Optional[dict[str, Any]] = None


# Request/Response schemas
class SimilarityAnalyzeRequest(BaseModel):
    """Request body for similarity analysis."""

    extensions: List[str] = Field(
        default=[".py"], description="File extensions to analyze"
    )
    exclude_patterns: Optional[List[str]] = Field(
        default=None,
        description="Glob patterns to exclude (e.g., '**/tests/**', '**/venv/**'). If null, uses defaults.",
    )
    min_tokens: int = Field(
        default=30, ge=5, le=500, description="Minimum tokens for a clone"
    )
    min_similarity: float = Field(
        default=0.7, ge=0.5, le=1.0, description="Minimum similarity threshold"
    )
    type3: bool = Field(default=False, description="Enable Type-3 detection")
    max_gap: int = Field(default=5, ge=1, le=20, description="Maximum gap for Type-3")
    threads: Optional[int] = Field(
        default=None, ge=1, le=32, description="Number of threads"
    )


class SimilarityStatusResponse(BaseModel):
    """Status of the similarity service."""

    available: bool
    message: str


class HotspotsResponse(BaseModel):
    """Response for hotspots endpoint."""

    hotspots: List[dict[str, Any]]
    count: int


class DefaultPatternsResponse(BaseModel):
    """Response with default exclude patterns."""

    patterns: List[str]


@router.get("/default-exclude-patterns", response_model=DefaultPatternsResponse)
async def get_default_exclude_patterns() -> DefaultPatternsResponse:
    """Get the default exclude patterns used for similarity analysis."""
    return DefaultPatternsResponse(patterns=list(DEFAULT_EXCLUDE_PATTERNS))


@router.get("/status", response_model=SimilarityStatusResponse)
async def get_similarity_status() -> SimilarityStatusResponse:
    """Check if the C++ similarity motor is available."""
    available = is_available()
    message = (
        "C++ similarity motor is available"
        if available
        else "C++ similarity motor not found. Build with: cd cpp && cmake -B build && cmake --build build"
    )
    return SimilarityStatusResponse(available=available, message=message)


@router.get("/latest")
async def get_latest_report(
    state: AppState = Depends(get_app_state),
) -> Optional[dict[str, Any]]:
    """Get the latest similarity analysis report."""
    return state.similarity_report


@router.post("/analyze")
async def run_analysis(
    request: SimilarityAnalyzeRequest,
    state: AppState = Depends(get_app_state),
) -> dict[str, Any]:
    """
    Run similarity analysis on the project.

    This endpoint triggers a new similarity analysis using the C++ motor.
    Results are cached and returned.
    """
    global _latest_report

    if not state.settings.root_path:
        raise InvalidConfigError(field="root_path", reason="No root path configured")

    if not is_available():
        raise ServiceUnavailableError(
            "C++ similarity motor not available. Build with: cd cpp && cmake -B build && cmake --build build"
        )

    try:
        logger.info(
            f"Running similarity analysis on {state.settings.root_path} "
            f"with extensions={request.extensions}, type3={request.type3}"
        )

        # Trigger background run logic but wait for it here for the POST response
        # or we could reimplement just the blocking call here.
        # To reuse logic, we can call the function we added to state,
        # but state.run_similarity_bg is async wrapping a blocking call.

        # Explicit call to update state
        await state.run_similarity_bg(
            extensions=request.extensions, type3=request.type3
        )

        return state.similarity_report or {}

    except SimilarityServiceError as e:
        logger.error(f"Similarity analysis failed: {e}")
        raise SimilarityException(str(e)) from e


@router.get("/hotspots", response_model=HotspotsResponse)
async def get_hotspots(
    limit: int = Query(
        default=10, ge=1, le=100, description="Maximum hotspots to return"
    ),
    extensions: Optional[str] = Query(
        default=None, description="Comma-separated extensions (e.g., '.py,.js')"
    ),
    state: AppState = Depends(get_app_state),
) -> HotspotsResponse:
    """
    Get files with highest duplication scores.

    Returns the top N files sorted by duplication score.
    """
    # If we have a cached report in state, use it
    if state.similarity_report:
        hotspots = state.similarity_report.get("hotspots", [])
        sorted_hotspots = sorted(
            hotspots, key=lambda h: h.get("duplication_score", 0), reverse=True
        )
        return HotspotsResponse(hotspots=sorted_hotspots[:limit], count=len(hotspots))

    # Otherwise, run a fresh analysis
    if not state.settings.root_path:
        raise InvalidConfigError(field="root_path", reason="No root path configured")

    if not is_available():
        raise ServiceUnavailableError("C++ similarity motor not available")

    try:
        ext_list = extensions.split(",") if extensions else [".py"]
        # Trigger update in state
        await state.run_similarity_bg(extensions=ext_list)

        hotspots = (state.similarity_report or {}).get("hotspots", [])
        sorted_hotspots = sorted(
            hotspots, key=lambda h: h.get("duplication_score", 0), reverse=True
        )
        return HotspotsResponse(hotspots=sorted_hotspots[:limit], count=len(hotspots))

    except SimilarityServiceError as e:
        raise SimilarityException(str(e)) from e
