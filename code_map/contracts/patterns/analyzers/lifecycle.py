# SPDX-License-Identifier: MIT
"""
Lifecycle Analyzer for L4 static analysis.

Detects lifecycle phases from:
- Method names (start, stop, init, shutdown, etc.)
- State enum members with atomic storage
- State transitions based on method semantics
"""

import re
from typing import Dict, List, Set, Tuple

from tree_sitter import Node

from ..models import L4Confidence, L4Finding, L4FindingType
from ..queries.cpp import CppQueryHelper


class LifecycleAnalyzer:
    """Analyzes lifecycle patterns from method names and state enums."""

    name = "lifecycle"

    # Method name patterns mapped to (target_phase, transition_name)
    LIFECYCLE_METHODS: Dict[Tuple[str, ...], Tuple[str, str]] = {
        # Start methods -> "running" phase
        ("start", "begin", "run", "activate", "launch", "execute"): ("running", "start"),
        # Stop methods -> "stopped" phase
        ("stop", "shutdown", "close", "terminate", "finish", "halt", "kill"): (
            "stopped",
            "stop",
        ),
        # Init methods -> "initialized" phase
        ("init", "initialize", "setup", "configure", "prepare"): (
            "initialized",
            "init",
        ),
        # Cleanup methods -> "destroyed" phase
        ("destroy", "cleanup", "dispose", "release", "teardown", "deinit"): (
            "destroyed",
            "cleanup",
        ),
        # Pause methods -> "paused" phase
        ("pause", "suspend", "freeze", "sleep"): ("paused", "pause"),
        # Resume methods -> "running" phase (from paused)
        ("resume", "wake", "unpause", "unfreeze", "wakeup", "continue"): (
            "running",
            "resume",
        ),
        # Connect methods -> "connected" phase
        ("connect", "open", "attach", "bind"): ("connected", "connect"),
        # Disconnect methods -> "disconnected" phase
        ("disconnect", "detach", "unbind"): ("disconnected", "disconnect"),
    }

    # Patterns for state enum/atomic detection
    STATE_TYPE_PATTERNS = [
        re.compile(r"State$", re.IGNORECASE),
        re.compile(r"Status$", re.IGNORECASE),
        re.compile(r"Phase$", re.IGNORECASE),
        re.compile(r"Mode$", re.IGNORECASE),
    ]

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
        helper = CppQueryHelper(source)

        for class_node in helper.find_class_declarations(ast):
            class_findings = self._analyze_class(class_node, helper)
            findings.extend(class_findings)

        return findings

    def _analyze_class(self, class_node: Node, helper: CppQueryHelper) -> List[L4Finding]:
        """Analyze a single class for lifecycle patterns."""
        findings = []
        phases_found: Set[str] = set()
        transitions: List[str] = []
        has_state_member = False
        state_evidence: List[str] = []

        # Check for atomic state members
        for field in helper.find_field_declarations(class_node):
            if self._is_state_field(field):
                has_state_member = True
                state_evidence.append(f"{field.type_name} {field.name}")

        # Analyze methods for lifecycle patterns
        for method in helper.find_methods(class_node):
            method_name_lower = method.name.lower()

            for patterns, (phase, transition) in self.LIFECYCLE_METHODS.items():
                if self._matches_lifecycle_pattern(method_name_lower, patterns):
                    phases_found.add(phase)
                    transitions.append(f"{method.name}()")
                    break

        # Generate findings
        if phases_found:
            # Create lifecycle phases finding
            findings.append(
                L4Finding(
                    type=L4FindingType.LIFECYCLE,
                    confidence=L4Confidence.MEDIUM,
                    value=f"phases: {', '.join(sorted(phases_found))}",
                    evidence=f"methods: {', '.join(transitions)}",
                )
            )

        if has_state_member:
            # Create state machine finding
            findings.append(
                L4Finding(
                    type=L4FindingType.LIFECYCLE,
                    confidence=L4Confidence.HIGH,
                    value="has state machine",
                    evidence="; ".join(state_evidence),
                )
            )

        # Infer transitions if we have both start and stop
        if "running" in phases_found and "stopped" in phases_found:
            findings.append(
                L4Finding(
                    type=L4FindingType.LIFECYCLE,
                    confidence=L4Confidence.MEDIUM,
                    value="transitions: stopped -> running -> stopped",
                    evidence="start/stop method pair detected",
                )
            )

        if "initialized" in phases_found and "destroyed" in phases_found:
            findings.append(
                L4Finding(
                    type=L4FindingType.LIFECYCLE,
                    confidence=L4Confidence.MEDIUM,
                    value="transitions: uninitialized -> initialized -> destroyed",
                    evidence="init/destroy method pair detected",
                )
            )

        return findings

    def _matches_lifecycle_pattern(self, method_name: str, patterns: Tuple[str, ...]) -> bool:
        """Check if method name matches any lifecycle pattern."""
        # Exact match
        if method_name in patterns:
            return True

        # Prefix match (e.g., "startProcessing" matches "start")
        for pattern in patterns:
            if method_name.startswith(pattern):
                return True

        # Suffix match for common patterns (e.g., "doStart" matches "start")
        for pattern in patterns:
            if method_name.endswith(pattern):
                return True

        return False

    def _is_state_field(self, field) -> bool:
        """Check if field is a state-related member."""
        # Check if it's an atomic type
        is_atomic = field.template_name and "atomic" in field.template_name.lower()

        # Check if the type name suggests state
        type_suggests_state = False
        for pattern in self.STATE_TYPE_PATTERNS:
            if pattern.search(field.type_name):
                type_suggests_state = True
                break

        # Check template args for state types
        if field.template_args:
            for arg in field.template_args:
                for pattern in self.STATE_TYPE_PATTERNS:
                    if pattern.search(arg):
                        type_suggests_state = True
                        break

        # Check field name for state-related patterns
        name_lower = field.name.lower()
        name_suggests_state = any(
            hint in name_lower for hint in ("state", "status", "phase", "mode")
        )

        # High confidence: atomic + state type
        if is_atomic and (type_suggests_state or name_suggests_state):
            return True

        # Medium confidence: just state type (non-atomic)
        if type_suggests_state and name_suggests_state:
            return True

        return False
