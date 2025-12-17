# SPDX-License-Identifier: MIT
"""
SymbolMixin: Symbol ID generation for stable node identification.

Provides consistent symbol ID generation across all extractors.
Symbol IDs are used to uniquely identify functions/methods across files.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional


class SymbolMixin:
    """
    Mixin providing symbol ID generation.

    Symbol IDs follow the format: {relative_path}:{line}:{col}:{kind}:{name}

    This format ensures:
    - Stable IDs across runs (based on source location)
    - Uniqueness within a project
    - Human readability for debugging

    Usage:
        class MyExtractor(SymbolMixin):
            def some_method(self):
                symbol_id = self._make_symbol_id(
                    file_path=Path("src/main.py"),
                    line=42,
                    col=0,
                    kind="function",
                    name="process",
                    root=Path("/project"),
                )
                # Returns: "src/main.py:42:0:function:process"
    """

    def _make_symbol_id(
        self,
        file_path: Path,
        line: int,
        col: int,
        kind: str,
        name: str,
        root: Optional[Path] = None,
    ) -> str:
        """
        Generate a stable symbol ID for a function/method.

        Args:
            file_path: Absolute or relative path to source file.
            line: Line number (0-based from tree-sitter).
            col: Column number (0-based from tree-sitter).
            kind: Symbol kind ("function", "method", "class", etc.).
            name: Symbol name.
            root: Project root for relative path calculation.
                  If None, uses file's parent directory.

        Returns:
            Stable symbol ID in format: {rel_path}:{line}:{col}:{kind}:{name}
        """
        if root is None:
            root = file_path.parent

        try:
            rel_path = file_path.relative_to(root)
        except ValueError:
            # File is not under root, use as-is
            rel_path = file_path

        return f"{rel_path.as_posix()}:{line}:{col}:{kind}:{name}"

    def _parse_symbol_id(self, symbol_id: str) -> dict:
        """
        Parse a symbol ID back into its components.

        Args:
            symbol_id: Symbol ID string.

        Returns:
            Dictionary with keys: path, line, col, kind, name.
            Returns empty dict if parsing fails.
        """
        try:
            parts = symbol_id.rsplit(":", 4)
            if len(parts) == 5:
                return {
                    "path": parts[0],
                    "line": int(parts[1]),
                    "col": int(parts[2]),
                    "kind": parts[3],
                    "name": parts[4],
                }
        except (ValueError, IndexError):
            pass
        return {}
