# SPDX-License-Identifier: MIT
"""
Endpoints relacionados con visualizaciones de grafos.
"""

from __future__ import annotations

from typing import List, Optional, Set

from fastapi import APIRouter, Depends, Query, Response

from ..exceptions import InternalError
from ..class_graph import build_class_graph
from ..uml import GraphvizStyleOptions, build_uml_model, render_uml_svg, convert_to_uml_project
from ..state import AppState
from .deps import get_app_state
from .schemas import ClassGraphResponse, UMLDiagramResponse, UmlProjectDefResponse

router = APIRouter(prefix="/graph", tags=["graph"])


@router.get("/classes", response_model=ClassGraphResponse)
async def get_class_graph(
    include_external: bool = Query(
        False,
        description="Incluir relaciones externas (clases fuera del workspace).",
    ),
    edge_types: Optional[List[str]] = Query(
        None,
        description="Filtra un conjunto concreto de relaciones (inherits, instantiates).",
    ),
    module_prefix: Optional[List[str]] = Query(
        None,
        description="Limita el grafo a módulos que comiencen por alguno de estos prefijos.",
    ),
    state: AppState = Depends(get_app_state),
) -> ClassGraphResponse:
    """
    Genera el grafo de clases detectado en el workspace actual.
    """
    valid_types: Set[str] = {"inherits", "instantiates"}
    requested: Optional[Set[str]] = None
    if edge_types:
        requested = {edge for edge in edge_types if edge in valid_types}
        if not requested:
            requested = valid_types
    graph = build_class_graph(
        state.settings.root_path,
        include_external=include_external,
        edge_types=requested,
        module_prefixes={prefix for prefix in module_prefix or [] if prefix},
    )
    return ClassGraphResponse.model_validate(graph)


def get_graphviz_options(
    layout_engine: str = Query(
        "dot",
        description="Graphviz engine to use (dot, neato, fdp, sfdp, circo, twopi).",
    ),
    rankdir: str = Query("LR", description="Graph orientation (LR, RL, TB, BT)."),
    splines: str = Query(
        "true",
        description="Spline mode (true, false, line, polyline, spline, curved, ortho).",
    ),
    nodesep: float = Query(
        0.6, ge=0.1, le=5.0, description="Minimum space between nodes."
    ),
    ranksep: float = Query(1.1, ge=0.4, le=8.0, description="Minimum rank separation."),
    pad: float = Query(0.3, ge=0.0, le=5.0, description="Graph padding."),
    margin: float = Query(0.0, ge=0.0, le=5.0, description="Graph margin."),
    bgcolor: str = Query("#0b1120", description="Background color."),
    graph_fontname: str = Query("Inter", description="Graph font family."),
    graph_fontsize: int = Query(11, ge=6, le=32, description="Graph font size."),
    node_shape: str = Query(
        "box", description="Node shape (box, rect, ellipse, record, etc)."
    ),
    node_style: str = Query(
        "rounded,filled", description="Comma separated node styles."
    ),
    node_fillcolor: str = Query("#111827", description="Node fill color."),
    node_color: str = Query("#1f2937", description="Node border color."),
    node_fontcolor: str = Query("#e2e8f0", description="Node text color."),
    node_fontname: str = Query("Inter", description="Node font family."),
    node_fontsize: int = Query(11, ge=6, le=32, description="Node font size."),
    node_width: float = Query(1.6, ge=0.2, le=6.0, description="Minimum node width."),
    node_height: float = Query(0.6, ge=0.2, le=6.0, description="Minimum node height."),
    node_margin_x: float = Query(
        0.12, ge=0.02, le=1.0, description="Horizontal label margin."
    ),
    node_margin_y: float = Query(
        0.06, ge=0.02, le=1.0, description="Vertical label margin."
    ),
    edge_color: str = Query("#475569", description="Default edge color."),
    edge_fontname: str = Query("Inter", description="Edge font family."),
    edge_fontsize: int = Query(9, ge=6, le=24, description="Edge font size."),
    edge_penwidth: float = Query(1.0, ge=0.5, le=4.0, description="Edge stroke width."),
    inheritance_style: str = Query(
        "solid", description="Line style for inheritance edges."
    ),
    inheritance_color: str = Query(
        "#60a5fa", description="Color for inheritance edges."
    ),
    association_color: str = Query(
        "#f97316", description="Color for association edges."
    ),
    instantiation_color: str = Query(
        "#10b981", description="Color for instantiation edges."
    ),
    reference_color: str = Query("#a855f7", description="Color for reference edges."),
    inheritance_arrowhead: str = Query(
        "empty", description="Arrowhead style for inheritance."
    ),
    association_arrowhead: str = Query(
        "normal", description="Arrowhead style for association."
    ),
    instantiation_arrowhead: str = Query(
        "diamond", description="Arrowhead for instantiation."
    ),
    reference_arrowhead: str = Query(
        "vee", description="Arrowhead for reference edges."
    ),
    association_style: str = Query(
        "dashed", description="Line style for association edges."
    ),
    instantiation_style: str = Query(
        "dashed", description="Line style for instantiation edges."
    ),
    reference_style: str = Query(
        "dotted", description="Line style for reference edges."
    ),
) -> GraphvizStyleOptions:
    return GraphvizStyleOptions(
        layout_engine=layout_engine,
        rankdir=rankdir,
        splines=splines,
        nodesep=nodesep,
        ranksep=ranksep,
        pad=pad,
        margin=margin,
        bgcolor=bgcolor,
        graph_fontname=graph_fontname,
        graph_fontsize=graph_fontsize,
        node_shape=node_shape,
        node_style=node_style,
        node_fillcolor=node_fillcolor,
        node_color=node_color,
        node_fontcolor=node_fontcolor,
        node_fontname=node_fontname,
        node_fontsize=node_fontsize,
        node_width=node_width,
        node_height=node_height,
        node_margin_x=node_margin_x,
        node_margin_y=node_margin_y,
        edge_color=edge_color,
        edge_fontname=edge_fontname,
        edge_fontsize=edge_fontsize,
        edge_penwidth=edge_penwidth,
        inheritance_style=inheritance_style,
        inheritance_color=inheritance_color,
        association_color=association_color,
        instantiation_color=instantiation_color,
        reference_color=reference_color,
        inheritance_arrowhead=inheritance_arrowhead,
        association_arrowhead=association_arrowhead,
        instantiation_arrowhead=instantiation_arrowhead,
        reference_arrowhead=reference_arrowhead,
        association_style=association_style,
        instantiation_style=instantiation_style,
        reference_style=reference_style,
    )


@router.get("/uml", response_model=UMLDiagramResponse)
async def get_uml_diagram(
    include_external: bool = Query(
        False,
        description="Incluir relaciones con clases externas.",
    ),
    module_prefix: Optional[List[str]] = Query(
        None,
        description="Prefijos de módulo a incluir en el diagrama.",
    ),
    edge_types: Optional[List[str]] = Query(
        None,
        description="Tipos de relaciones a mostrar: inheritance, association, instantiation, reference. Default: inheritance, association.",
    ),
    state: AppState = Depends(get_app_state),
    _graphviz: GraphvizStyleOptions = Depends(get_graphviz_options),
) -> UMLDiagramResponse:
    prefixes = {prefix for prefix in module_prefix or [] if prefix}

    # Parse edge types - default to inheritance + association for backwards compatibility
    valid_types = {"inheritance", "association", "instantiation", "reference"}
    if edge_types:
        requested_types = {edge for edge in edge_types if edge in valid_types}
        if not requested_types:
            requested_types = {"inheritance", "association"}
    else:
        requested_types = {"inheritance", "association"}

    uml = build_uml_model(
        state.settings.root_path,
        module_prefixes=prefixes,
        include_external=include_external,
    )
    return UMLDiagramResponse.model_validate(uml)


@router.get("/uml/svg", response_class=Response)
async def get_uml_svg(
    include_external: bool = Query(
        False,
        description="Incluir relaciones con clases externas.",
    ),
    module_prefix: Optional[List[str]] = Query(
        None,
        description="Prefijos de módulo a incluir en el diagrama.",
    ),
    edge_types: Optional[List[str]] = Query(
        None,
        description="Tipos de relaciones a mostrar: inheritance, association, instantiation, reference. Default: inheritance, association.",
    ),
    state: AppState = Depends(get_app_state),
    graphviz: GraphvizStyleOptions = Depends(get_graphviz_options),
) -> Response:
    prefixes = {prefix for prefix in module_prefix or [] if prefix}

    # Parse edge types - default to inheritance + association for backwards compatibility
    valid_types = {"inheritance", "association", "instantiation", "reference"}
    if edge_types:
        requested_types = {edge for edge in edge_types if edge in valid_types}
        if not requested_types:
            requested_types = {"inheritance", "association"}
    else:
        requested_types = {"inheritance", "association"}

    model = build_uml_model(
        state.settings.root_path,
        module_prefixes=prefixes,
        include_external=include_external,
    )
    try:
        svg = render_uml_svg(model, requested_types, graphviz)
    except RuntimeError as exc:  # pragma: no cover
        raise InternalError(str(exc)) from exc
    return Response(content=svg, media_type="image/svg+xml")


@router.get("/uml/project", response_model=UmlProjectDefResponse)
async def get_uml_project(
    include_external: bool = Query(
        False,
        description="Include external classes (outside workspace).",
    ),
    module_prefix: Optional[List[str]] = Query(
        None,
        description="Filter to modules starting with these prefixes.",
    ),
    project_name: Optional[str] = Query(
        None,
        description="Custom project name (defaults to directory name).",
    ),
    target_language: str = Query(
        "python",
        description="Target language for type mapping (python, typescript, cpp).",
    ),
    language: Optional[List[str]] = Query(
        None,
        description="Languages to analyze: python, typescript, cpp. Analyzes all if not specified.",
    ),
    custom_path: Optional[str] = Query(
        None,
        description="Custom path to scan (overrides root_path from settings).",
    ),
    state: AppState = Depends(get_app_state),
) -> UmlProjectDefResponse:
    """
    Convert analyzed code to UmlProjectDef format for the UML Editor.

    This endpoint analyzes Python, TypeScript/TSX, and C++ files in the workspace
    and returns a complete UML project definition that can be imported directly
    into the AEGIS UML Editor using the mergeProject() action.

    The response includes:
    - Classes with attributes, methods, visibility, and inheritance
    - Interfaces (from TypeScript)
    - Structs (from C++)
    - Relationships (inheritance, implementation, association)
    - Automatic grid-based layout positioning

    Example usage:
    ```
    GET /api/graph/uml/project?module_prefix=code_map&target_language=python
    GET /api/graph/uml/project?language=python&language=typescript
    GET /api/graph/uml/project?custom_path=/path/to/folder
    ```
    """
    from pathlib import Path

    prefixes = {prefix for prefix in module_prefix or [] if prefix} or None
    languages = {lang.lower() for lang in language or []} or None

    # Use custom_path if provided, otherwise use settings root_path
    scan_path = Path(custom_path) if custom_path else state.settings.root_path

    project_def = convert_to_uml_project(
        scan_path,
        module_prefixes=prefixes,
        include_external=include_external,
        project_name=project_name,
        target_language=target_language,
        languages=languages,
    )

    return UmlProjectDefResponse.model_validate(project_def)
