# SPDX-License-Identifier: MIT
"""
API endpoints for sequence diagram generation.

Transforms call flow graphs into UML sequence diagrams for visualization.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ..graph_analysis.call_flow.languages.python import PythonCallFlowExtractor
from ..graph_analysis.call_flow.languages.cpp import CppCallFlowExtractor
from ..graph_analysis.call_flow.languages.typescript import TsCallFlowExtractor
from ..graph_analysis.call_flow.models import ExtractionMode
from ..graph_analysis.sequence import CallFlowToSequenceTransformer
from .call_flow import _add_external_nodes_to_graph

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sequence", tags=["sequence"])

# Reuse extractor singletons from call_flow
_python_extractor: Optional[PythonCallFlowExtractor] = None
_cpp_extractor: Optional[CppCallFlowExtractor] = None
_ts_extractor: Optional[TsCallFlowExtractor] = None

# Supported file extensions
PYTHON_EXTENSIONS = {".py"}
CPP_EXTENSIONS = {".cpp", ".c", ".hpp", ".h", ".cc", ".cxx", ".hxx"}
TS_EXTENSIONS = {".ts", ".tsx", ".mts", ".cts"}
JS_EXTENSIONS = {".js", ".jsx", ".mjs", ".cjs"}
TSJS_EXTENSIONS = TS_EXTENSIONS | JS_EXTENSIONS
SUPPORTED_EXTENSIONS = PYTHON_EXTENSIONS | CPP_EXTENSIONS | TSJS_EXTENSIONS


def _get_python_extractor() -> PythonCallFlowExtractor:
    global _python_extractor
    if _python_extractor is None:
        _python_extractor = PythonCallFlowExtractor()
    return _python_extractor


def _get_cpp_extractor() -> CppCallFlowExtractor:
    global _cpp_extractor
    if _cpp_extractor is None:
        _cpp_extractor = CppCallFlowExtractor()
    return _cpp_extractor


def _get_ts_extractor() -> TsCallFlowExtractor:
    global _ts_extractor
    if _ts_extractor is None:
        _ts_extractor = TsCallFlowExtractor()
    return _ts_extractor


# -----------------------------------------------------------------------------
# Response Schemas
# -----------------------------------------------------------------------------


class SequenceLifelineSchema(BaseModel):
    """A lifeline (participant) in the sequence diagram."""

    id: str
    name: str
    qualified_name: str = Field(alias="qualifiedName")
    participant_type: str = Field(alias="participantType")
    order: int
    file_path: Optional[str] = Field(None, alias="filePath")
    line: int
    is_entry_point: bool = Field(alias="isEntryPoint")

    model_config = {"populate_by_name": True}


class SequenceMessageSchema(BaseModel):
    """A message (arrow) between lifelines."""

    id: str
    from_lifeline: str = Field(alias="fromLifeline")
    to_lifeline: str = Field(alias="toLifeline")
    label: str
    message_type: str = Field(alias="messageType")
    sequence_number: int = Field(alias="sequenceNumber")
    arguments: Optional[List[str]] = None
    return_value: Optional[str] = Field(None, alias="returnValue")
    call_site_line: int = Field(alias="callSiteLine")
    fragment_id: Optional[str] = Field(None, alias="fragmentId")
    fragment_operand_index: Optional[int] = Field(None, alias="fragmentOperandIndex")

    model_config = {"populate_by_name": True}


class SequenceActivationBoxSchema(BaseModel):
    """An activation box on a lifeline."""

    id: str
    lifeline_id: str = Field(alias="lifelineId")
    start_sequence: int = Field(alias="startSequence")
    end_sequence: int = Field(alias="endSequence")
    nesting_level: int = Field(alias="nestingLevel")

    model_config = {"populate_by_name": True}


class SequenceFragmentOperandSchema(BaseModel):
    """An operand (branch) within a combined fragment."""

    guard: str
    message_ids: List[str] = Field(alias="messageIds")

    model_config = {"populate_by_name": True}


class SequenceCombinedFragmentSchema(BaseModel):
    """A combined fragment (alt, opt, loop) in the sequence diagram."""

    id: str
    fragment_type: str = Field(alias="fragmentType")
    condition_text: str = Field(alias="conditionText")
    operands: List[SequenceFragmentOperandSchema]
    start_sequence: int = Field(alias="startSequence")
    end_sequence: int = Field(alias="endSequence")
    covering_lifelines: List[str] = Field(alias="coveringLifelines")
    parent_fragment_id: Optional[str] = Field(None, alias="parentFragmentId")

    model_config = {"populate_by_name": True}


class SequenceMetadataSchema(BaseModel):
    """Metadata about the generated sequence diagram."""

    entry_point: str = Field(alias="entryPoint")
    source_file: Optional[str] = Field(None, alias="sourceFile")
    function_name: str = Field(alias="functionName")
    lifeline_count: int = Field(alias="lifelineCount")
    message_count: int = Field(alias="messageCount")
    fragment_count: int = Field(alias="fragmentCount")
    max_depth: int = Field(alias="maxDepth")

    model_config = {"populate_by_name": True}


class SequenceDiagramResponse(BaseModel):
    """Complete sequence diagram response for React Flow rendering."""

    lifelines: List[Dict[str, Any]]  # React Flow node format
    messages: List[Dict[str, Any]]  # React Flow edge format
    activation_boxes: List[Dict[str, Any]] = Field(alias="activationBoxes")
    fragments: List[Dict[str, Any]]
    metadata: SequenceMetadataSchema

    model_config = {"populate_by_name": True}


# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------


@router.get("/{file_path:path}", response_model=SequenceDiagramResponse)
async def get_sequence_diagram(
    file_path: str,
    function: str = Query(..., description="Function or method name to analyze"),
    max_depth: int = Query(default=5, ge=1, le=10, description="Maximum call depth"),
    class_name: Optional[str] = Query(
        default=None, description="Class name if analyzing a method"
    ),
) -> SequenceDiagramResponse:
    """
    Generate a sequence diagram from a function or method.

    Extracts the call flow from the entry point and transforms it into
    a UML sequence diagram format suitable for visualization.

    Args:
        file_path: Path to source file (Python, C++, TypeScript, JavaScript)
        function: Name of function/method to analyze
        max_depth: Maximum depth to follow calls (default: 5, max: 10)
        class_name: Class name if analyzing a method (optional)

    Returns:
        Sequence diagram data with lifelines, messages, activation boxes,
        and combined fragments in React Flow compatible format.
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

    logger.info("Generating sequence diagram for %s in %s", function, path)

    # Extract call graph using full mode (we want all paths for sequence diagram)
    call_graph = extractor.extract(
        file_path=path,
        function_name=function,
        max_depth=max_depth,
        project_root=path.parent,
        extraction_mode=ExtractionMode.FULL,
    )

    if call_graph is None:
        raise HTTPException(
            status_code=422,
            detail=f"Failed to extract call flow from {path}::{function}. "
            "Check that the function exists.",
        )

    # Include external calls (builtin, stdlib, third-party) as nodes in the graph
    # This converts ignored_calls into actual CallNode + CallEdge objects
    _add_external_nodes_to_graph(call_graph)

    # Transform to sequence diagram
    transformer = CallFlowToSequenceTransformer()
    sequence_diagram = transformer.transform(call_graph)

    # Convert to React Flow format
    react_flow_data = sequence_diagram.to_react_flow()

    return SequenceDiagramResponse(
        lifelines=react_flow_data["lifelines"],
        messages=react_flow_data["messages"],
        activation_boxes=react_flow_data["activationBoxes"],
        fragments=react_flow_data["fragments"],
        metadata=SequenceMetadataSchema(
            entry_point=sequence_diagram.entry_point,
            source_file=str(sequence_diagram.source_file) if sequence_diagram.source_file else None,
            function_name=function,
            lifeline_count=sequence_diagram.lifeline_count(),
            message_count=sequence_diagram.message_count(),
            fragment_count=len(sequence_diagram.fragments),
            max_depth=max_depth,
        ),
    )
