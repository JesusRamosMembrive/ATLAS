# SPDX-License-Identifier: MIT
"""
Shared analysis utilities for code parsing and extraction.

This module provides common functionality used by both Call Flow and UML analyzers:
- TreeSitterMixin: Unified tree-sitter parser initialization and traversal
- Future: Symbol ID generation, external call classification
"""

from .tree_sitter_base import TreeSitterMixin

__all__ = ["TreeSitterMixin"]
