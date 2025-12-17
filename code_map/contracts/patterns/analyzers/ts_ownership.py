# SPDX-License-Identifier: MIT
"""
Ownership Analyzer for TypeScript/JavaScript L4 static analysis.

Detects ownership relations from:
- private readonly fields -> owns
- private fields -> owns/manages
- Constructor parameter properties
- Dependency injection patterns
"""

from typing import List

from tree_sitter import Node

from ..models import L4Confidence, L4Finding, L4FindingType
from ..queries.typescript import TypeScriptQueryHelper


class TypeScriptOwnershipAnalyzer:
    """Analyzes ownership relations in TypeScript/JavaScript classes."""

    name = "ts_ownership"

    # Types that indicate exclusive ownership when declared as fields
    OWNED_TYPES = {
        "Worker": L4Confidence.HIGH,
        "SharedWorker": L4Confidence.HIGH,
        "WebSocket": L4Confidence.HIGH,
        "EventEmitter": L4Confidence.MEDIUM,
        "Subject": L4Confidence.MEDIUM,  # RxJS
        "BehaviorSubject": L4Confidence.MEDIUM,
        "ReplaySubject": L4Confidence.MEDIUM,
        "Map": L4Confidence.LOW,
        "Set": L4Confidence.LOW,
        "Array": L4Confidence.LOW,
    }

    # Observable/Stream types (shared references typically)
    SHARED_TYPES = {
        "Observable": L4Confidence.MEDIUM,
        "Promise": L4Confidence.LOW,
        "Stream": L4Confidence.MEDIUM,
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
        helper = TypeScriptQueryHelper(source)

        for class_node in helper.find_class_declarations(ast):
            class_name = helper.get_class_name(class_node)

            # Analyze declared fields
            for field in helper.find_field_definitions(class_node):
                finding = self._analyze_field(field, class_name)
                if finding:
                    findings.append(finding)

            # Analyze constructor parameter properties
            for constructor in helper.find_constructors(class_node):
                findings.extend(
                    self._analyze_constructor_params(constructor, class_name)
                )

        return findings

    def _analyze_field(self, field, class_name: str | None) -> L4Finding | None:
        """Analyze a single field for ownership semantics."""
        # private readonly = strong ownership signal
        if field.is_private and field.is_readonly:
            type_name = field.type_name or "unknown"
            return L4Finding(
                type=L4FindingType.OWNERSHIP,
                confidence=L4Confidence.HIGH,
                value=f"owns {type_name}",
                evidence=f"private readonly {field.name}: {type_name}",
                line=field.line,
                member=field.name,
            )

        # private (not readonly) = manages/owns
        if field.is_private:
            type_name = field.type_name or "unknown"

            # Check for known owned types
            if type_name in self.OWNED_TYPES:
                confidence = self.OWNED_TYPES[type_name]
                return L4Finding(
                    type=L4FindingType.OWNERSHIP,
                    confidence=confidence,
                    value=f"owns {type_name}",
                    evidence=f"private {field.name}: {type_name}",
                    line=field.line,
                    member=field.name,
                )

            # Check for shared types
            if type_name in self.SHARED_TYPES:
                confidence = self.SHARED_TYPES[type_name]
                return L4Finding(
                    type=L4FindingType.OWNERSHIP,
                    confidence=confidence,
                    value=f"observes {type_name}",
                    evidence=f"private {field.name}: {type_name}",
                    line=field.line,
                    member=field.name,
                )

            return L4Finding(
                type=L4FindingType.OWNERSHIP,
                confidence=L4Confidence.MEDIUM,
                value=f"manages {type_name}",
                evidence=f"private {field.name}: {type_name}",
                line=field.line,
                member=field.name,
            )

        # readonly (public) = shares
        if field.is_readonly:
            type_name = field.type_name or "unknown"
            return L4Finding(
                type=L4FindingType.OWNERSHIP,
                confidence=L4Confidence.LOW,
                value=f"exposes {type_name}",
                evidence=f"readonly {field.name}: {type_name}",
                line=field.line,
                member=field.name,
            )

        return None

    def _analyze_constructor_params(
        self, constructor, class_name: str | None
    ) -> List[L4Finding]:
        """Analyze constructor parameter properties for ownership."""
        findings = []

        for param in constructor.parameters:
            # Parameter properties (private/public in constructor)
            if param.accessibility:
                type_name = param.type_name or "unknown"

                if param.accessibility == "private" and param.is_readonly:
                    findings.append(
                        L4Finding(
                            type=L4FindingType.OWNERSHIP,
                            confidence=L4Confidence.HIGH,
                            value=f"owns {type_name}",
                            evidence=f"constructor(private readonly {param.name}: {type_name})",
                            line=constructor.line,
                            member=param.name,
                        )
                    )
                elif param.accessibility == "private":
                    findings.append(
                        L4Finding(
                            type=L4FindingType.OWNERSHIP,
                            confidence=L4Confidence.MEDIUM,
                            value=f"manages {type_name}",
                            evidence=f"constructor(private {param.name}: {type_name})",
                            line=constructor.line,
                            member=param.name,
                        )
                    )

        return findings
