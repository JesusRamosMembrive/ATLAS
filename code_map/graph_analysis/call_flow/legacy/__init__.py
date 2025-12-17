# SPDX-License-Identifier: MIT
"""
Legacy compatibility module for deprecated call flow APIs.

This module provides backward-compatible wrappers for the deprecated
CrossFileCallGraphExtractor from call_tracer_v2.py.

DEPRECATED: This module will be removed in a future release.
Use the new extractors from code_map.graph_analysis.call_flow.languages instead.

Migration Guide:
    # Old (deprecated)
    from code_map.call_tracer_v2 import CrossFileCallGraphExtractor
    extractor = CrossFileCallGraphExtractor(project_root)
    extractor.analyze_file(filepath)
    graph = extractor.call_graph

    # New (recommended)
    from code_map.graph_analysis.call_flow import PythonCallFlowExtractor
    extractor = PythonCallFlowExtractor(root_path=project_root)
    graph = extractor.extract(filepath, function_name)
"""

from .compat import CrossFileCallGraphExtractor

__all__ = ["CrossFileCallGraphExtractor"]
