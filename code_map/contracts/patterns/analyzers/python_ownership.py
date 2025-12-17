# SPDX-License-Identifier: MIT
"""
Ownership Analyzer for Python L4 static analysis.

Detects ownership relations from field assignments in __init__:
- Parameter assignment (self._x = x) -> uses/stores the dependency
- New object creation (self._x = SomeClass()) -> owns
- Threading primitives (self._lock = Lock()) -> owns
"""

from typing import List

from tree_sitter import Node

from ..models import L4Confidence, L4Finding, L4FindingType
from ..queries.python import PythonQueryHelper


class PythonOwnershipAnalyzer:
    """Analyzes ownership relations in Python classes."""

    name = "python_ownership"

    # Types that indicate exclusive ownership when instantiated
    OWNED_TYPES = {
        "Lock": L4Confidence.HIGH,
        "RLock": L4Confidence.HIGH,
        "Condition": L4Confidence.HIGH,
        "Semaphore": L4Confidence.HIGH,
        "Event": L4Confidence.HIGH,
        "Barrier": L4Confidence.HIGH,
        "Queue": L4Confidence.MEDIUM,
        "deque": L4Confidence.MEDIUM,
        "dict": L4Confidence.LOW,
        "list": L4Confidence.LOW,
        "set": L4Confidence.LOW,
    }

    # Threading module types
    THREADING_TYPES = {
        "threading.Lock",
        "threading.RLock",
        "threading.Condition",
        "threading.Semaphore",
        "threading.Event",
        "threading.Barrier",
        "threading.Thread",
    }

    # Asyncio types
    ASYNCIO_TYPES = {
        "asyncio.Lock",
        "asyncio.Semaphore",
        "asyncio.Event",
        "asyncio.Condition",
        "asyncio.Queue",
    }

    def analyze(self, ast: Node, source: str) -> List[L4Finding]:
        """
        Analyze AST for ownership patterns.

        Args:
            ast: Tree-sitter AST root node
            source: Original source code

        Returns:
            List of ownership findings
        """
        findings = []
        helper = PythonQueryHelper(source)

        for class_node in helper.find_class_definitions(ast):
            class_name = helper.get_class_name(class_node)

            for field in helper.find_field_assignments(class_node):
                finding = self._analyze_field(field, class_name)
                if finding:
                    findings.append(finding)

        return findings

    def _analyze_field(self, field, class_name: str | None) -> L4Finding | None:
        """Analyze a single field for ownership semantics."""
        assigned_from = field.assigned_from or ""

        # Check if it's a call expression (creating new object)
        if "(" in assigned_from and ")" in assigned_from:
            return self._analyze_instantiation(field, assigned_from)

        # Check if assigned from a parameter (dependency injection)
        if field.type_name:
            # Has type annotation - probably storing a dependency
            return L4Finding(
                type=L4FindingType.OWNERSHIP,
                confidence=L4Confidence.MEDIUM,
                value=f"stores {field.type_name}",
                evidence=f"self.{field.name} = {assigned_from}",
                line=field.line,
                member=field.name,
            )

        # Simple assignment without type info
        if assigned_from and not assigned_from.startswith("self."):
            return L4Finding(
                type=L4FindingType.OWNERSHIP,
                confidence=L4Confidence.LOW,
                value=f"stores {assigned_from}",
                evidence=f"self.{field.name} = {assigned_from}",
                line=field.line,
                member=field.name,
            )

        return None

    def _analyze_instantiation(
        self, field, assigned_from: str
    ) -> L4Finding | None:
        """Analyze ownership when field is assigned from instantiation."""
        # Check for threading types
        for threading_type in self.THREADING_TYPES:
            if threading_type in assigned_from:
                return L4Finding(
                    type=L4FindingType.OWNERSHIP,
                    confidence=L4Confidence.HIGH,
                    value=f"owns {threading_type.split('.')[-1]}",
                    evidence=f"self.{field.name} = {assigned_from}",
                    line=field.line,
                    member=field.name,
                )

        # Check for asyncio types
        for asyncio_type in self.ASYNCIO_TYPES:
            if asyncio_type in assigned_from:
                return L4Finding(
                    type=L4FindingType.OWNERSHIP,
                    confidence=L4Confidence.HIGH,
                    value=f"owns {asyncio_type.split('.')[-1]}",
                    evidence=f"self.{field.name} = {assigned_from}",
                    line=field.line,
                    member=field.name,
                )

        # Check for known owned types
        for type_name, confidence in self.OWNED_TYPES.items():
            if type_name in assigned_from:
                return L4Finding(
                    type=L4FindingType.OWNERSHIP,
                    confidence=confidence,
                    value=f"owns {type_name}",
                    evidence=f"self.{field.name} = {assigned_from}",
                    line=field.line,
                    member=field.name,
                )

        # Generic instantiation - likely owns
        return L4Finding(
            type=L4FindingType.OWNERSHIP,
            confidence=L4Confidence.LOW,
            value=f"owns instance",
            evidence=f"self.{field.name} = {assigned_from}",
            line=field.line,
            member=field.name,
        )
