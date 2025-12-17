# SPDX-License-Identifier: MIT
"""
Backward compatibility wrapper for CrossFileCallGraphExtractor.

DEPRECATED: This module provides a compatibility layer for code using the
old CrossFileCallGraphExtractor from call_tracer_v2.py. Use the new
PythonCallFlowExtractor instead.

Migration:
    # Old API
    extractor = CrossFileCallGraphExtractor(project_root, use_cache=True)
    extractor.analyze_file(filepath, recursive=True)
    chain = extractor.trace_chain_cross_file("file.py::func", max_depth=10)
    entry_points = extractor.find_entry_points()
    export = extractor.export_to_dict()

    # New API
    extractor = PythonCallFlowExtractor(root_path=project_root)
    graph = extractor.extract(filepath, function_name, max_depth=5)
    # CallGraph provides nodes, edges, entry_point, max_depth_reached
"""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from ..languages import PythonCallFlowExtractor
from ..models import CallGraph


class CrossFileCallGraphExtractor:
    """
    DEPRECATED: Backward compatibility wrapper for CrossFileCallGraphExtractor.

    This class wraps the new PythonCallFlowExtractor to provide the old API.
    All methods emit deprecation warnings.

    Use PythonCallFlowExtractor directly for new code:
        from code_map.graph_analysis.call_flow import PythonCallFlowExtractor

    Attributes:
        project_root: Project root path
        call_graph: Dict mapping qualified names to list of callees
        analyzed_files: Set of files that have been analyzed
        instance_attrs: Dict tracking instance attribute types
    """

    def __init__(self, project_root: Path, use_cache: bool = True):
        """
        Initialize the deprecated extractor.

        Args:
            project_root: Root path of the project
            use_cache: Ignored (kept for API compatibility)

        Warns:
            DeprecationWarning: Always emitted on instantiation
        """
        warnings.warn(
            "CrossFileCallGraphExtractor is deprecated and will be removed in a future release. "
            "Use PythonCallFlowExtractor from code_map.graph_analysis.call_flow.languages instead. "
            "See the migration guide in the module docstring.",
            DeprecationWarning,
            stacklevel=2,
        )

        self.project_root = Path(project_root).resolve()
        self._extractor = PythonCallFlowExtractor(root_path=self.project_root)

        # Legacy API attributes
        self.call_graph: Dict[str, List[str]] = {}
        self.analyzed_files: Set[Path] = set()
        self.instance_attrs: Dict[Path, Dict[str, Dict[str, str]]] = {}
        self.use_cache = use_cache

        # Store extracted graphs for chain tracing
        self._graphs: Dict[str, CallGraph] = {}

    def _get_qualified_name(self, filepath: Path, function_name: str) -> str:
        """Generate qualified name for a function (legacy format)."""
        try:
            relative = filepath.relative_to(self.project_root)
        except ValueError:
            relative = filepath
        return f"{relative}::{function_name}"

    def analyze_file(
        self, filepath: Path, recursive: bool = True
    ) -> Dict[str, List[Tuple[str, bool, Optional[str]]]]:
        """
        DEPRECATED: Analyze a file and optionally its dependencies.

        This method provides backward compatibility but uses the new
        extractor internally. Results are approximate as the new API
        has a different data model.

        Args:
            filepath: File to analyze
            recursive: If True, analyze imported files (affects max_depth)

        Returns:
            Local call graph in legacy format (simplified)

        Warns:
            DeprecationWarning: Always emitted
        """
        warnings.warn(
            "analyze_file() is deprecated. Use PythonCallFlowExtractor.extract() instead.",
            DeprecationWarning,
            stacklevel=2,
        )

        filepath = Path(filepath).resolve()
        self.analyzed_files.add(filepath)

        # Get entry points to analyze
        entry_points = self._extractor.list_entry_points(filepath)
        local_graph: Dict[str, List[Tuple[str, bool, Optional[str]]]] = {}

        max_depth = 5 if recursive else 1

        for entry in entry_points:
            func_name = entry.get("qualified_name", entry.get("name", ""))
            if not func_name:
                continue

            # Extract call graph for this entry point
            graph = self._extractor.extract(
                filepath, func_name, max_depth=max_depth, project_root=self.project_root
            )

            if graph:
                qualified_name = self._get_qualified_name(filepath, func_name)
                self._graphs[qualified_name] = graph

                # Convert to legacy format
                callees: List[Tuple[str, bool, Optional[str]]] = []
                entry_node_id = graph.entry_point
                if entry_node_id and entry_node_id in graph.nodes:
                    # Find direct callees from edges
                    for edge in graph.edges.values():
                        if edge.caller_id == entry_node_id:
                            callee_node = graph.nodes.get(edge.callee_id)
                            if callee_node:
                                callee_name = callee_node.name
                                # Legacy format: (name, is_instance_method, instance_attr)
                                callees.append((callee_name, False, None))

                local_graph[func_name] = callees

                # Update global call graph
                qualified_callees = [c[0] for c in callees]
                self.call_graph[qualified_name] = qualified_callees

        return local_graph

    def trace_chain_cross_file(
        self, start_function: str, max_depth: int = 10
    ) -> List[Tuple[int, str, List[str]]]:
        """
        DEPRECATED: Trace call chain across files.

        Args:
            start_function: Qualified function name ("file.py::function")
            max_depth: Maximum depth to trace

        Returns:
            List of (depth, qualified_name, callees)

        Warns:
            DeprecationWarning: Always emitted
        """
        warnings.warn(
            "trace_chain_cross_file() is deprecated. "
            "Use PythonCallFlowExtractor.extract() which returns a complete CallGraph.",
            DeprecationWarning,
            stacklevel=2,
        )

        chain: List[Tuple[int, str, List[str]]] = []
        visited: Set[str] = set()

        def dfs(func: str, depth: int = 0):
            if depth > max_depth or func in visited:
                return

            visited.add(func)
            callees = self.call_graph.get(func, [])
            chain.append((depth, func, callees.copy()))

            for callee in callees:
                dfs(callee, depth + 1)

        dfs(start_function)
        return chain

    def find_entry_points(self) -> List[str]:
        """
        DEPRECATED: Find functions that are not called by anyone.

        Returns:
            List of qualified names of entry points

        Warns:
            DeprecationWarning: Always emitted
        """
        warnings.warn(
            "find_entry_points() is deprecated. "
            "Use PythonCallFlowExtractor.list_entry_points() instead.",
            DeprecationWarning,
            stacklevel=2,
        )

        all_callees: Set[str] = set()
        for callees in self.call_graph.values():
            all_callees.update(callees)

        entry_points = set(self.call_graph.keys()) - all_callees
        return list(entry_points)

    def export_to_dict(self) -> Dict[str, Any]:
        """
        DEPRECATED: Export call graph to a serializable dictionary.

        Returns:
            Dict with call graph structure

        Warns:
            DeprecationWarning: Always emitted
        """
        warnings.warn(
            "export_to_dict() is deprecated. "
            "CallGraph dataclass can be serialized with dataclasses.asdict().",
            DeprecationWarning,
            stacklevel=2,
        )

        return {
            "call_graph": self.call_graph,
            "entry_points": self.find_entry_points(),
            "total_functions": len(self.call_graph),
            "analyzed_files": [
                str(f.relative_to(self.project_root)) for f in self.analyzed_files
            ],
        }
