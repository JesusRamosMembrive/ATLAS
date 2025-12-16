# SPDX-License-Identifier: MIT
"""
Graph builder for converting CompositionRoot to InstanceGraph.

This module implements Phase 2 of the AEGIS v2 architecture:
- Converts Phase 1 output (CompositionRoot) to graph model (InstanceGraph)
- Generates UUIDs for nodes and edges
- Builds index maps for efficient lookups
- Infers roles based on graph topology
- Resolves type locations for jump-to-definition
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Dict, Optional, Set
from uuid import uuid4

from .models import (
    CompositionRoot,
    InstanceGraph,
    InstanceInfo,
    InstanceNode,
    InstanceRole,
    Location,
    WiringEdge,
    WiringInfo,
)

logger = logging.getLogger(__name__)

# C++ header extensions to search for type definitions
HEADER_EXTENSIONS: Set[str] = {".h", ".hpp", ".hxx", ".hh"}

# Patterns to match class/struct definitions
CLASS_PATTERN = re.compile(r"^\s*(?:class|struct)\s+(\w+)", re.MULTILINE)


class TypeLocationResolver:
    """
    Resolves type names to their definition locations.

    Searches through project header files to find class/struct definitions.
    Uses simple regex matching for performance (no tree-sitter dependency).
    """

    def __init__(self, project_root: Path) -> None:
        """
        Initialize the resolver.

        Args:
            project_root: Root directory of the C++ project
        """
        self.project_root = project_root
        # Cache: type_name -> Location
        self._cache: Dict[str, Optional[Location]] = {}
        # Index: type_name -> file_path (built on first use)
        self._type_index: Optional[Dict[str, Path]] = None

    def resolve(self, type_name: str) -> Optional[Location]:
        """
        Find the definition location for a type.

        Args:
            type_name: Name of the class/struct (e.g., "GeneratorModule")

        Returns:
            Location of the type definition, or None if not found
        """
        logger.info("[DEBUG] TypeLocationResolver.resolve('%s') called", type_name)

        # Check cache first
        if type_name in self._cache:
            cached = self._cache[type_name]
            logger.info("[DEBUG] Cache hit for '%s': %s", type_name, cached)
            return cached

        # Build index if not yet done
        if self._type_index is None:
            self._build_index()

        # Look up in index
        file_path = self._type_index.get(type_name)
        logger.info("[DEBUG] Type index lookup '%s' -> %s", type_name, file_path)
        if file_path is None:
            self._cache[type_name] = None
            return None

        # Find exact line number
        location = self._find_definition_line(file_path, type_name)
        logger.info("[DEBUG] _find_definition_line('%s', '%s') -> %s", file_path, type_name, location)
        self._cache[type_name] = location
        return location

    def _build_index(self) -> None:
        """Build an index of type names to files."""
        self._type_index = {}

        # Find all header files
        for ext in HEADER_EXTENSIONS:
            for header_file in self.project_root.rglob(f"*{ext}"):
                # Skip build directories and hidden folders
                if any(
                    part.startswith(".") or part in ("build", "cmake-build", "out")
                    for part in header_file.parts
                ):
                    continue

                try:
                    content = header_file.read_text(encoding="utf-8", errors="ignore")
                    for match in CLASS_PATTERN.finditer(content):
                        type_name = match.group(1)
                        # Don't overwrite existing entries (prefer first found)
                        if type_name not in self._type_index:
                            self._type_index[type_name] = header_file
                except OSError:
                    # Skip files we can't read
                    pass

        logger.debug(
            "Built type index with %d entries from %s",
            len(self._type_index),
            self.project_root,
        )

    def _find_definition_line(
        self,
        file_path: Path,
        type_name: str,
    ) -> Optional[Location]:
        """Find the line number of a type definition in a file."""
        try:
            lines = file_path.read_text(encoding="utf-8", errors="ignore").splitlines()
            pattern = re.compile(rf"^\s*(?:class|struct)\s+{re.escape(type_name)}\b")

            for i, line in enumerate(lines, start=1):
                if pattern.match(line):
                    return Location(
                        file_path=file_path.resolve(),
                        line=i,
                        column=0,
                    )
        except OSError:
            pass

        return None


class GraphBuilder:
    """
    Builds an InstanceGraph from a CompositionRoot.

    The builder:
    1. Creates InstanceNode for each InstanceInfo (with UUID)
    2. Creates WiringEdge for each WiringInfo (with UUID)
    3. Builds adjacency lists for graph traversal
    4. Infers roles based on edge connectivity:
       - SOURCE: No incoming edges (generates data)
       - SINK: No outgoing edges (consumes data)
       - PROCESSING: Both incoming and outgoing edges
       - UNKNOWN: No edges (isolated node)
    5. Resolves type_location for jump-to-definition support
    """

    def __init__(self, project_root: Optional[Path] = None) -> None:
        """
        Initialize the builder.

        Args:
            project_root: Root directory for type resolution. If None,
                         type_location will not be resolved.
        """
        self._type_resolver: Optional[TypeLocationResolver] = None
        if project_root:
            self._type_resolver = TypeLocationResolver(project_root)

    def build(self, composition_root: CompositionRoot) -> InstanceGraph:
        """
        Convert a CompositionRoot to an InstanceGraph.

        Args:
            composition_root: Phase 1 output with instances and wiring

        Returns:
            InstanceGraph with nodes, edges, indexes, and inferred roles
        """
        graph = InstanceGraph(
            source_file=composition_root.file_path,
            function_name=composition_root.function_name,
        )

        # Step 1: Create nodes with temporary UNKNOWN role
        name_to_id: Dict[str, str] = {}
        for instance in composition_root.instances:
            node = self._create_node(instance)
            graph.add_node(node)
            name_to_id[instance.name] = node.id

        # Step 2: Create edges
        for wiring in composition_root.wiring:
            edge = self._create_edge(wiring, name_to_id)
            if edge is not None:
                graph.add_edge(edge)

        # Step 3: Infer roles based on connectivity
        self._infer_roles(graph)

        return graph

    def _create_node(self, instance: InstanceInfo) -> InstanceNode:
        """Create a graph node from instance info."""
        logger.info("[DEBUG] _create_node() for instance '%s'", instance.name)

        # Determine the type symbol - prefer actual_type if available
        type_symbol = instance.actual_type or instance.type_name
        logger.info("[DEBUG]   actual_type=%s, type_name=%s -> type_symbol=%s",
                    instance.actual_type, instance.type_name, type_symbol)

        # If we have a factory name, we can infer the type from it
        # e.g., createGeneratorModule -> GeneratorModule
        if instance.factory_name and type_symbol == "auto":
            # Try to extract type from factory name
            factory = instance.factory_name
            if factory.startswith("create"):
                type_symbol = factory[6:]  # Remove "create" prefix
            elif factory.startswith("make"):
                type_symbol = factory[4:]  # Remove "make" prefix
            logger.info("[DEBUG]   Inferred type_symbol from factory '%s' -> '%s'",
                        instance.factory_name, type_symbol)

        # Resolve type location for jump-to-definition
        type_location: Optional[Location] = None
        if self._type_resolver and type_symbol and type_symbol != "auto":
            logger.info("[DEBUG]   Resolving type_location for '%s'...", type_symbol)
            type_location = self._type_resolver.resolve(type_symbol)
            logger.info("[DEBUG]   type_location resolved: %s", type_location)
        else:
            logger.info("[DEBUG]   Skipping type resolution (resolver=%s, type_symbol=%s)",
                        self._type_resolver is not None, type_symbol)

        return InstanceNode(
            id=str(uuid4()),
            name=instance.name,
            type_symbol=type_symbol,
            role=InstanceRole.UNKNOWN,  # Will be inferred later
            location=instance.location,
            type_location=type_location,
            args=instance.constructor_args,
            config={
                "creation_pattern": instance.creation_pattern.value,
                "factory_name": instance.factory_name,
                "is_pointer": instance.is_pointer,
                "pointer_type": instance.pointer_type,
            },
        )

    def _create_edge(
        self,
        wiring: WiringInfo,
        name_to_id: Dict[str, str],
    ) -> WiringEdge | None:
        """Create a graph edge from wiring info."""
        source_id = name_to_id.get(wiring.source)
        target_id = name_to_id.get(wiring.target)

        if source_id is None or target_id is None:
            # One of the endpoints doesn't exist in the graph
            return None

        return WiringEdge(
            id=str(uuid4()),
            source_id=source_id,
            target_id=target_id,
            method=wiring.method,
            location=wiring.location,
            metadata={
                "wiring_type": wiring.wiring_type,
            } if wiring.wiring_type else {},
        )

    def _infer_roles(self, graph: InstanceGraph) -> None:
        """
        Infer node roles based on edge connectivity.

        Role inference rules:
        - No incoming edges, has outgoing -> SOURCE (data producer)
        - Has incoming edges, no outgoing -> SINK (data consumer)
        - Has both incoming and outgoing -> PROCESSING (transformer)
        - No edges at all -> UNKNOWN (isolated)
        """
        for node in graph.iter_nodes():
            has_incoming = len(graph.incoming.get(node.id, [])) > 0
            has_outgoing = len(graph.outgoing.get(node.id, [])) > 0

            if has_incoming and has_outgoing:
                node.role = InstanceRole.PROCESSING
            elif has_outgoing and not has_incoming:
                node.role = InstanceRole.SOURCE
            elif has_incoming and not has_outgoing:
                node.role = InstanceRole.SINK
            else:
                node.role = InstanceRole.UNKNOWN
