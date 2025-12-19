# SPDX-License-Identifier: MIT
"""
Tests for the evidence execution and gate checking system.
"""

import asyncio
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from code_map.contracts import ContractData, EvidenceItem, EvidencePolicy
from code_map.contracts.evidence import EvidenceExecutor, GateChecker, GateResult
from code_map.contracts.schema import EvidenceResult


# ─────────────────────────────────────────────────────────────
# EvidenceItem Tests
# ─────────────────────────────────────────────────────────────


class TestEvidenceItem:
    """Tests for EvidenceItem model."""

    def test_create_required_evidence(self):
        """Should create required evidence item."""
        item = EvidenceItem(
            type="test",
            reference="tests/test_foo.py::test_bar",
            policy=EvidencePolicy.REQUIRED,
        )
        assert item.type == "test"
        assert item.policy == EvidencePolicy.REQUIRED
        assert item.last_result is None

    def test_create_optional_evidence(self):
        """Should create optional evidence item."""
        item = EvidenceItem(
            type="lint",
            reference="ruff",
            policy=EvidencePolicy.OPTIONAL,
        )
        assert item.policy == EvidencePolicy.OPTIONAL

    def test_evidence_to_dict(self):
        """Should serialize to dict in YAML-friendly format."""
        item = EvidenceItem(
            type="typecheck",
            reference="mypy",
            policy=EvidencePolicy.REQUIRED,
        )
        data = item.to_dict()
        # Format is {type: reference, policy: value}
        assert data["typecheck"] == "mypy"
        assert data["policy"] == "required"


# ─────────────────────────────────────────────────────────────
# EvidenceExecutor Tests
# ─────────────────────────────────────────────────────────────


class TestEvidenceExecutor:
    """Tests for EvidenceExecutor."""

    @pytest.fixture
    def executor(self, tmp_path):
        """Create executor with temp project root."""
        return EvidenceExecutor(project_root=tmp_path)

    @pytest.mark.asyncio
    async def test_run_unknown_evidence_type(self, executor):
        """Unknown evidence type should fail."""
        item = EvidenceItem(
            type="unknown_type",
            reference="something",
            policy=EvidencePolicy.OPTIONAL,
        )

        result = await executor.run_evidence(item)

        assert not result.passed
        assert "Unknown evidence type" in result.output

    @pytest.mark.asyncio
    async def test_run_test_command_not_found(self, executor):
        """Missing test command should fail gracefully."""
        item = EvidenceItem(
            type="test",
            reference="tests/nonexistent.py::test_foo",
            policy=EvidencePolicy.OPTIONAL,
        )

        result = await executor.run_evidence(item)

        assert not result.passed
        assert result.duration_ms > 0

    @pytest.mark.asyncio
    async def test_run_lint_command_not_found(self, executor):
        """Missing linter should fail gracefully."""
        item = EvidenceItem(
            type="lint",
            reference="nonexistent_linter",
            policy=EvidencePolicy.OPTIONAL,
        )

        result = await executor.run_evidence(item)

        assert not result.passed
        assert "not found" in result.output.lower() or not result.passed

    @pytest.mark.asyncio
    async def test_run_contract_evidence_filters_by_scope(self, executor):
        """Should filter evidence by scope."""
        contract = ContractData(
            evidence=[
                EvidenceItem(
                    type="test", reference="test1.py", policy=EvidencePolicy.REQUIRED
                ),
                EvidenceItem(
                    type="test", reference="test2.py", policy=EvidencePolicy.OPTIONAL
                ),
                EvidenceItem(
                    type="lint", reference="ruff", policy=EvidencePolicy.REQUIRED
                ),
            ]
        )

        # Mock _run_command to avoid actual execution
        with patch.object(executor, "_run_command", new_callable=AsyncMock) as mock_cmd:
            mock_cmd.return_value = {"passed": True, "output": "OK"}

            results = await executor.run_contract_evidence(contract, scope="required")

            # Should only run required items (2 of 3)
            assert len(results) == 2
            assert mock_cmd.call_count == 2

    @pytest.mark.asyncio
    async def test_run_contract_evidence_all_scope(self, executor):
        """Scope 'all' should run all evidence."""
        contract = ContractData(
            evidence=[
                EvidenceItem(
                    type="test", reference="test1.py", policy=EvidencePolicy.REQUIRED
                ),
                EvidenceItem(
                    type="test", reference="test2.py", policy=EvidencePolicy.OPTIONAL
                ),
            ]
        )

        with patch.object(executor, "_run_command", new_callable=AsyncMock) as mock_cmd:
            mock_cmd.return_value = {"passed": True, "output": "OK"}

            results = await executor.run_contract_evidence(contract, scope="all")

            assert len(results) == 2
            assert mock_cmd.call_count == 2

    @pytest.mark.asyncio
    async def test_evidence_result_updates_item_state(self, executor):
        """Running evidence should update item's last_result."""
        item = EvidenceItem(
            type="test",
            reference="test.py",
            policy=EvidencePolicy.OPTIONAL,
        )

        assert item.last_result is None
        assert item.last_run is None

        with patch.object(executor, "_run_command", new_callable=AsyncMock) as mock_cmd:
            mock_cmd.return_value = {"passed": True, "output": "All tests passed"}

            await executor.run_evidence(item)

            assert item.last_result is True
            assert item.last_run is not None
            assert "All tests passed" in item.last_output


# ─────────────────────────────────────────────────────────────
# GateChecker Tests
# ─────────────────────────────────────────────────────────────


class TestGateChecker:
    """Tests for GateChecker."""

    @pytest.fixture
    def checker(self, tmp_path):
        """Create gate checker with temp project root."""
        return GateChecker(project_root=tmp_path)

    @pytest.mark.asyncio
    async def test_gates_pass_when_no_contracts(self, checker):
        """Empty contract list should pass gates."""
        can_proceed, result = await checker.check_gates([])

        assert can_proceed is True
        assert result.passed is True
        assert len(result.blocking_failures) == 0

    @pytest.mark.asyncio
    async def test_gates_pass_when_no_evidence(self, checker):
        """Contracts without evidence should pass gates."""
        contracts = [
            ContractData(preconditions=["x > 0"]),
            ContractData(postconditions=["result valid"]),
        ]

        can_proceed, result = await checker.check_gates(contracts)

        assert can_proceed is True
        assert result.passed is True

    @pytest.mark.asyncio
    async def test_gates_fail_on_required_failure(self, checker):
        """Required evidence failure should fail gates."""
        contract = ContractData(
            evidence=[
                EvidenceItem(
                    type="test",
                    reference="tests/critical.py::test_important",
                    policy=EvidencePolicy.REQUIRED,
                )
            ]
        )

        with patch.object(
            checker.executor, "_run_command", new_callable=AsyncMock
        ) as mock_cmd:
            mock_cmd.return_value = {"passed": False, "output": "Test failed"}

            can_proceed, result = await checker.check_gates([contract])

            assert can_proceed is False
            assert result.passed is False
            assert len(result.blocking_failures) == 1

    @pytest.mark.asyncio
    async def test_gates_pass_on_optional_failure(self, checker):
        """Optional evidence failure should not fail gates."""
        contract = ContractData(
            evidence=[
                EvidenceItem(
                    type="lint",
                    reference="ruff",
                    policy=EvidencePolicy.OPTIONAL,
                )
            ]
        )

        with patch.object(
            checker.executor, "_run_command", new_callable=AsyncMock
        ) as mock_cmd:
            mock_cmd.return_value = {"passed": False, "output": "Lint warnings"}

            can_proceed, result = await checker.check_gates([contract])

            assert can_proceed is True
            assert result.passed is True
            assert len(result.blocking_failures) == 0

    @pytest.mark.asyncio
    async def test_bypass_gates_always_succeeds(self, checker):
        """Bypass flag should always return True."""
        contract = ContractData(
            evidence=[
                EvidenceItem(
                    type="test",
                    reference="tests/critical.py",
                    policy=EvidencePolicy.REQUIRED,
                )
            ]
        )

        with patch.object(
            checker.executor, "_run_command", new_callable=AsyncMock
        ) as mock_cmd:
            mock_cmd.return_value = {"passed": False, "output": "Test failed"}

            can_proceed, result = await checker.check_gates(
                [contract], bypass_gates=True
            )

            # Should proceed despite failure
            assert can_proceed is True
            # But result still reflects actual state
            assert result.passed is False

    def test_format_gate_report_passed(self, checker):
        """Should format passing gate report."""
        result = GateResult(
            passed=True,
            results=[],
            blocking_failures=[],
            total_duration_ms=150.5,
            run_at=datetime.now(timezone.utc),
        )

        report = checker.format_gate_report(result)

        assert "PASSED" in report
        assert "150.5ms" in report

    def test_format_gate_report_failed(self, checker):
        """Should format failing gate report."""
        item = EvidenceItem(
            type="test",
            reference="tests/test_foo.py",
            policy=EvidencePolicy.REQUIRED,
        )
        failure = EvidenceResult(
            item=item,
            passed=False,
            duration_ms=50.0,
            output="AssertionError: expected 1, got 2",
            run_at=datetime.now(timezone.utc),
        )

        result = GateResult(
            passed=False,
            results=[failure],
            blocking_failures=[failure],
            total_duration_ms=50.0,
            run_at=datetime.now(timezone.utc),
        )

        report = checker.format_gate_report(result)

        assert "FAILED" in report
        assert "BLOCKING FAILURES" in report
        assert "test_foo.py" in report


# ─────────────────────────────────────────────────────────────
# EvidenceExecutor Command Tests
# ─────────────────────────────────────────────────────────────


class TestEvidenceCommands:
    """Tests for specific evidence command execution."""

    @pytest.fixture
    def executor(self, tmp_path):
        return EvidenceExecutor(project_root=tmp_path)

    @pytest.mark.asyncio
    async def test_pytest_command_format(self, executor):
        """Should format pytest command correctly."""
        with patch.object(executor, "_run_command", new_callable=AsyncMock) as mock_cmd:
            mock_cmd.return_value = {"passed": True, "output": ""}

            item = EvidenceItem(
                type="test",
                reference="tests/test_foo.py::test_bar",
                policy=EvidencePolicy.REQUIRED,
            )
            await executor.run_evidence(item)

            # Check command format
            call_args = mock_cmd.call_args[0][0]
            assert "pytest" in call_args
            assert "tests/test_foo.py" in call_args
            assert "-k" in call_args
            assert "test_bar" in call_args

    @pytest.mark.asyncio
    async def test_ruff_command_format(self, executor):
        """Should format ruff command correctly."""
        with patch.object(executor, "_run_command", new_callable=AsyncMock) as mock_cmd:
            mock_cmd.return_value = {"passed": True, "output": ""}

            item = EvidenceItem(
                type="lint",
                reference="ruff",
                policy=EvidencePolicy.OPTIONAL,
            )
            await executor.run_evidence(item)

            call_args = mock_cmd.call_args[0][0]
            assert "ruff" in call_args
            assert "check" in call_args

    @pytest.mark.asyncio
    async def test_mypy_typecheck_command(self, executor):
        """Should format mypy command correctly."""
        with patch.object(executor, "_run_command", new_callable=AsyncMock) as mock_cmd:
            mock_cmd.return_value = {"passed": True, "output": ""}

            item = EvidenceItem(
                type="typecheck",
                reference="mypy",
                policy=EvidencePolicy.REQUIRED,
            )
            await executor.run_evidence(item)

            call_args = mock_cmd.call_args[0][0]
            assert "mypy" in call_args


# ─────────────────────────────────────────────────────────────
# Integration Tests
# ─────────────────────────────────────────────────────────────


class TestEvidenceIntegration:
    """Integration tests for evidence system."""

    @pytest.mark.asyncio
    async def test_multiple_contracts_gate_check(self, tmp_path):
        """Should check gates across multiple contracts."""
        contracts = [
            ContractData(
                evidence=[
                    EvidenceItem(
                        type="test",
                        reference="test1.py",
                        policy=EvidencePolicy.REQUIRED,
                    ),
                ]
            ),
            ContractData(
                evidence=[
                    EvidenceItem(
                        type="test",
                        reference="test2.py",
                        policy=EvidencePolicy.REQUIRED,
                    ),
                    EvidenceItem(
                        type="lint",
                        reference="ruff",
                        policy=EvidencePolicy.OPTIONAL,
                    ),
                ]
            ),
        ]

        checker = GateChecker(project_root=tmp_path)

        with patch.object(
            checker.executor, "_run_command", new_callable=AsyncMock
        ) as mock_cmd:
            # All pass
            mock_cmd.return_value = {"passed": True, "output": "OK"}

            can_proceed, result = await checker.check_gates(contracts)

            assert can_proceed is True
            assert result.passed is True
            # Only required items: 2 (test1.py and test2.py)
            assert mock_cmd.call_count == 2

    @pytest.mark.asyncio
    async def test_mixed_results_gate_check(self, tmp_path):
        """Mixed results should fail if any required fails."""
        contract = ContractData(
            evidence=[
                EvidenceItem(
                    type="test",
                    reference="test1.py",
                    policy=EvidencePolicy.REQUIRED,
                ),
                EvidenceItem(
                    type="test",
                    reference="test2.py",
                    policy=EvidencePolicy.REQUIRED,
                ),
            ]
        )

        checker = GateChecker(project_root=tmp_path)

        call_count = 0

        async def mixed_results(cmd, timeout=300.0):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return {"passed": True, "output": "OK"}
            return {"passed": False, "output": "Failed"}

        with patch.object(checker.executor, "_run_command", side_effect=mixed_results):
            can_proceed, result = await checker.check_gates([contract])

            assert can_proceed is False
            assert result.passed is False
            assert len(result.blocking_failures) == 1

    @pytest.mark.asyncio
    async def test_gate_result_timing(self, tmp_path):
        """Gate result should track total duration."""
        contract = ContractData(
            evidence=[
                EvidenceItem(
                    type="test",
                    reference="test.py",
                    policy=EvidencePolicy.REQUIRED,
                ),
            ]
        )

        checker = GateChecker(project_root=tmp_path)

        async def slow_command(cmd, timeout=300.0):
            await asyncio.sleep(0.1)  # 100ms
            return {"passed": True, "output": "OK"}

        with patch.object(checker.executor, "_run_command", side_effect=slow_command):
            _, result = await checker.check_gates([contract])

            # Should be at least 100ms
            assert result.total_duration_ms >= 100
