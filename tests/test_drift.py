# SPDX-License-Identifier: MIT
"""
Tests for the drift detection system.
"""

import pytest
from pathlib import Path
from textwrap import dedent

from code_map.drift import (
    DriftType,
    DriftCategory,
    DriftSeverity,
    DriftItem,
    DriftReport,
    DriftAnalyzer,
    StructuralDriftDetector,
    WiringDriftDetector,
    SemanticDriftDetector,
)
from code_map.drift.detectors import DriftContext


# ─────────────────────────────────────────────────────────────
# DriftItem Tests
# ─────────────────────────────────────────────────────────────


class TestDriftItem:
    """Tests for DriftItem model."""

    def test_create_drift_item(self):
        """Should create a drift item with required fields."""
        item = DriftItem(
            type=DriftType.STRUCTURAL,
            category=DriftCategory.SIGNATURE_CHANGED,
            severity=DriftSeverity.WARNING,
            file_path=Path("src/module.py"),
            title="Function signature changed",
            description="The function 'process' signature has changed",
        )

        assert item.type == DriftType.STRUCTURAL
        assert item.category == DriftCategory.SIGNATURE_CHANGED
        assert item.severity == DriftSeverity.WARNING
        assert item.title == "Function signature changed"
        assert item.id is not None  # Auto-generated

    def test_drift_item_to_dict(self):
        """Should serialize to dict for JSON."""
        item = DriftItem(
            type=DriftType.WIRING,
            category=DriftCategory.EDGE_REMOVED,
            severity=DriftSeverity.CRITICAL,
            file_path=Path("main.cpp"),
            line_number=42,
            symbol_name="m1",
            title="Connection removed",
            description="Edge from m1 to m2 was removed",
            suggestion="Verify this was intentional",
        )

        data = item.to_dict()

        assert data["type"] == "wiring"
        assert data["category"] == "edge_removed"
        assert data["severity"] == "critical"
        assert data["file_path"] == "main.cpp"
        assert data["line_number"] == 42
        assert data["symbol_name"] == "m1"
        assert data["suggestion"] == "Verify this was intentional"

    def test_drift_item_from_dict(self):
        """Should deserialize from dict."""
        data = {
            "id": "abc123",
            "type": "semantic",
            "category": "thread_safety_mismatch",
            "severity": "warning",
            "file_path": "handler.py",
            "title": "Thread safety issue",
            "description": "Contract claims safe but no locks found",
            "detected_at": "2025-12-15T10:30:00+00:00",
        }

        item = DriftItem.from_dict(data)

        assert item.id == "abc123"
        assert item.type == DriftType.SEMANTIC
        assert item.category == DriftCategory.THREAD_SAFETY_MISMATCH
        assert item.severity == DriftSeverity.WARNING


# ─────────────────────────────────────────────────────────────
# DriftReport Tests
# ─────────────────────────────────────────────────────────────


class TestDriftReport:
    """Tests for DriftReport model."""

    def test_empty_report(self):
        """Empty report should have no blocking drift."""
        report = DriftReport()

        assert report.total_count == 0
        assert not report.has_blocking_drift
        assert report.count_by_type() == {}
        assert report.count_by_severity() == {}

    def test_report_with_items(self):
        """Report should correctly count and categorize items."""
        items = [
            DriftItem(
                type=DriftType.STRUCTURAL,
                category=DriftCategory.EVIDENCE_MISSING,
                severity=DriftSeverity.WARNING,
                file_path=Path("a.py"),
                title="Test 1",
                description="Desc 1",
            ),
            DriftItem(
                type=DriftType.STRUCTURAL,
                category=DriftCategory.SIGNATURE_CHANGED,
                severity=DriftSeverity.CRITICAL,
                file_path=Path("b.py"),
                title="Test 2",
                description="Desc 2",
            ),
            DriftItem(
                type=DriftType.WIRING,
                category=DriftCategory.EDGE_ADDED,
                severity=DriftSeverity.INFO,
                file_path=Path("c.cpp"),
                title="Test 3",
                description="Desc 3",
            ),
        ]

        report = DriftReport(items=items)

        assert report.total_count == 3
        assert report.has_blocking_drift  # Has CRITICAL item
        assert report.count_by_type() == {"structural": 2, "wiring": 1}
        assert report.count_by_severity() == {"warning": 1, "critical": 1, "info": 1}

    def test_filter_by_type(self):
        """Should filter items by drift type."""
        items = [
            DriftItem(
                type=DriftType.STRUCTURAL,
                category=DriftCategory.EVIDENCE_MISSING,
                severity=DriftSeverity.WARNING,
                file_path=Path("a.py"),
                title="Structural",
                description="Desc",
            ),
            DriftItem(
                type=DriftType.WIRING,
                category=DriftCategory.EDGE_ADDED,
                severity=DriftSeverity.INFO,
                file_path=Path("b.cpp"),
                title="Wiring",
                description="Desc",
            ),
        ]

        report = DriftReport(items=items)
        structural = report.filter_by_type(DriftType.STRUCTURAL)
        wiring = report.filter_by_type(DriftType.WIRING)

        assert len(structural) == 1
        assert structural[0].title == "Structural"
        assert len(wiring) == 1
        assert wiring[0].title == "Wiring"

    def test_get_blocking_items(self):
        """Should return only critical items."""
        items = [
            DriftItem(
                type=DriftType.STRUCTURAL,
                category=DriftCategory.EVIDENCE_MISSING,
                severity=DriftSeverity.WARNING,
                file_path=Path("a.py"),
                title="Warning",
                description="Desc",
            ),
            DriftItem(
                type=DriftType.STRUCTURAL,
                category=DriftCategory.SYMBOL_DELETED,
                severity=DriftSeverity.CRITICAL,
                file_path=Path("b.py"),
                title="Critical",
                description="Desc",
            ),
        ]

        report = DriftReport(items=items)
        blocking = report.get_blocking_items()

        assert len(blocking) == 1
        assert blocking[0].title == "Critical"

    def test_report_to_dict(self):
        """Should serialize report to dict."""
        report = DriftReport(
            items=[
                DriftItem(
                    type=DriftType.STRUCTURAL,
                    category=DriftCategory.EVIDENCE_MISSING,
                    severity=DriftSeverity.WARNING,
                    file_path=Path("a.py"),
                    title="Test",
                    description="Desc",
                ),
            ],
            analyzed_files=[Path("a.py")],
            duration_ms=150.5,
        )

        data = report.to_dict()

        assert len(data["items"]) == 1
        assert data["duration_ms"] == 150.5
        assert data["summary"]["total"] == 1
        assert data["summary"]["has_blocking"] is False

    def test_format_summary(self):
        """Should format human-readable summary."""
        items = [
            DriftItem(
                type=DriftType.STRUCTURAL,
                category=DriftCategory.SYMBOL_DELETED,
                severity=DriftSeverity.CRITICAL,
                file_path=Path("module.py"),
                line_number=10,
                title="Critical issue",
                description="Symbol deleted",
                suggestion="Fix it",
            ),
        ]

        report = DriftReport(items=items, duration_ms=100.0)
        summary = report.format_summary()

        assert "Drift Analysis Report" in summary
        assert "Total items: 1" in summary
        assert "Blocking: YES" in summary
        assert "BLOCKING ISSUES" in summary
        assert "Critical issue" in summary


# ─────────────────────────────────────────────────────────────
# StructuralDriftDetector Tests
# ─────────────────────────────────────────────────────────────


class TestStructuralDriftDetector:
    """Tests for structural drift detection."""

    @pytest.fixture
    def detector(self):
        return StructuralDriftDetector()

    def test_drift_type(self, detector):
        """Should report structural drift type."""
        assert detector.drift_type == DriftType.STRUCTURAL

    @pytest.mark.asyncio
    async def test_detect_no_contracts(self, detector, tmp_path):
        """Should return empty list when no contracts found."""
        test_file = tmp_path / "empty.py"
        test_file.write_text("def func(): pass")

        context = DriftContext(project_root=tmp_path)

        # Without contract discovery, should return empty
        items = await detector.detect(context, [test_file])
        assert len(items) == 0

    @pytest.mark.asyncio
    async def test_detect_evidence_stale(self, detector, tmp_path):
        """Should detect when evidence hasn't been run."""
        test_file = tmp_path / "module.py"
        test_file.write_text(
            dedent(
                '''
            def process(data):
                """
                @aegis-contract-begin
                evidence:
                  - test: tests/test_module.py::test_process
                    policy: required
                @aegis-contract-end
                """
                return data
        '''
            ).strip()
        )

        # Create contract discovery
        from code_map.contracts import ContractDiscovery

        context = DriftContext(
            project_root=tmp_path,
            contract_discovery=ContractDiscovery(enable_llm=False),
        )

        items = await detector.detect(context, [test_file])

        # Should find stale evidence (never run)
        stale_items = [i for i in items if i.category == DriftCategory.EVIDENCE_STALE]
        assert len(stale_items) >= 1


# ─────────────────────────────────────────────────────────────
# WiringDriftDetector Tests
# ─────────────────────────────────────────────────────────────


class TestWiringDriftDetector:
    """Tests for wiring drift detection."""

    @pytest.fixture
    def detector(self):
        return WiringDriftDetector()

    def test_drift_type(self, detector):
        """Should report wiring drift type."""
        assert detector.drift_type == DriftType.WIRING

    @pytest.mark.asyncio
    async def test_detect_no_wiring_state(self, detector, tmp_path):
        """Should return empty when no wiring state available."""
        context = DriftContext(project_root=tmp_path)
        items = await detector.detect(context)
        assert len(items) == 0

    @pytest.mark.asyncio
    async def test_detect_instance_added(self, detector, tmp_path):
        """Should detect when instance is added."""
        prev_wiring = {
            "instances": {
                "m1": {"type": "ModuleA", "file": "main.cpp", "line": 10},
            },
            "edges": [],
        }
        curr_wiring = {
            "instances": {
                "m1": {"type": "ModuleA", "file": "main.cpp", "line": 10},
                "m2": {"type": "ModuleB", "file": "main.cpp", "line": 15},
            },
            "edges": [],
        }

        context = DriftContext(
            project_root=tmp_path,
            previous_wiring=prev_wiring,
            current_wiring=curr_wiring,
        )

        items = await detector.detect(context)

        added = [i for i in items if i.category == DriftCategory.INSTANCE_ADDED]
        assert len(added) == 1
        assert added[0].symbol_name == "m2"

    @pytest.mark.asyncio
    async def test_detect_instance_removed(self, detector, tmp_path):
        """Should detect when instance is removed."""
        prev_wiring = {
            "instances": {
                "m1": {"type": "ModuleA", "file": "main.cpp", "line": 10},
                "m2": {"type": "ModuleB", "file": "main.cpp", "line": 15},
            },
            "edges": [],
        }
        curr_wiring = {
            "instances": {
                "m1": {"type": "ModuleA", "file": "main.cpp", "line": 10},
            },
            "edges": [],
        }

        context = DriftContext(
            project_root=tmp_path,
            previous_wiring=prev_wiring,
            current_wiring=curr_wiring,
        )

        items = await detector.detect(context)

        removed = [i for i in items if i.category == DriftCategory.INSTANCE_REMOVED]
        assert len(removed) == 1
        assert removed[0].symbol_name == "m2"
        assert removed[0].severity == DriftSeverity.WARNING

    @pytest.mark.asyncio
    async def test_detect_edge_added(self, detector, tmp_path):
        """Should detect when edge is added."""
        prev_wiring = {
            "instances": {"m1": {}, "m2": {}},
            "edges": [],
        }
        curr_wiring = {
            "instances": {"m1": {}, "m2": {}},
            "edges": [{"from": "m1", "to": "m2"}],
        }

        context = DriftContext(
            project_root=tmp_path,
            previous_wiring=prev_wiring,
            current_wiring=curr_wiring,
        )

        items = await detector.detect(context)

        added = [i for i in items if i.category == DriftCategory.EDGE_ADDED]
        assert len(added) == 1
        assert "m1 → m2" in added[0].title

    @pytest.mark.asyncio
    async def test_detect_edge_removed(self, detector, tmp_path):
        """Should detect when edge is removed."""
        prev_wiring = {
            "instances": {"m1": {}, "m2": {}},
            "edges": [{"from": "m1", "to": "m2"}],
        }
        curr_wiring = {
            "instances": {"m1": {}, "m2": {}},
            "edges": [],
        }

        context = DriftContext(
            project_root=tmp_path,
            previous_wiring=prev_wiring,
            current_wiring=curr_wiring,
        )

        items = await detector.detect(context)

        removed = [i for i in items if i.category == DriftCategory.EDGE_REMOVED]
        assert len(removed) == 1
        assert removed[0].severity == DriftSeverity.WARNING

    @pytest.mark.asyncio
    async def test_detect_type_changed(self, detector, tmp_path):
        """Should detect when instance type changes."""
        prev_wiring = {
            "instances": {
                "m1": {"type": "ModuleA", "file": "main.cpp"},
            },
            "edges": [],
        }
        curr_wiring = {
            "instances": {
                "m1": {"type": "ModuleB", "file": "main.cpp"},
            },
            "edges": [],
        }

        context = DriftContext(
            project_root=tmp_path,
            previous_wiring=prev_wiring,
            current_wiring=curr_wiring,
        )

        items = await detector.detect(context)

        changed = [i for i in items if i.category == DriftCategory.TYPE_CHANGED]
        assert len(changed) == 1
        assert changed[0].before_context == "ModuleA"
        assert changed[0].after_context == "ModuleB"


# ─────────────────────────────────────────────────────────────
# SemanticDriftDetector Tests
# ─────────────────────────────────────────────────────────────


class TestSemanticDriftDetector:
    """Tests for semantic drift detection."""

    @pytest.fixture
    def detector(self):
        return SemanticDriftDetector()

    def test_drift_type(self, detector):
        """Should report semantic drift type."""
        assert detector.drift_type == DriftType.SEMANTIC

    @pytest.mark.asyncio
    async def test_detect_no_contracts(self, detector, tmp_path):
        """Should return empty when no contracts found."""
        test_file = tmp_path / "empty.py"
        test_file.write_text("def func(): pass")

        context = DriftContext(project_root=tmp_path)
        items = await detector.detect(context, [test_file])
        assert len(items) == 0


# ─────────────────────────────────────────────────────────────
# DriftAnalyzer Tests
# ─────────────────────────────────────────────────────────────


class TestDriftAnalyzer:
    """Tests for DriftAnalyzer service."""

    @pytest.fixture
    def analyzer(self, tmp_path):
        return DriftAnalyzer(project_root=tmp_path)

    @pytest.mark.asyncio
    async def test_analyze_empty_project(self, analyzer):
        """Should return empty report for empty project."""
        report = await analyzer.analyze()

        assert report.total_count == 0
        assert not report.has_blocking_drift

    @pytest.mark.asyncio
    async def test_analyze_with_semantic(self, analyzer):
        """Should include semantic detection when enabled."""
        report = await analyzer.analyze(include_semantic=True)

        # Just verify it runs without error
        assert isinstance(report, DriftReport)

    def test_update_wiring_state(self, analyzer):
        """Should update wiring state for drift detection."""
        wiring1 = {"instances": {"m1": {}}, "edges": []}
        wiring2 = {"instances": {"m1": {}, "m2": {}}, "edges": []}

        analyzer.update_wiring_state(wiring1)
        assert analyzer._current_wiring == wiring1
        assert analyzer._previous_wiring is None

        analyzer.update_wiring_state(wiring2)
        assert analyzer._current_wiring == wiring2
        assert analyzer._previous_wiring == wiring1

    def test_clear_wiring_state(self, analyzer):
        """Should clear wiring state."""
        analyzer.update_wiring_state({"instances": {}, "edges": []})
        analyzer.clear_wiring_state()

        assert analyzer._previous_wiring is None
        assert analyzer._current_wiring is None

    def test_get_status(self, analyzer):
        """Should return current status."""
        status = analyzer.get_status()

        assert "project_root" in status
        assert "semantic_enabled" in status
        assert status["detectors"]["structural"] is True
        assert status["detectors"]["wiring"] is True

    @pytest.mark.asyncio
    async def test_analyze_structural_only(self, analyzer):
        """Should run only structural detection."""
        report = await analyzer.analyze_structural()
        assert isinstance(report, DriftReport)

    @pytest.mark.asyncio
    async def test_analyze_wiring_only(self, analyzer):
        """Should run only wiring detection."""
        report = await analyzer.analyze_wiring()
        assert isinstance(report, DriftReport)

    @pytest.mark.asyncio
    async def test_analyze_semantic_only(self, analyzer):
        """Should run only semantic detection."""
        report = await analyzer.analyze_semantic()
        assert isinstance(report, DriftReport)


# ─────────────────────────────────────────────────────────────
# Integration Tests
# ─────────────────────────────────────────────────────────────


class TestDriftIntegration:
    """Integration tests for drift detection system."""

    @pytest.mark.asyncio
    async def test_full_wiring_drift_workflow(self, tmp_path):
        """Should detect wiring drift through full workflow."""
        analyzer = DriftAnalyzer(project_root=tmp_path)

        # Initial state
        initial_wiring = {
            "instances": {
                "source": {"type": "SourceModule", "file": "main.cpp", "line": 10},
                "processor": {
                    "type": "ProcessorModule",
                    "file": "main.cpp",
                    "line": 15,
                },
            },
            "edges": [
                {"from": "source", "to": "processor"},
            ],
        }
        analyzer.update_wiring_state(initial_wiring)

        # Modified state - added sink, removed edge
        modified_wiring = {
            "instances": {
                "source": {"type": "SourceModule", "file": "main.cpp", "line": 10},
                "processor": {
                    "type": "ProcessorModule",
                    "file": "main.cpp",
                    "line": 15,
                },
                "sink": {"type": "SinkModule", "file": "main.cpp", "line": 20},
            },
            "edges": [
                {"from": "processor", "to": "sink"},
            ],
        }
        analyzer.update_wiring_state(modified_wiring)

        # Analyze
        report = await analyzer.analyze_wiring()

        # Should detect:
        # - sink instance added
        # - source->processor edge removed
        # - processor->sink edge added
        assert report.total_count >= 3

        by_category = {}
        for item in report.items:
            cat = item.category.value
            by_category[cat] = by_category.get(cat, 0) + 1

        assert by_category.get("instance_added", 0) >= 1
        assert by_category.get("edge_added", 0) >= 1
        assert by_category.get("edge_removed", 0) >= 1

    @pytest.mark.asyncio
    async def test_check_before_apply(self, tmp_path):
        """Should check drift before applying changes."""
        from code_map.drift.analyzer import check_drift_before_apply

        test_file = tmp_path / "module.py"
        test_file.write_text("def func(): pass")

        can_proceed, report = await check_drift_before_apply(tmp_path, [test_file])

        # No blocking drift expected for simple file
        assert can_proceed is True
        assert not report.has_blocking_drift
