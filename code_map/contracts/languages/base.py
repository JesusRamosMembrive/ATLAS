# SPDX-License-Identifier: MIT
"""
Base class for language-specific contract strategies.

Defines the interface that each language implementation must follow.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Tuple

from ..schema import ContractData


@dataclass
class ContractBlock:
    """A contract block found in source code."""

    start_line: int  # 1-indexed
    end_line: int  # 1-indexed
    content: str  # YAML content inside the markers
    raw_text: str  # Original text including delimiters


@dataclass
class CommentBlock:
    """A comment or docstring block associated with a symbol."""

    start_line: int  # 1-indexed
    end_line: int  # 1-indexed
    content: str  # Cleaned content
    style: str  # 'line', 'block', 'docstring'


class LanguageStrategy(ABC):
    """
    Strategy base for contract parsing/rewriting by language.

    Each concrete implementation handles:
    - Language-specific comment syntax
    - Known documentation patterns (Doxygen, Google style, etc.)
    - Canonical location for inserting contracts
    - Output format when rewriting
    """

    # ─────────────────────────────────────────────────────────────
    # Abstract properties
    # ─────────────────────────────────────────────────────────────

    @property
    @abstractmethod
    def language_id(self) -> str:
        """
        Unique identifier for this language.

        Examples: 'cpp', 'python', 'typescript', 'java'
        """
        pass

    @property
    @abstractmethod
    def file_extensions(self) -> Tuple[str, ...]:
        """
        File extensions supported by this strategy.

        Examples: ('.cpp', '.hpp', '.h') for C++
        """
        pass

    @property
    @abstractmethod
    def comment_styles(self) -> dict:
        """
        Comment styles supported by this language.

        Example for C++:
        {
            'line': '//',
            'block_start': '/*',
            'block_end': '*/',
            'doc_start': '/**',
        }
        """
        pass

    # ─────────────────────────────────────────────────────────────
    # Abstract methods: Parsing
    # ─────────────────────────────────────────────────────────────

    @abstractmethod
    def find_contract_block(
        self, source: str, symbol_line: int
    ) -> Optional[ContractBlock]:
        """
        Level 1: Find @aegis-contract block near the symbol.

        Args:
            source: Complete source code of the file
            symbol_line: Line where the symbol is defined (1-indexed)

        Returns:
            ContractBlock if found, None otherwise
        """
        pass

    @abstractmethod
    def find_comment_block(
        self, source: str, symbol_line: int
    ) -> Optional[CommentBlock]:
        """
        Find comment/docstring block associated with a symbol.

        Args:
            source: Complete source code
            symbol_line: Symbol line number

        Returns:
            CommentBlock with the comment found, None if none
        """
        pass

    @abstractmethod
    def parse_known_patterns(self, comment: CommentBlock) -> ContractData:
        """
        Level 2: Extract contract from known language patterns.

        Patterns by language:
        - C++: Doxygen (@pre, @post, @invariant, @throws)
        - Python: Google style, NumPy style, Sphinx
        - TypeScript: JSDoc (@throws, @returns)

        Args:
            comment: Comment block to analyze

        Returns:
            ContractData with extracted fields (may be partially empty)
        """
        pass

    # ─────────────────────────────────────────────────────────────
    # Abstract methods: Rewriting
    # ─────────────────────────────────────────────────────────────

    @abstractmethod
    def insert_contract_block(
        self, source: str, symbol_line: int, contract: ContractData
    ) -> str:
        """
        Insert new @aegis-contract block at canonical location.

        Canonical location by language:
        - C++: Comment immediately before the declaration
        - Python: Start of docstring (before existing text)

        Args:
            source: Original source code
            symbol_line: Target symbol line
            contract: Contract data to insert

        Returns:
            Modified source code with block inserted
        """
        pass

    @abstractmethod
    def update_contract_block(
        self, source: str, block: ContractBlock, contract: ContractData
    ) -> str:
        """
        Update existing @aegis-contract block.

        IMPORTANT: Only modify content between delimiters,
        preserving indentation and format of the rest of file.

        Args:
            source: Original source code
            block: Existing block to replace
            contract: New contract data

        Returns:
            Source code with updated block
        """
        pass

    # ─────────────────────────────────────────────────────────────
    # Concrete methods (shared)
    # ─────────────────────────────────────────────────────────────

    def format_contract_yaml(self, contract: ContractData, indent: str = "") -> str:
        """
        Format ContractData as YAML for embedding in comment.

        Args:
            contract: Data to format
            indent: Indentation prefix for each line

        Returns:
            Formatted YAML string
        """
        lines = []

        if contract.thread_safety:
            lines.append(f"thread_safety: {contract.thread_safety.value}")

        if contract.lifecycle:
            lines.append(f"lifecycle: {contract.lifecycle}")

        if contract.invariants:
            lines.append("invariants:")
            for inv in contract.invariants:
                lines.append(f"  - {inv}")

        if contract.preconditions:
            lines.append("preconditions:")
            for pre in contract.preconditions:
                lines.append(f"  - {pre}")

        if contract.postconditions:
            lines.append("postconditions:")
            for post in contract.postconditions:
                lines.append(f"  - {post}")

        if contract.errors:
            lines.append("errors:")
            for err in contract.errors:
                lines.append(f"  - {err}")

        if contract.dependencies:
            lines.append("dependencies:")
            for dep in contract.dependencies:
                lines.append(f"  - {dep}")

        if contract.evidence:
            lines.append("evidence:")
            for ev in contract.evidence:
                lines.append(f"  - {ev.type}: {ev.reference}")
                if ev.policy.value != "optional":
                    lines.append(f"    policy: {ev.policy.value}")

        return "\n".join(f"{indent}{line}" for line in lines)

    def detect_indentation(self, source: str, line_number: int) -> str:
        """
        Detect indentation used at a specific line.

        Args:
            source: Source code
            line_number: Line number (1-indexed)

        Returns:
            Indentation string (spaces/tabs)
        """
        lines = source.splitlines()
        if 0 < line_number <= len(lines):
            line = lines[line_number - 1]
            return line[: len(line) - len(line.lstrip())]
        return ""
