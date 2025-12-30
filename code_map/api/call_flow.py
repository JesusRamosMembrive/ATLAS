# SPDX-License-Identifier: MIT
"""
API endpoints for call flow graph visualization.

Provides React Flow compatible graph data showing function call chains
from a selected entry point (e.g., button handlers, event callbacks).
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Union

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse

from ..graph_analysis.call_flow.languages.python import PythonCallFlowExtractor
from ..graph_analysis.call_flow.languages.cpp import CppCallFlowExtractor
from ..graph_analysis.call_flow.languages.typescript import TsCallFlowExtractor
from ..graph_analysis.call_flow.models import (
    CallGraph,
    CallNode,
    CallEdge,
    ExtractionMode,
    ResolutionStatus,
)
from .schemas import (
    CallFlowBranchExpansionRequest,
    CallFlowBranchExpansionResponse,
    CallFlowEntryPointSchema,
    CallFlowEntryPointsResponse,
    CallFlowExtractionMode,
    CallFlowIgnoredCallSchema,
    CallFlowResolutionStatus,
    CallFlowResponse,
)

# Type alias for any extractor
ExtractorType = Union[
    PythonCallFlowExtractor, CppCallFlowExtractor, TsCallFlowExtractor
]

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/call-flow", tags=["call-flow"])

# Singleton extractor instances
_python_extractor: Optional[PythonCallFlowExtractor] = None
_cpp_extractor: Optional[CppCallFlowExtractor] = None
_ts_extractor: Optional[TsCallFlowExtractor] = None

# Supported file extensions by language
PYTHON_EXTENSIONS = {".py"}
CPP_EXTENSIONS = {".cpp", ".c", ".hpp", ".h", ".cc", ".cxx", ".hxx"}
TS_EXTENSIONS = {".ts", ".tsx", ".mts", ".cts"}
JS_EXTENSIONS = {".js", ".jsx", ".mjs", ".cjs"}
TSJS_EXTENSIONS = TS_EXTENSIONS | JS_EXTENSIONS
SUPPORTED_EXTENSIONS = PYTHON_EXTENSIONS | CPP_EXTENSIONS | TSJS_EXTENSIONS


def _get_python_extractor() -> PythonCallFlowExtractor:
    """Get or create the Python extractor singleton."""
    global _python_extractor
    if _python_extractor is None:
        _python_extractor = PythonCallFlowExtractor()
    return _python_extractor


def _get_cpp_extractor() -> CppCallFlowExtractor:
    """Get or create the C++ extractor singleton."""
    global _cpp_extractor
    if _cpp_extractor is None:
        _cpp_extractor = CppCallFlowExtractor()
    return _cpp_extractor


def _get_ts_extractor() -> TsCallFlowExtractor:
    """Get or create the TypeScript/JavaScript extractor singleton."""
    global _ts_extractor
    if _ts_extractor is None:
        _ts_extractor = TsCallFlowExtractor()
    return _ts_extractor


def _get_extractor() -> PythonCallFlowExtractor:
    """Get or create the Python extractor singleton (for backward compatibility)."""
    return _get_python_extractor()


# Maximum file size for source code preview (512 KB)
MAX_SOURCE_BYTES = 512 * 1024

# Allowed file extensions for source code viewing
ALLOWED_SOURCE_EXTENSIONS = {
    ".py",
    ".js",
    ".ts",
    ".jsx",
    ".tsx",
    ".java",
    ".c",
    ".cpp",
    ".h",
    ".hpp",
    ".go",
    ".rs",
}


def _add_external_nodes_to_graph(graph: CallGraph) -> None:
    """
    Add external/builtin calls as leaf nodes in the graph.

    Converts IgnoredCall entries into CallNode + CallEdge objects,
    allowing visualization of external dependencies without source code.

    Args:
        graph: The CallGraph to modify in-place
    """
    # Track external nodes we've already added to avoid duplicates
    external_nodes: dict[str, str] = {}  # expression -> node_id

    for ignored in graph.ignored_calls:
        # Skip if no caller info (shouldn't happen with updated extractors)
        if not ignored.caller_id:
            continue

        # Determine edge source: if this call is inside a branch, connect from the decision node
        # Otherwise connect from the caller
        if ignored.decision_id and ignored.decision_id in graph.decision_nodes:
            edge_source = ignored.decision_id
        elif ignored.caller_id in graph.nodes:
            edge_source = ignored.caller_id
        else:
            # Skip if neither caller nor decision node exists
            continue

        # Determine kind based on resolution status
        if ignored.status == ResolutionStatus.IGNORED_BUILTIN:
            kind = "builtin"
        else:
            kind = "external"

        # Create a unique ID for this external call
        # Include branch_id in key to allow same call in different branches
        branch_suffix = f":{ignored.branch_id}" if ignored.branch_id else ""
        expr_key = f"{ignored.module_hint or ''}:{ignored.expression}{branch_suffix}"

        if expr_key not in external_nodes:
            # Create new external node
            node_id = f"external:{ignored.module_hint or ''}:{ignored.expression}:{ignored.call_site_line}"

            # Get depth: from decision node or caller
            if ignored.decision_id and ignored.decision_id in graph.decision_nodes:
                decision_node = graph.decision_nodes[ignored.decision_id]
                depth = decision_node.depth + 1
            elif ignored.caller_id in graph.nodes:
                caller_node = graph.nodes[ignored.caller_id]
                depth = caller_node.depth + 1
            else:
                depth = 1

            # Extract simple name from expression (e.g., "print" from "print(...)")
            name = ignored.expression.split("(")[0].split(".")[-1]
            qualified_name = ignored.expression.split("(")[0]
            if ignored.module_hint:
                qualified_name = f"{ignored.module_hint}.{qualified_name}"

            external_node = CallNode(
                id=node_id,
                name=name,
                qualified_name=qualified_name,
                file_path=None,  # External - no file path
                line=0,
                column=0,
                kind=kind,
                is_entry_point=False,
                depth=depth,
                docstring=f"External call: {ignored.status.value}",
                symbol_id=None,
                resolution_status=ignored.status,
                reasons=None,
                complexity=None,
                loc=None,
                # Store branch context in the node for frontend rendering
                branch_id=ignored.branch_id,
                decision_id=ignored.decision_id,
            )
            graph.add_node(external_node)
            external_nodes[expr_key] = node_id
        else:
            node_id = external_nodes[expr_key]

        # Create edge from decision node (if in branch) or caller to external node
        edge = CallEdge(
            source_id=edge_source,
            target_id=node_id,
            call_site_line=ignored.call_site_line,
            call_type="external",
            arguments=None,
            expression=ignored.expression,
            resolution_status=ignored.status,
            branch_id=ignored.branch_id,
            decision_id=ignored.decision_id,
        )
        graph.add_edge(edge)


@router.get("/source/{file_path:path}", response_class=PlainTextResponse)
async def get_source_code(
    file_path: str,
    start_line: int = Query(
        default=1, ge=1, description="Start line number (1-indexed)"
    ),
    end_line: Optional[int] = Query(
        default=None, ge=1, description="End line number (optional)"
    ),
) -> str:
    """
    Get source code from a file for call flow node details.

    This endpoint allows reading source files that may be outside the
    configured AEGIS root, since Call Flow can analyze external projects.

    Security:
    - Only allows reading files with code extensions (.py, .js, etc.)
    - File size limited to 512 KB
    - Read-only operation

    Args:
        file_path: Absolute path to the source file
        start_line: Start line number (1-indexed, default: 1)
        end_line: End line number (optional, reads to end if not specified)

    Returns:
        Plain text source code content
    """
    path = Path(file_path)

    if not path.is_absolute():
        path = Path("/") / path

    # Security: Only allow code file extensions
    if path.suffix.lower() not in ALLOWED_SOURCE_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type not allowed for source viewing: {path.suffix}. "
            f"Allowed: {', '.join(sorted(ALLOWED_SOURCE_EXTENSIONS))}",
        )

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

    # Security: Check file size
    try:
        file_size = path.stat().st_size
        if file_size > MAX_SOURCE_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"File too large: {file_size} bytes (max: {MAX_SOURCE_BYTES} bytes)",
            )
    except OSError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to read file stats: {exc}",
        )

    # Read file content
    try:
        with path.open("r", encoding="utf-8") as f:
            lines = f.readlines()
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=400,
            detail="File is not valid UTF-8 text",
        )
    except OSError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to read file: {exc}",
        )

    # Extract requested line range
    total_lines = len(lines)
    start_idx = start_line - 1  # Convert to 0-indexed

    if start_idx >= total_lines:
        raise HTTPException(
            status_code=400,
            detail=f"Start line {start_line} exceeds file length ({total_lines} lines)",
        )

    if end_line is not None:
        end_idx = min(end_line, total_lines)
        selected_lines = lines[start_idx:end_idx]
    else:
        selected_lines = lines[start_idx:]

    return "".join(selected_lines)


@router.get(
    "/entry-points/{file_path:path}", response_model=CallFlowEntryPointsResponse
)
async def list_entry_points(
    file_path: str,
) -> CallFlowEntryPointsResponse:
    """
    List available entry points (functions/methods) in a file.

    These can be used as starting points for call flow analysis.
    Supports Python (.py), C++ (.cpp, .c, .hpp, .h), and TypeScript/JavaScript files.

    Args:
        file_path: Path to source file (Python, C++, TypeScript, or JavaScript)

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

    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {path.suffix}. "
            f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}",
        )

    # Select appropriate extractor based on file type
    extractor: ExtractorType
    if suffix in PYTHON_EXTENSIONS:
        extractor = _get_python_extractor()
        lang_name = "Python"
    elif suffix in CPP_EXTENSIONS:
        extractor = _get_cpp_extractor()
        lang_name = "C++"
    else:
        extractor = _get_ts_extractor()
        lang_name = "TypeScript/JavaScript"

    if not extractor.is_available():
        raise HTTPException(
            status_code=503,
            detail=f"tree-sitter for {lang_name} not available. "
            "Install tree_sitter and tree_sitter_languages packages.",
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
                node_count=ep.get("node_count"),
            )
            for ep in entry_points
        ],
    )


@router.get("/{file_path:path}", response_model=CallFlowResponse)
async def get_call_flow(
    file_path: str,
    function: str = Query(..., description="Function or method name to analyze"),
    max_depth: int = Query(default=5, ge=1, le=20, description="Maximum call depth"),
    class_name: Optional[str] = Query(
        default=None, description="Class name if analyzing a method"
    ),
    include_external: bool = Query(
        default=False,
        description="Include external calls (builtins, stdlib, third-party) as leaf nodes",
    ),
    extraction_mode: str = Query(
        default="full",
        description="Extraction mode: 'full' (all paths) or 'lazy' (stop at decision points)",
    ),
) -> CallFlowResponse:
    """
    Extract call flow graph from a function or method.

    Returns a React Flow compatible graph showing all function calls
    reachable from the entry point up to max_depth levels.

    Supports Python (.py), C++ (.cpp, .c, .hpp, .h), and TypeScript/JavaScript files.

    Args:
        file_path: Path to source file (Python, C++, TypeScript, or JavaScript)
        function: Name of function/method to analyze
        max_depth: Maximum depth to follow calls (default: 5)
        class_name: Class name if analyzing a method (optional)
        include_external: If True, include external calls (builtins, stdlib, third-party)
                         as leaf nodes in the graph. These won't be expanded further
                         but will show all dependencies visually.
        extraction_mode: 'full' extracts all paths (default), 'lazy' stops at decision
                        points and allows interactive branch expansion.

    Returns:
        React Flow compatible graph with nodes, edges, decision_nodes, and metadata
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

    suffix = path.suffix.lower()

    if suffix not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {path.suffix}. "
            f"Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}",
        )

    # Select appropriate extractor
    extractor: ExtractorType
    if suffix in PYTHON_EXTENSIONS:
        extractor = _get_python_extractor()
        lang_name = "Python"
    elif suffix in CPP_EXTENSIONS:
        extractor = _get_cpp_extractor()
        lang_name = "C++"
    else:
        extractor = _get_ts_extractor()
        lang_name = "TypeScript/JavaScript"

    if not extractor.is_available():
        raise HTTPException(
            status_code=503,
            detail=f"tree-sitter for {lang_name} not available. "
            "Install tree_sitter and tree_sitter_languages packages.",
        )

    # Build the function identifier
    if class_name:
        func_to_find = function
        logger.info("Extracting call flow for %s::%s in %s", class_name, function, path)
    else:
        func_to_find = function
        logger.info("Extracting call flow for %s in %s", function, path)

    # Convert extraction_mode string to enum
    try:
        mode = ExtractionMode(extraction_mode.lower())
    except ValueError:
        mode = ExtractionMode.FULL

    # Extract call graph - Python and C++ support lazy mode
    if suffix in PYTHON_EXTENSIONS or suffix in CPP_EXTENSIONS:
        graph = extractor.extract(
            file_path=path,
            function_name=func_to_find,
            max_depth=max_depth,
            project_root=path.parent,
            extraction_mode=mode,
        )
    else:
        # TypeScript extractor doesn't support lazy mode yet
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

    # If include_external is True, add external calls as leaf nodes
    if include_external:
        _add_external_nodes_to_graph(graph)

    # Convert to React Flow format
    react_flow_data = graph.to_react_flow()

    # Convert ignored calls to schema format
    ignored_calls_schema = [
        CallFlowIgnoredCallSchema(
            expression=ic.expression,
            status=CallFlowResolutionStatus(ic.status.value),
            call_site_line=ic.call_site_line,
            module_hint=ic.module_hint,
            caller_id=ic.caller_id,
        )
        for ic in graph.ignored_calls[:50]  # Limit to first 50
    ]

    return CallFlowResponse(
        nodes=react_flow_data["nodes"],
        edges=react_flow_data["edges"],
        decision_nodes=react_flow_data.get("decision_nodes", []),
        return_nodes=react_flow_data.get("return_nodes", []),
        statement_nodes=react_flow_data.get("statement_nodes", []),
        external_call_nodes=react_flow_data.get("external_call_nodes", []),
        unexpanded_branches=graph.unexpanded_branches,
        extraction_mode=graph.extraction_mode,
        metadata={
            "entry_point": graph.entry_point,
            "source_file": str(graph.source_file),
            "function_name": function,
            "max_depth": graph.max_depth,
            "max_depth_reached": graph.max_depth_reached,
            "node_count": graph.node_count(),
            "edge_count": graph.edge_count(),
            "decision_node_count": len(graph.decision_nodes),
            "return_node_count": graph.return_node_count(),
        },
        ignored_calls=ignored_calls_schema,
        unresolved_calls=graph.unresolved_calls[:20],  # Limit to first 20
        diagnostics=graph.diagnostics,
    )


@router.post("/{file_path:path}/expand-branch", response_model=CallFlowBranchExpansionResponse)
async def expand_branch(
    file_path: str,
    branch_id: str = Query(..., description="Branch ID to expand"),
    function: str = Query(..., description="Entry point function name"),
    max_depth: int = Query(default=5, ge=1, le=20, description="Maximum call depth"),
    include_external: bool = Query(
        default=True,
        description="Include external calls (builtins, stdlib, third-party) as leaf nodes",
    ),
) -> CallFlowBranchExpansionResponse:
    """
    Expand a specific branch in lazy extraction mode.

    This endpoint is used incrementally after an initial lazy extraction.
    It extracts the call flow for a specific branch that was left unexpanded.

    Currently only supported for Python files.

    Args:
        file_path: Path to source file
        branch_id: ID of the branch to expand (from unexpanded_branches)
        function: Entry point function name (same as initial extraction)
        max_depth: Maximum depth to follow calls

    Returns:
        New nodes, edges, and decision nodes discovered in the expanded branch
    """
    path = Path(file_path)

    if not path.is_absolute():
        path = Path("/") / path

    if not path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"File not found: {path}",
        )

    suffix = path.suffix.lower()

    # Select appropriate extractor based on file type
    # Both Python and C++ support lazy mode / branch expansion
    extractor: ExtractorType
    if suffix in PYTHON_EXTENSIONS:
        extractor = _get_python_extractor()
        lang_name = "Python"
    elif suffix in CPP_EXTENSIONS:
        extractor = _get_cpp_extractor()
        lang_name = "C++"
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Branch expansion only supported for Python and C++ files. Got: {path.suffix}",
        )

    if not extractor.is_available():
        raise HTTPException(
            status_code=503,
            detail=f"tree-sitter for {lang_name} not available. "
            "Install tree_sitter and tree_sitter_languages packages.",
        )

    # Re-extract with the branch expanded
    # We pass expand_branches containing the branch to expand
    graph = extractor.extract(
        file_path=path,
        function_name=function,
        max_depth=max_depth,
        project_root=path.parent,
        extraction_mode=ExtractionMode.LAZY,
        expand_branches=[branch_id],
    )

    if graph is None:
        raise HTTPException(
            status_code=422,
            detail=f"Failed to expand branch {branch_id} in {path}::{function}.",
        )

    # If include_external is True, add external calls as leaf nodes
    if include_external:
        _add_external_nodes_to_graph(graph)

    # Convert to React Flow format
    react_flow_data = graph.to_react_flow()

    return CallFlowBranchExpansionResponse(
        new_nodes=react_flow_data["nodes"],
        new_edges=react_flow_data["edges"],
        new_decision_nodes=react_flow_data.get("decision_nodes", []),
        new_return_nodes=react_flow_data.get("return_nodes", []),
        new_statement_nodes=react_flow_data.get("statement_nodes", []),
        new_external_call_nodes=react_flow_data.get("external_call_nodes", []),
        new_unexpanded_branches=graph.unexpanded_branches,
        expanded_branch_id=branch_id,
    )
