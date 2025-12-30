# SPDX-License-Identifier: MIT
"""
Python Call Flow extractor using tree-sitter.

Refactored to use BaseCallFlowExtractor and shared mixins.
Reduces code duplication while maintaining full functionality.

Features:
- Proper classification of external calls (builtin/stdlib/third-party)
- Stable symbol IDs: {rel_path}:{line}:{col}:{kind}:{name}
- Per-branch cycle detection (allows same symbol in different paths)
- Optional SymbolIndex integration for faster lookups
- TypeResolver integration for type inference
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional, Set, Tuple, TYPE_CHECKING

from .base_extractor import BaseCallFlowExtractor
from ..constants import PYTHON_BUILTINS, is_stdlib
from ..models import (
    BranchInfo,
    CallEdge,
    CallGraph,
    CallNode,
    DecisionNode,
    DecisionType,
    ExternalCallNode,
    ExternalCallType,
    ExtractionMode,
    IgnoredCall,
    ResolutionStatus,
    ReturnNode,
    StatementNode,
    StatementType,
)
from ..type_resolver import TypeResolver, ScopeInfo

if TYPE_CHECKING:
    from code_map.index import SymbolIndex

logger = logging.getLogger(__name__)


@dataclass
class CallInfo:
    """Information about a Python function/method call."""

    name: str  # Simple name: "foo" or "bar"
    receiver: Optional[str]  # Object receiving the call: "self", "obj", None
    qualified_name: str  # Full call: "self.foo", "obj.bar()", "foo"
    line: int  # Line where call occurs
    call_type: str  # "direct" | "method" | "attribute_chain"
    arguments: List[str]  # Argument expressions


class PythonCallFlowExtractor(BaseCallFlowExtractor):
    """
    Extracts function call flows from Python source code.

    Inherits from BaseCallFlowExtractor to share:
    - Tree-sitter initialization (TreeSitterMixin)
    - Complexity and LOC calculation (MetricsMixin)
    - Symbol ID generation (SymbolMixin)

    Adds Python-specific features:
    - TypeResolver integration for type inference
    - Import resolution across project files
    - Builtin/stdlib/third-party classification

    Example:
        >>> extractor = PythonCallFlowExtractor(Path("/project"))
        >>> graph = extractor.extract(Path("app.py"), "on_button_click", max_depth=5)
        >>> print(graph.to_react_flow())
    """

    # Class variables from BaseCallFlowExtractor
    LANGUAGE: ClassVar[str] = "python"
    EXTENSIONS: ClassVar[Set[str]] = {".py", ".pyw"}

    def __init__(
        self,
        root_path: Optional[Path] = None,
        symbol_index: Optional["SymbolIndex"] = None,
    ) -> None:
        """
        Initialize the extractor.

        Args:
            root_path: Project root for relative paths in symbol IDs.
                       If None, uses file's parent directory.
            symbol_index: Optional SymbolIndex for faster symbol lookups.
        """
        super().__init__(root_path, symbol_index)
        self._type_resolver: Optional[TypeResolver] = None

    @property
    def decision_types(self) -> Set[str]:
        """Python decision point node types for complexity calculation.

        Note: Comprehensions (list/dict/set/generator) are intentionally excluded
        to maintain consistency with code_map/analyzer.py and keep values readable.
        Boolean operators (and/or) are counted separately by MetricsMixin.
        """
        return {
            "if_statement",
            "elif_clause",
            "for_statement",
            "while_statement",
            "except_clause",
            "with_statement",
            "case_clause",  # match/case (Python 3.10+)
            "conditional_expression",  # ternary: x if cond else y
        }

    @property
    def builtin_functions(self) -> Set[str]:
        """Python builtin functions to ignore."""
        return PYTHON_BUILTINS

    # ─────────────────────────────────────────────────────────────
    # Override tree-sitter initialization for Python specifics
    # ─────────────────────────────────────────────────────────────

    def is_available(self) -> bool:
        """Check if tree-sitter is available for Python parsing."""
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

    def _get_type_resolver(self, project_root: Path) -> TypeResolver:
        """Get or create the type resolver (lazy initialization)."""
        if self._type_resolver is None:
            self._type_resolver = TypeResolver(project_root, self._parser)
        return self._type_resolver

    # ─────────────────────────────────────────────────────────────
    # Override complexity calculation for Python-specific patterns
    # ─────────────────────────────────────────────────────────────

    def _calculate_complexity(self, func_node: Any) -> int:
        """
        Calculate cyclomatic complexity (McCabe) for a function node.

        Extended for Python:
        - Counts 'and' and 'or' operators as decision points
        """
        count = 0
        to_visit = [func_node]
        boolean_ops = {"and", "or"}

        while to_visit:
            node = to_visit.pop()
            if node.type in self.decision_types:
                count += 1
            elif node.type == "boolean_operator":
                for child in node.children:
                    if child.type in boolean_ops:
                        count += 1
                        break
            to_visit.extend(node.children)

        return 1 + count

    # ─────────────────────────────────────────────────────────────
    # Python-specific helper methods
    # ─────────────────────────────────────────────────────────────

    def _get_function_name(self, node: Any, source: str = "") -> Optional[str]:
        """Extract function name from function_definition node."""
        for child in node.children:
            if child.type == "identifier":
                text = child.text
                if isinstance(text, bytes):
                    return text.decode("utf-8")
                return text
        return None

    def _get_class_name(self, node: Any, source: str = "") -> Optional[str]:
        """Extract class name from class_definition node."""
        for child in node.children:
            if child.type == "identifier":
                text = child.text
                if isinstance(text, bytes):
                    return text.decode("utf-8")
                return text
        return None

    def _get_docstring(self, func_node: Any, source: str) -> Optional[str]:
        """Get first line of docstring from a function definition."""
        body = self._find_child_by_type(func_node, "block")
        if body is None:
            return None

        for child in body.children:
            if child.type == "expression_statement":
                for subchild in child.children:
                    if subchild.type == "string":
                        doc = self._get_node_text(
                            subchild,
                            (
                                source.encode("utf-8")
                                if isinstance(source, str)
                                else source
                            ),
                        )
                        # Clean up and get first line
                        doc = doc.strip("\"'")
                        first_line = doc.split("\n")[0].strip()
                        return first_line if first_line else None
            break
        return None

    def _should_skip_function(self, name: str) -> bool:
        """Check if function should be skipped from entry points."""
        return name.startswith("_") and not name.startswith("__")

    def _count_calls_in_node(self, node: Any) -> int:
        """Count function/method calls within an AST node."""
        count = 0
        for child in self._walk_tree(node):
            if child.type == "call":
                count += 1
        return count

    def _classify_external(
        self, name: str, module_hint: Optional[str] = None
    ) -> ResolutionStatus:
        """Classify an external (non-project) call."""
        if name in PYTHON_BUILTINS:
            return ResolutionStatus.IGNORED_BUILTIN

        if module_hint:
            if is_stdlib(module_hint):
                return ResolutionStatus.IGNORED_STDLIB
            return ResolutionStatus.IGNORED_THIRD_PARTY

        if is_stdlib(name):
            return ResolutionStatus.IGNORED_STDLIB

        return ResolutionStatus.IGNORED_THIRD_PARTY

    # ─────────────────────────────────────────────────────────────
    # Required abstract method implementations
    # ─────────────────────────────────────────────────────────────

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
                if func_name and not self._should_skip_function(func_name):
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

                    call_count = self._count_calls_in_node(node)

                    entry_points.append(
                        {
                            "name": func_name,
                            "qualified_name": qualified_name,
                            "line": node.start_point[0] + 1,
                            "kind": kind,
                            "class_name": class_name,
                            "node_count": call_count,
                            "file_path": str(file_path),
                        }
                    )

            elif node.type == "class_definition":
                class_name = self._get_class_name(node)
                if class_name and not self._should_skip_function(class_name):
                    # Count calls in __init__ method if present
                    init_calls = 0
                    for child in self._walk_tree(node):
                        if child.type == "function_definition":
                            init_name = self._get_function_name(child)
                            if init_name == "__init__":
                                init_calls = self._count_calls_in_node(child)
                                break

                    entry_points.append(
                        {
                            "name": class_name,
                            "qualified_name": class_name,
                            "line": node.start_point[0] + 1,
                            "kind": "class",
                            "class_name": None,
                            "node_count": init_calls,
                            "file_path": str(file_path),
                        }
                    )

        return entry_points

    def extract(
        self,
        file_path: Path,
        function_name: str,
        max_depth: int = 5,
        project_root: Optional[Path] = None,
        extraction_mode: ExtractionMode = ExtractionMode.FULL,
        expand_branches: Optional[List[str]] = None,
    ) -> Optional[CallGraph]:
        """
        Extract call flow graph starting from a function.

        Args:
            file_path: Path to the Python source file
            function_name: Name of the entry point function/method
            max_depth: Maximum depth to follow calls
            project_root: Project root for resolving imports
            extraction_mode: FULL (all paths) or LAZY (stop at decisions)
            expand_branches: Specific branch IDs to expand (for incremental lazy expansion)

        Returns:
            CallGraph containing all reachable calls, or None if extraction fails
        """
        if not self._ensure_parser():
            logger.warning("tree-sitter not available for call flow extraction")
            return None

        file_path = file_path.resolve()
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
            logger.warning("Function '%s' not found in %s", function_name, file_path)
            return None

        # Build qualified name
        if class_name:
            qualified_name = f"{class_name}.{function_name}"
        else:
            qualified_name = function_name

        # Create entry point node using SymbolMixin
        line = func_node.start_point[0] + 1
        col = func_node.start_point[1]
        kind = "method" if class_name else "function"
        entry_id = self._make_symbol_id(
            file_path, line, col, kind, function_name, effective_root
        )

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
            extraction_mode=extraction_mode.value,
        )
        graph.add_node(entry_node)

        # Extract imports for resolution context
        imports = self._extract_imports(tree.root_node, source)

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
            imports=imports,
            extraction_mode=extraction_mode,
            expand_branches=expand_branches or [],
        )

        return graph

    # ─────────────────────────────────────────────────────────────
    # Internal extraction methods
    # ─────────────────────────────────────────────────────────────

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
        extraction_mode: ExtractionMode = ExtractionMode.FULL,
        expand_branches: Optional[List[str]] = None,
    ) -> None:
        """Recursively extract calls from a function body.

        Args:
            extraction_mode: FULL extracts all paths; LAZY stops at decision points
            expand_branches: Specific branch IDs to expand in LAZY mode
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

        expand_branches = expand_branches or []

        # In LAZY mode, find ALL decision points and process them
        if extraction_mode == ExtractionMode.LAZY:
            all_decisions = self._find_all_decision_points(body)
            if all_decisions:
                # Extract calls before the first decision point
                first_decision = all_decisions[0]
                calls = self._extract_calls_before_decision(body, first_decision, source)

                # Process these calls (same logic as FULL mode)
                self._process_calls(
                    graph=graph,
                    calls=calls,
                    parent_id=parent_id,
                    file_path=file_path,
                    source=source,
                    project_root=project_root,
                    depth=depth,
                    max_depth=max_depth,
                    call_stack=call_stack,
                    class_context=class_context,
                    imports=imports,
                    extraction_mode=extraction_mode,
                    expand_branches=expand_branches,
                )

                # Process each decision point
                for decision_ast in all_decisions:
                    # Parse the decision node
                    decision_node = self._parse_decision_node(
                        decision_ast, source, file_path, parent_id, depth
                    )
                    if decision_node:
                        # Note: add_decision_node already tracks unexpanded branches
                        graph.add_decision_node(decision_node)

                        # Check if any branches should be expanded
                        for branch in decision_node.branches:
                            if branch.branch_id in expand_branches:
                                # This branch should be expanded - extract its contents
                                # Remove from unexpanded list since we're expanding it now
                                if branch.branch_id in graph.unexpanded_branches:
                                    graph.unexpanded_branches.remove(branch.branch_id)
                                self._expand_branch(
                                    graph=graph,
                                    decision_ast=decision_ast,
                                    branch=branch,
                                    decision_node=decision_node,
                                    file_path=file_path,
                                    source=source,
                                    project_root=project_root,
                                    depth=depth,
                                    max_depth=max_depth,
                                    call_stack=call_stack,
                                    class_context=class_context,
                                    imports=imports,
                                    extraction_mode=extraction_mode,
                                    expand_branches=expand_branches,
                                )

                # Stop here (branches not in expand_branches remain unexpanded)
                return

        # FULL mode: Extract all calls in this function
        calls = self._extract_calls_from_body(body, source)

        # Get type resolver for type inference
        type_resolver = self._get_type_resolver(project_root)

        # Analyze scope for type inference
        scope_info = type_resolver.analyze_scope(node, source, file_path, imports)

        for call_info in calls:
            # Try to resolve the call
            resolved, status, module_hint = self._resolve_call_v2(
                call_info=call_info,
                file_path=file_path,
                source=source,
                project_root=project_root,
                class_context=class_context,
                imports=imports,
                scope_info=scope_info,
            )

            # Handle external/ignored calls (no branch context in FULL mode)
            if status != ResolutionStatus.RESOLVED_PROJECT:
                ignored_call = IgnoredCall(
                    expression=call_info.qualified_name,
                    status=status,
                    call_site_line=call_info.line,
                    module_hint=module_hint,
                    caller_id=parent_id,
                    branch_id=None,
                    decision_id=None,
                )
                graph.ignored_calls.append(ignored_call)

                if status == ResolutionStatus.UNRESOLVED:
                    graph.unresolved_calls.append(call_info.qualified_name)
                continue

            # We have a resolved project call
            target_file, target_func, target_line, target_col, target_class = resolved

            # Build target node ID using stable symbol ID
            target_kind = "method" if target_class else "function"
            target_id = self._make_symbol_id(
                target_file,
                target_line,
                target_col,
                target_kind,
                target_func,
                project_root,
            )

            if target_class:
                target_qualified = f"{target_class}.{target_func}"
            else:
                target_qualified = target_func

            # Per-branch cycle detection
            is_cycle = target_id in call_stack
            if is_cycle:
                graph.diagnostics.setdefault("cycles_detected", []).append(
                    {
                        "from": parent_id,
                        "to": target_id,
                        "path": list(call_stack),
                    }
                )

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

            # Check if node already exists (from another branch)
            existing_node = graph.get_node(target_id)
            if existing_node is None:
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
                    # Update node with complexity metrics
                    node_to_update = graph.get_node(target_id)
                    if node_to_update:
                        node_to_update.complexity = self._calculate_complexity(
                            target_node_ast
                        )
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
                        extraction_mode=extraction_mode,
                        expand_branches=expand_branches,
                    )
            else:
                # Different file - need to load and parse
                try:
                    target_source = target_file.read_text(encoding="utf-8")
                    target_tree = self._parser.parse(bytes(target_source, "utf-8"))
                    target_imports = self._extract_imports(
                        target_tree.root_node, target_source
                    )
                    target_node_ast, _ = self._find_function_or_method(
                        target_tree.root_node, target_func, target_source, target_class
                    )
                    if target_node_ast:
                        # Update node with complexity metrics
                        node_to_update = graph.get_node(target_id)
                        if node_to_update:
                            node_to_update.complexity = self._calculate_complexity(
                                target_node_ast
                            )
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
                            extraction_mode=extraction_mode,
                            expand_branches=expand_branches,
                        )
                except OSError:
                    logger.debug(
                        "Could not read file for recursive extraction: %s", target_file
                    )

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

    def _process_calls(
        self,
        graph: CallGraph,
        calls: List[CallInfo],
        parent_id: str,
        file_path: Path,
        source: str,
        project_root: Path,
        depth: int,
        max_depth: int,
        call_stack: List[str],
        class_context: Optional[str] = None,
        imports: Optional[Dict[str, Dict[str, Any]]] = None,
        extraction_mode: ExtractionMode = ExtractionMode.FULL,
        expand_branches: Optional[List[str]] = None,
        branch_id: Optional[str] = None,
        decision_id: Optional[str] = None,
    ) -> None:
        """Process a list of calls, adding nodes/edges and recursing.

        This method extracts the call processing logic from _extract_calls_recursive
        to allow reuse in both FULL and LAZY extraction modes.

        Args:
            branch_id: If processing calls within a branch, the branch ID
            decision_id: If processing calls within a branch, the parent decision ID
        """
        if depth > max_depth:
            return

        # Get type resolver for type inference
        type_resolver = self._get_type_resolver(project_root)

        # Parse the source to get scope info
        tree = self._parser.parse(bytes(source, "utf-8"))

        # We need a function node for scope analysis - use root if we don't have one
        # For now, we'll skip scope-based type resolution in this context
        scope_info = None

        expand_branches = expand_branches or []

        for call_info in calls:
            # Try to resolve the call
            resolved, status, module_hint = self._resolve_call_v2(
                call_info=call_info,
                file_path=file_path,
                source=source,
                project_root=project_root,
                class_context=class_context,
                imports=imports,
                scope_info=scope_info,
            )

            # Handle external/ignored calls (pass branch context if available)
            if status != ResolutionStatus.RESOLVED_PROJECT:
                ignored_call = IgnoredCall(
                    expression=call_info.qualified_name,
                    status=status,
                    call_site_line=call_info.line,
                    module_hint=module_hint,
                    caller_id=parent_id,
                    branch_id=branch_id,
                    decision_id=decision_id,
                )
                graph.ignored_calls.append(ignored_call)

                if status == ResolutionStatus.UNRESOLVED:
                    graph.unresolved_calls.append(call_info.qualified_name)
                continue

            # We have a resolved project call
            target_file, target_func, target_line, target_col, target_class = resolved

            # Build target node ID using stable symbol ID
            target_kind = "method" if target_class else "function"
            target_id = self._make_symbol_id(
                target_file,
                target_line,
                target_col,
                target_kind,
                target_func,
                project_root,
            )

            if target_class:
                target_qualified = f"{target_class}.{target_func}"
            else:
                target_qualified = target_func

            # Per-branch cycle detection
            is_cycle = target_id in call_stack
            if is_cycle:
                graph.diagnostics.setdefault("cycles_detected", []).append(
                    {
                        "from": parent_id,
                        "to": target_id,
                        "path": list(call_stack),
                    }
                )

            # Add edge - include branch context if processing within a branch
            edge = CallEdge(
                source_id=parent_id,
                target_id=target_id,
                call_site_line=call_info.line,
                call_type=call_info.call_type,
                arguments=call_info.arguments if call_info.arguments else None,
                expression=call_info.qualified_name,
                resolution_status=ResolutionStatus.RESOLVED_PROJECT,
                branch_id=branch_id,
                decision_id=decision_id,
            )
            graph.add_edge(edge)

            if is_cycle:
                continue

            # Check if node already exists (from another branch)
            existing_node = graph.get_node(target_id)
            if existing_node is None:
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

            # Add to call stack for this branch and recurse (_process_calls)
            call_stack.append(target_id)

            if target_file == file_path:
                # Same file - parse from existing tree
                target_node_ast, _ = self._find_function_or_method(
                    tree.root_node, target_func, source, target_class
                )
                if target_node_ast:
                    # Update node with complexity metrics
                    node_to_update = graph.get_node(target_id)
                    if node_to_update:
                        node_to_update.complexity = self._calculate_complexity(
                            target_node_ast
                        )
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
                        extraction_mode=extraction_mode,
                        expand_branches=expand_branches,
                    )
            else:
                # Different file - need to load and parse
                try:
                    target_source = target_file.read_text(encoding="utf-8")
                    target_tree = self._parser.parse(bytes(target_source, "utf-8"))
                    target_imports = self._extract_imports(
                        target_tree.root_node, target_source
                    )
                    target_node_ast, _ = self._find_function_or_method(
                        target_tree.root_node, target_func, target_source, target_class
                    )
                    if target_node_ast:
                        # Update node with complexity metrics
                        node_to_update = graph.get_node(target_id)
                        if node_to_update:
                            node_to_update.complexity = self._calculate_complexity(
                                target_node_ast
                            )
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
                            extraction_mode=extraction_mode,
                            expand_branches=expand_branches,
                        )
                except OSError:
                    logger.debug(
                        "Could not read file for recursive extraction: %s", target_file
                    )

            call_stack.pop()

    # ─────────────────────────────────────────────────────────────
    # Decision point detection for lazy extraction
    # ─────────────────────────────────────────────────────────────

    @property
    def _decision_point_types(self) -> Set[str]:
        """Node types that represent decision points for lazy extraction.

        Note: Loops (for_statement, while_statement) are excluded per user preference
        to keep visualization simpler - they're treated as linear flow.
        """
        return {
            "if_statement",  # if/elif/else
            "match_statement",  # Python 3.10+ match/case
            "try_statement",  # try/except/finally
            "conditional_expression",  # ternary: x if cond else y
        }

    def _find_first_decision_point(self, body: Any) -> Optional[Any]:
        """Find the first decision point in a function body.

        Searches recursively through loops (for/while) to find decisions inside them.
        Returns the AST node of the first decision point, or None.
        """
        # Loop types to search inside (not decision points themselves)
        loop_types = {"for_statement", "while_statement"}

        for child in body.children:
            # Direct decision point found
            if child.type in self._decision_point_types:
                return child

            # Search inside loops for nested decision points
            if child.type in loop_types:
                # Find the body of the loop
                loop_body = None
                for sub in child.children:
                    if sub.type == "block":
                        loop_body = sub
                        break

                if loop_body:
                    nested = self._find_first_decision_point(loop_body)
                    if nested:
                        return nested

        return None

    def _find_all_decision_points(self, body: Any) -> List[Any]:
        """Find ALL decision points in a function body (top-level only).

        Unlike _find_first_decision_point, this finds all if/try/match statements
        at the body level (including those nested inside loops).

        Returns a list of AST nodes for all decision points found.
        """
        decisions: List[Any] = []
        # Loop types to search inside (not decision points themselves)
        loop_types = {"for_statement", "while_statement"}

        for child in body.children:
            # Direct decision point found
            if child.type in self._decision_point_types:
                decisions.append(child)

            # Search inside loops for nested decision points
            elif child.type in loop_types:
                # Find the body of the loop
                loop_body = None
                for sub in child.children:
                    if sub.type == "block":
                        loop_body = sub
                        break

                if loop_body:
                    # Recursively find decisions in the loop body
                    nested = self._find_all_decision_points(loop_body)
                    decisions.extend(nested)

        return decisions

    def _extract_calls_before_decision(
        self, body: Any, decision_node: Any, source: str
    ) -> List[CallInfo]:
        """Extract calls that occur before a decision point in the body.

        Handles decision points nested inside loops by extracting calls from
        the containing structure up to the decision point.
        """
        calls: List[CallInfo] = []
        decision_line = decision_node.start_point[0]
        loop_types = {"for_statement", "while_statement"}

        for child in body.children:
            child_start = child.start_point[0]
            child_end = child.end_point[0]

            # If decision is after this child entirely, extract all calls from child
            if decision_line > child_end:
                for node in self._walk_tree(child):
                    if node.type == "call":
                        call_info = self._parse_call(node, source)
                        if call_info:
                            calls.append(call_info)

            # If decision is inside this child (nested in a loop)
            elif child_start <= decision_line <= child_end:
                if child.type in loop_types:
                    # Extract calls from loop header (e.g., range() call in for)
                    for node in self._walk_tree(child):
                        # Stop before the block (loop body)
                        if node.type == "block":
                            break
                        if node.type == "call":
                            call_info = self._parse_call(node, source)
                            if call_info:
                                calls.append(call_info)
                    # Note: calls inside the loop body before the decision
                    # would be executed multiple times, so we don't include them
                break
            else:
                # Decision is before this child, stop
                break

        return calls

    def _expand_branch(
        self,
        graph: CallGraph,
        decision_ast: Any,
        branch: BranchInfo,
        decision_node: "DecisionNode",
        file_path: Path,
        source: str,
        project_root: Path,
        depth: int,
        max_depth: int,
        call_stack: List[str],
        class_context: Optional[str] = None,
        imports: Optional[Dict[str, Dict[str, Any]]] = None,
        extraction_mode: ExtractionMode = ExtractionMode.FULL,
        expand_branches: Optional[List[str]] = None,
    ) -> None:
        """Expand a specific branch from a decision node.

        Finds the branch's AST block and extracts calls from it.
        """
        branch_block = self._find_branch_block(decision_ast, branch)
        if branch_block is None:
            return

        # Mark branch as expanded
        branch.is_expanded = True

        # Remove from unexpanded list if present
        if branch.branch_id in graph.unexpanded_branches:
            graph.unexpanded_branches.remove(branch.branch_id)

        # Extract calls from this branch's block
        calls = self._extract_calls_from_body(branch_block, source)

        # Process the calls (this will recurse into called functions)
        # Pass branch context so edges connect from decision node, not parent
        self._process_calls(
            graph=graph,
            calls=calls,
            parent_id=graph.entry_point,  # Connect to parent decision's caller
            file_path=file_path,
            source=source,
            project_root=project_root,
            depth=depth + 1,
            max_depth=max_depth,
            call_stack=call_stack,
            class_context=class_context,
            imports=imports,
            extraction_mode=extraction_mode,
            expand_branches=expand_branches or [],
            branch_id=branch.branch_id,
            decision_id=decision_node.id,
        )

        # Extract return statements from the branch
        # This is especially important for branches that only have returns
        returns = self._extract_returns_from_body(branch_block, source)
        for ret_info in returns:
            return_node = ReturnNode(
                id=f"return:{file_path}:{ret_info['line']}",
                return_value=ret_info["value"],
                file_path=file_path,
                line=ret_info["line"],
                column=ret_info["column"],
                parent_call_id=graph.entry_point,
                branch_id=branch.branch_id,
                decision_id=decision_node.id,
                depth=depth + 1,
            )
            graph.add_return_node(return_node)

        # Extract statement nodes (break, continue, pass, raise)
        # This ensures branches always show something to the user
        statements = self._extract_statements_from_body(branch_block, source)
        for stmt_info in statements:
            stmt_node = StatementNode(
                id=f"stmt:{file_path}:{stmt_info['line']}:{stmt_info['type'].value}",
                statement_type=stmt_info["type"],
                content=stmt_info["content"],
                file_path=file_path,
                line=stmt_info["line"],
                column=stmt_info["column"],
                parent_call_id=graph.entry_point,
                branch_id=branch.branch_id,
                decision_id=decision_node.id,
                depth=depth + 1,
            )
            graph.add_statement_node(stmt_node)

        # Extract assignment nodes (x = ..., x += ...)
        # This shows data flow operations in branches
        assignments = self._extract_assignments_from_body(branch_block, source)
        for assign_info in assignments:
            assign_node = StatementNode(
                id=f"stmt:{file_path}:{assign_info['line']}:assignment",
                statement_type=StatementType.ASSIGNMENT,
                content=assign_info["content"],
                file_path=file_path,
                line=assign_info["line"],
                column=assign_info["column"],
                parent_call_id=graph.entry_point,
                branch_id=branch.branch_id,
                decision_id=decision_node.id,
                depth=depth + 1,
            )
            graph.add_statement_node(assign_node)

        # Convert IgnoredCalls from this branch to ExternalCallNodes
        # This shows external library calls (requests.get, len, etc.) in the visualization
        for ignored_call in graph.ignored_calls:
            if (ignored_call.branch_id == branch.branch_id and
                ignored_call.decision_id == decision_node.id):
                # Map ResolutionStatus to ExternalCallType
                if ignored_call.status == ResolutionStatus.IGNORED_BUILTIN:
                    call_type = ExternalCallType.BUILTIN
                elif ignored_call.status == ResolutionStatus.IGNORED_STDLIB:
                    call_type = ExternalCallType.STDLIB
                else:
                    call_type = ExternalCallType.THIRD_PARTY

                # Create a unique ID for this external call
                ext_id = f"ext:{file_path}:{ignored_call.call_site_line}:{ignored_call.expression[:30]}"

                ext_node = ExternalCallNode(
                    id=ext_id,
                    expression=ignored_call.expression,
                    call_type=call_type,
                    module_hint=ignored_call.module_hint,
                    file_path=file_path,
                    line=ignored_call.call_site_line,
                    column=0,  # We don't have column info in IgnoredCall
                    parent_call_id=graph.entry_point,
                    branch_id=branch.branch_id,
                    decision_id=decision_node.id,
                    depth=depth + 1,
                )
                graph.add_external_call_node(ext_node)

    def _extract_statements_from_body(
        self, body: Any, source: str
    ) -> List[Dict[str, Any]]:
        """Extract control flow statements from a code block (recursively).

        Finds break, continue, pass, and raise statements at any nesting level.
        Returns a list of dicts with 'type', 'line', 'column', and 'content' keys.
        """
        statements: List[Dict[str, Any]] = []
        if body is None:
            return statements

        source_bytes = source.encode("utf-8")

        def visit_node(node: Any) -> None:
            """Recursively visit nodes to find statements."""
            stmt_type: Optional[StatementType] = None
            content = ""

            if node.type == "break_statement":
                stmt_type = StatementType.BREAK
                content = "break"
            elif node.type == "continue_statement":
                stmt_type = StatementType.CONTINUE
                content = "continue"
            elif node.type == "pass_statement":
                stmt_type = StatementType.PASS
                content = "pass"
            elif node.type == "raise_statement":
                stmt_type = StatementType.RAISE
                # Extract the full raise expression
                content = source_bytes[node.start_byte : node.end_byte].decode("utf-8")

            if stmt_type:
                statements.append({
                    "type": stmt_type,
                    "line": node.start_point[0] + 1,
                    "column": node.start_point[1],
                    "content": content,
                })
            else:
                # Recurse into children for nested structures
                # (loops, if statements, with blocks, etc.)
                for child in node.children:
                    visit_node(child)

        # Start recursive traversal
        for child in body.children:
            visit_node(child)

        return statements

    def _extract_assignments_from_body(
        self, body: Any, source: str
    ) -> List[Dict[str, Any]]:
        """Extract assignment statements from a code block.

        Finds simple assignments (x = ...) and augmented assignments (x += ...).
        Returns a list of dicts with 'type', 'line', 'column', and 'content' keys.
        """
        assignments: List[Dict[str, Any]] = []
        if body is None:
            return assignments

        source_bytes = source.encode("utf-8")
        assignment_types = {"assignment", "augmented_assignment"}

        for child in body.children:
            if child.type in assignment_types:
                content = source_bytes[child.start_byte : child.end_byte].decode("utf-8")
                # Truncate long assignments for display
                if len(content) > 60:
                    content = content[:57] + "..."
                assignments.append({
                    "type": StatementType.ASSIGNMENT,
                    "line": child.start_point[0] + 1,
                    "column": child.start_point[1],
                    "content": content,
                })
            elif child.type == "expression_statement":
                # Handle expression statements that contain assignments
                for subchild in child.children:
                    if subchild.type in assignment_types:
                        content = source_bytes[subchild.start_byte : subchild.end_byte].decode("utf-8")
                        if len(content) > 60:
                            content = content[:57] + "..."
                        assignments.append({
                            "type": StatementType.ASSIGNMENT,
                            "line": subchild.start_point[0] + 1,
                            "column": subchild.start_point[1],
                            "content": content,
                        })

        return assignments

    def _extract_returns_from_body(
        self, body: Any, source: str
    ) -> List[Dict[str, Any]]:
        """Extract return statements from a code block.

        Returns a list of dicts with 'line', 'column', and 'value' keys.
        """
        returns = []
        if body is None:
            return returns

        for child in body.children:
            if child.type == "return_statement":
                line = child.start_point[0] + 1
                column = child.start_point[1]

                # Extract the return value
                value = "None"  # Default for bare return
                for sub in child.children:
                    if sub.type not in ("return",):  # Skip the 'return' keyword
                        value = source[sub.start_byte : sub.end_byte]
                        break

                returns.append({
                    "line": line,
                    "column": column,
                    "value": value,
                })

        return returns

    def _find_branch_block(self, decision_ast: Any, branch: BranchInfo) -> Optional[Any]:
        """Find the AST block node for a specific branch.

        Uses start_line from BranchInfo to locate the correct block.
        """
        target_line = branch.start_line - 1  # Convert to 0-indexed

        if decision_ast.type == "if_statement":
            # Main if block
            main_block = self._find_child_by_type(decision_ast, "block")
            if main_block and main_block.start_point[0] + 1 == branch.start_line:
                return main_block

            # elif and else clauses
            for child in decision_ast.children:
                if child.type in ("elif_clause", "else_clause"):
                    block = self._find_child_by_type(child, "block")
                    if block and block.start_point[0] + 1 == branch.start_line:
                        return block

        elif decision_ast.type == "match_statement":
            for child in decision_ast.children:
                if child.type == "case_clause":
                    block = self._find_child_by_type(child, "block")
                    if block and block.start_point[0] + 1 == branch.start_line:
                        return block

        elif decision_ast.type == "try_statement":
            # Main try block
            main_block = self._find_child_by_type(decision_ast, "block")
            if main_block and main_block.start_point[0] + 1 == branch.start_line:
                return main_block

            # except and finally clauses
            for child in decision_ast.children:
                if child.type in ("except_clause", "finally_clause"):
                    block = self._find_child_by_type(child, "block")
                    if block and block.start_point[0] + 1 == branch.start_line:
                        return block

        return None

    def _parse_decision_node(
        self,
        decision_ast: Any,
        source: str,
        file_path: Path,
        parent_call_id: str,
        depth: int,
    ) -> Optional[DecisionNode]:
        """Parse a tree-sitter decision node into a DecisionNode model."""
        source_bytes = source.encode("utf-8") if isinstance(source, str) else source
        line = decision_ast.start_point[0] + 1
        column = decision_ast.start_point[1]

        if decision_ast.type == "if_statement":
            return self._parse_if_statement(
                decision_ast, source, source_bytes, file_path,
                parent_call_id, depth, line, column
            )
        elif decision_ast.type == "match_statement":
            return self._parse_match_statement(
                decision_ast, source, source_bytes, file_path,
                parent_call_id, depth, line, column
            )
        elif decision_ast.type == "try_statement":
            return self._parse_try_statement(
                decision_ast, source, source_bytes, file_path,
                parent_call_id, depth, line, column
            )
        elif decision_ast.type == "conditional_expression":
            return self._parse_ternary_expression(
                decision_ast, source, source_bytes, file_path,
                parent_call_id, depth, line, column
            )
        return None

    def _parse_if_statement(
        self,
        node: Any,
        source: str,
        source_bytes: bytes,
        file_path: Path,
        parent_call_id: str,
        depth: int,
        line: int,
        column: int,
    ) -> DecisionNode:
        """Parse an if/elif/else statement into a DecisionNode."""
        # Extract condition text
        condition_node = self._find_child_by_type(node, "comparison_operator")
        if condition_node is None:
            # Try other condition types
            for child in node.children:
                if child.type not in ("if", ":", "block", "elif_clause", "else_clause"):
                    condition_node = child
                    break

        condition_text = (
            self._get_node_text(condition_node, source_bytes)
            if condition_node
            else "???"
        )

        decision_id = f"decision:{file_path}:{line}:if_else"
        branches: List[BranchInfo] = []

        # Find the main if block (TRUE branch)
        if_block = self._find_child_by_type(node, "block")
        if if_block:
            branches.append(
                BranchInfo(
                    branch_id=f"{decision_id}:branch:0",
                    label="TRUE",
                    condition_text=condition_text,
                    is_expanded=False,
                    call_count=self._count_calls_in_node(if_block),
                    start_line=if_block.start_point[0] + 1,
                    end_line=if_block.end_point[0] + 1,
                )
            )

        # Find elif and else clauses
        branch_index = 1
        for child in node.children:
            if child.type == "elif_clause":
                elif_condition = None
                elif_block = None
                for subchild in child.children:
                    if subchild.type == "block":
                        elif_block = subchild
                    elif subchild.type not in ("elif", ":"):
                        elif_condition = subchild

                elif_condition_text = (
                    self._get_node_text(elif_condition, source_bytes)
                    if elif_condition
                    else "???"
                )

                if elif_block:
                    branches.append(
                        BranchInfo(
                            branch_id=f"{decision_id}:branch:{branch_index}",
                            label=f"ELIF: {elif_condition_text[:30]}",
                            condition_text=elif_condition_text,
                            is_expanded=False,
                            call_count=self._count_calls_in_node(elif_block),
                            start_line=elif_block.start_point[0] + 1,
                            end_line=elif_block.end_point[0] + 1,
                        )
                    )
                    branch_index += 1

            elif child.type == "else_clause":
                else_block = self._find_child_by_type(child, "block")
                if else_block:
                    branches.append(
                        BranchInfo(
                            branch_id=f"{decision_id}:branch:{branch_index}",
                            label="FALSE",
                            condition_text="else",
                            is_expanded=False,
                            call_count=self._count_calls_in_node(else_block),
                            start_line=else_block.start_point[0] + 1,
                            end_line=else_block.end_point[0] + 1,
                        )
                    )

        return DecisionNode(
            id=decision_id,
            decision_type=DecisionType.IF_ELSE,
            condition_text=condition_text,
            file_path=file_path,
            line=line,
            column=column,
            parent_call_id=parent_call_id,
            branches=branches,
            depth=depth,
        )

    def _parse_match_statement(
        self,
        node: Any,
        source: str,
        source_bytes: bytes,
        file_path: Path,
        parent_call_id: str,
        depth: int,
        line: int,
        column: int,
    ) -> DecisionNode:
        """Parse a match/case statement into a DecisionNode."""
        # Extract the subject being matched
        subject_node = None
        for child in node.children:
            if child.type not in ("match", ":", "block", "case_clause"):
                subject_node = child
                break

        subject_text = (
            self._get_node_text(subject_node, source_bytes)
            if subject_node
            else "???"
        )

        decision_id = f"decision:{file_path}:{line}:match_case"
        branches: List[BranchInfo] = []

        # Find case clauses - they are inside a block child of the match statement
        branch_index = 0
        case_clauses = []
        for child in node.children:
            if child.type == "block":
                # Case clauses are nested inside the block
                for subchild in child.children:
                    if subchild.type == "case_clause":
                        case_clauses.append(subchild)
            elif child.type == "case_clause":
                # Direct case_clause (fallback for different tree-sitter versions)
                case_clauses.append(child)

        for case_node in case_clauses:
            # Extract pattern
            pattern_node = None
            case_block = None
            for subchild in case_node.children:
                if subchild.type == "block":
                    case_block = subchild
                elif subchild.type not in ("case", ":"):
                    pattern_node = subchild

            pattern_text = (
                self._get_node_text(pattern_node, source_bytes)
                if pattern_node
                else "???"
            )

            if case_block:
                branches.append(
                    BranchInfo(
                        branch_id=f"{decision_id}:branch:{branch_index}",
                        label=f"case {pattern_text[:20]}",
                        condition_text=pattern_text,
                        is_expanded=False,
                        call_count=self._count_calls_in_node(case_block),
                        start_line=case_block.start_point[0] + 1,
                        end_line=case_block.end_point[0] + 1,
                    )
                )
                branch_index += 1

        return DecisionNode(
            id=decision_id,
            decision_type=DecisionType.MATCH_CASE,
            condition_text=f"match {subject_text}",
            file_path=file_path,
            line=line,
            column=column,
            parent_call_id=parent_call_id,
            branches=branches,
            depth=depth,
        )

    def _parse_try_statement(
        self,
        node: Any,
        source: str,
        source_bytes: bytes,
        file_path: Path,
        parent_call_id: str,
        depth: int,
        line: int,
        column: int,
    ) -> DecisionNode:
        """Parse a try/except/finally statement into a DecisionNode."""
        decision_id = f"decision:{file_path}:{line}:try_except"
        branches: List[BranchInfo] = []

        # Main try block
        try_block = self._find_child_by_type(node, "block")
        if try_block:
            branches.append(
                BranchInfo(
                    branch_id=f"{decision_id}:branch:0",
                    label="try",
                    condition_text="try block",
                    is_expanded=False,
                    call_count=self._count_calls_in_node(try_block),
                    start_line=try_block.start_point[0] + 1,
                    end_line=try_block.end_point[0] + 1,
                )
            )

        # Find except and finally clauses
        branch_index = 1
        for child in node.children:
            if child.type == "except_clause":
                # Extract exception type
                exception_type = None
                except_block = None
                for subchild in child.children:
                    if subchild.type == "block":
                        except_block = subchild
                    elif subchild.type not in ("except", ":", "as"):
                        exception_type = subchild

                exception_text = (
                    self._get_node_text(exception_type, source_bytes)
                    if exception_type
                    else "Exception"
                )

                if except_block:
                    branches.append(
                        BranchInfo(
                            branch_id=f"{decision_id}:branch:{branch_index}",
                            label=f"except {exception_text[:15]}",
                            condition_text=exception_text,
                            is_expanded=False,
                            call_count=self._count_calls_in_node(except_block),
                            start_line=except_block.start_point[0] + 1,
                            end_line=except_block.end_point[0] + 1,
                        )
                    )
                    branch_index += 1

            elif child.type == "finally_clause":
                finally_block = self._find_child_by_type(child, "block")
                if finally_block:
                    branches.append(
                        BranchInfo(
                            branch_id=f"{decision_id}:branch:{branch_index}",
                            label="finally",
                            condition_text="finally block",
                            is_expanded=False,
                            call_count=self._count_calls_in_node(finally_block),
                            start_line=finally_block.start_point[0] + 1,
                            end_line=finally_block.end_point[0] + 1,
                        )
                    )

        return DecisionNode(
            id=decision_id,
            decision_type=DecisionType.TRY_EXCEPT,
            condition_text="try/except",
            file_path=file_path,
            line=line,
            column=column,
            parent_call_id=parent_call_id,
            branches=branches,
            depth=depth,
        )

    def _parse_ternary_expression(
        self,
        node: Any,
        source: str,
        source_bytes: bytes,
        file_path: Path,
        parent_call_id: str,
        depth: int,
        line: int,
        column: int,
    ) -> DecisionNode:
        """Parse a ternary expression (x if cond else y) into a DecisionNode."""
        # Structure: value_if_true if condition else value_if_false
        condition_text = self._get_node_text(node, source_bytes)

        decision_id = f"decision:{file_path}:{line}:ternary"
        branches: List[BranchInfo] = [
            BranchInfo(
                branch_id=f"{decision_id}:branch:0",
                label="TRUE",
                condition_text="if true",
                is_expanded=False,
                call_count=0,  # Ternary expressions typically inline
                start_line=line,
                end_line=line,
            ),
            BranchInfo(
                branch_id=f"{decision_id}:branch:1",
                label="FALSE",
                condition_text="else",
                is_expanded=False,
                call_count=0,
                start_line=line,
                end_line=line,
            ),
        ]

        return DecisionNode(
            id=decision_id,
            decision_type=DecisionType.TERNARY,
            condition_text=condition_text[:50],  # Truncate long expressions
            file_path=file_path,
            line=line,
            column=column,
            parent_call_id=parent_call_id,
            branches=branches,
            depth=depth,
        )

    def _parse_call(self, node: Any, source: str) -> Optional[CallInfo]:
        """Parse a call node to extract call information."""
        if node.type != "call":
            return None

        func_node = node.children[0] if node.children else None
        if func_node is None:
            return None

        name = ""
        receiver = None
        call_type = "direct"

        if func_node.type == "identifier":
            name = self._get_node_text(
                func_node, source.encode("utf-8") if isinstance(source, str) else source
            )
            call_type = "direct"
        elif func_node.type == "attribute":
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
                    arg_text = self._get_node_text(
                        child,
                        source.encode("utf-8") if isinstance(source, str) else source,
                    )
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
        source_bytes = source.encode("utf-8") if isinstance(source, str) else source

        def extract_parts(n: Any) -> None:
            if n.type == "identifier":
                parts.append(self._get_node_text(n, source_bytes))
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
        Optional[Tuple[Path, str, int, int, Optional[str]]],
        ResolutionStatus,
        Optional[str],
    ]:
        """Resolve a call to its definition location with resolution status."""
        tree = self._parser.parse(bytes(source, "utf-8"))

        if imports is None:
            imports = self._extract_imports(tree.root_node, source)

        # Check for builtins first
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
            return (None, ResolutionStatus.UNRESOLVED, None)

        # Case 2: Direct function call - look in same file
        if call_info.call_type == "direct":
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

            if is_stdlib(module_name):
                return (None, ResolutionStatus.IGNORED_STDLIB, module_name)

            resolved_file = self._resolve_import_path(
                module_name, project_root, file_path.parent
            )
            if resolved_file and resolved_file.exists():
                try:
                    target_source = resolved_file.read_text(encoding="utf-8")
                    target_tree = self._parser.parse(bytes(target_source, "utf-8"))
                    original_name = import_info.get("original_name", call_info.name)

                    target_func, target_class = self._find_function_or_method(
                        target_tree.root_node, original_name, target_source
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

                    target_cls = self._find_class(
                        target_tree.root_node, original_name, target_source
                    )
                    if target_cls:
                        init_node = self._find_method_in_class(
                            target_tree.root_node,
                            original_name,
                            "__init__",
                            target_source,
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

            return (None, ResolutionStatus.IGNORED_THIRD_PARTY, module_name)

        # Case 4: Method call on object (obj.method) - use type inference
        if call_info.receiver and call_info.receiver != "self":
            if call_info.receiver in imports:
                module_name = imports[call_info.receiver]["module"]
                if is_stdlib(module_name):
                    return (None, ResolutionStatus.IGNORED_STDLIB, module_name)
                return (None, ResolutionStatus.IGNORED_THIRD_PARTY, module_name)

            if scope_info:
                type_resolver = self._get_type_resolver(project_root)
                type_info = type_resolver.resolve_type(call_info.receiver, scope_info)

                if type_info and type_info.name:
                    method_result = self._find_method_in_type(
                        type_name=type_info.name,
                        method_name=call_info.name,
                        file_path=file_path,
                        project_root=project_root,
                        imports=imports,
                    )
                    if method_result:
                        (
                            target_file,
                            target_method,
                            target_line,
                            target_col,
                            target_class,
                        ) = method_result
                        return (
                            (
                                target_file,
                                target_method,
                                target_line,
                                target_col,
                                target_class,
                            ),
                            ResolutionStatus.RESOLVED_PROJECT,
                            None,
                        )

            return (None, ResolutionStatus.UNRESOLVED, None)

        # Could not resolve - check if it might be external
        status = self._classify_external(call_info.name)
        if status in (
            ResolutionStatus.IGNORED_BUILTIN,
            ResolutionStatus.IGNORED_STDLIB,
        ):
            return (None, status, call_info.name)

        return (None, ResolutionStatus.UNRESOLVED, None)

    def _extract_imports(self, root: Any, source: str) -> Dict[str, Dict[str, Any]]:
        """Extract import statements and map names to modules."""
        imports: Dict[str, Dict[str, Any]] = {}
        source_bytes = source.encode("utf-8") if isinstance(source, str) else source

        for node in self._walk_tree(root):
            if node.type == "import_statement":
                for child in node.children:
                    if child.type == "dotted_name":
                        module_name = self._get_node_text(child, source_bytes)
                        imports[module_name.split(".")[-1]] = {
                            "module": module_name,
                            "type": "import",
                        }

            elif node.type == "import_from_statement":
                module_name = None
                seen_import_keyword = False
                for child in node.children:
                    if child.type == "from":
                        continue
                    elif child.type == "import":
                        seen_import_keyword = True
                        continue
                    elif child.type == "dotted_name":
                        name_text = self._get_node_text(child, source_bytes)
                        if not seen_import_keyword:
                            module_name = name_text
                        else:
                            if module_name:
                                imports[name_text] = {
                                    "module": module_name,
                                    "original_name": name_text,
                                    "type": "from",
                                }
                    elif child.type == "import_prefix":
                        module_name = self._get_node_text(child, source_bytes)
                    elif child.type == "aliased_import":
                        original = None
                        alias = None
                        for subchild in child.children:
                            if subchild.type == "identifier":
                                if original is None:
                                    original = self._get_node_text(
                                        subchild, source_bytes
                                    )
                                else:
                                    alias = self._get_node_text(subchild, source_bytes)
                        if original and alias and module_name:
                            imports[alias] = {
                                "module": module_name,
                                "original_name": original,
                                "type": "from",
                            }
                    elif child.type == "identifier":
                        name = self._get_node_text(child, source_bytes)
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

        # Absolute import
        module_path = module_name.replace(".", "/")

        candidate = project_root / f"{module_path}.py"
        if candidate.exists():
            return candidate

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
        """Find a function or method by name."""
        if class_name:
            method = self._find_method_in_class(root, class_name, name, source)
            if method:
                return (method, class_name)
            return (None, None)

        for node in self._walk_tree(root):
            if node.type == "function_definition":
                func_name = self._get_function_name(node)
                if func_name == name:
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
                    for child in self._walk_tree(node):
                        if child.type == "function_definition":
                            func_name = self._get_function_name(child)
                            if func_name == method_name:
                                return child
        return None

    def _find_class(self, root: Any, class_name: str, source: str) -> Optional[Any]:
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
        """Find a method in a class by type name."""
        try:
            source = file_path.read_text(encoding="utf-8")
            tree = self._parser.parse(bytes(source, "utf-8"))

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

            if imports is None:
                imports = self._extract_imports(tree.root_node, source)

            if type_name in imports:
                import_info = imports[type_name]
                module_name = import_info["module"]

                resolved_file = self._resolve_import_path(
                    module_name, project_root, file_path.parent
                )
                if resolved_file and resolved_file.exists():
                    target_source = resolved_file.read_text(encoding="utf-8")
                    target_tree = self._parser.parse(bytes(target_source, "utf-8"))

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
