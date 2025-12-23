# SPDX-License-Identifier: MIT
"""
TypeScript/TSX analyzer for UML extraction using tree-sitter.

Extracts classes, interfaces, methods, attributes for UML diagram generation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from ..dependencies import optional_dependencies
from .models import AttributeInfo, ClassModel, MethodInfo, ModuleModel


@dataclass
class InterfaceModel:
    """Represents a TypeScript interface."""

    name: str
    module: str
    file: Path
    extends: List[str] = field(default_factory=list)
    methods: List[MethodInfo] = field(default_factory=list)
    attributes: List[AttributeInfo] = field(default_factory=list)
    docstring: Optional[str] = None


@dataclass
class TsModuleModel:
    """Extended module model for TypeScript."""

    name: str
    file: Path
    imports: Dict[str, str] = field(default_factory=dict)
    classes: Dict[str, ClassModel] = field(default_factory=dict)
    interfaces: Dict[str, InterfaceModel] = field(default_factory=dict)


class UMLTsAnalyzer:
    """Analyzes TypeScript/TSX files for UML extraction."""

    def __init__(self, module: str, file_path: Path, *, is_tsx: bool = False) -> None:
        self.module = module
        self.file_path = file_path
        self.model = TsModuleModel(name=module, file=file_path)
        self._current_class: Optional[ClassModel] = None
        self._current_interface: Optional[InterfaceModel] = None

        # Initialize tree-sitter parser
        self._modules = optional_dependencies.load("tree_sitter_languages")
        self.parser = None
        if self._modules:
            try:
                parser_cls = getattr(self._modules.get("tree_sitter"), "Parser", None)
                get_language = getattr(
                    self._modules.get("tree_sitter_languages"), "get_language", None
                )
                if parser_cls and get_language:
                    language = get_language("tsx" if is_tsx else "typescript")
                    self.parser = parser_cls()
                    self.parser.set_language(language)
            except Exception:
                self.parser = None

    @property
    def available(self) -> bool:
        return self.parser is not None

    def parse(self) -> TsModuleModel:
        """Parse the TypeScript file and extract UML-relevant information."""
        if not self.parser:
            return self.model

        try:
            source = self.file_path.read_text(encoding="utf-8")
        except OSError:
            return self.model

        tree = self.parser.parse(bytes(source, "utf-8"))
        lines = source.splitlines()
        self._visit_node(tree.root_node, lines)
        return self.model

    def _visit_node(self, node: Any, lines: List[str]) -> None:
        """Recursively visit tree-sitter nodes."""
        if node.type == "class_declaration":
            self._handle_class(node, lines)
        elif node.type == "interface_declaration":
            self._handle_interface(node, lines)
        elif node.type == "import_statement":
            self._handle_import(node)
        else:
            for child in node.children:
                self._visit_node(child, lines)

    def _handle_class(self, node: Any, lines: List[str]) -> None:
        """Extract class information."""
        name = self._get_identifier(node)
        if not name:
            return

        # Get base classes (extends)
        bases: List[str] = []
        implements: List[str] = []
        heritage = self._find_child(node, "class_heritage")
        if heritage:
            for child in heritage.children:
                if child.type == "extends_clause":
                    for type_node in child.children:
                        type_name = self._extract_type_name(type_node)
                        if type_name:
                            bases.append(type_name)
                elif child.type == "implements_clause":
                    for type_node in child.children:
                        type_name = self._extract_type_name(type_node)
                        if type_name:
                            implements.append(type_name)

        # Check for abstract
        is_abstract = any(
            child.type == "abstract" for child in node.children
        )

        # Get docstring
        docstring = self._find_leading_comment(node, lines)

        model = ClassModel(
            name=name,
            module=self.module,
            file=self.file_path,
            bases=bases + implements,  # Combine for now
            is_abstract=is_abstract,
            docstring=docstring,
        )
        self.model.classes[name] = model

        # Parse class body
        body = self._find_child(node, "class_body")
        if body:
            self._current_class = model
            for child in body.children:
                if child.type == "method_definition":
                    self._handle_method(child, lines)
                elif child.type in ("public_field_definition", "property_signature"):
                    self._handle_field(child, lines)
                elif child.type == "field_definition":
                    self._handle_field(child, lines)
            self._current_class = None

    def _handle_interface(self, node: Any, lines: List[str]) -> None:
        """Extract interface information."""
        name = self._get_identifier(node)
        if not name:
            return

        # Get extends
        extends: List[str] = []
        heritage = self._find_child(node, "extends_type_clause")
        if heritage:
            for child in heritage.children:
                type_name = self._extract_type_name(child)
                if type_name:
                    extends.append(type_name)

        docstring = self._find_leading_comment(node, lines)

        model = InterfaceModel(
            name=name,
            module=self.module,
            file=self.file_path,
            extends=extends,
            docstring=docstring,
        )
        self.model.interfaces[name] = model

        # Parse interface body
        body = self._find_child(node, "interface_body") or self._find_child(
            node, "object_type"
        )
        if body:
            self._current_interface = model
            for child in body.children:
                if child.type in ("method_signature", "call_signature"):
                    self._handle_interface_method(child, lines)
                elif child.type == "property_signature":
                    self._handle_interface_property(child, lines)
            self._current_interface = None

    def _handle_method(self, node: Any, lines: List[str]) -> None:
        """Extract method from class."""
        if not self._current_class:
            return

        name = self._get_identifier(node)
        if not name:
            return

        # Detect visibility
        visibility = "public"
        is_static = False
        is_async = False
        is_abstract = False

        for child in node.children:
            if child.type == "accessibility_modifier":
                mod_text = child.text.decode("utf-8")
                if mod_text == "private":
                    visibility = "private"
                elif mod_text == "protected":
                    visibility = "protected"
            elif child.type == "static":
                is_static = True
            elif child.type == "async":
                is_async = True
            elif child.type == "abstract":
                is_abstract = True

        # Get parameters
        params = self._extract_parameters(node)

        # Get return type
        returns = self._extract_return_type(node)

        # Get docstring
        docstring = self._find_leading_comment(node, lines)

        self._current_class.methods.append(
            MethodInfo(
                name=name,
                parameters=params,
                returns=returns,
                visibility=visibility,
                is_static=is_static,
                is_async=is_async,
                is_abstract=is_abstract,
                docstring=docstring,
            )
        )

    def _handle_field(self, node: Any, lines: List[str]) -> None:
        """Extract field/property from class."""
        if not self._current_class:
            return

        name = self._get_identifier(node)
        if not name:
            return

        visibility = "public"
        is_static = False
        is_readonly = False

        for child in node.children:
            if child.type == "accessibility_modifier":
                mod_text = child.text.decode("utf-8")
                if mod_text == "private":
                    visibility = "private"
                elif mod_text == "protected":
                    visibility = "protected"
            elif child.type == "static":
                is_static = True
            elif child.type == "readonly":
                is_readonly = True

        # Get type annotation
        annotation = None
        type_annotation = self._find_child(node, "type_annotation")
        if type_annotation:
            annotation = self._extract_type_from_annotation(type_annotation)

        # Check if optional
        optional = any(child.type == "?" for child in node.children)

        self._current_class.attributes.append(
            AttributeInfo(
                name=name,
                annotation=annotation,
                optional=optional,
                visibility=visibility,
                is_static=is_static,
                is_readonly=is_readonly,
            )
        )

    def _handle_interface_method(self, node: Any, lines: List[str]) -> None:
        """Extract method signature from interface."""
        if not self._current_interface:
            return

        name = self._get_identifier(node)
        if not name:
            return

        params = self._extract_parameters(node)
        returns = self._extract_return_type(node)
        docstring = self._find_leading_comment(node, lines)

        self._current_interface.methods.append(
            MethodInfo(
                name=name,
                parameters=params,
                returns=returns,
                docstring=docstring,
            )
        )

    def _handle_interface_property(self, node: Any, lines: List[str]) -> None:
        """Extract property from interface."""
        if not self._current_interface:
            return

        name = self._get_identifier(node)
        if not name:
            return

        annotation = None
        type_annotation = self._find_child(node, "type_annotation")
        if type_annotation:
            annotation = self._extract_type_from_annotation(type_annotation)

        optional = any(child.type == "?" for child in node.children)

        self._current_interface.attributes.append(
            AttributeInfo(
                name=name,
                annotation=annotation,
                optional=optional,
            )
        )

    def _handle_import(self, node: Any) -> None:
        """Track imports for reference resolution."""
        # Extract imported names
        for child in node.children:
            if child.type == "import_clause":
                for sub in child.children:
                    if sub.type == "identifier":
                        name = sub.text.decode("utf-8")
                        self.model.imports[name] = name
                    elif sub.type == "named_imports":
                        for spec in sub.children:
                            if spec.type == "import_specifier":
                                name = self._get_identifier(spec)
                                if name:
                                    self.model.imports[name] = name

    def _get_identifier(self, node: Any) -> Optional[str]:
        """Get identifier from a node."""
        # Try direct identifier child
        for child in node.children:
            if child.type in ("identifier", "type_identifier", "property_identifier"):
                return child.text.decode("utf-8")
        # Try field name
        name_node = node.child_by_field_name("name")
        if name_node:
            return name_node.text.decode("utf-8")
        return None

    def _find_child(self, node: Any, type_name: str) -> Optional[Any]:
        """Find first child of given type."""
        for child in node.children:
            if child.type == type_name:
                return child
        return None

    def _extract_type_name(self, node: Any) -> Optional[str]:
        """Extract type name from type node."""
        if node.type in ("identifier", "type_identifier"):
            return node.text.decode("utf-8")
        for child in node.children:
            result = self._extract_type_name(child)
            if result:
                return result
        return None

    def _extract_type_from_annotation(self, node: Any) -> Optional[str]:
        """Extract type string from type_annotation node."""
        # Skip the colon
        for child in node.children:
            if child.type != ":":
                return child.text.decode("utf-8")
        return None

    def _extract_parameters(self, node: Any) -> List[str]:
        """Extract parameter names from a method/function."""
        params: List[str] = []
        param_node = self._find_child(node, "formal_parameters")
        if param_node:
            for child in param_node.children:
                if child.type in ("required_parameter", "optional_parameter"):
                    name = self._get_identifier(child)
                    if name and name not in ("this",):
                        params.append(name)
        return params

    def _extract_return_type(self, node: Any) -> Optional[str]:
        """Extract return type from method/function."""
        type_annotation = self._find_child(node, "type_annotation")
        if type_annotation:
            return self._extract_type_from_annotation(type_annotation)
        return None

    def _find_leading_comment(self, node: Any, lines: List[str]) -> Optional[str]:
        """Find JSDoc or comment before a node."""
        start_line = node.start_point[0]
        for offset in range(1, 6):
            index = start_line - offset
            if index < 0:
                break
            text = lines[index].strip()
            # JSDoc style
            if text.endswith("*/"):
                comment_lines: List[str] = []
                j = index
                while j >= 0:
                    line = lines[j].strip()
                    comment_lines.insert(0, line)
                    if line.startswith("/**") or line.startswith("/*"):
                        break
                    j -= 1
                # Clean up
                cleaned = []
                for line in comment_lines:
                    line = line.strip("/* \t")
                    line = line.lstrip("*").strip()
                    if line and not line.startswith("@"):
                        cleaned.append(line)
                return " ".join(cleaned).strip() if cleaned else None
            # Single line comment
            if text.startswith("//"):
                return text[2:].strip()
            # Non-empty, non-comment line means no doc
            if text and not text.startswith("*"):
                break
        return None
