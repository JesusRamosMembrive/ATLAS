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
class ReturnNode:
    """
    Represents a return statement in the call graph.

    Return nodes show where execution exits a branch, making it clear
    to users why clicking a branch button didn't expand into more calls
    (because it just returns a value).
    """

    id: str  # Unique ID: "return:{file}:{line}"
    return_value: str  # The return expression (e.g., "True", "result + 1", "None")
    file_path: Optional[Path] = None  # Source file
    line: int = 0  # Line number
    column: int = 0  # Column number
    parent_call_id: str = ""  # ID of the CallNode containing this return
    branch_id: Optional[str] = None  # Which branch this return is in
    decision_id: Optional[str] = None  # Parent decision node
    depth: int = 0  # Depth in call graph

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = {
            "id": self.id,
            "return_value": self.return_value,
            "file_path": str(self.file_path) if self.file_path else None,
            "line": self.line,
            "column": self.column,
            "parent_call_id": self.parent_call_id,
            "depth": self.depth,
        }
        if self.branch_id is not None:
            result["branch_id"] = self.branch_id
        if self.decision_id is not None:
            result["decision_id"] = self.decision_id
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ReturnNode":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            return_value=data["return_value"],
            file_path=Path(data["file_path"]) if data.get("file_path") else None,
            line=data.get("line", 0),
            column=data.get("column", 0),
            parent_call_id=data.get("parent_call_id", ""),
            branch_id=data.get("branch_id"),
            decision_id=data.get("decision_id"),
            depth=data.get("depth", 0),
        )


class StatementType(str, Enum):
    """Types of control flow statements that terminate or alter branch execution."""

    BREAK = "break"
    CONTINUE = "continue"
    PASS = "pass"
    RAISE = "raise"
    ASSIGNMENT = "assignment"  # When branch only has assignments


@dataclass
class StatementNode:
    """
    A node representing a control flow statement in a branch.

    Used to visualize branch content when there are no function calls.
    This ensures decision nodes are never "dead ends" visually - the user
    always sees what happens in a branch.

    Examples:
    - break/continue in loops
    - pass (empty branch)
    - raise Exception (exception throwing)
    - Simple assignments (when that's all the branch does)
    """

    id: str  # Unique ID: "stmt:{file}:{line}:{type}"
    statement_type: StatementType  # break, continue, pass, raise, assignment
    content: str  # The statement text (e.g., "break", "raise ValueError(...)")
    file_path: Optional[Path] = None  # Source file
    line: int = 0  # Line number
    column: int = 0  # Column number
    parent_call_id: str = ""  # ID of the CallNode containing this statement
    branch_id: Optional[str] = None  # Which branch this statement is in
    decision_id: Optional[str] = None  # Parent decision node
    depth: int = 0  # Depth in call graph

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = {
            "id": self.id,
            "statement_type": self.statement_type.value,
            "content": self.content,
            "file_path": str(self.file_path) if self.file_path else None,
            "line": self.line,
            "column": self.column,
            "parent_call_id": self.parent_call_id,
            "depth": self.depth,
        }
        if self.branch_id is not None:
            result["branch_id"] = self.branch_id
        if self.decision_id is not None:
            result["decision_id"] = self.decision_id
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StatementNode":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            statement_type=StatementType(data["statement_type"]),
            content=data["content"],
            file_path=Path(data["file_path"]) if data.get("file_path") else None,
            line=data.get("line", 0),
            column=data.get("column", 0),
            parent_call_id=data.get("parent_call_id", ""),
            branch_id=data.get("branch_id"),
            decision_id=data.get("decision_id"),
            depth=data.get("depth", 0),
        )


class ExternalCallType(str, Enum):
    """Types of external calls for visual distinction."""

    BUILTIN = "builtin"  # Python builtins: len, print, str, etc.
    STDLIB = "stdlib"  # Standard library: json.loads, os.path, etc.
    THIRD_PARTY = "third_party"  # External packages: requests.get, etc.


@dataclass
class ExternalCallNode:
    """
    A node representing an external library/builtin call in a branch.

    Used to visualize external calls that were previously "ignored" but
    still need to be shown so branches are never "dead ends".
    """

    id: str  # Unique ID: "ext:{file}:{line}:{expression}"
    expression: str  # The call expression (e.g., "session.get(url)")
    call_type: ExternalCallType  # builtin, stdlib, third_party
    module_hint: Optional[str] = None  # Module name if known (e.g., "requests")
    file_path: Optional[Path] = None  # Source file
    line: int = 0  # Line number
    column: int = 0  # Column number
    parent_call_id: str = ""  # ID of the CallNode containing this call
    branch_id: Optional[str] = None  # Which branch this call is in
    decision_id: Optional[str] = None  # Parent decision node
    depth: int = 0  # Depth in call graph

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = {
            "id": self.id,
            "expression": self.expression,
            "call_type": self.call_type.value,
            "module_hint": self.module_hint,
            "file_path": str(self.file_path) if self.file_path else None,
            "line": self.line,
            "column": self.column,
            "parent_call_id": self.parent_call_id,
            "depth": self.depth,
        }
        if self.branch_id is not None:
            result["branch_id"] = self.branch_id
        if self.decision_id is not None:
            result["decision_id"] = self.decision_id
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExternalCallNode":
        """Create from dictionary."""
        return cls(
            id=data["id"],
            expression=data["expression"],
            call_type=ExternalCallType(data["call_type"]),
            module_hint=data.get("module_hint"),
            file_path=Path(data["file_path"]) if data.get("file_path") else None,
            line=data.get("line", 0),
            column=data.get("column", 0),
            parent_call_id=data.get("parent_call_id", ""),
            branch_id=data.get("branch_id"),
            decision_id=data.get("decision_id"),
            depth=data.get("depth", 0),
        )


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
    branch_id: Optional[str] = None  # Branch ID if this call is inside a branch
    decision_id: Optional[str] = None  # Decision node ID if inside a branch

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "expression": self.expression,
            "status": self.status.value,
            "call_site_line": self.call_site_line,
            "module_hint": self.module_hint,
            "caller_id": self.caller_id,
            "branch_id": self.branch_id,
            "decision_id": self.decision_id,
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
            branch_id=data.get("branch_id"),
            decision_id=data.get("decision_id"),
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
    branch_id: Optional[str] = None  # Branch ID if inside a decision branch
    decision_id: Optional[str] = None  # Decision node ID if inside a branch

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
            "branch_id": self.branch_id,
            "decision_id": self.decision_id,
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
            branch_id=data.get("branch_id"),
            decision_id=data.get("decision_id"),
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
        return_nodes: Dictionary of return_id -> ReturnNode (for showing return statements)
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
    # Return statement tracking
    return_nodes: Dict[str, ReturnNode] = field(default_factory=dict)
    # Statement node tracking (break, continue, pass, raise, assignments)
    statement_nodes: Dict[str, StatementNode] = field(default_factory=dict)
    # External call node tracking (builtin, stdlib, third-party calls)
    external_call_nodes: Dict[str, ExternalCallNode] = field(default_factory=dict)

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

    def add_return_node(self, node: ReturnNode) -> None:
        """Add a return node to the graph."""
        self.return_nodes[node.id] = node

    def get_return_node(self, node_id: str) -> Optional[ReturnNode]:
        """Get a return node by ID."""
        return self.return_nodes.get(node_id)

    def iter_return_nodes(self) -> Iterator[ReturnNode]:
        """Iterate over all return nodes."""
        yield from self.return_nodes.values()

    def return_node_count(self) -> int:
        """Get number of return nodes."""
        return len(self.return_nodes)

    def add_statement_node(self, node: StatementNode) -> None:
        """Add a statement node to the graph."""
        self.statement_nodes[node.id] = node

    def get_statement_node(self, node_id: str) -> Optional[StatementNode]:
        """Get a statement node by ID."""
        return self.statement_nodes.get(node_id)

    def iter_statement_nodes(self) -> Iterator[StatementNode]:
        """Iterate over all statement nodes."""
        yield from self.statement_nodes.values()

    def statement_node_count(self) -> int:
        """Get number of statement nodes."""
        return len(self.statement_nodes)

    def add_external_call_node(self, node: ExternalCallNode) -> None:
        """Add an external call node to the graph."""
        self.external_call_nodes[node.id] = node

    def get_external_call_node(self, node_id: str) -> Optional[ExternalCallNode]:
        """Get an external call node by ID."""
        return self.external_call_nodes.get(node_id)

    def iter_external_call_nodes(self) -> Iterator[ExternalCallNode]:
        """Iterate over all external call nodes."""
        yield from self.external_call_nodes.values()

    def external_call_node_count(self) -> int:
        """Get number of external call nodes."""
        return len(self.external_call_nodes)

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
        # Only include return nodes if there are any
        if self.return_nodes:
            result["return_nodes"] = {
                rid: r.to_dict() for rid, r in self.return_nodes.items()
            }
        # Only include statement nodes if there are any
        if self.statement_nodes:
            result["statement_nodes"] = {
                sid: s.to_dict() for sid, s in self.statement_nodes.items()
            }
        # Only include external call nodes if there are any
        if self.external_call_nodes:
            result["external_call_nodes"] = {
                eid: e.to_dict() for eid, e in self.external_call_nodes.items()
            }
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
        # Load return nodes if present
        for rid, rdata in data.get("return_nodes", {}).items():
            graph.return_nodes[rid] = ReturnNode.from_dict(rdata)
        # Load statement nodes if present
        for sid, sdata in data.get("statement_nodes", {}).items():
            graph.statement_nodes[sid] = StatementNode.from_dict(sdata)
        # Load external call nodes if present
        for eid, edata in data.get("external_call_nodes", {}).items():
            graph.external_call_nodes[eid] = ExternalCallNode.from_dict(edata)
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
                        "x": depth * 350,
                        "y": y_index * 140,
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
                        "x": depth * 350 + 175,  # Offset slightly from call nodes
                        "y": y_index * 140,
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

        # Add return nodes to React Flow format
        react_return_nodes = []
        for return_node in self.iter_return_nodes():
            depth = return_node.depth
            y_index = depth_counts.get(depth, 0)
            depth_counts[depth] = y_index + 1

            react_return_nodes.append(
                {
                    "id": return_node.id,
                    "type": "returnNode",
                    "position": {
                        "x": depth * 350 + 175,
                        "y": y_index * 140,
                    },
                    "data": {
                        "label": "return",
                        "returnValue": return_node.return_value,
                        "filePath": (
                            str(return_node.file_path)
                            if return_node.file_path
                            else None
                        ),
                        "line": return_node.line,
                        "column": return_node.column,
                        "parentCallId": return_node.parent_call_id,
                        "branchId": return_node.branch_id,
                        "decisionId": return_node.decision_id,
                        "depth": return_node.depth,
                    },
                }
            )

        # Track which targets already have edges from decision nodes
        # to avoid duplicates (key: decision_id:target_id)
        decision_to_target_edges: set[str] = set()

        for edge in self.iter_edges():
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

            # If this edge belongs to a branch, create edge from decision node
            # instead of from the original source (parent function)
            if edge.decision_id and edge.branch_id:
                edge_key = f"{edge.decision_id}:{edge.target_id}"
                if edge_key not in decision_to_target_edges:
                    decision_to_target_edges.add(edge_key)
                    # Stable ID for branch edges
                    branch_edge_id = f"eb:{edge.decision_id}->{edge.target_id}"
                    react_edges.append(
                        {
                            "id": branch_edge_id,
                            "source": edge.decision_id,
                            "target": edge.target_id,
                            "type": "smoothstep",
                            "animated": False,
                            "data": {
                                "callSiteLine": edge.call_site_line,
                                "callType": "branch_call",
                                "branchId": edge.branch_id,
                                "decisionId": edge.decision_id,
                            },
                        }
                    )
            else:
                # Regular edge (not in a branch) - connect from source to target
                edge_id = f"e:{edge.source_id}->{edge.target_id}@{edge.call_site_line}"
                react_edges.append(
                    {
                        "id": edge_id,
                        "source": edge.source_id,
                        "target": edge.target_id,
                        "type": "smoothstep",
                        "animated": edge.source_id == self.entry_point,
                        "data": edge_data,
                    }
                )

        # Create edges from parent call nodes to decision nodes
        for decision_node in self.iter_decision_nodes():
            if decision_node.parent_call_id:
                # Stable ID for decision edges
                decision_edge_id = f"ed:{decision_node.parent_call_id}->{decision_node.id}"
                react_edges.append(
                    {
                        "id": decision_edge_id,
                        "source": decision_node.parent_call_id,
                        "target": decision_node.id,
                        "type": "smoothstep",
                        "animated": False,
                        "style": {"strokeDasharray": "5,5"},  # Dashed line for decision edges
                        "data": {
                            "callSiteLine": decision_node.line,
                            "callType": "decision",
                            "decisionType": decision_node.decision_type.value,
                        },
                    }
                )

        # Create edges from decision nodes to return nodes
        for return_node in self.iter_return_nodes():
            if return_node.decision_id:
                return_edge_id = f"er:{return_node.decision_id}->{return_node.id}"
                react_edges.append(
                    {
                        "id": return_edge_id,
                        "source": return_node.decision_id,
                        "target": return_node.id,
                        "type": "smoothstep",
                        "animated": False,
                        "data": {
                            "callSiteLine": return_node.line,
                            "callType": "return",
                            "branchId": return_node.branch_id,
                            "decisionId": return_node.decision_id,
                        },
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
                "return_node_count": self.return_node_count(),
                "statement_node_count": self.statement_node_count(),
                "external_call_node_count": self.external_call_node_count(),
            },
        }

        # Include decision nodes and unexpanded branches if present
        if self.decision_nodes:
            result["decision_nodes"] = react_decision_nodes
            result["unexpanded_branches"] = self.unexpanded_branches

        # Include return nodes if present
        if self.return_nodes:
            result["return_nodes"] = react_return_nodes

        # Include statement nodes if present
        if self.statement_nodes:
            react_statement_nodes = []
            for stmt_node in self.iter_statement_nodes():
                depth = stmt_node.depth
                y_index = depth_counts.get(depth, 0)
                depth_counts[depth] = y_index + 1

                react_statement_nodes.append(
                    {
                        "id": stmt_node.id,
                        "type": "statementNode",
                        "position": {
                            "x": depth * 350 + 175,
                            "y": y_index * 140,
                        },
                        "data": {
                            "label": stmt_node.statement_type.value,
                            "statementType": stmt_node.statement_type.value,
                            "content": stmt_node.content,
                            "filePath": (
                                str(stmt_node.file_path)
                                if stmt_node.file_path
                                else None
                            ),
                            "line": stmt_node.line,
                            "column": stmt_node.column,
                            "parentCallId": stmt_node.parent_call_id,
                            "branchId": stmt_node.branch_id,
                            "decisionId": stmt_node.decision_id,
                            "depth": stmt_node.depth,
                        },
                    }
                )

            result["statement_nodes"] = react_statement_nodes

            # Create edges from decision nodes to statement nodes
            for stmt_node in self.iter_statement_nodes():
                if stmt_node.decision_id:
                    stmt_edge_id = f"es:{stmt_node.decision_id}->{stmt_node.id}"
                    react_edges.append(
                        {
                            "id": stmt_edge_id,
                            "source": stmt_node.decision_id,
                            "target": stmt_node.id,
                            "type": "smoothstep",
                            "animated": False,
                            "data": {
                                "callSiteLine": stmt_node.line,
                                "callType": "statement",
                                "branchId": stmt_node.branch_id,
                                "decisionId": stmt_node.decision_id,
                            },
                        }
                    )

        # Include external call nodes if present
        if self.external_call_nodes:
            react_external_call_nodes = []
            for ext_node in self.iter_external_call_nodes():
                depth = ext_node.depth
                y_index = depth_counts.get(depth, 0)
                depth_counts[depth] = y_index + 1

                react_external_call_nodes.append(
                    {
                        "id": ext_node.id,
                        "type": "externalCallNode",
                        "position": {
                            "x": depth * 350 + 175,
                            "y": y_index * 140,
                        },
                        "data": {
                            "label": ext_node.expression,
                            "expression": ext_node.expression,
                            "callType": ext_node.call_type.value,
                            "moduleHint": ext_node.module_hint,
                            "filePath": (
                                str(ext_node.file_path)
                                if ext_node.file_path
                                else None
                            ),
                            "line": ext_node.line,
                            "column": ext_node.column,
                            "parentCallId": ext_node.parent_call_id,
                            "branchId": ext_node.branch_id,
                            "decisionId": ext_node.decision_id,
                            "depth": ext_node.depth,
                        },
                    }
                )

            result["external_call_nodes"] = react_external_call_nodes

            # Create edges from decision nodes to external call nodes
            for ext_node in self.iter_external_call_nodes():
                if ext_node.decision_id:
                    ext_edge_id = f"ex:{ext_node.decision_id}->{ext_node.id}"
                    react_edges.append(
                        {
                            "id": ext_edge_id,
                            "source": ext_node.decision_id,
                            "target": ext_node.id,
                            "type": "smoothstep",
                            "animated": False,
                            "data": {
                                "callSiteLine": ext_node.line,
                                "callType": "external",
                                "branchId": ext_node.branch_id,
                                "decisionId": ext_node.decision_id,
                            },
                        }
                    )

        return result
