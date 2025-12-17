# SPDX-License-Identifier: MIT
"""
L4 Static Analysis patterns and analyzers.

This package provides:
- StaticAnalyzer: Main orchestrator for L4 analysis
- Individual analyzers for ownership, dependencies, lifecycle, thread safety
- Tree-sitter query helpers for C++ AST navigation
- Data models for findings with sub-level confidence
"""

from .static import StaticAnalyzer
from .models import L4Confidence, L4Finding, L4FindingType

__all__ = [
    "StaticAnalyzer",
    "L4Confidence",
    "L4Finding",
    "L4FindingType",
]
