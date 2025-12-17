# SPDX-License-Identifier: MIT
"""
Level 4: Static analysis for contract inference.

Orchestrates multiple analyzers to extract implied contracts:
- Ownership from smart pointers (C++), field assignments (Python), readonly fields (TS)
- Dependencies from constructors/setters
- Lifecycle from method names
- Thread safety from sync primitives
- Preconditions from asserts
- Errors from throw/raise

Supports: C++, Python, TypeScript/JavaScript
"""

import logging
import re
from pathlib import Path
from typing import List, Optional

from ..schema import ContractData, ThreadSafety

# Import tree-sitter for AST parsing
try:
    import tree_sitter_languages

    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False

# Import new analyzers
from .models import L4Confidence, L4Finding, L4FindingType

logger = logging.getLogger(__name__)


class StaticAnalyzer:
    """
    Orchestrator for L4 static analysis.

    Combines multiple specialized analyzers with legacy regex patterns
    to extract contract information from source code.
    """

    # Legacy precondition patterns (kept for backward compatibility)
    PRECONDITION_PATTERNS = [
        # C++ assert
        (re.compile(r"assert\s*\(\s*(.+?)\s*\)"), "cpp"),
        # C++ null check before throw
        (re.compile(r"if\s*\(\s*!?\s*(\w+)\s*\)\s*throw"), "cpp"),
        (re.compile(r"if\s*\(\s*(\w+)\s*==\s*nullptr\s*\)"), "cpp"),
        # Python assert
        (re.compile(r"assert\s+(.+?)(?:,|\n|$)"), "python"),
        # Python if-raise
        (re.compile(r"if\s+(.+?):\s*\n\s*raise"), "python"),
    ]

    # Legacy thread safety patterns (kept for non-C++ languages)
    THREAD_SAFETY_PATTERNS = [
        # Python
        (re.compile(r"threading\.Lock"), "python", ThreadSafety.SAFE),
        (re.compile(r"threading\.RLock"), "python", ThreadSafety.SAFE),
        (re.compile(r"asyncio\.Lock"), "python", ThreadSafety.SAFE),
    ]

    # Legacy error patterns
    ERROR_PATTERNS = [
        # C++ throw
        (re.compile(r"throw\s+(\w+)(?:\s*\()?"), "cpp"),
        # Python raise
        (re.compile(r"raise\s+(\w+)(?:\s*\()?"), "python"),
    ]

    # File extensions by language
    CPP_EXTENSIONS = (".cpp", ".hpp", ".h", ".cc", ".c", ".cxx", ".hxx")
    PYTHON_EXTENSIONS = (".py", ".pyi")
    TS_EXTENSIONS = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".mts")

    def __init__(self):
        """Initialize the analyzer with all sub-analyzers."""
        self._cpp_analyzers = []
        self._python_analyzers = []
        self._ts_analyzers = []
        self._tree_sitter_ready = False

        if TREE_SITTER_AVAILABLE:
            try:
                # Initialize C++ analyzers
                from .analyzers import (
                    DependencyAnalyzer,
                    LifecycleAnalyzer,
                    OwnershipAnalyzer,
                    ThreadSafetyAnalyzer,
                )

                self._cpp_analyzers = [
                    OwnershipAnalyzer(),
                    DependencyAnalyzer(),
                    LifecycleAnalyzer(),
                    ThreadSafetyAnalyzer(),
                ]

                # Initialize Python analyzers
                from .analyzers import (
                    PythonDependencyAnalyzer,
                    PythonLifecycleAnalyzer,
                    PythonOwnershipAnalyzer,
                    PythonThreadSafetyAnalyzer,
                )

                self._python_analyzers = [
                    PythonOwnershipAnalyzer(),
                    PythonDependencyAnalyzer(),
                    PythonLifecycleAnalyzer(),
                    PythonThreadSafetyAnalyzer(),
                ]

                # Initialize TypeScript/JavaScript analyzers
                from .analyzers import (
                    TypeScriptDependencyAnalyzer,
                    TypeScriptLifecycleAnalyzer,
                    TypeScriptOwnershipAnalyzer,
                    TypeScriptThreadSafetyAnalyzer,
                )

                self._ts_analyzers = [
                    TypeScriptOwnershipAnalyzer(),
                    TypeScriptDependencyAnalyzer(),
                    TypeScriptLifecycleAnalyzer(),
                    TypeScriptThreadSafetyAnalyzer(),
                ]

                self._tree_sitter_ready = True
                logger.debug("L4 analyzers initialized with tree-sitter support (C++, Python, TS)")
            except Exception as e:
                logger.warning(f"Failed to initialize L4 analyzers: {e}")

    def analyze(self, source: str, file_path: Path) -> ContractData:
        """
        Analyze source code for implied contracts.

        Uses AST-based analyzers for C++, Python, and TypeScript when tree-sitter
        is available. Falls back to regex patterns otherwise.

        Args:
            source: Source code content
            file_path: Path to determine language

        Returns:
            ContractData with inferred contracts
        """
        ext = file_path.suffix.lower()
        lang = self._detect_language(ext)

        # Try AST-based analysis if available
        if self._tree_sitter_ready and lang in ("cpp", "python", "typescript"):
            try:
                return self._analyze_with_ast(source, file_path, lang)
            except Exception as e:
                logger.warning(f"AST analysis failed for {lang}, falling back to regex: {e}")

        # Fallback to legacy regex analysis
        return self._analyze_with_regex(source, file_path)

    def _detect_language(self, ext: str) -> str:
        """Detect language from file extension."""
        if ext in self.CPP_EXTENSIONS:
            return "cpp"
        elif ext in self.PYTHON_EXTENSIONS:
            return "python"
        elif ext in self.TS_EXTENSIONS:
            return "typescript"
        return "unknown"

    def _analyze_with_ast(
        self, source: str, file_path: Path, lang: str
    ) -> ContractData:
        """
        Analyze source using tree-sitter AST.

        Args:
            source: Source code content
            file_path: File path for metadata
            lang: Language identifier ("cpp", "python", "typescript")

        Returns:
            ContractData with merged findings from all analyzers
        """
        # Get parser and analyzers for language
        parser_lang, analyzers = self._get_parser_and_analyzers(lang)

        # Parse with tree-sitter
        parser = tree_sitter_languages.get_parser(parser_lang)
        tree = parser.parse(source.encode("utf-8"))
        ast = tree.root_node

        # Run all analyzers and collect findings
        all_findings: List[L4Finding] = []

        for analyzer in analyzers:
            try:
                findings = analyzer.analyze(ast, source)
                all_findings.extend(findings)
                logger.debug(f"{analyzer.name}: {len(findings)} findings")
            except Exception as e:
                logger.warning(f"Analyzer {analyzer.name} failed: {e}")

        # Also run legacy regex patterns for preconditions and errors
        legacy_contract = self._analyze_with_regex(source, file_path)

        # Merge everything into final contract
        return self._merge_findings(all_findings, legacy_contract, file_path)

    def _get_parser_and_analyzers(self, lang: str) -> tuple[str, list]:
        """Get the tree-sitter parser name and analyzers for a language."""
        if lang == "cpp":
            return "cpp", self._cpp_analyzers
        elif lang == "python":
            return "python", self._python_analyzers
        elif lang == "typescript":
            # tree-sitter uses "typescript" for both .ts and .tsx
            return "typescript", self._ts_analyzers
        return "cpp", []  # Fallback

    def _analyze_with_regex(self, source: str, file_path: Path) -> ContractData:
        """
        Legacy regex-based analysis.

        Args:
            source: Source code content
            file_path: Path to determine language

        Returns:
            ContractData with inferred contracts
        """
        contract = ContractData(
            confidence=0.4,
            source_level=4,
            inferred=True,
            file_path=file_path,
        )

        # Determine language
        ext = file_path.suffix.lower()
        lang = "cpp" if ext in self.CPP_EXTENSIONS else "python"

        # Extract preconditions
        preconditions = self._extract_preconditions(source, lang)
        contract.preconditions = preconditions[:5]  # Limit to avoid noise

        # Detect thread safety (only for non-C++ since AST handles C++)
        if lang != "cpp" or not self._tree_sitter_ready:
            thread_safety = self._detect_thread_safety(source, lang)
            if thread_safety:
                contract.thread_safety = thread_safety

        # Extract errors
        errors = self._extract_errors(source, lang)
        contract.errors = list(set(errors))[:5]  # Dedupe and limit

        if contract.is_empty():
            contract.confidence = 0.0
            contract.confidence_notes = "No patterns detected in static analysis"

        return contract

    def _merge_findings(
        self,
        findings: List[L4Finding],
        legacy: ContractData,
        file_path: Path,
    ) -> ContractData:
        """
        Merge AST findings with legacy regex findings.

        Args:
            findings: Findings from AST analyzers
            legacy: Contract from legacy regex analysis
            file_path: File path for metadata

        Returns:
            Merged ContractData
        """
        contract = ContractData(
            source_level=4,
            inferred=True,
            file_path=file_path,
        )

        # Start with legacy data (preconditions, errors)
        contract.preconditions = legacy.preconditions
        contract.errors = legacy.errors

        # Track what we found for notes
        finding_sources = []
        max_confidence = legacy.confidence if not legacy.is_empty() else 0.0

        # Process findings by type
        ownership_items = []
        dependency_items = []
        lifecycle_items = []
        thread_safety_found = False

        for finding in findings:
            max_confidence = max(max_confidence, finding.confidence_score)

            if finding.type == L4FindingType.OWNERSHIP:
                ownership_items.append(finding.value)

            elif finding.type == L4FindingType.DEPENDENCY:
                dependency_items.append(finding.value)

            elif finding.type == L4FindingType.LIFECYCLE:
                lifecycle_items.append(finding.value)

            elif finding.type == L4FindingType.THREAD_SAFETY:
                if "safe" in finding.value.lower():
                    contract.thread_safety = ThreadSafety.SAFE
                    thread_safety_found = True

        # Populate contract fields
        if dependency_items:
            contract.dependencies = list(set(dependency_items))[:5]
            finding_sources.append(f"dependencies({len(contract.dependencies)})")

        if lifecycle_items:
            # Combine lifecycle items into a single string
            contract.lifecycle = "; ".join(sorted(set(lifecycle_items)))
            finding_sources.append("lifecycle")

        if ownership_items:
            finding_sources.append(f"ownership({len(ownership_items)})")

        if thread_safety_found:
            finding_sources.append("thread_safety")

        if contract.preconditions:
            finding_sources.append(f"preconditions({len(contract.preconditions)})")

        if contract.errors:
            finding_sources.append(f"errors({len(contract.errors)})")

        # Set confidence
        contract.confidence = max_confidence

        # Build confidence notes
        if finding_sources:
            contract.confidence_notes = f"L4 findings: {', '.join(finding_sources)}"
        elif contract.is_empty():
            contract.confidence = 0.0
            contract.confidence_notes = "No patterns detected in static analysis"

        return contract

    def _extract_preconditions(self, source: str, lang: str) -> List[str]:
        """Extract preconditions from assert patterns."""
        preconditions = []

        for pattern, pattern_lang in self.PRECONDITION_PATTERNS:
            if pattern_lang != lang:
                continue
            for match in pattern.finditer(source):
                condition = match.group(1).strip()
                if condition and len(condition) < 100:  # Skip overly complex
                    # Clean up the condition
                    condition = " ".join(condition.split())
                    preconditions.append(condition)

        return preconditions

    def _detect_thread_safety(self, source: str, lang: str) -> Optional[ThreadSafety]:
        """Detect thread safety from synchronization primitives (legacy)."""
        for pattern, pattern_lang, safety in self.THREAD_SAFETY_PATTERNS:
            if pattern_lang != lang:
                continue
            if pattern.search(source):
                return safety
        return None

    def _extract_errors(self, source: str, lang: str) -> List[str]:
        """Extract error types from throw/raise statements."""
        errors = []

        for pattern, pattern_lang in self.ERROR_PATTERNS:
            if pattern_lang != lang:
                continue
            for match in pattern.finditer(source):
                error_type = match.group(1).strip()
                if error_type and error_type not in ("if", "else", "return"):
                    errors.append(error_type)

        return errors

    def get_findings(self, source: str, file_path: Path) -> List[L4Finding]:
        """
        Get raw findings without merging into ContractData.

        Useful for debugging or detailed analysis.

        Args:
            source: Source code content
            file_path: File path

        Returns:
            List of all L4Finding objects
        """
        if not self._tree_sitter_ready:
            return []

        ext = file_path.suffix.lower()
        lang = self._detect_language(ext)

        if lang == "unknown":
            return []

        try:
            parser_lang, analyzers = self._get_parser_and_analyzers(lang)
            parser = tree_sitter_languages.get_parser(parser_lang)
            tree = parser.parse(source.encode("utf-8"))
            ast = tree.root_node

            all_findings = []
            for analyzer in analyzers:
                findings = analyzer.analyze(ast, source)
                all_findings.extend(findings)

            return all_findings
        except Exception as e:
            logger.warning(f"Failed to get findings: {e}")
            return []
