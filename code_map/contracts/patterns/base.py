# SPDX-License-Identifier: MIT
"""
Base analyzer protocol for L4 static analysis.
"""

from typing import List, Protocol

from tree_sitter import Node

from .models import L4Finding


class BaseAnalyzer(Protocol):
    """
    Protocol for L4 analyzers.

    Each analyzer focuses on extracting a specific type of contract
    information from the AST.
    """

    @property
    def name(self) -> str:
        """Analyzer identifier (e.g., 'ownership', 'lifecycle')."""
        ...

    def analyze(self, ast: Node, source: str) -> List[L4Finding]:
        """
        Analyze AST and return findings.

        Args:
            ast: Tree-sitter AST root node
            source: Original source code (for text extraction)

        Returns:
            List of findings with confidence levels
        """
        ...
