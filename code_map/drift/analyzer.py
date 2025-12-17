# SPDX-License-Identifier: MIT
"""
DriftAnalyzer service for orchestrating drift detection.

Coordinates all drift detectors and produces comprehensive reports.
"""

import logging
import time
from pathlib import Path
from typing import Optional

from .detectors import (
    DriftContext,
    DriftDetector,
    SemanticDriftDetector,
    StructuralDriftDetector,
    WiringDriftDetector,
)
from .models import DriftReport, DriftType

logger = logging.getLogger(__name__)


class DriftAnalyzer:
    """
    Orchestrates drift detection across multiple detectors.

    Usage:
        analyzer = DriftAnalyzer(project_root=Path("/path/to/project"))
        report = await analyzer.analyze()
        if report.has_blocking_drift:
            print("Cannot apply changes - blocking drift detected")
    """

    def __init__(
        self,
        project_root: Path,
        enable_semantic: bool = False,
    ):
        """
        Initialize the drift analyzer.

        Args:
            project_root: Root directory of the project
            enable_semantic: Whether to enable semantic drift detection (heuristic)
        """
        self.project_root = project_root
        self.enable_semantic = enable_semantic

        # Initialize detectors
        self._structural = StructuralDriftDetector()
        self._wiring = WiringDriftDetector()
        self._semantic = SemanticDriftDetector()

        # Wiring state cache (session-based)
        self._previous_wiring: Optional[dict] = None
        self._current_wiring: Optional[dict] = None

    async def analyze(
        self,
        file_paths: Optional[list[Path]] = None,
        include_semantic: Optional[bool] = None,
    ) -> DriftReport:
        """
        Run full drift analysis.

        Args:
            file_paths: Optional list of files to check (None = all)
            include_semantic: Override semantic detection setting

        Returns:
            Complete drift report
        """
        start_time = time.time()

        # Build context
        context = await self._build_context()

        # Determine which detectors to run
        detectors: list[DriftDetector] = [
            self._structural,
            self._wiring,
        ]

        use_semantic = include_semantic if include_semantic is not None else self.enable_semantic
        if use_semantic:
            detectors.append(self._semantic)

        # Run all detectors
        all_items = []
        analyzed_files = set()

        for detector in detectors:
            try:
                items = await detector.detect(context, file_paths)
                all_items.extend(items)

                # Track analyzed files
                for item in items:
                    if item.file_path:
                        analyzed_files.add(item.file_path)

                logger.info(
                    f"{detector.__class__.__name__}: found {len(items)} drift items"
                )
            except Exception as e:
                logger.error(f"Error in {detector.__class__.__name__}: {e}")

        # Calculate duration
        duration_ms = (time.time() - start_time) * 1000

        # Build report
        report = DriftReport(
            items=all_items,
            analyzed_files=list(analyzed_files),
            duration_ms=duration_ms,
        )

        logger.info(
            f"Drift analysis complete: {report.total_count} items, "
            f"blocking={report.has_blocking_drift}, {duration_ms:.1f}ms"
        )

        return report

    async def analyze_structural(
        self,
        file_paths: Optional[list[Path]] = None,
    ) -> DriftReport:
        """Run only structural drift detection."""
        return await self._run_single_detector(self._structural, file_paths)

    async def analyze_wiring(
        self,
        file_paths: Optional[list[Path]] = None,
    ) -> DriftReport:
        """Run only wiring drift detection."""
        return await self._run_single_detector(self._wiring, file_paths)

    async def analyze_semantic(
        self,
        file_paths: Optional[list[Path]] = None,
    ) -> DriftReport:
        """Run only semantic drift detection."""
        return await self._run_single_detector(self._semantic, file_paths)

    async def _run_single_detector(
        self,
        detector: DriftDetector,
        file_paths: Optional[list[Path]] = None,
    ) -> DriftReport:
        """Run a single detector and return report."""
        start_time = time.time()
        context = await self._build_context()

        items = await detector.detect(context, file_paths)
        duration_ms = (time.time() - start_time) * 1000

        analyzed_files = list(set(item.file_path for item in items if item.file_path))

        return DriftReport(
            items=items,
            analyzed_files=analyzed_files,
            duration_ms=duration_ms,
        )

    async def _build_context(self) -> DriftContext:
        """Build drift detection context with available services."""
        context = DriftContext(project_root=self.project_root)

        # Try to load contract discovery
        try:
            from code_map.contracts import ContractDiscovery

            context.contract_discovery = ContractDiscovery(enable_llm=False)
        except ImportError:
            logger.debug("ContractDiscovery not available")

        # Try to load symbol index
        try:
            from code_map.index import SymbolIndex

            context.symbol_index = SymbolIndex(self.project_root)
        except ImportError:
            logger.debug("SymbolIndex not available")

        # Add wiring state
        context.previous_wiring = self._previous_wiring
        context.current_wiring = self._current_wiring

        return context

    def update_wiring_state(self, wiring: dict) -> None:
        """
        Update wiring state for drift detection.

        Call this when composition root is re-analyzed to enable
        wiring drift detection.

        Args:
            wiring: New wiring state dict with "instances" and "edges"
        """
        self._previous_wiring = self._current_wiring
        self._current_wiring = wiring
        logger.debug("Wiring state updated")

    def clear_wiring_state(self) -> None:
        """Clear wiring state cache."""
        self._previous_wiring = None
        self._current_wiring = None
        logger.debug("Wiring state cleared")

    def get_status(self) -> dict:
        """Get current analyzer status."""
        return {
            "project_root": str(self.project_root),
            "semantic_enabled": self.enable_semantic,
            "has_previous_wiring": self._previous_wiring is not None,
            "has_current_wiring": self._current_wiring is not None,
            "detectors": {
                "structural": True,
                "wiring": True,
                "semantic": self.enable_semantic,
            },
        }


async def check_drift_before_apply(
    project_root: Path,
    affected_files: list[Path],
) -> tuple[bool, DriftReport]:
    """
    Convenience function to check drift before applying changes.

    Args:
        project_root: Project root directory
        affected_files: Files that will be affected by changes

    Returns:
        Tuple of (can_proceed, drift_report)
    """
    analyzer = DriftAnalyzer(project_root)
    report = await analyzer.analyze(file_paths=affected_files)

    can_proceed = not report.has_blocking_drift
    return can_proceed, report
