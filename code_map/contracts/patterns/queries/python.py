# SPDX-License-Identifier: MIT
"""
Tree-sitter query helpers for Python analysis.

Provides utilities for navigating and extracting information from
Python AST nodes parsed by tree-sitter.
"""

from dataclasses import dataclass
from typing import Iterator, List, Optional

from tree_sitter import Node


@dataclass
class FieldInfo:
    """Information about a class field/attribute."""

    name: str
    type_name: Optional[str]
    is_private: bool  # Starts with _
    assigned_from: Optional[str]  # e.g., "threading.Lock()" or parameter name
    line: int
    node: Node


@dataclass
class MethodInfo:
    """Information about a class method."""

    name: str
    parameters: List["ParameterInfo"]
    return_type: Optional[str]
    is_async: bool
    is_property: bool
    is_classmethod: bool
    is_staticmethod: bool
    line: int
    node: Node


@dataclass
class ParameterInfo:
    """Information about a function parameter."""

    name: str
    type_name: Optional[str]
    has_default: bool
    is_self: bool


class PythonQueryHelper:
    """Helper class for querying Python AST nodes."""

    # Threading-related types
    THREAD_TYPES = {"Lock", "RLock", "Condition", "Semaphore", "Event", "Barrier"}
    ASYNC_LOCK_TYPES = {"Lock", "Semaphore", "Event", "Condition"}

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

    def find_class_definitions(self, root: Node) -> Iterator[Node]:
        """Find all class definitions in the AST."""
        yield from self._find_nodes_by_type(root, ("class_definition",))

    def find_field_assignments(self, class_node: Node) -> Iterator[FieldInfo]:
        """
        Find all field assignments within a class (self.x = ...).

        Args:
            class_node: A class_definition node

        Yields:
            FieldInfo for each field found
        """
        # Find __init__ method first
        init_method = None
        for method in self.find_methods(class_node):
            if method.name == "__init__":
                init_method = method
                break

        if init_method is None:
            return

        # Find assignments in __init__ body
        body = self._find_method_body(init_method.node)
        if body is None:
            return

        for node in self._find_nodes_by_type(body, ("assignment",)):
            field_info = self._parse_field_assignment(node, init_method)
            if field_info:
                yield field_info

    def find_methods(self, class_node: Node) -> Iterator[MethodInfo]:
        """
        Find all method definitions within a class.

        Args:
            class_node: A class_definition node

        Yields:
            MethodInfo for each method found
        """
        # Find the block (class body)
        body = None
        for child in class_node.children:
            if child.type == "block":
                body = child
                break

        if body is None:
            return

        for node in body.children:
            if node.type == "function_definition":
                method_info = self._parse_method(node)
                if method_info:
                    yield method_info
            elif node.type == "decorated_definition":
                # Handle decorated methods (@property, @classmethod, etc.)
                method_info = self._parse_decorated_method(node)
                if method_info:
                    yield method_info

    def find_constructors(self, class_node: Node) -> Iterator[MethodInfo]:
        """
        Find __init__ method.

        Args:
            class_node: A class_definition node

        Yields:
            MethodInfo for __init__ if found
        """
        for method in self.find_methods(class_node):
            if method.name == "__init__":
                yield method

    def get_class_name(self, class_node: Node) -> Optional[str]:
        """Get the name of a class."""
        for child in class_node.children:
            if child.type == "identifier":
                return self.get_node_text(child)
        return None

    def get_base_classes(self, class_node: Node) -> List[str]:
        """Get base class names from class definition."""
        bases = []
        for child in class_node.children:
            if child.type == "argument_list":
                for arg in child.children:
                    if arg.type == "identifier":
                        bases.append(self.get_node_text(arg))
                    elif arg.type == "attribute":
                        bases.append(self.get_node_text(arg))
        return bases

    def _parse_field_assignment(
        self, node: Node, init_method: MethodInfo
    ) -> Optional[FieldInfo]:
        """Parse an assignment node into FieldInfo if it's a self.x = assignment."""
        # Check if left side is self.something
        left = None
        right = None

        for child in node.children:
            if child.type == "attribute":
                left = child
            elif child.type not in ("=",):
                right = child

        if left is None:
            return None

        # Check if it's self.x pattern
        attr_parts = self._parse_attribute(left)
        if not attr_parts or attr_parts[0] != "self" or len(attr_parts) < 2:
            return None

        field_name = attr_parts[1]
        is_private = field_name.startswith("_")

        # Determine what it's assigned from
        assigned_from = None
        type_name = None

        if right:
            right_text = self.get_node_text(right)
            assigned_from = right_text

            # Check if it's from a parameter
            param_names = [p.name for p in init_method.parameters if not p.is_self]
            if right.type == "identifier" and right_text in param_names:
                # Find type from parameter
                for param in init_method.parameters:
                    if param.name == right_text:
                        type_name = param.type_name
                        break
            elif right.type == "call":
                # e.g., threading.Lock()
                type_name = self._extract_call_type(right)

        return FieldInfo(
            name=field_name,
            type_name=type_name,
            is_private=is_private,
            assigned_from=assigned_from,
            line=node.start_point[0] + 1,
            node=node,
        )

    def _extract_call_type(self, call_node: Node) -> Optional[str]:
        """Extract the type from a call expression like threading.Lock()."""
        for child in call_node.children:
            if child.type == "attribute":
                return self.get_node_text(child)
            elif child.type == "identifier":
                return self.get_node_text(child)
        return None

    def _parse_attribute(self, node: Node) -> List[str]:
        """Parse an attribute node into parts (e.g., self.x -> ['self', 'x'])."""
        parts = []
        current = node

        while current:
            if current.type == "identifier":
                parts.insert(0, self.get_node_text(current))
                break
            elif current.type == "attribute":
                for child in current.children:
                    if child.type == "identifier":
                        parts.insert(0, self.get_node_text(child))
                # Move to the nested attribute/identifier
                for child in current.children:
                    if child.type in ("attribute", "identifier"):
                        current = child
                        break
                else:
                    break
            else:
                break

        return parts

    def _parse_method(self, node: Node) -> Optional[MethodInfo]:
        """Parse a function_definition node into MethodInfo."""
        name = None
        parameters = []
        return_type = None
        is_async = False

        for child in node.children:
            if child.type == "identifier":
                name = self.get_node_text(child)
            elif child.type == "parameters":
                parameters = self._parse_parameters(child)
            elif child.type == "type":
                return_type = self.get_node_text(child)
            elif child.type == "async":
                is_async = True

        if name is None:
            return None

        return MethodInfo(
            name=name,
            parameters=parameters,
            return_type=return_type,
            is_async=is_async,
            is_property=False,
            is_classmethod=False,
            is_staticmethod=False,
            line=node.start_point[0] + 1,
            node=node,
        )

    def _parse_decorated_method(self, node: Node) -> Optional[MethodInfo]:
        """Parse a decorated_definition node."""
        decorators = []
        function_def = None

        for child in node.children:
            if child.type == "decorator":
                dec_name = self._get_decorator_name(child)
                if dec_name:
                    decorators.append(dec_name)
            elif child.type == "function_definition":
                function_def = child

        if function_def is None:
            return None

        method_info = self._parse_method(function_def)
        if method_info is None:
            return None

        # Apply decorator info
        method_info.is_property = "property" in decorators
        method_info.is_classmethod = "classmethod" in decorators
        method_info.is_staticmethod = "staticmethod" in decorators

        return method_info

    def _get_decorator_name(self, decorator_node: Node) -> Optional[str]:
        """Get the name of a decorator."""
        for child in decorator_node.children:
            if child.type == "identifier":
                return self.get_node_text(child)
            elif child.type == "attribute":
                return self.get_node_text(child)
            elif child.type == "call":
                # @decorator(args)
                for sub in child.children:
                    if sub.type in ("identifier", "attribute"):
                        return self.get_node_text(sub)
        return None

    def _parse_parameters(self, node: Node) -> List[ParameterInfo]:
        """Parse parameters node into list of ParameterInfo."""
        parameters = []

        for child in node.children:
            if child.type == "identifier":
                # Simple parameter like 'self'
                name = self.get_node_text(child)
                parameters.append(
                    ParameterInfo(
                        name=name,
                        type_name=None,
                        has_default=False,
                        is_self=name == "self",
                    )
                )
            elif child.type == "typed_parameter":
                param = self._parse_typed_parameter(child)
                if param:
                    parameters.append(param)
            elif child.type == "default_parameter":
                param = self._parse_default_parameter(child)
                if param:
                    parameters.append(param)
            elif child.type == "typed_default_parameter":
                param = self._parse_typed_default_parameter(child)
                if param:
                    parameters.append(param)

        return parameters

    def _parse_typed_parameter(self, node: Node) -> Optional[ParameterInfo]:
        """Parse typed_parameter: name: Type."""
        name = None
        type_name = None

        for child in node.children:
            if child.type == "identifier":
                name = self.get_node_text(child)
            elif child.type == "type":
                type_name = self.get_node_text(child)

        if name is None:
            return None

        return ParameterInfo(
            name=name,
            type_name=type_name,
            has_default=False,
            is_self=name == "self",
        )

    def _parse_default_parameter(self, node: Node) -> Optional[ParameterInfo]:
        """Parse default_parameter: name=value."""
        name = None

        for child in node.children:
            if child.type == "identifier":
                name = self.get_node_text(child)
                break

        if name is None:
            return None

        return ParameterInfo(
            name=name,
            type_name=None,
            has_default=True,
            is_self=False,
        )

    def _parse_typed_default_parameter(self, node: Node) -> Optional[ParameterInfo]:
        """Parse typed_default_parameter: name: Type = value."""
        name = None
        type_name = None

        for child in node.children:
            if child.type == "identifier":
                name = self.get_node_text(child)
            elif child.type == "type":
                type_name = self.get_node_text(child)

        if name is None:
            return None

        return ParameterInfo(
            name=name,
            type_name=type_name,
            has_default=True,
            is_self=False,
        )

    def _find_method_body(self, method_node: Node) -> Optional[Node]:
        """Find the block (body) of a method."""
        for child in method_node.children:
            if child.type == "block":
                return child
        return None

    def _find_nodes_by_type(self, root: Node, types: tuple[str, ...]) -> Iterator[Node]:
        """Recursively find all nodes of given types."""
        if root.type in types:
            yield root
        for child in root.children:
            yield from self._find_nodes_by_type(child, types)
