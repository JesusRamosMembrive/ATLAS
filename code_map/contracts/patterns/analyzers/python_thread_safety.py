# SPDX-License-Identifier: MIT
"""
Thread Safety Analyzer for Python L4 static analysis.

Detects thread safety patterns from:
- threading module primitives (Lock, RLock, Condition, etc.)
- asyncio synchronization primitives
- queue.Queue (thread-safe by design)
- Naming patterns (ThreadSafe*, *Lock, etc.)
"""

from typing import List

from tree_sitter import Node

from ..models import L4Confidence, L4Finding, L4FindingType
from ..queries.python import PythonQueryHelper


class PythonThreadSafetyAnalyzer:
    """Analyzes thread safety patterns in Python classes."""

    name = "python_thread_safety"

    # Threading primitives (field assignments)
    THREADING_PRIMITIVES = {
        "threading.Lock": L4Confidence.HIGH,
        "threading.RLock": L4Confidence.HIGH,
        "threading.Condition": L4Confidence.HIGH,
        "threading.Semaphore": L4Confidence.HIGH,
        "threading.BoundedSemaphore": L4Confidence.HIGH,
        "threading.Event": L4Confidence.MEDIUM,
        "threading.Barrier": L4Confidence.MEDIUM,
        "Lock": L4Confidence.HIGH,
        "RLock": L4Confidence.HIGH,
        "Condition": L4Confidence.MEDIUM,
        "Semaphore": L4Confidence.MEDIUM,
    }

    # Asyncio primitives
    ASYNCIO_PRIMITIVES = {
        "asyncio.Lock": L4Confidence.HIGH,
        "asyncio.Semaphore": L4Confidence.HIGH,
        "asyncio.BoundedSemaphore": L4Confidence.HIGH,
        "asyncio.Event": L4Confidence.MEDIUM,
        "asyncio.Condition": L4Confidence.MEDIUM,
    }

    # Thread-safe queue types
    QUEUE_TYPES = {
        "queue.Queue": L4Confidence.HIGH,
        "queue.LifoQueue": L4Confidence.HIGH,
        "queue.PriorityQueue": L4Confidence.HIGH,
        "asyncio.Queue": L4Confidence.HIGH,
        "Queue": L4Confidence.MEDIUM,
    }

    # Field name patterns indicating thread safety
    SAFE_NAME_PATTERNS = ("_lock", "_mutex", "_semaphore", "_condition")

    # Type name patterns indicating thread safety
    SAFE_TYPE_PATTERNS = ("ThreadSafe", "Synchronized", "Concurrent", "Atomic")

    def analyze(self, ast: Node, source: str) -> List[L4Finding]:
        """
        Analyze AST for thread safety patterns.

        Args:
            ast: Tree-sitter AST root node
            source: Original source code

        Returns:
            List of thread safety findings
        """
        findings = []
        helper = PythonQueryHelper(source)

        for class_node in helper.find_class_definitions(ast):
            class_name = helper.get_class_name(class_node)

            # Check fields for thread safety primitives
            has_sync_primitive = False
            primitive_lines = []

            for field in helper.find_field_assignments(class_node):
                finding = self._analyze_field(field)
                if finding:
                    findings.append(finding)
                    has_sync_primitive = True
                    primitive_lines.append(field.line)

            # If we found sync primitives, mark class as thread-safe
            if has_sync_primitive:
                findings.append(
                    L4Finding(
                        type=L4FindingType.THREAD_SAFETY,
                        confidence=L4Confidence.HIGH,
                        value="safe",
                        evidence=f"synchronization primitives at lines {primitive_lines}",
                        line=min(primitive_lines) if primitive_lines else 0,
                        member=None,
                    )
                )

            # Check class name for thread-safety patterns
            if class_name:
                name_finding = self._analyze_class_name(class_name, class_node)
                if name_finding:
                    findings.append(name_finding)

        return findings

    def _analyze_field(self, field) -> L4Finding | None:
        """Analyze a field for thread safety primitives."""
        assigned_from = field.assigned_from or ""

        # Check threading primitives
        for primitive, confidence in self.THREADING_PRIMITIVES.items():
            if primitive in assigned_from:
                return L4Finding(
                    type=L4FindingType.THREAD_SAFETY,
                    confidence=confidence,
                    value=f"uses {primitive.split('.')[-1]}",
                    evidence=f"self.{field.name} = {assigned_from}",
                    line=field.line,
                    member=field.name,
                )

        # Check asyncio primitives
        for primitive, confidence in self.ASYNCIO_PRIMITIVES.items():
            if primitive in assigned_from:
                return L4Finding(
                    type=L4FindingType.THREAD_SAFETY,
                    confidence=confidence,
                    value=f"uses async {primitive.split('.')[-1]}",
                    evidence=f"self.{field.name} = {assigned_from}",
                    line=field.line,
                    member=field.name,
                )

        # Check queue types
        for queue_type, confidence in self.QUEUE_TYPES.items():
            if queue_type in assigned_from:
                return L4Finding(
                    type=L4FindingType.THREAD_SAFETY,
                    confidence=confidence,
                    value=f"uses thread-safe {queue_type.split('.')[-1]}",
                    evidence=f"self.{field.name} = {assigned_from}",
                    line=field.line,
                    member=field.name,
                )

        # Check field name patterns
        field_name_lower = field.name.lower()
        for pattern in self.SAFE_NAME_PATTERNS:
            if pattern in field_name_lower:
                return L4Finding(
                    type=L4FindingType.THREAD_SAFETY,
                    confidence=L4Confidence.LOW,
                    value="likely synchronized",
                    evidence=f"field name '{field.name}' suggests synchronization",
                    line=field.line,
                    member=field.name,
                )

        # Check type annotation patterns
        if field.type_name:
            for pattern in self.SAFE_TYPE_PATTERNS:
                if pattern in field.type_name:
                    return L4Finding(
                        type=L4FindingType.THREAD_SAFETY,
                        confidence=L4Confidence.MEDIUM,
                        value="thread-safe type",
                        evidence=f"type {field.type_name} suggests thread safety",
                        line=field.line,
                        member=field.name,
                    )

        return None

    def _analyze_class_name(self, class_name: str, class_node: Node) -> L4Finding | None:
        """Check class name for thread-safety patterns."""
        for pattern in self.SAFE_TYPE_PATTERNS:
            if pattern in class_name:
                return L4Finding(
                    type=L4FindingType.THREAD_SAFETY,
                    confidence=L4Confidence.LOW,
                    value="likely thread-safe",
                    evidence=f"class name '{class_name}' suggests thread safety",
                    line=class_node.start_point[0] + 1,
                    member=None,
                )

        return None
