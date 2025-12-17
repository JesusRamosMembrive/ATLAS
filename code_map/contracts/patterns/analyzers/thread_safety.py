# SPDX-License-Identifier: MIT
"""
Thread Safety Analyzer for L4 static analysis.

Detects thread safety from:
- Synchronization primitives (mutex, atomic, lock_guard)
- Naming patterns (Safe*, ThreadSafe*, *Queue, *Pool)
- Member naming conventions (*_mutex, *_lock)
"""

import re
from typing import List, Set

from tree_sitter import Node

from ..models import L4Confidence, L4Finding, L4FindingType
from ..queries.cpp import CppQueryHelper


class ThreadSafetyAnalyzer:
    """Analyzes thread safety from synchronization primitives and naming."""

    name = "thread_safety"

    # Standard library synchronization types (HIGH confidence)
    SYNC_TYPES = {
        "mutex": L4Confidence.HIGH,
        "shared_mutex": L4Confidence.HIGH,
        "recursive_mutex": L4Confidence.HIGH,
        "timed_mutex": L4Confidence.HIGH,
        "atomic": L4Confidence.HIGH,
        "lock_guard": L4Confidence.HIGH,
        "unique_lock": L4Confidence.HIGH,
        "shared_lock": L4Confidence.HIGH,
        "scoped_lock": L4Confidence.HIGH,
        "condition_variable": L4Confidence.HIGH,
        "condition_variable_any": L4Confidence.HIGH,
        "counting_semaphore": L4Confidence.HIGH,
        "binary_semaphore": L4Confidence.HIGH,
        "latch": L4Confidence.HIGH,
        "barrier": L4Confidence.HIGH,
    }

    # Naming patterns that suggest thread safety (MEDIUM confidence)
    SAFE_TYPE_PATTERNS = [
        (re.compile(r"^Safe[A-Z]"), L4Confidence.MEDIUM),  # SafeQueue
        (re.compile(r"^ThreadSafe"), L4Confidence.MEDIUM),  # ThreadSafeMap
        (re.compile(r"^Concurrent"), L4Confidence.MEDIUM),  # ConcurrentQueue
        (re.compile(r"^Synchronized"), L4Confidence.MEDIUM),  # SynchronizedList
        (re.compile(r"^Atomic[A-Z]"), L4Confidence.MEDIUM),  # AtomicCounter
        (re.compile(r"Queue$"), L4Confidence.LOW),  # MessageQueue (maybe safe)
        (re.compile(r"Pool$"), L4Confidence.LOW),  # ThreadPool (maybe safe)
        (re.compile(r"Cache$"), L4Confidence.LOW),  # SharedCache (maybe safe)
        (re.compile(r"Buffer$"), L4Confidence.LOW),  # RingBuffer (maybe safe)
    ]

    # Member name patterns that suggest synchronization (HIGH confidence)
    SYNC_MEMBER_PATTERNS = [
        re.compile(r"_mutex$"),
        re.compile(r"_mtx$"),
        re.compile(r"_lock$"),
        re.compile(r"^mutex_"),
        re.compile(r"^lock_"),
        re.compile(r"_cv$"),
        re.compile(r"_cond$"),
    ]

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
        helper = CppQueryHelper(source)

        for class_node in helper.find_class_declarations(ast):
            class_findings = self._analyze_class(class_node, helper)
            findings.extend(class_findings)

        return findings

    def _analyze_class(self, class_node: Node, helper: CppQueryHelper) -> List[L4Finding]:
        """Analyze a single class for thread safety patterns."""
        findings = []
        mechanisms_found: Set[str] = set()
        highest_confidence = L4Confidence.LOW
        evidence_items: List[str] = []

        # Check class name for thread safety patterns
        class_name = helper.get_class_name(class_node)
        if class_name:
            class_finding = self._check_type_name_pattern(class_name)
            if class_finding:
                confidence, _ = class_finding
                if confidence.value > highest_confidence.value:
                    highest_confidence = confidence
                mechanisms_found.add(f"class name: {class_name}")
                evidence_items.append(f"class {class_name}")

        # Check field types and names
        for field in helper.find_field_declarations(class_node):
            # Check for standard sync types
            field_finding = self._analyze_field_type(field)
            if field_finding:
                confidence, mechanism = field_finding
                if confidence.value > highest_confidence.value:
                    highest_confidence = confidence
                mechanisms_found.add(mechanism)
                evidence_items.append(f"{field.type_name} {field.name}")
                continue

            # Check field type name pattern (SafeQueue, etc.)
            type_pattern_match = self._check_type_name_pattern(field.type_name)
            if type_pattern_match:
                confidence, _ = type_pattern_match
                if confidence.value > highest_confidence.value:
                    highest_confidence = confidence
                mechanisms_found.add(f"type: {field.type_name}")
                evidence_items.append(f"{field.type_name} {field.name}")
                continue

            # Check member name pattern (*_mutex, etc.)
            if self._is_sync_member_name(field.name):
                highest_confidence = L4Confidence.HIGH
                mechanisms_found.add(f"sync member: {field.name}")
                evidence_items.append(f"{field.type_name} {field.name}")

        # Generate findings
        if mechanisms_found:
            findings.append(
                L4Finding(
                    type=L4FindingType.THREAD_SAFETY,
                    confidence=highest_confidence,
                    value="safe",
                    evidence="; ".join(evidence_items[:5]),  # Limit evidence items
                )
            )

            # Add detail about mechanisms
            if len(mechanisms_found) > 1:
                findings.append(
                    L4Finding(
                        type=L4FindingType.THREAD_SAFETY,
                        confidence=highest_confidence,
                        value=f"mechanisms: {', '.join(sorted(mechanisms_found)[:3])}",
                        evidence=f"{len(mechanisms_found)} sync primitives detected",
                    )
                )

        return findings

    def _analyze_field_type(self, field) -> tuple[L4Confidence, str] | None:
        """Check if field type is a synchronization primitive."""
        # Check template name (e.g., atomic<T>)
        if field.template_name:
            template_lower = field.template_name.lower()
            if template_lower in self.SYNC_TYPES:
                return self.SYNC_TYPES[template_lower], f"std::{template_lower}"

        # Check full type name
        type_lower = field.type_name.lower().replace("std::", "")

        # Direct match
        if type_lower in self.SYNC_TYPES:
            return self.SYNC_TYPES[type_lower], f"std::{type_lower}"

        # Partial match (for qualified names like std::mutex)
        for sync_type, confidence in self.SYNC_TYPES.items():
            if sync_type in type_lower:
                return confidence, f"std::{sync_type}"

        return None

    def _check_type_name_pattern(self, type_name: str) -> tuple[L4Confidence, str] | None:
        """Check if type name matches thread safety patterns."""
        for pattern, confidence in self.SAFE_TYPE_PATTERNS:
            if pattern.search(type_name):
                return confidence, type_name
        return None

    def _is_sync_member_name(self, name: str) -> bool:
        """Check if member name suggests synchronization."""
        for pattern in self.SYNC_MEMBER_PATTERNS:
            if pattern.search(name):
                return True
        return False
