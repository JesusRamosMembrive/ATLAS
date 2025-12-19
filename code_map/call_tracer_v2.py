# SPDX-License-Identifier: MIT
"""
Call Graph Tracer - DEPRECATED

This module is deprecated and will be removed in a future release.
Use the new extractors from code_map.graph_analysis.call_flow instead.

Migration Guide:
    # Old (this module - deprecated)
    from code_map.call_tracer_v2 import CrossFileCallGraphExtractor
    extractor = CrossFileCallGraphExtractor(project_root)
    extractor.analyze_file(filepath)

    # New (recommended)
    from code_map.graph_analysis.call_flow import PythonCallFlowExtractor
    extractor = PythonCallFlowExtractor(root_path=project_root)
    graph = extractor.extract(filepath, function_name)

The new API provides:
- CallGraph dataclass with nodes, edges, and metrics
- Per-node cyclomatic complexity and LOC
- Cleaner separation of concerns
- Multi-language support (Python, TypeScript, C++)
"""

import warnings

# Emit module-level deprecation warning on import
warnings.warn(
    "The call_tracer_v2 module is deprecated and will be removed in a future release. "
    "Use code_map.graph_analysis.call_flow.languages.PythonCallFlowExtractor instead.",
    DeprecationWarning,
    stacklevel=2,
)

# Re-export from legacy compatibility layer
from .graph_analysis.call_flow.legacy import CrossFileCallGraphExtractor  # noqa: E402

__all__ = ["CrossFileCallGraphExtractor"]
