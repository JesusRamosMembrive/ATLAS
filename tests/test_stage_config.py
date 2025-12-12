from pathlib import Path

from stage_config import (
    StageMetrics,
    collect_metrics,
    evaluate_stage,
)
import assess_stage
from code_map import ProjectScanner, SymbolIndex


def write_module(tmp_path: Path, relative: str, content: str) -> Path:
    target = tmp_path / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content.strip() + "\n", encoding="utf-8")
    return target


def test_evaluate_stage_returns_stage1_for_small_project() -> None:
    metrics = StageMetrics(
        file_count=2,
        lines_of_code=200,
        complexity={"total": 0, "max": 0, "avg": 0},
        complexity_distribution={"low": 0, "medium": 0, "high": 0, "critical": 0},
        top_complex_functions=[],
        problematic_functions=[],
        directory_count=1,
        patterns_found=[],
        architectural_folders=[],
    )

    assessment = evaluate_stage(metrics)

    assert assessment.recommended_stage == 1
    assert assessment.confidence == "high"
    assert assessment.metrics.file_count == 2


def test_evaluate_stage_returns_stage3_for_large_project() -> None:
    metrics = StageMetrics(
        file_count=45,
        lines_of_code=7500,
        complexity={"total": 100, "max": 15, "avg": 5},
        complexity_distribution={"low": 15, "medium": 10, "high": 5, "critical": 0},
        top_complex_functions=[],
        problematic_functions=[],
        directory_count=12,
        patterns_found=["Service Layer", "Repository", "Strategy", "Adapter"],
        architectural_folders=[
            "services",
            "repositories",
            "domain",
            "infrastructure",
            "application",
        ],
    )

    assessment = evaluate_stage(metrics)

    assert assessment.recommended_stage == 3
    assert "Large or complex codebase" in assessment.reasons[0]
    assert assessment.diagnostics.applied_stage.number == 3


def test_collect_metrics_uses_symbol_index(tmp_path: Path) -> None:
    write_module(
        tmp_path,
        "pkg/module.py",
        """
class Service:
    def run(self) -> int:
        return 1
""",
    )

    scanner = ProjectScanner(tmp_path)
    summaries = scanner.scan()

    index = SymbolIndex(tmp_path)
    index.update(summaries)

    metrics_from_index = collect_metrics(tmp_path, symbol_index=index)
    metrics_from_fs = collect_metrics(tmp_path)

    # Core metrics should match
    assert metrics_from_index.file_count == metrics_from_fs.file_count
    assert metrics_from_index.lines_of_code == metrics_from_fs.lines_of_code
    assert metrics_from_index.directory_count == metrics_from_fs.directory_count
    assert metrics_from_index.patterns_found == metrics_from_fs.patterns_found
    assert (
        metrics_from_index.architectural_folders
        == metrics_from_fs.architectural_folders
    )
    assert metrics_from_index.file_count == 1


def test_assess_stage_accepts_precomputed_metrics(tmp_path: Path) -> None:
    write_module(
        tmp_path,
        "app.py",
        """
def main():
    return "ok"
""",
    )

    metrics = collect_metrics(tmp_path)
    payload = assess_stage.assess_stage(tmp_path, metrics=metrics)

    assert payload is not None
    assert payload["recommended_stage"] == 1

    assessment_obj = assess_stage.assess_stage(
        tmp_path, metrics=metrics, return_dataclass=True
    )
    assert assessment_obj is not None
    assert assessment_obj.recommended_stage == payload["recommended_stage"]
