# SPDX-License-Identifier: MIT
"""
MetricsMixin: Cyclomatic complexity and LOC calculation.

Provides code metrics calculation for call flow nodes.
Works with any language by accepting decision types as parameter.
"""

from __future__ import annotations

from typing import Any, Set


class MetricsMixin:
    """
    Mixin providing code metrics calculation.

    Calculates:
    - Cyclomatic complexity (McCabe)
    - Lines of code (LOC)

    Requires TreeSitterMixin for _walk_tree method.

    Usage:
        class MyExtractor(TreeSitterMixin, MetricsMixin):
            @property
            def decision_types(self) -> Set[str]:
                return {"if_statement", "for_statement", ...}
    """

    # Subclasses should provide language-specific decision types
    # via a property or class variable
    def _get_decision_types(self) -> Set[str]:
        """
        Get decision point node types for complexity calculation.

        Override this or provide a 'decision_types' property.
        Default returns empty set.
        """
        if hasattr(self, "decision_types"):
            return self.decision_types
        return set()

    def _get_boolean_operators(self) -> Set[str]:
        """
        Get boolean operator strings that add complexity.

        Override for language-specific operators.
        Default returns Python/JS-style operators.
        """
        return {"and", "or", "&&", "||"}

    def _calculate_loc(self, func_node: Any) -> int:
        """
        Calculate lines of code for a function node.

        Args:
            func_node: Tree-sitter node for the function.

        Returns:
            Number of lines (end_line - start_line + 1).
        """
        start_line = func_node.start_point[0]
        end_line = func_node.end_point[0]
        return end_line - start_line + 1

    def _calculate_complexity(
        self,
        func_node: Any,
        decision_types: Set[str] = None,
    ) -> int:
        """
        Calculate cyclomatic complexity (McCabe) for a function node.

        Counts decision points: if, for, while, except, with, match/case,
        comprehensions, boolean operators (and, or, &&, ||).

        Args:
            func_node: Tree-sitter node for the function.
            decision_types: Set of node types that count as decision points.
                           If None, uses _get_decision_types().

        Returns:
            Cyclomatic complexity (1 + number of decision points).
        """
        if decision_types is None:
            decision_types = self._get_decision_types()

        boolean_ops = self._get_boolean_operators()
        count = 0
        to_visit = [func_node]

        while to_visit:
            node = to_visit.pop()

            # Check for decision point node types
            if node.type in decision_types:
                count += 1
            # Handle boolean operators (language-specific)
            elif node.type in ("boolean_operator", "binary_expression"):
                # Check children for and/or/&&/||
                for child in node.children:
                    if child.type in boolean_ops:
                        count += 1
                        break
                    # Also check node text for inline operators
                    if hasattr(self, "_get_node_text"):
                        try:
                            # This requires source, but we can check type
                            pass
                        except Exception:
                            pass

            to_visit.extend(node.children)

        return 1 + count
