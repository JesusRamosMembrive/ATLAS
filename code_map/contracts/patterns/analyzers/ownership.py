# SPDX-License-Identifier: MIT
"""
Ownership Analyzer for L4 static analysis.

Detects ownership relations from smart pointers and raw pointers:
- unique_ptr<T> -> owns (exclusive)
- shared_ptr<T> -> shares
- weak_ptr<T> -> observes
- T* -> uses (no ownership)
- T& -> borrows
"""

from typing import List

from tree_sitter import Node

from ..models import L4Confidence, L4Finding, L4FindingType
from ..queries.cpp import CppQueryHelper


class OwnershipAnalyzer:
    """Analyzes ownership relations from pointer types."""

    name = "ownership"

    # Smart pointer types and their ownership semantics
    OWNERSHIP_PATTERNS = {
        "unique_ptr": ("owns", L4Confidence.HIGH),
        "shared_ptr": ("shares", L4Confidence.HIGH),
        "weak_ptr": ("observes", L4Confidence.HIGH),
    }

    # Value types that indicate ownership
    VALUE_OWNERSHIP_TYPES = {
        "thread": ("owns", L4Confidence.HIGH),
        "mutex": ("owns", L4Confidence.HIGH),
        "condition_variable": ("owns", L4Confidence.HIGH),
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
        helper = CppQueryHelper(source)

        for class_node in helper.find_class_declarations(ast):
            class_name = helper.get_class_name(class_node)

            for field in helper.find_field_declarations(class_node):
                finding = self._analyze_field(field, class_name)
                if finding:
                    findings.append(finding)

        return findings

    def _analyze_field(self, field, class_name: str | None) -> L4Finding | None:
        """Analyze a single field for ownership semantics."""
        # Check for smart pointer templates
        if field.template_name:
            template_lower = field.template_name.lower()

            # Check smart pointers
            if template_lower in self.OWNERSHIP_PATTERNS:
                relation, confidence = self.OWNERSHIP_PATTERNS[template_lower]
                inner_type = field.template_args[0] if field.template_args else "?"

                return L4Finding(
                    type=L4FindingType.OWNERSHIP,
                    confidence=confidence,
                    value=f"{relation} {inner_type}",
                    evidence=f"{field.template_name}<{inner_type}>",
                    line=field.line,
                    member=field.name,
                )

            # Check std:: prefixed versions
            for pattern, (relation, confidence) in self.OWNERSHIP_PATTERNS.items():
                if pattern in template_lower:
                    inner_type = field.template_args[0] if field.template_args else "?"
                    return L4Finding(
                        type=L4FindingType.OWNERSHIP,
                        confidence=confidence,
                        value=f"{relation} {inner_type}",
                        evidence=f"std::{pattern}<{inner_type}>",
                        line=field.line,
                        member=field.name,
                    )

        # Check for value types that indicate ownership (std::thread, etc.)
        type_name = field.type_name.lower()
        for value_type, (relation, confidence) in self.VALUE_OWNERSHIP_TYPES.items():
            if value_type in type_name:
                return L4Finding(
                    type=L4FindingType.OWNERSHIP,
                    confidence=confidence,
                    value=f"{relation} {field.type_name}",
                    evidence=f"{field.type_name} {field.name}",
                    line=field.line,
                    member=field.name,
                )

        # Raw pointer = uses (no ownership transfer)
        if field.is_pointer:
            return L4Finding(
                type=L4FindingType.OWNERSHIP,
                confidence=L4Confidence.MEDIUM,
                value=f"uses {field.type_name}",
                evidence=f"{field.type_name}* {field.name}",
                line=field.line,
                member=field.name,
            )

        # Reference member = borrows (rare in class members)
        if field.is_reference:
            return L4Finding(
                type=L4FindingType.OWNERSHIP,
                confidence=L4Confidence.MEDIUM,
                value=f"borrows {field.type_name}",
                evidence=f"{field.type_name}& {field.name}",
                line=field.line,
                member=field.name,
            )

        # Value member of complex type = owns
        # Skip primitive types and common containers
        if not self._is_primitive_type(field.type_name):
            return L4Finding(
                type=L4FindingType.OWNERSHIP,
                confidence=L4Confidence.LOW,
                value=f"owns {field.type_name}",
                evidence=f"{field.type_name} {field.name} (value member)",
                line=field.line,
                member=field.name,
            )

        return None

    def _is_primitive_type(self, type_name: str) -> bool:
        """Check if type is a primitive (don't report ownership)."""
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
        }
        return type_name.lower() in primitives
