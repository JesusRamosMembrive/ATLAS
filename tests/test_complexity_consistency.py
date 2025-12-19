# SPDX-License-Identifier: MIT
"""
Tests for complexity calculation consistency across different implementations.

This test file ensures that cyclomatic complexity is calculated consistently
between:
- code_map/analyzer.py (Python AST-based for symbols endpoint)
- code_map/graph_analysis/call_flow/languages/python.py (tree-sitter based for call-flow)
- code_map/c_analyzer.py (tree-sitter based for C/C++ symbols)

Criteria (as per user decisions):
- Boolean operators (and/or, &&/||): INCLUDED
- Comprehensions (list/dict/set/generator): EXCLUDED
"""

import ast
import tempfile
from pathlib import Path

import pytest

from code_map.analyzer import calculate_complexity


# ─────────────────────────────────────────────────────────────────────────────
# Test Fixtures - Python Code Samples
# ─────────────────────────────────────────────────────────────────────────────

PYTHON_SIMPLE_FUNCTION = """
def simple():
    return 1
"""

PYTHON_IF_ONLY = """
def with_if(x):
    if x > 0:
        return 1
    return 0
"""

PYTHON_BOOLEAN_OPS = """
def with_boolops(a, b, c):
    if a and b:
        return 1
    if a or b or c:
        return 2
    return 0
"""

PYTHON_NESTED_BOOLOPS = """
def nested_boolops(a, b, c, d):
    # 'a and b and c' has 2 'and' operators
    if a and b and c:
        return 1
    return 0
"""

PYTHON_COMPREHENSION = """
def with_comprehension(items):
    # Comprehensions should NOT add complexity per user decision
    return [x for x in items if x > 0]
"""

PYTHON_COMPLEX = """
def complex_function(x, y, z):
    if x > 0 and y > 0:
        for i in range(x):
            if z and i > 5:
                return True
    elif y < 0 or z < 0:
        while x > 0:
            x -= 1
    return False
"""

PYTHON_MATCH_CASE = """
def with_match(value):
    match value:
        case 1:
            return "one"
        case 2:
            return "two"
        case _:
            return "other"
"""


# ─────────────────────────────────────────────────────────────────────────────
# Helper Functions
# ─────────────────────────────────────────────────────────────────────────────


def get_ast_complexity(code: str) -> int:
    """Calculate complexity using code_map/analyzer.py (AST-based)."""
    tree = ast.parse(code)
    # Find the function definition
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            return calculate_complexity(node)
    raise ValueError("No function found in code")


def get_call_flow_complexity(code: str, func_name: str = None) -> int:
    """Calculate complexity using call_flow/languages/python.py (tree-sitter)."""
    try:
        from code_map.graph_analysis.call_flow import PythonCallFlowExtractor
    except ImportError:
        pytest.skip("PythonCallFlowExtractor not available")
        return 0

    # Create temp file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(code)
        temp_path = Path(f.name)

    try:
        extractor = PythonCallFlowExtractor()
        if not extractor.is_available():
            pytest.skip("tree-sitter not available")
            return 0

        # Get entry points
        entries = extractor.list_entry_points(temp_path)
        if not entries:
            raise ValueError("No entry points found")

        # Use specified function or first one
        if func_name:
            entry = next((e for e in entries if e["name"] == func_name), None)
        else:
            entry = entries[0]

        if not entry:
            raise ValueError(f"Function {func_name} not found")

        # Extract graph for the function
        graph = extractor.extract(
            temp_path,
            entry.get("qualified_name", entry["name"]),
            max_depth=1,
        )

        if not graph or not graph.entry_point:
            raise ValueError("Could not extract graph")

        # Get entry node complexity
        entry_node = graph.nodes.get(graph.entry_point)
        if entry_node:
            return entry_node.complexity or 1

        return 1
    finally:
        temp_path.unlink()


# ─────────────────────────────────────────────────────────────────────────────
# Tests
# ─────────────────────────────────────────────────────────────────────────────


class TestASTComplexity:
    """Test the AST-based complexity calculation (analyzer.py)."""

    def test_simple_function(self):
        """A function with no branches has complexity 1."""
        assert get_ast_complexity(PYTHON_SIMPLE_FUNCTION) == 1

    def test_single_if(self):
        """A single if statement adds 1 to complexity."""
        assert get_ast_complexity(PYTHON_IF_ONLY) == 2  # 1 base + 1 if

    def test_boolean_operators(self):
        """Boolean operators (and/or) should add to complexity."""
        # First if: 'a and b' = 1 and op
        # Second if: 'a or b or c' = 2 or ops
        # Total: 1 base + 2 ifs + 1 and + 2 or = 6
        result = get_ast_complexity(PYTHON_BOOLEAN_OPS)
        assert result == 6, f"Expected 6, got {result}"

    def test_nested_boolean_ops(self):
        """'a and b and c' has 2 'and' operators."""
        # 1 base + 1 if + 2 and = 4
        result = get_ast_complexity(PYTHON_NESTED_BOOLOPS)
        assert result == 4, f"Expected 4, got {result}"

    def test_comprehension_excluded(self):
        """Comprehensions should NOT add to complexity."""
        # 1 base only (comprehension excluded)
        result = get_ast_complexity(PYTHON_COMPREHENSION)
        assert result == 1, f"Expected 1, got {result}"

    def test_complex_function(self):
        """Complex function with multiple control structures."""
        # 1 base + 2 if + 1 elif + 1 for + 1 while + 3 boolean ops = 9
        # if x > 0 and y > 0: (1 if + 1 and)
        # for i in range(x): (1 for)
        # if z and i > 5: (1 if + 1 and)
        # elif y < 0 or z < 0: (1 elif + 1 or)
        # while x > 0: (1 while)
        result = get_ast_complexity(PYTHON_COMPLEX)
        assert result == 9, f"Expected 9, got {result}"


class TestCallFlowComplexity:
    """Test the tree-sitter based complexity (call_flow/languages/python.py)."""

    def test_simple_function(self):
        """A function with no branches has complexity 1."""
        result = get_call_flow_complexity(PYTHON_SIMPLE_FUNCTION)
        assert result == 1

    def test_single_if(self):
        """A single if statement adds 1 to complexity."""
        result = get_call_flow_complexity(PYTHON_IF_ONLY)
        assert result == 2  # 1 base + 1 if

    def test_comprehension_excluded(self):
        """Comprehensions should NOT add to complexity (after fix)."""
        result = get_call_flow_complexity(PYTHON_COMPREHENSION)
        assert result == 1, f"Expected 1, got {result}"


class TestConsistency:
    """Test that AST and tree-sitter implementations give same results."""

    @pytest.mark.parametrize(
        "code,expected",
        [
            (PYTHON_SIMPLE_FUNCTION, 1),
            (PYTHON_IF_ONLY, 2),
            (PYTHON_COMPREHENSION, 1),  # Both should exclude comprehensions
        ],
    )
    def test_consistency(self, code: str, expected: int):
        """Both implementations should return the same complexity."""
        ast_result = get_ast_complexity(code)
        call_flow_result = get_call_flow_complexity(code)

        assert ast_result == expected, f"AST: expected {expected}, got {ast_result}"
        assert (
            call_flow_result == expected
        ), f"CallFlow: expected {expected}, got {call_flow_result}"
        assert (
            ast_result == call_flow_result
        ), f"Inconsistency: AST={ast_result}, CallFlow={call_flow_result}"


# ─────────────────────────────────────────────────────────────────────────────
# C/C++ Tests (if available)
# ─────────────────────────────────────────────────────────────────────────────

C_SIMPLE_FUNCTION = """
int simple() {
    return 1;
}
"""

C_WITH_IF = """
int with_if(int x) {
    if (x > 0) {
        return 1;
    }
    return 0;
}
"""

C_BOOLEAN_OPS = """
int with_boolops(int a, int b) {
    if (a && b) {
        return 1;
    }
    if (a || b) {
        return 2;
    }
    return 0;
}
"""


class TestCAnalyzerComplexity:
    """Test the C analyzer complexity calculation."""

    def test_c_analyzer_available(self):
        """Check if C analyzer is available."""
        try:
            from code_map.c_analyzer import CAnalyzer

            analyzer = CAnalyzer()
            assert hasattr(analyzer, "_calculate_complexity")
        except ImportError:
            pytest.skip("CAnalyzer not available")


# ─────────────────────────────────────────────────────────────────────────────
# Run tests
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
