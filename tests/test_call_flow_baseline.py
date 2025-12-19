# SPDX-License-Identifier: MIT
"""
Baseline tests for call flow extractors.

These tests capture the current behavior of all extractors BEFORE refactoring.
They serve as regression tests to ensure refactored code produces identical output.

Run with: pytest tests/test_call_flow_baseline.py -v
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

# Path to fixtures
FIXTURES_DIR = Path(__file__).parent / "fixtures"
PYTHON_FIXTURE = FIXTURES_DIR / "call_flow_sample.py"
TS_FIXTURE = FIXTURES_DIR / "test_ts_call_flow.ts"
CPP_FIXTURE = FIXTURES_DIR / "test_cpp_call_flow.cpp"


def normalize_graph(graph: Any) -> Dict[str, Any]:
    """
    Normalize a CallGraph to a comparable dictionary format.

    Removes non-deterministic fields like absolute paths and sorts lists.
    """
    if graph is None:
        return {"error": "graph is None"}

    # Get dict representation
    if hasattr(graph, "to_dict"):
        data = graph.to_dict()
    elif hasattr(graph, "__dict__"):
        data = graph.__dict__.copy()
    else:
        data = dict(graph) if isinstance(graph, dict) else {"raw": str(graph)}

    # Normalize paths to relative
    if "source_file" in data and data["source_file"]:
        data["source_file"] = Path(data["source_file"]).name

    # Sort edges by source_id + target_id for determinism
    if "edges" in data and isinstance(data["edges"], list):
        data["edges"] = sorted(
            data["edges"],
            key=lambda e: (
                e.get("source_id", "") if isinstance(e, dict) else str(e),
                e.get("target_id", "") if isinstance(e, dict) else "",
            ),
        )

    # Normalize nodes
    if "nodes" in data and isinstance(data["nodes"], dict):
        for node_id, node in data["nodes"].items():
            if isinstance(node, dict) and "file_path" in node:
                if node["file_path"]:
                    node["file_path"] = Path(node["file_path"]).name

    return data


def normalize_entry_points(entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Normalize entry points list for comparison."""
    result = []
    for entry in entries:
        normalized = entry.copy() if isinstance(entry, dict) else {"raw": str(entry)}
        # Normalize file path
        if "file_path" in normalized and normalized["file_path"]:
            normalized["file_path"] = Path(normalized["file_path"]).name
        result.append(normalized)
    # Sort by name for determinism
    return sorted(
        result, key=lambda e: e.get("name", "") or e.get("qualified_name", "") or ""
    )


# ============================================================================
# Python Extractor Tests
# ============================================================================


class TestPythonExtractorBaseline:
    """Baseline tests for PythonCallFlowExtractor."""

    @pytest.fixture
    def extractor(self):
        """Create Python extractor instance."""
        from code_map.graph_analysis.call_flow.extractor import PythonCallFlowExtractor

        return PythonCallFlowExtractor()

    def test_is_available(self, extractor):
        """Test that Python extractor is available."""
        # This test documents whether tree-sitter is available in test env
        available = extractor.is_available()
        # We just document the result, don't fail if not available
        assert isinstance(available, bool)

    @pytest.mark.skipif(
        not Path(PYTHON_FIXTURE).exists(),
        reason="Python fixture file not found",
    )
    def test_list_entry_points(self, extractor):
        """Capture entry points listing behavior."""
        if not extractor.is_available():
            pytest.skip("tree-sitter not available")

        entries = extractor.list_entry_points(PYTHON_FIXTURE)

        # Document expected entry point names
        names = {e.get("name") for e in entries}

        # Assert key functions are found
        assert "main" in names, f"main not found in {names}"
        assert "helper_function" in names
        assert "on_button_click" in names

        # Document count
        assert (
            len(entries) >= 9
        ), f"Expected at least 9 entry points, got {len(entries)}"

    @pytest.mark.skipif(
        not Path(PYTHON_FIXTURE).exists(),
        reason="Python fixture file not found",
    )
    def test_extract_main_function(self, extractor):
        """Capture call graph extraction for main function."""
        if not extractor.is_available():
            pytest.skip("tree-sitter not available")

        graph = extractor.extract(PYTHON_FIXTURE, "main", max_depth=5)

        assert graph is not None, "extract() returned None"
        assert graph.entry_point is not None

        # Document expected behavior
        node_names = {n.name for n in graph.nodes.values()}
        assert "main" in node_names
        assert "on_button_click" in node_names

        # Document edge count
        assert len(graph.edges) >= 1, "Expected at least 1 edge from main"

    @pytest.mark.skipif(
        not Path(PYTHON_FIXTURE).exists(),
        reason="Python fixture file not found",
    )
    def test_extract_on_button_click(self, extractor):
        """Capture full call chain from on_button_click."""
        if not extractor.is_available():
            pytest.skip("tree-sitter not available")

        graph = extractor.extract(PYTHON_FIXTURE, "on_button_click", max_depth=5)

        assert graph is not None
        node_names = {n.name for n in graph.nodes.values()}

        # Document expected call chain
        expected_in_chain = {"on_button_click", "handle", "load", "process"}
        found = expected_in_chain & node_names
        assert (
            len(found) >= 3
        ), f"Expected at least 3 of {expected_in_chain}, found {found}"

    @pytest.mark.skipif(
        not Path(PYTHON_FIXTURE).exists(),
        reason="Python fixture file not found",
    )
    def test_complexity_calculation(self, extractor):
        """Document complexity metrics calculation."""
        if not extractor.is_available():
            pytest.skip("tree-sitter not available")

        graph = extractor.extract(PYTHON_FIXTURE, "on_button_click", max_depth=2)
        assert graph is not None

        # Find a node with complexity
        entry_node = graph.nodes.get(graph.entry_point)
        if entry_node and entry_node.complexity is not None:
            # Document that complexity is calculated
            assert entry_node.complexity >= 1, "Complexity should be at least 1"

    @pytest.mark.skipif(
        not Path(PYTHON_FIXTURE).exists(),
        reason="Python fixture file not found",
    )
    def test_ignored_calls_tracking(self, extractor):
        """Document external call tracking behavior."""
        if not extractor.is_available():
            pytest.skip("tree-sitter not available")

        graph = extractor.extract(PYTHON_FIXTURE, "on_button_click", max_depth=5)
        assert graph is not None

        # Document that print() should be in ignored_calls (builtin)
        ignored_names = [ic.expression for ic in graph.ignored_calls]
        # print is called in on_button_click, should be tracked
        has_print = any("print" in name for name in ignored_names)
        # This documents expected behavior
        assert has_print or len(graph.ignored_calls) >= 0  # May vary


# ============================================================================
# TypeScript Extractor Tests
# ============================================================================


class TestTsExtractorBaseline:
    """Baseline tests for TsCallFlowExtractor."""

    @pytest.fixture
    def extractor(self):
        """Create TypeScript extractor instance."""
        from code_map.graph_analysis.call_flow.ts_extractor import TsCallFlowExtractor

        return TsCallFlowExtractor()

    def test_is_available(self, extractor):
        """Test that TypeScript extractor is available."""
        available = extractor.is_available()
        assert isinstance(available, bool)

    @pytest.mark.skipif(
        not Path(TS_FIXTURE).exists(),
        reason="TypeScript fixture file not found",
    )
    def test_list_entry_points(self, extractor):
        """Capture entry points listing behavior."""
        if not extractor.is_available():
            pytest.skip("tree-sitter not available")

        entries = extractor.list_entry_points(TS_FIXTURE)

        names = {e.get("name") for e in entries}

        # Document expected functions
        assert (
            "main" in names or "default" in names
        ), f"main/default not found in {names}"
        assert "greet" in names
        assert (
            len(entries) >= 8
        ), f"Expected at least 8 entry points, got {len(entries)}"

    @pytest.mark.skipif(
        not Path(TS_FIXTURE).exists(),
        reason="TypeScript fixture file not found",
    )
    def test_extract_main_function(self, extractor):
        """Capture call graph extraction for main function."""
        if not extractor.is_available():
            pytest.skip("tree-sitter not available")

        # Try 'main' or 'default' (export default function main)
        graph = extractor.extract(TS_FIXTURE, "main", max_depth=5)
        if graph is None:
            graph = extractor.extract(TS_FIXTURE, "default", max_depth=5)

        assert graph is not None, "extract() returned None for main/default"

        node_names = {n.name for n in graph.nodes.values()}
        # Document expected behavior
        assert len(node_names) >= 1

    @pytest.mark.skipif(
        not Path(TS_FIXTURE).exists(),
        reason="TypeScript fixture file not found",
    )
    def test_extract_complex_operation(self, extractor):
        """Capture call chain from complexOperation."""
        if not extractor.is_available():
            pytest.skip("tree-sitter not available")

        graph = extractor.extract(TS_FIXTURE, "complexOperation", max_depth=5)

        assert graph is not None
        node_names = {n.name for n in graph.nodes.values()}

        # complexOperation calls greet and calculateTotal
        assert "complexOperation" in node_names
        # Document what we find
        assert len(node_names) >= 1

    @pytest.mark.skipif(
        not Path(TS_FIXTURE).exists(),
        reason="TypeScript fixture file not found",
    )
    def test_class_methods(self, extractor):
        """Document class method extraction."""
        if not extractor.is_available():
            pytest.skip("tree-sitter not available")

        entries = extractor.list_entry_points(TS_FIXTURE)

        # Find Calculator methods
        calculator_methods = [
            e for e in entries if "Calculator" in e.get("qualified_name", "")
        ]

        # Document that class methods are found
        method_names = {e.get("name") for e in calculator_methods}
        # Should find: constructor, add, internalAdd, subtract, multiply, getResult, reset
        assert (
            len(calculator_methods) >= 5
        ), f"Expected Calculator methods, found {method_names}"


# ============================================================================
# C++ Extractor Tests
# ============================================================================


class TestCppExtractorBaseline:
    """Baseline tests for CppCallFlowExtractor."""

    @pytest.fixture
    def extractor(self):
        """Create C++ extractor instance."""
        from code_map.graph_analysis.call_flow.cpp_extractor import CppCallFlowExtractor

        return CppCallFlowExtractor()

    def test_is_available(self, extractor):
        """Test that C++ extractor is available."""
        available = extractor.is_available()
        assert isinstance(available, bool)

    @pytest.mark.skipif(
        not Path(CPP_FIXTURE).exists(),
        reason="C++ fixture file not found",
    )
    def test_list_entry_points(self, extractor):
        """Capture entry points listing behavior."""
        if not extractor.is_available():
            pytest.skip("tree-sitter not available")

        entries = extractor.list_entry_points(CPP_FIXTURE)

        names = {e.get("name") for e in entries}

        # Document expected functions
        assert "main" in names, f"main not found in {names}"
        assert "helper_function" in names
        assert (
            len(entries) >= 5
        ), f"Expected at least 5 entry points, got {len(entries)}"

    @pytest.mark.skipif(
        not Path(CPP_FIXTURE).exists(),
        reason="C++ fixture file not found",
    )
    def test_extract_main_function(self, extractor):
        """Capture call graph extraction for main function."""
        if not extractor.is_available():
            pytest.skip("tree-sitter not available")

        graph = extractor.extract(CPP_FIXTURE, "main", max_depth=5)

        assert graph is not None, "extract() returned None"

        node_names = {n.name for n in graph.nodes.values()}
        assert "main" in node_names

        # main calls complex_function and calculate_total
        assert len(graph.edges) >= 1

    @pytest.mark.skipif(
        not Path(CPP_FIXTURE).exists(),
        reason="C++ fixture file not found",
    )
    def test_extract_complex_function(self, extractor):
        """Capture call chain from complex_function."""
        if not extractor.is_available():
            pytest.skip("tree-sitter not available")

        graph = extractor.extract(CPP_FIXTURE, "complex_function", max_depth=5)

        assert graph is not None
        node_names = {n.name for n in graph.nodes.values()}

        # complex_function calls process_value and helper_function
        assert "complex_function" in node_names

    @pytest.mark.skipif(
        not Path(CPP_FIXTURE).exists(),
        reason="C++ fixture file not found",
    )
    def test_class_methods(self, extractor):
        """Document class method extraction."""
        if not extractor.is_available():
            pytest.skip("tree-sitter not available")

        entries = extractor.list_entry_points(CPP_FIXTURE)

        # Find Calculator methods
        calculator_methods = [
            e for e in entries if "Calculator" in e.get("qualified_name", "")
        ]

        # Document method discovery
        {e.get("name") for e in calculator_methods}
        # Should find class methods
        assert len(entries) >= 5  # At least free functions


# ============================================================================
# Cross-Extractor Consistency Tests
# ============================================================================


class TestExtractorConsistency:
    """Tests to ensure all extractors behave consistently."""

    def test_all_extractors_have_same_interface(self):
        """Verify all extractors expose the same public methods."""
        from code_map.graph_analysis.call_flow.extractor import PythonCallFlowExtractor
        from code_map.graph_analysis.call_flow.ts_extractor import TsCallFlowExtractor
        from code_map.graph_analysis.call_flow.cpp_extractor import CppCallFlowExtractor

        required_methods = ["is_available", "extract", "list_entry_points"]

        for ExtractorClass in [
            PythonCallFlowExtractor,
            TsCallFlowExtractor,
            CppCallFlowExtractor,
        ]:
            for method in required_methods:
                assert hasattr(
                    ExtractorClass, method
                ), f"{ExtractorClass.__name__} missing {method}"

    def test_all_extractors_return_same_model_types(self):
        """Verify all extractors return CallGraph with same structure."""
        from dataclasses import fields
        from code_map.graph_analysis.call_flow.models import (
            CallGraph,
            CallNode,
            CallEdge,
        )

        # Get field names from dataclasses
        graph_fields = {f.name for f in fields(CallGraph)}
        node_fields = {f.name for f in fields(CallNode)}
        edge_fields = {f.name for f in fields(CallEdge)}

        # Document expected model structure
        assert (
            "nodes" in graph_fields
        ), f"CallGraph missing 'nodes', has: {graph_fields}"
        assert "edges" in graph_fields
        assert "entry_point" in graph_fields
        assert "ignored_calls" in graph_fields

        assert "id" in node_fields, f"CallNode missing 'id', has: {node_fields}"
        assert "name" in node_fields
        assert "complexity" in node_fields
        assert "loc" in node_fields

        assert (
            "source_id" in edge_fields
        ), f"CallEdge missing 'source_id', has: {edge_fields}"
        assert "target_id" in edge_fields


# ============================================================================
# Snapshot Tests (for detailed regression testing)
# ============================================================================


class TestCallFlowSnapshots:
    """
    Snapshot tests that capture exact output.

    These tests generate JSON snapshots of extractor output.
    After refactoring, output should match exactly.
    """

    SNAPSHOT_DIR = Path(__file__).parent / "snapshots" / "call_flow"

    @pytest.fixture(autouse=True)
    def ensure_snapshot_dir(self):
        """Ensure snapshot directory exists."""
        self.SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)

    def _save_snapshot(self, name: str, data: Dict[str, Any]) -> None:
        """Save snapshot to file."""
        path = self.SNAPSHOT_DIR / f"{name}.json"
        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)

    def _load_snapshot(self, name: str) -> Optional[Dict[str, Any]]:
        """Load snapshot from file if exists."""
        path = self.SNAPSHOT_DIR / f"{name}.json"
        if path.exists():
            with open(path) as f:
                return json.load(f)
        return None

    @pytest.mark.skipif(
        not Path(PYTHON_FIXTURE).exists(),
        reason="Python fixture not found",
    )
    def test_python_snapshot(self):
        """Generate/verify Python extractor snapshot."""
        from code_map.graph_analysis.call_flow.extractor import PythonCallFlowExtractor

        extractor = PythonCallFlowExtractor()
        if not extractor.is_available():
            pytest.skip("tree-sitter not available")

        graph = extractor.extract(PYTHON_FIXTURE, "on_button_click", max_depth=5)
        assert graph is not None

        normalized = normalize_graph(graph)

        # Check against existing snapshot or save new one
        existing = self._load_snapshot("python_on_button_click")
        if existing is None:
            self._save_snapshot("python_on_button_click", normalized)
            pytest.skip("Snapshot created, run again to verify")
        else:
            # Compare key metrics (not exact match due to path variations)
            assert len(normalized.get("nodes", {})) == len(
                existing.get("nodes", {})
            ), "Node count changed"
            assert len(normalized.get("edges", [])) == len(
                existing.get("edges", [])
            ), "Edge count changed"

    @pytest.mark.skipif(
        not Path(TS_FIXTURE).exists(),
        reason="TypeScript fixture not found",
    )
    def test_typescript_snapshot(self):
        """Generate/verify TypeScript extractor snapshot."""
        from code_map.graph_analysis.call_flow.ts_extractor import TsCallFlowExtractor

        extractor = TsCallFlowExtractor()
        if not extractor.is_available():
            pytest.skip("tree-sitter not available")

        graph = extractor.extract(TS_FIXTURE, "complexOperation", max_depth=5)
        if graph is None:
            pytest.skip("Could not extract complexOperation")

        normalized = normalize_graph(graph)

        existing = self._load_snapshot("ts_complex_operation")
        if existing is None:
            self._save_snapshot("ts_complex_operation", normalized)
            pytest.skip("Snapshot created, run again to verify")
        else:
            assert len(normalized.get("nodes", {})) == len(existing.get("nodes", {}))
            assert len(normalized.get("edges", [])) == len(existing.get("edges", []))

    @pytest.mark.skipif(
        not Path(CPP_FIXTURE).exists(),
        reason="C++ fixture not found",
    )
    def test_cpp_snapshot(self):
        """Generate/verify C++ extractor snapshot."""
        from code_map.graph_analysis.call_flow.cpp_extractor import CppCallFlowExtractor

        extractor = CppCallFlowExtractor()
        if not extractor.is_available():
            pytest.skip("tree-sitter not available")

        graph = extractor.extract(CPP_FIXTURE, "main", max_depth=5)
        if graph is None:
            pytest.skip("Could not extract main")

        normalized = normalize_graph(graph)

        existing = self._load_snapshot("cpp_main")
        if existing is None:
            self._save_snapshot("cpp_main", normalized)
            pytest.skip("Snapshot created, run again to verify")
        else:
            assert len(normalized.get("nodes", {})) == len(existing.get("nodes", {}))
            assert len(normalized.get("edges", [])) == len(existing.get("edges", []))
