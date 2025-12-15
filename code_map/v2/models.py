# SPDX-License-Identifier: MIT
"""
Data models for AEGIS v2 composition root extraction.

These models represent the runtime instance graph extracted from
composition roots (main functions, factories, DI containers).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Set


class CreationPattern(str, Enum):
    """How an instance was created."""

    FACTORY = "factory"  # createFoo() or FooFactory.create()
    MAKE_UNIQUE = "make_unique"  # std::make_unique<T>()
    MAKE_SHARED = "make_shared"  # std::make_shared<T>()
    DIRECT = "direct"  # T obj; or T obj(args);
    NEW = "new"  # new T()
    UNKNOWN = "unknown"


class LifecycleMethod(str, Enum):
    """Known lifecycle method types."""

    START = "start"
    STOP = "stop"
    INIT = "init"
    SHUTDOWN = "shutdown"
    CONNECT = "connect"
    DISCONNECT = "disconnect"


class InstanceRole(str, Enum):
    """
    Role of an instance in the data flow graph.

    Determined by analyzing wiring patterns:
    - SOURCE: No incoming edges (data producers)
    - PROCESSING: Has both incoming and outgoing edges (transformers)
    - SINK: No outgoing edges (data consumers)
    - UNKNOWN: Role not yet determined
    """

    SOURCE = "source"
    PROCESSING = "processing"
    SINK = "sink"
    UNKNOWN = "unknown"


@dataclass(slots=True)
class Location:
    """
    Precise source code location.

    Attributes:
        file_path: Absolute path to the source file
        line: Line number (1-indexed)
        column: Column number (0-indexed, optional)
        end_line: End line for multi-line constructs (optional)
        end_column: End column (optional)
    """

    file_path: Path
    line: int
    column: int = 0
    end_line: Optional[int] = None
    end_column: Optional[int] = None

    def __str__(self) -> str:
        return f"{self.file_path}:{self.line}"

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "file_path": str(self.file_path),
            "line": self.line,
            "column": self.column,
            "end_line": self.end_line,
            "end_column": self.end_column,
        }


@dataclass(slots=True)
class InstanceInfo:
    """
    Information about a component instance in the composition root.

    Represents a variable holding a long-lived component that participates
    in the application's runtime graph.

    Attributes:
        name: Variable name (e.g., "m1", "generator")
        type_name: Declared type (e.g., "IModule", "auto")
        actual_type: Resolved concrete type (e.g., "GeneratorModule")
        location: Where the variable is declared
        creation_pattern: How the instance was created
        factory_name: Name of factory function if applicable
        constructor_args: Arguments passed to constructor/factory
        is_pointer: True if unique_ptr/shared_ptr/raw pointer
        pointer_type: "unique_ptr", "shared_ptr", "raw", or None
    """

    name: str
    type_name: str
    location: Location
    creation_pattern: CreationPattern = CreationPattern.UNKNOWN
    actual_type: Optional[str] = None
    factory_name: Optional[str] = None
    constructor_args: List[str] = field(default_factory=list)
    is_pointer: bool = False
    pointer_type: Optional[str] = None

    def __str__(self) -> str:
        type_str = self.actual_type or self.type_name
        return f"{self.name}: {type_str}"


@dataclass(slots=True)
class WiringInfo:
    """
    Connection between two component instances.

    Represents a method call that establishes a relationship between
    components (e.g., setNext, connect, addListener).

    Attributes:
        source: Name of the calling instance
        target: Name of the instance being passed as argument
        method: Method name used for wiring (e.g., "setNext", "connect")
        location: Where the wiring call occurs
        wiring_type: Semantic type ("chain", "observer", "dependency")
    """

    source: str
    target: str
    method: str
    location: Location
    wiring_type: Optional[str] = None

    def __str__(self) -> str:
        return f"{self.source} --[{self.method}]--> {self.target}"


@dataclass(slots=True)
class LifecycleCall:
    """
    Lifecycle method invocation on an instance.

    Tracks start/stop/init calls to understand component lifecycle order.

    Attributes:
        instance: Name of the instance being called
        method: Method name (start, stop, init, etc.)
        location: Where the call occurs
        order: Sequence number within the composition root
    """

    instance: str
    method: LifecycleMethod
    location: Location
    order: int = 0

    def __str__(self) -> str:
        return f"{self.instance}.{self.method.value}()"


# -----------------------------------------------------------------------------
# Graph Model Structures (Phase 2)
# -----------------------------------------------------------------------------


@dataclass(slots=True)
class InstanceNode:
    """
    A node in the instance graph representing a runtime component.

    This is the graph-oriented representation of an instance, with a unique ID
    for graph operations and additional metadata for visualization.

    Attributes:
        id: Unique identifier (UUID string)
        name: Variable name from source code
        type_symbol: Resolved type symbol (qualified name)
        role: Role in data flow (SOURCE, PROCESSING, SINK)
        location: Where the instance is declared
        args: Constructor/factory arguments
        config: Additional configuration data
        type_location: Location of the type definition (if resolved)
        contract: Contract information from type analysis (methods, signals)
    """

    id: str
    name: str
    type_symbol: str
    role: InstanceRole
    location: Location
    args: List[str] = field(default_factory=list)
    config: Dict[str, Any] = field(default_factory=dict)
    type_location: Optional[Location] = None
    contract: Optional[Dict[str, Any]] = None

    def __str__(self) -> str:
        return f"Node({self.name}: {self.type_symbol}, role={self.role.value})"

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for JSON/API responses."""
        return {
            "id": self.id,
            "name": self.name,
            "type_symbol": self.type_symbol,
            "role": self.role.value,
            "location": self.location.to_dict(),
            "args": self.args,
            "config": self.config,
            "type_location": self.type_location.to_dict() if self.type_location else None,
            "contract": self.contract,
        }


@dataclass(slots=True)
class WiringEdge:
    """
    An edge in the instance graph representing a connection between components.

    This is the graph-oriented representation of wiring, with unique IDs
    for both the edge and its endpoints.

    Attributes:
        id: Unique identifier (UUID string)
        source_id: ID of the source node
        target_id: ID of the target node
        method: Method name used for wiring (e.g., "setNext", "connect")
        location: Where the wiring call occurs in source
        channel: Communication channel/port name (if applicable)
        metadata: Additional edge metadata (wiring_type, etc.)
    """

    id: str
    source_id: str
    target_id: str
    method: str
    location: Location
    channel: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __str__(self) -> str:
        channel_str = f"[{self.channel}]" if self.channel else ""
        return f"Edge({self.source_id} --{self.method}{channel_str}--> {self.target_id})"

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for JSON/API responses."""
        return {
            "id": self.id,
            "source_id": self.source_id,
            "target_id": self.target_id,
            "method": self.method,
            "location": self.location.to_dict(),
            "channel": self.channel,
            "metadata": self.metadata,
        }


@dataclass
class InstanceGraph:
    """
    A directed graph of component instances and their connections.

    This is the primary output of Phase 2, converting the flat lists from
    CompositionRoot into a proper graph structure with efficient lookups
    and graph algorithms.

    Attributes:
        nodes: Dictionary mapping node ID to InstanceNode
        edges: Dictionary mapping edge ID to WiringEdge
        name_to_id: Index mapping instance name to node ID
        outgoing: Adjacency list for outgoing edges (node_id -> [edge_id])
        incoming: Adjacency list for incoming edges (node_id -> [edge_id])
        source_file: Path to the source file
        function_name: Name of the composition root function
    """

    nodes: Dict[str, InstanceNode] = field(default_factory=dict)
    edges: Dict[str, WiringEdge] = field(default_factory=dict)
    name_to_id: Dict[str, str] = field(default_factory=dict)
    outgoing: Dict[str, List[str]] = field(default_factory=dict)
    incoming: Dict[str, List[str]] = field(default_factory=dict)
    source_file: Optional[Path] = None
    function_name: Optional[str] = None

    def add_node(self, node: InstanceNode) -> None:
        """Add a node to the graph."""
        self.nodes[node.id] = node
        self.name_to_id[node.name] = node.id
        if node.id not in self.outgoing:
            self.outgoing[node.id] = []
        if node.id not in self.incoming:
            self.incoming[node.id] = []

    def add_edge(self, edge: WiringEdge) -> None:
        """Add an edge to the graph."""
        self.edges[edge.id] = edge
        if edge.source_id not in self.outgoing:
            self.outgoing[edge.source_id] = []
        if edge.target_id not in self.incoming:
            self.incoming[edge.target_id] = []
        self.outgoing[edge.source_id].append(edge.id)
        self.incoming[edge.target_id].append(edge.id)

    def get_node(self, node_id: str) -> Optional[InstanceNode]:
        """Get a node by its ID."""
        return self.nodes.get(node_id)

    def get_node_by_name(self, name: str) -> Optional[InstanceNode]:
        """Get a node by instance name."""
        node_id = self.name_to_id.get(name)
        if node_id is None:
            return None
        return self.nodes.get(node_id)

    def get_edge(self, edge_id: str) -> Optional[WiringEdge]:
        """Get an edge by its ID."""
        return self.edges.get(edge_id)

    def get_outgoing_edges(self, node_id: str) -> List[WiringEdge]:
        """Get all outgoing edges from a node."""
        edge_ids = self.outgoing.get(node_id, [])
        return [self.edges[eid] for eid in edge_ids if eid in self.edges]

    def get_incoming_edges(self, node_id: str) -> List[WiringEdge]:
        """Get all incoming edges to a node."""
        edge_ids = self.incoming.get(node_id, [])
        return [self.edges[eid] for eid in edge_ids if eid in self.edges]

    def get_connected_nodes(self, node_id: str) -> List[InstanceNode]:
        """
        Get all nodes directly connected to a given node.

        Returns both upstream (sources) and downstream (targets) nodes.

        Args:
            node_id: UUID of the node

        Returns:
            List of connected nodes (deduplicated)
        """
        connected_ids: Set[str] = set()

        # Add targets of outgoing edges
        for edge in self.get_outgoing_edges(node_id):
            connected_ids.add(edge.target_id)

        # Add sources of incoming edges
        for edge in self.get_incoming_edges(node_id):
            connected_ids.add(edge.source_id)

        return [self.nodes[nid] for nid in connected_ids if nid in self.nodes]

    def find_sources(self) -> List[InstanceNode]:
        """Find all source nodes (no incoming edges)."""
        return [
            node for node in self.nodes.values()
            if not self.incoming.get(node.id, [])
        ]

    def find_sinks(self) -> List[InstanceNode]:
        """Find all sink nodes (no outgoing edges)."""
        return [
            node for node in self.nodes.values()
            if not self.outgoing.get(node.id, [])
        ]

    def find_isolated(self) -> List[InstanceNode]:
        """
        Find all isolated nodes (no edges at all).

        Isolated nodes may indicate:
        - Components not yet wired
        - Utility objects
        - Configuration holders

        Returns:
            List of nodes with no edges
        """
        return [
            node for node in self.nodes.values()
            if not self.incoming.get(node.id, [])
            and not self.outgoing.get(node.id, [])
        ]

    def topological_sort(self) -> List[InstanceNode]:
        """
        Return nodes in topological order (sources first, sinks last).

        Uses Kahn's algorithm for topological sorting.
        Returns empty list if the graph has cycles.
        """
        # Calculate in-degrees
        in_degree: Dict[str, int] = {
            node_id: len(self.incoming.get(node_id, []))
            for node_id in self.nodes
        }

        # Start with nodes that have no incoming edges
        queue: List[str] = [
            node_id for node_id, degree in in_degree.items() if degree == 0
        ]
        result: List[InstanceNode] = []

        while queue:
            node_id = queue.pop(0)
            node = self.nodes.get(node_id)
            if node:
                result.append(node)

            # Reduce in-degree for all neighbors
            for edge_id in self.outgoing.get(node_id, []):
                edge = self.edges.get(edge_id)
                if edge:
                    in_degree[edge.target_id] -= 1
                    if in_degree[edge.target_id] == 0:
                        queue.append(edge.target_id)

        # If we didn't process all nodes, there's a cycle
        if len(result) != len(self.nodes):
            return []

        return result

    def iter_nodes(self) -> Iterator[InstanceNode]:
        """Iterate over all nodes."""
        return iter(self.nodes.values())

    def iter_edges(self) -> Iterator[WiringEdge]:
        """Iterate over all edges."""
        return iter(self.edges.values())

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for JSON/API responses."""
        return {
            "nodes": [node.to_dict() for node in self.nodes.values()],
            "edges": [edge.to_dict() for edge in self.edges.values()],
            "source_file": str(self.source_file) if self.source_file else None,
            "function_name": self.function_name,
            "stats": {
                "node_count": len(self.nodes),
                "edge_count": len(self.edges),
                "source_count": len(self.find_sources()),
                "sink_count": len(self.find_sinks()),
            },
        }

    def to_react_flow(self) -> Dict[str, Any]:
        """
        Serialize to React Flow format for frontend visualization.

        Returns a dictionary with 'nodes' and 'edges' arrays formatted
        for direct use with React Flow library. Includes enriched data
        for the Phase 4 detail panel.

        Node data includes:
            - label: Instance name
            - type: Type symbol
            - role: Instance role (source, processing, sink)
            - location: Short location string for display
            - args: Constructor/factory arguments
            - config: Configuration data
            - type_location: Full location dict for jump-to-type (if available)
            - creation_location: Full location dict for the instance declaration
            - incoming_connections: List of {from_name, method, location} dicts
            - outgoing_connections: List of {to_name, method, location} dicts

        Edge data includes:
            - source_location: Full location dict for the wiring call
            - source_name: Name of the source instance
            - target_name: Name of the target instance
        """
        rf_nodes = []
        rf_edges = []

        # Build reverse lookup: node_id -> node_name for edge enrichment
        id_to_name: Dict[str, str] = {
            node.id: node.name for node in self.nodes.values()
        }

        # Position nodes in a simple left-to-right layout
        sorted_nodes = self.topological_sort() or list(self.nodes.values())
        x_spacing = 200
        y_spacing = 100

        for i, node in enumerate(sorted_nodes):
            # Build incoming connections list
            incoming_connections: List[Dict[str, Any]] = []
            for edge in self.get_incoming_edges(node.id):
                source_name = id_to_name.get(edge.source_id, "unknown")
                incoming_connections.append({
                    "from_name": source_name,
                    "method": edge.method,
                    "location": edge.location.to_dict(),
                })

            # Build outgoing connections list
            outgoing_connections: List[Dict[str, Any]] = []
            for edge in self.get_outgoing_edges(node.id):
                target_name = id_to_name.get(edge.target_id, "unknown")
                outgoing_connections.append({
                    "to_name": target_name,
                    "method": edge.method,
                    "location": edge.location.to_dict(),
                })

            # Map role to React Flow node type for styling
            rf_type = self._get_react_flow_node_type(node)
            rf_nodes.append({
                "id": node.id,
                "type": rf_type,
                "data": {
                    "label": node.name,
                    "type": node.type_symbol,
                    "role": node.role.value,
                    "location": f"{node.location.file_path.name}:{node.location.line}",
                    "args": node.args,
                    "config": node.config,
                    "type_location": node.type_location.to_dict() if node.type_location else None,
                    "creation_location": node.location.to_dict(),
                    "incoming_connections": incoming_connections,
                    "outgoing_connections": outgoing_connections,
                },
                "position": {"x": i * x_spacing, "y": (i % 2) * y_spacing},
            })

        for edge in self.edges.values():
            source_name = id_to_name.get(edge.source_id, "unknown")
            target_name = id_to_name.get(edge.target_id, "unknown")
            rf_edges.append({
                "id": edge.id,
                "source": edge.source_id,
                "target": edge.target_id,
                "label": edge.method,
                "type": "smoothstep",
                "animated": True,
                "data": {
                    "source_location": edge.location.to_dict(),
                    "source_name": source_name,
                    "target_name": target_name,
                },
            })

        return {"nodes": rf_nodes, "edges": rf_edges}

    def _get_react_flow_node_type(self, node: InstanceNode) -> str:
        """
        Determine React Flow node type based on instance role.

        React Flow uses node types for custom styling/rendering.

        Args:
            node: The InstanceNode

        Returns:
            String identifying the node type for React Flow
        """
        role_to_type = {
            InstanceRole.SOURCE: "input",
            InstanceRole.SINK: "output",
            InstanceRole.PROCESSING: "default",
            InstanceRole.UNKNOWN: "default",
        }
        return role_to_type.get(node.role, "default")

    def __len__(self) -> int:
        """Return the number of nodes in the graph."""
        return len(self.nodes)

    def __contains__(self, node_id: str) -> bool:
        """Check if a node ID exists in the graph."""
        return node_id in self.nodes

    def __iter__(self) -> Iterator[InstanceNode]:
        """Iterate over nodes in topological order (or arbitrary if cyclic)."""
        sorted_nodes = self.topological_sort()
        if sorted_nodes:
            return iter(sorted_nodes)
        return iter(self.nodes.values())


# -----------------------------------------------------------------------------
# Composition Root (Phase 1 output)
# -----------------------------------------------------------------------------


@dataclass
class CompositionRoot:
    """
    A composition root is where components are assembled and wired.

    Typically the main() function, but can be any function that:
    - Instantiates long-lived components
    - Wires them together
    - Manages their lifecycle

    Attributes:
        file_path: Path to the file containing the composition root
        function_name: Name of the function (e.g., "main")
        location: Start location of the function
        instances: List of component instances created
        wiring: List of connections between instances
        lifecycle: Ordered list of lifecycle calls
        metadata: Additional extracted information
    """

    file_path: Path
    function_name: str
    location: Location
    instances: List[InstanceInfo] = field(default_factory=list)
    wiring: List[WiringInfo] = field(default_factory=list)
    lifecycle: List[LifecycleCall] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def get_instance(self, name: str) -> Optional[InstanceInfo]:
        """Get instance by name."""
        for inst in self.instances:
            if inst.name == name:
                return inst
        return None

    def get_wiring_for(self, instance_name: str) -> List[WiringInfo]:
        """Get all wiring where instance is source or target."""
        return [
            w
            for w in self.wiring
            if w.source == instance_name or w.target == instance_name
        ]

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for JSON/API responses."""
        return {
            "file_path": str(self.file_path),
            "function_name": self.function_name,
            "location": {
                "file": str(self.location.file_path),
                "line": self.location.line,
            },
            "instances": [
                {
                    "name": i.name,
                    "type_name": i.type_name,
                    "actual_type": i.actual_type,
                    "location": {"line": i.location.line},
                    "creation_pattern": i.creation_pattern.value,
                    "factory_name": i.factory_name,
                    "constructor_args": i.constructor_args,
                }
                for i in self.instances
            ],
            "wiring": [
                {
                    "source": w.source,
                    "target": w.target,
                    "method": w.method,
                    "location": {"line": w.location.line},
                }
                for w in self.wiring
            ],
            "lifecycle": [
                {
                    "instance": lc.instance,
                    "method": lc.method.value,
                    "order": lc.order,
                }
                for lc in self.lifecycle
            ],
        }
