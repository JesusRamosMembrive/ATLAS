# SPDX-License-Identifier: MIT
"""
Language-specific call flow extractors.

Each extractor inherits from BaseCallFlowExtractor and provides
language-specific implementations for parsing and resolution.

Available extractors:
- PythonCallFlowExtractor: Python code (.py)
- TsCallFlowExtractor: TypeScript/JavaScript (.ts, .tsx, .js, .jsx)
- CppCallFlowExtractor: C/C++ (.c, .cpp, .h, .hpp)

Usage:
    # Direct import
    from code_map.graph_analysis.call_flow.languages import PythonCallFlowExtractor

    # Lazy import (recommended for large codebases)
    from code_map.graph_analysis.call_flow.languages import get_python_extractor
    PythonCallFlowExtractor = get_python_extractor()
"""

from .base_extractor import BaseCallFlowExtractor

__all__ = [
    "BaseCallFlowExtractor",
    "PythonCallFlowExtractor",
    "TsCallFlowExtractor",
    "CppCallFlowExtractor",
    "get_python_extractor",
    "get_typescript_extractor",
    "get_cpp_extractor",
]


def get_python_extractor():
    """Get Python extractor class (lazy import)."""
    from .python import PythonCallFlowExtractor
    return PythonCallFlowExtractor


def get_typescript_extractor():
    """Get TypeScript extractor class (lazy import)."""
    from .typescript import TsCallFlowExtractor
    return TsCallFlowExtractor


def get_cpp_extractor():
    """Get C++ extractor class (lazy import)."""
    from .cpp import CppCallFlowExtractor
    return CppCallFlowExtractor


# Backward compatibility - direct imports
# These allow: from code_map.graph_analysis.call_flow.languages import PythonCallFlowExtractor
from .python import PythonCallFlowExtractor
from .typescript import TsCallFlowExtractor
from .cpp import CppCallFlowExtractor
