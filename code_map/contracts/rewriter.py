# SPDX-License-Identifier: MIT
"""
Contract rewriter for inserting/updating @aegis-contract blocks.

Generates minimal diffs by only modifying contract blocks.
"""

import difflib
import logging
from pathlib import Path
from typing import Optional

from .discovery import ContractDiscovery
from .languages.registry import LanguageRegistry
from .schema import ContractData

logger = logging.getLogger(__name__)


class ContractRewriter:
    """
    Rewrites source files to insert or update contract blocks.

    Principles:
    1. Only touch content between @aegis-contract markers
    2. Preserve indentation and formatting of surrounding code
    3. Generate minimal, predictable diffs
    """

    def __init__(self):
        """Initialize the rewriter."""
        self._discovery = ContractDiscovery(enable_llm=False)

    def write_contract(
        self,
        file_path: Path,
        symbol_line: int,
        contract: ContractData,
    ) -> tuple[str, str]:
        """
        Write a contract to a source file.

        If a contract block exists, it will be updated.
        Otherwise, a new block will be inserted.

        Args:
            file_path: Path to the source file
            symbol_line: Line of the symbol (1-indexed)
            contract: Contract data to write

        Returns:
            Tuple of (modified_source, unified_diff)

        Raises:
            ValueError: If language not supported
            FileNotFoundError: If file doesn't exist
        """
        # Get strategy for the language
        strategy = LanguageRegistry.get_for_file(file_path)
        if not strategy:
            raise ValueError(f"Unsupported language: {file_path.suffix}")

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        original_source = file_path.read_text(encoding="utf-8")

        # Check for existing contract block
        existing_block = strategy.find_contract_block(original_source, symbol_line)

        if existing_block:
            # Update existing block
            modified_source = strategy.update_contract_block(
                original_source, existing_block, contract
            )
            logger.info(f"Updated existing contract at {file_path}:{existing_block.start_line}")
        else:
            # Insert new block
            modified_source = strategy.insert_contract_block(
                original_source, symbol_line, contract
            )
            logger.info(f"Inserted new contract at {file_path}:{symbol_line}")

        # Generate diff
        diff = self._generate_diff(
            original_source, modified_source, str(file_path)
        )

        return modified_source, diff

    def apply_contract(
        self,
        file_path: Path,
        symbol_line: int,
        contract: ContractData,
    ) -> str:
        """
        Write contract and save to file.

        Args:
            file_path: Path to the source file
            symbol_line: Line of the symbol
            contract: Contract data to write

        Returns:
            Unified diff of changes
        """
        modified_source, diff = self.write_contract(file_path, symbol_line, contract)

        # Write to file
        file_path.write_text(modified_source, encoding="utf-8")
        logger.info(f"Applied contract changes to {file_path}")

        return diff

    def preview_contract(
        self,
        file_path: Path,
        symbol_line: int,
        contract: ContractData,
    ) -> str:
        """
        Preview changes without writing to file.

        Args:
            file_path: Path to the source file
            symbol_line: Line of the symbol
            contract: Contract data to write

        Returns:
            Unified diff showing proposed changes
        """
        _, diff = self.write_contract(file_path, symbol_line, contract)
        return diff

    def remove_contract(
        self,
        file_path: Path,
        symbol_line: int,
    ) -> Optional[str]:
        """
        Remove contract block from a symbol.

        Args:
            file_path: Path to the source file
            symbol_line: Line of the symbol

        Returns:
            Unified diff if contract was removed, None if no contract existed
        """
        strategy = LanguageRegistry.get_for_file(file_path)
        if not strategy:
            raise ValueError(f"Unsupported language: {file_path.suffix}")

        original_source = file_path.read_text(encoding="utf-8")

        # Find existing block
        existing_block = strategy.find_contract_block(original_source, symbol_line)
        if not existing_block:
            return None

        # Remove the block
        lines = original_source.splitlines()
        start_idx = existing_block.start_line - 1
        end_idx = existing_block.end_line

        modified_lines = lines[:start_idx] + lines[end_idx:]
        modified_source = "\n".join(modified_lines)

        # Generate diff
        diff = self._generate_diff(original_source, modified_source, str(file_path))

        # Write to file
        file_path.write_text(modified_source, encoding="utf-8")
        logger.info(f"Removed contract from {file_path}:{symbol_line}")

        return diff

    def _generate_diff(
        self, original: str, modified: str, filename: str
    ) -> str:
        """Generate unified diff between two versions."""
        original_lines = original.splitlines(keepends=True)
        modified_lines = modified.splitlines(keepends=True)

        diff = difflib.unified_diff(
            original_lines,
            modified_lines,
            fromfile=f"a/{filename}",
            tofile=f"b/{filename}",
            lineterm="",
        )

        return "".join(diff)

    def validate_contract(
        self,
        file_path: Path,
        symbol_line: int,
    ) -> tuple[bool, str]:
        """
        Validate that a contract can be written to a location.

        Args:
            file_path: Path to the source file
            symbol_line: Line of the symbol

        Returns:
            Tuple of (is_valid, message)
        """
        # Check language support
        strategy = LanguageRegistry.get_for_file(file_path)
        if not strategy:
            return False, f"Unsupported language: {file_path.suffix}"

        # Check file exists
        if not file_path.exists():
            return False, f"File not found: {file_path}"

        # Check symbol line is valid
        source = file_path.read_text(encoding="utf-8")
        lines = source.splitlines()
        if symbol_line < 1 or symbol_line > len(lines):
            return False, f"Invalid line number: {symbol_line} (file has {len(lines)} lines)"

        # Check we can find or create a contract location
        existing_block = strategy.find_contract_block(source, symbol_line)
        if existing_block:
            return True, "Existing contract block found, will be updated"

        return True, "New contract block will be inserted"
