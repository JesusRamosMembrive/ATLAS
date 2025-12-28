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


class DecisionType(str, Enum):
    """
    Type of control flow decision point.

    Note: Loops (FOR_LOOP, WHILE_LOOP) are intentionally excluded
    to keep visualization simpler - they're treated as linear flow.
    """

    IF_ELSE = "if_else"  # if/elif/else statements
    MATCH_CASE = "match_case"  # Python 3.10+ match/case
    TRY_EXCEPT = "try_except"  # try/except/finally blocks
    TERNARY = "ternary"  # Conditional expressions (x if cond else y)


class ExtractionMode(str, Enum):
    """
    Mode for call flow extraction.

    Controls how decision points are handled during extraction.
    """

    FULL = "full"  # Extract all paths (current behavior)
    LAZY = "lazy"  # Stop at decision points, allow incremental expansion


@dataclass
class BranchInfo:
    """
    Information about a specific branch within a decision point.

    Used to represent individual branches (TRUE/FALSE for if,
    case clauses for match, except handlers for try).
    """

    branch_id: str  # Unique ID: "{decision_id}:branch:{index}"
    label: str  # Human-readable: "TRUE", "FALSE", "case X", "except ValueError"
    condition_text: str  # The condition expression or case pattern
    is_expanded: bool = False  # Whether this branch has been explored
    call_count: int = 0  # Preview: number of direct calls in this branch
    start_line: int = 0  # Branch body start line
    end_line: int = 0  # Branch body end line

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "branch_id": self.branch_id,
            "label": self.label,
            "condition_text": self.condition_text,
            "is_expanded": self.is_expanded,
            "call_count": self.call_count,
            "start_line": self.start_line,
            "end_line": self.end_line,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BranchInfo":
        """Create from dictionary."""
        return cls(
            branch_id=data["branch_id"],
            label=data["label"],
            condition_text=data["condition_text"],
            is_expanded=data.get("is_expanded", False),
            call_count=data.get("call_count", 0),
            start_line=data.get("start_line", 0),
            end_line=data.get("end_line", 0),
        )


@dataclass
class DecisionNode:
    """
    Represents a control flow decision point in the call graph.

    Decision nodes are special nodes that don't represent function calls
    but represent points where execution can diverge into multiple branches.
    """

    id: str  # Unique ID: "decision:{file}:{line}:{type}"
    decision_type: DecisionType  # Type of decision (if_else, match_case, etc.)
    condition_text: str  # The condition expression
    file_path: Optional[Path] = None  # Source file
    line: int = 0  # Line number of the decision
    column: int = 0  # Column number
    parent_call_id: str = ""  # ID of the CallNode containing this decision
    branches: List[BranchInfo] = field(default_factory=list)  # Available branches
    depth: int = 0  # Depth in call graph (same as parent call)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "decision_type": self.decision_type.value,
            "condition_text": self.condition_text,
            "file_path": str(self.file_path) if self.file_path else None,
            "line": self.line,
            "column": self.column,
            "parent_call_id": self.parent_call_id,
            "branches": [b.to_dict() for b in self.branches],
            "depth": self.depth,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DecisionNode":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            decision_type=DecisionType(data["decision_type"]),
            condition_text=data["condition_text"],
            file_path=Path(data["file_path"]) if data.get("file_path") else None,
            line=data.get("line", 0),
            column=data.get("column", 0),
            parent_call_id=data.get("parent_call_id", ""),
            branches=[BranchInfo.from_dict(b) for b in data.get("branches", [])],
            depth=data.get("depth", 0),
        )

    def get_unexpanded_branches(self) -> List[str]:
        """Return IDs of branches that haven't been expanded yet."""
        return [b.branch_id for b in self.branches if not b.is_expanded]

    def mark_branch_expanded(self, branch_id: str) -> bool:
        """Mark a branch as expanded. Returns True if found."""
        for branch in self.branches:
            if branch.branch_id == branch_id:
                branch.is_expanded = True
                return True
        return False


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
    caller_id: Optional[str] = None  # ID of the node that made this call

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "expression": self.expression,
            "status": self.status.value,
            "call_site_line": self.call_site_line,
            "module_hint": self.module_hint,
            "caller_id": self.caller_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IgnoredCall":
        """Create from dictionary."""
        return cls(
            expression=data["expression"],
            status=ResolutionStatus(data["status"]),
            call_site_line=data["call_site_line"],
            module_hint=data.get("module_hint"),
            caller_id=data.get("caller_id"),
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
        branch_id: ID of the branch this call is within (for decision-aware extraction)
        decision_id: ID of the parent decision node (for decision-aware extraction)
    """

    source_id: str
    target_id: str
    call_site_line: int
    call_type: str = (
        "direct"  # direct | method | constructor | module_attr | super | static
    )
    arguments: Optional[List[str]] = None
    expression: Optional[str] = None  # The call expression
    resolution_status: ResolutionStatus = ResolutionStatus.RESOLVED_PROJECT
    # Branch context for decision-aware extraction
    branch_id: Optional[str] = None  # Which branch this call is within
    decision_id: Optional[str] = None  # Parent decision node

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = {
            "source_id": self.source_id,
            "target_id": self.target_id,
            "call_site_line": self.call_site_line,
            "call_type": self.call_type,
            "arguments": self.arguments,
            "expression": self.expression,
            "resolution_status": self.resolution_status.value,
        }
        # Only include branch context if present
        if self.branch_id is not None:
            result["branch_id"] = self.branch_id
        if self.decision_id is not None:
            result["decision_id"] = self.decision_id
        return result

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
            branch_id=data.get("branch_id"),
            decision_id=data.get("decision_id"),
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
        decision_nodes: Dictionary of decision_id -> DecisionNode (for lazy extraction)
        unexpanded_branches: List of branch IDs not yet explored
        extraction_mode: Mode used for extraction ("full" or "lazy")
    """

    entry_point: str
    nodes: Dict[str, CallNode] = field(default_factory=dict)
    edges: List[CallEdge] = field(default_factory=list)
    max_depth: int = 5
    max_depth_reached: bool = False
    ignored_calls: List[IgnoredCall] = field(default_factory=list)
    unresolved_calls: List[str] = field(
        default_factory=list
    )  # Simple list of call expressions
    source_file: Optional[Path] = None
    diagnostics: Dict[str, Any] = field(default_factory=dict)
    # Decision point tracking for lazy/interactive extraction
    decision_nodes: Dict[str, DecisionNode] = field(default_factory=dict)
    unexpanded_branches: List[str] = field(default_factory=list)
    extraction_mode: str = "full"  # "full" | "lazy"

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

    def add_decision_node(self, node: DecisionNode) -> None:
        """Add a decision node to the graph."""
        self.decision_nodes[node.id] = node
        # Track unexpanded branches
        for branch in node.branches:
            if not branch.is_expanded:
                self.unexpanded_branches.append(branch.branch_id)

    def get_decision_node(self, node_id: str) -> Optional[DecisionNode]:
        """Get a decision node by ID."""
        return self.decision_nodes.get(node_id)

    def iter_decision_nodes(self) -> Iterator[DecisionNode]:
        """Iterate over all decision nodes."""
        yield from self.decision_nodes.values()

    def decision_node_count(self) -> int:
        """Get number of decision nodes."""
        return len(self.decision_nodes)

    def mark_branch_expanded(self, branch_id: str) -> bool:
        """
        Mark a branch as expanded.

        Returns True if the branch was found and marked.
        """
        # Find the decision node containing this branch
        for decision_node in self.decision_nodes.values():
            if decision_node.mark_branch_expanded(branch_id):
                # Remove from unexpanded list
                if branch_id in self.unexpanded_branches:
                    self.unexpanded_branches.remove(branch_id)
                return True
        return False

    def get_branch_info(self, branch_id: str) -> Optional[BranchInfo]:
        """Get branch info by branch ID."""
        for decision_node in self.decision_nodes.values():
            for branch in decision_node.branches:
                if branch.branch_id == branch_id:
                    return branch
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = {
            "entry_point": self.entry_point,
            "nodes": {nid: n.to_dict() for nid, n in self.nodes.items()},
            "edges": [e.to_dict() for e in self.edges],
            "max_depth": self.max_depth,
            "max_depth_reached": self.max_depth_reached,
            "ignored_calls": [ic.to_dict() for ic in self.ignored_calls],
            "unresolved_calls": self.unresolved_calls,  # Already List[str]
            "source_file": str(self.source_file) if self.source_file else None,
            "diagnostics": self.diagnostics,
            "extraction_mode": self.extraction_mode,
        }
        # Only include decision node fields if there are any
        if self.decision_nodes:
            result["decision_nodes"] = {
                did: d.to_dict() for did, d in self.decision_nodes.items()
            }
            result["unexpanded_branches"] = self.unexpanded_branches
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CallGraph":
        """Create from dictionary."""
        graph = cls(
            entry_point=data["entry_point"],
            max_depth=data.get("max_depth", 5),
            max_depth_reached=data.get("max_depth_reached", False),
            source_file=Path(data["source_file"]) if data.get("source_file") else None,
            diagnostics=data.get("diagnostics", {}),
            extraction_mode=data.get("extraction_mode", "full"),
        )
        for nid, ndata in data.get("nodes", {}).items():
            graph.nodes[nid] = CallNode.from_dict(ndata)
        for edata in data.get("edges", []):
            graph.edges.append(CallEdge.from_dict(edata))
        for icdata in data.get("ignored_calls", []):
            graph.ignored_calls.append(IgnoredCall.from_dict(icdata))
        graph.unresolved_calls = list(data.get("unresolved_calls", []))
        # Load decision nodes if present
        for did, ddata in data.get("decision_nodes", {}).items():
            graph.decision_nodes[did] = DecisionNode.from_dict(ddata)
        graph.unexpanded_branches = list(data.get("unexpanded_branches", []))
        return graph

    def to_react_flow(self) -> Dict[str, Any]:
        """
        Convert to React Flow format for frontend visualization.

        Returns:
            Dictionary with 'nodes', 'edges', 'decision_nodes', and 'metadata'
            for React Flow.
        """
        react_nodes = []
        react_edges = []
        react_decision_nodes = []

        # Calculate positions (simple left-to-right by depth)
        depth_counts: Dict[int, int] = {}

        for node in self.iter_nodes():
            depth = node.depth
            y_index = depth_counts.get(depth, 0)
            depth_counts[depth] = y_index + 1

            react_nodes.append(
                {
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
                }
            )

        # Add decision nodes to React Flow format
        for decision_node in self.iter_decision_nodes():
            depth = decision_node.depth
            y_index = depth_counts.get(depth, 0)
            depth_counts[depth] = y_index + 1

            react_decision_nodes.append(
                {
                    "id": decision_node.id,
                    "type": "decisionNode",
                    "position": {
                        "x": depth * 280 + 140,  # Offset slightly from call nodes
                        "y": y_index * 120,
                    },
                    "data": {
                        "label": decision_node.decision_type.value,
                        "decisionType": decision_node.decision_type.value,
                        "conditionText": decision_node.condition_text,
                        "filePath": (
                            str(decision_node.file_path)
                            if decision_node.file_path
                            else None
                        ),
                        "line": decision_node.line,
                        "column": decision_node.column,
                        "parentCallId": decision_node.parent_call_id,
                        "depth": decision_node.depth,
                        "branches": [b.to_dict() for b in decision_node.branches],
                    },
                }
            )

        for i, edge in enumerate(self.iter_edges()):
            edge_data: Dict[str, Any] = {
                "callSiteLine": edge.call_site_line,
                "callType": edge.call_type,
                "expression": edge.expression,
                "resolutionStatus": edge.resolution_status.value,
            }
            # Include branch context if present
            if edge.branch_id:
                edge_data["branchId"] = edge.branch_id
            if edge.decision_id:
                edge_data["decisionId"] = edge.decision_id

            react_edges.append(
                {
                    "id": f"e{i}",
                    "source": edge.source_id,
                    "target": edge.target_id,
                    "type": "smoothstep",
                    "animated": edge.source_id == self.entry_point,
                    "data": edge_data,
                }
            )

        result = {
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
                "extraction_mode": self.extraction_mode,
            },
        }

        # Include decision nodes and unexpanded branches if present
        if self.decision_nodes:
            result["decision_nodes"] = react_decision_nodes
            result["unexpanded_branches"] = self.unexpanded_branches

        return result
