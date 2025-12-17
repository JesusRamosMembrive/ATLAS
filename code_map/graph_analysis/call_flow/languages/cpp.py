# SPDX-License-Identifier: MIT
"""
C++ Call Flow extractor using tree-sitter.

Refactored to use BaseCallFlowExtractor and shared mixins.
Reduces code duplication while maintaining full functionality.

Limitations (by design):
- Header files: Analyzed independently, not as includes
- Namespaces: Basic support, not full resolution
- Templates: Listed as entry points, limited call tracking
- Multiple translation units: Each file analyzed separately
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional, Set, Tuple

from .base_extractor import BaseCallFlowExtractor
from ..models import CallEdge, CallGraph, CallNode, IgnoredCall, ResolutionStatus

logger = logging.getLogger(__name__)


# Common C++ stdlib functions/types to ignore
CPP_STDLIB_FUNCTIONS: Set[str] = {
    # I/O
    "cout", "cin", "cerr", "clog", "endl", "printf", "scanf", "puts", "gets",
    "fprintf", "fscanf", "sprintf", "sscanf", "fopen", "fclose", "fread", "fwrite",
    # Memory
    "malloc", "calloc", "realloc", "free", "new", "delete",
    # String
    "strlen", "strcpy", "strncpy", "strcat", "strcmp", "strncmp", "memcpy", "memset",
    # Math
    "abs", "sqrt", "pow", "sin", "cos", "tan", "log", "exp", "floor", "ceil",
    # STL containers common methods
    "push_back", "pop_back", "push_front", "pop_front", "begin", "end",
    "size", "empty", "clear", "insert", "erase", "find", "front", "back",
    "at", "reserve", "resize", "capacity", "data",
    # STL algorithms
    "sort", "find", "count", "copy", "transform", "accumulate",
    # Utility
    "swap", "move", "forward", "make_pair", "make_tuple", "get",
    "make_unique", "make_shared",
    # Type traits
    "static_cast", "dynamic_cast", "const_cast", "reinterpret_cast",
}

# Common C++ stdlib namespaces/prefixes to ignore
CPP_STDLIB_NAMESPACES: Set[str] = {
    "std", "boost", "fmt", "spdlog", "nlohmann", "google", "absl",
}


@dataclass
class CppCallInfo:
    """Information about a C++ function/method call."""

    name: str  # Function/method name
    receiver: Optional[str]  # Object (obj in obj.method()) or namespace (ns in ns::func())
    qualified_name: str  # Full call expression
    line: int  # Line where call occurs
    call_type: str  # "direct" | "method" | "static" | "constructor"
    arguments: List[str]  # Argument expressions


class CppCallFlowExtractor(BaseCallFlowExtractor):
    """
    Extracts function call flows from C++ source code.

    Inherits from BaseCallFlowExtractor to share:
    - Tree-sitter initialization (TreeSitterMixin)
    - Complexity and LOC calculation (MetricsMixin)
    - Symbol ID generation (SymbolMixin)

    Example:
        >>> extractor = CppCallFlowExtractor()
        >>> entries = extractor.list_entry_points(Path("main.cpp"))
        >>> graph = extractor.extract(Path("main.cpp"), "main", max_depth=5)
    """

    # Class variables from BaseCallFlowExtractor
    LANGUAGE: ClassVar[str] = "cpp"
    EXTENSIONS: ClassVar[Set[str]] = {".cpp", ".c", ".hpp", ".h", ".cc", ".cxx", ".hxx"}

    # For backward compatibility
    CPP_EXTENSIONS = EXTENSIONS

    @property
    def decision_types(self) -> Set[str]:
        """C++ decision point node types for complexity calculation."""
        return {
            "if_statement",
            "for_statement",
            "for_range_loop",
            "while_statement",
            "do_statement",
            "case_statement",
            "catch_clause",
            "conditional_expression",  # ternary: x ? y : z
        }

    @property
    def builtin_functions(self) -> Set[str]:
        """C++ stdlib functions to ignore."""
        return CPP_STDLIB_FUNCTIONS

    # ─────────────────────────────────────────────────────────────
    # C++-specific helper methods
    # ─────────────────────────────────────────────────────────────

    def _get_function_name(self, node: Any, source: bytes) -> Optional[str]:
        """
        Extract function name from a function_definition node.

        Handles:
        - Simple functions: void foo() {}
        - Methods: void Class::foo() {}
        - Destructors: ~Class()
        - Constructors: Class()
        """
        for child in node.children:
            if child.type == "function_declarator":
                return self._get_declarator_name(child, source)
        return None

    def _get_declarator_name(self, node: Any, source: bytes) -> Optional[str]:
        """Extract the actual name from a declarator."""
        for child in node.children:
            if child.type == "identifier":
                return self._get_node_text(child, source)
            elif child.type == "qualified_identifier":
                # For Class::method, get the method name
                parts = []
                for sub in child.children:
                    if sub.type == "identifier":
                        parts.append(self._get_node_text(sub, source))
                    elif sub.type == "destructor_name":
                        parts.append(self._get_node_text(sub, source))
                return parts[-1] if parts else None
            elif child.type == "destructor_name":
                return self._get_node_text(child, source)
            elif child.type == "field_identifier":
                return self._get_node_text(child, source)
        return None

    def _get_class_context(self, node: Any, source: bytes) -> Optional[str]:
        """
        Get the class name if this function is defined inside a class.

        Also checks for qualified names like Class::method.
        """
        # Check for qualified identifier in function_declarator
        for child in node.children:
            if child.type == "function_declarator":
                for sub in child.children:
                    if sub.type == "qualified_identifier":
                        # Class::method format
                        for part in sub.children:
                            if part.type == "namespace_identifier":
                                return self._get_node_text(part, source)
                            elif part.type == "identifier":
                                # First identifier is the class name
                                text = self._get_node_text(part, source)
                                # Skip if this is the function name (last part)
                                if part.next_sibling is not None:
                                    return text
                        break

        # Check parent nodes for class definition
        parent = node.parent
        while parent:
            if parent.type in ("class_specifier", "struct_specifier"):
                for child in parent.children:
                    if child.type == "type_identifier":
                        return self._get_node_text(child, source)
            parent = parent.parent

        return None

    def _is_template_function(self, node: Any) -> bool:
        """Check if this is a template function."""
        parent = node.parent
        while parent:
            if parent.type == "template_declaration":
                return True
            parent = parent.parent
        return False

    def _should_skip_function(self, name: str) -> bool:
        """Check if function should be skipped."""
        if name.startswith("_") and not name.startswith("__"):
            return True
        if name in ("main",):
            return False  # Always include main
        return False

    def _count_calls_in_node(self, node: Any) -> int:
        """Count function/method calls within an AST node."""
        count = 0
        for child in self._walk_tree(node):
            if child.type == "call_expression":
                count += 1
        return count

    # ─────────────────────────────────────────────────────────────
    # Required abstract method implementations
    # ─────────────────────────────────────────────────────────────

    def list_entry_points(self, file_path: Path) -> List[Dict[str, Any]]:
        """
        List all functions and methods in a C++ file that could be entry points.

        Args:
            file_path: Path to C++ file

        Returns:
            List of entry point info with name, qualified_name, line, kind, node_count
        """
        if not self._ensure_parser():
            return []

        try:
            source = file_path.read_bytes()
        except OSError as e:
            logger.error(f"Failed to read file {file_path}: {e}")
            return []

        tree = self._parser.parse(source)
        entry_points: List[Dict[str, Any]] = []

        for node in self._walk_tree(tree.root_node):
            if node.type == "function_definition":
                func_name = self._get_function_name(node, source)

                if not func_name:
                    continue

                if self._should_skip_function(func_name):
                    continue

                class_name = self._get_class_context(node, source)
                is_template = self._is_template_function(node)

                if class_name:
                    qualified_name = f"{class_name}::{func_name}"
                    kind = "method"
                else:
                    qualified_name = func_name
                    kind = "function"

                if is_template:
                    kind = f"template_{kind}"

                call_count = self._count_calls_in_node(node)

                entry_points.append({
                    "name": func_name,
                    "qualified_name": qualified_name,
                    "line": node.start_point[0] + 1,
                    "kind": kind,
                    "class_name": class_name,
                    "node_count": call_count,
                    "file_path": str(file_path),
                })

        return entry_points

    def extract(
        self,
        file_path: Path,
        function_name: str,
        max_depth: int = 5,
        project_root: Optional[Path] = None,
    ) -> Optional[CallGraph]:
        """
        Extract call flow graph starting from a function.

        Args:
            file_path: Path to the C++ source file
            function_name: Name of the entry point function/method
            max_depth: Maximum depth to follow calls
            project_root: Project root for relative paths (default: file's parent)

        Returns:
            CallGraph containing all reachable calls, or None if extraction fails
        """
        if not self._ensure_parser():
            logger.warning("tree-sitter not available for C++ call flow extraction")
            return None

        file_path = file_path.resolve()
        effective_root = project_root or self.root_path or file_path.parent

        try:
            source = file_path.read_bytes()
        except OSError as e:
            logger.error("Failed to read file %s: %s", file_path, e)
            return None

        tree = self._parser.parse(source)

        # Find the target function
        func_node, class_name = self._find_function_by_name(
            tree.root_node, function_name, source
        )
        if func_node is None:
            logger.warning(
                "Function '%s' not found in %s", function_name, file_path
            )
            return None

        # Build qualified name
        if class_name:
            qualified_name = f"{class_name}::{function_name}"
        else:
            qualified_name = function_name

        # Create entry point node using SymbolMixin
        line = func_node.start_point[0] + 1
        col = func_node.start_point[1]
        kind = "method" if class_name else "function"
        entry_id = self._make_symbol_id(file_path, line, col, kind, function_name, effective_root)

        entry_node = CallNode(
            id=entry_id,
            name=function_name,
            qualified_name=qualified_name,
            file_path=file_path,
            line=line,
            column=col,
            kind=kind,
            is_entry_point=True,
            depth=0,
            symbol_id=entry_id,
            resolution_status=ResolutionStatus.RESOLVED_PROJECT,
            complexity=self._calculate_complexity(func_node),
            loc=self._calculate_loc(func_node),
        )

        # Initialize graph
        graph = CallGraph(
            entry_point=entry_id,
            max_depth=max_depth,
            source_file=file_path,
        )
        graph.add_node(entry_node)

        # Build index of all functions in file for resolution
        function_index = self._build_function_index(tree.root_node, source, file_path, effective_root)

        # Extract calls recursively
        call_stack: List[str] = [entry_id]
        self._extract_calls_recursive(
            graph=graph,
            node=func_node,
            parent_id=entry_id,
            file_path=file_path,
            source=source,
            project_root=effective_root,
            depth=1,
            max_depth=max_depth,
            call_stack=call_stack,
            class_context=class_name,
            function_index=function_index,
        )

        return graph

    # ─────────────────────────────────────────────────────────────
    # Internal extraction methods
    # ─────────────────────────────────────────────────────────────

    def _build_function_index(
        self,
        root: Any,
        source: bytes,
        file_path: Path,
        project_root: Path,
    ) -> Dict[str, Dict[str, Any]]:
        """Build index of all functions in file for fast lookup."""
        index: Dict[str, Dict[str, Any]] = {}

        for node in self._walk_tree(root):
            if node.type == "function_definition":
                func_name = self._get_function_name(node, source)
                if not func_name:
                    continue

                class_name = self._get_class_context(node, source)
                line = node.start_point[0] + 1
                col = node.start_point[1]

                key = f"{class_name}::{func_name}" if class_name else func_name

                index[key] = {
                    "node": node,
                    "name": func_name,
                    "class_name": class_name,
                    "line": line,
                    "col": col,
                    "kind": "method" if class_name else "function",
                }

                if key != func_name and func_name not in index:
                    index[func_name] = index[key]

        return index

    def _find_function_by_name(
        self,
        root: Any,
        name: str,
        source: bytes,
        class_name: Optional[str] = None,
    ) -> Tuple[Optional[Any], Optional[str]]:
        """Find a function definition by name."""
        for node in self._walk_tree(root):
            if node.type == "function_definition":
                func_name = self._get_function_name(node, source)
                if func_name != name:
                    continue

                found_class = self._get_class_context(node, source)

                if class_name:
                    if found_class == class_name:
                        return (node, found_class)
                else:
                    return (node, found_class)

        return (None, None)

    def _extract_calls_recursive(
        self,
        graph: CallGraph,
        node: Any,
        parent_id: str,
        file_path: Path,
        source: bytes,
        project_root: Path,
        depth: int,
        max_depth: int,
        call_stack: List[str],
        class_context: Optional[str] = None,
        function_index: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> None:
        """Recursively extract calls from a function body."""
        if depth > max_depth:
            graph.max_depth_reached = True
            graph.diagnostics["max_depth_reached"] = True
            return

        # Find function body using mixin method
        body = self._find_child_by_type(node, "compound_statement")
        if body is None:
            return

        calls = self._extract_calls_from_body(body, source)

        for call_info in calls:
            resolved, status, hint = self._resolve_call(
                call_info=call_info,
                file_path=file_path,
                source=source,
                project_root=project_root,
                class_context=class_context,
                function_index=function_index,
            )

            if status != ResolutionStatus.RESOLVED_PROJECT:
                ignored_call = IgnoredCall(
                    expression=call_info.qualified_name,
                    status=status,
                    call_site_line=call_info.line,
                    module_hint=hint,
                    caller_id=parent_id,
                )
                graph.ignored_calls.append(ignored_call)

                if status == ResolutionStatus.UNRESOLVED:
                    graph.unresolved_calls.append(call_info.qualified_name)
                continue

            target_node, target_info = resolved
            target_id = self._make_symbol_id(
                file_path,
                target_info["line"],
                target_info["col"],
                target_info["kind"],
                target_info["name"],
                project_root,
            )

            target_class = target_info.get("class_name")
            if target_class:
                target_qualified = f"{target_class}::{target_info['name']}"
            else:
                target_qualified = target_info["name"]

            is_cycle = target_id in call_stack
            if is_cycle:
                graph.diagnostics.setdefault("cycles_detected", []).append({
                    "from": parent_id,
                    "to": target_id,
                    "path": list(call_stack),
                })

            edge = CallEdge(
                source_id=parent_id,
                target_id=target_id,
                call_site_line=call_info.line,
                call_type=call_info.call_type,
                arguments=call_info.arguments if call_info.arguments else None,
                expression=call_info.qualified_name,
                resolution_status=ResolutionStatus.RESOLVED_PROJECT,
            )
            graph.add_edge(edge)

            if is_cycle:
                continue

            if graph.get_node(target_id) is None:
                target_node_obj = CallNode(
                    id=target_id,
                    name=target_info["name"],
                    qualified_name=target_qualified,
                    file_path=file_path,
                    line=target_info["line"],
                    column=target_info["col"],
                    kind=target_info["kind"],
                    is_entry_point=False,
                    depth=depth,
                    symbol_id=target_id,
                    resolution_status=ResolutionStatus.RESOLVED_PROJECT,
                    complexity=self._calculate_complexity(target_node),
                    loc=self._calculate_loc(target_node),
                )
                graph.add_node(target_node_obj)

            call_stack.append(target_id)
            self._extract_calls_recursive(
                graph=graph,
                node=target_node,
                parent_id=target_id,
                file_path=file_path,
                source=source,
                project_root=project_root,
                depth=depth + 1,
                max_depth=max_depth,
                call_stack=call_stack,
                class_context=target_class,
                function_index=function_index,
            )
            call_stack.pop()

    def _extract_calls_from_body(self, body: Any, source: bytes) -> List[CppCallInfo]:
        """Extract all function calls from a code block."""
        calls: List[CppCallInfo] = []

        for node in self._walk_tree(body):
            if node.type == "call_expression":
                call_info = self._parse_call(node, source)
                if call_info:
                    calls.append(call_info)

        return calls

    def _parse_call(self, node: Any, source: bytes) -> Optional[CppCallInfo]:
        """Parse a call_expression node to extract call information."""
        if node.type != "call_expression":
            return None

        func_node = node.children[0] if node.children else None
        if func_node is None:
            return None

        name = ""
        receiver = None
        call_type = "direct"

        if func_node.type == "identifier":
            name = self._get_node_text(func_node, source)
            call_type = "direct"

        elif func_node.type == "field_expression":
            parts = self._parse_field_expression(func_node, source)
            if parts:
                receiver = parts[0] if len(parts) > 1 else None
                name = parts[-1]
                call_type = "method"

        elif func_node.type == "qualified_identifier":
            parts = self._parse_qualified_identifier(func_node, source)
            if parts:
                receiver = parts[0] if len(parts) > 1 else None
                name = parts[-1]
                call_type = "static"

        elif func_node.type == "template_function":
            for child in func_node.children:
                if child.type == "identifier":
                    name = self._get_node_text(child, source)
                    call_type = "direct"
                    break

        if not name:
            return None

        if receiver:
            if call_type == "static":
                qualified_name = f"{receiver}::{name}"
            else:
                qualified_name = f"{receiver}.{name}"
        else:
            qualified_name = name

        arguments: List[str] = []
        args_node = self._find_child_by_type(node, "argument_list")
        if args_node:
            for child in args_node.children:
                if child.type not in ("(", ")", ","):
                    arg_text = self._get_node_text(child, source)
                    arguments.append(arg_text)

        return CppCallInfo(
            name=name,
            receiver=receiver,
            qualified_name=qualified_name,
            line=node.start_point[0] + 1,
            call_type=call_type,
            arguments=arguments,
        )

    def _parse_field_expression(self, node: Any, source: bytes) -> List[str]:
        """Parse field expression like obj.method or ptr->method into parts."""
        parts: List[str] = []

        def extract(n: Any) -> None:
            if n.type == "identifier":
                parts.append(self._get_node_text(n, source))
            elif n.type == "field_identifier":
                parts.append(self._get_node_text(n, source))
            elif n.type == "field_expression":
                for child in n.children:
                    if child.type not in (".", "->"):
                        extract(child)
            elif n.type == "this":
                parts.append("this")

        extract(node)
        return parts

    def _parse_qualified_identifier(self, node: Any, source: bytes) -> List[str]:
        """Parse qualified identifier like Class::method or ns::func into parts."""
        parts: List[str] = []

        for child in node.children:
            if child.type == "identifier":
                parts.append(self._get_node_text(child, source))
            elif child.type == "namespace_identifier":
                parts.append(self._get_node_text(child, source))
            elif child.type == "template_type":
                for sub in child.children:
                    if sub.type == "type_identifier":
                        parts.append(self._get_node_text(sub, source))
                        break

        return parts

    def _resolve_call(
        self,
        call_info: CppCallInfo,
        file_path: Path,
        source: bytes,
        project_root: Path,
        class_context: Optional[str] = None,
        function_index: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> Tuple[
        Optional[Tuple[Any, Dict[str, Any]]],
        ResolutionStatus,
        Optional[str],
    ]:
        """Resolve a call to its definition in the same file."""
        if function_index is None:
            function_index = {}

        if call_info.name in CPP_STDLIB_FUNCTIONS:
            return (None, ResolutionStatus.IGNORED_STDLIB, call_info.name)

        if call_info.receiver and call_info.receiver in CPP_STDLIB_NAMESPACES:
            return (None, ResolutionStatus.IGNORED_STDLIB, call_info.receiver)

        if call_info.receiver == "this" and class_context:
            qualified_key = f"{class_context}::{call_info.name}"
            if qualified_key in function_index:
                info = function_index[qualified_key]
                return ((info["node"], info), ResolutionStatus.RESOLVED_PROJECT, None)
            return (None, ResolutionStatus.UNRESOLVED, None)

        if call_info.call_type == "static" and call_info.receiver:
            qualified_key = f"{call_info.receiver}::{call_info.name}"
            if qualified_key in function_index:
                info = function_index[qualified_key]
                return ((info["node"], info), ResolutionStatus.RESOLVED_PROJECT, None)
            return (None, ResolutionStatus.IGNORED_THIRD_PARTY, call_info.receiver)

        if call_info.call_type == "method":
            return (None, ResolutionStatus.UNRESOLVED, None)

        if call_info.call_type == "direct":
            if call_info.name in function_index:
                info = function_index[call_info.name]
                return ((info["node"], info), ResolutionStatus.RESOLVED_PROJECT, None)
            return (None, ResolutionStatus.UNRESOLVED, None)

        return (None, ResolutionStatus.UNRESOLVED, None)
