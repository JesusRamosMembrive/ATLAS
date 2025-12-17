# SPDX-License-Identifier: MIT
"""L4 Static Analyzers for contract extraction."""

# C++ analyzers
from .ownership import OwnershipAnalyzer
from .dependency import DependencyAnalyzer
from .lifecycle import LifecycleAnalyzer
from .thread_safety import ThreadSafetyAnalyzer

# Python analyzers
from .python_ownership import PythonOwnershipAnalyzer
from .python_dependency import PythonDependencyAnalyzer
from .python_lifecycle import PythonLifecycleAnalyzer
from .python_thread_safety import PythonThreadSafetyAnalyzer

# TypeScript/JavaScript analyzers
from .ts_ownership import TypeScriptOwnershipAnalyzer
from .ts_dependency import TypeScriptDependencyAnalyzer
from .ts_lifecycle import TypeScriptLifecycleAnalyzer
from .ts_thread_safety import TypeScriptThreadSafetyAnalyzer

__all__ = [
    # C++
    "OwnershipAnalyzer",
    "DependencyAnalyzer",
    "LifecycleAnalyzer",
    "ThreadSafetyAnalyzer",
    # Python
    "PythonOwnershipAnalyzer",
    "PythonDependencyAnalyzer",
    "PythonLifecycleAnalyzer",
    "PythonThreadSafetyAnalyzer",
    # TypeScript/JavaScript
    "TypeScriptOwnershipAnalyzer",
    "TypeScriptDependencyAnalyzer",
    "TypeScriptLifecycleAnalyzer",
    "TypeScriptThreadSafetyAnalyzer",
]
