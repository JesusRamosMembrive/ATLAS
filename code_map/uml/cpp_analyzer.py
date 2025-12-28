# SPDX-License-Identifier: MIT
"""
C++ analyzer for UML extraction using tree-sitter.

Extracts classes, structs, methods, attributes for UML diagram generation.
Supports .cpp, .hpp, .h, .cc, .cxx files.
Uses shared TreeSitterMixin for parser initialization and tree traversal.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..analysis import TreeSitterMixin
from .models import AttributeInfo, ClassModel, MethodInfo


@dataclass
class CppStructModel:
    """Represents a C++ struct."""

    name: str
    module: str
    file: Path
    attributes: List[AttributeInfo] = field(default_factory=list)
    methods: List[MethodInfo] = field(default_factory=list)
    docstring: Optional[str] = None


@dataclass
class CppModuleModel:
    """Extended module model for C++."""

    name: str
    file: Path
    includes: Dict[str, str] = field(default_factory=dict)
    classes: Dict[str, ClassModel] = field(default_factory=dict)
    structs: Dict[str, CppStructModel] = field(default_factory=dict)
    namespaces: List[str] = field(default_factory=list)


class UMLCppAnalyzer(TreeSitterMixin):
    """
    Analyzes C++ files for UML extraction.

    Inherits from TreeSitterMixin for shared parser initialization and tree traversal.
    """

    # Tree-sitter language name
    LANGUAGE: str = "cpp"

    # C++ extensions we support
    EXTENSIONS = {".cpp", ".hpp", ".h", ".cc", ".cxx", ".hxx", ".c++", ".h++"}

    def __init__(self, module: str, file_path: Path) -> None:
        # Initialize TreeSitterMixin
        super().__init__()

        self.module = module
        self.file_path = file_path
        self.model = CppModuleModel(name=module, file=file_path)
        self._current_class: Optional[ClassModel] = None
        self._current_struct: Optional[CppStructModel] = None
        self._current_visibility: str = "public"  # Default for structs
        self._current_namespace: List[str] = []

    @property
    def available(self) -> bool:
        """Check if tree-sitter is available for parsing."""
        return self.is_available()

    def parse(self) -> CppModuleModel:
        """Parse the C++ file and extract UML-relevant information."""
        if not self._ensure_parser():
            return self.model

        try:
            source = self.file_path.read_text(encoding="utf-8")
        except OSError:
            return self.model

        tree = self._parser.parse(bytes(source, "utf-8"))
        lines = source.splitlines()
        self._visit_node(tree.root_node, lines)
        return self.model

    def _visit_node(self, node: Any, lines: List[str]) -> None:
        """Recursively visit tree-sitter nodes."""
        if node.type == "class_specifier":
            self._handle_class(node, lines)
        elif node.type == "struct_specifier":
            self._handle_struct(node, lines)
        elif node.type == "namespace_definition":
            self._handle_namespace(node, lines)
        elif node.type == "preproc_include":
            self._handle_include(node)
        else:
            for child in node.children:
                self._visit_node(child, lines)

    def _handle_namespace(self, node: Any, lines: List[str]) -> None:
        """Handle namespace and parse its contents."""
        name = None
        for child in node.children:
            if child.type == "namespace_identifier":
                name = child.text.decode("utf-8")
                break
            elif child.type == "identifier":
                name = child.text.decode("utf-8")
                break

        if name:
            self._current_namespace.append(name)
            self.model.namespaces.append("::".join(self._current_namespace))

        # Visit namespace body
        body = self._find_child_by_type(node, "declaration_list")
        if body:
            for child in body.children:
                self._visit_node(child, lines)

        if name:
            self._current_namespace.pop()

    def _handle_class(self, node: Any, lines: List[str]) -> None:
        """Extract class information."""
        name = self._get_type_identifier(node)
        if not name:
            return

        # Get base classes
        bases: List[str] = []
        base_clause = self._find_child_by_type(node, "base_class_clause")
        if base_clause:
            for child in base_clause.children:
                if child.type == "base_class_specifier":
                    base_name = self._extract_base_class_name(child)
                    if base_name:
                        bases.append(base_name)

        # Check for abstract (has pure virtual methods - we'll detect this later)
        is_abstract = False

        # Get docstring from preceding comment
        docstring = self._find_leading_comment(node, lines)

        # Add namespace prefix if applicable
        full_name = name
        if self._current_namespace:
            full_name = "::".join(self._current_namespace) + "::" + name

        model = ClassModel(
            name=full_name,
            module=self.module,
            file=self.file_path,
            bases=bases,
            is_abstract=is_abstract,
            docstring=docstring,
        )
        self.model.classes[full_name] = model

        # Parse class body
        body = self._find_child_by_type(node, "field_declaration_list")
        if body:
            self._current_class = model
            self._current_visibility = "private"  # Default for C++ classes
            for child in body.children:
                if child.type == "access_specifier":
                    self._handle_access_specifier(child)
                elif child.type == "function_definition":
                    self._handle_method_definition(child, lines)
                elif child.type == "declaration":
                    self._handle_member_declaration(child, lines)
                elif child.type == "field_declaration":
                    self._handle_field_declaration(child, lines)

            # Mark as abstract if has any pure virtual method
            if any(m.is_abstract for m in model.methods):
                model.is_abstract = True

            self._current_class = None

    def _handle_struct(self, node: Any, lines: List[str]) -> None:
        """Extract struct information (similar to class but public by default)."""
        name = self._get_type_identifier(node)
        if not name:
            return

        docstring = self._find_leading_comment(node, lines)

        # Add namespace prefix if applicable
        full_name = name
        if self._current_namespace:
            full_name = "::".join(self._current_namespace) + "::" + name

        model = CppStructModel(
            name=full_name,
            module=self.module,
            file=self.file_path,
            docstring=docstring,
        )
        self.model.structs[full_name] = model

        # Parse struct body
        body = self._find_child_by_type(node, "field_declaration_list")
        if body:
            self._current_struct = model
            self._current_visibility = "public"  # Default for C++ structs
            for child in body.children:
                if child.type == "access_specifier":
                    self._handle_access_specifier(child)
                elif child.type == "function_definition":
                    self._handle_struct_method(child, lines)
                elif child.type == "declaration":
                    self._handle_struct_member(child, lines)
                elif child.type == "field_declaration":
                    self._handle_struct_field(child, lines)
            self._current_struct = None

    def _handle_access_specifier(self, node: Any) -> None:
        """Update current visibility based on access specifier."""
        for child in node.children:
            if child.type in ("public", "private", "protected"):
                self._current_visibility = child.type

    def _handle_method_definition(self, node: Any, lines: List[str]) -> None:
        """Extract method from function_definition in class body."""
        if not self._current_class:
            return

        method_info = self._extract_method_info(node, lines)
        if method_info:
            self._current_class.methods.append(method_info)

    def _handle_member_declaration(self, node: Any, lines: List[str]) -> None:
        """Handle declaration inside class (could be method declaration or field)."""
        if not self._current_class:
            return

        # Check if it's a function declaration
        declarator = self._find_child_by_type(node, "function_declarator")
        if declarator:
            method_info = self._extract_method_from_declaration(node, lines)
            if method_info:
                self._current_class.methods.append(method_info)
        else:
            # It's a field declaration
            self._handle_field_declaration(node, lines)

    def _handle_field_declaration(self, node: Any, lines: List[str]) -> None:
        """Extract field/attribute from class."""
        if not self._current_class:
            return

        attr_info = self._extract_attribute_info(node, lines)
        if attr_info:
            self._current_class.attributes.append(attr_info)

    def _handle_struct_method(self, node: Any, lines: List[str]) -> None:
        """Extract method from struct."""
        if not self._current_struct:
            return

        method_info = self._extract_method_info(node, lines)
        if method_info:
            self._current_struct.methods.append(method_info)

    def _handle_struct_member(self, node: Any, lines: List[str]) -> None:
        """Handle declaration inside struct."""
        if not self._current_struct:
            return

        declarator = self._find_child_by_type(node, "function_declarator")
        if declarator:
            method_info = self._extract_method_from_declaration(node, lines)
            if method_info:
                self._current_struct.methods.append(method_info)
        else:
            self._handle_struct_field(node, lines)

    def _handle_struct_field(self, node: Any, lines: List[str]) -> None:
        """Extract field from struct."""
        if not self._current_struct:
            return

        attr_info = self._extract_attribute_info(node, lines)
        if attr_info:
            self._current_struct.attributes.append(attr_info)

    def _extract_method_info(self, node: Any, lines: List[str]) -> Optional[MethodInfo]:
        """Extract method information from function_definition."""
        # Get declarator
        declarator = self._find_child_by_type(node, "function_declarator")
        if not declarator:
            return None

        name = self._get_function_name(declarator)
        if not name:
            return None

        # Check for virtual, static, const
        is_static = False
        is_virtual = False
        is_abstract = False  # pure virtual = 0

        for child in node.children:
            if child.type == "storage_class_specifier":
                if child.text.decode("utf-8") == "static":
                    is_static = True
            elif child.type == "virtual":
                is_virtual = True
            elif child.type == "virtual_function_specifier":
                # Check for pure virtual (= 0)
                text = child.text.decode("utf-8")
                if "= 0" in text or text == "0":
                    is_abstract = True

        # Check for "= 0" indicating pure virtual
        for child in node.children:
            if child.type == "pure_virtual_clause":
                is_abstract = True

        # Get return type
        returns = self._extract_return_type(node)

        # Get parameters
        params = self._extract_parameters(declarator)

        # Get docstring
        docstring = self._find_leading_comment(node, lines)

        return MethodInfo(
            name=name,
            parameters=params,
            returns=returns,
            visibility=self._current_visibility,
            is_static=is_static,
            is_async=False,  # C++ doesn't have async in same way
            is_abstract=is_abstract,
            is_virtual=is_virtual,
            is_pure_virtual=is_abstract,
            docstring=docstring,
        )

    def _extract_method_from_declaration(
        self, node: Any, lines: List[str]
    ) -> Optional[MethodInfo]:
        """Extract method info from a declaration (prototype)."""
        declarator = self._find_child_by_type(node, "function_declarator")
        if not declarator:
            # Try to find it recursively
            for child in node.children:
                if child.type == "init_declarator":
                    declarator = self._find_child_by_type(child, "function_declarator")
                    if declarator:
                        break

        if not declarator:
            return None

        name = self._get_function_name(declarator)
        if not name:
            return None

        is_static = False
        is_virtual = False
        is_abstract = False

        for child in node.children:
            if child.type == "storage_class_specifier":
                if child.text.decode("utf-8") == "static":
                    is_static = True
            elif child.type == "virtual":
                is_virtual = True
            elif child.type == "virtual_function_specifier":
                is_abstract = True

        # Check for pure virtual (= 0) in the declaration
        node_text = node.text.decode("utf-8")
        if "= 0" in node_text:
            is_abstract = True

        returns = self._extract_return_type(node)
        params = self._extract_parameters(declarator)
        docstring = self._find_leading_comment(node, lines)

        return MethodInfo(
            name=name,
            parameters=params,
            returns=returns,
            visibility=self._current_visibility,
            is_static=is_static,
            is_async=False,
            is_abstract=is_abstract,
            is_virtual=is_virtual,
            is_pure_virtual=is_abstract,
            docstring=docstring,
        )

    def _extract_attribute_info(
        self, node: Any, lines: List[str]
    ) -> Optional[AttributeInfo]:
        """Extract attribute/field information."""
        # Get type
        type_str = self._extract_field_type(node)

        # Get name(s) from declarator
        name = None
        is_static = False

        for child in node.children:
            if child.type == "storage_class_specifier":
                if child.text.decode("utf-8") == "static":
                    is_static = True
            elif child.type in ("identifier", "field_identifier"):
                name = child.text.decode("utf-8")
            elif child.type == "init_declarator":
                for sub in child.children:
                    if sub.type in ("identifier", "field_identifier"):
                        name = sub.text.decode("utf-8")
                        break

        if not name:
            return None

        return AttributeInfo(
            name=name,
            annotation=type_str,
            optional=False,
            visibility=self._current_visibility,
            is_static=is_static,
            is_readonly=False,
        )

    def _handle_include(self, node: Any) -> None:
        """Track include directives."""
        for child in node.children:
            if child.type == "string_literal":
                include_path = child.text.decode("utf-8").strip('"')
                self.model.includes[include_path] = include_path
            elif child.type == "system_lib_string":
                include_path = child.text.decode("utf-8").strip("<>")
                self.model.includes[include_path] = include_path

    def _get_type_identifier(self, node: Any) -> Optional[str]:
        """Get type identifier from class/struct specifier."""
        for child in node.children:
            if child.type == "type_identifier":
                return child.text.decode("utf-8")
        return None

    def _get_function_name(self, declarator: Any) -> Optional[str]:
        """Get function name from declarator."""
        for child in declarator.children:
            if child.type in ("identifier", "field_identifier"):
                return child.text.decode("utf-8")
            elif child.type == "destructor_name":
                return child.text.decode("utf-8")
            elif child.type == "operator_name":
                return child.text.decode("utf-8")
            elif child.type == "qualified_identifier":
                # Get the last part
                for sub in reversed(child.children):
                    if sub.type in ("identifier", "field_identifier"):
                        return sub.text.decode("utf-8")
        return None

    # Note: _find_child_by_type is inherited from TreeSitterMixin

    def _extract_base_class_name(self, node: Any) -> Optional[str]:
        """Extract base class name from base_class_specifier."""
        for child in node.children:
            if child.type == "type_identifier":
                return child.text.decode("utf-8")
            elif child.type == "qualified_identifier":
                return child.text.decode("utf-8")
            elif child.type == "template_type":
                # Get the template name
                for sub in child.children:
                    if sub.type == "type_identifier":
                        return sub.text.decode("utf-8")
        return None

    def _extract_return_type(self, node: Any) -> Optional[str]:
        """Extract return type from function definition or declaration."""
        for child in node.children:
            if child.type in ("type_identifier", "primitive_type"):
                return child.text.decode("utf-8")
            elif child.type == "qualified_identifier":
                return child.text.decode("utf-8")
            elif child.type == "template_type":
                return child.text.decode("utf-8")
            elif child.type == "pointer_declarator":
                # Handle pointer return types
                for sub in child.children:
                    if sub.type in ("type_identifier", "primitive_type"):
                        return sub.text.decode("utf-8") + "*"
        return None

    def _extract_field_type(self, node: Any) -> Optional[str]:
        """Extract type from field declaration."""
        for child in node.children:
            if child.type in ("type_identifier", "primitive_type"):
                return child.text.decode("utf-8")
            elif child.type == "qualified_identifier":
                return child.text.decode("utf-8")
            elif child.type == "template_type":
                return child.text.decode("utf-8")
        return None

    def _extract_parameters(self, declarator: Any) -> List[str]:
        """Extract parameter names from function declarator."""
        params: List[str] = []
        param_list = self._find_child_by_type(declarator, "parameter_list")
        if param_list:
            for child in param_list.children:
                if child.type == "parameter_declaration":
                    name = self._get_parameter_name(child)
                    if name:
                        params.append(name)
        return params

    def _get_parameter_name(self, node: Any) -> Optional[str]:
        """Get parameter name from parameter_declaration."""
        for child in node.children:
            if child.type in ("identifier", "field_identifier"):
                return child.text.decode("utf-8")
            elif child.type == "pointer_declarator":
                for sub in child.children:
                    if sub.type in ("identifier", "field_identifier"):
                        return sub.text.decode("utf-8")
            elif child.type == "reference_declarator":
                for sub in child.children:
                    if sub.type in ("identifier", "field_identifier"):
                        return sub.text.decode("utf-8")
        return None

    def _find_leading_comment(self, node: Any, lines: List[str]) -> Optional[str]:
        """Find comment/docstring preceding a node."""
        start_line = node.start_point[0]
        if start_line == 0:
            return None

        # Look for comment in previous lines
        comments: List[str] = []
        for i in range(start_line - 1, max(0, start_line - 10), -1):
            line = lines[i].strip()
            if line.startswith("//"):
                comments.insert(0, line[2:].strip())
            elif line.startswith("/*"):
                # Multi-line comment
                comment_text = line[2:].rstrip("*/").strip()
                if comment_text:
                    comments.insert(0, comment_text)
                break
            elif line.startswith("*"):
                # Middle of multi-line comment
                comment_text = line[1:].strip()
                if comment_text and not comment_text.startswith("/"):
                    comments.insert(0, comment_text)
            elif line.endswith("*/"):
                # End of multi-line comment, look for start
                pass
            elif line == "":
                continue
            else:
                break

        return " ".join(comments) if comments else None
