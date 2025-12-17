# SPDX-License-Identifier: MIT
"""
Call Flow extractor using tree-sitter (v2).

Extracts function/method calls from Python code to build call graphs.
Detects: direct calls, method calls, attribute chains.

v2 features:
- Proper classification of external calls (builtin/stdlib/third-party)
- Stable symbol IDs: {rel_path}:{line}:{col}:{kind}:{name}
- Per-branch cycle detection (allows same symbol in different paths)
- Optional SymbolIndex integration for faster lookups
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, TYPE_CHECKING, Tuple

from .constants import PYTHON_BUILTINS, is_stdlib
from .models import CallEdge, CallGraph, CallNode, IgnoredCall, ResolutionStatus
from .type_resolver import TypeResolver, TypeInfo, ScopeInfo

if TYPE_CHECKING:
    from code_map.index import SymbolIndex

logger = logging.getLogger(__name__)


@dataclass
class CallInfo:
    """Information about a function/method call."""

    name: str  # Simple name: "foo" or "bar"
    receiver: Optional[str]  # Object receiving the call: "self", "obj", None
    qualified_name: str  # Full call: "self.foo", "obj.bar()", "foo"
    line: int  # Line where call occurs
    call_type: str  # "direct" | "method" | "attribute_chain"
    arguments: List[str]  # Argument expressions


class PythonCallFlowExtractor:
    """
    Extracts function call flows from Python source code.

    Given a starting function, extracts all calls it makes and recursively
    builds a call graph up to a configurable depth.

    Example:
        >>> extractor = PythonCallFlowExtractor(Path("/project"))
        >>> graph = extractor.extract(Path("app.py"), "on_button_click", max_depth=5)
        >>> print(graph.to_react_flow())
    """

    def __init__(
        self,
        root_path: Optional[Path] = None,
        symbol_index: Optional["SymbolIndex"] = None,
    ) -> None:
        """
        Initialize the extractor with tree-sitter parser.

        Args:
            root_path: Project root for relative paths in symbol IDs.
                       If None, uses file's parent directory.
            symbol_index: Optional SymbolIndex for faster symbol lookups.
                          If provided, can resolve symbols across files more efficiently.
        """
        self._parser: Optional[Any] = None
        self._available: Optional[bool] = None
        self.root_path = root_path
        self.symbol_index = symbol_index
        self._type_resolver: Optional[TypeResolver] = None

    def is_available(self) -> bool:
        """Check if tree-sitter is available."""
        if self._available is not None:
            return self._available

        try:
            from code_map.dependencies import optional_dependencies

            modules = optional_dependencies.load("tree_sitter_languages")
            if not modules:
                self._available = False
                return False

            import warnings

            parser_cls = getattr(modules.get("tree_sitter"), "Parser", None)
            get_language = getattr(
                modules.get("tree_sitter_languages"), "get_language", None
            )

            if parser_cls is None or get_language is None:
                self._available = False
                return False

            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=FutureWarning)
                language = get_language("python")

            parser = parser_cls()
            parser.set_language(language)
            self._parser = parser
            self._available = True
            return True

        except Exception:
            self._available = False
            return False

    def _ensure_parser(self) -> bool:
        """Ensure parser is initialized."""
        if self._parser is not None:
            return True
        return self.is_available()

    def _get_type_resolver(self, project_root: Path) -> TypeResolver:
        """Get or create the type resolver (lazy initialization)."""
        if self._type_resolver is None:
            self._type_resolver = TypeResolver(project_root, self._parser)
        return self._type_resolver

    # ─────────────────────────────────────────────────────────────
    # Complexity calculation
    # ─────────────────────────────────────────────────────────────

    def _calculate_complexity(self, func_node: Any) -> int:
        """
        Calculate cyclomatic complexity (McCabe) for a function node.

        Counts decision points: if, for, while, except, with, match/case,
        comprehensions, boolean operators (and, or).

        Args:
            func_node: tree-sitter node for the function

        Returns:
            Cyclomatic complexity (1 + number of decision points)
        """
        count = 0
        to_visit = [func_node]

        # Decision point node types in Python
        decision_types = {
            "if_statement",
            "elif_clause",
            "for_statement",
            "while_statement",
            "except_clause",
            "with_statement",
            "case_clause",  # match/case (Python 3.10+)
            "list_comprehension",
            "dictionary_comprehension",
            "set_comprehension",
            "generator_expression",
            "conditional_expression",  # ternary: x if cond else y
        }

        # Boolean operators also add complexity
        boolean_ops = {"and", "or"}

        while to_visit:
            node = to_visit.pop()
            if node.type in decision_types:
                count += 1
            elif node.type == "boolean_operator":
                # Check if it's 'and' or 'or'
                for child in node.children:
                    if child.type in boolean_ops:
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
    # v2 Resolution methods
    # ─────────────────────────────────────────────────────────────

    def _classify_external(self, name: str, module_hint: Optional[str] = None) -> ResolutionStatus:
        """
        Classify an external (non-project) call.

        Args:
            name: The function/class name being called
            module_hint: Optional module name from import statement

        Returns:
            ResolutionStatus indicating the type of external call
        """
        # Check if it's a Python builtin
        if name in PYTHON_BUILTINS:
            return ResolutionStatus.IGNORED_BUILTIN

        # Check module hint for stdlib/third-party classification
        if module_hint:
            if is_stdlib(module_hint):
                return ResolutionStatus.IGNORED_STDLIB
            return ResolutionStatus.IGNORED_THIRD_PARTY

        # Without module hint, we can only check if name looks like a stdlib module
        if is_stdlib(name):
            return ResolutionStatus.IGNORED_STDLIB

        # Default to third-party for unknown external calls
        return ResolutionStatus.IGNORED_THIRD_PARTY

    def _make_symbol_id(
        self,
        file_path: Path,
        line: int,
        col: int,
        kind: str,
        name: str,
    ) -> str:
        """
        Generate a stable, deterministic symbol ID.

        Format: {rel_path}:{line}:{col}:{kind}:{name}

        Args:
            file_path: Absolute path to the file
            line: Line number (1-indexed)
            col: Column number (0-indexed)
            kind: Symbol kind (function, method, class)
            name: Symbol name

        Returns:
            Stable symbol ID string
        """
        root = self.root_path or file_path.parent
        try:
            rel_path = file_path.relative_to(root)
        except ValueError:
            # File is outside root, use absolute path
            rel_path = file_path
        return f"{rel_path.as_posix()}:{line}:{col}:{kind}:{name}"

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
            file_path: Path to the Python source file
            function_name: Name of the entry point function/method
            max_depth: Maximum depth to follow calls
            project_root: Project root for resolving imports (overrides self.root_path)

        Returns:
            CallGraph containing all reachable calls, or None if extraction fails
        """
        if not self._ensure_parser():
            logger.warning("tree-sitter not available for call flow extraction")
            return None

        file_path = file_path.resolve()
        # Use provided project_root, or instance root_path, or file's parent
        effective_root = project_root or self.root_path or file_path.parent

        try:
            source = file_path.read_text(encoding="utf-8")
        except OSError as e:
            logger.error("Failed to read file %s: %s", file_path, e)
            return None

        tree = self._parser.parse(bytes(source, "utf-8"))

        # Find the target function
        func_node, class_name = self._find_function_or_method(
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

        # Create entry point node with stable symbol ID
        line = func_node.start_point[0] + 1
        col = func_node.start_point[1]
        kind = "method" if class_name else "function"
        entry_id = self._make_symbol_id(file_path, line, col, kind, function_name)

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
            docstring=self._get_docstring(func_node, source),
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

        # Extract imports for resolution context
        imports = self._extract_imports(tree.root_node, source)

        # Extract calls recursively using per-branch call stack (not global visited)
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
            imports=imports,
        )

        return graph

    def _extract_calls_recursive(
        self,
        graph: CallGraph,
        node: Any,
        parent_id: str,
        file_path: Path,
        source: str,
        project_root: Path,
        depth: int,
        max_depth: int,
        call_stack: List[str],
        class_context: Optional[str] = None,
        imports: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> None:
        """
        Recursively extract calls from a function body.

        Uses per-branch cycle detection via call_stack instead of global visited set.
        This allows the same function to appear in different call paths.
        """
        if depth > max_depth:
            graph.max_depth_reached = True
            graph.diagnostics["max_depth_reached"] = True
            return

        # Find function body
        body = self._find_child_by_type(node, "block")
        if body is None:
            return

        # Extract imports if not provided
        if imports is None:
            tree = self._parser.parse(bytes(source, "utf-8"))
            imports = self._extract_imports(tree.root_node, source)

        # Extract all calls in this function
        calls = self._extract_calls_from_body(body, source)

        # Get type resolver for type inference
        type_resolver = self._get_type_resolver(project_root)

        # Analyze scope for type inference (cached per function)
        scope_info = type_resolver.analyze_scope(node, source, file_path, imports)

        for call_info in calls:
            # Try to resolve the call to a definition
            resolved, status, module_hint = self._resolve_call_v2(
                call_info=call_info,
                file_path=file_path,
                source=source,
                project_root=project_root,
                class_context=class_context,
                imports=imports,
                scope_info=scope_info,
            )

            # Handle external/ignored calls
            if status != ResolutionStatus.RESOLVED_PROJECT:
                ignored_call = IgnoredCall(
                    expression=call_info.qualified_name,
                    status=status,
                    call_site_line=call_info.line,
                    module_hint=module_hint,
                )
                graph.ignored_calls.append(ignored_call)

                # Also track unresolved calls separately for diagnostics
                if status == ResolutionStatus.UNRESOLVED:
                    graph.unresolved_calls.append(call_info.qualified_name)

                continue

            # We have a resolved project call
            target_file, target_func, target_line, target_col, target_class = resolved

            # Build target node ID using stable symbol ID
            target_kind = "method" if target_class else "function"
            target_id = self._make_symbol_id(
                target_file, target_line, target_col, target_kind, target_func
            )

            if target_class:
                target_qualified = f"{target_class}.{target_func}"
            else:
                target_qualified = target_func

            # Per-branch cycle detection: check if this symbol is in current call path
            is_cycle = target_id in call_stack
            if is_cycle:
                graph.diagnostics.setdefault("cycles_detected", []).append({
                    "from": parent_id,
                    "to": target_id,
                    "path": list(call_stack),
                })

            # Add edge (even for cycles, to show the connection)
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

            # Only create node and recurse if not a cycle in this branch
            if is_cycle:
                continue

            # Check if node already exists (from another branch)
            existing_node = graph.get_node(target_id)
            if existing_node is None:
                # Create target node
                target_node = CallNode(
                    id=target_id,
                    name=target_func,
                    qualified_name=target_qualified,
                    file_path=target_file,
                    line=target_line,
                    column=target_col,
                    kind=target_kind,
                    is_entry_point=False,
                    depth=depth,
                    symbol_id=target_id,
                    resolution_status=ResolutionStatus.RESOLVED_PROJECT,
                )
                graph.add_node(target_node)

            # Add to call stack for this branch and recurse
            call_stack.append(target_id)

            if target_file == file_path:
                # Same file - parse from existing tree
                tree = self._parser.parse(bytes(source, "utf-8"))
                target_node_ast, _ = self._find_function_or_method(
                    tree.root_node, target_func, source, target_class
                )
                if target_node_ast:
                    # Update node with complexity metrics now that we have AST
                    node_to_update = graph.get_node(target_id)
                    if node_to_update:
                        node_to_update.complexity = self._calculate_complexity(target_node_ast)
                        node_to_update.loc = self._calculate_loc(target_node_ast)

                    self._extract_calls_recursive(
                        graph=graph,
                        node=target_node_ast,
                        parent_id=target_id,
                        file_path=target_file,
                        source=source,
                        project_root=project_root,
                        depth=depth + 1,
                        max_depth=max_depth,
                        call_stack=call_stack,
                        class_context=target_class,
                        imports=imports,
                    )
            else:
                # Different file - need to load and parse
                try:
                    target_source = target_file.read_text(encoding="utf-8")
                    target_tree = self._parser.parse(bytes(target_source, "utf-8"))
                    target_imports = self._extract_imports(target_tree.root_node, target_source)
                    target_node_ast, _ = self._find_function_or_method(
                        target_tree.root_node, target_func, target_source, target_class
                    )
                    if target_node_ast:
                        # Update node with complexity metrics now that we have AST
                        node_to_update = graph.get_node(target_id)
                        if node_to_update:
                            node_to_update.complexity = self._calculate_complexity(target_node_ast)
                            node_to_update.loc = self._calculate_loc(target_node_ast)

                        self._extract_calls_recursive(
                            graph=graph,
                            node=target_node_ast,
                            parent_id=target_id,
                            file_path=target_file,
                            source=target_source,
                            project_root=project_root,
                            depth=depth + 1,
                            max_depth=max_depth,
                            call_stack=call_stack,
                            class_context=target_class,
                            imports=target_imports,
                        )
                except OSError:
                    logger.debug("Could not read file for recursive extraction: %s", target_file)

            # Remove from call stack after processing this branch
            call_stack.pop()

    def _extract_calls_from_body(self, body: Any, source: str) -> List[CallInfo]:
        """Extract all function/method calls from a code block."""
        calls: List[CallInfo] = []

        for node in self._walk_tree(body):
            if node.type == "call":
                call_info = self._parse_call(node, source)
                if call_info:
                    calls.append(call_info)

        return calls

    def _parse_call(self, node: Any, source: str) -> Optional[CallInfo]:
        """Parse a call node to extract call information."""
        if node.type != "call":
            return None

        # Get the function/method being called
        func_node = node.children[0] if node.children else None
        if func_node is None:
            return None

        name = ""
        receiver = None
        call_type = "direct"

        if func_node.type == "identifier":
            # Direct function call: foo()
            name = self._get_node_text(func_node, source)
            call_type = "direct"
        elif func_node.type == "attribute":
            # Method call: obj.method() or self.method()
            parts = self._parse_attribute_chain(func_node, source)
            if parts:
                receiver = ".".join(parts[:-1]) if len(parts) > 1 else None
                name = parts[-1]
                call_type = "method" if receiver else "direct"

        if not name:
            return None

        # Build qualified name
        if receiver:
            qualified_name = f"{receiver}.{name}"
        else:
            qualified_name = name

        # Extract arguments
        arguments: List[str] = []
        args_node = self._find_child_by_type(node, "argument_list")
        if args_node:
            for child in args_node.children:
                if child.type not in ("(", ")", ","):
                    arg_text = self._get_node_text(child, source)
                    arguments.append(arg_text)

        return CallInfo(
            name=name,
            receiver=receiver,
            qualified_name=qualified_name,
            line=node.start_point[0] + 1,
            call_type=call_type,
            arguments=arguments,
        )

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

    def _resolve_call_v2(
        self,
        call_info: CallInfo,
        file_path: Path,
        source: str,
        project_root: Path,
        class_context: Optional[str] = None,
        imports: Optional[Dict[str, Dict[str, Any]]] = None,
        scope_info: Optional[ScopeInfo] = None,
    ) -> Tuple[
        Optional[Tuple[Path, str, int, int, Optional[str]]],  # resolved: (file, func, line, col, class)
        ResolutionStatus,
        Optional[str],  # module_hint
    ]:
        """
        Resolve a call to its definition location with resolution status.

        Args:
            call_info: Information about the call expression
            file_path: Path to the current file
            source: Source code of the current file
            project_root: Root path for import resolution
            class_context: Current class name if inside a method
            imports: Pre-extracted import information
            scope_info: Type information for the current scope (from TypeResolver)

        Returns:
            Tuple of:
            - resolved: (file_path, function_name, line, col, class_name) or None
            - status: ResolutionStatus
            - module_hint: Optional module name for external calls
        """
        tree = self._parser.parse(bytes(source, "utf-8"))

        # Extract imports if not provided
        if imports is None:
            imports = self._extract_imports(tree.root_node, source)

        # Check for builtins first (quick rejection)
        if call_info.name in PYTHON_BUILTINS:
            return (None, ResolutionStatus.IGNORED_BUILTIN, None)

        # Case 1: self.method() - look in current class
        if call_info.receiver == "self" and class_context:
            method_node = self._find_method_in_class(
                tree.root_node, class_context, call_info.name, source
            )
            if method_node:
                return (
                    (
                        file_path,
                        call_info.name,
                        method_node.start_point[0] + 1,
                        method_node.start_point[1],
                        class_context,
                    ),
                    ResolutionStatus.RESOLVED_PROJECT,
                    None,
                )
            # self.method() not found in class - might be inherited
            # For MVP, mark as unresolved (type inference needed for inheritance)
            return (None, ResolutionStatus.UNRESOLVED, None)

        # Case 2: Direct function call - look in same file
        if call_info.call_type == "direct":
            # First try to find as function in same file
            func_node, found_class = self._find_function_or_method(
                tree.root_node, call_info.name, source
            )
            if func_node:
                return (
                    (
                        file_path,
                        call_info.name,
                        func_node.start_point[0] + 1,
                        func_node.start_point[1],
                        found_class,
                    ),
                    ResolutionStatus.RESOLVED_PROJECT,
                    None,
                )

            # Try to find as class (constructor call)
            class_node = self._find_class(tree.root_node, call_info.name, source)
            if class_node:
                # Return __init__ method if exists, otherwise class definition
                init_node = self._find_method_in_class(
                    tree.root_node, call_info.name, "__init__", source
                )
                if init_node:
                    return (
                        (
                            file_path,
                            "__init__",
                            init_node.start_point[0] + 1,
                            init_node.start_point[1],
                            call_info.name,
                        ),
                        ResolutionStatus.RESOLVED_PROJECT,
                        None,
                    )
                # Class without __init__, point to class definition
                return (
                    (
                        file_path,
                        call_info.name,
                        class_node.start_point[0] + 1,
                        class_node.start_point[1],
                        None,
                    ),
                    ResolutionStatus.RESOLVED_PROJECT,
                    None,
                )

        # Case 3: Check imports and resolve to other files
        if call_info.name in imports:
            import_info = imports[call_info.name]
            module_name = import_info["module"]

            # Check if this is an external module (stdlib or third-party)
            if is_stdlib(module_name):
                return (None, ResolutionStatus.IGNORED_STDLIB, module_name)

            # Try to resolve within project
            resolved_file = self._resolve_import_path(
                module_name, project_root, file_path.parent
            )
            if resolved_file and resolved_file.exists():
                try:
                    target_source = resolved_file.read_text(encoding="utf-8")
                    target_tree = self._parser.parse(bytes(target_source, "utf-8"))
                    original_name = import_info.get("original_name", call_info.name)

                    # Try as function/method
                    target_func, target_class = self._find_function_or_method(
                        target_tree.root_node,
                        original_name,
                        target_source,
                    )
                    if target_func:
                        return (
                            (
                                resolved_file,
                                original_name,
                                target_func.start_point[0] + 1,
                                target_func.start_point[1],
                                target_class,
                            ),
                            ResolutionStatus.RESOLVED_PROJECT,
                            None,
                        )

                    # Try as class (constructor)
                    target_cls = self._find_class(
                        target_tree.root_node, original_name, target_source
                    )
                    if target_cls:
                        init_node = self._find_method_in_class(
                            target_tree.root_node, original_name, "__init__", target_source
                        )
                        if init_node:
                            return (
                                (
                                    resolved_file,
                                    "__init__",
                                    init_node.start_point[0] + 1,
                                    init_node.start_point[1],
                                    original_name,
                                ),
                                ResolutionStatus.RESOLVED_PROJECT,
                                None,
                            )
                        return (
                            (
                                resolved_file,
                                original_name,
                                target_cls.start_point[0] + 1,
                                target_cls.start_point[1],
                                None,
                            ),
                            ResolutionStatus.RESOLVED_PROJECT,
                            None,
                        )
                except OSError:
                    pass

            # Module import found but couldn't resolve in project - third-party
            return (None, ResolutionStatus.IGNORED_THIRD_PARTY, module_name)

        # Case 4: Method call on object (obj.method) - use type inference
        if call_info.receiver and call_info.receiver != "self":
            # First check if receiver is an imported module/name
            if call_info.receiver in imports:
                module_name = imports[call_info.receiver]["module"]
                if is_stdlib(module_name):
                    return (None, ResolutionStatus.IGNORED_STDLIB, module_name)
                return (None, ResolutionStatus.IGNORED_THIRD_PARTY, module_name)

            # Try type inference to resolve the receiver's type
            if scope_info:
                type_resolver = self._get_type_resolver(project_root)
                type_info = type_resolver.resolve_type(call_info.receiver, scope_info)

                if type_info and type_info.name:
                    # We have a type - try to find the method in that type
                    method_result = self._find_method_in_type(
                        type_name=type_info.name,
                        method_name=call_info.name,
                        file_path=file_path,
                        project_root=project_root,
                        imports=imports,
                    )
                    if method_result:
                        target_file, target_method, target_line, target_col, target_class = method_result
                        return (
                            (target_file, target_method, target_line, target_col, target_class),
                            ResolutionStatus.RESOLVED_PROJECT,
                            None,
                        )

            # Unknown receiver - unresolved
            return (None, ResolutionStatus.UNRESOLVED, None)

        # Could not resolve - check if it might be external
        status = self._classify_external(call_info.name)
        if status in (ResolutionStatus.IGNORED_BUILTIN, ResolutionStatus.IGNORED_STDLIB):
            return (None, status, call_info.name)

        # Truly unresolved - not found anywhere
        return (None, ResolutionStatus.UNRESOLVED, None)

    def _resolve_call(
        self,
        call_info: CallInfo,
        file_path: Path,
        source: str,
        project_root: Path,
        class_context: Optional[str] = None,
    ) -> Optional[Tuple[Path, str, int, Optional[str]]]:
        """
        Resolve a call to its definition location (legacy v1 method).

        Returns:
            Tuple of (file_path, function_name, line, class_name) or None if unresolved

        Note:
            This method is kept for backwards compatibility.
            New code should use _resolve_call_v2() instead.
        """
        tree = self._parser.parse(bytes(source, "utf-8"))

        # Case 1: self.method() - look in current class
        if call_info.receiver == "self" and class_context:
            method_node = self._find_method_in_class(
                tree.root_node, class_context, call_info.name, source
            )
            if method_node:
                return (
                    file_path,
                    call_info.name,
                    method_node.start_point[0] + 1,
                    class_context,
                )

        # Case 2: Direct function call - look in same file
        if call_info.call_type == "direct":
            # First try to find as function
            func_node, found_class = self._find_function_or_method(
                tree.root_node, call_info.name, source
            )
            if func_node:
                return (
                    file_path,
                    call_info.name,
                    func_node.start_point[0] + 1,
                    found_class,
                )

            # Try to find as class (constructor call)
            class_node = self._find_class(tree.root_node, call_info.name, source)
            if class_node:
                # Return __init__ method if exists, otherwise class definition
                init_node = self._find_method_in_class(
                    tree.root_node, call_info.name, "__init__", source
                )
                if init_node:
                    return (
                        file_path,
                        "__init__",
                        init_node.start_point[0] + 1,
                        call_info.name,
                    )
                return (
                    file_path,
                    call_info.name,
                    class_node.start_point[0] + 1,
                    None,  # It's the class itself, not a method
                )

        # Case 3: Check imports and resolve to other files
        imports = self._extract_imports(tree.root_node, source)
        if call_info.name in imports:
            import_info = imports[call_info.name]
            resolved_file = self._resolve_import_path(
                import_info["module"], project_root, file_path.parent
            )
            if resolved_file and resolved_file.exists():
                try:
                    target_source = resolved_file.read_text(encoding="utf-8")
                    target_tree = self._parser.parse(bytes(target_source, "utf-8"))
                    target_func, target_class = self._find_function_or_method(
                        target_tree.root_node,
                        import_info.get("original_name", call_info.name),
                        target_source,
                    )
                    if target_func:
                        return (
                            resolved_file,
                            import_info.get("original_name", call_info.name),
                            target_func.start_point[0] + 1,
                            target_class,
                        )
                except OSError:
                    pass

        # Case 4: Attribute call on imported object (obj.method)
        if call_info.receiver and "." not in call_info.receiver:
            # Check if receiver is an imported class instance
            # This is complex and requires type inference - skip for v1
            pass

        return None

    def _extract_imports(self, root: Any, source: str) -> Dict[str, Dict[str, Any]]:
        """Extract import statements and map names to modules."""
        imports: Dict[str, Dict[str, Any]] = {}

        for node in self._walk_tree(root):
            if node.type == "import_statement":
                # import foo, bar
                for child in node.children:
                    if child.type == "dotted_name":
                        module_name = self._get_node_text(child, source)
                        imports[module_name.split(".")[-1]] = {
                            "module": module_name,
                            "type": "import",
                        }

            elif node.type == "import_from_statement":
                # from foo import bar, baz
                # AST structure: from, dotted_name (module), import, dotted_name|identifier (names)
                module_name = None
                seen_import_keyword = False
                for child in node.children:
                    if child.type == "from":
                        continue
                    elif child.type == "import":
                        seen_import_keyword = True
                        continue
                    elif child.type == "dotted_name":
                        name_text = self._get_node_text(child, source)
                        if not seen_import_keyword:
                            # This is the module name (before 'import' keyword)
                            module_name = name_text
                        else:
                            # This is an imported name (after 'import' keyword)
                            # e.g., from foo import Bar where Bar is dotted_name
                            if module_name:
                                imports[name_text] = {
                                    "module": module_name,
                                    "original_name": name_text,
                                    "type": "from",
                                }
                    elif child.type == "import_prefix":
                        # relative import: from . import or from .. import
                        module_name = self._get_node_text(child, source)
                    elif child.type == "aliased_import":
                        # from foo import bar as baz
                        original = None
                        alias = None
                        for subchild in child.children:
                            if subchild.type == "identifier":
                                if original is None:
                                    original = self._get_node_text(subchild, source)
                                else:
                                    alias = self._get_node_text(subchild, source)
                        if original and alias and module_name:
                            imports[alias] = {
                                "module": module_name,
                                "original_name": original,
                                "type": "from",
                            }
                    elif child.type == "identifier":
                        name = self._get_node_text(child, source)
                        if module_name:
                            imports[name] = {
                                "module": module_name,
                                "original_name": name,
                                "type": "from",
                            }

        return imports

    def _resolve_import_path(
        self, module_name: str, project_root: Path, current_dir: Path
    ) -> Optional[Path]:
        """Resolve a module name to a file path within the project."""
        # Handle relative imports
        if module_name.startswith("."):
            # Count leading dots
            dots = 0
            for c in module_name:
                if c == ".":
                    dots += 1
                else:
                    break

            # Navigate up directories
            base_dir = current_dir
            for _ in range(dots - 1):
                base_dir = base_dir.parent

            # Get remaining module path
            remaining = module_name[dots:]
            if remaining:
                module_path = remaining.replace(".", "/")
                candidate = base_dir / f"{module_path}.py"
                if candidate.exists():
                    return candidate
                # Try as package
                candidate = base_dir / module_path / "__init__.py"
                if candidate.exists():
                    return candidate
            return None

        # Absolute import
        module_path = module_name.replace(".", "/")

        # Try as file
        candidate = project_root / f"{module_path}.py"
        if candidate.exists():
            return candidate

        # Try as package
        candidate = project_root / module_path / "__init__.py"
        if candidate.exists():
            return candidate

        return None

    def _find_function_or_method(
        self,
        root: Any,
        name: str,
        source: str,
        class_name: Optional[str] = None,
    ) -> Tuple[Optional[Any], Optional[str]]:
        """
        Find a function or method by name.

        Args:
            root: AST root node
            name: Function/method name to find
            source: Source code
            class_name: If provided, look for method in this class

        Returns:
            Tuple of (node, class_name) or (None, None)
        """
        if class_name:
            # Look for method in specific class
            method = self._find_method_in_class(root, class_name, name, source)
            if method:
                return (method, class_name)
            return (None, None)

        # Look for standalone function first
        for node in self._walk_tree(root):
            if node.type == "function_definition":
                func_name = self._get_function_name(node)
                if func_name == name:
                    # Check if it's inside a class
                    parent = node.parent
                    while parent:
                        if parent.type == "class_definition":
                            cls_name = self._get_class_name(parent)
                            return (node, cls_name)
                        parent = parent.parent
                    return (node, None)

        return (None, None)

    def _find_method_in_class(
        self, root: Any, class_name: str, method_name: str, source: str
    ) -> Optional[Any]:
        """Find a method within a specific class."""
        for node in self._walk_tree(root):
            if node.type == "class_definition":
                cls_name = self._get_class_name(node)
                if cls_name == class_name:
                    # Search for method in class body
                    for child in self._walk_tree(node):
                        if child.type == "function_definition":
                            func_name = self._get_function_name(child)
                            if func_name == method_name:
                                return child
        return None

    def _find_class(
        self, root: Any, class_name: str, source: str
    ) -> Optional[Any]:
        """Find a class definition by name."""
        for node in self._walk_tree(root):
            if node.type == "class_definition":
                name = self._get_class_name(node)
                if name == class_name:
                    return node
        return None

    def _find_method_in_type(
        self,
        type_name: str,
        method_name: str,
        file_path: Path,
        project_root: Path,
        imports: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> Optional[Tuple[Path, str, int, int, str]]:
        """
        Find a method in a class by type name.

        Searches for the class definition in the current file first,
        then looks in imported modules.

        Args:
            type_name: Name of the class/type
            method_name: Name of the method to find
            file_path: Current file path for context
            project_root: Project root for resolving imports
            imports: Pre-extracted import information

        Returns:
            Tuple of (file_path, method_name, line, col, class_name) or None
        """
        try:
            source = file_path.read_text(encoding="utf-8")
            tree = self._parser.parse(bytes(source, "utf-8"))

            # First, try to find class in current file
            method_node = self._find_method_in_class(
                tree.root_node, type_name, method_name, source
            )
            if method_node:
                return (
                    file_path,
                    method_name,
                    method_node.start_point[0] + 1,
                    method_node.start_point[1],
                    type_name,
                )

            # If not found, check if type_name is imported
            if imports is None:
                imports = self._extract_imports(tree.root_node, source)

            if type_name in imports:
                import_info = imports[type_name]
                module_name = import_info["module"]

                # Try to resolve the import to a file
                resolved_file = self._resolve_import_path(
                    module_name, project_root, file_path.parent
                )
                if resolved_file and resolved_file.exists():
                    target_source = resolved_file.read_text(encoding="utf-8")
                    target_tree = self._parser.parse(bytes(target_source, "utf-8"))

                    # Look for method in the imported class
                    original_name = import_info.get("original_name", type_name)
                    method_node = self._find_method_in_class(
                        target_tree.root_node, original_name, method_name, target_source
                    )
                    if method_node:
                        return (
                            resolved_file,
                            method_name,
                            method_node.start_point[0] + 1,
                            method_node.start_point[1],
                            original_name,
                        )

        except OSError:
            logger.debug("Could not read file for type resolution: %s", file_path)

        return None

    def _count_calls_in_node(self, node: Any) -> int:
        """
        Count function/method calls within an AST node.

        Args:
            node: AST node (typically a function_definition)

        Returns:
            Number of call expressions found in the node
        """
        count = 0
        for child in self._walk_tree(node):
            if child.type == "call":
                count += 1
        return count

    def list_entry_points(self, file_path: Path) -> List[Dict[str, Any]]:
        """
        List all functions and methods in a file that could be entry points.

        Args:
            file_path: Path to Python file

        Returns:
            List of entry point info with name, qualified_name, line, kind, node_count
        """
        if not self._ensure_parser():
            return []

        try:
            source = file_path.read_text(encoding="utf-8")
        except OSError:
            return []

        tree = self._parser.parse(bytes(source, "utf-8"))
        entry_points: List[Dict[str, Any]] = []

        for node in self._walk_tree(tree.root_node):
            if node.type == "function_definition":
                func_name = self._get_function_name(node)
                if func_name and not func_name.startswith("_"):
                    # Check if method or function
                    parent = node.parent
                    class_name = None
                    while parent:
                        if parent.type == "class_definition":
                            class_name = self._get_class_name(parent)
                            break
                        parent = parent.parent

                    if class_name:
                        qualified_name = f"{class_name}.{func_name}"
                        kind = "method"
                    else:
                        qualified_name = func_name
                        kind = "function"

                    # Count calls within this function
                    call_count = self._count_calls_in_node(node)

                    entry_points.append({
                        "name": func_name,
                        "qualified_name": qualified_name,
                        "line": node.start_point[0] + 1,
                        "kind": kind,
                        "class_name": class_name,
                        "node_count": call_count,
                    })

            elif node.type == "class_definition":
                # Include class itself as potential entry point
                class_name = self._get_class_name(node)
                if class_name and not class_name.startswith("_"):
                    # Count calls in __init__ method if present
                    init_calls = 0
                    for child in self._walk_tree(node):
                        if child.type == "function_definition":
                            init_name = self._get_function_name(child)
                            if init_name == "__init__":
                                init_calls = self._count_calls_in_node(child)
                                break

                    entry_points.append({
                        "name": class_name,
                        "qualified_name": class_name,
                        "line": node.start_point[0] + 1,
                        "kind": "class",
                        "class_name": None,
                        "node_count": init_calls,
                    })

        return entry_points

    # ─────────────────────────────────────────────────────────────
    # Helper methods
    # ─────────────────────────────────────────────────────────────

    def _walk_tree(self, node: Any):
        """Walk AST tree yielding all nodes."""
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

    def _get_class_name(self, node: Any) -> Optional[str]:
        """Extract class name from class_definition node."""
        for child in node.children:
            if child.type == "identifier":
                text = child.text
                if isinstance(text, bytes):
                    return text.decode("utf-8")
                return text
        return None

    def _get_docstring(self, node: Any, source: str) -> Optional[str]:
        """Get first line of docstring from a function definition."""
        body = self._find_child_by_type(node, "block")
        if body is None:
            return None

        for child in body.children:
            if child.type == "expression_statement":
                for subchild in child.children:
                    if subchild.type == "string":
                        doc = self._get_node_text(subchild, source)
                        # Clean up and get first line
                        doc = doc.strip("\"'")
                        first_line = doc.split("\n")[0].strip()
                        return first_line if first_line else None
            break
        return None
