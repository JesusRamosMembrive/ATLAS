# SPDX-License-Identifier: MIT
"""
Dependency Analyzer for Python L4 static analysis.

Detects dependencies from:
- Constructor parameters with type annotations
- Setter methods with type-annotated parameters
- ABC/Protocol interface dependencies
"""

from typing import List

from tree_sitter import Node

from ..models import L4Confidence, L4Finding, L4FindingType
from ..queries.python import PythonQueryHelper


class PythonDependencyAnalyzer:
    """Analyzes dependencies in Python classes."""

    name = "python_dependency"

    # Interface prefixes that indicate abstraction
    INTERFACE_PREFIXES = ("I", "Abstract", "Base")

    # Protocol/ABC patterns
    PROTOCOL_PATTERNS = ("Protocol", "ABC", "Interface")

    # Setter method prefixes
    SETTER_PREFIXES = ("set_", "set", "register_", "register", "add_", "add")

    def analyze(self, ast: Node, source: str) -> List[L4Finding]:
        """
        Analyze AST for dependency patterns.

        Args:
            ast: Tree-sitter AST root node
            source: Original source code

        Returns:
            List of dependency findings
        """
        findings = []
        helper = PythonQueryHelper(source)

        for class_node in helper.find_class_definitions(ast):
            class_name = helper.get_class_name(class_node)

            # Analyze constructor parameters
            for constructor in helper.find_constructors(class_node):
                findings.extend(
                    self._analyze_constructor(constructor, class_name, helper)
                )

            # Analyze setter methods
            for method in helper.find_methods(class_node):
                if self._is_setter_method(method.name):
                    findings.extend(
                        self._analyze_setter(method, class_name, helper)
                    )

        return findings

    def _analyze_constructor(
        self, constructor, class_name: str | None, helper: PythonQueryHelper
    ) -> List[L4Finding]:
        """Analyze constructor parameters for dependencies."""
        findings = []

        for param in constructor.parameters:
            # Skip self
            if param.is_self:
                continue

            # Skip parameters without type annotations
            if not param.type_name:
                continue

            confidence = self._get_dependency_confidence(param.type_name)
            is_interface = self._is_interface_type(param.type_name)

            finding = L4Finding(
                type=L4FindingType.DEPENDENCY,
                confidence=confidence,
                value=f"requires {param.type_name}"
                + (" (interface)" if is_interface else ""),
                evidence=f"__init__({param.name}: {param.type_name})",
                line=constructor.line,
                member=param.name,
            )
            findings.append(finding)

        return findings

    def _analyze_setter(
        self, method, class_name: str | None, helper: PythonQueryHelper
    ) -> List[L4Finding]:
        """Analyze setter methods for optional dependencies."""
        findings = []

        for param in method.parameters:
            # Skip self
            if param.is_self:
                continue

            # Skip parameters without type annotations
            if not param.type_name:
                continue

            # Setters indicate optional dependencies
            confidence = L4Confidence.MEDIUM if param.type_name else L4Confidence.LOW
            is_interface = self._is_interface_type(param.type_name) if param.type_name else False

            finding = L4Finding(
                type=L4FindingType.DEPENDENCY,
                confidence=confidence,
                value=f"optional {param.type_name}"
                + (" (interface)" if is_interface else ""),
                evidence=f"{method.name}({param.name}: {param.type_name})",
                line=method.line,
                member=param.name,
            )
            findings.append(finding)

        return findings

    def _is_setter_method(self, name: str) -> bool:
        """Check if method name indicates a setter."""
        name_lower = name.lower()
        return any(name_lower.startswith(prefix.lower()) for prefix in self.SETTER_PREFIXES)

    def _is_interface_type(self, type_name: str) -> bool:
        """Check if type name follows interface naming conventions."""
        # Check prefixes
        for prefix in self.INTERFACE_PREFIXES:
            if type_name.startswith(prefix) and len(type_name) > len(prefix):
                # Ensure next char is uppercase (e.g., ILogger not Ilogger)
                if type_name[len(prefix)].isupper():
                    return True

        # Check if it's a Protocol or ABC
        for pattern in self.PROTOCOL_PATTERNS:
            if pattern in type_name:
                return True

        return False

    def _get_dependency_confidence(self, type_name: str) -> L4Confidence:
        """Determine confidence level based on type characteristics."""
        # Interface types = high confidence (clear abstraction)
        if self._is_interface_type(type_name):
            return L4Confidence.HIGH

        # Type annotation present = medium confidence
        return L4Confidence.MEDIUM
