# SPDX-License-Identifier: MIT
"""
Service layer for Instance Graph management.

Orchestrates extraction, building, persistence, and caching of instance graphs.
Integrates with file watcher for incremental updates.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from .builder import GraphBuilder
from .composition.cpp import CppCompositionExtractor
from .models import InstanceGraph
from .storage import InstanceGraphStore, StoredInstanceGraph

logger = logging.getLogger(__name__)

# File extensions that trigger instance graph invalidation
CPP_EXTENSIONS: Set[str] = {".cpp", ".hpp", ".h", ".cc", ".cxx", ".hxx"}


def _generate_graph_id(project_path: str, source_file: str, function_name: str) -> str:
    """Generate a stable ID for a graph based on its source."""
    content = f"{project_path}:{source_file}:{function_name}"
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def _get_file_mtime(path: Path) -> Optional[datetime]:
    """Get file modification time as datetime, or None if not accessible."""
    try:
        stat = path.stat()
        return datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
    except OSError:
        return None


class InstanceGraphService:
    """
    Manages instance graph lifecycle with caching and persistence.

    Responsibilities:
    - Extract instance graphs from composition roots
    - Cache graphs in memory for fast access
    - Persist graphs to disk for startup optimization
    - Invalidate cache on file changes
    - Provide graph queries

    Example:
        >>> service = InstanceGraphService(Path("/my/project"))
        >>> await service.startup()
        >>> graph = await service.get_graph(Path("src/main.cpp"), "main")
        >>> await service.shutdown()
    """

    def __init__(
        self,
        root: Path,
        cache_dir: Optional[Path] = None,
    ) -> None:
        """
        Initialize the service.

        Args:
            root: Project root directory
            cache_dir: Alternative cache directory (for Docker/read-only mounts)
        """
        self.root = Path(root).expanduser().resolve()
        self.store = InstanceGraphStore(root, cache_dir=cache_dir)
        self.extractor = CppCompositionExtractor()
        # Note: We create a new GraphBuilder per request to resolve types
        # from the correct project directory (not self.root)

        # In-memory cache: graph_id -> (InstanceGraph, source_mtime)
        self._cache: Dict[str, tuple[InstanceGraph, datetime]] = {}

        # Track which files contribute to each graph for invalidation
        # graph_id -> Set[source_file_paths]
        self._file_deps: Dict[str, Set[Path]] = {}

        self._started = False

    async def startup(self) -> None:
        """
        Initialize the service and load persisted graphs.

        Called during application startup to restore cached state.
        """
        if self._started:
            return

        logger.info("InstanceGraphService starting up for %s", self.root)

        # Load persisted graphs into memory cache
        stored_graphs = self.store.load()
        for stored in stored_graphs:
            source_path = self.root / stored.source_file
            current_mtime = _get_file_mtime(source_path)

            # Check if cache is still valid
            if current_mtime and current_mtime <= stored.source_modified_at:
                # Cache is valid, restore graph
                try:
                    graph = InstanceGraph.from_dict(stored.graph_data)
                    self._cache[stored.id] = (graph, stored.source_modified_at)
                    self._file_deps[stored.id] = {source_path}
                    logger.debug(
                        "Restored graph %s from cache (source: %s)",
                        stored.id,
                        stored.source_file,
                    )
                except (KeyError, TypeError, ValueError) as e:
                    logger.warning(
                        "Failed to restore graph %s: %s",
                        stored.id,
                        e,
                    )
            else:
                logger.debug(
                    "Graph %s cache invalid (source modified)",
                    stored.id,
                )

        logger.info(
            "InstanceGraphService started with %d cached graphs",
            len(self._cache),
        )
        self._started = True

    async def shutdown(self) -> None:
        """
        Persist current state and cleanup.

        Called during application shutdown to save cached graphs.
        """
        if not self._started:
            return

        logger.info("InstanceGraphService shutting down")

        # Persist all cached graphs
        await self._persist_all()

        self._cache.clear()
        self._file_deps.clear()
        self._started = False

        logger.info("InstanceGraphService shutdown complete")

    async def get_graph(
        self,
        source_file: Path,
        function_name: str = "main",
        *,
        force_refresh: bool = False,
    ) -> Optional[InstanceGraph]:
        """
        Get the instance graph for a composition root.

        Returns cached graph if valid, otherwise extracts and builds fresh.

        Args:
            source_file: Path to composition root file (absolute or relative to root)
            function_name: Name of the composition root function
            force_refresh: If True, bypass cache and re-extract

        Returns:
            InstanceGraph if extraction successful, None otherwise
        """
        # Normalize path
        if not source_file.is_absolute():
            source_file = self.root / source_file
        source_file = source_file.resolve()

        # Generate graph ID
        try:
            rel_path = source_file.relative_to(self.root)
        except ValueError:
            rel_path = source_file
        graph_id = _generate_graph_id(
            str(self.root),
            str(rel_path),
            function_name,
        )

        # Check cache validity
        if not force_refresh and graph_id in self._cache:
            cached_graph, cached_mtime = self._cache[graph_id]
            current_mtime = _get_file_mtime(source_file)
            if current_mtime and current_mtime <= cached_mtime:
                logger.debug("Cache hit for graph %s", graph_id)
                return cached_graph
            else:
                logger.debug("Cache stale for graph %s", graph_id)

        # Extract and build fresh graph
        logger.info("Extracting graph from %s::%s", source_file, function_name)

        if not self.extractor.is_available():
            logger.warning("C++ extractor not available (tree-sitter not installed)")
            return None

        if not source_file.exists():
            logger.warning("Source file not found: %s", source_file)
            return None

        try:
            # Phase 1: Extract composition root
            logger.info("[DEBUG] Phase 1: Extracting composition root from %s", source_file)
            composition_root = self.extractor.extract(source_file, function_name)
            if composition_root is None:
                logger.warning(
                    "No composition root found in %s::%s",
                    source_file,
                    function_name,
                )
                return None

            logger.info("[DEBUG] Phase 1 complete: Found %d instances, %d wiring",
                        len(composition_root.instances), len(composition_root.wiring))
            for inst in composition_root.instances:
                logger.info("[DEBUG]   Instance: name=%s, type=%s, actual_type=%s, factory=%s",
                            inst.name, inst.type_name, inst.actual_type, inst.factory_name)

            # Phase 2: Build graph with type resolution from project directory
            # Use the source file's directory as project root for type lookup
            project_dir = source_file.parent
            logger.info("[DEBUG] Phase 2: Building graph with project_dir=%s", project_dir)
            builder = GraphBuilder(project_root=project_dir)
            graph = builder.build(composition_root)

            # Log resulting type_locations
            for node in graph.iter_nodes():
                logger.info("[DEBUG] Node '%s' (type=%s): type_location=%s",
                            node.name, node.type_symbol, node.type_location)

            # Update cache
            current_mtime = _get_file_mtime(source_file)
            if current_mtime:
                self._cache[graph_id] = (graph, current_mtime)
                self._file_deps[graph_id] = {source_file}

            logger.info(
                "Built graph with %d nodes, %d edges",
                len(graph.nodes),
                len(graph.edges),
            )
            return graph

        except Exception as e:
            logger.error("Failed to extract graph from %s: %s", source_file, e)
            return None

    async def invalidate_for_file(self, file_path: Path) -> List[str]:
        """
        Invalidate cached graphs affected by a file change.

        Args:
            file_path: Path to the changed file

        Returns:
            List of invalidated graph IDs
        """
        file_path = file_path.resolve()
        invalidated: List[str] = []

        # Check if this is a C++ file
        if file_path.suffix.lower() not in CPP_EXTENSIONS:
            return invalidated

        # Find graphs that depend on this file
        for graph_id, deps in list(self._file_deps.items()):
            if file_path in deps:
                # Remove from cache
                if graph_id in self._cache:
                    del self._cache[graph_id]
                    invalidated.append(graph_id)
                    logger.debug(
                        "Invalidated graph %s due to change in %s",
                        graph_id,
                        file_path,
                    )

        return invalidated

    async def handle_file_changes(self, changed_files: List[Path]) -> Dict[str, Any]:
        """
        Process file changes from the watcher.

        Invalidates affected graphs and optionally re-extracts.

        Args:
            changed_files: List of changed file paths

        Returns:
            Summary of changes: {invalidated: [...], refreshed: [...]}
        """
        invalidated: List[str] = []
        refreshed: List[str] = []

        for file_path in changed_files:
            invalidated.extend(await self.invalidate_for_file(file_path))

        # For now, we don't auto-refresh - let the next get_graph() do it
        # This avoids unnecessary work if the graph isn't needed

        return {
            "invalidated": invalidated,
            "refreshed": refreshed,
            "cpp_files_changed": len([
                f for f in changed_files
                if f.suffix.lower() in CPP_EXTENSIONS
            ]),
        }

    def list_graphs(self) -> List[Dict[str, Any]]:
        """
        List all known graphs with metadata.

        Returns:
            List of graph summaries with id, source_file, stats
        """
        result: List[Dict[str, Any]] = []

        for graph_id, (graph, mtime) in self._cache.items():
            result.append({
                "id": graph_id,
                "source_file": str(graph.source_file) if graph.source_file else None,
                "function_name": graph.function_name,
                "node_count": len(graph.nodes),
                "edge_count": len(graph.edges),
                "cached_at": mtime.isoformat(),
            })

        return result

    def get_cached_graph(self, graph_id: str) -> Optional[InstanceGraph]:
        """
        Get a graph by ID from cache only (no extraction).

        Args:
            graph_id: The graph identifier

        Returns:
            Cached InstanceGraph or None
        """
        if graph_id in self._cache:
            return self._cache[graph_id][0]
        return None

    async def _persist_all(self) -> None:
        """Persist all cached graphs to disk."""
        stored_graphs: List[StoredInstanceGraph] = []

        for graph_id, (graph, mtime) in self._cache.items():
            try:
                rel_path = (
                    graph.source_file.relative_to(self.root)
                    if graph.source_file
                    else Path("unknown")
                )
            except ValueError:
                rel_path = graph.source_file or Path("unknown")

            stored = StoredInstanceGraph(
                id=graph_id,
                project_path=str(self.root),
                source_file=str(rel_path),
                function_name=graph.function_name or "main",
                analyzed_at=datetime.now(timezone.utc),
                source_modified_at=mtime,
                node_count=len(graph.nodes),
                edge_count=len(graph.edges),
                graph_data=graph.to_dict(),
            )
            stored_graphs.append(stored)

        if stored_graphs:
            self.store.save(stored_graphs)
            logger.info("Persisted %d graphs to disk", len(stored_graphs))
