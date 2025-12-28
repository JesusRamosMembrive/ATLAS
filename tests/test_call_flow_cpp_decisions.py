# SPDX-License-Identifier: MIT
"""
Tests for decision point detection and lazy extraction in Call Flow for C++.

These tests verify:
1. Decision point detection (if/else, switch/case, try/catch, ternary)
2. Lazy extraction mode (stops at first decision point)
3. Branch expansion (expands specific branches on demand)
4. Loops are NOT treated as decision points (user preference)

Run with: pytest tests/test_call_flow_cpp_decisions.py -v
"""

from __future__ import annotations

from pathlib import Path

import pytest

from code_map.graph_analysis.call_flow.models import (
    DecisionType,
    ExtractionMode,
)
from code_map.graph_analysis.call_flow.languages.cpp import CppCallFlowExtractor

# Path to decision flow fixture
FIXTURES_DIR = Path(__file__).parent / "fixtures"
CPP_DECISION_FIXTURE = FIXTURES_DIR / "decision_flow_cpp.cpp"


class TestCppDecisionDetection:
    """Tests for decision point detection in C++ code."""

    @pytest.fixture
    def extractor(self):
        """Create C++ extractor instance."""
        return CppCallFlowExtractor()

    def test_extractor_available(self, extractor):
        """Verify tree-sitter is available for testing."""
        assert extractor.is_available(), "tree-sitter required for decision tests"

    @pytest.mark.skipif(
        not Path(CPP_DECISION_FIXTURE).exists(),
        reason="C++ decision fixture file not found",
    )
    def test_detect_if_else_decision(self, extractor):
        """Test detection of if/else decision points in LAZY mode."""
        if not extractor.is_available():
            pytest.skip("tree-sitter not available")

        # Extract with LAZY mode to detect decision points
        graph = extractor.extract(
            CPP_DECISION_FIXTURE,
            "process_order",
            max_depth=5,
            extraction_mode=ExtractionMode.LAZY,
        )

        assert graph is not None, "extract() returned None"

        # Should detect the if statement as a decision point
        decision_nodes = graph.decision_nodes
        assert len(decision_nodes) >= 1, "Expected at least 1 decision node"

        # Find the if decision
        if_decisions = [
            d for d in decision_nodes.values() if d.decision_type == DecisionType.IF_ELSE
        ]
        assert len(if_decisions) >= 1, "Expected at least 1 IF_ELSE decision"

        # Check decision properties
        if_decision = if_decisions[0]
        assert len(if_decision.branches) >= 2, "if/else should have at least 2 branches"

        # Check branch labels
        branch_labels = {b.label for b in if_decision.branches}
        assert "TRUE" in branch_labels or "true" in branch_labels.union(
            {l.lower() for l in branch_labels}
        )
        assert "FALSE" in branch_labels or "false" in branch_labels.union(
            {l.lower() for l in branch_labels}
        )

    @pytest.mark.skipif(
        not Path(CPP_DECISION_FIXTURE).exists(),
        reason="C++ decision fixture file not found",
    )
    def test_detect_switch_case_decision(self, extractor):
        """Test detection of switch/case decision points in LAZY mode."""
        if not extractor.is_available():
            pytest.skip("tree-sitter not available")

        graph = extractor.extract(
            CPP_DECISION_FIXTURE,
            "process_status",
            max_depth=3,
            extraction_mode=ExtractionMode.LAZY,
        )

        assert graph is not None

        # Find switch decisions
        switch_decisions = [
            d
            for d in graph.decision_nodes.values()
            if d.decision_type == DecisionType.MATCH_CASE  # switch/case maps to MATCH_CASE
        ]

        assert len(switch_decisions) >= 1, "Expected switch/case decision point"

        switch_decision = switch_decisions[0]
        # Should have multiple case branches
        assert len(switch_decision.branches) >= 3, "switch should have multiple cases"

    @pytest.mark.skipif(
        not Path(CPP_DECISION_FIXTURE).exists(),
        reason="C++ decision fixture file not found",
    )
    def test_detect_try_catch_decision(self, extractor):
        """Test detection of try/catch decision points in LAZY mode."""
        if not extractor.is_available():
            pytest.skip("tree-sitter not available")

        graph = extractor.extract(
            CPP_DECISION_FIXTURE,
            "process_with_error_handling",
            max_depth=3,
            extraction_mode=ExtractionMode.LAZY,
        )

        assert graph is not None

        # Find try/catch decisions
        try_decisions = [
            d
            for d in graph.decision_nodes.values()
            if d.decision_type == DecisionType.TRY_EXCEPT
        ]
        assert len(try_decisions) >= 1, "Expected try/catch decision point"

        try_decision = try_decisions[0]
        # Should have branches for try and catch clauses
        assert len(try_decision.branches) >= 2, "try/catch should have multiple branches"

    @pytest.mark.skipif(
        not Path(CPP_DECISION_FIXTURE).exists(),
        reason="C++ decision fixture file not found",
    )
    def test_loops_not_detected_as_decisions(self, extractor):
        """Verify loops are NOT treated as decision points per user preference."""
        if not extractor.is_available():
            pytest.skip("tree-sitter not available")

        graph = extractor.extract(
            CPP_DECISION_FIXTURE,
            "iterate_items",
            max_depth=3,
            extraction_mode=ExtractionMode.LAZY,
        )

        assert graph is not None

        # Should have NO decision nodes (loops are linear)
        assert (
            len(graph.decision_nodes) == 0
        ), f"Loops should not be decision points, found: {graph.decision_nodes}"

        # But should still extract the call to process_item
        node_names = {n.name for n in graph.nodes.values()}
        assert "iterate_items" in node_names


class TestCppLazyExtraction:
    """Tests for lazy extraction mode (stops at decision points) for C++."""

    @pytest.fixture
    def extractor(self):
        """Create C++ extractor instance."""
        return CppCallFlowExtractor()

    @pytest.mark.skipif(
        not Path(CPP_DECISION_FIXTURE).exists(),
        reason="C++ decision fixture file not found",
    )
    def test_lazy_mode_stops_at_first_decision(self, extractor):
        """Test that lazy mode stops at the first decision point."""
        if not extractor.is_available():
            pytest.skip("tree-sitter not available")

        # Extract with LAZY mode
        graph = extractor.extract(
            CPP_DECISION_FIXTURE,
            "process_order",
            max_depth=5,
            extraction_mode=ExtractionMode.LAZY,
        )

        assert graph is not None
        assert graph.extraction_mode == "lazy"

        # Should have extracted calls before the decision
        node_names = {n.name for n in graph.nodes.values()}
        assert "process_order" in node_names
        assert "validate" in node_names

        # Should NOT have extracted calls inside branches
        # (process_priority, process_standard should not be in nodes)
        assert (
            "process_priority" not in node_names
        ), "Should not extract inside unexpanded branches"
        assert (
            "process_standard" not in node_names
        ), "Should not extract inside unexpanded branches"

        # Should have unexpanded branches
        assert (
            len(graph.unexpanded_branches) >= 2
        ), f"Expected unexpanded branches, got: {graph.unexpanded_branches}"

        # Should have a decision node
        assert len(graph.decision_nodes) >= 1, "Expected decision node in lazy mode"

    @pytest.mark.skipif(
        not Path(CPP_DECISION_FIXTURE).exists(),
        reason="C++ decision fixture file not found",
    )
    def test_full_mode_extracts_all_paths(self, extractor):
        """Test that full mode extracts all call paths."""
        if not extractor.is_available():
            pytest.skip("tree-sitter not available")

        # Extract with FULL mode (default)
        graph = extractor.extract(
            CPP_DECISION_FIXTURE,
            "process_order",
            max_depth=5,
            extraction_mode=ExtractionMode.FULL,
        )

        assert graph is not None
        assert graph.extraction_mode == "full"

        # Should have extracted all paths
        node_names = {n.name for n in graph.nodes.values()}
        assert "process_order" in node_names
        assert "validate" in node_names
        assert "process_priority" in node_names
        assert "process_standard" in node_names
        assert "finalize" in node_names

        # No unexpanded branches in full mode
        assert (
            len(graph.unexpanded_branches) == 0
        ), f"Full mode should have no unexpanded branches: {graph.unexpanded_branches}"

    @pytest.mark.skipif(
        not Path(CPP_DECISION_FIXTURE).exists(),
        reason="C++ decision fixture file not found",
    )
    def test_full_mode_unchanged_behavior(self, extractor):
        """Verify FULL mode produces same results as before (backward compat)."""
        if not extractor.is_available():
            pytest.skip("tree-sitter not available")

        # Extract without specifying mode (should default to FULL)
        graph_default = extractor.extract(
            CPP_DECISION_FIXTURE,
            "process_order",
            max_depth=5,
        )

        # Extract explicitly with FULL mode
        graph_full = extractor.extract(
            CPP_DECISION_FIXTURE,
            "process_order",
            max_depth=5,
            extraction_mode=ExtractionMode.FULL,
        )

        assert graph_default is not None
        assert graph_full is not None

        # Should have same nodes
        default_nodes = {n.name for n in graph_default.nodes.values()}
        full_nodes = {n.name for n in graph_full.nodes.values()}
        assert default_nodes == full_nodes, "Default and FULL mode should produce same nodes"


class TestCppBranchExpansion:
    """Tests for branch expansion functionality for C++."""

    @pytest.fixture
    def extractor(self):
        """Create C++ extractor instance."""
        return CppCallFlowExtractor()

    @pytest.mark.skipif(
        not Path(CPP_DECISION_FIXTURE).exists(),
        reason="C++ decision fixture file not found",
    )
    def test_expand_true_branch(self, extractor):
        """Test expanding the TRUE branch of an if statement."""
        if not extractor.is_available():
            pytest.skip("tree-sitter not available")

        # First, extract in LAZY mode
        graph = extractor.extract(
            CPP_DECISION_FIXTURE,
            "process_order",
            max_depth=5,
            extraction_mode=ExtractionMode.LAZY,
        )

        assert graph is not None
        assert len(graph.unexpanded_branches) >= 2

        # Find the TRUE branch
        true_branch_id = None
        for branch_id in graph.unexpanded_branches:
            if "TRUE" in branch_id.upper() or ":0" in branch_id:
                true_branch_id = branch_id
                break

        if true_branch_id is None:
            pytest.skip("Could not identify TRUE branch for expansion test")

        # Extract again with the TRUE branch expanded
        expanded_graph = extractor.extract(
            CPP_DECISION_FIXTURE,
            "process_order",
            max_depth=5,
            extraction_mode=ExtractionMode.LAZY,
            expand_branches=[true_branch_id],
        )

        assert expanded_graph is not None

        # Should now have process_priority in nodes
        node_names = {n.name for n in expanded_graph.nodes.values()}
        assert (
            "process_priority" in node_names
        ), f"Expected process_priority after expanding TRUE branch, got: {node_names}"

    @pytest.mark.skipif(
        not Path(CPP_DECISION_FIXTURE).exists(),
        reason="C++ decision fixture file not found",
    )
    def test_expand_false_branch(self, extractor):
        """Test expanding the FALSE branch of an if statement."""
        if not extractor.is_available():
            pytest.skip("tree-sitter not available")

        # First, extract in LAZY mode
        graph = extractor.extract(
            CPP_DECISION_FIXTURE,
            "process_order",
            max_depth=5,
            extraction_mode=ExtractionMode.LAZY,
        )

        assert graph is not None

        # Find the FALSE branch
        false_branch_id = None
        for branch_id in graph.unexpanded_branches:
            if "FALSE" in branch_id.upper() or ":1" in branch_id:
                false_branch_id = branch_id
                break

        if false_branch_id is None:
            pytest.skip("Could not identify FALSE branch for expansion test")

        # Extract again with the FALSE branch expanded
        expanded_graph = extractor.extract(
            CPP_DECISION_FIXTURE,
            "process_order",
            max_depth=5,
            extraction_mode=ExtractionMode.LAZY,
            expand_branches=[false_branch_id],
        )

        assert expanded_graph is not None

        # Should now have process_standard in nodes
        node_names = {n.name for n in expanded_graph.nodes.values()}
        assert (
            "process_standard" in node_names
        ), f"Expected process_standard after expanding FALSE branch, got: {node_names}"

    @pytest.mark.skipif(
        not Path(CPP_DECISION_FIXTURE).exists(),
        reason="C++ decision fixture file not found",
    )
    def test_nested_decision_extraction(self, extractor):
        """Test extraction of nested decision points with branch expansion."""
        if not extractor.is_available():
            pytest.skip("tree-sitter not available")

        # First extract to find the first decision and its branches
        graph = extractor.extract(
            CPP_DECISION_FIXTURE,
            "process_nested_decisions",
            max_depth=5,
            extraction_mode=ExtractionMode.LAZY,
        )

        assert graph is not None

        # Should find the first (outer) decision
        if_decisions = [
            d
            for d in graph.decision_nodes.values()
            if d.decision_type == DecisionType.IF_ELSE
        ]

        # Should have at least 1 decision node (the outer if)
        assert len(if_decisions) >= 1, "Expected at least 1 if decision"

        # The outer decision should have 2 branches
        if if_decisions:
            outer_decision = if_decisions[0]
            assert len(outer_decision.branches) >= 2, "Outer if should have 2 branches"


class TestCppDecisionNodeProperties:
    """Tests for decision node data structure properties for C++."""

    @pytest.fixture
    def extractor(self):
        """Create C++ extractor instance."""
        return CppCallFlowExtractor()

    @pytest.mark.skipif(
        not Path(CPP_DECISION_FIXTURE).exists(),
        reason="C++ decision fixture file not found",
    )
    def test_decision_node_has_required_fields(self, extractor):
        """Test that decision nodes have all required fields."""
        if not extractor.is_available():
            pytest.skip("tree-sitter not available")

        graph = extractor.extract(
            CPP_DECISION_FIXTURE,
            "process_order",
            max_depth=5,
            extraction_mode=ExtractionMode.LAZY,
        )

        assert graph is not None
        assert len(graph.decision_nodes) >= 1

        for decision_id, decision in graph.decision_nodes.items():
            # Check required fields
            assert decision.id, "Decision must have id"
            assert decision.decision_type, "Decision must have decision_type"
            assert decision.line > 0, "Decision must have valid line number"
            assert decision.parent_call_id, "Decision must have parent_call_id"
            assert len(decision.branches) >= 1, "Decision must have at least 1 branch"

            # Check branch properties
            for branch in decision.branches:
                assert branch.branch_id, "Branch must have branch_id"
                assert branch.label, "Branch must have label"
                assert branch.start_line >= 0, "Branch must have valid start_line"
                assert branch.end_line >= branch.start_line, "Branch end_line >= start_line"


class TestCppTernaryExpression:
    """Tests for ternary expression (conditional) detection in C++."""

    @pytest.fixture
    def extractor(self):
        """Create C++ extractor instance."""
        return CppCallFlowExtractor()

    @pytest.mark.skipif(
        not Path(CPP_DECISION_FIXTURE).exists(),
        reason="C++ decision fixture file not found",
    )
    def test_detect_ternary_decision(self, extractor):
        """Test detection of ternary expression decision points."""
        if not extractor.is_available():
            pytest.skip("tree-sitter not available")

        graph = extractor.extract(
            CPP_DECISION_FIXTURE,
            "process_with_ternary",
            max_depth=3,
            extraction_mode=ExtractionMode.LAZY,
        )

        assert graph is not None

        # Find ternary decisions
        ternary_decisions = [
            d
            for d in graph.decision_nodes.values()
            if d.decision_type == DecisionType.TERNARY
        ]

        # Should detect the ternary operator as a decision point
        assert len(ternary_decisions) >= 1, "Expected ternary decision point"

        ternary_decision = ternary_decisions[0]
        # Ternary should have 2 branches (true and false)
        assert len(ternary_decision.branches) == 2, "Ternary should have 2 branches"
