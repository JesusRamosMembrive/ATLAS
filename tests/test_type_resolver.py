# SPDX-License-Identifier: MIT
"""
Tests for the TypeResolver module.

Tests type inference from:
1. Constructor assignments: loader = FileLoader()
2. Type annotations: loader: FileLoader = ...
3. Return types: result = get_loader() where get_loader() -> FileLoader
"""

import pytest
from textwrap import dedent


# Skip all tests if tree-sitter is not available
pytest.importorskip("tree_sitter")
pytest.importorskip("tree_sitter_languages")


from code_map.graph_analysis.call_flow.type_resolver import (  # noqa: E402
    TypeResolver,
)


@pytest.fixture
def parser():
    """Create a tree-sitter parser for Python."""
    import tree_sitter
    import tree_sitter_languages
    import warnings

    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=FutureWarning)
        language = tree_sitter_languages.get_language("python")

    p = tree_sitter.Parser()
    p.set_language(language)
    return p


@pytest.fixture
def resolver(parser, tmp_path):
    """Create a TypeResolver instance."""
    return TypeResolver(tmp_path, parser)


class TestConstructorAssignments:
    """Tests for constructor assignment type inference."""

    def test_simple_constructor(self, resolver, parser, tmp_path):
        """loader = FileLoader() -> loader is FileLoader."""
        source = dedent(
            """
            def process():
                loader = FileLoader()
                loader.load()
        """
        )

        tree = parser.parse(bytes(source, "utf-8"))
        func_node = self._find_function(tree.root_node, "process")

        scope = resolver.analyze_scope(func_node, source, tmp_path / "test.py")

        assert "loader" in scope.variables
        assert scope.variables["loader"].name == "FileLoader"
        assert scope.variables["loader"].source == "constructor"

    def test_constructor_with_args(self, resolver, parser, tmp_path):
        """client = HttpClient("https://api.example.com") -> client is HttpClient."""
        source = dedent(
            """
            def connect():
                client = HttpClient("https://api.example.com")
                client.get("/users")
        """
        )

        tree = parser.parse(bytes(source, "utf-8"))
        func_node = self._find_function(tree.root_node, "connect")

        scope = resolver.analyze_scope(func_node, source, tmp_path / "test.py")

        assert "client" in scope.variables
        assert scope.variables["client"].name == "HttpClient"

    def test_lowercase_call_not_constructor(self, resolver, parser, tmp_path):
        """result = process_data() should NOT be inferred (not PascalCase)."""
        source = dedent(
            """
            def main():
                result = process_data()
        """
        )

        tree = parser.parse(bytes(source, "utf-8"))
        func_node = self._find_function(tree.root_node, "main")

        scope = resolver.analyze_scope(func_node, source, tmp_path / "test.py")

        assert "result" not in scope.variables

    def test_builtin_type_excluded(self, resolver, parser, tmp_path):
        """data = dict() should NOT create a TypeInfo for dict."""
        source = dedent(
            """
            def init():
                data = dict()
                items = list()
        """
        )

        tree = parser.parse(bytes(source, "utf-8"))
        func_node = self._find_function(tree.root_node, "init")

        scope = resolver.analyze_scope(func_node, source, tmp_path / "test.py")

        # Builtins should not be tracked
        assert "data" not in scope.variables
        assert "items" not in scope.variables

    def _find_function(self, root, name):
        """Find a function node by name."""
        for child in self._walk(root):
            if child.type == "function_definition":
                for c in child.children:
                    if c.type == "identifier":
                        if c.text.decode("utf-8") == name:
                            return child
        return None

    def _walk(self, node):
        yield node
        for child in node.children:
            yield from self._walk(child)


class TestTypeAnnotations:
    """Tests for type annotation inference."""

    def test_annotated_parameter(self, resolver, parser, tmp_path):
        """def foo(loader: FileLoader) -> loader is FileLoader."""
        source = dedent(
            """
            def process(loader: FileLoader):
                loader.load()
        """
        )

        tree = parser.parse(bytes(source, "utf-8"))
        func_node = self._find_function(tree.root_node, "process")

        scope = resolver.analyze_scope(func_node, source, tmp_path / "test.py")

        assert "loader" in scope.parameters
        assert scope.parameters["loader"].name == "FileLoader"
        assert scope.parameters["loader"].source == "parameter"

    def test_annotated_parameter_with_default(self, resolver, parser, tmp_path):
        """def foo(loader: FileLoader = None) -> loader is FileLoader."""
        source = dedent(
            """
            def process(loader: FileLoader = None):
                if loader:
                    loader.load()
        """
        )

        tree = parser.parse(bytes(source, "utf-8"))
        func_node = self._find_function(tree.root_node, "process")

        scope = resolver.analyze_scope(func_node, source, tmp_path / "test.py")

        assert "loader" in scope.parameters
        assert scope.parameters["loader"].name == "FileLoader"

    def test_self_parameter_excluded(self, resolver, parser, tmp_path):
        """self should not be tracked as a typed parameter."""
        source = dedent(
            """
            def process(self, data: DataLoader):
                data.load()
        """
        )

        tree = parser.parse(bytes(source, "utf-8"))
        func_node = self._find_function(tree.root_node, "process")

        scope = resolver.analyze_scope(func_node, source, tmp_path / "test.py")

        assert "self" not in scope.parameters
        assert "data" in scope.parameters

    def test_optional_type_extracts_base(self, resolver, parser, tmp_path):
        """def foo(x: Optional[FileLoader]) -> x is FileLoader (base type)."""
        source = dedent(
            """
            def process(loader: Optional[FileLoader]):
                if loader:
                    loader.load()
        """
        )

        tree = parser.parse(bytes(source, "utf-8"))
        func_node = self._find_function(tree.root_node, "process")

        scope = resolver.analyze_scope(func_node, source, tmp_path / "test.py")

        assert "loader" in scope.parameters
        assert scope.parameters["loader"].name == "FileLoader"

    def _find_function(self, root, name):
        """Find a function node by name."""
        for child in self._walk(root):
            if child.type == "function_definition":
                for c in child.children:
                    if c.type == "identifier":
                        if c.text.decode("utf-8") == name:
                            return child
        return None

    def _walk(self, node):
        yield node
        for child in node.children:
            yield from self._walk(child)


class TestReturnTypeInference:
    """Tests for return type inference."""

    def test_return_type_extraction(self, resolver, parser, tmp_path):
        """def get_loader() -> FileLoader should be extracted."""
        source = dedent(
            """
            def get_loader() -> FileLoader:
                return FileLoader()

            def process():
                loader = get_loader()
                loader.load()
        """
        )

        return_types = resolver._get_return_types_for_file(tmp_path / "test.py", source)

        assert "get_loader" in return_types
        assert return_types["get_loader"] == "FileLoader"

    def test_return_type_assignment_inference(self, resolver, parser, tmp_path):
        """result = get_loader() where get_loader() -> FileLoader."""
        source = dedent(
            """
            def get_loader() -> FileLoader:
                return FileLoader()

            def process():
                loader = get_loader()
                loader.load()
        """
        )

        tree = parser.parse(bytes(source, "utf-8"))
        func_node = self._find_function(tree.root_node, "process")

        scope = resolver.analyze_scope(func_node, source, tmp_path / "test.py")

        assert "loader" in scope.variables
        assert scope.variables["loader"].name == "FileLoader"
        assert scope.variables["loader"].source == "return_type"

    def test_return_type_optional(self, resolver, parser, tmp_path):
        """def get_data() -> Optional[DataLoader] extracts DataLoader."""
        source = dedent(
            """
            def get_data() -> Optional[DataLoader]:
                return None

            def process():
                data = get_data()
        """
        )

        return_types = resolver._get_return_types_for_file(tmp_path / "test.py", source)

        assert "get_data" in return_types
        # The return type should be the full annotation
        assert "DataLoader" in return_types["get_data"]

    def _find_function(self, root, name):
        """Find a function node by name."""
        for child in self._walk(root):
            if child.type == "function_definition":
                for c in child.children:
                    if c.type == "identifier":
                        if c.text.decode("utf-8") == name:
                            return child
        return None

    def _walk(self, node):
        yield node
        for child in node.children:
            yield from self._walk(child)


class TestTypePriority:
    """Tests for type priority: annotation > constructor > return_type."""

    def test_annotation_overrides_constructor(self, resolver, parser, tmp_path):
        """If annotation exists, it should win over constructor inference."""
        source = dedent(
            """
            def process():
                loader: BaseLoader = FileLoader()
                loader.load()
        """
        )

        tree = parser.parse(bytes(source, "utf-8"))
        func_node = self._find_function(tree.root_node, "process")

        scope = resolver.analyze_scope(func_node, source, tmp_path / "test.py")

        # Annotation should win
        assert "loader" in scope.variables
        assert scope.variables["loader"].name == "BaseLoader"
        assert scope.variables["loader"].source == "annotation"

    def test_parameter_takes_highest_priority(self, resolver, parser, tmp_path):
        """Parameters should take priority over local variables."""
        source = dedent(
            """
            def process(loader: ParamLoader):
                loader = FileLoader()
                loader.load()
        """
        )

        tree = parser.parse(bytes(source, "utf-8"))
        func_node = self._find_function(tree.root_node, "process")

        scope = resolver.analyze_scope(func_node, source, tmp_path / "test.py")

        # resolve_type should return parameter type
        type_info = resolver.resolve_type("loader", scope)
        assert type_info is not None
        assert type_info.name == "ParamLoader"

    def _find_function(self, root, name):
        """Find a function node by name."""
        for child in self._walk(root):
            if child.type == "function_definition":
                for c in child.children:
                    if c.type == "identifier":
                        if c.text.decode("utf-8") == name:
                            return child
        return None

    def _walk(self, node):
        yield node
        for child in node.children:
            yield from self._walk(child)


class TestResolveType:
    """Tests for the resolve_type method."""

    def test_resolve_type_found(self, resolver, parser, tmp_path):
        """resolve_type returns TypeInfo when type is known."""
        source = dedent(
            """
            def process():
                loader = FileLoader()
                loader.load()
        """
        )

        tree = parser.parse(bytes(source, "utf-8"))
        func_node = self._find_function(tree.root_node, "process")

        scope = resolver.analyze_scope(func_node, source, tmp_path / "test.py")
        type_info = resolver.resolve_type("loader", scope)

        assert type_info is not None
        assert type_info.name == "FileLoader"

    def test_resolve_type_not_found(self, resolver, parser, tmp_path):
        """resolve_type returns None when type is unknown."""
        source = dedent(
            """
            def process():
                result = unknown_function()
        """
        )

        tree = parser.parse(bytes(source, "utf-8"))
        func_node = self._find_function(tree.root_node, "process")

        scope = resolver.analyze_scope(func_node, source, tmp_path / "test.py")
        type_info = resolver.resolve_type("result", scope)

        assert type_info is None

    def _find_function(self, root, name):
        """Find a function node by name."""
        for child in self._walk(root):
            if child.type == "function_definition":
                for c in child.children:
                    if c.type == "identifier":
                        if c.text.decode("utf-8") == name:
                            return child
        return None

    def _walk(self, node):
        yield node
        for child in node.children:
            yield from self._walk(child)


class TestBaseTypeExtraction:
    """Tests for extracting base types from complex type hints."""

    def test_extract_from_optional(self, resolver, parser, tmp_path):
        """Optional[X] -> X."""
        result = resolver._extract_base_type("Optional[FileLoader]")
        assert result == "FileLoader"

    def test_extract_from_union(self, resolver, parser, tmp_path):
        """Union[X, Y] -> X (first type)."""
        result = resolver._extract_base_type("Union[FileLoader, None]")
        assert result == "FileLoader"

    def test_extract_from_pipe_union(self, resolver, parser, tmp_path):
        """X | Y -> X (first type)."""
        result = resolver._extract_base_type("FileLoader | None")
        assert result == "FileLoader"

    def test_extract_from_list(self, resolver, parser, tmp_path):
        """List[X] -> List."""
        result = resolver._extract_base_type("List[FileLoader]")
        assert result == "List"

    def test_plain_type(self, resolver, parser, tmp_path):
        """Plain type returned as-is."""
        result = resolver._extract_base_type("FileLoader")
        assert result == "FileLoader"

    def test_nested_optional(self, resolver, parser, tmp_path):
        """Optional[List[X]] -> List."""
        result = resolver._extract_base_type("Optional[List[FileLoader]]")
        assert result == "List"


class TestIsClassName:
    """Tests for class name detection."""

    def test_pascal_case_is_class(self, resolver, parser, tmp_path):
        """PascalCase names are classes."""
        assert resolver._is_class_name("FileLoader") is True
        assert resolver._is_class_name("HttpClient") is True
        assert resolver._is_class_name("XMLParser") is True

    def test_lowercase_not_class(self, resolver, parser, tmp_path):
        """Lowercase names are not classes."""
        assert resolver._is_class_name("process") is False
        assert resolver._is_class_name("get_data") is False

    def test_builtins_excluded(self, resolver, parser, tmp_path):
        """Built-in types are excluded."""
        assert resolver._is_class_name("int") is False
        assert resolver._is_class_name("str") is False
        assert resolver._is_class_name("list") is False
        assert resolver._is_class_name("dict") is False
        assert resolver._is_class_name("List") is False
        assert resolver._is_class_name("Dict") is False
        assert resolver._is_class_name("Optional") is False

    def test_empty_string(self, resolver, parser, tmp_path):
        """Empty string is not a class."""
        assert resolver._is_class_name("") is False
