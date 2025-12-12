# SPDX-License-Identifier: MIT
"""
Pipeline para ejecutar linters, recopilar resultados y generar un LintersReport.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess  # nosec B404 - invoca herramientas de linters definidas por la app
import sys
import time
from collections import Counter
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Set, Tuple, cast

from defusedxml import ElementTree as _ElementTree  # type: ignore[import-not-found, import-untyped]

from ..constants import DEFAULT_EXCLUDED_DIRS
from .report_schema import (
    ChartData,
    CheckStatus,
    CoverageSnapshot,
    CustomRuleResult,
    IssueDetail,
    LintersReport,
    ReportSummary,
    Severity,
    ToolRunResult,
)

ElementTree = cast(Any, _ElementTree)


# ============================================================================
# CONSTANTS - Linter Pipeline Configuration
# ============================================================================


@dataclass(frozen=True)
class LinterConfig:
    """
    Centralized configuration for linter pipeline.
    All magic numbers and thresholds in one place for easy tuning.
    """

    # Output truncation limits
    max_output_chars: int = 2000  # Maximum characters before truncating tool output
    max_issues_sample: int = 25  # Maximum issues to include in report samples

    # Linter tool timeouts (seconds)
    timeout_fast: int = 180  # For ruff, black (fast formatters/linters)
    timeout_standard: int = 240  # For mypy, bandit (type checkers, security scanners)
    timeout_tests: int = 600  # For pytest with coverage (can be slow)

    # File length thresholds
    max_file_length_warn: int = 500  # Recommended maximum lines per file before warning
    max_file_length_critical: int = (
        1000  # Critical threshold where files are severely oversized
    )

    # Default timeout fallback
    default_timeout: int = 300  # Used when no specific timeout is defined


# Global configuration instance (can be overridden for testing or custom deployments)
LINTER_CONFIG = LinterConfig()

# Backward compatibility: export constants for existing code
MAX_OUTPUT_TRUNCATE_CHARS = LINTER_CONFIG.max_output_chars
MAX_ISSUES_SAMPLE_SIZE = LINTER_CONFIG.max_issues_sample
LINTER_TIMEOUT_FAST = LINTER_CONFIG.timeout_fast
LINTER_TIMEOUT_STANDARD = LINTER_CONFIG.timeout_standard
LINTER_TIMEOUT_TESTS = LINTER_CONFIG.timeout_tests
MAX_FILE_LENGTH_THRESHOLD = LINTER_CONFIG.max_file_length_warn
MAX_FILE_LENGTH_CRITICAL = LINTER_CONFIG.max_file_length_critical

# ============================================================================

ParsedIssues = Tuple[int, List[IssueDetail]]
IssueParser = Callable[[str, str], ParsedIssues]


def _safe_severity(
    value: Optional[str], default: Severity = Severity.MEDIUM
) -> Severity:
    if not value:
        return default
    try:
        return Severity(value.lower())
    except ValueError:
        return default


@dataclass(frozen=True)
class ToolSpec:
    """Metadatos para ejecutar una herramienta estándar del pipeline."""

    key: str
    name: str
    command: List[str]
    module: Optional[str] = None
    parser: Optional[IssueParser] = None
    timeout: int = 300


@dataclass(frozen=True)
class LinterRunOptions:
    """Configuración opcional para ajustar la ejecución del pipeline."""

    enabled_tools: Optional[Set[str]] = None
    max_project_files: Optional[int] = None
    max_project_bytes: Optional[int] = None

    @staticmethod
    def from_names(names: Optional[Iterable[str]]) -> Optional[Set[str]]:
        if not names:
            return None
        normalized = {name.strip().lower() for name in names if name.strip()}
        return normalized or None


def _which(command: str) -> Optional[str]:
    path = shutil.which(command)
    return path


def _truncate_output(text: str, limit: int = MAX_OUTPUT_TRUNCATE_CHARS) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def _ensure_text(data: bytes | str | None) -> str:
    if data is None:
        return ""
    if isinstance(data, bytes):
        return data.decode("utf-8", errors="replace")
    return data


def _parse_ruff(stdout: str, _: str) -> ParsedIssues:
    issues: List[IssueDetail] = []
    try:
        payload = json.loads(stdout or "[]")
    except json.JSONDecodeError:
        return 0, issues

    for item in payload[:MAX_ISSUES_SAMPLE_SIZE]:
        filename = item.get("filename", "")
        code = item.get("code")
        message = item.get("message", "")
        location = item.get("location", {}) or {}
        row = location.get("row")
        column = location.get("column")
        issues.append(
            IssueDetail(
                message=message,
                file=filename,
                line=row,
                column=column,
                code=code,
                severity=Severity.LOW,
            )
        )
    return len(payload), issues


def _parse_bandit(stdout: str, _: str) -> ParsedIssues:
    issues: List[IssueDetail] = []
    try:
        payload = json.loads(stdout or "{}")
    except json.JSONDecodeError:
        return 0, issues

    results = payload.get("results", [])[:MAX_ISSUES_SAMPLE_SIZE]
    for item in results:
        issues.append(
            IssueDetail(
                message=item.get("issue_text", ""),
                file=item.get("filename"),
                line=item.get("line_number"),
                severity=_safe_severity(item.get("issue_severity"), Severity.LOW),
                code=item.get("test_id"),
            )
        )
    return len(results), issues


def _default_parser(stdout: str, stderr: str) -> ParsedIssues:
    if stdout:
        message = stdout.strip().splitlines()[:5]
    else:
        message = stderr.strip().splitlines()[:5]
    if not message:
        return 0, []
    return (
        len(message),
        [
            IssueDetail(
                message="\n".join(message),
                severity=Severity.MEDIUM,
            )
        ],
    )


TOOL_SPECS: Tuple[ToolSpec, ...] = (
    ToolSpec(
        key="ruff",
        name="Ruff",
        command=["ruff", "check", ".", "--output-format", "json"],
        module="ruff",
        parser=_parse_ruff,
        timeout=LINTER_TIMEOUT_FAST,
    ),
    ToolSpec(
        key="black",
        name="Black",
        command=["black", "--check", "--diff", "--no-color", "."],
        module="black",
        parser=_default_parser,
        timeout=LINTER_TIMEOUT_FAST,
    ),
    ToolSpec(
        key="mypy",
        name="mypy",
        command=["mypy", "."],
        module="mypy",
        parser=_default_parser,
        timeout=LINTER_TIMEOUT_STANDARD,
    ),
    ToolSpec(
        key="bandit",
        name="Bandit",
        command=["bandit", "-q", "-r", ".", "-f", "json", "-x", "./.venv/*,./tests/*"],
        module="bandit",
        parser=_parse_bandit,
        timeout=LINTER_TIMEOUT_STANDARD,
    ),
    ToolSpec(
        key="pytest",
        name="pytest",
        command=[
            "pytest",
            "--maxfail=1",
            "--disable-warnings",
            "--cov=.",
            "--cov-report=term",
            "--cov-report=xml",
        ],
        module="pytest",
        parser=_default_parser,
        timeout=LINTER_TIMEOUT_TESTS,
    ),
)


EXCLUDE_FILENAMES: Tuple[str, ...] = (
    "__pycache__",
    ".git",
    ".hg",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
    ".code-map",
    "node_modules",
    ".venv",
    "venv",
)

EXCLUDED_DIRS = DEFAULT_EXCLUDED_DIRS | set(EXCLUDE_FILENAMES)


def _should_skip(path: Path) -> bool:
    parts = set(path.parts)
    return any(excluded in parts for excluded in EXCLUDED_DIRS)


def _check_max_file_length(
    root: Path,
    threshold: int = MAX_FILE_LENGTH_THRESHOLD,
    critical_threshold: int = MAX_FILE_LENGTH_CRITICAL,
) -> Tuple[CustomRuleResult, Dict[str, float]]:
    violations: List[IssueDetail] = []
    files_scanned = 0
    total_lines = 0
    max_lines = 0
    for path in root.rglob("*.py"):
        if _should_skip(path):
            continue
        try:
            with path.open("r", encoding="utf-8", errors="ignore") as handle:
                line_count = sum(1 for _ in handle)
        except OSError:
            continue
        files_scanned += 1
        total_lines += line_count
        max_lines = max(max_lines, line_count)
        if line_count <= threshold:
            continue
        severity = (
            Severity.CRITICAL if line_count >= critical_threshold else Severity.HIGH
        )
        violations.append(
            IssueDetail(
                message=f"{path.relative_to(root)} tiene {line_count} líneas.",
                file=str(path.relative_to(root)),
                severity=severity,
            )
        )

    if not violations:
        result = CustomRuleResult(
            key="max_file_length",
            name="Longitud máxima de archivo",
            status=CheckStatus.PASS,
            description="Los archivos no superan el umbral establecido.",
            threshold=threshold,
            violations=[],
        )
        metrics = {
            "files_scanned": float(files_scanned),
            "lines_scanned": float(total_lines),
            "max_lines_observed": float(max_lines),
        }
        return result, metrics

    status = (
        CheckStatus.FAIL
        if any(item.severity == Severity.CRITICAL for item in violations)
        else CheckStatus.WARN
    )
    result = CustomRuleResult(
        key="max_file_length",
        name="Longitud máxima de archivo",
        status=status,
        description=f"Algunos archivos superan las {threshold} líneas permitidas.",
        threshold=threshold,
        violations=violations[:MAX_ISSUES_SAMPLE_SIZE],
    )
    metrics = {
        "files_scanned": float(files_scanned),
        "lines_scanned": float(total_lines),
        "max_lines_observed": float(max_lines),
        "max_file_length_violations": float(len(violations)),
    }
    return result, metrics


def _execute_tool(
    root: Path, spec: ToolSpec, audit_run_id: Optional[int] = None
) -> Tuple[ToolRunResult, Optional[CoverageSnapshot]]:
    base_command = list(spec.command)
    binary = base_command[0]
    effective_command = base_command
    if _which(binary) is None:
        if spec.module:
            effective_command = [sys.executable, "-m", spec.module, *base_command[1:]]
        else:
            return (
                ToolRunResult(
                    key=spec.key,
                    name=spec.name,
                    status=CheckStatus.SKIPPED,
                    command=" ".join(base_command),
                    issues_found=0,
                    issues_sample=[],
                    stdout_excerpt=None,
                    stderr_excerpt="Comando no encontrado en PATH.",
                ),
                None,
            )

    start = time.perf_counter()

    # Use audit hook if run_id provided
    if audit_run_id is not None:
        try:
            from ..audit.hooks import audit_run_command

            completed = audit_run_command(
                effective_command,
                run_id=audit_run_id,
                phase="validate",
                actor="system",
                timeout=spec.timeout,
                cwd=root,
            )
        except ImportError:
            # Fallback if audit module not available
            try:
                completed = subprocess.run(  # nosec B603
                    effective_command,
                    cwd=root,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=spec.timeout,
                )
            except subprocess.TimeoutExpired as exc:
                duration_ms = int((time.perf_counter() - start) * 1000)
                message = f"Ejecución excedió el timeout ({spec.timeout}s)."
                issue = IssueDetail(message=message, severity=Severity.HIGH)
                stdout_excerpt = _truncate_output(_ensure_text(exc.stdout))
                stderr_excerpt = _truncate_output(_ensure_text(exc.stderr))
                return (
                    ToolRunResult(
                        key=spec.key,
                        name=spec.name,
                        status=CheckStatus.ERROR,
                        command=" ".join(effective_command),
                        duration_ms=duration_ms,
                        exit_code=None,
                        issues_found=1,
                        issues_sample=[issue],
                        stdout_excerpt=stdout_excerpt,
                        stderr_excerpt=stderr_excerpt,
                    ),
                    None,
                )
    else:
        # Normal execution without audit
        try:
            completed = subprocess.run(  # nosec B603 - comandos provienen de ToolSpec controlado
                effective_command,
                cwd=root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=spec.timeout,
            )
        except subprocess.TimeoutExpired as exc:
            duration_ms = int((time.perf_counter() - start) * 1000)
            message = f"Ejecución excedió el timeout ({spec.timeout}s)."
            issue = IssueDetail(message=message, severity=Severity.HIGH)
            stdout_excerpt = _truncate_output(_ensure_text(exc.stdout))
            stderr_excerpt = _truncate_output(_ensure_text(exc.stderr))
            return (
                ToolRunResult(
                    key=spec.key,
                    name=spec.name,
                    status=CheckStatus.ERROR,
                    command=" ".join(effective_command),
                    duration_ms=duration_ms,
                    exit_code=None,
                    issues_found=1,
                    issues_sample=[issue],
                    stdout_excerpt=stdout_excerpt,
                    stderr_excerpt=stderr_excerpt,
                ),
                None,
            )

    duration_ms = int((time.perf_counter() - start) * 1000)
    returncode = completed.returncode
    stdout = _ensure_text(completed.stdout)
    stderr = _ensure_text(completed.stderr)
    parser = spec.parser or _default_parser

    issues_found = 0
    issues_sample: List[IssueDetail] = []
    if returncode != 0:
        parsed = parser(stdout, stderr)
        issues_found, issues_sample = parsed
        if issues_found == 0 and not issues_sample:
            issues_found, issues_sample = _default_parser(stdout, stderr)

    status = CheckStatus.PASS if returncode == 0 else CheckStatus.FAIL
    coverage: Optional[CoverageSnapshot] = None

    if spec.key == "pytest":
        coverage = _extract_coverage(root)

    return (
        ToolRunResult(
            key=spec.key,
            name=spec.name,
            status=status,
            command=" ".join(effective_command),
            duration_ms=duration_ms,
            exit_code=returncode,
            issues_found=issues_found,
            issues_sample=issues_sample,
            stdout_excerpt=_truncate_output(stdout),
            stderr_excerpt=_truncate_output(stderr),
        ),
        coverage,
    )


def _extract_coverage(root: Path) -> Optional[CoverageSnapshot]:
    xml_path = root / "coverage.xml"
    if not xml_path.exists():
        return None
    try:
        tree = ElementTree.parse(xml_path)
        root_element = tree.getroot()
        statement_rate = float(root_element.attrib.get("line-rate", 0.0)) * 100
        branch_rate = float(root_element.attrib.get("branch-rate", 0.0)) * 100
        missed = int(root_element.attrib.get("lines-not-covered", 0))
        return CoverageSnapshot(
            statement_coverage=round(statement_rate, 2),
            branch_coverage=round(branch_rate, 2),
            missing_lines=missed,
        )
    except (ElementTree.ParseError, ValueError, OSError):
        return None
    finally:
        try:
            xml_path.unlink()
        except OSError:
            pass


def _aggregate_summary(
    tools: List[ToolRunResult],
    custom_rules: List[CustomRuleResult],
) -> Tuple[ReportSummary, ChartData, Dict[str, float], Counter]:
    total_checks = len(tools) + len(custom_rules)
    checks_passed = sum(
        1 for item in tools + custom_rules if item.status == CheckStatus.PASS
    )
    checks_warned = sum(
        1 for item in tools + custom_rules if item.status == CheckStatus.WARN
    )
    checks_failed = sum(
        1
        for item in tools + custom_rules
        if item.status in {CheckStatus.FAIL, CheckStatus.ERROR}
    )

    issues_total = sum(tool.issues_found for tool in tools) + sum(
        len(rule.violations) for rule in custom_rules
    )
    severity_counter: Counter[Severity] = Counter()
    issues_by_tool: Dict[str, int] = {}
    top_candidates: List[str] = []
    for tool in tools:
        if tool.issues_found:
            issues_by_tool[tool.key] = tool.issues_found
            for issue in tool.issues_sample:
                severity_counter[issue.severity] += 1
                if issue.file:
                    top_candidates.append(issue.file)
    for rule in custom_rules:
        if rule.violations:
            issues_by_tool[rule.key] = len(rule.violations)
            for issue in rule.violations:
                severity_counter[issue.severity] += 1
                if issue.file:
                    top_candidates.append(issue.file)

    critical_issues = severity_counter[Severity.CRITICAL]

    if any(
        item.status in {CheckStatus.FAIL, CheckStatus.ERROR}
        for item in tools + custom_rules
    ):
        overall_status = CheckStatus.FAIL
    elif any(item.status == CheckStatus.WARN for item in tools + custom_rules):
        overall_status = CheckStatus.WARN
    elif all(item.status == CheckStatus.SKIPPED for item in tools + custom_rules):
        overall_status = CheckStatus.SKIPPED
    else:
        overall_status = CheckStatus.PASS

    seen: set[str] = set()
    top_offenders: List[str] = []
    for candidate in top_candidates:
        if candidate and candidate not in seen:
            seen.add(candidate)
            top_offenders.append(candidate)
        if len(top_offenders) >= 5:
            break

    chart_data = ChartData(
        issues_by_tool=issues_by_tool,
        issues_by_severity=dict(severity_counter),
        top_offenders=top_offenders,
    )

    metrics = {
        "tools_duration_ms": float(sum(tool.duration_ms or 0 for tool in tools)),
        "custom_rules_count": float(len(custom_rules)),
    }

    summary = ReportSummary(
        overall_status=overall_status,
        total_checks=total_checks,
        checks_passed=checks_passed,
        checks_warned=checks_warned,
        checks_failed=checks_failed,
        duration_ms=int(metrics["tools_duration_ms"]),
        issues_total=issues_total,
        critical_issues=critical_issues,
    )

    return summary, chart_data, metrics, severity_counter


def run_linters_pipeline(
    root: Path,
    options: Optional[LinterRunOptions] = None,
    audit_run_id: Optional[int] = None,
) -> LintersReport:
    """Ejecuta las herramientas estándar y devuelve un reporte completo."""
    resolved_root = Path(root).expanduser().resolve()
    start = time.perf_counter()

    # Get audit run ID from environment if not provided
    if audit_run_id is None:
        audit_run_id_str = os.getenv("AEGIS_AUDIT_RUN_ID")
        if audit_run_id_str:
            try:
                audit_run_id = int(audit_run_id_str)
            except ValueError:
                pass

    selected_specs = _select_tool_specs(options)
    if not selected_specs:
        return _build_skipped_report(
            resolved_root,
            reason="No hay herramientas de linters habilitadas. Ajusta CODE_MAP_LINTERS_TOOLS para ejecutar el pipeline.",
        )

    if options and (
        options.max_project_files is not None or options.max_project_bytes is not None
    ):
        stats = _collect_project_stats(resolved_root)
        if (
            options.max_project_files is not None
            and stats["files"] > options.max_project_files
        ):
            return _build_skipped_report(
                resolved_root,
                reason=(
                    f"Pipeline omitido: {stats['files']} archivos exceden el limite "
                    f"de {options.max_project_files} (CODE_MAP_LINTERS_MAX_PROJECT_FILES)."
                ),
                stats=stats,
            )
        if (
            options.max_project_bytes is not None
            and stats["bytes"] > options.max_project_bytes
        ):
            limit_mb = options.max_project_bytes / (1024 * 1024)
            total_mb = stats["bytes"] / (1024 * 1024)
            return _build_skipped_report(
                resolved_root,
                reason=(
                    f"Pipeline omitido: tamaño total {total_mb:.1f} MiB excede el limite "
                    f"de {limit_mb:.1f} MiB (CODE_MAP_LINTERS_MAX_PROJECT_SIZE_MB)."
                ),
                stats=stats,
            )

    tool_results: List[ToolRunResult] = []
    coverage_snapshot: Optional[CoverageSnapshot] = None
    for spec in selected_specs:
        tool_result, coverage = _execute_tool(
            resolved_root, spec, audit_run_id=audit_run_id
        )
        tool_results.append(tool_result)
        if coverage:
            coverage_snapshot = coverage

    custom_rule, custom_metrics = _check_max_file_length(resolved_root)
    custom_rules = [custom_rule]

    summary, chart_data, metrics, severity_counter = _aggregate_summary(
        tool_results, custom_rules
    )
    pipeline_duration_ms = int((time.perf_counter() - start) * 1000)
    files_scanned_val = custom_metrics.get("files_scanned")
    lines_scanned_val = custom_metrics.get("lines_scanned")
    summary = replace(
        summary,
        duration_ms=pipeline_duration_ms,
        files_scanned=(
            int(files_scanned_val) if files_scanned_val else summary.files_scanned
        ),
        lines_scanned=(
            int(lines_scanned_val) if lines_scanned_val else summary.lines_scanned
        ),
    )
    metrics["pipeline_duration_ms"] = float(pipeline_duration_ms)
    metrics["issues_total"] = float(summary.issues_total)
    metrics["critical_issues"] = float(summary.critical_issues)
    metrics.update(custom_metrics)

    notes: List[str] = []
    if summary.overall_status == CheckStatus.PASS:
        notes.append("Todas las herramientas pasaron sin incidencias.")
    elif summary.overall_status == CheckStatus.FAIL:
        notes.append("Se detectaron fallos en el pipeline de linters.")
    elif summary.overall_status == CheckStatus.WARN:
        notes.append("Hay advertencias que conviene revisar.")
    elif summary.overall_status == CheckStatus.SKIPPED:
        notes.append("No se pudieron ejecutar las herramientas configuradas.")

    return LintersReport(
        root_path=str(resolved_root),
        generated_at=datetime.now(timezone.utc),
        summary=summary,
        tools=tool_results,
        custom_rules=custom_rules,
        coverage=coverage_snapshot,
        metrics=metrics,
        chart_data=chart_data,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Internal helpers for optional throttling / filtering


def _select_tool_specs(options: Optional[LinterRunOptions]) -> Tuple[ToolSpec, ...]:
    if not options or options.enabled_tools is None:
        return TOOL_SPECS

    enabled = {name.lower() for name in options.enabled_tools}
    filtered = tuple(spec for spec in TOOL_SPECS if spec.key.lower() in enabled)
    return filtered


def _collect_project_stats(root: Path) -> Dict[str, float]:
    total_files = 0
    total_bytes = 0
    for path in root.rglob("*"):
        if path.is_dir():
            continue
        try:
            relative = path.relative_to(root)
        except ValueError:
            relative = path
        if _should_skip(relative):
            continue
        total_files += 1
        try:
            total_bytes += path.stat().st_size
        except OSError:
            continue
    return {"files": float(total_files), "bytes": float(total_bytes)}


def _build_skipped_report(
    root: Path, reason: str, *, stats: Optional[Dict[str, float]] = None
) -> LintersReport:
    resolved_root = Path(root).expanduser().resolve()
    now = datetime.now(timezone.utc)
    summary = ReportSummary(
        overall_status=CheckStatus.SKIPPED,
        total_checks=0,
        checks_passed=0,
        checks_warned=0,
        checks_failed=0,
        duration_ms=0,
        issues_total=0,
        critical_issues=0,
    )
    metrics: Dict[str, float] = {}
    if stats:
        metrics.update({f"project_{key}": value for key, value in stats.items()})

    chart_data = ChartData(issues_by_tool={}, issues_by_severity={}, top_offenders=[])
    return LintersReport(
        root_path=str(resolved_root),
        generated_at=now,
        summary=summary,
        tools=[],
        custom_rules=[],
        coverage=None,
        metrics=metrics,
        chart_data=chart_data,
        notes=[reason],
    )
