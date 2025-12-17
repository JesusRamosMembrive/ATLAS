# SPDX-License-Identifier: MIT
"""
API endpoints for call flow graph visualization.

Provides React Flow compatible graph data showing function call chains
from a selected entry point (e.g., button handlers, event callbacks).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from ..v2.call_flow.extractor import PythonCallFlowExtractor
from .schemas import (
    CallFlowEntryPointSchema,
    CallFlowEntryPointsResponse,
    CallFlowIgnoredCallSchema,
    CallFlowResolutionStatus,
    CallFlowResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/call-flow", tags=["call-flow"])

# Singleton extractor instance
_extractor: Optional[PythonCallFlowExtractor] = None


def _get_extractor() -> PythonCallFlowExtractor:
    """Get or create the extractor singleton."""
    global _extractor
    if _extractor is None:
        _extractor = PythonCallFlowExtractor()
    return _extractor


@router.get("/entry-points/{file_path:path}", response_model=CallFlowEntryPointsResponse)
async def list_entry_points(
    file_path: str,
) -> CallFlowEntryPointsResponse:
    """
    List available entry points (functions/methods) in a file.

    These can be used as starting points for call flow analysis.

    Args:
        file_path: Path to Python file

    Returns:
        List of entry points with name, qualified_name, line, and kind
    """
    path = Path(file_path)

    if not path.is_absolute():
        path = Path("/") / path

    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"File not found: {path}",
        )

    if not path.is_file():
        raise HTTPException(
            status_code=400,
            detail=f"Path is not a file: {path}",
        )

    if path.suffix != ".py":
        raise HTTPException(
            status_code=400,
            detail=f"Only Python files are supported. Got: {path.suffix}",
        )

    extractor = _get_extractor()

    if not extractor.is_available():
        raise HTTPException(
            status_code=503,
            detail="tree-sitter not available. Install tree_sitter and tree_sitter_languages packages.",
        )

    entry_points = extractor.list_entry_points(path)

    return CallFlowEntryPointsResponse(
        file_path=str(path),
        entry_points=[
            CallFlowEntryPointSchema(
                name=ep["name"],
                qualified_name=ep["qualified_name"],
                line=ep["line"],
                kind=ep["kind"],
                class_name=ep.get("class_name"),
            )
            for ep in entry_points
        ],
    )


@router.get("/{file_path:path}", response_model=CallFlowResponse)
async def get_call_flow(
    file_path: str,
    function: str = Query(..., description="Function or method name to analyze"),
    max_depth: int = Query(default=5, ge=1, le=20, description="Maximum call depth"),
    class_name: Optional[str] = Query(default=None, description="Class name if analyzing a method"),
) -> CallFlowResponse:
    """
    Extract call flow graph from a function or method.

    Returns a React Flow compatible graph showing all function calls
    reachable from the entry point up to max_depth levels.

    Args:
        file_path: Path to Python file
        function: Name of function/method to analyze
        max_depth: Maximum depth to follow calls (default: 5)
        class_name: Class name if analyzing a method (optional)

    Returns:
        React Flow compatible graph with nodes, edges, and metadata
    """
    path = Path(file_path)

    if not path.is_absolute():
        path = Path("/") / path

    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"File not found: {path}",
        )

    if not path.is_file():
        raise HTTPException(
            status_code=400,
            detail=f"Path is not a file: {path}",
        )

    if path.suffix != ".py":
        raise HTTPException(
            status_code=400,
            detail=f"Only Python files are supported. Got: {path.suffix}",
        )

    extractor = _get_extractor()

    if not extractor.is_available():
        raise HTTPException(
            status_code=503,
            detail="tree-sitter not available. Install tree_sitter and tree_sitter_languages packages.",
        )

    # Build the function identifier
    if class_name:
        func_to_find = function
        logger.info("Extracting call flow for %s.%s in %s", class_name, function, path)
    else:
        func_to_find = function
        logger.info("Extracting call flow for %s in %s", function, path)

    # Extract call graph
    graph = extractor.extract(
        file_path=path,
        function_name=func_to_find,
        max_depth=max_depth,
        project_root=path.parent,
    )

    if graph is None:
        raise HTTPException(
            status_code=422,
            detail=f"Failed to extract call flow from {path}::{function}. "
            "Check that the function exists.",
        )

    # Convert to React Flow format
    react_flow_data = graph.to_react_flow()

    # Convert ignored calls to schema format
    ignored_calls_schema = [
        CallFlowIgnoredCallSchema(
            expression=ic.expression,
            status=CallFlowResolutionStatus(ic.status.value),
            call_site_line=ic.call_site_line,
            module_hint=ic.module_hint,
        )
        for ic in graph.ignored_calls[:50]  # Limit to first 50
    ]

    return CallFlowResponse(
        nodes=react_flow_data["nodes"],
        edges=react_flow_data["edges"],
        metadata={
            "entry_point": graph.entry_point,
            "source_file": str(graph.source_file),
            "function_name": function,
            "max_depth": graph.max_depth,
            "max_depth_reached": graph.max_depth_reached,
            "node_count": graph.node_count(),
            "edge_count": graph.edge_count(),
        },
        ignored_calls=ignored_calls_schema,
        unresolved_calls=graph.unresolved_calls[:20],  # Limit to first 20
        diagnostics=graph.diagnostics,
    )
