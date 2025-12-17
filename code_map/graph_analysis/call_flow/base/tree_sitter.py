# SPDX-License-Identifier: MIT
"""
TreeSitterMixin: Shared tree-sitter operations for all extractors.

Provides unified tree-sitter initialization and common tree traversal utilities.
This mixin eliminates code duplication across Python, TypeScript, and C++ extractors.
"""

from __future__ import annotations

import logging
from typing import Any, Iterator, Optional

logger = logging.getLogger(__name__)


class TreeSitterMixin:
    """
    Mixin providing tree-sitter parser management and tree traversal utilities.

    All call flow extractors inherit from this mixin to share:
    - Parser initialization with consistent error handling
    - Common tree traversal methods
    - Node text extraction

    Usage:
        class MyExtractor(TreeSitterMixin):
            LANGUAGE = "python"  # or "typescript", "cpp"

            def __init__(self):
                super().__init__()  # Initializes _parser, _available
    """

    # Subclasses should override with their tree-sitter language name
    LANGUAGE: str = "python"

    def __init__(self) -> None:
        """Initialize mixin state."""
        self._parser: Optional[Any] = None
        self._available: Optional[bool] = None

    def is_available(self) -> bool:
        """
        Check if tree-sitter is available for this language.

        Returns:
            True if tree-sitter and the language grammar are available.
        """
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

            # Suppress FutureWarning from tree-sitter
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=FutureWarning)
                language = get_language(self.LANGUAGE)

            parser = parser_cls()
            parser.set_language(language)
            self._parser = parser
            self._available = True
            return True

        except Exception as e:
            logger.debug(f"tree-sitter not available for {self.LANGUAGE}: {e}")
            self._available = False
            return False

    def _ensure_parser(self) -> bool:
        """
        Ensure parser is initialized.

        Returns:
            True if parser is ready for use.
        """
        if self._parser is not None:
            return True
        return self.is_available()

    def _walk_tree(self, node: Any) -> Iterator[Any]:
        """
        Walk tree yielding all nodes in depth-first order.

        Args:
            node: Root node to start walking from.

        Yields:
            All nodes in the subtree including the root.
        """
        yield node
        for child in node.children:
            yield from self._walk_tree(child)

    def _get_node_text(self, node: Any, source: bytes) -> str:
        """
        Get text content of a tree-sitter node.

        Handles both byte and string returns from tree-sitter.

        Args:
            node: Tree-sitter node.
            source: Source code as bytes.

        Returns:
            Text content of the node as a string.
        """
        # Some tree-sitter versions provide .text attribute
        if hasattr(node, "text") and node.text is not None:
            text = node.text
            return text.decode("utf-8") if isinstance(text, bytes) else text

        # Fall back to byte slice extraction
        return source[node.start_byte : node.end_byte].decode("utf-8")

    def _find_child_by_type(self, node: Any, type_name: str) -> Optional[Any]:
        """
        Find first direct child of given type.

        Args:
            node: Parent node to search in.
            type_name: Node type to find.

        Returns:
            First child matching the type, or None if not found.
        """
        for child in node.children:
            if child.type == type_name:
                return child
        return None

    def _find_children_by_type(self, node: Any, type_name: str) -> list:
        """
        Find all direct children of given type.

        Args:
            node: Parent node to search in.
            type_name: Node type to find.

        Returns:
            List of children matching the type.
        """
        return [child for child in node.children if child.type == type_name]

    def _find_descendant_by_type(self, node: Any, type_name: str) -> Optional[Any]:
        """
        Find first descendant of given type (recursive search).

        Args:
            node: Root node to search from.
            type_name: Node type to find.

        Returns:
            First descendant matching the type, or None if not found.
        """
        for descendant in self._walk_tree(node):
            if descendant.type == type_name:
                return descendant
        return None
