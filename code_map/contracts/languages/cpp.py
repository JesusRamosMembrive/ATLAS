# SPDX-License-Identifier: MIT
"""
C/C++ language strategy for contract parsing and rewriting.

Supports:
- @aegis-contract blocks in line comments
- Doxygen documentation patterns (@pre, @post, @throws, etc.)
"""

import logging
import re
from typing import List, Optional, Tuple

from ..schema import ContractData, ThreadSafety
from .base import CommentBlock, ContractBlock, LanguageStrategy
from .registry import LanguageRegistry

logger = logging.getLogger(__name__)


@LanguageRegistry.register
class CppLanguageStrategy(LanguageStrategy):
    """Strategy for C/C++ files."""

    # ─────────────────────────────────────────────────────────────
    # Properties
    # ─────────────────────────────────────────────────────────────

    @property
    def language_id(self) -> str:
        return "cpp"

    @property
    def file_extensions(self) -> Tuple[str, ...]:
        return (".cpp", ".hpp", ".h", ".cc", ".cxx", ".hxx", ".c")

    @property
    def comment_styles(self) -> dict:
        return {
            "line": "//",
            "block_start": "/*",
            "block_end": "*/",
            "doc_start": "/**",
        }

    # ─────────────────────────────────────────────────────────────
    # Doxygen patterns
    # ─────────────────────────────────────────────────────────────

    DOXYGEN_PATTERNS = {
        "preconditions": re.compile(
            r"@pre\s+(.+?)(?=\n\s*[@*]|\*/|\Z)", re.DOTALL
        ),
        "postconditions": re.compile(
            r"@post\s+(.+?)(?=\n\s*[@*]|\*/|\Z)", re.DOTALL
        ),
        "invariants": re.compile(
            r"@invariant\s+(.+?)(?=\n\s*[@*]|\*/|\Z)", re.DOTALL
        ),
        "errors": re.compile(
            r"@throws?\s+(\S+)\s+(.+?)(?=\n\s*[@*]|\*/|\Z)", re.DOTALL
        ),
    }

    THREAD_SAFETY_PATTERNS = [
        (re.compile(r"not\s+thread[_-]?safe", re.I), ThreadSafety.NOT_SAFE),
        (re.compile(r"safe\s+after\s+start", re.I), ThreadSafety.SAFE_AFTER_START),
        (re.compile(r"thread[_-]?safe", re.I), ThreadSafety.SAFE),
        (re.compile(r"immutable", re.I), ThreadSafety.IMMUTABLE),
    ]

    # ─────────────────────────────────────────────────────────────
    # Parsing: Level 1 - AEGIS contract blocks
    # ─────────────────────────────────────────────────────────────

    def find_contract_block(
        self, source: str, symbol_line: int
    ) -> Optional[ContractBlock]:
        """Find @aegis-contract-begin/end before the symbol."""
        lines = source.splitlines()

        start_marker = "@aegis-contract-begin"
        end_marker = "@aegis-contract-end"

        start_idx = None
        end_idx = None

        # Search in the 30 lines before the symbol
        # Note: symbol_line is 1-based, lines[] is 0-based
        # Start from line BEFORE the symbol (symbol_line - 2 in 0-based)
        search_start = max(0, symbol_line - 31)
        logger.info("[DEBUG] find_contract_block: symbol_line=%d, search_range=[%d..%d]",
                    symbol_line, search_start, symbol_line - 2)
        for i in range(symbol_line - 2, search_start - 1, -1):
            if i >= len(lines):
                continue
            line = lines[i]
            if end_marker in line and end_idx is None:
                end_idx = i
                logger.info("[DEBUG] Found end_marker at line %d (0-indexed)", i)
            if start_marker in line:
                start_idx = i
                logger.info("[DEBUG] Found start_marker at line %d (0-indexed)", i)
                break

        logger.info("[DEBUG] Result: start_idx=%s, end_idx=%s", start_idx, end_idx)
        if start_idx is not None and end_idx is not None and start_idx < end_idx:
            # Extract content between markers
            content_lines = []
            for i in range(start_idx + 1, end_idx):
                line = lines[i]
                # Clean comment prefix
                cleaned = line.strip()
                if cleaned.startswith("//"):
                    cleaned = cleaned[2:].strip()
                elif cleaned.startswith("*"):
                    cleaned = cleaned[1:].strip()
                content_lines.append(cleaned)

            return ContractBlock(
                start_line=start_idx + 1,
                end_line=end_idx + 1,
                content="\n".join(content_lines),
                raw_text="\n".join(lines[start_idx : end_idx + 1]),
            )

        return None

    # ─────────────────────────────────────────────────────────────
    # Parsing: Level 2 - Doxygen patterns
    # ─────────────────────────────────────────────────────────────

    def find_comment_block(
        self, source: str, symbol_line: int
    ) -> Optional[CommentBlock]:
        """Find Doxygen/normal comment before the symbol."""
        lines = source.splitlines()

        # Search upward from symbol_line - 1
        end_idx = symbol_line - 2  # 0-indexed, previous line
        if end_idx < 0:
            return None

        comment_lines: List[str] = []
        style = None
        start_idx = end_idx

        # Skip empty lines
        while end_idx >= 0 and not lines[end_idx].strip():
            end_idx -= 1

        if end_idx < 0:
            return None

        # Case 1: Block comment /** ... */ or /* ... */
        if lines[end_idx].strip().endswith("*/"):
            style = "block"
            # Find start of block
            for i in range(end_idx, -1, -1):
                line = lines[i]
                comment_lines.insert(0, line)
                if "/**" in line or "/*" in line:
                    start_idx = i
                    break
            end_idx = symbol_line - 2

        # Case 2: Line comments // ...
        elif lines[end_idx].strip().startswith("//"):
            style = "line"
            for i in range(end_idx, -1, -1):
                line = lines[i].strip()
                if line.startswith("//"):
                    comment_lines.insert(0, lines[i])
                    start_idx = i
                elif not line:
                    # Skip empty lines in block of comments
                    continue
                else:
                    break

        if not comment_lines:
            return None

        # Clean content
        content = self._clean_comment_content(comment_lines, style or "line")

        return CommentBlock(
            start_line=start_idx + 1,
            end_line=end_idx + 1,
            content=content,
            style=style or "line",
        )

    def _clean_comment_content(self, lines: List[str], style: str) -> str:
        """Clean comment content removing prefixes."""
        cleaned = []
        for line in lines:
            text = line.strip()
            if style == "line":
                if text.startswith("//"):
                    text = text[2:].strip()
            elif style == "block":
                text = text.lstrip("/*").rstrip("*/").strip()
                if text.startswith("*"):
                    text = text[1:].strip()
            cleaned.append(text)
        return "\n".join(cleaned)

    def parse_known_patterns(self, comment: CommentBlock) -> ContractData:
        """Extract contract from Doxygen patterns."""
        content = comment.content
        contract = ContractData(confidence=0.8, source_level=2)

        # Preconditions
        for match in self.DOXYGEN_PATTERNS["preconditions"].finditer(content):
            text = match.group(1).strip()
            # Clean up multiline
            text = " ".join(text.split())
            if text:
                contract.preconditions.append(text)

        # Postconditions
        for match in self.DOXYGEN_PATTERNS["postconditions"].finditer(content):
            text = match.group(1).strip()
            text = " ".join(text.split())
            if text:
                contract.postconditions.append(text)

        # Invariants
        for match in self.DOXYGEN_PATTERNS["invariants"].finditer(content):
            text = match.group(1).strip()
            text = " ".join(text.split())
            if text:
                contract.invariants.append(text)

        # Errors/exceptions
        for match in self.DOXYGEN_PATTERNS["errors"].finditer(content):
            exception_type = match.group(1)
            description = match.group(2).strip()
            description = " ".join(description.split())
            contract.errors.append(f"{exception_type}: {description}")

        # Thread safety (search in entire comment)
        for pattern, safety in self.THREAD_SAFETY_PATTERNS:
            if pattern.search(content):
                contract.thread_safety = safety
                break

        return contract

    # ─────────────────────────────────────────────────────────────
    # Rewriting
    # ─────────────────────────────────────────────────────────────

    def insert_contract_block(
        self, source: str, symbol_line: int, contract: ContractData
    ) -> str:
        """Insert @aegis-contract block before the symbol."""
        lines = source.splitlines()
        indent = self.detect_indentation(source, symbol_line)

        # Generate contract block
        block_lines = [
            f"{indent}// @aegis-contract-begin",
        ]

        yaml_content = self.format_contract_yaml(contract, indent=f"{indent}// ")
        block_lines.extend(yaml_content.splitlines())

        block_lines.append(f"{indent}// @aegis-contract-end")

        # Insert before the symbol
        insert_idx = symbol_line - 1  # 0-indexed

        # Check if there's an existing comment to insert after
        if insert_idx > 0:
            prev_line = lines[insert_idx - 1].strip()
            if prev_line.endswith("*/"):
                # There's a block comment, insert between it and symbol
                pass

        new_lines = lines[:insert_idx] + block_lines + lines[insert_idx:]
        return "\n".join(new_lines)

    def update_contract_block(
        self, source: str, block: ContractBlock, contract: ContractData
    ) -> str:
        """Update existing block preserving format."""
        lines = source.splitlines()

        # Detect indentation from existing block
        first_line = lines[block.start_line - 1]
        indent = first_line[: len(first_line) - len(first_line.lstrip())]

        # Generate new content
        new_block_lines = [
            f"{indent}// @aegis-contract-begin",
        ]

        yaml_content = self.format_contract_yaml(contract, indent=f"{indent}// ")
        new_block_lines.extend(yaml_content.splitlines())

        new_block_lines.append(f"{indent}// @aegis-contract-end")

        # Replace block lines
        start_idx = block.start_line - 1
        end_idx = block.end_line  # Exclusive

        new_lines = lines[:start_idx] + new_block_lines + lines[end_idx:]
        return "\n".join(new_lines)
