# SPDX-License-Identifier: MIT
"""
Contract system for AEGIS v2.

Provides contract discovery, parsing, and rewriting for embedded code contracts.
Supports multiple languages through the Strategy pattern.
"""

from .schema import (
    ContractData,
    EvidenceItem,
    EvidencePolicy,
    EvidenceResult,
    ThreadSafety,
)
from .discovery import ContractDiscovery, DiscoveryStats, DocumentationType
from .rewriter import ContractRewriter

# Import language strategies to trigger registration
from .languages import cpp, python  # noqa: F401

__all__ = [
    # Schema
    "ContractData",
    "EvidenceItem",
    "EvidencePolicy",
    "EvidenceResult",
    "ThreadSafety",
    # Discovery
    "ContractDiscovery",
    "DiscoveryStats",
    "DocumentationType",
    # Rewriter
    "ContractRewriter",
]
