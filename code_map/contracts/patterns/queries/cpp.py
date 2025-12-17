# SPDX-License-Identifier: MIT
"""
Tree-sitter query helpers for C++ analysis.

Provides utilities for navigating and extracting information from
C++ AST nodes parsed by tree-sitter.
"""

from dataclasses import dataclass
from typing import Iterator, List, Optional

from tree_sitter import Node


@dataclass
class FieldInfo:
    """Information about a class field/member."""

    name: str
    type_name: str
    is_pointer: bool
    is_reference: bool
    template_name: Optional[str]  # e.g., "unique_ptr", "atomic"
    template_args: List[str]  # e.g., ["ILogger"] for unique_ptr<ILogger>
    line: int
    node: Node


@dataclass
class MethodInfo:
    """Information about a class method."""

    name: str
    return_type: Optional[str]
    parameters: List["ParameterInfo"]
    is_virtual: bool
    is_override: bool
    is_const: bool
    line: int
    node: Node


@dataclass
class ParameterInfo:
    """Information about a function parameter."""

    name: str
    type_name: str
    is_pointer: bool
    is_reference: bool
    is_const: bool


class CppQueryHelper:
    """Helper class for querying C++ AST nodes."""

    # Template types that indicate ownership
    SMART_POINTER_TYPES = {"unique_ptr", "shared_ptr", "weak_ptr"}
    ATOMIC_TYPES = {"atomic"}
    CONTAINER_TYPES = {"vector", "map", "set", "unordered_map", "unordered_set", "list", "deque"}

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
        """Find all class/struct declarations in the AST."""
        yield from self._find_nodes_by_type(root, ("class_specifier", "struct_specifier"))

    def find_field_declarations(self, class_node: Node) -> Iterator[FieldInfo]:
        """
        Find all field declarations within a class.

        Args:
            class_node: A class_specifier or struct_specifier node

        Yields:
            FieldInfo for each field found
        """
        # Find the field_declaration_list (class body)
        body = None
        for child in class_node.children:
            if child.type == "field_declaration_list":
                body = child
                break

        if body is None:
            return

        for node in body.children:
            if node.type == "field_declaration":
                # Skip if this is actually a method declaration
                if self._has_function_declarator(node):
                    continue
                field_info = self._parse_field_declaration(node)
                if field_info:
                    yield field_info

    def find_methods(self, class_node: Node) -> Iterator[MethodInfo]:
        """
        Find all method declarations within a class.

        Args:
            class_node: A class_specifier or struct_specifier node

        Yields:
            MethodInfo for each method found
        """
        body = None
        for child in class_node.children:
            if child.type == "field_declaration_list":
                body = child
                break

        if body is None:
            return

        for node in body.children:
            if node.type == "function_definition":
                method_info = self._parse_method(node)
                if method_info:
                    yield method_info
            elif node.type == "declaration":
                # Method declaration (not definition)
                method_info = self._parse_method_declaration(node)
                if method_info:
                    yield method_info
            elif node.type == "field_declaration":
                # Could be a method declaration (void foo();) or a field
                # Check if it has a function_declarator child
                if self._has_function_declarator(node):
                    method_info = self._parse_field_as_method(node)
                    if method_info:
                        yield method_info

    def find_constructors(self, class_node: Node) -> Iterator[MethodInfo]:
        """
        Find constructor declarations/definitions.

        Args:
            class_node: A class_specifier or struct_specifier node

        Yields:
            MethodInfo for each constructor
        """
        class_name = self._get_class_name(class_node)
        if not class_name:
            return

        for method in self.find_methods(class_node):
            # Constructor has same name as class and no return type
            if method.name == class_name and method.return_type is None:
                yield method

    def get_class_name(self, class_node: Node) -> Optional[str]:
        """Get the name of a class/struct."""
        return self._get_class_name(class_node)

    def _get_class_name(self, class_node: Node) -> Optional[str]:
        """Extract class name from class_specifier."""
        for child in class_node.children:
            if child.type == "type_identifier":
                return self.get_node_text(child)
        return None

    def _parse_field_declaration(self, node: Node) -> Optional[FieldInfo]:
        """Parse a field_declaration node into FieldInfo."""
        type_node = None
        declarator_node = None
        template_name = None
        template_args = []
        is_pointer = False
        is_reference = False

        for child in node.children:
            if child.type == "qualified_identifier":
                type_node = child
                # Check if qualified_identifier contains a template_type (e.g., std::unique_ptr<T>)
                template_type = self._find_template_in_qualified(child)
                if template_type:
                    template_name, template_args = self._parse_template_type(template_type)
            elif child.type in ("type_identifier", "primitive_type"):
                type_node = child
            elif child.type == "template_type":
                type_node = child
                template_name, template_args = self._parse_template_type(child)
            elif child.type == "field_identifier":
                declarator_node = child
            elif child.type == "pointer_declarator":
                is_pointer = True
                # Find the actual identifier inside
                declarator_node = self._find_identifier_in_declarator(child)
            elif child.type == "reference_declarator":
                is_reference = True
                declarator_node = self._find_identifier_in_declarator(child)

        if type_node is None or declarator_node is None:
            return None

        type_name = self.get_node_text(type_node)
        field_name = self.get_node_text(declarator_node)

        # Clean up field name (remove trailing underscore patterns like name_)
        field_name = field_name.strip()

        return FieldInfo(
            name=field_name,
            type_name=type_name,
            is_pointer=is_pointer,
            is_reference=is_reference,
            template_name=template_name,
            template_args=template_args,
            line=node.start_point[0] + 1,
            node=node,
        )

    def _find_template_in_qualified(self, node: Node) -> Optional[Node]:
        """
        Find template_type within a qualified_identifier.

        For types like std::unique_ptr<T>, the AST structure is:
        qualified_identifier
          namespace_identifier: std
          ::
          template_type
            type_identifier: unique_ptr
            template_argument_list: <T>
        """
        for child in node.children:
            if child.type == "template_type":
                return child
        return None

    def _parse_template_type(self, node: Node) -> tuple[Optional[str], List[str]]:
        """
        Parse a template_type node.

        Returns:
            Tuple of (template_name, [template_arguments])
        """
        template_name = None
        template_args = []

        for child in node.children:
            if child.type == "type_identifier":
                template_name = self.get_node_text(child)
            elif child.type == "template_argument_list":
                for arg in child.children:
                    if arg.type == "type_descriptor":
                        # Get the type inside the descriptor
                        for sub in arg.children:
                            if sub.type in ("type_identifier", "primitive_type", "qualified_identifier"):
                                template_args.append(self.get_node_text(sub))
                                break

        return template_name, template_args

    def _parse_method(self, node: Node) -> Optional[MethodInfo]:
        """Parse a function_definition node into MethodInfo."""
        return_type = None
        name = None
        parameters = []
        is_virtual = False
        is_override = False
        is_const = False

        # Check for virtual specifier
        for child in node.children:
            if child.type == "virtual":
                is_virtual = True
            elif child.type in ("type_identifier", "primitive_type"):
                return_type = self.get_node_text(child)
            elif child.type == "function_declarator":
                name, parameters, is_const = self._parse_function_declarator(child)
            elif child.type == "virtual_specifier":
                text = self.get_node_text(child)
                if "override" in text:
                    is_override = True

        if name is None:
            return None

        return MethodInfo(
            name=name,
            return_type=return_type,
            parameters=parameters,
            is_virtual=is_virtual,
            is_override=is_override,
            is_const=is_const,
            line=node.start_point[0] + 1,
            node=node,
        )

    def _parse_method_declaration(self, node: Node) -> Optional[MethodInfo]:
        """Parse a declaration node that contains a method declaration."""
        return_type = None
        name = None
        parameters = []
        is_virtual = False
        is_override = False
        is_const = False

        for child in node.children:
            if child.type == "virtual":
                is_virtual = True
            elif child.type in ("type_identifier", "primitive_type"):
                return_type = self.get_node_text(child)
            elif child.type == "function_declarator":
                name, parameters, is_const = self._parse_function_declarator(child)
            elif child.type == "virtual_specifier":
                text = self.get_node_text(child)
                if "override" in text:
                    is_override = True

        if name is None:
            return None

        return MethodInfo(
            name=name,
            return_type=return_type,
            parameters=parameters,
            is_virtual=is_virtual,
            is_override=is_override,
            is_const=is_const,
            line=node.start_point[0] + 1,
            node=node,
        )

    def _has_function_declarator(self, node: Node) -> bool:
        """Check if a field_declaration contains a function_declarator (is a method)."""
        for child in node.children:
            if child.type == "function_declarator":
                return True
        return False

    def _parse_field_as_method(self, node: Node) -> Optional[MethodInfo]:
        """
        Parse a field_declaration that is actually a method declaration.

        This handles cases like:
            void start();
            void stop() override;
        """
        return_type = None
        name = None
        parameters = []
        is_virtual = False
        is_override = False
        is_const = False

        for child in node.children:
            if child.type == "virtual":
                is_virtual = True
            elif child.type in ("type_identifier", "primitive_type"):
                return_type = self.get_node_text(child)
            elif child.type == "function_declarator":
                name, parameters, is_const = self._parse_function_declarator(child)
            elif child.type == "virtual_specifier":
                text = self.get_node_text(child)
                if "override" in text:
                    is_override = True

        if name is None:
            return None

        return MethodInfo(
            name=name,
            return_type=return_type,
            parameters=parameters,
            is_virtual=is_virtual,
            is_override=is_override,
            is_const=is_const,
            line=node.start_point[0] + 1,
            node=node,
        )

    def _parse_function_declarator(self, node: Node) -> tuple[Optional[str], List[ParameterInfo], bool]:
        """
        Parse function_declarator to extract name, parameters, and const qualifier.

        Returns:
            Tuple of (name, parameters, is_const)
        """
        name = None
        parameters = []
        is_const = False

        for child in node.children:
            if child.type == "identifier":
                name = self.get_node_text(child)
            elif child.type == "field_identifier":
                name = self.get_node_text(child)
            elif child.type == "parameter_list":
                parameters = self._parse_parameter_list(child)
            elif child.type == "type_qualifier" and self.get_node_text(child) == "const":
                is_const = True

        return name, parameters, is_const

    def _parse_parameter_list(self, node: Node) -> List[ParameterInfo]:
        """Parse parameter_list into list of ParameterInfo."""
        parameters = []

        for child in node.children:
            if child.type == "parameter_declaration":
                param = self._parse_parameter(child)
                if param:
                    parameters.append(param)

        return parameters

    def _parse_parameter(self, node: Node) -> Optional[ParameterInfo]:
        """Parse a single parameter_declaration."""
        type_name = None
        param_name = None
        is_pointer = False
        is_reference = False
        is_const = False

        for child in node.children:
            if child.type == "type_qualifier" and self.get_node_text(child) == "const":
                is_const = True
            elif child.type in ("type_identifier", "primitive_type", "qualified_identifier"):
                type_name = self.get_node_text(child)
            elif child.type == "template_type":
                type_name = self.get_node_text(child)
            elif child.type == "pointer_declarator":
                is_pointer = True
                param_name = self._get_identifier_from_declarator(child)
            elif child.type == "reference_declarator":
                is_reference = True
                param_name = self._get_identifier_from_declarator(child)
            elif child.type == "identifier":
                param_name = self.get_node_text(child)

        if type_name is None:
            return None

        return ParameterInfo(
            name=param_name or "",
            type_name=type_name,
            is_pointer=is_pointer,
            is_reference=is_reference,
            is_const=is_const,
        )

    def _find_identifier_in_declarator(self, node: Node) -> Optional[Node]:
        """Recursively find the identifier within a declarator."""
        for child in node.children:
            if child.type in ("field_identifier", "identifier"):
                return child
            result = self._find_identifier_in_declarator(child)
            if result:
                return result
        return None

    def _get_identifier_from_declarator(self, node: Node) -> Optional[str]:
        """Get identifier text from a declarator node."""
        id_node = self._find_identifier_in_declarator(node)
        if id_node:
            return self.get_node_text(id_node)
        return None

    def _find_nodes_by_type(self, root: Node, types: tuple[str, ...]) -> Iterator[Node]:
        """Recursively find all nodes of given types."""
        if root.type in types:
            yield root
        for child in root.children:
            yield from self._find_nodes_by_type(child, types)
