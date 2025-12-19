# SPDX-License-Identifier: MIT
"""
Call Flow Graph extraction and visualization (v2).

Extracts function call chains from Python, TypeScript/JavaScript, and C++
source code to visualize execution flows in GUI applications and event-driven systems.

Key features in v2:
- Resolution status tracking (RESOLVED_PROJECT, IGNORED_*, UNRESOLVED, AMBIGUOUS)
- Stable symbol IDs: {rel_path}:{line}:{col}:{kind}:{name}
- Proper classification of external calls (builtin vs stdlib vs third-party)
- Per-branch cycle detection
- Type inference for obj.method() resolution
- Multi-language support (Python, TypeScript/JavaScript, C++)

Architecture (refactored):
- base/: Shared mixins (TreeSitterMixin, MetricsMixin, SymbolMixin)
- languages/: Language-specific extractors inheriting from BaseCallFlowExtractor
- factory.py: ExtractorFactory for automatic language detection
- models.py: Data models (CallGraph, CallNode, CallEdge)
- type_resolver.py: Type inference for Python

Usage:
    # Using factory (recommended)
    from code_map.graph_analysis.call_flow import get_extractor
    extractor = get_extractor(Path("app.py"))
    graph = extractor.extract(Path("app.py"), "main")

    # Using specific extractor
    from code_map.graph_analysis.call_flow import PythonCallFlowExtractor
    extractor = PythonCallFlowExtractor()
    graph = extractor.extract(Path("app.py"), "main")
"""

# Core models
from .models import (
    CallNode,
    CallEdge,
    CallGraph,
    IgnoredCall,
    ResolutionStatus,
)

# Type resolution (Python-specific)
from .type_resolver import TypeResolver, TypeInfo, ScopeInfo

# Factory for automatic language detection
from .factory import ExtractorFactory, get_extractor

# Base class for custom extractors
from .languages.base_extractor import BaseCallFlowExtractor

# Language-specific extractors (lazy import for performance)
# Use factory methods get_*_extractor() for lazy loading


def get_python_extractor():
    """Get Python extractor class (lazy import)."""
    from .languages.python import PythonCallFlowExtractor

    return PythonCallFlowExtractor


def get_typescript_extractor():
    """Get TypeScript extractor class (lazy import)."""
    from .languages.typescript import TsCallFlowExtractor

    return TsCallFlowExtractor


def get_cpp_extractor():
    """Get C++ extractor class (lazy import)."""
    from .languages.cpp import CppCallFlowExtractor

    return CppCallFlowExtractor


# Backward compatibility - import concrete classes
# These imports make old code work without changes:
#   from code_map.graph_analysis.call_flow import PythonCallFlowExtractor
from .languages.python import PythonCallFlowExtractor  # noqa: E402
from .languages.typescript import TsCallFlowExtractor  # noqa: E402
from .languages.cpp import CppCallFlowExtractor  # noqa: E402

# Legacy imports from old locations (deprecated)
# These are kept for backward compatibility during transition:
# from .extractor import PythonCallFlowExtractor  # -> use languages.python
# from .ts_extractor import TsCallFlowExtractor   # -> use languages.typescript
# from .cpp_extractor import CppCallFlowExtractor # -> use languages.cpp


__all__ = [
    # Core models
    "CallNode",
    "CallEdge",
    "CallGraph",
    "IgnoredCall",
    "ResolutionStatus",
    # Type resolution
    "TypeResolver",
    "TypeInfo",
    "ScopeInfo",
    # Factory
    "ExtractorFactory",
    "get_extractor",
    # Base class
    "BaseCallFlowExtractor",
    # Language extractors
    "PythonCallFlowExtractor",
    "TsCallFlowExtractor",
    "CppCallFlowExtractor",
    # Lazy loader functions
    "get_python_extractor",
    "get_typescript_extractor",
    "get_cpp_extractor",
]
