# SPDX-License-Identifier: MIT
"""
BaseCallFlowExtractor: Abstract base class for all language extractors.

Defines the common interface and provides shared functionality via mixins.
Language-specific extractors inherit from this and implement abstract methods.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional, Set, TYPE_CHECKING

from ..base.tree_sitter import TreeSitterMixin
from ..base.metrics import MetricsMixin
from ..base.symbols import SymbolMixin
from ..models import CallGraph

if TYPE_CHECKING:
    from code_map.index import SymbolIndex


class BaseCallFlowExtractor(TreeSitterMixin, MetricsMixin, SymbolMixin, ABC):
    """
    Abstract base class for language-specific call flow extractors.

    This class combines shared functionality from mixins:
    - TreeSitterMixin: Parser initialization and tree traversal
    - MetricsMixin: Complexity and LOC calculation
    - SymbolMixin: Symbol ID generation

    Subclasses must implement:
    - LANGUAGE: tree-sitter language name
    - EXTENSIONS: supported file extensions
    - decision_types: node types for complexity calculation
    - extract(): main extraction logic
    - list_entry_points(): list callable entry points

    Example:
        class PythonCallFlowExtractor(BaseCallFlowExtractor):
            LANGUAGE = "python"
            EXTENSIONS = {".py"}

            @property
            def decision_types(self) -> Set[str]:
                return {"if_statement", "for_statement", ...}

            def extract(self, file_path, function_name, ...) -> CallGraph:
                ...

            def list_entry_points(self, file_path) -> List[Dict]:
                ...
    """

    # Subclasses must define these
    LANGUAGE: ClassVar[str] = "python"  # tree-sitter language name
    EXTENSIONS: ClassVar[Set[str]] = {".py"}  # supported file extensions

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
        # Initialize mixins
        TreeSitterMixin.__init__(self)
        # SymbolMixin and MetricsMixin don't need __init__

        self.root_path = root_path
        self.symbol_index = symbol_index

    @property
    @abstractmethod
    def decision_types(self) -> Set[str]:
        """
        Return node types that count as decision points for complexity.

        Example for Python:
            return {
                "if_statement", "elif_clause", "for_statement",
                "while_statement", "except_clause", "with_statement",
                ...
            }
        """
        ...

    @property
    def builtin_functions(self) -> Set[str]:
        """
        Return function names to ignore (builtins, stdlib).

        Override in subclasses for language-specific builtins.
        Default returns empty set.
        """
        return set()

    @abstractmethod
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
            file_path: Path to the source file.
            function_name: Name of the entry point function/method.
            max_depth: Maximum depth to follow calls.
            project_root: Project root for resolving imports.

        Returns:
            CallGraph containing all reachable calls, or None if extraction fails.
        """
        ...

    @abstractmethod
    def list_entry_points(
        self,
        file_path: Path,
    ) -> List[Dict[str, Any]]:
        """
        List all callable entry points in a file.

        Args:
            file_path: Path to the source file.

        Returns:
            List of dictionaries with entry point information:
            - name: function/method name
            - qualified_name: full name including class
            - line: line number
            - kind: "function" or "method"
            - file_path: path to the file
        """
        ...

    @classmethod
    def supports_extension(cls, extension: str) -> bool:
        """
        Check if this extractor supports a file extension.

        Args:
            extension: File extension including dot (e.g., ".py").

        Returns:
            True if extension is supported.
        """
        return extension.lower() in cls.EXTENSIONS

    def _get_docstring(self, func_node: Any, source: str) -> Optional[str]:
        """
        Extract docstring from a function node.

        Override in subclasses for language-specific docstring extraction.

        Args:
            func_node: Function node from tree-sitter.
            source: Source code.

        Returns:
            First line of docstring, or None if not found.
        """
        # Default implementation - subclasses should override
        return None

    # Expose MetricsMixin methods with language-specific decision types
    def _calculate_complexity(self, func_node: Any) -> int:
        """Calculate cyclomatic complexity using language-specific decision types."""
        return MetricsMixin._calculate_complexity(self, func_node, self.decision_types)

    def _get_decision_types(self) -> Set[str]:
        """Return decision types for MetricsMixin."""
        return self.decision_types
