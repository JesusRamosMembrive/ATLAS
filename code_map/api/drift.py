# SPDX-License-Identifier: MIT
"""
API endpoints for drift detection.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..drift import DriftAnalyzer, DriftReport
from ..state import AppState
from .deps import get_app_state

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/drift", tags=["drift"])

# Cache analyzer per app state
_analyzer_cache: dict[int, DriftAnalyzer] = {}


# ─────────────────────────────────────────────────────────────
# Request/Response Models
# ─────────────────────────────────────────────────────────────


class DriftAnalyzeRequest(BaseModel):
    """Request to run drift analysis."""

    file_paths: Optional[list[str]] = Field(
        default=None,
        description="Optional list of file paths to analyze (relative to project root)",
    )
    include_semantic: bool = Field(
        default=False,
        description="Include semantic drift detection (heuristic, may have false positives)",
    )


class DriftItemResponse(BaseModel):
    """A single drift item."""

    id: str
    type: str
    category: str
    severity: str
    file_path: str
    line_number: Optional[int] = None
    symbol_name: Optional[str] = None
    title: str
    description: str
    suggestion: Optional[str] = None
    before_context: Optional[str] = None
    after_context: Optional[str] = None
    detected_at: str


class DriftReportResponse(BaseModel):
    """Complete drift analysis report."""

    items: list[DriftItemResponse]
    analyzed_at: str
    analyzed_files: list[str]
    duration_ms: float
    summary: dict


class DriftStatusResponse(BaseModel):
    """Current drift analyzer status."""

    project_root: str
    semantic_enabled: bool
    has_previous_wiring: bool
    has_current_wiring: bool
    detectors: dict


class WiringUpdateRequest(BaseModel):
    """Request to update wiring state."""

    instances: dict = Field(
        description="Map of instance_id to instance info (type, file, line)"
    )
    edges: list[dict] = Field(
        description="List of edges with 'from' and 'to' keys"
    )


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────


def _get_analyzer(state: AppState) -> DriftAnalyzer:
    """Get or create drift analyzer for current app state."""
    state_id = id(state)
    if state_id not in _analyzer_cache:
        _analyzer_cache[state_id] = DriftAnalyzer(state.settings.root_path)
    return _analyzer_cache[state_id]


def _report_to_response(report: DriftReport) -> DriftReportResponse:
    """Convert DriftReport to API response."""
    return DriftReportResponse(
        items=[
            DriftItemResponse(
                id=item.id,
                type=item.type.value,
                category=item.category.value,
                severity=item.severity.value,
                file_path=str(item.file_path),
                line_number=item.line_number,
                symbol_name=item.symbol_name,
                title=item.title,
                description=item.description,
                suggestion=item.suggestion,
                before_context=item.before_context,
                after_context=item.after_context,
                detected_at=item.detected_at.isoformat(),
            )
            for item in report.items
        ],
        analyzed_at=report.analyzed_at.isoformat(),
        analyzed_files=[str(f) for f in report.analyzed_files],
        duration_ms=report.duration_ms,
        summary=report.to_dict()["summary"],
    )


# ─────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────


@router.post("/analyze", response_model=DriftReportResponse)
async def analyze_drift(
    request: DriftAnalyzeRequest,
    state: AppState = Depends(get_app_state),
) -> DriftReportResponse:
    """
    Run full drift analysis.

    Analyzes the project for:
    - Structural drift (contract vs symbol signatures)
    - Wiring drift (graph vs code composition)
    - Semantic drift (contract claims vs implementation) - optional
    """
    analyzer = _get_analyzer(state)

    # Convert file paths
    file_paths = None
    if request.file_paths:
        file_paths = [
            state.settings.root_path / fp for fp in request.file_paths
        ]

    try:
        report = await analyzer.analyze(
            file_paths=file_paths,
            include_semantic=request.include_semantic,
        )
        return _report_to_response(report)
    except Exception as e:
        logger.error(f"Drift analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/structural", response_model=DriftReportResponse)
async def analyze_structural(
    file_paths: Optional[list[str]] = None,
    state: AppState = Depends(get_app_state),
) -> DriftReportResponse:
    """
    Run only structural drift detection.

    Checks for:
    - Contract references to deleted symbols
    - Symbol signature changes
    - Missing or stale evidence references
    """
    analyzer = _get_analyzer(state)

    paths = None
    if file_paths:
        paths = [state.settings.root_path / fp for fp in file_paths]

    try:
        report = await analyzer.analyze_structural(file_paths=paths)
        return _report_to_response(report)
    except Exception as e:
        logger.error(f"Structural drift analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/wiring", response_model=DriftReportResponse)
async def analyze_wiring(
    file_paths: Optional[list[str]] = None,
    state: AppState = Depends(get_app_state),
) -> DriftReportResponse:
    """
    Run only wiring drift detection.

    Checks for changes in composition roots:
    - Added/removed instances
    - Added/removed edges
    - Type changes

    Note: Requires wiring state to be updated via POST /drift/wiring/update
    """
    analyzer = _get_analyzer(state)

    paths = None
    if file_paths:
        paths = [state.settings.root_path / fp for fp in file_paths]

    try:
        report = await analyzer.analyze_wiring(file_paths=paths)
        return _report_to_response(report)
    except Exception as e:
        logger.error(f"Wiring drift analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/semantic", response_model=DriftReportResponse)
async def analyze_semantic(
    file_paths: Optional[list[str]] = None,
    state: AppState = Depends(get_app_state),
) -> DriftReportResponse:
    """
    Run only semantic drift detection (heuristic).

    Uses heuristics to detect obvious mismatches:
    - Thread safety claims vs mutex/lock usage
    - Precondition checks not present in code
    - Error handling claims vs actual throws

    Note: This is heuristic-based and may have false positives.
    """
    analyzer = _get_analyzer(state)

    paths = None
    if file_paths:
        paths = [state.settings.root_path / fp for fp in file_paths]

    try:
        report = await analyzer.analyze_semantic(file_paths=paths)
        return _report_to_response(report)
    except Exception as e:
        logger.error(f"Semantic drift analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status", response_model=DriftStatusResponse)
async def get_drift_status(
    state: AppState = Depends(get_app_state),
) -> DriftStatusResponse:
    """Get current drift analyzer status."""
    analyzer = _get_analyzer(state)
    status = analyzer.get_status()
    return DriftStatusResponse(**status)


@router.post("/wiring/update")
async def update_wiring_state(
    request: WiringUpdateRequest,
    state: AppState = Depends(get_app_state),
) -> dict:
    """
    Update wiring state for drift detection.

    Call this when composition root is re-analyzed to enable
    wiring drift detection between states.
    """
    analyzer = _get_analyzer(state)

    wiring = {
        "instances": request.instances,
        "edges": request.edges,
    }

    analyzer.update_wiring_state(wiring)

    return {
        "status": "ok",
        "message": "Wiring state updated",
        "has_previous": analyzer._previous_wiring is not None,
    }


@router.post("/wiring/clear")
async def clear_wiring_state(
    state: AppState = Depends(get_app_state),
) -> dict:
    """Clear wiring state cache."""
    analyzer = _get_analyzer(state)
    analyzer.clear_wiring_state()
    return {"status": "ok", "message": "Wiring state cleared"}


@router.post("/check-before-apply")
async def check_before_apply(
    affected_files: list[str],
    state: AppState = Depends(get_app_state),
) -> dict:
    """
    Check drift before applying changes.

    Returns whether changes can proceed based on drift detection.
    """
    from ..drift.analyzer import check_drift_before_apply

    file_paths = [state.settings.root_path / fp for fp in affected_files]

    try:
        can_proceed, report = await check_drift_before_apply(
            state.settings.root_path, file_paths
        )

        return {
            "can_proceed": can_proceed,
            "blocking_count": len(report.get_blocking_items()),
            "total_drift_items": report.total_count,
            "report": _report_to_response(report).model_dump(),
        }
    except Exception as e:
        logger.error(f"Check before apply failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
