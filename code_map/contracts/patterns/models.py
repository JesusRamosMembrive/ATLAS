# SPDX-License-Identifier: MIT
"""
L4 Static Analysis Models.

Defines data structures for Level 4 contract extraction with
sub-level confidence gradation.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class L4Confidence(Enum):
    """
    Sub-levels within L4 (base 40%) for confidence gradation.

    - HIGH (40%): Very reliable patterns (unique_ptr, mutex, assert)
    - MEDIUM (30%): Reasonable inferences (lifecycle names, guards)
    - LOW (20%): Speculative heuristics (naming patterns like *Cache)
    """

    HIGH = 0.40
    MEDIUM = 0.30
    LOW = 0.20


class L4FindingType(Enum):
    """Types of findings from static analysis."""

    OWNERSHIP = "ownership"
    DEPENDENCY = "dependency"
    LIFECYCLE = "lifecycle"
    THREAD_SAFETY = "thread_safety"
    PRECONDITION = "precondition"
    POSTCONDITION = "postcondition"
    ERROR = "error"
    INVARIANT = "invariant"


@dataclass
class L4Finding:
    """
    A single finding from static analysis.

    Attributes:
        type: The category of finding
        confidence: Sub-level confidence (HIGH/MEDIUM/LOW)
        value: The contract value (e.g., "owns ILogger", "requires started")
        evidence: Code evidence that led to this finding
        line: Source line number if available
        member: Member name if applicable (for ownership, etc.)
    """

    type: L4FindingType
    confidence: L4Confidence
    value: str
    evidence: str
    line: Optional[int] = None
    member: Optional[str] = None

    @property
    def confidence_score(self) -> float:
        """Return numeric confidence score."""
        return self.confidence.value

    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        result = {
            "type": self.type.value,
            "confidence": self.confidence.name,
            "confidence_score": self.confidence_score,
            "value": self.value,
            "evidence": self.evidence,
        }
        if self.line is not None:
            result["line"] = self.line
        if self.member is not None:
            result["member"] = self.member
        return result
