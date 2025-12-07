# SPDX-License-Identifier: MIT
"""
Renderizado de grafos UML usando Graphviz.
"""
from __future__ import annotations

import html
import shutil
import subprocess  # nosec B404
from dataclasses import dataclass
from typing import Dict, List, Optional, Set


@dataclass
class GraphvizStyleOptions:
    layout_engine: str = "dot"
    rankdir: str = "LR"
    splines: str = "true"
    nodesep: float = 0.6
    ranksep: float = 1.1
    pad: float = 0.3
    margin: float = 0.0
    bgcolor: str = "#0b1120"
    graph_fontname: str = "Inter"
    graph_fontsize: int = 11
    node_shape: str = "box"
    node_style: str = "rounded,filled"
    node_fillcolor: str = "#111827"
    node_color: str = "#1f2937"
    node_fontcolor: str = "#e2e8f0"
    node_fontname: str = "Inter"
    node_fontsize: int = 11
    node_width: float = 1.6
    node_height: float = 0.6
    node_margin_x: float = 0.12
    node_margin_y: float = 0.06
    edge_color: str = "#475569"
    edge_fontname: str = "Inter"
    edge_fontsize: int = 9
    edge_penwidth: float = 1.0
    inheritance_style: str = "solid"
    inheritance_color: str = "#60a5fa"
    association_color: str = "#f97316"
    instantiation_color: str = "#10b981"
    reference_color: str = "#a855f7"
    inheritance_arrowhead: str = "empty"
    association_arrowhead: str = "normal"
    instantiation_arrowhead: str = "diamond"
    reference_arrowhead: str = "vee"
    association_style: str = "dashed"
    instantiation_style: str = "dashed"
    reference_style: str = "dotted"


def build_uml_dot(
    model: Dict[str, object],
    edge_types: Optional[Set[str]] = None,
    graphviz: Optional[GraphvizStyleOptions] = None,
) -> str:
    """Generate Graphviz DOT format from UML model."""
    if edge_types is None:
        edge_types = {"inheritance", "association", "instantiation", "reference"}

    options = _prepare_graphviz_options(graphviz)

    splines_attr = (
        options.splines
        if options.splines.lower() in {"true", "false"}
        else f'"{_quote_attr(options.splines)}"'
    )

    classes: List[dict] = model.get("classes", [])  # type: ignore[assignment]
    lines: List[str] = [
        "digraph UML {",
        f"  rankdir={options.rankdir};",
        '  graph [fontname="'
        + _quote_attr(options.graph_fontname)
        + f'", fontsize={options.graph_fontsize}, overlap=false, splines={splines_attr}, nodesep={_format_float(options.nodesep)}, ranksep={_format_float(options.ranksep)}, pad="{_format_float(options.pad)}", margin="{_format_float(options.margin)}", bgcolor="{_quote_attr(options.bgcolor)}"];',
        "  node [shape="
        + options.node_shape
        + ', style="'
        + _quote_attr(options.node_style)
        + '", fontname="'
        + _quote_attr(options.node_fontname)
        + f'", fontsize={options.node_fontsize}, color="{_quote_attr(options.node_color)}", fillcolor="{_quote_attr(options.node_fillcolor)}", fontcolor="{_quote_attr(options.node_fontcolor)}", width={_format_float(options.node_width)}, height={_format_float(options.node_height)}, margin="{_format_float(options.node_margin_x)},{_format_float(options.node_margin_y)}"];',
        '  edge [fontname="'
        + _quote_attr(options.edge_fontname)
        + f'", fontsize={options.edge_fontsize}, color="{_quote_attr(options.edge_color)}", penwidth={_format_float(options.edge_penwidth)}];',
    ]

    # Add nodes
    for cls in classes:
        node_id = _escape_id(cls["id"])
        label = _build_node_label(cls)
        lines.append(f"  {node_id} [label={label}];")

    # Add edges based on requested types
    for cls in classes:
        source = _escape_id(cls["id"])

        # Inheritance (blue, solid, empty arrow)
        if "inheritance" in edge_types:
            for base in cls.get("bases", []):
                target = _escape_id(base)
                lines.append(
                    "  "
                    + target
                    + " -> "
                    + source
                    + ' [style="'
                    + _quote_attr(options.inheritance_style)
                    + '", arrowhead="'
                    + _quote_attr(options.inheritance_arrowhead)
                    + '", penwidth='
                    + _format_float(options.edge_penwidth)
                    + f', color="{_quote_attr(options.inheritance_color)}"];'
                )

        # Association (orange, dashed, normal arrow)
        if "association" in edge_types:
            for assoc in cls.get("associations", []):
                target = _escape_id(assoc)
                lines.append(
                    "  "
                    + source
                    + " -> "
                    + target
                    + ' [style="'
                    + _quote_attr(options.association_style)
                    + '", penwidth='
                    + _format_float(options.edge_penwidth)
                    + f', color="{_quote_attr(options.association_color)}", arrowhead="{_quote_attr(options.association_arrowhead)}"];'
                )

        # Instantiation (green, dashed, diamond arrow)
        if "instantiation" in edge_types:
            for inst in cls.get("instantiates", []):
                target = _escape_id(inst)
                lines.append(
                    "  "
                    + source
                    + " -> "
                    + target
                    + ' [style="'
                    + _quote_attr(options.instantiation_style)
                    + '", penwidth='
                    + _format_float(options.edge_penwidth)
                    + f', color="{_quote_attr(options.instantiation_color)}", arrowhead="{_quote_attr(options.instantiation_arrowhead)}"];'
                )

        # Reference (purple, dotted, vee arrow)
        if "reference" in edge_types:
            for ref in cls.get("references", []):
                target = _escape_id(ref)
                lines.append(
                    "  "
                    + source
                    + " -> "
                    + target
                    + ' [style="'
                    + _quote_attr(options.reference_style)
                    + '", penwidth='
                    + _format_float(options.edge_penwidth)
                    + f', color="{_quote_attr(options.reference_color)}", arrowhead="{_quote_attr(options.reference_arrowhead)}"];'
                )

    lines.append("}")
    return "\n".join(lines)


def render_uml_svg(
    model: Dict[str, object],
    edge_types: Optional[Set[str]] = None,
    graphviz: Optional[GraphvizStyleOptions] = None,
) -> str:
    """Render UML model to SVG using Graphviz."""
    options = _prepare_graphviz_options(graphviz)
    dot = build_uml_dot(model, edge_types, options)
    engine = options.layout_engine or "dot"
    dot_binary = shutil.which(engine)
    if not dot_binary:
        dot_binary = shutil.which("dot")
    if not dot_binary:
        raise RuntimeError("Graphviz command not found (looked for dot/neato family)")
    try:
        result = subprocess.run(  # nosec B603
            [dot_binary, "-Tsvg"],
            input=dot.encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        raise RuntimeError(exc.stderr.decode("utf-8", errors="ignore")) from exc

    return result.stdout.decode("utf-8")


def _prepare_graphviz_options(
    graphviz: Optional[GraphvizStyleOptions],
) -> GraphvizStyleOptions:
    source = graphviz or GraphvizStyleOptions()
    return GraphvizStyleOptions(
        layout_engine=_normalize_layout_engine(source.layout_engine),
        rankdir=_normalize_rankdir(source.rankdir),
        splines=_normalize_splines(source.splines),
        nodesep=_clamp_float(source.nodesep, default=0.6, minimum=0.1),
        ranksep=_clamp_float(source.ranksep, default=1.1, minimum=0.4),
        pad=_clamp_float(source.pad, default=0.3, minimum=0.0),
        margin=_clamp_float(source.margin, default=0.0, minimum=0.0),
        bgcolor=_sanitize_string(source.bgcolor, "#0b1120"),
        graph_fontname=_sanitize_string(source.graph_fontname, "Inter"),
        graph_fontsize=_clamp_int(source.graph_fontsize, default=11, minimum=6),
        node_shape=_normalize_node_shape(source.node_shape),
        node_style=_sanitize_string(source.node_style, "rounded,filled"),
        node_fillcolor=_sanitize_string(source.node_fillcolor, "#111827"),
        node_color=_sanitize_string(source.node_color, "#1f2937"),
        node_fontcolor=_sanitize_string(source.node_fontcolor, "#e2e8f0"),
        node_fontname=_sanitize_string(source.node_fontname, "Inter"),
        node_fontsize=_clamp_int(source.node_fontsize, default=11, minimum=6),
        node_width=_clamp_float(source.node_width, default=1.6, minimum=0.2),
        node_height=_clamp_float(source.node_height, default=0.6, minimum=0.2),
        node_margin_x=_clamp_float(source.node_margin_x, default=0.12, minimum=0.02),
        node_margin_y=_clamp_float(source.node_margin_y, default=0.06, minimum=0.02),
        edge_color=_sanitize_string(source.edge_color, "#475569"),
        edge_fontname=_sanitize_string(source.edge_fontname, "Inter"),
        edge_fontsize=_clamp_int(source.edge_fontsize, default=9, minimum=6),
        edge_penwidth=_clamp_float(source.edge_penwidth, default=1.0, minimum=0.5),
        inheritance_style=_sanitize_string(source.inheritance_style, "solid"),
        inheritance_color=_sanitize_string(source.inheritance_color, "#60a5fa"),
        association_color=_sanitize_string(source.association_color, "#f97316"),
        instantiation_color=_sanitize_string(source.instantiation_color, "#10b981"),
        reference_color=_sanitize_string(source.reference_color, "#a855f7"),
        inheritance_arrowhead=_sanitize_string(source.inheritance_arrowhead, "empty"),
        association_arrowhead=_sanitize_string(source.association_arrowhead, "normal"),
        instantiation_arrowhead=_sanitize_string(
            source.instantiation_arrowhead, "diamond"
        ),
        reference_arrowhead=_sanitize_string(source.reference_arrowhead, "vee"),
        association_style=_sanitize_string(source.association_style, "dashed"),
        instantiation_style=_sanitize_string(source.instantiation_style, "dashed"),
        reference_style=_sanitize_string(source.reference_style, "dotted"),
    )


def _normalize_layout_engine(value: Optional[str]) -> str:
    allowed = {"dot", "neato", "fdp", "sfdp", "circo", "twopi"}
    candidate = (value or "dot").lower()
    return candidate if candidate in allowed else "dot"


def _normalize_rankdir(value: Optional[str]) -> str:
    allowed = {"TB", "BT", "LR", "RL"}
    candidate = (value or "LR").upper()
    return candidate if candidate in allowed else "LR"


def _normalize_splines(value: Optional[str]) -> str:
    if value is None:
        return "true"
    candidate = value.strip().lower()
    if candidate in {"true", "false"}:
        return candidate
    allowed = {"line", "polyline", "spline", "curved", "ortho"}
    return candidate if candidate in allowed else "true"


def _normalize_node_shape(value: Optional[str]) -> str:
    allowed = {
        "box",
        "rect",
        "ellipse",
        "plaintext",
        "record",
        "component",
        "cylinder",
        "tab",
    }
    candidate = (value or "box").lower()
    return candidate if candidate in allowed else "box"


def _clamp_float(
    value: Optional[float],
    *,
    default: float,
    minimum: float,
    maximum: Optional[float] = None,
) -> float:
    try:
        numeric = float(value) if value is not None else default
    except (TypeError, ValueError):
        numeric = default
    if maximum is not None:
        numeric = min(numeric, maximum)
    if numeric < minimum:
        numeric = minimum
    return numeric


def _clamp_int(
    value: Optional[int],
    *,
    default: int,
    minimum: int,
    maximum: Optional[int] = None,
) -> int:
    try:
        numeric = int(value) if value is not None else default
    except (TypeError, ValueError):
        numeric = default
    if maximum is not None:
        numeric = min(numeric, maximum)
    if numeric < minimum:
        numeric = minimum
    return numeric


def _sanitize_string(value: Optional[str], fallback: str) -> str:
    candidate = (value or "").strip()
    return candidate or fallback


def _format_float(value: float) -> str:
    formatted = f"{value:.3f}"
    return formatted.rstrip("0").rstrip(".") or "0"


def _quote_attr(value: str) -> str:
    return value.replace('"', '\\"')


def _escape_id(value: str) -> str:
    return '"' + value.replace('"', '\\"') + '"'


def _build_node_label(cls: dict) -> str:
    name = html.escape(cls.get("name", ""))
    module = html.escape(cls.get("module", ""))
    if module:
        return f'<<b>{name}</b><br/><font point-size="9">{module}</font>>'
    return f"<<b>{name}</b>>"
