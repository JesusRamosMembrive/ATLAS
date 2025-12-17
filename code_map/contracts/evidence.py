# SPDX-License-Identifier: MIT
"""
Evidence execution for contract verification.

Runs tests, linters, and type checkers as evidence to back contracts.
"""

import asyncio
import logging
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .schema import ContractData, EvidenceItem, EvidencePolicy, EvidenceResult

logger = logging.getLogger(__name__)


@dataclass
class GateResult:
    """Result of running all gates for a set of contracts."""

    passed: bool
    results: List[EvidenceResult]
    blocking_failures: List[EvidenceResult]
    total_duration_ms: float
    run_at: datetime


class EvidenceExecutor:
    """
    Executes evidence items (tests, lints) for contracts.

    Integrates with existing linter pipeline and test frameworks.
    """

    def __init__(self, project_root: Optional[Path] = None):
        """
        Initialize the executor.

        Args:
            project_root: Root directory of the project for running commands
        """
        self.project_root = project_root or Path.cwd()
        self._linter_pipeline = None

    async def run_evidence(self, item: EvidenceItem) -> EvidenceResult:
        """
        Run a single evidence item.

        Args:
            item: Evidence item to execute

        Returns:
            EvidenceResult with pass/fail status
        """
        start_time = time.perf_counter()

        if item.type == "test":
            result = await self._run_test(item.reference)
        elif item.type == "lint":
            result = await self._run_lint(item.reference)
        elif item.type == "typecheck":
            result = await self._run_typecheck(item.reference)
        else:
            result = {
                "passed": False,
                "output": f"Unknown evidence type: {item.type}",
            }

        duration_ms = (time.perf_counter() - start_time) * 1000

        evidence_result = EvidenceResult(
            item=item,
            passed=result["passed"],
            duration_ms=duration_ms,
            output=result.get("output", ""),
            run_at=datetime.now(timezone.utc),
        )

        # Update the item's runtime state
        item.last_result = evidence_result.passed
        item.last_run = evidence_result.run_at
        item.last_output = evidence_result.output[:1000]  # Truncate

        return evidence_result

    async def run_contract_evidence(
        self, contract: ContractData, scope: str = "required"
    ) -> List[EvidenceResult]:
        """
        Run all evidence items for a contract.

        Args:
            contract: Contract with evidence items
            scope: "required" to run only required, "all" for everything

        Returns:
            List of evidence results
        """
        evidence_items = contract.evidence

        if scope == "required":
            evidence_items = [
                e for e in evidence_items if e.policy == EvidencePolicy.REQUIRED
            ]

        results = []
        for item in evidence_items:
            result = await self.run_evidence(item)
            results.append(result)

        return results

    async def run_gates(
        self,
        contracts: List[ContractData],
        scope: str = "required",
    ) -> GateResult:
        """
        Run gates for multiple contracts.

        Args:
            contracts: List of contracts to validate
            scope: "required" or "all"

        Returns:
            GateResult with overall pass/fail and details
        """
        start_time = time.perf_counter()
        all_results: List[EvidenceResult] = []
        blocking_failures: List[EvidenceResult] = []

        for contract in contracts:
            results = await self.run_contract_evidence(contract, scope)
            all_results.extend(results)

            # Track blocking failures
            for result in results:
                if not result.passed and result.item.policy == EvidencePolicy.REQUIRED:
                    blocking_failures.append(result)

        total_duration = (time.perf_counter() - start_time) * 1000

        return GateResult(
            passed=len(blocking_failures) == 0,
            results=all_results,
            blocking_failures=blocking_failures,
            total_duration_ms=total_duration,
            run_at=datetime.now(timezone.utc),
        )

    # ─────────────────────────────────────────────────────────────
    # Test execution
    # ─────────────────────────────────────────────────────────────

    async def _run_test(self, reference: str) -> Dict[str, Any]:
        """
        Run a specific test.

        Reference format: "path/to/test_file.py::test_name"
        or "path/to/test_file.cpp::TestClassName"
        """
        # Parse reference
        if "::" in reference:
            file_path, test_name = reference.rsplit("::", 1)
        else:
            file_path = reference
            test_name = None

        # Determine test framework by extension
        if file_path.endswith(".py"):
            return await self._run_pytest(file_path, test_name)
        elif file_path.endswith((".cpp", ".cc", ".cxx")):
            return await self._run_ctest(test_name)
        else:
            return {
                "passed": False,
                "output": f"Unknown test file type: {file_path}",
            }

    async def _run_pytest(
        self, file_path: str, test_name: Optional[str]
    ) -> Dict[str, Any]:
        """Run pytest for Python tests."""
        cmd = ["pytest", file_path, "-v", "--tb=short"]
        if test_name:
            cmd.extend(["-k", test_name])

        return await self._run_command(cmd)

    async def _run_ctest(self, test_name: Optional[str]) -> Dict[str, Any]:
        """Run ctest for C++ tests."""
        cmd = ["ctest", "-V"]
        if test_name:
            cmd.extend(["-R", test_name])

        return await self._run_command(cmd)

    # ─────────────────────────────────────────────────────────────
    # Lint execution
    # ─────────────────────────────────────────────────────────────

    async def _run_lint(self, reference: str) -> Dict[str, Any]:
        """
        Run a linter.

        Reference is the linter name: "ruff", "clang-tidy", "mypy", etc.
        """
        linter = reference.lower()

        if linter == "ruff":
            return await self._run_command(["ruff", "check", str(self.project_root)])
        elif linter == "clang-tidy":
            # Assumes compile_commands.json exists
            return await self._run_command(
                ["clang-tidy", "-p", str(self.project_root)]
            )
        elif linter == "mypy":
            return await self._run_command(["mypy", str(self.project_root)])
        elif linter == "eslint":
            return await self._run_command(["eslint", str(self.project_root)])
        else:
            # Try to run the linter as-is
            return await self._run_command([linter, str(self.project_root)])

    # ─────────────────────────────────────────────────────────────
    # Typecheck execution
    # ─────────────────────────────────────────────────────────────

    async def _run_typecheck(self, reference: str) -> Dict[str, Any]:
        """
        Run type checker.

        Reference is the tool name: "mypy", "pyright", "tsc", etc.
        """
        tool = reference.lower()

        if tool in ("mypy", "pyright"):
            return await self._run_command([tool, str(self.project_root)])
        elif tool == "tsc":
            return await self._run_command(["tsc", "--noEmit"])
        else:
            return await self._run_command([tool, str(self.project_root)])

    # ─────────────────────────────────────────────────────────────
    # Command execution
    # ─────────────────────────────────────────────────────────────

    async def _run_command(
        self, cmd: List[str], timeout: float = 300.0
    ) -> Dict[str, Any]:
        """Run a shell command and capture output."""
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(self.project_root),
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), timeout=timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                return {
                    "passed": False,
                    "output": f"Command timed out after {timeout}s: {' '.join(cmd)}",
                }

            output = stdout.decode("utf-8", errors="replace")
            if stderr:
                output += "\n" + stderr.decode("utf-8", errors="replace")

            return {
                "passed": process.returncode == 0,
                "output": output,
            }

        except FileNotFoundError:
            return {
                "passed": False,
                "output": f"Command not found: {cmd[0]}",
            }
        except Exception as e:
            return {
                "passed": False,
                "output": f"Error running command: {e}",
            }


class GateChecker:
    """
    High-level gate checking for applying patches.

    Ensures contracts are satisfied before allowing changes.
    """

    def __init__(self, project_root: Optional[Path] = None):
        """Initialize the gate checker."""
        self.executor = EvidenceExecutor(project_root)

    async def check_gates(
        self,
        contracts: List[ContractData],
        bypass_gates: bool = False,
    ) -> tuple[bool, GateResult]:
        """
        Check if gates pass for a set of contracts.

        Args:
            contracts: Contracts to validate
            bypass_gates: If True, always return True (for emergencies)

        Returns:
            Tuple of (can_proceed, gate_result)
        """
        result = await self.executor.run_gates(contracts, scope="required")

        if bypass_gates:
            logger.warning("Gates bypassed by user request")
            return True, result

        return result.passed, result

    def format_gate_report(self, result: GateResult) -> str:
        """Format gate result as human-readable report."""
        lines = [
            "=" * 50,
            "GATE CHECK REPORT",
            "=" * 50,
            f"Status: {'✅ PASSED' if result.passed else '❌ FAILED'}",
            f"Duration: {result.total_duration_ms:.1f}ms",
            f"Run at: {result.run_at.isoformat()}",
            "",
        ]

        if result.blocking_failures:
            lines.append("BLOCKING FAILURES:")
            lines.append("-" * 30)
            for failure in result.blocking_failures:
                lines.append(f"  ❌ {failure.item.type}: {failure.item.reference}")
                if failure.output:
                    # Show first 200 chars of output
                    output_preview = failure.output[:200].replace("\n", " ")
                    lines.append(f"     {output_preview}...")
            lines.append("")

        if result.passed:
            lines.append(f"All {len(result.results)} evidence items passed.")
        else:
            passing = len([r for r in result.results if r.passed])
            lines.append(f"{passing}/{len(result.results)} evidence items passed.")
            lines.append("")
            lines.append("⚠️ Cannot apply changes until all required gates pass.")

        lines.append("=" * 50)
        return "\n".join(lines)
