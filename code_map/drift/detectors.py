# SPDX-License-Identifier: MIT
"""
Drift detectors for different types of inconsistencies.

Each detector focuses on a specific aspect:
- StructuralDriftDetector: Contract vs symbol signatures
- WiringDriftDetector: Graph vs code composition
- SemanticDriftDetector: Contract claims vs implementation (heuristic)
"""

import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from .models import (
    DriftCategory,
    DriftItem,
    DriftSeverity,
    DriftType,
)

if TYPE_CHECKING:
    from code_map.contracts import ContractData, ContractDiscovery
    from code_map.index import SymbolIndex

logger = logging.getLogger(__name__)


@dataclass
class DriftContext:
    """Shared context for drift detection."""

    project_root: Path
    symbol_index: Optional["SymbolIndex"] = None
    contract_discovery: Optional["ContractDiscovery"] = None
    # Cache for previous wiring state (session-based)
    previous_wiring: Optional[dict] = None
    current_wiring: Optional[dict] = None


class DriftDetector(ABC):
    """Abstract base class for drift detectors."""

    @property
    @abstractmethod
    def drift_type(self) -> DriftType:
        """The type of drift this detector finds."""
        pass

    @abstractmethod
    async def detect(
        self,
        context: DriftContext,
        file_paths: Optional[list[Path]] = None,
    ) -> list[DriftItem]:
        """
        Detect drift issues.

        Args:
            context: Shared drift detection context
            file_paths: Optional list of files to check (None = all)

        Returns:
            List of detected drift items
        """
        pass


class StructuralDriftDetector(DriftDetector):
    """
    Detects structural drift between contracts and symbol signatures.

    Checks:
    - Contract references symbols that no longer exist
    - Symbol signatures changed (params, return type)
    - Evidence references that don't exist
    - Orphaned contract blocks
    """

    @property
    def drift_type(self) -> DriftType:
        return DriftType.STRUCTURAL

    async def detect(
        self,
        context: DriftContext,
        file_paths: Optional[list[Path]] = None,
    ) -> list[DriftItem]:
        """Detect structural drift."""
        items: list[DriftItem] = []

        if not context.contract_discovery:
            logger.warning("No contract discovery available for structural drift detection")
            return items

        # Get files to analyze
        files_to_check = file_paths or self._get_supported_files(context.project_root)

        for file_path in files_to_check:
            if not file_path.exists():
                continue

            try:
                items.extend(await self._check_file(context, file_path))
            except Exception as e:
                logger.error(f"Error checking {file_path}: {e}")

        return items

    def _get_supported_files(self, root: Path) -> list[Path]:
        """Get all supported source files."""
        supported_extensions = {".py", ".cpp", ".hpp", ".h", ".hxx", ".cxx"}
        files = []
        for ext in supported_extensions:
            files.extend(root.rglob(f"*{ext}"))
        return files

    async def _check_file(
        self, context: DriftContext, file_path: Path
    ) -> list[DriftItem]:
        """Check a single file for structural drift."""
        items: list[DriftItem] = []

        # Discover contracts in the file
        try:
            contract = context.contract_discovery.discover(file_path, symbol_line=1)
        except Exception as e:
            logger.debug(f"Could not discover contract in {file_path}: {e}")
            return items

        if contract.is_empty():
            return items

        # Check evidence references
        items.extend(self._check_evidence_references(contract, file_path))

        # If we have symbol index, check signature drift
        if context.symbol_index:
            items.extend(
                await self._check_signature_drift(context, contract, file_path)
            )

        return items

    def _check_evidence_references(
        self, contract: "ContractData", file_path: Path
    ) -> list[DriftItem]:
        """Check if evidence references are valid."""
        items: list[DriftItem] = []

        for evidence in contract.evidence:
            reference = evidence.reference

            # Check if test file exists (for test references)
            if evidence.type == "test" and "::" in reference:
                test_file = reference.split("::")[0]
                test_path = file_path.parent / test_file
                if not test_path.exists():
                    items.append(
                        DriftItem(
                            type=DriftType.STRUCTURAL,
                            category=DriftCategory.EVIDENCE_MISSING,
                            severity=DriftSeverity.WARNING,
                            file_path=file_path,
                            title=f"Missing test file: {test_file}",
                            description=f"Contract references test '{reference}' but file doesn't exist",
                            suggestion=f"Create test file at {test_path} or update evidence reference",
                        )
                    )

            # Check if evidence is stale (hasn't run recently)
            if evidence.last_run is None:
                items.append(
                    DriftItem(
                        type=DriftType.STRUCTURAL,
                        category=DriftCategory.EVIDENCE_STALE,
                        severity=DriftSeverity.INFO,
                        file_path=file_path,
                        title=f"Evidence never executed: {reference}",
                        description=f"Evidence '{evidence.type}:{reference}' has never been run",
                        suggestion="Run gates to verify evidence",
                    )
                )

        return items

    async def _check_signature_drift(
        self,
        context: DriftContext,
        contract: "ContractData",
        file_path: Path,
    ) -> list[DriftItem]:
        """Check if symbol signatures match contract expectations."""
        items: list[DriftItem] = []
        # This would require symbol index integration
        # For MVP, we detect basic signature info from preconditions

        # Example: if precondition mentions "x > 0" but function has no param x
        source = file_path.read_text(encoding="utf-8")

        for precondition in contract.preconditions:
            # Extract parameter names from preconditions (simple heuristic)
            param_match = re.search(r"\b([a-z_][a-z0-9_]*)\s*[><=!]", precondition, re.I)
            if param_match:
                param_name = param_match.group(1)
                # Check if this param appears in function signatures nearby
                if param_name not in source:
                    items.append(
                        DriftItem(
                            type=DriftType.STRUCTURAL,
                            category=DriftCategory.SIGNATURE_CHANGED,
                            severity=DriftSeverity.WARNING,
                            file_path=file_path,
                            title=f"Precondition references unknown parameter",
                            description=f"Precondition '{precondition}' references '{param_name}' which may not exist",
                            suggestion=f"Verify parameter '{param_name}' exists or update precondition",
                            before_context=precondition,
                        )
                    )

        return items


class WiringDriftDetector(DriftDetector):
    """
    Detects wiring drift in composition roots.

    Checks:
    - Edges added or removed
    - Instances added or removed
    - Instance types changed
    """

    @property
    def drift_type(self) -> DriftType:
        return DriftType.WIRING

    async def detect(
        self,
        context: DriftContext,
        file_paths: Optional[list[Path]] = None,
    ) -> list[DriftItem]:
        """Detect wiring drift."""
        items: list[DriftItem] = []

        if context.previous_wiring is None or context.current_wiring is None:
            logger.debug("No wiring state available for drift detection")
            return items

        prev = context.previous_wiring
        curr = context.current_wiring

        # Compare instances
        prev_instances = set(prev.get("instances", {}).keys())
        curr_instances = set(curr.get("instances", {}).keys())

        # Detect added instances
        for instance_id in curr_instances - prev_instances:
            instance = curr["instances"][instance_id]
            items.append(
                DriftItem(
                    type=DriftType.WIRING,
                    category=DriftCategory.INSTANCE_ADDED,
                    severity=DriftSeverity.INFO,
                    file_path=Path(instance.get("file", "unknown")),
                    line_number=instance.get("line"),
                    symbol_name=instance_id,
                    title=f"New instance: {instance_id}",
                    description=f"Instance '{instance_id}' was added to composition root",
                    after_context=f"Type: {instance.get('type', 'unknown')}",
                )
            )

        # Detect removed instances
        for instance_id in prev_instances - curr_instances:
            instance = prev["instances"][instance_id]
            items.append(
                DriftItem(
                    type=DriftType.WIRING,
                    category=DriftCategory.INSTANCE_REMOVED,
                    severity=DriftSeverity.WARNING,
                    file_path=Path(instance.get("file", "unknown")),
                    line_number=instance.get("line"),
                    symbol_name=instance_id,
                    title=f"Removed instance: {instance_id}",
                    description=f"Instance '{instance_id}' was removed from composition root",
                    suggestion="Verify this removal was intentional",
                    before_context=f"Type: {instance.get('type', 'unknown')}",
                )
            )

        # Compare edges
        prev_edges = set(
            (e["from"], e["to"]) for e in prev.get("edges", [])
        )
        curr_edges = set(
            (e["from"], e["to"]) for e in curr.get("edges", [])
        )

        # Detect added edges
        for from_id, to_id in curr_edges - prev_edges:
            items.append(
                DriftItem(
                    type=DriftType.WIRING,
                    category=DriftCategory.EDGE_ADDED,
                    severity=DriftSeverity.INFO,
                    file_path=context.project_root,
                    title=f"New connection: {from_id} → {to_id}",
                    description=f"Edge from '{from_id}' to '{to_id}' was added",
                    after_context=f"{from_id} → {to_id}",
                )
            )

        # Detect removed edges
        for from_id, to_id in prev_edges - curr_edges:
            items.append(
                DriftItem(
                    type=DriftType.WIRING,
                    category=DriftCategory.EDGE_REMOVED,
                    severity=DriftSeverity.WARNING,
                    file_path=context.project_root,
                    title=f"Removed connection: {from_id} → {to_id}",
                    description=f"Edge from '{from_id}' to '{to_id}' was removed",
                    suggestion="Verify this edge removal was intentional",
                    before_context=f"{from_id} → {to_id}",
                )
            )

        # Check for type changes on existing instances
        for instance_id in prev_instances & curr_instances:
            prev_type = prev["instances"][instance_id].get("type")
            curr_type = curr["instances"][instance_id].get("type")
            if prev_type != curr_type:
                items.append(
                    DriftItem(
                        type=DriftType.WIRING,
                        category=DriftCategory.TYPE_CHANGED,
                        severity=DriftSeverity.WARNING,
                        file_path=Path(curr["instances"][instance_id].get("file", "unknown")),
                        symbol_name=instance_id,
                        title=f"Type changed: {instance_id}",
                        description=f"Instance '{instance_id}' type changed from '{prev_type}' to '{curr_type}'",
                        before_context=prev_type,
                        after_context=curr_type,
                    )
                )

        return items


class SemanticDriftDetector(DriftDetector):
    """
    Detects semantic drift between contracts and implementation.

    Uses heuristics to detect obvious mismatches:
    - Thread safety claims vs mutex/lock usage
    - Precondition checks not present in code
    - Error handling claims vs actual throws
    """

    @property
    def drift_type(self) -> DriftType:
        return DriftType.SEMANTIC

    async def detect(
        self,
        context: DriftContext,
        file_paths: Optional[list[Path]] = None,
    ) -> list[DriftItem]:
        """Detect semantic drift."""
        items: list[DriftItem] = []

        if not context.contract_discovery:
            logger.warning("No contract discovery available for semantic drift detection")
            return items

        # Get files to analyze
        files_to_check = file_paths or self._get_supported_files(context.project_root)

        for file_path in files_to_check:
            if not file_path.exists():
                continue

            try:
                items.extend(await self._check_file(context, file_path))
            except Exception as e:
                logger.error(f"Error checking {file_path}: {e}")

        return items

    def _get_supported_files(self, root: Path) -> list[Path]:
        """Get all supported source files."""
        supported_extensions = {".py", ".cpp", ".hpp", ".h"}
        files = []
        for ext in supported_extensions:
            files.extend(root.rglob(f"*{ext}"))
        return files

    async def _check_file(
        self, context: DriftContext, file_path: Path
    ) -> list[DriftItem]:
        """Check a single file for semantic drift."""
        items: list[DriftItem] = []

        try:
            contract = context.contract_discovery.discover(file_path, symbol_line=1)
        except Exception as e:
            logger.debug(f"Could not discover contract in {file_path}: {e}")
            return items

        if contract.is_empty():
            return items

        source = file_path.read_text(encoding="utf-8")

        # Check thread safety claims
        items.extend(self._check_thread_safety(contract, source, file_path))

        # Check precondition validations
        items.extend(self._check_preconditions(contract, source, file_path))

        # Check error handling
        items.extend(self._check_error_handling(contract, source, file_path))

        return items

    def _check_thread_safety(
        self, contract: "ContractData", source: str, file_path: Path
    ) -> list[DriftItem]:
        """Check if thread safety claims match implementation."""
        items: list[DriftItem] = []

        if not contract.thread_safety:
            return items

        from code_map.contracts import ThreadSafety

        safety = contract.thread_safety
        source_lower = source.lower()

        # Patterns indicating thread-safe implementation
        thread_safe_patterns = [
            "mutex", "lock", "atomic", "synchronized",
            "thread_local", "threading.lock", "asyncio.lock",
        ]

        # Patterns indicating not thread-safe
        not_safe_patterns = [
            "global ", "self._", "this->",  # Mutable state
        ]

        has_sync_primitives = any(p in source_lower for p in thread_safe_patterns)
        has_mutable_state = any(p in source_lower for p in not_safe_patterns)

        # Contract says safe but no sync primitives and has mutable state
        if safety == ThreadSafety.SAFE and has_mutable_state and not has_sync_primitives:
            items.append(
                DriftItem(
                    type=DriftType.SEMANTIC,
                    category=DriftCategory.THREAD_SAFETY_MISMATCH,
                    severity=DriftSeverity.WARNING,
                    file_path=file_path,
                    title="Thread safety claim may be incorrect",
                    description="Contract claims thread-safe but code has mutable state without visible synchronization",
                    suggestion="Add synchronization primitives or change thread_safety to 'not_safe'",
                    before_context=f"Contract: thread_safety={safety.value}",
                    after_context="Found mutable state, no sync primitives",
                )
            )

        # Contract says not safe but has sync primitives
        if safety == ThreadSafety.NOT_SAFE and has_sync_primitives:
            items.append(
                DriftItem(
                    type=DriftType.SEMANTIC,
                    category=DriftCategory.THREAD_SAFETY_MISMATCH,
                    severity=DriftSeverity.INFO,
                    file_path=file_path,
                    title="Thread safety may be understated",
                    description="Contract claims not thread-safe but code has synchronization primitives",
                    suggestion="Consider updating thread_safety to 'safe' if fully synchronized",
                    before_context=f"Contract: thread_safety={safety.value}",
                    after_context="Found synchronization primitives",
                )
            )

        return items

    def _check_preconditions(
        self, contract: "ContractData", source: str, file_path: Path
    ) -> list[DriftItem]:
        """Check if preconditions appear to be validated in code."""
        items: list[DriftItem] = []

        for precondition in contract.preconditions:
            # Extract the condition pattern
            # Simple heuristic: look for if/assert with similar terms
            terms = re.findall(r"\b([a-z_][a-z0-9_]*)\b", precondition.lower())

            # Check if any validation appears in code
            validation_patterns = [
                rf"if\s+.*\b({'|'.join(terms)})\b",
                rf"assert\s+.*\b({'|'.join(terms)})\b",
                rf"raise\s+.*\b({'|'.join(terms)})\b",
            ]

            has_validation = any(
                re.search(p, source, re.I) for p in validation_patterns
            )

            if not has_validation and terms:
                items.append(
                    DriftItem(
                        type=DriftType.SEMANTIC,
                        category=DriftCategory.PRECONDITION_UNCHECKED,
                        severity=DriftSeverity.INFO,
                        file_path=file_path,
                        title=f"Precondition may not be validated",
                        description=f"Precondition '{precondition}' has no obvious validation in code",
                        suggestion="Add runtime check or document that validation happens elsewhere",
                        before_context=f"Precondition: {precondition}",
                    )
                )

        return items

    def _check_error_handling(
        self, contract: "ContractData", source: str, file_path: Path
    ) -> list[DriftItem]:
        """Check if declared errors are handled in code."""
        items: list[DriftItem] = []

        for error in contract.errors:
            # Extract error type from declaration
            error_match = re.search(r"(\w+Error|\w+Exception)", error)
            if not error_match:
                continue

            error_type = error_match.group(1)

            # Check if this error is raised or caught
            if error_type not in source:
                items.append(
                    DriftItem(
                        type=DriftType.SEMANTIC,
                        category=DriftCategory.ERROR_UNHANDLED,
                        severity=DriftSeverity.INFO,
                        file_path=file_path,
                        title=f"Declared error not found in code",
                        description=f"Contract declares '{error_type}' but it's not raised or caught in code",
                        suggestion="Add error handling or remove from contract",
                        before_context=f"Error: {error}",
                    )
                )

        return items
