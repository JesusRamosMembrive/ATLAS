# SPDX-License-Identifier: MIT
"""
Type inference resolver for Call Flow analysis.

Provides local type inference for Python code to resolve obj.method() calls
by tracking:
1. Constructor assignments: loader = FileLoader()
2. Type annotations: loader: FileLoader = ...
3. Return types: result = get_loader() where get_loader() -> FileLoader
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Set

logger = logging.getLogger(__name__)


@dataclass
class TypeInfo:
    """Information about an inferred type."""

    name: str  # Type name (e.g., "FileLoader")
    module: Optional[str] = None  # Module where type is defined
    file_path: Optional[Path] = None  # File where the class is defined
    confidence: float = 1.0  # 0.0-1.0 confidence in inference
    source: str = "unknown"  # "constructor" | "annotation" | "return_type" | "parameter"


@dataclass
class ScopeInfo:
    """Type information for a function scope."""

    variables: Dict[str, TypeInfo] = field(default_factory=dict)
    parameters: Dict[str, TypeInfo] = field(default_factory=dict)


class TypeResolver:
    """
    Resolves types of local variables and parameters.

    Uses tree-sitter to analyze Python code and infer types from:
    - Constructor calls: x = SomeClass()
    - Type annotations: x: SomeClass = ...
    - Function return types: result = func() where func() -> SomeClass

    Example:
        >>> resolver = TypeResolver(Path("/project"), parser)
        >>> scope = resolver.analyze_scope(func_node, source, file_path)
        >>> type_info = scope.variables.get("loader")
        >>> if type_info:
        ...     print(f"loader has type {type_info.name}")
    """

    # Pattern to detect PascalCase class names
    _CLASS_NAME_PATTERN = re.compile(r"^[A-Z][a-zA-Z0-9]*$")

    def __init__(self, project_root: Path, parser: Any) -> None:
        """
        Initialize the type resolver.

        Args:
            project_root: Root path of the project for resolving imports
            parser: tree-sitter parser instance
        """
        self.root = project_root
        self.parser = parser
        # Cache of return types: {file_path: {func_name: return_type}}
        self._return_type_cache: Dict[Path, Dict[str, str]] = {}
        # Cache of class definitions: {file_path: {class_name: line_number}}
        self._class_cache: Dict[Path, Dict[str, int]] = {}

    def analyze_scope(
        self,
        func_node: Any,
        source: str,
        file_path: Path,
        imports: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> ScopeInfo:
        """
        Analyze a function scope and extract type information.

        Args:
            func_node: tree-sitter node for the function definition
            source: Full source code of the file
            file_path: Path to the file being analyzed
            imports: Optional pre-extracted import information

        Returns:
            ScopeInfo with variables and parameters type mappings
        """
        scope = ScopeInfo()

        # Extract parameter types from function signature
        self._extract_parameter_types(func_node, source, scope)

        # Find function body
        body = self._find_child_by_type(func_node, "block")
        if body is None:
            return scope

        # Extract return types for the file (cached)
        return_types = dict(self._get_return_types_for_file(file_path, source))

        # Also extract return types from imported functions
        if imports:
            imported_return_types = self._get_imported_return_types(imports, file_path.parent)
            return_types.update(imported_return_types)

        # Extract type annotations from function body
        self._extract_type_annotations(body, source, scope)

        # Extract constructor assignments from function body
        self._extract_constructor_assignments(body, source, scope)

        # Extract return type assignments (x = func() where func() -> Type)
        self._extract_return_type_assignments(body, source, return_types, scope)

        return scope

    def resolve_type(
        self,
        var_name: str,
        scope: ScopeInfo,
    ) -> Optional[TypeInfo]:
        """
        Resolve the type of a variable in a scope.

        Priority: parameters > annotations > constructor assignments

        Args:
            var_name: Variable name to resolve
            scope: Scope information from analyze_scope()

        Returns:
            TypeInfo if type could be resolved, None otherwise
        """
        # Check parameters first (highest priority)
        if var_name in scope.parameters:
            return scope.parameters[var_name]

        # Then check variables (annotations take priority over constructors)
        if var_name in scope.variables:
            return scope.variables[var_name]

        return None

    def _extract_parameter_types(
        self,
        func_node: Any,
        source: str,
        scope: ScopeInfo,
    ) -> None:
        """Extract type annotations from function parameters."""
        # Find parameters node
        params = self._find_child_by_type(func_node, "parameters")
        if params is None:
            return

        for child in params.children:
            if child.type == "typed_parameter":
                # parameter: Type
                name = None
                type_hint = None

                for subchild in child.children:
                    if subchild.type == "identifier":
                        name = self._get_node_text(subchild, source)
                    elif subchild.type == "type":
                        type_hint = self._get_node_text(subchild, source)

                if name and type_hint and name != "self":
                    # Extract base type name (strip Optional[], List[], etc.)
                    base_type = self._extract_base_type(type_hint)
                    if base_type and self._is_class_name(base_type):
                        scope.parameters[name] = TypeInfo(
                            name=base_type,
                            confidence=1.0,
                            source="parameter",
                        )

            elif child.type == "typed_default_parameter":
                # parameter: Type = default
                name = None
                type_hint = None

                for subchild in child.children:
                    if subchild.type == "identifier":
                        if name is None:
                            name = self._get_node_text(subchild, source)
                    elif subchild.type == "type":
                        type_hint = self._get_node_text(subchild, source)

                if name and type_hint and name != "self":
                    base_type = self._extract_base_type(type_hint)
                    if base_type and self._is_class_name(base_type):
                        scope.parameters[name] = TypeInfo(
                            name=base_type,
                            confidence=1.0,
                            source="parameter",
                        )

    def _extract_type_annotations(
        self,
        body: Any,
        source: str,
        scope: ScopeInfo,
    ) -> None:
        """Extract type annotations from variable declarations."""
        for node in self._walk_tree(body):
            # x: Type = value  or  x: Type
            if node.type == "expression_statement":
                for child in node.children:
                    if child.type == "assignment":
                        # Check if it's an annotated assignment
                        self._process_annotated_assignment(child, source, scope)

    def _process_annotated_assignment(
        self,
        node: Any,
        source: str,
        scope: ScopeInfo,
    ) -> None:
        """Process a potentially annotated assignment."""
        # In tree-sitter Python, annotated assignments look like:
        # assignment: left=identifier, ":", type, "=", right=expression

        # Find identifier and type children
        identifier = None
        type_annotation = None

        for child in node.children:
            if child.type == "identifier" and identifier is None:
                identifier = self._get_node_text(child, source)
            elif child.type == "type":
                type_annotation = self._get_node_text(child, source)

        if identifier and type_annotation:
            base_type = self._extract_base_type(type_annotation)
            if base_type and self._is_class_name(base_type):
                # Annotations have higher confidence than constructor inference
                scope.variables[identifier] = TypeInfo(
                    name=base_type,
                    confidence=1.0,
                    source="annotation",
                )

    def _extract_constructor_assignments(
        self,
        body: Any,
        source: str,
        scope: ScopeInfo,
    ) -> None:
        """
        Extract constructor assignments: x = ClassName()

        Only processes simple identifier = Call() patterns where
        the call target looks like a class name (PascalCase).
        """
        for node in self._walk_tree(body):
            if node.type == "assignment":
                # Get left side (target)
                left = None
                right = None

                children = list(node.children)
                for i, child in enumerate(children):
                    if child.type == "identifier" and left is None:
                        left = self._get_node_text(child, source)
                    elif child.type == "=":
                        # Next non-whitespace child is the value
                        for j in range(i + 1, len(children)):
                            if children[j].type not in ("comment",):
                                right = children[j]
                                break

                if left and right and right.type == "call":
                    # Get the call target
                    call_target = self._get_call_target(right, source)
                    if call_target and self._is_class_name(call_target):
                        # Don't override annotation types (lower confidence)
                        if left not in scope.variables:
                            scope.variables[left] = TypeInfo(
                                name=call_target,
                                confidence=0.9,  # Slightly lower than annotation
                                source="constructor",
                            )

    def _extract_return_type_assignments(
        self,
        body: Any,
        source: str,
        return_types: Dict[str, str],
        scope: ScopeInfo,
    ) -> None:
        """
        Extract assignments where the RHS is a function call with known return type.

        Example: result = get_loader() where get_loader() -> FileLoader
        """
        if not return_types:
            return

        for node in self._walk_tree(body):
            if node.type == "assignment":
                left = None
                right = None

                children = list(node.children)
                for i, child in enumerate(children):
                    if child.type == "identifier" and left is None:
                        left = self._get_node_text(child, source)
                    elif child.type == "=":
                        for j in range(i + 1, len(children)):
                            if children[j].type not in ("comment",):
                                right = children[j]
                                break

                if left and right and right.type == "call":
                    call_target = self._get_call_target(right, source)
                    if call_target and call_target in return_types:
                        return_type = return_types[call_target]
                        base_type = self._extract_base_type(return_type)
                        if base_type and self._is_class_name(base_type):
                            # Don't override higher confidence types
                            if left not in scope.variables:
                                scope.variables[left] = TypeInfo(
                                    name=base_type,
                                    confidence=0.8,  # Lower than constructor
                                    source="return_type",
                                )

    def _get_return_types_for_file(
        self,
        file_path: Path,
        source: str,
    ) -> Dict[str, str]:
        """
        Get return types for all functions in a file (cached).

        Args:
            file_path: Path to the file
            source: Source code of the file

        Returns:
            Dict mapping function names to return type strings
        """
        if file_path in self._return_type_cache:
            return self._return_type_cache[file_path]

        return_types: Dict[str, str] = {}
        tree = self.parser.parse(bytes(source, "utf-8"))

        for node in self._walk_tree(tree.root_node):
            if node.type == "function_definition":
                func_name = self._get_function_name(node)
                return_type = self._get_return_type_annotation(node, source)
                if func_name and return_type:
                    return_types[func_name] = return_type

        self._return_type_cache[file_path] = return_types
        return return_types

    def _get_imported_return_types(
        self,
        imports: Dict[str, Dict[str, Any]],
        current_dir: Path,
    ) -> Dict[str, str]:
        """
        Get return types for imported functions.

        Args:
            imports: Dict mapping imported names to import info
            current_dir: Current directory for resolving relative imports

        Returns:
            Dict mapping imported function names to their return type strings
        """
        return_types: Dict[str, str] = {}

        for name, import_info in imports.items():
            # Skip if not a 'from' import (regular imports are modules, not functions)
            if import_info.get("type") != "from":
                continue

            module_name = import_info.get("module")
            if not module_name:
                continue

            # Resolve module to file path
            resolved_file = self._resolve_import_path(module_name, current_dir)
            if not resolved_file or not resolved_file.exists():
                continue

            try:
                # Load and parse the imported file
                source = resolved_file.read_text(encoding="utf-8")
                original_name = import_info.get("original_name", name)

                # Get return types from the imported file
                file_return_types = self._get_return_types_for_file(resolved_file, source)

                # If the original function has a return type, add it
                if original_name in file_return_types:
                    # Map using the imported name (which might be an alias)
                    return_types[name] = file_return_types[original_name]
            except OSError:
                logger.debug("Could not read imported file: %s", resolved_file)

        return return_types

    def _resolve_import_path(
        self,
        module_name: str,
        current_dir: Path,
    ) -> Optional[Path]:
        """
        Resolve a module name to a file path.

        Args:
            module_name: Module name (e.g., 'loader' or 'package.module')
            current_dir: Current directory for context

        Returns:
            Resolved Path or None if not found
        """
        # Handle relative imports
        if module_name.startswith("."):
            dots = 0
            for c in module_name:
                if c == ".":
                    dots += 1
                else:
                    break

            base_dir = current_dir
            for _ in range(dots - 1):
                base_dir = base_dir.parent

            remaining = module_name[dots:]
            if remaining:
                module_path = remaining.replace(".", "/")
                candidate = base_dir / f"{module_path}.py"
                if candidate.exists():
                    return candidate
                candidate = base_dir / module_path / "__init__.py"
                if candidate.exists():
                    return candidate
            return None

        # Absolute import - try relative to project root and current dir
        module_path = module_name.replace(".", "/")

        # Try relative to project root
        candidate = self.root / f"{module_path}.py"
        if candidate.exists():
            return candidate
        candidate = self.root / module_path / "__init__.py"
        if candidate.exists():
            return candidate

        # Try relative to current directory
        candidate = current_dir / f"{module_path}.py"
        if candidate.exists():
            return candidate
        candidate = current_dir / module_path / "__init__.py"
        if candidate.exists():
            return candidate

        return None

    def _get_return_type_annotation(
        self,
        func_node: Any,
        source: str,
    ) -> Optional[str]:
        """Extract return type annotation from a function definition."""
        # Look for return_type child (the "-> Type" part)
        for child in func_node.children:
            if child.type == "type":
                return self._get_node_text(child, source)
        return None

    def _get_call_target(self, call_node: Any, source: str) -> Optional[str]:
        """Get the target name of a call expression."""
        if not call_node.children:
            return None

        func = call_node.children[0]
        if func.type == "identifier":
            return self._get_node_text(func, source)
        elif func.type == "attribute":
            # For x.method(), return just "method" for now
            # Full attribute chain resolution is Phase 3
            parts = self._parse_attribute_chain(func, source)
            if parts:
                return parts[-1]
        return None

    def _parse_attribute_chain(self, node: Any, source: str) -> List[str]:
        """Parse attribute chain like self.loader.load into ['self', 'loader', 'load']."""
        parts: List[str] = []

        def extract_parts(n: Any) -> None:
            if n.type == "identifier":
                parts.append(self._get_node_text(n, source))
            elif n.type == "attribute":
                for child in n.children:
                    if child.type != ".":
                        extract_parts(child)

        extract_parts(node)
        return parts

    def _extract_base_type(self, type_hint: str) -> Optional[str]:
        """
        Extract base type from a type hint.

        Handles: Optional[X] -> X, List[X] -> List, Dict[K,V] -> Dict,
                 Union[X,Y] -> X (first), X | Y -> X (first)
        """
        if not type_hint:
            return None

        type_hint = type_hint.strip()

        # Handle Optional[X] -> X
        if type_hint.startswith("Optional[") and type_hint.endswith("]"):
            inner = type_hint[9:-1]
            return self._extract_base_type(inner)

        # Handle Union[X, Y] or X | Y -> take first type
        if type_hint.startswith("Union[") and type_hint.endswith("]"):
            inner = type_hint[6:-1]
            # Get first type before comma
            first = inner.split(",")[0].strip()
            return self._extract_base_type(first)

        if "|" in type_hint:
            first = type_hint.split("|")[0].strip()
            return self._extract_base_type(first)

        # Handle List[X], Dict[K,V], etc. -> return container type
        if "[" in type_hint:
            base = type_hint.split("[")[0].strip()
            return base

        # Plain type name
        return type_hint

    def _is_class_name(self, name: str) -> bool:
        """
        Check if a name looks like a class name (PascalCase).

        Returns False for:
        - Built-in types (int, str, bool, etc.)
        - lowercase names
        - Names starting with underscore
        """
        if not name:
            return False

        # Built-in types that aren't classes we want to track
        builtins = {
            "int",
            "str",
            "bool",
            "float",
            "list",
            "dict",
            "set",
            "tuple",
            "bytes",
            "None",
            "type",
            "object",
            "Any",
            "List",
            "Dict",
            "Set",
            "Tuple",
            "Optional",
            "Union",
            "Callable",
            "Iterator",
            "Iterable",
            "Type",
            "Sequence",
            "Mapping",
        }
        if name in builtins:
            return False

        # Must be PascalCase
        return bool(self._CLASS_NAME_PATTERN.match(name))

    def _walk_tree(self, node: Any) -> Iterator[Any]:
        """Walk tree-sitter tree yielding all nodes."""
        yield node
        for child in node.children:
            yield from self._walk_tree(child)

    def _find_child_by_type(self, node: Any, type_name: str) -> Optional[Any]:
        """Find first direct child of given type."""
        for child in node.children:
            if child.type == type_name:
                return child
        return None

    def _get_node_text(self, node: Any, source: str) -> str:
        """Get the source text for a node."""
        if hasattr(node, "text"):
            text = node.text
            if isinstance(text, bytes):
                return text.decode("utf-8")
            return text
        start = node.start_byte
        end = node.end_byte
        return source[start:end]

    def _get_function_name(self, node: Any) -> Optional[str]:
        """Extract function name from function_definition node."""
        for child in node.children:
            if child.type == "identifier":
                text = child.text
                if isinstance(text, bytes):
                    return text.decode("utf-8")
                return text
        return None

    def clear_cache(self) -> None:
        """Clear all cached data."""
        self._return_type_cache.clear()
        self._class_cache.clear()
