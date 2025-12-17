# SPDX-License-Identifier: MIT
"""
Lifecycle Analyzer for TypeScript/JavaScript L4 static analysis.

Detects lifecycle patterns from:
- Method names (start/stop, init/destroy, etc.)
- Framework lifecycle hooks (Angular, React, Vue)
- Event emitter patterns
"""

from typing import List, Set

from tree_sitter import Node

from ..models import L4Confidence, L4Finding, L4FindingType
from ..queries.typescript import TypeScriptQueryHelper


class TypeScriptLifecycleAnalyzer:
    """Analyzes lifecycle patterns in TypeScript/JavaScript classes."""

    name = "ts_lifecycle"

    # Generic lifecycle method pairs -> (start_phase, end_phase, confidence)
    LIFECYCLE_PAIRS = {
        ("start", "stop"): ("running", "stopped", L4Confidence.HIGH),
        ("run", "stop"): ("running", "stopped", L4Confidence.HIGH),
        ("begin", "end"): ("active", "ended", L4Confidence.MEDIUM),
        ("open", "close"): ("open", "closed", L4Confidence.HIGH),
        ("connect", "disconnect"): ("connected", "disconnected", L4Confidence.HIGH),
        ("initialize", "destroy"): ("initialized", "destroyed", L4Confidence.HIGH),
        ("init", "destroy"): ("initialized", "destroyed", L4Confidence.MEDIUM),
        ("setup", "teardown"): ("setup", "torndown", L4Confidence.HIGH),
        ("enable", "disable"): ("enabled", "disabled", L4Confidence.MEDIUM),
        ("activate", "deactivate"): ("active", "inactive", L4Confidence.MEDIUM),
        ("subscribe", "unsubscribe"): ("subscribed", "unsubscribed", L4Confidence.HIGH),
        ("mount", "unmount"): ("mounted", "unmounted", L4Confidence.HIGH),
    }

    # Single lifecycle methods
    SINGLE_LIFECYCLE_METHODS = {
        "dispose": ("disposed", L4Confidence.HIGH),
        "destroy": ("destroyed", L4Confidence.MEDIUM),
        "cleanup": ("cleaned", L4Confidence.MEDIUM),
        "shutdown": ("shutdown", L4Confidence.HIGH),
        "terminate": ("terminated", L4Confidence.HIGH),
    }

    # Angular lifecycle hooks
    ANGULAR_HOOKS = {
        "ngOnInit": ("initialized", L4Confidence.HIGH),
        "ngOnDestroy": ("destroyed", L4Confidence.HIGH),
        "ngOnChanges": ("updated", L4Confidence.MEDIUM),
        "ngAfterViewInit": ("view-initialized", L4Confidence.HIGH),
        "ngAfterContentInit": ("content-initialized", L4Confidence.HIGH),
    }

    # React lifecycle methods (class components)
    REACT_HOOKS = {
        "componentDidMount": ("mounted", L4Confidence.HIGH),
        "componentWillUnmount": ("unmounting", L4Confidence.HIGH),
        "componentDidUpdate": ("updated", L4Confidence.MEDIUM),
        "shouldComponentUpdate": ("updating", L4Confidence.LOW),
    }

    # Vue lifecycle hooks
    VUE_HOOKS = {
        "created": ("created", L4Confidence.HIGH),
        "mounted": ("mounted", L4Confidence.HIGH),
        "beforeDestroy": ("destroying", L4Confidence.HIGH),
        "destroyed": ("destroyed", L4Confidence.HIGH),
        "beforeUnmount": ("unmounting", L4Confidence.HIGH),
        "unmounted": ("unmounted", L4Confidence.HIGH),
    }

    # Node.js/Express patterns
    NODE_PATTERNS = {
        "listen": ("listening", L4Confidence.MEDIUM),
    }

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
        helper = TypeScriptQueryHelper(source)

        for class_node in helper.find_class_declarations(ast):
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

            # Check for framework-specific hooks
            findings.extend(
                self._analyze_framework_hooks(method_names, class_name, methods)
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

    def _analyze_framework_hooks(
        self, method_names: Set[str], class_name: str | None, methods: list
    ) -> List[L4Finding]:
        """Analyze framework-specific lifecycle hooks."""
        findings = []

        # Check all framework hook sets
        all_hooks = {
            **self.ANGULAR_HOOKS,
            **self.REACT_HOOKS,
            **self.VUE_HOOKS,
            **self.NODE_PATTERNS,
        }

        detected_framework = None
        for hook in method_names:
            if hook in self.ANGULAR_HOOKS:
                detected_framework = "Angular"
                break
            elif hook in self.REACT_HOOKS:
                detected_framework = "React"
                break
            elif hook in self.VUE_HOOKS:
                detected_framework = "Vue"
                break

        for hook_name, (phase, confidence) in all_hooks.items():
            if hook_name in method_names:
                hook_line = next((m.line for m in methods if m.name == hook_name), 0)

                framework_note = f" ({detected_framework})" if detected_framework else ""

                findings.append(
                    L4Finding(
                        type=L4FindingType.LIFECYCLE,
                        confidence=confidence,
                        value=f"hook: {phase}{framework_note}",
                        evidence=f"{hook_name}() lifecycle hook",
                        line=hook_line,
                        member=None,
                    )
                )

        return findings
