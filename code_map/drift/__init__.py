# SPDX-License-Identifier: MIT
"""
Drift detection module for AEGIS v2.

Detects inconsistencies between:
- Contracts and symbol signatures (structural drift)
- Wiring graph and code (wiring drift)
- Contract claims and implementation (semantic drift)

Principle: No second model file - everything derived from code.
"""

from .models import (
    DriftType,
    DriftCategory,
    DriftSeverity,
    DriftItem,
    DriftReport,
)
from .detectors import (
    DriftDetector,
    StructuralDriftDetector,
    WiringDriftDetector,
    SemanticDriftDetector,
)
from .analyzer import DriftAnalyzer

__all__ = [
    # Models
    "DriftType",
    "DriftCategory",
    "DriftSeverity",
    "DriftItem",
    "DriftReport",
    # Detectors
    "DriftDetector",
    "StructuralDriftDetector",
    "WiringDriftDetector",
    "SemanticDriftDetector",
    # Service
    "DriftAnalyzer",
]
