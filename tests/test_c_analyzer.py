# SPDX-License-Identifier: MIT
"""Tests for C/C++ analyzer."""

from pathlib import Path

import pytest

from code_map.c_analyzer import CAnalyzer
from code_map.models import SymbolKind


@pytest.fixture
def c_analyzer() -> CAnalyzer:
    """Create a C analyzer instance."""
    return CAnalyzer(include_docstrings=True)


@pytest.fixture
def cpp_analyzer() -> CAnalyzer:
    """Create a C++ analyzer instance."""
    return CAnalyzer(include_docstrings=True, is_cpp=True)


class TestCAnalyzerBasics:
    """Test basic C analyzer functionality."""

    def test_analyzer_initializes(self, c_analyzer: CAnalyzer) -> None:
        """Test that C analyzer initializes correctly."""
        assert c_analyzer is not None
        assert c_analyzer.is_cpp is False
        assert c_analyzer.include_docstrings is True

    def test_cpp_analyzer_initializes(self, cpp_analyzer: CAnalyzer) -> None:
        """Test that C++ analyzer initializes correctly."""
        assert cpp_analyzer is not None
        assert cpp_analyzer.is_cpp is True

    def test_parse_nonexistent_file(self, c_analyzer: CAnalyzer, tmp_path: Path) -> None:
        """Test parsing a file that doesn't exist."""
        fake_path = tmp_path / "nonexistent.c"
        result = c_analyzer.parse(fake_path)
        assert len(result.errors) > 0
        assert "No se pudo leer" in result.errors[0].message


class TestCFunctionParsing:
    """Test C function parsing."""

    def test_parse_simple_function(self, c_analyzer: CAnalyzer, tmp_path: Path) -> None:
        """Test parsing a simple C function."""
        if not c_analyzer.available:
            pytest.skip("tree_sitter_languages not available")

        c_file = tmp_path / "simple.c"
        c_file.write_text("""
int add(int a, int b) {
    return a + b;
}
""")
        result = c_analyzer.parse(c_file)
        assert len(result.errors) == 0

        functions = [s for s in result.symbols if s.kind == SymbolKind.FUNCTION]
        assert len(functions) == 1
        assert functions[0].name == "add"

    def test_parse_multiple_functions(self, c_analyzer: CAnalyzer, tmp_path: Path) -> None:
        """Test parsing multiple C functions."""
        if not c_analyzer.available:
            pytest.skip("tree_sitter_languages not available")

        c_file = tmp_path / "multi.c"
        c_file.write_text("""
int add(int a, int b) {
    return a + b;
}

int subtract(int a, int b) {
    return a - b;
}

void print_result(int value) {
    // Just a placeholder
}
""")
        result = c_analyzer.parse(c_file)
        assert len(result.errors) == 0

        functions = [s for s in result.symbols if s.kind == SymbolKind.FUNCTION]
        assert len(functions) == 3
        names = {f.name for f in functions}
        assert names == {"add", "subtract", "print_result"}

    def test_parse_function_with_pointer_return(self, c_analyzer: CAnalyzer, tmp_path: Path) -> None:
        """Test parsing function with pointer return type."""
        if not c_analyzer.available:
            pytest.skip("tree_sitter_languages not available")

        c_file = tmp_path / "pointer.c"
        c_file.write_text("""
char* get_string(void) {
    return "hello";
}

int* allocate_array(int size) {
    return malloc(size * sizeof(int));
}
""")
        result = c_analyzer.parse(c_file)
        assert len(result.errors) == 0

        functions = [s for s in result.symbols if s.kind == SymbolKind.FUNCTION]
        assert len(functions) == 2
        names = {f.name for f in functions}
        assert names == {"get_string", "allocate_array"}


class TestCStructParsing:
    """Test C struct parsing."""

    def test_parse_simple_struct(self, c_analyzer: CAnalyzer, tmp_path: Path) -> None:
        """Test parsing a simple struct."""
        if not c_analyzer.available:
            pytest.skip("tree_sitter_languages not available")

        c_file = tmp_path / "struct.c"
        c_file.write_text("""
struct Point {
    int x;
    int y;
};
""")
        result = c_analyzer.parse(c_file)
        assert len(result.errors) == 0

        structs = [s for s in result.symbols if s.kind == SymbolKind.CLASS]
        assert len(structs) == 1
        assert structs[0].name == "Point"

    def test_parse_typedef_struct(self, c_analyzer: CAnalyzer, tmp_path: Path) -> None:
        """Test parsing typedef'd struct."""
        if not c_analyzer.available:
            pytest.skip("tree_sitter_languages not available")

        c_file = tmp_path / "typedef_struct.c"
        c_file.write_text("""
typedef struct {
    int x;
    int y;
} Point;

typedef struct Node {
    int value;
    struct Node* next;
} Node;
""")
        result = c_analyzer.parse(c_file)
        assert len(result.errors) == 0

        types = [s for s in result.symbols if s.kind == SymbolKind.CLASS]
        # Should find Point typedef and Node struct/typedef
        assert len(types) >= 1


class TestCEnumParsing:
    """Test C enum parsing."""

    def test_parse_simple_enum(self, c_analyzer: CAnalyzer, tmp_path: Path) -> None:
        """Test parsing a simple enum."""
        if not c_analyzer.available:
            pytest.skip("tree_sitter_languages not available")

        c_file = tmp_path / "enum.c"
        c_file.write_text("""
enum Color {
    RED,
    GREEN,
    BLUE
};
""")
        result = c_analyzer.parse(c_file)
        assert len(result.errors) == 0

        enums = [s for s in result.symbols if s.kind == SymbolKind.CLASS and s.name == "Color"]
        assert len(enums) == 1


class TestCDocstrings:
    """Test docstring extraction from C comments."""

    def test_parse_function_with_line_comment(self, c_analyzer: CAnalyzer, tmp_path: Path) -> None:
        """Test extracting // comments as docstrings."""
        if not c_analyzer.available:
            pytest.skip("tree_sitter_languages not available")

        c_file = tmp_path / "comments.c"
        c_file.write_text("""
// Adds two integers together
int add(int a, int b) {
    return a + b;
}
""")
        result = c_analyzer.parse(c_file)
        assert len(result.errors) == 0

        functions = [s for s in result.symbols if s.kind == SymbolKind.FUNCTION]
        assert len(functions) == 1
        assert functions[0].docstring == "Adds two integers together"

    def test_parse_function_with_block_comment(self, c_analyzer: CAnalyzer, tmp_path: Path) -> None:
        """Test extracting /* */ comments as docstrings."""
        if not c_analyzer.available:
            pytest.skip("tree_sitter_languages not available")

        c_file = tmp_path / "block_comments.c"
        c_file.write_text("""
/* Multiplies two numbers */
int multiply(int a, int b) {
    return a * b;
}
""")
        result = c_analyzer.parse(c_file)
        assert len(result.errors) == 0

        functions = [s for s in result.symbols if s.kind == SymbolKind.FUNCTION]
        assert len(functions) == 1
        assert functions[0].docstring is not None
        assert "Multiplies" in functions[0].docstring


class TestCppSpecificFeatures:
    """Test C++ specific features."""

    def test_parse_cpp_class(self, cpp_analyzer: CAnalyzer, tmp_path: Path) -> None:
        """Test parsing a C++ class."""
        if not cpp_analyzer.available:
            pytest.skip("tree_sitter_languages not available")

        cpp_file = tmp_path / "class.cpp"
        cpp_file.write_text("""
class Calculator {
public:
    int add(int a, int b) {
        return a + b;
    }

    int subtract(int a, int b) {
        return a - b;
    }
};
""")
        result = cpp_analyzer.parse(cpp_file)
        assert len(result.errors) == 0

        classes = [s for s in result.symbols if s.kind == SymbolKind.CLASS]
        assert len(classes) >= 1
        assert any(c.name == "Calculator" for c in classes)

    def test_parse_cpp_namespace(self, cpp_analyzer: CAnalyzer, tmp_path: Path) -> None:
        """Test parsing C++ namespace."""
        if not cpp_analyzer.available:
            pytest.skip("tree_sitter_languages not available")

        cpp_file = tmp_path / "namespace.cpp"
        cpp_file.write_text("""
namespace math {
    int add(int a, int b) {
        return a + b;
    }
}
""")
        result = cpp_analyzer.parse(cpp_file)
        assert len(result.errors) == 0

        # Namespace detection may vary - at minimum should find the function inside
        # Namespaces are stored with SymbolKind.CLASS

        # Should find at least the add function
        functions = [s for s in result.symbols if s.kind == SymbolKind.FUNCTION]
        assert len(functions) >= 1
        assert any(f.name == "add" for f in functions)

    def test_parse_cpp_class_with_methods(self, cpp_analyzer: CAnalyzer, tmp_path: Path) -> None:
        """Test parsing C++ class methods."""
        if not cpp_analyzer.available:
            pytest.skip("tree_sitter_languages not available")

        cpp_file = tmp_path / "methods.cpp"
        cpp_file.write_text("""
class Point {
public:
    Point(int x, int y) : x_(x), y_(y) {}

    int getX() const { return x_; }
    int getY() const { return y_; }

private:
    int x_;
    int y_;
};
""")
        result = cpp_analyzer.parse(cpp_file)
        assert len(result.errors) == 0

        # Should find Point class
        classes = [s for s in result.symbols if s.name == "Point" and s.kind == SymbolKind.CLASS]
        assert len(classes) == 1


class TestCAnalyzerEdgeCases:
    """Test edge cases and error handling."""

    def test_parse_empty_file(self, c_analyzer: CAnalyzer, tmp_path: Path) -> None:
        """Test parsing an empty C file."""
        if not c_analyzer.available:
            pytest.skip("tree_sitter_languages not available")

        c_file = tmp_path / "empty.c"
        c_file.write_text("")
        result = c_analyzer.parse(c_file)
        assert len(result.errors) == 0
        assert len(result.symbols) == 0

    def test_parse_file_with_only_comments(self, c_analyzer: CAnalyzer, tmp_path: Path) -> None:
        """Test parsing a file with only comments."""
        if not c_analyzer.available:
            pytest.skip("tree_sitter_languages not available")

        c_file = tmp_path / "comments_only.c"
        c_file.write_text("""
// This is a comment
/* This is a block comment */
/*
 * Multi-line
 * block comment
 */
""")
        result = c_analyzer.parse(c_file)
        assert len(result.errors) == 0
        assert len(result.symbols) == 0

    def test_parse_file_with_preprocessor_directives(self, c_analyzer: CAnalyzer, tmp_path: Path) -> None:
        """Test parsing file with preprocessor directives."""
        if not c_analyzer.available:
            pytest.skip("tree_sitter_languages not available")

        c_file = tmp_path / "preprocessor.c"
        c_file.write_text("""
#include <stdio.h>
#include <stdlib.h>

#define MAX_SIZE 100

#ifdef DEBUG
void debug_print(const char* msg) {
    printf("%s\\n", msg);
}
#endif

int main(void) {
    return 0;
}
""")
        result = c_analyzer.parse(c_file)
        assert len(result.errors) == 0

        # Should find main function
        functions = [s for s in result.symbols if s.kind == SymbolKind.FUNCTION]
        assert any(f.name == "main" for f in functions)

    def test_parse_complex_declarations(self, c_analyzer: CAnalyzer, tmp_path: Path) -> None:
        """Test parsing complex C declarations."""
        if not c_analyzer.available:
            pytest.skip("tree_sitter_languages not available")

        c_file = tmp_path / "complex.c"
        c_file.write_text("""
// Function pointer type
typedef int (*callback_t)(int, int);

// Static function
static int helper(int x) {
    return x * 2;
}

// Function with static storage
int process(int value) {
    static int count = 0;
    count++;
    return value + count;
}
""")
        result = c_analyzer.parse(c_file)
        assert len(result.errors) == 0

        functions = [s for s in result.symbols if s.kind == SymbolKind.FUNCTION]
        names = {f.name for f in functions}
        assert "helper" in names or "process" in names

    def test_analyzer_without_tree_sitter(self, tmp_path: Path) -> None:
        """Test analyzer behavior when tree_sitter is not available."""
        # Create analyzer and mock unavailability
        analyzer = CAnalyzer()
        analyzer.parser_wrapper = None
        analyzer.available = False

        c_file = tmp_path / "test.c"
        c_file.write_text("int main() { return 0; }")

        result = analyzer.parse(c_file)
        # Should have degraded mode error
        assert len(result.errors) > 0
        assert "tree_sitter_languages no disponible" in result.errors[0].message
