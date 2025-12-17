# SPDX-License-Identifier: MIT
"""
Dependency Analyzer for TypeScript/JavaScript L4 static analysis.

Detects dependencies from:
- Constructor parameters with type annotations
- Constructor parameter properties (private/public)
- Setter methods
- Interface implementations
"""

from typing import List

from tree_sitter import Node

from ..models import L4Confidence, L4Finding, L4FindingType
from ..queries.typescript import TypeScriptQueryHelper


class TypeScriptDependencyAnalyzer:
    """Analyzes dependencies in TypeScript/JavaScript classes."""

    name = "ts_dependency"

    # Interface prefixes that indicate abstraction
    INTERFACE_PREFIXES = ("I", "Abstract", "Base")

    # Setter method patterns
    SETTER_PREFIXES = ("set", "register", "add", "configure", "inject")

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
        helper = TypeScriptQueryHelper(source)

        for class_node in helper.find_class_declarations(ast):
            class_name = helper.get_class_name(class_node)

            # Get implemented interfaces
            interfaces = helper.get_implemented_interfaces(class_node)
            for interface in interfaces:
                findings.append(
                    L4Finding(
                        type=L4FindingType.DEPENDENCY,
                        confidence=L4Confidence.HIGH,
                        value=f"implements {interface}",
                        evidence=f"class {class_name} implements {interface}",
                        line=class_node.start_point[0] + 1,
                        member=None,
                    )
                )

            # Analyze constructor parameters
            for constructor in helper.find_constructors(class_node):
                findings.extend(
                    self._analyze_constructor(constructor, class_name)
                )

            # Analyze setter methods
            for method in helper.find_methods(class_node):
                if self._is_setter_method(method.name):
                    findings.extend(self._analyze_setter(method, class_name))

        return findings

    def _analyze_constructor(
        self, constructor, class_name: str | None
    ) -> List[L4Finding]:
        """Analyze constructor parameters for dependencies."""
        findings = []

        for param in constructor.parameters:
            # Skip parameters without type
            if not param.type_name:
                continue

            # Parameter properties are ownership, not just dependencies
            # But we still report them as dependencies too
            is_interface = self._is_interface_type(param.type_name)
            confidence = L4Confidence.HIGH if is_interface else L4Confidence.MEDIUM

            finding = L4Finding(
                type=L4FindingType.DEPENDENCY,
                confidence=confidence,
                value=f"requires {param.type_name}"
                + (" (interface)" if is_interface else ""),
                evidence=f"constructor({param.name}: {param.type_name})",
                line=constructor.line,
                member=param.name,
            )
            findings.append(finding)

        return findings

    def _analyze_setter(self, method, class_name: str | None) -> List[L4Finding]:
        """Analyze setter methods for optional dependencies."""
        findings = []

        for param in method.parameters:
            # Skip parameters without type
            if not param.type_name:
                continue

            is_interface = self._is_interface_type(param.type_name)

            finding = L4Finding(
                type=L4FindingType.DEPENDENCY,
                confidence=L4Confidence.MEDIUM,
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
        return any(name_lower.startswith(prefix) for prefix in self.SETTER_PREFIXES)

    def _is_interface_type(self, type_name: str) -> bool:
        """Check if type name follows interface naming conventions."""
        # Check prefixes
        for prefix in self.INTERFACE_PREFIXES:
            if type_name.startswith(prefix) and len(type_name) > len(prefix):
                # Ensure next char is uppercase
                if type_name[len(prefix)].isupper():
                    return True

        return False
