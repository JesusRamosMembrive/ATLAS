# SPDX-License-Identifier: MIT
"""
Thread Safety Analyzer for TypeScript/JavaScript L4 static analysis.

Detects concurrency/thread safety patterns from:
- Web Workers usage
- SharedArrayBuffer
- Atomics API
- Mutex/Semaphore patterns (from libraries)
- RxJS Subjects (thread-safe observables)
"""

from typing import List

from tree_sitter import Node

from ..models import L4Confidence, L4Finding, L4FindingType
from ..queries.typescript import TypeScriptQueryHelper


class TypeScriptThreadSafetyAnalyzer:
    """Analyzes thread safety patterns in TypeScript/JavaScript classes."""

    name = "ts_thread_safety"

    # Web Worker types
    WORKER_TYPES = {
        "Worker": L4Confidence.HIGH,
        "SharedWorker": L4Confidence.HIGH,
        "ServiceWorker": L4Confidence.HIGH,
    }

    # Shared memory types
    SHARED_MEMORY_TYPES = {
        "SharedArrayBuffer": L4Confidence.HIGH,
        "Atomics": L4Confidence.HIGH,
    }

    # RxJS subjects (thread-safe by design)
    RXJS_SUBJECTS = {
        "Subject": L4Confidence.MEDIUM,
        "BehaviorSubject": L4Confidence.MEDIUM,
        "ReplaySubject": L4Confidence.MEDIUM,
        "AsyncSubject": L4Confidence.MEDIUM,
    }

    # Mutex/Lock patterns from libraries
    MUTEX_PATTERNS = {
        "Mutex": L4Confidence.HIGH,
        "Semaphore": L4Confidence.HIGH,
        "Lock": L4Confidence.HIGH,
        "AsyncMutex": L4Confidence.HIGH,
        "AsyncLock": L4Confidence.HIGH,
    }

    # Concurrent collection patterns
    CONCURRENT_PATTERNS = {
        "ConcurrentMap": L4Confidence.MEDIUM,
        "ConcurrentQueue": L4Confidence.MEDIUM,
        "ConcurrentSet": L4Confidence.MEDIUM,
    }

    # Type name patterns indicating thread safety
    SAFE_TYPE_PATTERNS = ("ThreadSafe", "Synchronized", "Concurrent", "Atomic")

    # Field name patterns indicating synchronization
    SAFE_NAME_PATTERNS = ("lock", "mutex", "semaphore", "worker")

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
        helper = TypeScriptQueryHelper(source)

        for class_node in helper.find_class_declarations(ast):
            class_name = helper.get_class_name(class_node)

            # Check fields for concurrency types
            has_concurrency_primitive = False
            primitive_lines = []

            for field in helper.find_field_definitions(class_node):
                finding = self._analyze_field(field)
                if finding:
                    findings.append(finding)
                    has_concurrency_primitive = True
                    primitive_lines.append(field.line)

            # If we found concurrency primitives, add overall finding
            if has_concurrency_primitive:
                findings.append(
                    L4Finding(
                        type=L4FindingType.THREAD_SAFETY,
                        confidence=L4Confidence.HIGH,
                        value="concurrency-aware",
                        evidence=f"concurrency primitives at lines {primitive_lines}",
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
        """Analyze a field for thread safety patterns."""
        type_name = field.type_name or ""

        # Check Worker types
        for worker_type, confidence in self.WORKER_TYPES.items():
            if worker_type in type_name:
                return L4Finding(
                    type=L4FindingType.THREAD_SAFETY,
                    confidence=confidence,
                    value=f"uses {worker_type}",
                    evidence=f"{field.name}: {type_name}",
                    line=field.line,
                    member=field.name,
                )

        # Check shared memory types
        for shared_type, confidence in self.SHARED_MEMORY_TYPES.items():
            if shared_type in type_name:
                return L4Finding(
                    type=L4FindingType.THREAD_SAFETY,
                    confidence=confidence,
                    value=f"uses {shared_type}",
                    evidence=f"{field.name}: {type_name}",
                    line=field.line,
                    member=field.name,
                )

        # Check RxJS subjects
        for subject_type, confidence in self.RXJS_SUBJECTS.items():
            if subject_type in type_name:
                return L4Finding(
                    type=L4FindingType.THREAD_SAFETY,
                    confidence=confidence,
                    value=f"uses RxJS {subject_type}",
                    evidence=f"{field.name}: {type_name}",
                    line=field.line,
                    member=field.name,
                )

        # Check mutex patterns
        for mutex_type, confidence in self.MUTEX_PATTERNS.items():
            if mutex_type in type_name:
                return L4Finding(
                    type=L4FindingType.THREAD_SAFETY,
                    confidence=confidence,
                    value=f"uses {mutex_type}",
                    evidence=f"{field.name}: {type_name}",
                    line=field.line,
                    member=field.name,
                )

        # Check concurrent patterns
        for concurrent_type, confidence in self.CONCURRENT_PATTERNS.items():
            if concurrent_type in type_name:
                return L4Finding(
                    type=L4FindingType.THREAD_SAFETY,
                    confidence=confidence,
                    value=f"uses {concurrent_type}",
                    evidence=f"{field.name}: {type_name}",
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
                    evidence=f"field name '{field.name}' suggests concurrency",
                    line=field.line,
                    member=field.name,
                )

        # Check type patterns
        for pattern in self.SAFE_TYPE_PATTERNS:
            if pattern in type_name:
                return L4Finding(
                    type=L4FindingType.THREAD_SAFETY,
                    confidence=L4Confidence.MEDIUM,
                    value="thread-safe type",
                    evidence=f"type {type_name} suggests thread safety",
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
