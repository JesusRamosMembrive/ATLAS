# SPDX-License-Identifier: MIT
"""
Contract data models for AEGIS v2.

Defines the schema for embedded contracts including:
- Thread safety annotations
- Lifecycle definitions
- Invariants, preconditions, postconditions
- Evidence references and policies
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


class ThreadSafety(Enum):
    """Thread safety level for a component."""

    NOT_SAFE = "not_safe"
    SAFE = "safe"
    SAFE_AFTER_START = "safe_after_start"
    IMMUTABLE = "immutable"
    UNKNOWN = "unknown"


class EvidencePolicy(Enum):
    """Policy for contract evidence."""

    REQUIRED = "required"  # Blocking - must pass
    OPTIONAL = "optional"  # Informative only
    WARNING = "warning"  # Warn but don't block


@dataclass
class EvidenceItem:
    """Reference to evidence that backs a contract."""

    type: str  # 'test', 'lint', 'typecheck'
    reference: str  # path::test_name or tool_name
    policy: EvidencePolicy = EvidencePolicy.OPTIONAL

    # Runtime state (not persisted in contract)
    last_result: Optional[bool] = None
    last_run: Optional[datetime] = None
    last_output: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for YAML embedding."""
        result: Dict[str, Any] = {
            self.type: self.reference,
        }
        if self.policy != EvidencePolicy.OPTIONAL:
            result["policy"] = self.policy.value
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EvidenceItem":
        """Deserialize from dictionary."""
        # Determine type from key
        ev_type = None
        reference = None
        for key in ("test", "lint", "typecheck"):
            if key in data:
                ev_type = key
                reference = data[key]
                break

        if ev_type is None or reference is None:
            raise ValueError(f"Invalid evidence item: {data}")

        policy_str = data.get("policy", "optional")
        policy = EvidencePolicy(policy_str)

        return cls(type=ev_type, reference=reference, policy=policy)


@dataclass
class EvidenceResult:
    """Result of running evidence for a contract."""

    item: EvidenceItem
    passed: bool
    duration_ms: float
    output: str
    run_at: datetime

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "type": self.item.type,
            "reference": self.item.reference,
            "policy": self.item.policy.value,
            "passed": self.passed,
            "duration_ms": self.duration_ms,
            "output": self.output,
            "run_at": self.run_at.isoformat(),
        }


@dataclass
class ContractData:
    """
    Contract extracted or defined for a symbol.

    Contains both the contract content and metadata about extraction.
    """

    # Contract content
    thread_safety: Optional[ThreadSafety] = None
    lifecycle: Optional[str] = None  # e.g., "stopped -> running -> stopped"
    invariants: List[str] = field(default_factory=list)
    preconditions: List[str] = field(default_factory=list)
    postconditions: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    evidence: List[EvidenceItem] = field(default_factory=list)

    # Extraction metadata
    confidence: float = 1.0  # 0.0 - 1.0
    source_level: int = 0  # 1-5 (pipeline level that found it)
    needs_review: bool = False  # True if LLM-extracted
    inferred: bool = False  # True if from static analysis
    confidence_notes: Optional[str] = None

    # Location in code
    file_path: Optional[Path] = None
    start_line: Optional[int] = None
    end_line: Optional[int] = None

    def is_empty(self) -> bool:
        """Return True if no meaningful content exists."""
        return not any(
            [
                self.thread_safety,
                self.lifecycle,
                self.invariants,
                self.preconditions,
                self.postconditions,
                self.errors,
                self.evidence,
            ]
        )

    def has_required_evidence(self) -> bool:
        """Return True if all required evidence is present and passing."""
        required = [e for e in self.evidence if e.policy == EvidencePolicy.REQUIRED]
        return all(e.last_result is True for e in required)

    def get_failing_required(self) -> List[EvidenceItem]:
        """Get list of required evidence items that are failing or not run."""
        return [
            e
            for e in self.evidence
            if e.policy == EvidencePolicy.REQUIRED and e.last_result is not True
        ]

    def to_yaml(self) -> str:
        """Serialize contract content to YAML string."""
        data: Dict[str, Any] = {}

        if self.thread_safety:
            data["thread_safety"] = self.thread_safety.value

        if self.lifecycle:
            data["lifecycle"] = self.lifecycle

        if self.invariants:
            data["invariants"] = self.invariants

        if self.preconditions:
            data["preconditions"] = self.preconditions

        if self.postconditions:
            data["postconditions"] = self.postconditions

        if self.errors:
            data["errors"] = self.errors

        if self.dependencies:
            data["dependencies"] = self.dependencies

        if self.evidence:
            data["evidence"] = [e.to_dict() for e in self.evidence]

        return yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True)

    @classmethod
    def from_yaml(cls, yaml_content: str) -> "ContractData":
        """Deserialize from YAML string."""
        try:
            data = yaml.safe_load(yaml_content)
        except yaml.YAMLError:
            return cls(confidence=0.0, confidence_notes="Invalid YAML")

        if not data or not isinstance(data, dict):
            return cls(confidence=0.0, confidence_notes="Empty or invalid contract")

        contract = cls()

        # Thread safety
        if "thread_safety" in data:
            try:
                contract.thread_safety = ThreadSafety(data["thread_safety"])
            except ValueError:
                contract.thread_safety = ThreadSafety.UNKNOWN

        # Lifecycle
        contract.lifecycle = data.get("lifecycle")

        # Lists
        contract.invariants = data.get("invariants", [])
        contract.preconditions = data.get("preconditions", [])
        contract.postconditions = data.get("postconditions", [])
        contract.errors = data.get("errors", [])
        contract.dependencies = data.get("dependencies", [])

        # Evidence
        if "evidence" in data:
            for ev_data in data["evidence"]:
                try:
                    contract.evidence.append(EvidenceItem.from_dict(ev_data))
                except (ValueError, KeyError):
                    pass  # Skip invalid evidence items

        return contract

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary including metadata."""
        result: Dict[str, Any] = {
            "confidence": self.confidence,
            "source_level": self.source_level,
            "needs_review": self.needs_review,
            "inferred": self.inferred,
        }

        if self.thread_safety:
            result["thread_safety"] = self.thread_safety.value
        if self.lifecycle:
            result["lifecycle"] = self.lifecycle
        if self.invariants:
            result["invariants"] = self.invariants
        if self.preconditions:
            result["preconditions"] = self.preconditions
        if self.postconditions:
            result["postconditions"] = self.postconditions
        if self.errors:
            result["errors"] = self.errors
        if self.dependencies:
            result["dependencies"] = self.dependencies
        if self.evidence:
            result["evidence"] = [e.to_dict() for e in self.evidence]
        if self.confidence_notes:
            result["confidence_notes"] = self.confidence_notes
        if self.file_path:
            result["file_path"] = str(self.file_path)
        if self.start_line:
            result["start_line"] = self.start_line
        if self.end_line:
            result["end_line"] = self.end_line

        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ContractData":
        """Deserialize from dictionary."""
        contract = cls()

        # Metadata
        contract.confidence = data.get("confidence", 1.0)
        contract.source_level = data.get("source_level", 0)
        contract.needs_review = data.get("needs_review", False)
        contract.inferred = data.get("inferred", False)
        contract.confidence_notes = data.get("confidence_notes")

        # Thread safety
        if "thread_safety" in data:
            try:
                contract.thread_safety = ThreadSafety(data["thread_safety"])
            except ValueError:
                contract.thread_safety = ThreadSafety.UNKNOWN

        # Simple fields
        contract.lifecycle = data.get("lifecycle")
        contract.invariants = data.get("invariants", [])
        contract.preconditions = data.get("preconditions", [])
        contract.postconditions = data.get("postconditions", [])
        contract.errors = data.get("errors", [])
        contract.dependencies = data.get("dependencies", [])

        # Evidence
        if "evidence" in data:
            for ev_data in data["evidence"]:
                try:
                    contract.evidence.append(EvidenceItem.from_dict(ev_data))
                except (ValueError, KeyError):
                    pass

        # Location
        if "file_path" in data:
            contract.file_path = Path(data["file_path"])
        contract.start_line = data.get("start_line")
        contract.end_line = data.get("end_line")

        return contract
