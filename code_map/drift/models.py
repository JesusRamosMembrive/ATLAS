# SPDX-License-Identifier: MIT
"""
Data models for drift detection.

Drift represents inconsistencies between contracts, code, and wiring
that can lead to bugs or misunderstandings.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional
import uuid


class DriftType(Enum):
    """Type of drift detected."""

    STRUCTURAL = "structural"  # Contract vs symbol signature
    WIRING = "wiring"  # Graph vs code composition
    SEMANTIC = "semantic"  # Contract claims vs implementation


class DriftSeverity(Enum):
    """Severity level of detected drift."""

    CRITICAL = "critical"  # Blocking - must fix before apply
    WARNING = "warning"  # Should review - potential issue
    INFO = "info"  # Informational - minor inconsistency


class DriftCategory(Enum):
    """Specific category of drift within each type."""

    # Structural drift categories
    SIGNATURE_CHANGED = "signature_changed"  # Method params/return type changed
    SYMBOL_DELETED = "symbol_deleted"  # Symbol referenced in contract no longer exists
    SYMBOL_ADDED = "symbol_added"  # New symbol without contract
    EVIDENCE_MISSING = "evidence_missing"  # Contract references non-existent evidence
    EVIDENCE_STALE = "evidence_stale"  # Evidence hasn't run recently
    CONTRACT_ORPHANED = "contract_orphaned"  # Contract block without associated symbol

    # Wiring drift categories
    EDGE_ADDED = "edge_added"  # New connection in composition root
    EDGE_REMOVED = "edge_removed"  # Connection removed from composition root
    INSTANCE_ADDED = "instance_added"  # New instance in composition root
    INSTANCE_REMOVED = "instance_removed"  # Instance removed from composition root
    TYPE_CHANGED = "type_changed"  # Instance type changed

    # Semantic drift categories
    THREAD_SAFETY_MISMATCH = "thread_safety_mismatch"  # Contract says safe, code is not
    PRECONDITION_UNCHECKED = (
        "precondition_unchecked"  # Precondition not validated in code
    )
    POSTCONDITION_UNMET = "postcondition_unmet"  # Postcondition not ensured
    ERROR_UNHANDLED = "error_unhandled"  # Declared error not handled


@dataclass
class DriftItem:
    """A single detected drift issue."""

    type: DriftType
    category: DriftCategory
    severity: DriftSeverity
    file_path: Path
    title: str
    description: str
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    line_number: Optional[int] = None
    symbol_name: Optional[str] = None
    suggestion: Optional[str] = None
    before_context: Optional[str] = None  # What was expected
    after_context: Optional[str] = None  # What was found
    detected_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "id": self.id,
            "type": self.type.value,
            "category": self.category.value,
            "severity": self.severity.value,
            "file_path": str(self.file_path),
            "line_number": self.line_number,
            "symbol_name": self.symbol_name,
            "title": self.title,
            "description": self.description,
            "suggestion": self.suggestion,
            "before_context": self.before_context,
            "after_context": self.after_context,
            "detected_at": self.detected_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DriftItem":
        """Create from dictionary."""
        return cls(
            id=data.get("id", str(uuid.uuid4())[:8]),
            type=DriftType(data["type"]),
            category=DriftCategory(data["category"]),
            severity=DriftSeverity(data["severity"]),
            file_path=Path(data["file_path"]),
            line_number=data.get("line_number"),
            symbol_name=data.get("symbol_name"),
            title=data["title"],
            description=data["description"],
            suggestion=data.get("suggestion"),
            before_context=data.get("before_context"),
            after_context=data.get("after_context"),
            detected_at=(
                datetime.fromisoformat(data["detected_at"])
                if "detected_at" in data
                else datetime.now(timezone.utc)
            ),
        )


@dataclass
class DriftReport:
    """Complete drift analysis report."""

    items: list[DriftItem] = field(default_factory=list)
    analyzed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    analyzed_files: list[Path] = field(default_factory=list)
    duration_ms: float = 0.0

    @property
    def has_blocking_drift(self) -> bool:
        """Check if any critical drift exists."""
        return any(item.severity == DriftSeverity.CRITICAL for item in self.items)

    @property
    def total_count(self) -> int:
        """Total number of drift items."""
        return len(self.items)

    def count_by_type(self) -> dict[str, int]:
        """Count items by drift type."""
        counts: dict[str, int] = {}
        for item in self.items:
            key = item.type.value
            counts[key] = counts.get(key, 0) + 1
        return counts

    def count_by_severity(self) -> dict[str, int]:
        """Count items by severity."""
        counts: dict[str, int] = {}
        for item in self.items:
            key = item.severity.value
            counts[key] = counts.get(key, 0) + 1
        return counts

    def filter_by_type(self, drift_type: DriftType) -> list[DriftItem]:
        """Get items of specific type."""
        return [item for item in self.items if item.type == drift_type]

    def filter_by_severity(self, severity: DriftSeverity) -> list[DriftItem]:
        """Get items of specific severity."""
        return [item for item in self.items if item.severity == severity]

    def filter_by_file(self, file_path: Path) -> list[DriftItem]:
        """Get items for specific file."""
        return [item for item in self.items if item.file_path == file_path]

    def get_blocking_items(self) -> list[DriftItem]:
        """Get all critical items that block apply."""
        return self.filter_by_severity(DriftSeverity.CRITICAL)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "items": [item.to_dict() for item in self.items],
            "analyzed_at": self.analyzed_at.isoformat(),
            "analyzed_files": [str(f) for f in self.analyzed_files],
            "duration_ms": self.duration_ms,
            "summary": {
                "total": self.total_count,
                "has_blocking": self.has_blocking_drift,
                "by_type": self.count_by_type(),
                "by_severity": self.count_by_severity(),
            },
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DriftReport":
        """Create from dictionary."""
        return cls(
            items=[DriftItem.from_dict(item) for item in data.get("items", [])],
            analyzed_at=(
                datetime.fromisoformat(data["analyzed_at"])
                if "analyzed_at" in data
                else datetime.now(timezone.utc)
            ),
            analyzed_files=[Path(f) for f in data.get("analyzed_files", [])],
            duration_ms=data.get("duration_ms", 0.0),
        )

    def format_summary(self) -> str:
        """Format a human-readable summary."""
        lines = [
            "Drift Analysis Report",
            "=====================",
            f"Analyzed at: {self.analyzed_at.strftime('%Y-%m-%d %H:%M:%S')}",
            f"Duration: {self.duration_ms:.1f}ms",
            f"Files analyzed: {len(self.analyzed_files)}",
            "",
            "Summary:",
            f"  Total items: {self.total_count}",
            f"  Blocking: {'YES' if self.has_blocking_drift else 'No'}",
            "",
        ]

        by_severity = self.count_by_severity()
        if by_severity:
            lines.append("By Severity:")
            for severity, count in sorted(by_severity.items()):
                icon = {"critical": "🔴", "warning": "🟡", "info": "🔵"}.get(
                    severity, "⚪"
                )
                lines.append(f"  {icon} {severity}: {count}")
            lines.append("")

        by_type = self.count_by_type()
        if by_type:
            lines.append("By Type:")
            for dtype, count in sorted(by_type.items()):
                lines.append(f"  - {dtype}: {count}")
            lines.append("")

        if self.has_blocking_drift:
            lines.append("BLOCKING ISSUES:")
            for item in self.get_blocking_items():
                lines.append(f"  [{item.category.value}] {item.title}")
                lines.append(f"    File: {item.file_path}:{item.line_number or '?'}")
                if item.suggestion:
                    lines.append(f"    Fix: {item.suggestion}")
            lines.append("")

        return "\n".join(lines)
