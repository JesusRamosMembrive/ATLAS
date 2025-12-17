# SPDX-License-Identifier: MIT
"""
Tree-sitter query helpers for TypeScript/JavaScript analysis.

Provides utilities for navigating and extracting information from
TypeScript/JavaScript AST nodes parsed by tree-sitter.
"""

from dataclasses import dataclass
from typing import Iterator, List, Optional

from tree_sitter import Node


@dataclass
class FieldInfo:
    """Information about a class field/property."""

    name: str
    type_name: Optional[str]
    is_private: bool
    is_readonly: bool
    is_optional: bool
    accessibility: Optional[str]  # "public", "private", "protected"
    line: int
    node: Node


@dataclass
class MethodInfo:
    """Information about a class method."""

    name: str
    parameters: List["ParameterInfo"]
    return_type: Optional[str]
    is_async: bool
    is_static: bool
    is_constructor: bool
    accessibility: Optional[str]
    line: int
    node: Node


@dataclass
class ParameterInfo:
    """Information about a function parameter."""

    name: str
    type_name: Optional[str]
    is_optional: bool
    is_readonly: bool
    accessibility: Optional[str]  # For constructor parameter properties


class TypeScriptQueryHelper:
    """Helper class for querying TypeScript/JavaScript AST nodes."""

    def __init__(self, source: str):
        """
        Initialize helper with source code.

        Args:
            source: Original source code for text extraction
        """
        self.source = source
        self._source_lines = source.split("\n")

    def get_node_text(self, node: Node) -> str:
        """Extract text from a node using byte positions."""
        return self.source[node.start_byte : node.end_byte]

    def find_class_declarations(self, root: Node) -> Iterator[Node]:
        """Find all class declarations in the AST."""
        # Only look for class_declaration, not the "class" keyword
        yield from self._find_nodes_by_type(root, ("class_declaration",))

    def find_field_definitions(self, class_node: Node) -> Iterator[FieldInfo]:
        """
        Find all field definitions within a class.

        Args:
            class_node: A class_declaration node

        Yields:
            FieldInfo for each field found
        """
        body = self._find_class_body(class_node)
        if body is None:
            return

        for node in body.children:
            if node.type == "public_field_definition":
                field_info = self._parse_field_definition(node)
                if field_info:
                    yield field_info
            elif node.type == "field_definition":
                field_info = self._parse_field_definition(node)
                if field_info:
                    yield field_info

    def find_methods(self, class_node: Node) -> Iterator[MethodInfo]:
        """
        Find all method definitions within a class.

        Args:
            class_node: A class_declaration node

        Yields:
            MethodInfo for each method found
        """
        body = self._find_class_body(class_node)
        if body is None:
            return

        for node in body.children:
            if node.type == "method_definition":
                method_info = self._parse_method(node)
                if method_info:
                    yield method_info

    def find_constructors(self, class_node: Node) -> Iterator[MethodInfo]:
        """
        Find constructor method.

        Args:
            class_node: A class_declaration node

        Yields:
            MethodInfo for constructor if found
        """
        for method in self.find_methods(class_node):
            if method.is_constructor:
                yield method

    def get_class_name(self, class_node: Node) -> Optional[str]:
        """Get the name of a class."""
        for child in class_node.children:
            if child.type == "type_identifier":
                return self.get_node_text(child)
            elif child.type == "identifier":
                return self.get_node_text(child)
        return None

    def get_base_classes(self, class_node: Node) -> List[str]:
        """Get base class names from extends clause."""
        bases = []
        for child in class_node.children:
            if child.type == "class_heritage":
                for heritage_child in child.children:
                    if heritage_child.type == "extends_clause":
                        for ext_child in heritage_child.children:
                            if ext_child.type in ("type_identifier", "identifier"):
                                bases.append(self.get_node_text(ext_child))
        return bases

    def get_implemented_interfaces(self, class_node: Node) -> List[str]:
        """Get implemented interface names from implements clause."""
        interfaces = []
        for child in class_node.children:
            if child.type == "class_heritage":
                for heritage_child in child.children:
                    if heritage_child.type == "implements_clause":
                        for impl_child in heritage_child.children:
                            if impl_child.type in ("type_identifier", "identifier"):
                                interfaces.append(self.get_node_text(impl_child))
        return interfaces

    def _find_class_body(self, class_node: Node) -> Optional[Node]:
        """Find the class_body node within a class declaration."""
        for child in class_node.children:
            if child.type == "class_body":
                return child
        return None

    def _parse_field_definition(self, node: Node) -> Optional[FieldInfo]:
        """Parse a field definition node into FieldInfo."""
        name = None
        type_name = None
        is_private = False
        is_readonly = False
        is_optional = False
        accessibility = None

        for child in node.children:
            if child.type == "accessibility_modifier":
                accessibility = self.get_node_text(child)
                is_private = accessibility == "private"
            elif child.type == "readonly":
                is_readonly = True
            elif child.type == "property_identifier":
                name = self.get_node_text(child)
            elif child.type == "type_annotation":
                type_name = self._extract_type_from_annotation(child)
            elif child.type == "?":
                is_optional = True

        if name is None:
            return None

        # Check for # prefix (private field)
        if name.startswith("#"):
            is_private = True
            name = name[1:]

        return FieldInfo(
            name=name,
            type_name=type_name,
            is_private=is_private,
            is_readonly=is_readonly,
            is_optional=is_optional,
            accessibility=accessibility,
            line=node.start_point[0] + 1,
            node=node,
        )

    def _parse_method(self, node: Node) -> Optional[MethodInfo]:
        """Parse a method_definition node into MethodInfo."""
        name = None
        parameters = []
        return_type = None
        is_async = False
        is_static = False
        is_constructor = False
        accessibility = None

        for child in node.children:
            if child.type == "accessibility_modifier":
                accessibility = self.get_node_text(child)
            elif child.type == "async":
                is_async = True
            elif child.type == "static":
                is_static = True
            elif child.type == "property_identifier":
                name = self.get_node_text(child)
                is_constructor = name == "constructor"
            elif child.type == "formal_parameters":
                parameters = self._parse_parameters(child)
            elif child.type == "type_annotation":
                return_type = self._extract_type_from_annotation(child)

        if name is None:
            return None

        return MethodInfo(
            name=name,
            parameters=parameters,
            return_type=return_type,
            is_async=is_async,
            is_static=is_static,
            is_constructor=is_constructor,
            accessibility=accessibility,
            line=node.start_point[0] + 1,
            node=node,
        )

    def _parse_parameters(self, node: Node) -> List[ParameterInfo]:
        """Parse formal_parameters into list of ParameterInfo."""
        parameters = []

        for child in node.children:
            if child.type == "required_parameter":
                param = self._parse_parameter(child)
                if param:
                    parameters.append(param)
            elif child.type == "optional_parameter":
                param = self._parse_parameter(child, is_optional=True)
                if param:
                    parameters.append(param)

        return parameters

    def _parse_parameter(
        self, node: Node, is_optional: bool = False
    ) -> Optional[ParameterInfo]:
        """Parse a parameter node."""
        name = None
        type_name = None
        is_readonly = False
        accessibility = None

        for child in node.children:
            if child.type == "accessibility_modifier":
                accessibility = self.get_node_text(child)
            elif child.type == "readonly":
                is_readonly = True
            elif child.type == "identifier":
                name = self.get_node_text(child)
            elif child.type == "type_annotation":
                type_name = self._extract_type_from_annotation(child)
            elif child.type == "?":
                is_optional = True

        if name is None:
            return None

        return ParameterInfo(
            name=name,
            type_name=type_name,
            is_optional=is_optional,
            is_readonly=is_readonly,
            accessibility=accessibility,
        )

    def _extract_type_from_annotation(self, node: Node) -> Optional[str]:
        """Extract type string from a type_annotation node."""
        for child in node.children:
            if child.type in (
                "type_identifier",
                "predefined_type",
                "generic_type",
                "union_type",
                "intersection_type",
                "array_type",
            ):
                return self.get_node_text(child)
        return None

    def _find_nodes_by_type(self, root: Node, types: tuple[str, ...]) -> Iterator[Node]:
        """Recursively find all nodes of given types."""
        if root.type in types:
            yield root
        for child in root.children:
            yield from self._find_nodes_by_type(child, types)
