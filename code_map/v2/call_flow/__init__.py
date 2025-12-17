# SPDX-License-Identifier: MIT
"""
Call Flow Graph extraction and visualization (v2).

Extracts function call chains from Python source code to visualize
execution flows in GUI applications and event-driven systems.

Key features in v2:
- Resolution status tracking (RESOLVED_PROJECT, IGNORED_*, UNRESOLVED, AMBIGUOUS)
- Stable symbol IDs: {rel_path}:{line}:{col}:{kind}:{name}
- Proper classification of external calls (builtin vs stdlib vs third-party)
- Per-branch cycle detection
- Type inference for obj.method() resolution
"""

from .models import (
    CallNode,
    CallEdge,
    CallGraph,
    IgnoredCall,
    ResolutionStatus,
)
from .type_resolver import TypeResolver, TypeInfo, ScopeInfo

__all__ = [
    "CallNode",
    "CallEdge",
    "CallGraph",
    "IgnoredCall",
    "ResolutionStatus",
    "TypeResolver",
    "TypeInfo",
    "ScopeInfo",
]
