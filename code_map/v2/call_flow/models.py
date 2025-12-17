# SPDX-License-Identifier: MIT
"""
Data models for Call Flow Graph (v2).

Represents function/method call chains for visualization in React Flow.
Includes resolution status tracking to distinguish between:
- Resolved project code
- Ignored external calls (builtin/stdlib/third-party)
- Unresolved calls (dynamic code, missing info)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional


class ResolutionStatus(str, Enum):
    """
    Status of call resolution.

    Distinguishes between intentionally ignored calls (product decision)
    and unresolved calls (technical limitation).
    """

    RESOLVED_PROJECT = "resolved_project"  # Symbol found in project
    IGNORED_BUILTIN = "ignored_builtin"  # Python builtin (print, len, etc.)
    IGNORED_STDLIB = "ignored_stdlib"  # Standard library (os, json, etc.)
    IGNORED_THIRD_PARTY = "ignored_third_party"  # External package
    UNRESOLVED = "unresolved"  # Could not determine target
    AMBIGUOUS = "ambiguous"  # Multiple possible targets


@dataclass
class IgnoredCall:
    """
    Represents a call that was intentionally not expanded.

    Used for builtin, stdlib, and third-party calls that are
    outside the project scope.
    """

    expression: str  # The call expression (e.g., "print(...)")
    status: ResolutionStatus  # IGNORED_BUILTIN, IGNORED_STDLIB, etc.
    call_site_line: int  # Line where the call occurs
    module_hint: Optional[str] = None  # Module name if known (e.g., "json")

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "expression": self.expression,
            "status": self.status.value,
            "call_site_line": self.call_site_line,
            "module_hint": self.module_hint,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IgnoredCall":
        """Create from dictionary."""
        return cls(
            expression=data["expression"],
            status=ResolutionStatus(data["status"]),
            call_site_line=data["call_site_line"],
            module_hint=data.get("module_hint"),
        )


@dataclass
class CallNode:
    """
    A node in the call flow graph representing a function or method.

    Attributes:
        id: Unique identifier (typically file:line:name)
        name: Simple function/method name
        qualified_name: Full qualified name including class (e.g., "MainWindow.on_click")
        file_path: Path to the source file
        line: Line number where the function is defined
        column: Column number where the function is defined (for stable ID)
        kind: Type of callable ("function", "method", "external", "builtin")
        is_entry_point: True if this is the starting point of the graph
        depth: Distance from entry point (0 = entry point)
        docstring: First line of docstring if available
        symbol_id: Stable identifier format: {rel_path}:{line}:{col}:{kind}:{name}
        resolution_status: How this node was resolved
        reasons: Explanation for UNRESOLVED/AMBIGUOUS status
        complexity: Cyclomatic complexity (McCabe) - None if not available
        loc: Lines of code in the function - None if not available
    """

    id: str
    name: str
    qualified_name: str
    file_path: Optional[Path] = None
    line: int = 0
    column: int = 0
    kind: str = "function"  # function | method | external | builtin
    is_entry_point: bool = False
    depth: int = 0
    docstring: Optional[str] = None
    symbol_id: Optional[str] = None  # Stable ID: {rel_path}:{line}:{col}:{kind}:{name}
    resolution_status: ResolutionStatus = ResolutionStatus.RESOLVED_PROJECT
    reasons: Optional[str] = None  # Why UNRESOLVED/AMBIGUOUS
    complexity: Optional[int] = None  # Cyclomatic complexity (McCabe)
    loc: Optional[int] = None  # Lines of code

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "qualified_name": self.qualified_name,
            "file_path": str(self.file_path) if self.file_path else None,
            "line": self.line,
            "column": self.column,
            "kind": self.kind,
            "is_entry_point": self.is_entry_point,
            "depth": self.depth,
            "docstring": self.docstring,
            "symbol_id": self.symbol_id,
            "resolution_status": self.resolution_status.value,
            "reasons": self.reasons,
            "complexity": self.complexity,
            "loc": self.loc,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CallNode":
        """Create from dictionary."""
        status_val = data.get("resolution_status", "resolved_project")
        return cls(
            id=data["id"],
            name=data["name"],
            qualified_name=data["qualified_name"],
            file_path=Path(data["file_path"]) if data.get("file_path") else None,
            line=data.get("line", 0),
            column=data.get("column", 0),
            kind=data.get("kind", "function"),
            is_entry_point=data.get("is_entry_point", False),
            depth=data.get("depth", 0),
            docstring=data.get("docstring"),
            symbol_id=data.get("symbol_id"),
            resolution_status=ResolutionStatus(status_val),
            reasons=data.get("reasons"),
            complexity=data.get("complexity"),
            loc=data.get("loc"),
        )


@dataclass
class CallEdge:
    """
    An edge representing a function call from source to target.

    Attributes:
        source_id: ID of the calling function
        target_id: ID of the called function
        call_site_line: Line number where the call occurs
        call_type: Type of call ("direct", "method", "constructor", "module_attr", etc.)
        arguments: Optional list of argument names/values
        expression: The call expression as it appears in code (e.g., "self.loader.load()")
        resolution_status: How this call was resolved
    """

    source_id: str
    target_id: str
    call_site_line: int
    call_type: str = "direct"  # direct | method | constructor | module_attr | super | static
    arguments: Optional[List[str]] = None
    expression: Optional[str] = None  # The call expression
    resolution_status: ResolutionStatus = ResolutionStatus.RESOLVED_PROJECT

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "call_site_line": self.call_site_line,
            "call_type": self.call_type,
            "arguments": self.arguments,
            "expression": self.expression,
            "resolution_status": self.resolution_status.value,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CallEdge":
        """Create from dictionary."""
        status_val = data.get("resolution_status", "resolved_project")
        return cls(
            source_id=data["source_id"],
            target_id=data["target_id"],
            call_site_line=data["call_site_line"],
            call_type=data.get("call_type", "direct"),
            arguments=data.get("arguments"),
            expression=data.get("expression"),
            resolution_status=ResolutionStatus(status_val),
        )


@dataclass
class CallGraph:
    """
    Complete call flow graph from an entry point.

    Represents all reachable function calls from a starting function,
    up to a configurable maximum depth.

    Attributes:
        entry_point: ID of the entry point function
        nodes: Dictionary of node_id -> CallNode
        edges: List of call edges
        max_depth: Maximum depth that was requested
        max_depth_reached: True if exploration stopped due to depth limit
        ignored_calls: List of calls that were not expanded (builtin/stdlib/third-party)
        unresolved_calls: List of calls that could not be resolved
        source_file: The entry point source file
        diagnostics: Metadata about graph construction (truncation, budget, etc.)
    """

    entry_point: str
    nodes: Dict[str, CallNode] = field(default_factory=dict)
    edges: List[CallEdge] = field(default_factory=list)
    max_depth: int = 5
    max_depth_reached: bool = False
    ignored_calls: List[IgnoredCall] = field(default_factory=list)
    unresolved_calls: List[str] = field(default_factory=list)  # Simple list of call expressions
    source_file: Optional[Path] = None
    diagnostics: Dict[str, Any] = field(default_factory=dict)

    def add_node(self, node: CallNode) -> None:
        """Add a node to the graph."""
        self.nodes[node.id] = node

    def add_edge(self, edge: CallEdge) -> None:
        """Add an edge to the graph."""
        self.edges.append(edge)

    def get_node(self, node_id: str) -> Optional[CallNode]:
        """Get a node by ID."""
        return self.nodes.get(node_id)

    def iter_nodes(self) -> Iterator[CallNode]:
        """Iterate over all nodes."""
        yield from self.nodes.values()

    def iter_edges(self) -> Iterator[CallEdge]:
        """Iterate over all edges."""
        yield from self.edges

    def node_count(self) -> int:
        """Get number of nodes."""
        return len(self.nodes)

    def edge_count(self) -> int:
        """Get number of edges."""
        return len(self.edges)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "entry_point": self.entry_point,
            "nodes": {nid: n.to_dict() for nid, n in self.nodes.items()},
            "edges": [e.to_dict() for e in self.edges],
            "max_depth": self.max_depth,
            "max_depth_reached": self.max_depth_reached,
            "ignored_calls": [ic.to_dict() for ic in self.ignored_calls],
            "unresolved_calls": self.unresolved_calls,  # Already List[str]
            "source_file": str(self.source_file) if self.source_file else None,
            "diagnostics": self.diagnostics,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CallGraph":
        """Create from dictionary."""
        graph = cls(
            entry_point=data["entry_point"],
            max_depth=data.get("max_depth", 5),
            max_depth_reached=data.get("max_depth_reached", False),
            source_file=Path(data["source_file"]) if data.get("source_file") else None,
            diagnostics=data.get("diagnostics", {}),
        )
        for nid, ndata in data.get("nodes", {}).items():
            graph.nodes[nid] = CallNode.from_dict(ndata)
        for edata in data.get("edges", []):
            graph.edges.append(CallEdge.from_dict(edata))
        for icdata in data.get("ignored_calls", []):
            graph.ignored_calls.append(IgnoredCall.from_dict(icdata))
        graph.unresolved_calls = list(data.get("unresolved_calls", []))
        return graph

    def to_react_flow(self) -> Dict[str, Any]:
        """
        Convert to React Flow format for frontend visualization.

        Returns:
            Dictionary with 'nodes', 'edges', and 'metadata' for React Flow.
        """
        react_nodes = []
        react_edges = []

        # Calculate positions (simple left-to-right by depth)
        depth_counts: Dict[int, int] = {}

        for node in self.iter_nodes():
            depth = node.depth
            y_index = depth_counts.get(depth, 0)
            depth_counts[depth] = y_index + 1

            react_nodes.append({
                "id": node.id,
                "type": "callNode",
                "position": {
                    "x": depth * 280,
                    "y": y_index * 120,
                },
                "data": {
                    "label": node.name,
                    "qualifiedName": node.qualified_name,
                    "filePath": str(node.file_path) if node.file_path else None,
                    "line": node.line,
                    "column": node.column,
                    "kind": node.kind,
                    "isEntryPoint": node.is_entry_point,
                    "depth": node.depth,
                    "docstring": node.docstring,
                    "symbolId": node.symbol_id,
                    "resolutionStatus": node.resolution_status.value,
                    "reasons": node.reasons,
                    "complexity": node.complexity,
                    "loc": node.loc,
                },
            })

        for i, edge in enumerate(self.iter_edges()):
            react_edges.append({
                "id": f"e{i}",
                "source": edge.source_id,
                "target": edge.target_id,
                "type": "smoothstep",
                "animated": edge.source_id == self.entry_point,
                "data": {
                    "callSiteLine": edge.call_site_line,
                    "callType": edge.call_type,
                    "expression": edge.expression,
                    "resolutionStatus": edge.resolution_status.value,
                },
            })

        return {
            "nodes": react_nodes,
            "edges": react_edges,
            "metadata": {
                "entry_point": self.entry_point,
                "source_file": str(self.source_file) if self.source_file else None,
                "max_depth": self.max_depth,
                "max_depth_reached": self.max_depth_reached,
                "node_count": self.node_count(),
                "edge_count": self.edge_count(),
                "ignored_calls_count": len(self.ignored_calls),
                "unresolved_calls_count": len(self.unresolved_calls),
                "diagnostics": self.diagnostics,
            },
        }
