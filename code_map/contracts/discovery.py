# SPDX-License-Identifier: MIT
"""
Contract discovery pipeline.

Orchestrates multi-level contract extraction:
- Level 1: @aegis-contract blocks (100% confidence)
- Level 2: Known patterns like Doxygen (80% confidence)
- Level 3: LLM extraction via Ollama (60% confidence)
- Level 4: Static analysis (40% confidence)
- Level 5: No contract found (0% confidence)
"""

import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import List, Optional

from .languages.registry import LanguageRegistry
from .llm.extractor import LLMContractExtractor
from .patterns.static import StaticAnalyzer
from .schema import ContractData

logger = logging.getLogger(__name__)


class DocumentationType(str, Enum):
    """Type of documentation found near a symbol."""

    AEGIS_CONTRACT = "aegis"  # L1: @aegis-contract-begin/end
    DOXYGEN = "doxygen"  # L2: @pre, @post, @throws, @invariant
    GENERIC_COMMENT = "comment"  # Has comment but no structured contract
    NONE = "none"  # No documentation found


@dataclass
class DiscoveryStats:
    """Statistics from discovery operation."""

    level_1_found: int = 0  # AEGIS blocks
    level_2_found: int = 0  # Known patterns
    level_3_found: int = 0  # LLM extracted
    level_4_found: int = 0  # Static analysis
    level_5_found: int = 0  # No contract
    total_symbols: int = 0


class ContractDiscovery:
    """
    Orchestrator for the contract discovery pipeline.

    Runs through levels 1-5 in order, stopping at the first
    level that produces a non-empty contract.
    """

    def __init__(self, enable_llm: bool = True):
        """
        Initialize the discovery pipeline.

        Args:
            enable_llm: If True and Ollama available, use Level 3
        """
        self._enable_llm = enable_llm
        self._llm_extractor = LLMContractExtractor() if enable_llm else None
        self._static_analyzer = StaticAnalyzer()

    def quick_scan(
        self,
        file_path: Path,
        symbol_line: int,
    ) -> DocumentationType:
        """
        Quick scan to detect what type of documentation exists.

        This is a fast pre-check before running the full discovery pipeline.
        It helps the UI decide whether to show warnings about missing docs.

        Args:
            file_path: File to analyze
            symbol_line: Line of the symbol (1-indexed)

        Returns:
            DocumentationType indicating what was found
        """
        strategy = LanguageRegistry.get_for_file(file_path)
        if not strategy:
            return DocumentationType.NONE

        try:
            source = file_path.read_text(encoding="utf-8")
        except Exception:
            return DocumentationType.NONE

        # Check for @aegis-contract block (Level 1)
        block = strategy.find_contract_block(source, symbol_line)
        if block:
            return DocumentationType.AEGIS_CONTRACT

        # Check for comment block (could be Doxygen or generic)
        comment = strategy.find_comment_block(source, symbol_line)
        if comment:
            content = comment.content
            # Check for Doxygen/structured patterns
            doxygen_markers = [
                "@pre",
                "@post",
                "@throws",
                "@invariant",
                "@param",
                "@return",
            ]
            if any(marker in content for marker in doxygen_markers):
                return DocumentationType.DOXYGEN
            # Has comment but no structure
            return DocumentationType.GENERIC_COMMENT

        return DocumentationType.NONE

    def is_llm_available(self) -> bool:
        """Check if Ollama LLM is available for Level 3 extraction."""
        if not self._enable_llm or not self._llm_extractor:
            return False
        return self._llm_extractor.is_available()

    def discover(
        self,
        file_path: Path,
        symbol_line: int,
        levels: Optional[List[int]] = None,
    ) -> ContractData:
        """
        Execute discovery pipeline for a symbol.

        Args:
            file_path: File to analyze
            symbol_line: Line of the symbol (1-indexed)
            levels: Optional list of levels to try (default: [1,2,3,4])

        Returns:
            ContractData with discovered contract
        """
        if levels is None:
            levels = [1, 2, 3, 4]

        # Get strategy for the language
        strategy = LanguageRegistry.get_for_file(file_path)

        if not strategy:
            return ContractData(
                confidence=0.0,
                source_level=5,
                confidence_notes=f"Unsupported language: {file_path.suffix}",
                file_path=file_path,
            )

        try:
            source = file_path.read_text(encoding="utf-8")
        except Exception as e:
            return ContractData(
                confidence=0.0,
                source_level=5,
                confidence_notes=f"Failed to read file: {e}",
                file_path=file_path,
            )

        # ─────────────────────────────────────────────────────
        # Level 1: @aegis-contract blocks
        # ─────────────────────────────────────────────────────
        if 1 in levels:
            block = strategy.find_contract_block(source, symbol_line)
            if block:
                contract = ContractData.from_yaml(block.content)
                contract.confidence = 1.0
                contract.source_level = 1
                contract.file_path = file_path
                contract.start_line = block.start_line
                contract.end_line = block.end_line

                if not contract.is_empty():
                    logger.debug(
                        f"Level 1: Found @aegis-contract at {file_path}:{symbol_line}"
                    )
                    return contract

        # ─────────────────────────────────────────────────────
        # Level 2: Known patterns (delegated to strategy)
        # ─────────────────────────────────────────────────────
        if 2 in levels:
            comment = strategy.find_comment_block(source, symbol_line)
            if comment:
                contract = strategy.parse_known_patterns(comment)
                if not contract.is_empty():
                    contract.file_path = file_path
                    contract.start_line = comment.start_line
                    contract.end_line = comment.end_line
                    logger.debug(
                        f"Level 2: Found pattern-based contract at {file_path}:{symbol_line}"
                    )
                    return contract

        # ─────────────────────────────────────────────────────
        # Level 3: LLM extraction (if enabled and available)
        # ─────────────────────────────────────────────────────
        if 3 in levels and self._enable_llm and self._llm_extractor:
            if self._llm_extractor.is_available():
                # Get context for LLM
                code_block = self._extract_code_context(source, symbol_line)
                comment = strategy.find_comment_block(source, symbol_line)
                if comment:
                    pass

                # Note: This is async, but we're in sync context
                # For now, skip LLM in sync discover()
                # LLM will be used via discover_async()
                pass

        # ─────────────────────────────────────────────────────
        # Level 4: Static analysis
        # ─────────────────────────────────────────────────────
        if 4 in levels:
            # Get code around the symbol for analysis
            code_block = self._extract_code_context(source, symbol_line, lines_after=50)
            contract = self._static_analyzer.analyze(code_block, file_path)

            if not contract.is_empty():
                contract.file_path = file_path
                contract.start_line = symbol_line
                logger.debug(
                    f"Level 4: Found static-inferred contract at {file_path}:{symbol_line}"
                )
                return contract

        # ─────────────────────────────────────────────────────
        # Level 5: No contract found
        # ─────────────────────────────────────────────────────
        return ContractData(
            confidence=0.0,
            source_level=5,
            file_path=file_path,
            start_line=symbol_line,
        )

    async def discover_async(
        self,
        file_path: Path,
        symbol_line: int,
        levels: Optional[List[int]] = None,
    ) -> ContractData:
        """
        Execute discovery pipeline with async LLM support.

        Args:
            file_path: File to analyze
            symbol_line: Line of the symbol (1-indexed)
            levels: Optional list of levels to try

        Returns:
            ContractData with discovered contract
        """
        if levels is None:
            levels = [1, 2, 3, 4]

        # Get strategy for the language
        strategy = LanguageRegistry.get_for_file(file_path)

        if not strategy:
            return ContractData(
                confidence=0.0,
                source_level=5,
                confidence_notes=f"Unsupported language: {file_path.suffix}",
                file_path=file_path,
            )

        try:
            source = file_path.read_text(encoding="utf-8")
        except Exception as e:
            return ContractData(
                confidence=0.0,
                source_level=5,
                confidence_notes=f"Failed to read file: {e}",
                file_path=file_path,
            )

        # Level 1: @aegis-contract blocks
        if 1 in levels:
            block = strategy.find_contract_block(source, symbol_line)
            if block:
                contract = ContractData.from_yaml(block.content)
                contract.confidence = 1.0
                contract.source_level = 1
                contract.file_path = file_path
                contract.start_line = block.start_line
                contract.end_line = block.end_line

                if not contract.is_empty():
                    return contract

        # Level 2: Known patterns
        if 2 in levels:
            comment = strategy.find_comment_block(source, symbol_line)
            if comment:
                contract = strategy.parse_known_patterns(comment)
                if not contract.is_empty():
                    contract.file_path = file_path
                    contract.start_line = comment.start_line
                    contract.end_line = comment.end_line
                    return contract

        # Level 3: LLM extraction
        if 3 in levels and self._enable_llm and self._llm_extractor:
            if self._llm_extractor.is_available():
                code_block = self._extract_code_context(source, symbol_line)
                documentation = ""
                comment = strategy.find_comment_block(source, symbol_line)
                if comment:
                    documentation = comment.content

                contract = await self._llm_extractor.extract(code_block, documentation)
                if not contract.is_empty():
                    contract.file_path = file_path
                    contract.start_line = symbol_line
                    return contract

        # Level 4: Static analysis
        if 4 in levels:
            code_block = self._extract_code_context(source, symbol_line, lines_after=50)
            contract = self._static_analyzer.analyze(code_block, file_path)

            if not contract.is_empty():
                contract.file_path = file_path
                contract.start_line = symbol_line
                return contract

        # Level 5: No contract found
        return ContractData(
            confidence=0.0,
            source_level=5,
            file_path=file_path,
            start_line=symbol_line,
        )

    def discover_file(
        self,
        file_path: Path,
        symbol_lines: List[int],
        levels: Optional[List[int]] = None,
    ) -> tuple[List[ContractData], DiscoveryStats]:
        """
        Discover contracts for multiple symbols in a file.

        Args:
            file_path: File to analyze
            symbol_lines: List of symbol line numbers
            levels: Levels to try

        Returns:
            Tuple of (contracts list, discovery stats)
        """
        stats = DiscoveryStats(total_symbols=len(symbol_lines))
        contracts = []

        for line in symbol_lines:
            contract = self.discover(file_path, line, levels)
            contracts.append(contract)

            # Update stats
            if contract.source_level == 1:
                stats.level_1_found += 1
            elif contract.source_level == 2:
                stats.level_2_found += 1
            elif contract.source_level == 3:
                stats.level_3_found += 1
            elif contract.source_level == 4:
                stats.level_4_found += 1
            else:
                stats.level_5_found += 1

        return contracts, stats

    def _extract_code_context(
        self,
        source: str,
        symbol_line: int,
        lines_before: int = 5,
        lines_after: int = 30,
    ) -> str:
        """Extract code context around a symbol."""
        lines = source.splitlines()
        start = max(0, symbol_line - 1 - lines_before)
        end = min(len(lines), symbol_line + lines_after)
        return "\n".join(lines[start:end])
