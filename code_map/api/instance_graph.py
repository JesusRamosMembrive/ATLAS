# SPDX-License-Identifier: MIT
"""
API endpoints for instance graph visualization.

Provides React Flow compatible graph data from C++ composition roots.
Uses InstanceGraphService for caching and persistence.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException

from ..state import AppState
from .deps import get_app_state
from .schemas import InstanceGraphResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/instance-graph", tags=["instance-graph"])


@router.get("/{project_path:path}", response_model=InstanceGraphResponse)
async def get_instance_graph(
    project_path: str,
    state: AppState = Depends(get_app_state),
) -> InstanceGraphResponse:
    """
    Extract instance graph from a C++ project's main.cpp.

    Uses cached graph if available and source hasn't changed.

    Args:
        project_path: Path to directory containing main.cpp

    Returns:
        React Flow compatible graph with nodes, edges, and metadata
    """
    project_dir = Path(project_path)

    if not project_dir.is_absolute():
        project_dir = Path("/") / project_dir

    if not project_dir.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Project directory not found: {project_dir}",
        )

    if not project_dir.is_dir():
        raise HTTPException(
            status_code=400,
            detail=f"Path is not a directory: {project_dir}",
        )

    # Look for main.cpp in the project directory
    main_cpp = project_dir / "main.cpp"
    if not main_cpp.exists():
        # Try src/main.cpp as fallback
        main_cpp = project_dir / "src" / "main.cpp"
        if not main_cpp.exists():
            raise HTTPException(
                status_code=404,
                detail=f"main.cpp not found in {project_dir} or {project_dir}/src/",
            )

    # Check if tree-sitter is available via the service
    if not state.instance_graph.extractor.is_available():
        raise HTTPException(
            status_code=503,
            detail="tree-sitter is not available. Install tree_sitter and tree_sitter_languages packages.",
        )

    # Get graph from service (uses cache if valid)
    logger.info("[DEBUG] API: Calling get_graph for %s", main_cpp)
    graph = await state.instance_graph.get_graph(main_cpp, "main")
    logger.info("[DEBUG] API: get_graph returned graph=%s", graph is not None)
    if graph is None:
        raise HTTPException(
            status_code=422,
            detail=f"Failed to extract composition root from {main_cpp}. Check that main() function exists.",
        )

    # Log node type_locations for debugging
    for node in graph.iter_nodes():
        logger.info("[DEBUG] API GET: Node '%s' type_location=%s", node.name, node.type_location)

    # Convert to React Flow format
    react_flow_data = graph.to_react_flow()

    return InstanceGraphResponse(
        nodes=react_flow_data["nodes"],
        edges=react_flow_data["edges"],
        metadata={
            "source_file": str(main_cpp),
            "function_name": graph.function_name or "main",
            "node_count": len(graph.nodes),
            "edge_count": len(graph.edges),
        },
    )


@router.post("/{project_path:path}/refresh", response_model=InstanceGraphResponse)
async def refresh_instance_graph(
    project_path: str,
    state: AppState = Depends(get_app_state),
) -> InstanceGraphResponse:
    """
    Force re-analysis of the instance graph.

    This endpoint re-parses the source file, bypassing the cache.

    Args:
        project_path: Path to directory containing main.cpp

    Returns:
        React Flow compatible graph with nodes, edges, and metadata
    """
    project_dir = Path(project_path)

    if not project_dir.is_absolute():
        project_dir = Path("/") / project_dir

    if not project_dir.exists():
        raise HTTPException(
            status_code=404,
            detail=f"Project directory not found: {project_dir}",
        )

    if not project_dir.is_dir():
        raise HTTPException(
            status_code=400,
            detail=f"Path is not a directory: {project_dir}",
        )

    # Look for main.cpp in the project directory
    main_cpp = project_dir / "main.cpp"
    if not main_cpp.exists():
        main_cpp = project_dir / "src" / "main.cpp"
        if not main_cpp.exists():
            raise HTTPException(
                status_code=404,
                detail=f"main.cpp not found in {project_dir} or {project_dir}/src/",
            )

    # Check if tree-sitter is available
    if not state.instance_graph.extractor.is_available():
        raise HTTPException(
            status_code=503,
            detail="tree-sitter is not available. Install tree_sitter and tree_sitter_languages packages.",
        )

    # Force refresh by bypassing cache
    graph = await state.instance_graph.get_graph(main_cpp, "main", force_refresh=True)
    if graph is None:
        raise HTTPException(
            status_code=422,
            detail=f"Failed to extract composition root from {main_cpp}. Check that main() function exists.",
        )

    # Convert to React Flow format
    react_flow_data = graph.to_react_flow()

    return InstanceGraphResponse(
        nodes=react_flow_data["nodes"],
        edges=react_flow_data["edges"],
        metadata={
            "source_file": str(main_cpp),
            "function_name": graph.function_name or "main",
            "node_count": len(graph.nodes),
            "edge_count": len(graph.edges),
        },
    )


@router.get("/", response_model=List[Dict[str, Any]])
async def list_instance_graphs(
    state: AppState = Depends(get_app_state),
) -> List[Dict[str, Any]]:
    """
    List all cached instance graphs.

    Returns:
        List of graph summaries with id, source_file, stats, and cache timestamp
    """
    return state.instance_graph.list_graphs()
