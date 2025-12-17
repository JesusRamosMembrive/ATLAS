# SPDX-License-Identifier: MIT
"""
TypeScript/JavaScript Call Flow extractor using tree-sitter.

Extracts function definitions and call graphs from TypeScript/JavaScript code.
Supports single-file analysis with function call tracking.

Supports:
- .ts, .tsx (TypeScript)
- .js, .jsx (JavaScript)
- .mjs, .cjs (ES/CommonJS modules)

Limitations (by design):
- External modules: Analyzed independently, not resolved across files
- Dynamic calls: obj[method]() cannot be resolved
- Generic/template types: Limited type inference
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from .models import CallEdge, CallGraph, CallNode, IgnoredCall, ResolutionStatus

logger = logging.getLogger(__name__)


# Common JavaScript/TypeScript built-in functions to ignore
JS_BUILTIN_FUNCTIONS: Set[str] = {
    # Console
    "log", "warn", "error", "info", "debug", "trace", "dir", "table",
    "time", "timeEnd", "group", "groupEnd", "clear", "count", "assert",
    # Array methods
    "push", "pop", "shift", "unshift", "splice", "slice", "concat",
    "map", "filter", "reduce", "reduceRight", "forEach", "find", "findIndex",
    "some", "every", "includes", "indexOf", "lastIndexOf", "join", "reverse",
    "sort", "flat", "flatMap", "fill", "copyWithin", "entries", "keys", "values",
    # Object methods
    "keys", "values", "entries", "assign", "freeze", "seal", "create",
    "defineProperty", "defineProperties", "getOwnPropertyDescriptor",
    "getOwnPropertyNames", "getOwnPropertySymbols", "getPrototypeOf",
    "setPrototypeOf", "hasOwnProperty", "isPrototypeOf", "propertyIsEnumerable",
    # String methods
    "charAt", "charCodeAt", "codePointAt", "concat", "includes", "endsWith",
    "startsWith", "indexOf", "lastIndexOf", "localeCompare", "match", "matchAll",
    "normalize", "padEnd", "padStart", "repeat", "replace", "replaceAll",
    "search", "slice", "split", "substring", "toLowerCase", "toUpperCase",
    "trim", "trimStart", "trimEnd", "valueOf", "toString",
    # Math
    "abs", "ceil", "floor", "round", "max", "min", "pow", "sqrt", "random",
    "sin", "cos", "tan", "log", "exp",
    # JSON
    "parse", "stringify",
    # Promise
    "then", "catch", "finally", "all", "allSettled", "any", "race", "resolve", "reject",
    # Utility
    "setTimeout", "setInterval", "clearTimeout", "clearInterval",
    "requestAnimationFrame", "cancelAnimationFrame",
    "fetch", "alert", "confirm", "prompt",
    # Type checking
    "isArray", "isNaN", "isFinite", "parseInt", "parseFloat",
    # DOM (common)
    "getElementById", "getElementsByClassName", "getElementsByTagName",
    "querySelector", "querySelectorAll", "createElement", "appendChild",
    "removeChild", "addEventListener", "removeEventListener",
    "getAttribute", "setAttribute", "removeAttribute",
    # React hooks (very common)
    "useState", "useEffect", "useContext", "useReducer", "useCallback",
    "useMemo", "useRef", "useImperativeHandle", "useLayoutEffect",
    "useDebugValue", "useTransition", "useDeferredValue", "useId",
}

# Common JS/TS library namespaces to ignore
JS_LIBRARY_NAMESPACES: Set[str] = {
    "console", "Math", "JSON", "Object", "Array", "String", "Number",
    "Boolean", "Date", "RegExp", "Error", "Promise", "Map", "Set",
    "WeakMap", "WeakSet", "Symbol", "Reflect", "Proxy", "Intl",
    "document", "window", "navigator", "localStorage", "sessionStorage",
    "React", "ReactDOM", "Vue", "Angular", "jQuery", "$",
    "axios", "lodash", "_", "moment", "dayjs",
    "fs", "path", "os", "http", "https", "crypto", "util", "events",
}


@dataclass
class TsCallInfo:
    """Information about a TypeScript/JavaScript function/method call."""

    name: str  # Function/method name
    receiver: Optional[str]  # Object (obj in obj.method())
    qualified_name: str  # Full call expression
    line: int  # Line where call occurs
    call_type: str  # "direct" | "method" | "constructor" | "callback"
    arguments: List[str]  # Argument expressions


class TsCallFlowExtractor:
    """
    Extracts function definitions and call graphs from TypeScript/JavaScript.

    Uses tree-sitter for parsing TypeScript and JavaScript files.
    Supports both .ts/.tsx and .js/.jsx files.
    """

    # Supported file extensions
    TS_EXTENSIONS = {".ts", ".tsx", ".mts", ".cts"}
    JS_EXTENSIONS = {".js", ".jsx", ".mjs", ".cjs"}
    ALL_EXTENSIONS = TS_EXTENSIONS | JS_EXTENSIONS

    def __init__(self) -> None:
        """Initialize the extractor."""
        self._parser: Any = None
        self._ts_language: Any = None
        self._tsx_language: Any = None
        self._available: Optional[bool] = None

    def is_available(self) -> bool:
        """Check if tree-sitter is available for TypeScript/JavaScript parsing."""
        if self._available is not None:
            return self._available

        try:
            import tree_sitter
            import tree_sitter_languages

            self._ts_language = tree_sitter_languages.get_language("typescript")
            self._tsx_language = tree_sitter_languages.get_language("tsx")
            self._parser = tree_sitter.Parser()
            self._available = True
        except (ImportError, Exception) as e:
            logger.debug("tree-sitter not available for TypeScript: %s", e)
            self._available = False

        return self._available

    def _ensure_parser(self, is_tsx: bool = False) -> bool:
        """Ensure parser is initialized with correct language."""
        if not self.is_available():
            return False

        language = self._tsx_language if is_tsx else self._ts_language
        self._parser.set_language(language)
        return True

    def _is_tsx_file(self, file_path: Path) -> bool:
        """Check if file should use TSX parser (for JSX support)."""
        return file_path.suffix.lower() in {".tsx", ".jsx"}

    def _walk_tree(self, node: Any):
        """Generator that yields all nodes in the tree."""
        yield node
        for child in node.children:
            yield from self._walk_tree(child)

    def _get_node_text(self, node: Any, source: bytes) -> str:
        """Extract text content from a node."""
        return source[node.start_byte:node.end_byte].decode("utf-8", errors="replace")

    def _should_skip_function(self, name: str) -> bool:
        """Check if function should be skipped from entry points."""
        if name.startswith("_") and not name.startswith("__"):
            return True
        # Skip anonymous/arrow functions without meaningful names
        if not name or name in {"anonymous", ""}:
            return True
        return False

    def _count_calls_in_node(self, node: Any) -> int:
        """
        Count function/method calls within an AST node.

        Args:
            node: AST node (typically a function body)

        Returns:
            Number of call expressions found in the node
        """
        count = 0
        for child in self._walk_tree(node):
            if child.type == "call_expression":
                count += 1
        return count

    def list_entry_points(self, file_path: Path) -> List[Dict[str, Any]]:
        """
        List all functions and methods in a TypeScript/JavaScript file.

        Args:
            file_path: Path to TS/JS file

        Returns:
            List of entry point info with name, qualified_name, line, kind, node_count
        """
        is_tsx = self._is_tsx_file(file_path)
        if not self._ensure_parser(is_tsx):
            return []

        try:
            source = file_path.read_bytes()
        except OSError as e:
            logger.error(f"Failed to read file {file_path}: {e}")
            return []

        tree = self._parser.parse(source)
        entry_points: List[Dict[str, Any]] = []
        current_class: Optional[str] = None

        for node in self._walk_tree(tree.root_node):
            # Function declarations: function foo() {}
            if node.type == "function_declaration":
                func_name = self._get_function_name(node, source)
                if func_name and not self._should_skip_function(func_name):
                    call_count = self._count_calls_in_node(node)
                    entry_points.append({
                        "name": func_name,
                        "qualified_name": func_name,
                        "line": node.start_point[0] + 1,
                        "kind": "function",
                        "class_name": None,
                        "node_count": call_count,
                    })

            # Arrow functions assigned to const/let/var
            elif node.type == "lexical_declaration" or node.type == "variable_declaration":
                for declarator in node.children:
                    if declarator.type == "variable_declarator":
                        name_node = declarator.child_by_field_name("name")
                        value_node = declarator.child_by_field_name("value")
                        if name_node and value_node:
                            if value_node.type in ("arrow_function", "function"):
                                func_name = self._get_node_text(name_node, source)
                                if func_name and not self._should_skip_function(func_name):
                                    call_count = self._count_calls_in_node(value_node)
                                    entry_points.append({
                                        "name": func_name,
                                        "qualified_name": func_name,
                                        "line": node.start_point[0] + 1,
                                        "kind": "function",
                                        "class_name": None,
                                        "node_count": call_count,
                                    })

            # Class declarations
            elif node.type == "class_declaration":
                class_name = self._get_class_name(node, source)
                if class_name:
                    # Find constructor call count for class
                    constructor_calls = 0
                    for child in self._walk_tree(node):
                        if child.type == "method_definition":
                            method_name = self._get_method_name(child, source)
                            if method_name == "constructor":
                                constructor_calls = self._count_calls_in_node(child)
                                break

                    entry_points.append({
                        "name": class_name,
                        "qualified_name": class_name,
                        "line": node.start_point[0] + 1,
                        "kind": "class",
                        "class_name": None,
                        "node_count": constructor_calls,
                    })

                    # Add methods
                    body = self._find_child_by_type(node, "class_body")
                    if body:
                        for child in body.children:
                            if child.type == "method_definition":
                                method_name = self._get_method_name(child, source)
                                if method_name and not self._should_skip_function(method_name):
                                    call_count = self._count_calls_in_node(child)
                                    entry_points.append({
                                        "name": method_name,
                                        "qualified_name": f"{class_name}.{method_name}",
                                        "line": child.start_point[0] + 1,
                                        "kind": "method",
                                        "class_name": class_name,
                                        "node_count": call_count,
                                    })

            # Exported functions
            elif node.type in ("export_statement", "export_default_declaration"):
                declaration = self._find_child_by_type(node, "function_declaration")
                if declaration:
                    func_name = self._get_function_name(declaration, source)
                    if func_name and not self._should_skip_function(func_name):
                        call_count = self._count_calls_in_node(declaration)
                        # Check if already added
                        if not any(ep["name"] == func_name for ep in entry_points):
                            entry_points.append({
                                "name": func_name,
                                "qualified_name": func_name,
                                "line": declaration.start_point[0] + 1,
                                "kind": "function",
                                "class_name": None,
                                "node_count": call_count,
                            })

        return entry_points

    def _get_function_name(self, node: Any, source: bytes) -> Optional[str]:
        """Extract function name from function_declaration node."""
        name_node = node.child_by_field_name("name")
        if name_node:
            return self._get_node_text(name_node, source)
        # Fallback: look for identifier child
        for child in node.children:
            if child.type == "identifier":
                return self._get_node_text(child, source)
        return None

    def _get_class_name(self, node: Any, source: bytes) -> Optional[str]:
        """Extract class name from class_declaration node."""
        name_node = node.child_by_field_name("name")
        if name_node:
            return self._get_node_text(name_node, source)
        for child in node.children:
            if child.type == "type_identifier" or child.type == "identifier":
                return self._get_node_text(child, source)
        return None

    def _get_method_name(self, node: Any, source: bytes) -> Optional[str]:
        """Extract method name from method_definition node."""
        name_node = node.child_by_field_name("name")
        if name_node:
            return self._get_node_text(name_node, source)
        for child in node.children:
            if child.type == "property_identifier":
                return self._get_node_text(child, source)
        return None

    def _find_child_by_type(self, node: Any, type_name: str) -> Optional[Any]:
        """Find first direct child of given type."""
        for child in node.children:
            if child.type == type_name:
                return child
        return None

    @classmethod
    def supports_extension(cls, extension: str) -> bool:
        """Check if this extractor supports the given file extension."""
        return extension.lower() in cls.ALL_EXTENSIONS

    # ─────────────────────────────────────────────────────────────
    # Complexity Calculation
    # ─────────────────────────────────────────────────────────────

    def _calculate_complexity(self, func_node: Any) -> int:
        """
        Calculate cyclomatic complexity (McCabe) for a function node.

        Counts decision points: if, for, while, switch/case, catch,
        ternary expressions, && and || operators.

        Args:
            func_node: tree-sitter node for the function

        Returns:
            Cyclomatic complexity (1 + number of decision points)
        """
        count = 0
        to_visit = [func_node]

        # Decision point node types in TypeScript/JavaScript
        decision_types = {
            "if_statement",
            "for_statement",
            "for_in_statement",
            "while_statement",
            "do_statement",
            "switch_case",
            "catch_clause",
            "ternary_expression",
            "conditional_expression",  # alias for ternary
        }

        while to_visit:
            node = to_visit.pop()
            if node.type in decision_types:
                count += 1
            elif node.type == "binary_expression":
                # Check for && or || operators
                for child in node.children:
                    if child.type in ("&&", "||"):
                        count += 1
                        break
            to_visit.extend(node.children)

        return 1 + count

    def _calculate_loc(self, func_node: Any) -> int:
        """
        Calculate lines of code for a function node.

        Args:
            func_node: tree-sitter node for the function

        Returns:
            Number of lines (end_line - start_line + 1)
        """
        start_line = func_node.start_point[0]
        end_line = func_node.end_point[0]
        return end_line - start_line + 1

    # ─────────────────────────────────────────────────────────────
    # Call Flow Extraction
    # ─────────────────────────────────────────────────────────────

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
            file_path: Path to the TypeScript/JavaScript source file
            function_name: Name of the entry point function/method
            max_depth: Maximum depth to follow calls
            project_root: Project root for relative paths (default: file's parent)

        Returns:
            CallGraph containing all reachable calls, or None if extraction fails
        """
        is_tsx = self._is_tsx_file(file_path)
        if not self._ensure_parser(is_tsx):
            logger.warning("tree-sitter not available for TypeScript call flow extraction")
            return None

        file_path = file_path.resolve()
        effective_root = project_root or file_path.parent

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
            qualified_name = f"{class_name}.{function_name}"
        else:
            qualified_name = function_name

        # Create entry point node
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

        # Build index of all functions in file
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

    def _make_symbol_id(
        self,
        file_path: Path,
        line: int,
        col: int,
        kind: str,
        name: str,
        root: Path,
    ) -> str:
        """Generate a stable symbol ID."""
        try:
            rel_path = file_path.relative_to(root)
        except ValueError:
            rel_path = file_path
        return f"{rel_path.as_posix()}:{line}:{col}:{kind}:{name}"

    def _build_function_index(
        self,
        root: Any,
        source: bytes,
        file_path: Path,
        project_root: Path,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Build index of all functions in file for fast lookup.

        Returns:
            Dict mapping function names to their info (node, line, col, class_name)
        """
        index: Dict[str, Dict[str, Any]] = {}

        for node in self._walk_tree(root):
            # Function declarations
            if node.type == "function_declaration":
                func_name = self._get_function_name(node, source)
                if not func_name:
                    continue

                line = node.start_point[0] + 1
                col = node.start_point[1]

                index[func_name] = {
                    "node": node,
                    "name": func_name,
                    "class_name": None,
                    "line": line,
                    "col": col,
                    "kind": "function",
                }

            # Arrow functions in variable declarations
            elif node.type == "variable_declarator":
                name_node = node.child_by_field_name("name")
                value_node = node.child_by_field_name("value")
                if name_node and value_node and value_node.type in ("arrow_function", "function"):
                    func_name = self._get_node_text(name_node, source)
                    if func_name:
                        line = value_node.start_point[0] + 1
                        col = value_node.start_point[1]
                        index[func_name] = {
                            "node": value_node,
                            "name": func_name,
                            "class_name": None,
                            "line": line,
                            "col": col,
                            "kind": "function",
                        }

            # Method definitions in classes
            elif node.type == "method_definition":
                method_name = self._get_method_name(node, source)
                if not method_name:
                    continue

                # Find parent class
                class_name = self._get_class_context(node, source)
                line = node.start_point[0] + 1
                col = node.start_point[1]

                key = f"{class_name}.{method_name}" if class_name else method_name

                index[key] = {
                    "node": node,
                    "name": method_name,
                    "class_name": class_name,
                    "line": line,
                    "col": col,
                    "kind": "method" if class_name else "function",
                }

                # Also index by simple name
                if key != method_name and method_name not in index:
                    index[method_name] = index[key]

        return index

    def _get_class_context(self, node: Any, source: bytes) -> Optional[str]:
        """Find the class name that contains a method node."""
        current = node.parent
        while current:
            if current.type == "class_declaration":
                return self._get_class_name(current, source)
            if current.type == "class_body":
                parent_class = current.parent
                if parent_class and parent_class.type == "class_declaration":
                    return self._get_class_name(parent_class, source)
            current = current.parent
        return None

    def _find_function_by_name(
        self,
        root: Any,
        name: str,
        source: bytes,
        class_name: Optional[str] = None,
    ) -> Tuple[Optional[Any], Optional[str]]:
        """
        Find a function definition by name.

        Args:
            root: AST root node
            name: Function name to find
            source: Source bytes
            class_name: If provided, look for method in this class

        Returns:
            Tuple of (function_node, class_name) or (None, None)
        """
        for node in self._walk_tree(root):
            # Function declarations
            if node.type == "function_declaration":
                func_name = self._get_function_name(node, source)
                if func_name == name:
                    return (node, None)

            # Arrow functions in variables
            elif node.type == "variable_declarator":
                name_node = node.child_by_field_name("name")
                value_node = node.child_by_field_name("value")
                if name_node and value_node and value_node.type in ("arrow_function", "function"):
                    func_name = self._get_node_text(name_node, source)
                    if func_name == name:
                        return (value_node, None)

            # Method definitions
            elif node.type == "method_definition":
                method_name = self._get_method_name(node, source)
                if method_name == name:
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
        """
        Recursively extract calls from a function body.

        Uses per-branch cycle detection via call_stack.
        """
        if depth > max_depth:
            graph.max_depth_reached = True
            graph.diagnostics["max_depth_reached"] = True
            return

        # Find function body
        body = self._find_function_body(node)
        if body is None:
            return

        # Extract all calls in this function
        calls = self._extract_calls_from_body(body, source)

        for call_info in calls:
            # Try to resolve the call
            resolved, status, hint = self._resolve_call(
                call_info=call_info,
                file_path=file_path,
                source=source,
                project_root=project_root,
                class_context=class_context,
                function_index=function_index,
            )

            # Handle ignored/unresolved calls
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

            # Resolved call
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
                target_qualified = f"{target_class}.{target_info['name']}"
            else:
                target_qualified = target_info["name"]

            # Per-branch cycle detection
            is_cycle = target_id in call_stack
            if is_cycle:
                graph.diagnostics.setdefault("cycles_detected", []).append({
                    "from": parent_id,
                    "to": target_id,
                    "path": list(call_stack),
                })

            # Add edge
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

            # Create node if not exists
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

            # Recurse
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

    def _find_function_body(self, node: Any) -> Optional[Any]:
        """Find the body node of a function."""
        # For function_declaration and method_definition
        body = self._find_child_by_type(node, "statement_block")
        if body:
            return body

        # For arrow functions, body can be expression or statement_block
        body = node.child_by_field_name("body")
        if body:
            return body

        return None

    def _extract_calls_from_body(self, body: Any, source: bytes) -> List[TsCallInfo]:
        """Extract all function calls from a code block."""
        calls: List[TsCallInfo] = []

        for node in self._walk_tree(body):
            if node.type == "call_expression":
                call_info = self._parse_call(node, source)
                if call_info:
                    calls.append(call_info)

        return calls

    def _parse_call(self, node: Any, source: bytes) -> Optional[TsCallInfo]:
        """
        Parse a call_expression node to extract call information.

        Handles:
        - Direct calls: foo()
        - Method calls: obj.method()
        - Chained calls: obj.foo().bar()
        - Constructor calls: new ClassName()
        """
        if node.type != "call_expression":
            return None

        func_node = node.child_by_field_name("function")
        if func_node is None and node.children:
            func_node = node.children[0]

        if func_node is None:
            return None

        name = ""
        receiver = None
        call_type = "direct"

        # Direct function call: foo()
        if func_node.type == "identifier":
            name = self._get_node_text(func_node, source)
            call_type = "direct"

        # Member expression: obj.method()
        elif func_node.type == "member_expression":
            parts = self._parse_member_expression(func_node, source)
            if parts:
                receiver = parts[0] if len(parts) > 1 else None
                name = parts[-1]
                call_type = "method"

        # Constructor call: new ClassName()
        elif func_node.type == "new_expression":
            class_node = func_node.children[1] if len(func_node.children) > 1 else None
            if class_node:
                name = self._get_node_text(class_node, source)
                call_type = "constructor"

        # Parenthesized expression: (getFunc())()
        elif func_node.type == "parenthesized_expression":
            # Get the inner call if it's immediately invoked
            inner = func_node.children[1] if len(func_node.children) > 1 else None
            if inner and inner.type == "call_expression":
                # This is a higher-order call, mark as callback
                call_type = "callback"
                name = self._get_node_text(func_node, source)

        if not name:
            return None

        # Build qualified name
        if receiver:
            qualified_name = f"{receiver}.{name}"
        else:
            qualified_name = name

        # Extract arguments
        arguments: List[str] = []
        args_node = self._find_child_by_type(node, "arguments")
        if args_node:
            for child in args_node.children:
                if child.type not in ("(", ")", ","):
                    arg_text = self._get_node_text(child, source)
                    arguments.append(arg_text)

        return TsCallInfo(
            name=name,
            receiver=receiver,
            qualified_name=qualified_name,
            line=node.start_point[0] + 1,
            call_type=call_type,
            arguments=arguments,
        )

    def _parse_member_expression(self, node: Any, source: bytes) -> List[str]:
        """Parse member expression like obj.method into parts."""
        parts: List[str] = []

        def extract(n: Any) -> None:
            if n.type == "identifier":
                parts.append(self._get_node_text(n, source))
            elif n.type == "property_identifier":
                parts.append(self._get_node_text(n, source))
            elif n.type == "member_expression":
                obj = n.child_by_field_name("object")
                prop = n.child_by_field_name("property")
                if obj:
                    extract(obj)
                if prop:
                    extract(prop)
            elif n.type == "this":
                parts.append("this")
            elif n.type == "call_expression":
                # Chained call: foo().bar()
                func = n.child_by_field_name("function")
                if func:
                    extract(func)

        extract(node)
        return parts

    def _resolve_call(
        self,
        call_info: TsCallInfo,
        file_path: Path,
        source: bytes,
        project_root: Path,
        class_context: Optional[str] = None,
        function_index: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> Tuple[
        Optional[Tuple[Any, Dict[str, Any]]],  # (node, info)
        ResolutionStatus,
        Optional[str],  # hint (module/class)
    ]:
        """
        Resolve a call to its definition in the same file.

        Args:
            call_info: Information about the call
            file_path: Current file
            source: Source bytes
            project_root: Project root
            class_context: Current class name if inside a method
            function_index: Pre-built index of functions

        Returns:
            Tuple of:
            - (node, info_dict) or None
            - ResolutionStatus
            - hint string for ignored calls
        """
        if function_index is None:
            function_index = {}

        # Check for builtin functions
        if call_info.name in JS_BUILTIN_FUNCTIONS:
            return (None, ResolutionStatus.IGNORED_BUILTIN, call_info.name)

        # Check for library namespace calls
        if call_info.receiver and call_info.receiver in JS_LIBRARY_NAMESPACES:
            return (None, ResolutionStatus.IGNORED_STDLIB, call_info.receiver)

        # Special case: console.log, etc.
        if call_info.receiver == "console":
            return (None, ResolutionStatus.IGNORED_BUILTIN, "console")

        # Case 1: this.method() calls
        if call_info.receiver == "this" and class_context:
            qualified_key = f"{class_context}.{call_info.name}"
            if qualified_key in function_index:
                info = function_index[qualified_key]
                return ((info["node"], info), ResolutionStatus.RESOLVED_PROJECT, None)
            return (None, ResolutionStatus.UNRESOLVED, None)

        # Case 2: Direct function call
        if call_info.call_type == "direct":
            if call_info.name in function_index:
                info = function_index[call_info.name]
                return ((info["node"], info), ResolutionStatus.RESOLVED_PROJECT, None)
            return (None, ResolutionStatus.UNRESOLVED, None)

        # Case 3: Method call on object
        if call_info.call_type == "method":
            # Try qualified name first (for class methods)
            if call_info.receiver:
                qualified_key = f"{call_info.receiver}.{call_info.name}"
                if qualified_key in function_index:
                    info = function_index[qualified_key]
                    return ((info["node"], info), ResolutionStatus.RESOLVED_PROJECT, None)

            # Try just the method name (might be defined locally)
            if call_info.name in function_index:
                info = function_index[call_info.name]
                return ((info["node"], info), ResolutionStatus.RESOLVED_PROJECT, None)

            # Can't resolve object type without full type analysis
            return (None, ResolutionStatus.UNRESOLVED, None)

        # Case 4: Constructor call
        if call_info.call_type == "constructor":
            # Look for constructor method or the class itself
            constructor_key = f"{call_info.name}.constructor"
            if constructor_key in function_index:
                info = function_index[constructor_key]
                return ((info["node"], info), ResolutionStatus.RESOLVED_PROJECT, None)
            return (None, ResolutionStatus.UNRESOLVED, None)

        return (None, ResolutionStatus.UNRESOLVED, None)
