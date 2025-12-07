# SPDX-License-Identifier: MIT
"""Tests for linters pipeline module."""

import json
from pathlib import Path



from code_map.linters import run_linters_pipeline
from code_map.linters.pipeline import (
    LINTER_CONFIG,
    LinterConfig,
    LinterRunOptions,
    ToolSpec,
    _check_max_file_length,
    _collect_project_stats,
    _default_parser,
    _ensure_text,
    _parse_bandit,
    _parse_ruff,
    _safe_severity,
    _select_tool_specs,
    _should_skip,
    _truncate_output,
    _build_skipped_report,
)
from code_map.linters.report_schema import CheckStatus, Severity


class TestLinterConfig:
    """Test LinterConfig dataclass."""

    def test_default_config_values(self) -> None:
        """Test that default config has reasonable values."""
        config = LinterConfig()
        assert config.max_output_chars == 2000
        assert config.max_issues_sample == 25
        assert config.timeout_fast == 180
        assert config.timeout_standard == 240
        assert config.timeout_tests == 600
        assert config.max_file_length_warn == 500
        assert config.max_file_length_critical == 1000
        assert config.default_timeout == 300

    def test_global_config_exists(self) -> None:
        """Test that global LINTER_CONFIG is available."""
        assert LINTER_CONFIG is not None
        assert isinstance(LINTER_CONFIG, LinterConfig)


class TestLinterRunOptions:
    """Test LinterRunOptions dataclass."""

    def test_default_options(self) -> None:
        """Test default options."""
        options = LinterRunOptions()
        assert options.enabled_tools is None
        assert options.max_project_files is None
        assert options.max_project_bytes is None

    def test_from_names_with_valid_names(self) -> None:
        """Test from_names with valid tool names."""
        result = LinterRunOptions.from_names(["ruff", "mypy", "bandit"])
        assert result == {"ruff", "mypy", "bandit"}

    def test_from_names_with_whitespace(self) -> None:
        """Test from_names strips whitespace."""
        result = LinterRunOptions.from_names(["  ruff  ", " mypy"])
        assert result == {"ruff", "mypy"}

    def test_from_names_normalizes_case(self) -> None:
        """Test from_names normalizes to lowercase."""
        result = LinterRunOptions.from_names(["RUFF", "MyPy"])
        assert result == {"ruff", "mypy"}

    def test_from_names_with_none(self) -> None:
        """Test from_names with None."""
        result = LinterRunOptions.from_names(None)
        assert result is None

    def test_from_names_with_empty_list(self) -> None:
        """Test from_names with empty list."""
        result = LinterRunOptions.from_names([])
        assert result is None

    def test_from_names_with_empty_strings(self) -> None:
        """Test from_names filters empty strings."""
        result = LinterRunOptions.from_names(["ruff", "", "  ", "mypy"])
        assert result == {"ruff", "mypy"}


class TestHelperFunctions:
    """Test helper functions in pipeline module."""

    def test_safe_severity_valid(self) -> None:
        """Test _safe_severity with valid severity."""
        assert _safe_severity("low") == Severity.LOW
        assert _safe_severity("medium") == Severity.MEDIUM
        assert _safe_severity("high") == Severity.HIGH
        assert _safe_severity("critical") == Severity.CRITICAL

    def test_safe_severity_case_insensitive(self) -> None:
        """Test _safe_severity is case insensitive."""
        assert _safe_severity("LOW") == Severity.LOW
        assert _safe_severity("High") == Severity.HIGH

    def test_safe_severity_with_none(self) -> None:
        """Test _safe_severity with None returns default."""
        assert _safe_severity(None) == Severity.MEDIUM
        assert _safe_severity(None, Severity.HIGH) == Severity.HIGH

    def test_safe_severity_with_invalid(self) -> None:
        """Test _safe_severity with invalid value returns default."""
        assert _safe_severity("invalid") == Severity.MEDIUM
        assert _safe_severity("invalid", Severity.LOW) == Severity.LOW

    def test_truncate_output_short(self) -> None:
        """Test _truncate_output with short text."""
        text = "short text"
        assert _truncate_output(text) == text

    def test_truncate_output_long(self) -> None:
        """Test _truncate_output truncates long text."""
        text = "x" * 3000
        result = _truncate_output(text, limit=100)
        assert len(result) == 100
        assert result.endswith("...")

    def test_truncate_output_exact_limit(self) -> None:
        """Test _truncate_output at exact limit."""
        text = "x" * 100
        result = _truncate_output(text, limit=100)
        assert result == text

    def test_ensure_text_with_string(self) -> None:
        """Test _ensure_text with string input."""
        assert _ensure_text("hello") == "hello"

    def test_ensure_text_with_bytes(self) -> None:
        """Test _ensure_text with bytes input."""
        assert _ensure_text(b"hello") == "hello"

    def test_ensure_text_with_none(self) -> None:
        """Test _ensure_text with None input."""
        assert _ensure_text(None) == ""

    def test_ensure_text_with_invalid_bytes(self) -> None:
        """Test _ensure_text with invalid UTF-8 bytes."""
        result = _ensure_text(b"\xff\xfe invalid")
        assert "invalid" in result

    def test_should_skip_venv(self) -> None:
        """Test _should_skip with .venv path."""
        assert _should_skip(Path("project/.venv/lib/python.py")) is True

    def test_should_skip_node_modules(self) -> None:
        """Test _should_skip with node_modules path."""
        assert _should_skip(Path("project/node_modules/package/index.js")) is True

    def test_should_skip_git(self) -> None:
        """Test _should_skip with .git path."""
        assert _should_skip(Path("project/.git/config")) is True

    def test_should_skip_regular_file(self) -> None:
        """Test _should_skip with regular file."""
        assert _should_skip(Path("project/src/main.py")) is False


class TestParseRuff:
    """Test ruff output parser."""

    def test_parse_ruff_valid_json(self) -> None:
        """Test parsing valid ruff JSON output."""
        ruff_output = json.dumps([
            {
                "filename": "test.py",
                "code": "E501",
                "message": "Line too long",
                "location": {"row": 10, "column": 80}
            }
        ])
        count, issues = _parse_ruff(ruff_output, "")
        assert count == 1
        assert len(issues) == 1
        assert issues[0].file == "test.py"
        assert issues[0].code == "E501"
        assert issues[0].message == "Line too long"
        assert issues[0].line == 10
        assert issues[0].column == 80

    def test_parse_ruff_invalid_json(self) -> None:
        """Test parsing invalid JSON returns empty."""
        count, issues = _parse_ruff("not valid json", "")
        assert count == 0
        assert issues == []

    def test_parse_ruff_empty_output(self) -> None:
        """Test parsing empty output."""
        count, issues = _parse_ruff("", "")
        assert count == 0
        assert issues == []

    def test_parse_ruff_null_location(self) -> None:
        """Test parsing with null location."""
        ruff_output = json.dumps([
            {
                "filename": "test.py",
                "code": "E501",
                "message": "Error",
                "location": None
            }
        ])
        count, issues = _parse_ruff(ruff_output, "")
        assert count == 1
        assert issues[0].line is None


class TestParseBandit:
    """Test bandit output parser."""

    def test_parse_bandit_valid_json(self) -> None:
        """Test parsing valid bandit JSON output."""
        bandit_output = json.dumps({
            "results": [
                {
                    "filename": "test.py",
                    "issue_text": "Possible hardcoded password",
                    "line_number": 5,
                    "issue_severity": "high",
                    "test_id": "B105"
                }
            ]
        })
        count, issues = _parse_bandit(bandit_output, "")
        assert count == 1
        assert len(issues) == 1
        assert issues[0].file == "test.py"
        assert issues[0].message == "Possible hardcoded password"
        assert issues[0].line == 5
        assert issues[0].severity == Severity.HIGH
        assert issues[0].code == "B105"

    def test_parse_bandit_invalid_json(self) -> None:
        """Test parsing invalid JSON returns empty."""
        count, issues = _parse_bandit("not valid json", "")
        assert count == 0
        assert issues == []

    def test_parse_bandit_empty_results(self) -> None:
        """Test parsing with empty results."""
        bandit_output = json.dumps({"results": []})
        count, issues = _parse_bandit(bandit_output, "")
        assert count == 0
        assert issues == []


class TestDefaultParser:
    """Test default output parser."""

    def test_default_parser_with_stdout(self) -> None:
        """Test default parser with stdout."""
        count, issues = _default_parser("line 1\nline 2\nline 3", "")
        assert count == 3
        assert len(issues) == 1
        assert "line 1" in issues[0].message

    def test_default_parser_with_stderr(self) -> None:
        """Test default parser with stderr only."""
        count, issues = _default_parser("", "error 1\nerror 2")
        assert count == 2
        assert "error 1" in issues[0].message

    def test_default_parser_empty(self) -> None:
        """Test default parser with empty input."""
        count, issues = _default_parser("", "")
        assert count == 0
        assert issues == []

    def test_default_parser_limits_lines(self) -> None:
        """Test default parser limits to 5 lines."""
        stdout = "\n".join([f"line {i}" for i in range(10)])
        count, issues = _default_parser(stdout, "")
        assert count == 5  # Limited to 5 lines


class TestSelectToolSpecs:
    """Test tool spec selection."""

    def test_select_all_tools_when_no_options(self) -> None:
        """Test all tools selected with no options."""
        from code_map.linters.pipeline import TOOL_SPECS
        result = _select_tool_specs(None)
        assert result == TOOL_SPECS

    def test_select_specific_tools(self) -> None:
        """Test selecting specific tools."""
        options = LinterRunOptions(enabled_tools={"ruff", "mypy"})
        result = _select_tool_specs(options)
        keys = {spec.key for spec in result}
        assert keys == {"ruff", "mypy"}

    def test_select_no_tools(self) -> None:
        """Test selecting no matching tools."""
        options = LinterRunOptions(enabled_tools={"nonexistent"})
        result = _select_tool_specs(options)
        assert len(result) == 0


class TestCheckMaxFileLength:
    """Test max file length checking."""

    def test_check_files_under_threshold(self, tmp_path: Path) -> None:
        """Test files under threshold pass."""
        (tmp_path / "small.py").write_text("# small file\n" * 10)
        result, metrics = _check_max_file_length(tmp_path, threshold=500)
        assert result.status == CheckStatus.PASS
        assert result.violations == []
        assert metrics["files_scanned"] == 1

    def test_check_files_over_threshold(self, tmp_path: Path) -> None:
        """Test files over threshold are flagged."""
        (tmp_path / "large.py").write_text("x = 1\n" * 600)
        result, metrics = _check_max_file_length(tmp_path, threshold=500)
        assert result.status == CheckStatus.WARN
        assert len(result.violations) == 1
        assert "large.py" in result.violations[0].file

    def test_check_files_critical_threshold(self, tmp_path: Path) -> None:
        """Test files over critical threshold are flagged as fail."""
        (tmp_path / "huge.py").write_text("x = 1\n" * 1100)
        result, metrics = _check_max_file_length(
            tmp_path, threshold=500, critical_threshold=1000
        )
        assert result.status == CheckStatus.FAIL
        assert result.violations[0].severity == Severity.CRITICAL

    def test_check_skips_excluded_dirs(self, tmp_path: Path) -> None:
        """Test that excluded directories are skipped."""
        venv = tmp_path / ".venv"
        venv.mkdir()
        (venv / "large.py").write_text("x = 1\n" * 1000)
        result, metrics = _check_max_file_length(tmp_path, threshold=500)
        assert result.status == CheckStatus.PASS
        assert metrics["files_scanned"] == 0


class TestCollectProjectStats:
    """Test project stats collection."""

    def test_collect_stats_empty_project(self, tmp_path: Path) -> None:
        """Test stats for empty project."""
        stats = _collect_project_stats(tmp_path)
        assert stats["files"] == 0
        assert stats["bytes"] == 0

    def test_collect_stats_with_files(self, tmp_path: Path) -> None:
        """Test stats with some files."""
        (tmp_path / "file1.py").write_text("content1")
        (tmp_path / "file2.py").write_text("content2")
        stats = _collect_project_stats(tmp_path)
        assert stats["files"] == 2
        assert stats["bytes"] > 0

    def test_collect_stats_skips_excluded(self, tmp_path: Path) -> None:
        """Test stats skip excluded directories."""
        venv = tmp_path / ".venv"
        venv.mkdir()
        (venv / "package.py").write_text("large content" * 100)
        (tmp_path / "main.py").write_text("small")
        stats = _collect_project_stats(tmp_path)
        assert stats["files"] == 1


class TestBuildSkippedReport:
    """Test skipped report building."""

    def test_build_skipped_report_basic(self, tmp_path: Path) -> None:
        """Test building a basic skipped report."""
        report = _build_skipped_report(tmp_path, reason="Test reason")
        assert report.summary.overall_status == CheckStatus.SKIPPED
        assert report.summary.total_checks == 0
        assert "Test reason" in report.notes

    def test_build_skipped_report_with_stats(self, tmp_path: Path) -> None:
        """Test building skipped report with stats."""
        stats = {"files": 100.0, "bytes": 1000000.0}
        report = _build_skipped_report(tmp_path, reason="Too many files", stats=stats)
        assert report.metrics["project_files"] == 100.0
        assert report.metrics["project_bytes"] == 1000000.0


class TestRunLintersPipeline:
    """Test the main pipeline function."""

    def test_run_pipeline_generates_report(self, tmp_path: Path) -> None:
        """Test basic pipeline execution generates a report."""
        pkg_dir = tmp_path / "pkg"
        tests_dir = tmp_path / "tests"
        pkg_dir.mkdir()
        tests_dir.mkdir()

        (pkg_dir / "__init__.py").write_text(
            "def add(a: int, b: int) -> int:\n    return a + b\n",
            encoding="utf-8",
        )
        (tests_dir / "test_pkg.py").write_text(
            "from pkg import add\n\n\ndef test_add() -> None:\n    assert add(2, 3) == 5\n",
            encoding="utf-8",
        )

        report = run_linters_pipeline(tmp_path)

        assert report.summary.total_checks == len(report.tools) + len(report.custom_rules)
        assert report.summary.overall_status.value in {"pass", "warn", "fail", "skipped"}
        assert isinstance(report.metrics, dict)
        assert report.summary.duration_ms is not None

    def test_run_pipeline_with_enabled_tools(self, tmp_path: Path) -> None:
        """Test pipeline with specific tools enabled."""
        (tmp_path / "test.py").write_text("x = 1\n")
        options = LinterRunOptions(enabled_tools={"ruff"})
        report = run_linters_pipeline(tmp_path, options=options)

        tool_keys = {t.key for t in report.tools}
        assert "ruff" in tool_keys or len(report.tools) == 0  # May be skipped if not installed

    def test_run_pipeline_empty_tools_returns_skipped(self, tmp_path: Path) -> None:
        """Test pipeline with no tools enabled returns skipped report."""
        (tmp_path / "test.py").write_text("x = 1\n")
        options = LinterRunOptions(enabled_tools={"nonexistent_tool"})
        report = run_linters_pipeline(tmp_path, options=options)
        assert report.summary.overall_status == CheckStatus.SKIPPED

    def test_run_pipeline_respects_max_files(self, tmp_path: Path) -> None:
        """Test pipeline respects max project files."""
        for i in range(10):
            (tmp_path / f"file{i}.py").write_text(f"x = {i}\n")

        options = LinterRunOptions(max_project_files=5)
        report = run_linters_pipeline(tmp_path, options=options)
        assert report.summary.overall_status == CheckStatus.SKIPPED
        assert "archivos exceden" in report.notes[0]

    def test_run_pipeline_respects_max_bytes(self, tmp_path: Path) -> None:
        """Test pipeline respects max project bytes."""
        (tmp_path / "large.py").write_text("x = 1\n" * 10000)

        options = LinterRunOptions(max_project_bytes=100)
        report = run_linters_pipeline(tmp_path, options=options)
        assert report.summary.overall_status == CheckStatus.SKIPPED
        assert "tamaño total" in report.notes[0]


class TestToolSpec:
    """Test ToolSpec dataclass."""

    def test_tool_spec_creation(self) -> None:
        """Test creating a ToolSpec."""
        spec = ToolSpec(
            key="test",
            name="Test Tool",
            command=["test", "--check"],
            module="test_module",
            timeout=60,
        )
        assert spec.key == "test"
        assert spec.name == "Test Tool"
        assert spec.command == ["test", "--check"]
        assert spec.module == "test_module"
        assert spec.timeout == 60
        assert spec.parser is None

    def test_tool_spec_default_values(self) -> None:
        """Test ToolSpec default values."""
        spec = ToolSpec(key="test", name="Test", command=["test"])
        assert spec.module is None
        assert spec.parser is None
        assert spec.timeout == 300
