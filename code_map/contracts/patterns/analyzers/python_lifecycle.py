# SPDX-License-Identifier: MIT
"""
Lifecycle Analyzer for Python L4 static analysis.

Detects lifecycle patterns from:
- Method names (start/stop, init/cleanup, open/close)
- Context manager methods (__enter__/__exit__)
- Async context managers (__aenter__/__aexit__)
"""

from typing import List, Set

from tree_sitter import Node

from ..models import L4Confidence, L4Finding, L4FindingType
from ..queries.python import PythonQueryHelper


class PythonLifecycleAnalyzer:
    """Analyzes lifecycle patterns in Python classes."""

    name = "python_lifecycle"

    # Lifecycle method pairs -> (start_phase, end_phase)
    LIFECYCLE_PAIRS = {
        ("start", "stop"): ("running", "stopped", L4Confidence.HIGH),
        ("run", "stop"): ("running", "stopped", L4Confidence.HIGH),
        ("begin", "end"): ("active", "ended", L4Confidence.MEDIUM),
        ("open", "close"): ("open", "closed", L4Confidence.HIGH),
        ("connect", "disconnect"): ("connected", "disconnected", L4Confidence.HIGH),
        ("initialize", "cleanup"): ("initialized", "cleaned", L4Confidence.HIGH),
        ("init", "cleanup"): ("initialized", "cleaned", L4Confidence.MEDIUM),
        ("setup", "teardown"): ("setup", "torndown", L4Confidence.HIGH),
        ("enable", "disable"): ("enabled", "disabled", L4Confidence.MEDIUM),
        ("activate", "deactivate"): ("active", "inactive", L4Confidence.MEDIUM),
        ("acquire", "release"): ("acquired", "released", L4Confidence.HIGH),
        ("enter", "exit"): ("entered", "exited", L4Confidence.MEDIUM),
    }

    # Single lifecycle methods
    SINGLE_LIFECYCLE_METHODS = {
        "shutdown": ("shutdown", L4Confidence.HIGH),
        "dispose": ("disposed", L4Confidence.HIGH),
        "destroy": ("destroyed", L4Confidence.MEDIUM),
        "finalize": ("finalized", L4Confidence.MEDIUM),
        "terminate": ("terminated", L4Confidence.HIGH),
    }

    # Context manager methods
    CONTEXT_MANAGER_SYNC = ("__enter__", "__exit__")
    CONTEXT_MANAGER_ASYNC = ("__aenter__", "__aexit__")

    def analyze(self, ast: Node, source: str) -> List[L4Finding]:
        """
        Analyze AST for lifecycle patterns.

        Args:
            ast: Tree-sitter AST root node
            source: Original source code

        Returns:
            List of lifecycle findings
        """
        findings = []
        helper = PythonQueryHelper(source)

        for class_node in helper.find_class_definitions(ast):
            class_name = helper.get_class_name(class_node)

            # Collect all method names
            methods = list(helper.find_methods(class_node))
            method_names = {m.name for m in methods}

            # Check for lifecycle pairs
            findings.extend(
                self._analyze_lifecycle_pairs(method_names, class_name, methods)
            )

            # Check for single lifecycle methods
            findings.extend(
                self._analyze_single_methods(method_names, class_name, methods)
            )

            # Check for context managers
            findings.extend(
                self._analyze_context_managers(method_names, class_name, methods)
            )

        return findings

    def _analyze_lifecycle_pairs(
        self, method_names: Set[str], class_name: str | None, methods: list
    ) -> List[L4Finding]:
        """Analyze for lifecycle method pairs."""
        findings = []

        for (start_method, end_method), (start_phase, end_phase, confidence) in self.LIFECYCLE_PAIRS.items():
            has_start = start_method in method_names
            has_end = end_method in method_names

            if has_start and has_end:
                # Full lifecycle pair found
                start_line = next((m.line for m in methods if m.name == start_method), 0)

                findings.append(
                    L4Finding(
                        type=L4FindingType.LIFECYCLE,
                        confidence=confidence,
                        value=f"phases: {start_phase}, {end_phase}",
                        evidence=f"{start_method}(), {end_method}() methods",
                        line=start_line,
                        member=None,
                    )
                )
            elif has_start:
                # Only start method - partial lifecycle
                start_line = next((m.line for m in methods if m.name == start_method), 0)

                findings.append(
                    L4Finding(
                        type=L4FindingType.LIFECYCLE,
                        confidence=L4Confidence.LOW,
                        value=f"phase: {start_phase} (no {end_method})",
                        evidence=f"{start_method}() method",
                        line=start_line,
                        member=None,
                    )
                )

        return findings

    def _analyze_single_methods(
        self, method_names: Set[str], class_name: str | None, methods: list
    ) -> List[L4Finding]:
        """Analyze single lifecycle methods."""
        findings = []

        for method_name, (phase, confidence) in self.SINGLE_LIFECYCLE_METHODS.items():
            if method_name in method_names:
                method_line = next((m.line for m in methods if m.name == method_name), 0)

                findings.append(
                    L4Finding(
                        type=L4FindingType.LIFECYCLE,
                        confidence=confidence,
                        value=f"phase: {phase}",
                        evidence=f"{method_name}() method",
                        line=method_line,
                        member=None,
                    )
                )

        return findings

    def _analyze_context_managers(
        self, method_names: Set[str], class_name: str | None, methods: list
    ) -> List[L4Finding]:
        """Analyze context manager patterns."""
        findings = []

        # Check sync context manager
        has_enter = "__enter__" in method_names
        has_exit = "__exit__" in method_names

        if has_enter and has_exit:
            enter_line = next((m.line for m in methods if m.name == "__enter__"), 0)

            findings.append(
                L4Finding(
                    type=L4FindingType.LIFECYCLE,
                    confidence=L4Confidence.HIGH,
                    value="context manager (with statement)",
                    evidence="__enter__(), __exit__() methods",
                    line=enter_line,
                    member=None,
                )
            )

        # Check async context manager
        has_aenter = "__aenter__" in method_names
        has_aexit = "__aexit__" in method_names

        if has_aenter and has_aexit:
            aenter_line = next((m.line for m in methods if m.name == "__aenter__"), 0)

            findings.append(
                L4Finding(
                    type=L4FindingType.LIFECYCLE,
                    confidence=L4Confidence.HIGH,
                    value="async context manager (async with)",
                    evidence="__aenter__(), __aexit__() methods",
                    line=aenter_line,
                    member=None,
                )
            )

        return findings
