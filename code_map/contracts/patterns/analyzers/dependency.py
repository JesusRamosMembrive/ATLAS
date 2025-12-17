# SPDX-License-Identifier: MIT
"""
Dependency Analyzer for L4 static analysis.

Detects dependencies from:
- Constructor parameters (injected dependencies)
- Setter methods (optional dependencies)
- Interface pointers/references
"""

import re
from typing import List

from tree_sitter import Node

from ..models import L4Confidence, L4Finding, L4FindingType
from ..queries.cpp import CppQueryHelper, ParameterInfo


class DependencyAnalyzer:
    """Analyzes dependencies from constructors and setters."""

    name = "dependency"

    # Patterns that suggest interface types
    INTERFACE_PATTERNS = [
        re.compile(r"^I[A-Z]"),  # ILogger, IService
        re.compile(r"Interface$"),  # LoggerInterface
        re.compile(r"^Abstract"),  # AbstractFactory
        re.compile(r"Base$"),  # ServiceBase
    ]

    # Setter method patterns
    SETTER_PATTERNS = [
        re.compile(r"^set[A-Z]"),  # setLogger, setNext
        re.compile(r"^Set[A-Z]"),  # SetLogger
        re.compile(r"^register"),  # registerCallback
        re.compile(r"^Register"),  # RegisterHandler
        re.compile(r"^add[A-Z]"),  # addObserver
        re.compile(r"^Add[A-Z]"),  # AddListener
    ]

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
        helper = CppQueryHelper(source)

        for class_node in helper.find_class_declarations(ast):
            # Analyze constructors
            for ctor in helper.find_constructors(class_node):
                findings.extend(self._analyze_constructor(ctor, helper))

            # Analyze setter methods
            for method in helper.find_methods(class_node):
                if self._is_setter_method(method.name):
                    findings.extend(self._analyze_setter(method))

        return findings

    def _analyze_constructor(self, ctor, helper: CppQueryHelper) -> List[L4Finding]:
        """Analyze constructor parameters for dependencies."""
        findings = []

        for param in ctor.parameters:
            finding = self._analyze_parameter(param, "constructor", ctor.line)
            if finding:
                findings.append(finding)

        return findings

    def _analyze_setter(self, method) -> List[L4Finding]:
        """Analyze setter method parameters for optional dependencies."""
        findings = []

        for param in method.parameters:
            finding = self._analyze_parameter(
                param, f"setter ({method.name})", method.line, is_optional=True
            )
            if finding:
                findings.append(finding)

        return findings

    def _analyze_parameter(
        self,
        param: ParameterInfo,
        source: str,
        line: int,
        is_optional: bool = False,
    ) -> L4Finding | None:
        """Analyze a parameter for dependency semantics."""
        # Skip primitive types
        if self._is_primitive_type(param.type_name):
            return None

        # Interface pointer = strong dependency signal
        if param.is_pointer and self._is_interface_type(param.type_name):
            return L4Finding(
                type=L4FindingType.DEPENDENCY,
                confidence=L4Confidence.HIGH,
                value=f"{'optional' if is_optional else 'requires'} {param.type_name}",
                evidence=f"{source}({param.type_name}* {param.name})",
                line=line,
                member=param.name,
            )

        # Interface reference = strong dependency signal
        if param.is_reference and self._is_interface_type(param.type_name):
            return L4Finding(
                type=L4FindingType.DEPENDENCY,
                confidence=L4Confidence.HIGH,
                value=f"{'optional' if is_optional else 'requires'} {param.type_name}",
                evidence=f"{source}({param.type_name}& {param.name})",
                line=line,
                member=param.name,
            )

        # Non-primitive pointer = medium confidence dependency
        if param.is_pointer:
            return L4Finding(
                type=L4FindingType.DEPENDENCY,
                confidence=L4Confidence.MEDIUM,
                value=f"{'optional' if is_optional else 'uses'} {param.type_name}",
                evidence=f"{source}({param.type_name}* {param.name})",
                line=line,
                member=param.name,
            )

        # Const reference = likely input data, not dependency
        if param.is_reference and param.is_const:
            # Could be configuration or data, low confidence as dependency
            return L4Finding(
                type=L4FindingType.DEPENDENCY,
                confidence=L4Confidence.LOW,
                value=f"configured with {param.type_name}",
                evidence=f"{source}(const {param.type_name}& {param.name})",
                line=line,
                member=param.name,
            )

        # Value parameter of complex type = configuration
        if not self._is_primitive_type(param.type_name) and not param.is_pointer:
            return L4Finding(
                type=L4FindingType.DEPENDENCY,
                confidence=L4Confidence.LOW,
                value=f"configured with {param.type_name}",
                evidence=f"{source}({param.type_name} {param.name})",
                line=line,
                member=param.name,
            )

        return None

    def _is_setter_method(self, name: str) -> bool:
        """Check if method name matches setter pattern."""
        for pattern in self.SETTER_PATTERNS:
            if pattern.match(name):
                return True
        return False

    def _is_interface_type(self, type_name: str) -> bool:
        """Check if type name suggests an interface."""
        # Remove std:: prefix if present
        clean_name = type_name.replace("std::", "").strip()

        for pattern in self.INTERFACE_PATTERNS:
            if pattern.search(clean_name):
                return True
        return False

    def _is_primitive_type(self, type_name: str) -> bool:
        """Check if type is a primitive."""
        primitives = {
            "int",
            "char",
            "bool",
            "float",
            "double",
            "void",
            "short",
            "long",
            "unsigned",
            "signed",
            "size_t",
            "uint8_t",
            "uint16_t",
            "uint32_t",
            "uint64_t",
            "int8_t",
            "int16_t",
            "int32_t",
            "int64_t",
            "string",
            "string_view",
        }
        clean = type_name.lower().replace("std::", "")
        return clean in primitives
