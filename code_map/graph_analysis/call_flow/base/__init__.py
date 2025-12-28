# SPDX-License-Identifier: MIT
"""
Base mixins and utilities for call flow extractors.

This module provides shared functionality for all language-specific extractors:
- TreeSitterMixin: Tree-sitter parser management and tree traversal (from shared analysis module)
- MetricsMixin: Cyclomatic complexity and LOC calculation
- SymbolMixin: Symbol ID generation
"""

# Import TreeSitterMixin from shared location
from code_map.analysis import TreeSitterMixin

from .metrics import MetricsMixin
from .symbols import SymbolMixin

__all__ = [
    "TreeSitterMixin",
    "MetricsMixin",
    "SymbolMixin",
]
