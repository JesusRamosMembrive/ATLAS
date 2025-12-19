# SPDX-License-Identifier: MIT
"""
API endpoints for contract discovery, writing, and gate validation.

Provides REST interface for AEGIS v2 contract system.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..contracts import (
    ContractData,
    ContractDiscovery,
    ContractRewriter,
    DocumentationType,
    EvidenceItem,
    EvidencePolicy,
    ThreadSafety,
)
from ..contracts.evidence import EvidenceExecutor, GateChecker
from ..state import AppState
from .deps import get_app_state

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/contracts", tags=["contracts"])


# ─────────────────────────────────────────────────────────────
# Request/Response Models
# ─────────────────────────────────────────────────────────────


class EvidenceItemModel(BaseModel):
    """Evidence item for API."""

    type: str
    reference: str
    policy: str = "optional"


class ContractModel(BaseModel):
    """Contract data for API."""

    thread_safety: Optional[str] = None
    lifecycle: Optional[str] = None
    invariants: List[str] = Field(default_factory=list)
    preconditions: List[str] = Field(default_factory=list)
    postconditions: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    dependencies: List[str] = Field(default_factory=list)
    evidence: List[EvidenceItemModel] = Field(default_factory=list)

    def to_contract_data(self) -> ContractData:
        """Convert to internal ContractData."""
        contract = ContractData()

        if self.thread_safety:
            try:
                contract.thread_safety = ThreadSafety(self.thread_safety)
            except ValueError:
                pass

        contract.lifecycle = self.lifecycle
        contract.invariants = self.invariants
        contract.preconditions = self.preconditions
        contract.postconditions = self.postconditions
        contract.errors = self.errors
        contract.dependencies = self.dependencies

        for ev in self.evidence:
            try:
                policy = EvidencePolicy(ev.policy)
            except ValueError:
                policy = EvidencePolicy.OPTIONAL

            contract.evidence.append(
                EvidenceItem(type=ev.type, reference=ev.reference, policy=policy)
            )

        return contract


class DiscoverRequest(BaseModel):
    """Request to discover contracts."""

    file_path: str
    symbol_line: Optional[int] = None
    levels: Optional[List[int]] = None


class DiscoverResponse(BaseModel):
    """Response from contract discovery."""

    contracts: List[Dict[str, Any]]
    stats: Dict[str, int]
    # New fields for interactive flow
    documentation_type: Optional[str] = None  # aegis, doxygen, comment, none
    warning: Optional[str] = None  # no_documentation_found, etc.
    llm_available: bool = False


class WriteRequest(BaseModel):
    """Request to write a contract."""

    file_path: str
    symbol_line: int
    contract: ContractModel


class WriteResponse(BaseModel):
    """Response from writing a contract."""

    success: bool
    diff: str
    warnings: List[str] = Field(default_factory=list)


class ValidateRequest(BaseModel):
    """Request to validate contract evidence."""

    file_path: str
    symbol_line: int


class ValidateResponse(BaseModel):
    """Response from validating a contract."""

    contract: Dict[str, Any]
    evidence_status: List[Dict[str, Any]]


class GatesRunRequest(BaseModel):
    """Request to run gates."""

    symbols: List[Dict[str, Any]]  # [{file_path, symbol_line}, ...]
    scope: str = "required"


class GatesRunResponse(BaseModel):
    """Response from running gates."""

    passed: bool
    results: List[Dict[str, Any]]
    blocking_failures: List[Dict[str, Any]]
    duration_ms: float


# ─────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────


@router.post("/discover", response_model=DiscoverResponse)
async def discover_contracts(
    request: DiscoverRequest,
    state: AppState = Depends(get_app_state),
) -> DiscoverResponse:
    """
    Discover contracts in a file.

    Runs the multi-level discovery pipeline to find contracts
    embedded in code comments and documentation.

    The response includes:
    - documentation_type: What kind of docs were found (aegis, doxygen, comment, none)
    - warning: Set to "no_documentation_found" if no structured docs exist
    - llm_available: Whether Ollama is available for L3 extraction
    - contracts: The discovered contracts (may be empty if user needs to choose method)
    """
    file_path = Path(request.file_path)

    if not file_path.is_absolute():
        file_path = state.settings.root_path / file_path

    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")

    if not request.symbol_line:
        raise HTTPException(
            status_code=400,
            detail="symbol_line is required (full-file scan not yet implemented)",
        )

    logger.info(
        "[DEBUG] /contracts/discover: file=%s, symbol_line=%d",
        file_path,
        request.symbol_line,
    )

    discovery = ContractDiscovery(enable_llm=True)

    # Quick scan to detect documentation type
    doc_type = discovery.quick_scan(file_path, request.symbol_line)
    logger.info("[DEBUG] quick_scan result: %s", doc_type)
    llm_available = discovery.is_llm_available()

    # Determine what levels to try based on documentation type
    if doc_type == DocumentationType.NONE:
        # No documentation found - return warning, let UI decide
        # Only run static analysis (L4) if explicitly requested
        if request.levels and (3 in request.levels or 4 in request.levels):
            # User explicitly requested L3/L4
            contract = await discovery.discover_async(
                file_path, request.symbol_line, request.levels
            )
            contracts = [contract.to_dict()]
            stats = {f"level_{contract.source_level}_found": 1, "total_symbols": 1}
        else:
            # Return empty with warning - UI will show options
            contracts = []
            stats = {"total_symbols": 1, "level_5_found": 1}

        return DiscoverResponse(
            contracts=contracts,
            stats=stats,
            documentation_type=doc_type.value,
            warning="no_documentation_found",
            llm_available=llm_available,
        )

    elif doc_type == DocumentationType.GENERIC_COMMENT:
        # Has comment but no structured contract
        # Still try L3/L4 if available, but warn user
        if request.levels:
            levels_to_try = request.levels
        else:
            # Default: skip L1/L2 (won't find anything), try L3/L4
            levels_to_try = [3, 4] if llm_available else [4]

        contract = await discovery.discover_async(
            file_path, request.symbol_line, levels_to_try
        )
        contracts = [contract.to_dict()]
        stats = {f"level_{contract.source_level}_found": 1, "total_symbols": 1}

        return DiscoverResponse(
            contracts=contracts,
            stats=stats,
            documentation_type=doc_type.value,
            warning="no_structured_documentation",
            llm_available=llm_available,
        )

    else:
        # Has structured documentation (AEGIS_CONTRACT or DOXYGEN)
        # Run normal discovery
        contract = await discovery.discover_async(
            file_path, request.symbol_line, request.levels
        )
        contracts = [contract.to_dict()]
        stats = {f"level_{contract.source_level}_found": 1, "total_symbols": 1}

        return DiscoverResponse(
            contracts=contracts,
            stats=stats,
            documentation_type=doc_type.value,
            llm_available=llm_available,
        )


@router.post("/write", response_model=WriteResponse)
async def write_contract(
    request: WriteRequest,
    state: AppState = Depends(get_app_state),
) -> WriteResponse:
    """
    Write a contract to a source file.

    Creates or updates an @aegis-contract block at the specified location.
    """
    file_path = Path(request.file_path)

    if not file_path.is_absolute():
        file_path = state.settings.root_path / file_path

    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")

    rewriter = ContractRewriter()
    contract = request.contract.to_contract_data()

    try:
        diff = rewriter.apply_contract(file_path, request.symbol_line, contract)
        return WriteResponse(success=True, diff=diff)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to write contract: {e}")


@router.post("/preview", response_model=WriteResponse)
async def preview_contract(
    request: WriteRequest,
    state: AppState = Depends(get_app_state),
) -> WriteResponse:
    """
    Preview contract changes without applying them.

    Returns the diff that would be generated.
    """
    file_path = Path(request.file_path)

    if not file_path.is_absolute():
        file_path = state.settings.root_path / file_path

    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")

    rewriter = ContractRewriter()
    contract = request.contract.to_contract_data()

    try:
        diff = rewriter.preview_contract(file_path, request.symbol_line, contract)
        return WriteResponse(success=True, diff=diff)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/validate", response_model=ValidateResponse)
async def validate_contract(
    request: ValidateRequest,
    state: AppState = Depends(get_app_state),
) -> ValidateResponse:
    """
    Validate a contract's evidence.

    Runs all evidence items and returns their status.
    """
    file_path = Path(request.file_path)

    if not file_path.is_absolute():
        file_path = state.settings.root_path / file_path

    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")

    # Discover contract first
    discovery = ContractDiscovery(enable_llm=False)
    contract = discovery.discover(file_path, request.symbol_line)

    if contract.is_empty():
        raise HTTPException(
            status_code=404,
            detail=f"No contract found at {file_path}:{request.symbol_line}",
        )

    # Run evidence
    executor = EvidenceExecutor(state.settings.root_path)
    results = await executor.run_contract_evidence(contract, scope="all")

    evidence_status = []
    for result in results:
        evidence_status.append(
            {
                "type": result.item.type,
                "reference": result.item.reference,
                "policy": result.item.policy.value,
                "passed": result.passed,
                "duration_ms": result.duration_ms,
                "output": result.output[:500],  # Truncate
            }
        )

    return ValidateResponse(
        contract=contract.to_dict(), evidence_status=evidence_status
    )


@router.post("/gates/run", response_model=GatesRunResponse)
async def run_gates(
    request: GatesRunRequest,
    state: AppState = Depends(get_app_state),
) -> GatesRunResponse:
    """
    Run gates for multiple symbols.

    Validates that all required evidence passes before allowing changes.
    """
    # Discover contracts for all symbols
    discovery = ContractDiscovery(enable_llm=False)
    contracts = []

    for symbol in request.symbols:
        file_path = Path(symbol["file_path"])
        if not file_path.is_absolute():
            file_path = state.settings.root_path / file_path

        if file_path.exists():
            contract = discovery.discover(file_path, symbol["symbol_line"])
            if not contract.is_empty():
                contracts.append(contract)

    if not contracts:
        # No contracts to validate = gates pass
        return GatesRunResponse(
            passed=True, results=[], blocking_failures=[], duration_ms=0
        )

    # Run gates
    checker = GateChecker(state.settings.root_path)
    _, gate_result = await checker.check_gates(contracts)

    return GatesRunResponse(
        passed=gate_result.passed,
        results=[r.to_dict() for r in gate_result.results],
        blocking_failures=[r.to_dict() for r in gate_result.blocking_failures],
        duration_ms=gate_result.total_duration_ms,
    )


@router.get("/languages")
async def list_supported_languages() -> Dict[str, Any]:
    """
    List supported languages for contract discovery.
    """
    from ..contracts.languages.registry import LanguageRegistry

    return {
        "languages": LanguageRegistry.supported_languages(),
        "extensions": LanguageRegistry.supported_extensions(),
    }
