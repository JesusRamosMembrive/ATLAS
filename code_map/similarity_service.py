# SPDX-License-Identifier: MIT
"""
Service for code similarity analysis using the C++ motor.

This module provides functions to run similarity analysis via the C++ executable,
either in standalone mode (direct CLI invocation) or server mode (UDS socket).
"""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Path to the C++ executable (relative to project root)
CPP_EXECUTABLE = "cpp/build/static_analysis_motor"


@dataclass
class CloneLocation:
    """Location of a code clone."""

    file: str
    start_line: int
    end_line: int
    snippet_preview: str = ""


@dataclass
class CloneEntry:
    """A detected code clone pair."""

    id: str
    type: str  # Type-1, Type-2, Type-3
    similarity: float
    locations: list[CloneLocation] = field(default_factory=list)
    recommendation: str = ""


@dataclass
class DuplicationHotspot:
    """A file with high duplication."""

    file: str
    clone_count: int
    duplication_score: float
    duplicated_lines: int = 0
    total_lines: int = 0
    recommendation: str = ""


@dataclass
class SimilaritySummary:
    """Summary of similarity analysis."""

    files_analyzed: int
    total_lines: int
    clone_pairs_found: int
    estimated_duplication: str
    analysis_time_ms: int


@dataclass
class SimilarityPerformance:
    """Performance metrics from similarity analysis."""

    loc_per_second: float
    tokens_per_second: float
    files_per_second: int = 0
    total_tokens: int = 0
    thread_count: int = 1
    parallel_enabled: bool = False


@dataclass
class SimilarityTiming:
    """Timing breakdown of similarity analysis."""

    tokenize_ms: int
    hash_ms: int
    match_ms: int
    total_ms: int


@dataclass
class SimilarityMetrics:
    """Metrics breakdown by type and language."""

    by_type: dict[str, int] = field(default_factory=dict)
    by_language: dict[str, int] = field(default_factory=dict)


@dataclass
class SimilarityReport:
    """Complete similarity analysis report."""

    summary: SimilaritySummary
    performance: SimilarityPerformance
    timing: SimilarityTiming
    metrics: SimilarityMetrics
    hotspots: list[DuplicationHotspot] = field(default_factory=list)
    clones: list[CloneEntry] = field(default_factory=list)


class SimilarityServiceError(Exception):
    """Exception raised when similarity analysis fails."""

    pass


def _get_executable_path() -> Path:
    """Get the path to the C++ executable."""
    project_root = Path(__file__).parent.parent
    return project_root / CPP_EXECUTABLE


def is_available() -> bool:
    """Check if the C++ similarity motor is available."""
    exe_path = _get_executable_path()
    return exe_path.exists() and exe_path.is_file()


# Default patterns to exclude from analysis
DEFAULT_EXCLUDE_PATTERNS = [
    # Package managers and caches
    "**/node_modules/**",
    "**/__pycache__/**",
    "**/venv/**",
    "**/.venv/**",
    "**/env/**",
    "**/.git/**",
    "**/dist/**",
    # Build directories
    "**/build/**",
    "**/cmake-build-*/**",  # CLion build directories
    "**/_deps/**",  # CMake FetchContent dependencies
    "**/vcpkg_installed/**",  # vcpkg dependencies
    # Third-party code
    "**/third_party/**",
    "**/vendor/**",
    "**/external/**",
    # Minified files
    "**/*.min.js",
    "**/*.min.css",
    # Test files (often have similar boilerplate)
    "**/tests/**",
    "**/test/**",
    "**/*_test.py",
    "**/*_test.js",
    "**/*.test.ts",
    "**/*.spec.ts",
]


def analyze_similarity(
    root: str | Path,
    extensions: Optional[list[str]] = None,
    exclude_patterns: Optional[list[str]] = None,
    min_tokens: int = 30,
    min_similarity: float = 0.7,
    type3: bool = False,
    max_gap: int = 5,
    threads: Optional[int] = None,
    timeout: int = 300,
) -> SimilarityReport:
    """
    Run similarity analysis on a directory.

    Args:
        root: Root directory to analyze
        extensions: File extensions to include (e.g., [".py", ".js"])
        exclude_patterns: Glob patterns to exclude (e.g., ["**/tests/**", "**/venv/**"])
        min_tokens: Minimum tokens for a clone (default 30)
        min_similarity: Minimum similarity threshold (default 0.7)
        type3: Enable Type-3 detection (default False)
        max_gap: Maximum gap for Type-3 detection (default 5)
        threads: Number of threads (None for auto)
        timeout: Timeout in seconds (default 300)

    Returns:
        SimilarityReport with analysis results

    Raises:
        SimilarityServiceError: If analysis fails
    """
    exe_path = _get_executable_path()

    if not is_available():
        raise SimilarityServiceError(
            f"C++ similarity motor not found at {exe_path}. "
            "Build it with: cd cpp && cmake -B build && cmake --build build"
        )

    # Build command
    cmd = [
        str(exe_path),
        "--root",
        str(root),
        "--min-tokens",
        str(min_tokens),
        "--threshold",
        str(min_similarity),
    ]

    # Add extensions
    if extensions:
        for ext in extensions:
            cmd.extend(["--ext", ext])
    else:
        cmd.extend(["--ext", ".py"])

    # Add exclude patterns
    patterns = (
        exclude_patterns if exclude_patterns is not None else DEFAULT_EXCLUDE_PATTERNS
    )
    for pattern in patterns:
        cmd.extend(["--exclude", pattern])

    # Type-3 detection
    if type3:
        cmd.append("--type3")
        cmd.extend(["--max-gap", str(max_gap)])

    # Threads
    if threads is not None:
        cmd.extend(["--threads", str(threads)])

    logger.info(f"Running similarity analysis: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        raise SimilarityServiceError(f"Analysis timed out after {timeout}s")

    if result.returncode != 0:
        raise SimilarityServiceError(f"Analysis failed: {result.stderr}")

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        raise SimilarityServiceError(
            f"Invalid JSON output: {e}\nOutput: {result.stdout[:500]}"
        )

    return _parse_report(data)


def get_hotspots(
    root: str | Path,
    extensions: Optional[list[str]] = None,
    limit: int = 10,
    timeout: int = 300,
) -> tuple[list[DuplicationHotspot], int]:
    """
    Get files with highest duplication scores.

    Args:
        root: Root directory to analyze
        extensions: File extensions to include
        limit: Maximum number of hotspots to return
        timeout: Timeout in seconds

    Returns:
        Tuple of (list of hotspots, total count)
    """
    report = analyze_similarity(root, extensions, timeout=timeout)
    hotspots = sorted(report.hotspots, key=lambda h: h.duplication_score, reverse=True)
    return hotspots[:limit], len(hotspots)


def _parse_report(data: dict[str, Any]) -> SimilarityReport:
    """Parse JSON data into SimilarityReport."""
    # Parse summary
    summary_data = data.get("summary", {})
    summary = SimilaritySummary(
        files_analyzed=summary_data.get("files_analyzed", 0),
        total_lines=summary_data.get("total_lines", 0),
        clone_pairs_found=summary_data.get("clone_pairs_found", 0),
        estimated_duplication=summary_data.get("estimated_duplication", "0%"),
        analysis_time_ms=summary_data.get("analysis_time_ms", 0),
    )

    # Parse performance
    perf_data = data.get("performance", {})
    performance = SimilarityPerformance(
        loc_per_second=perf_data.get("loc_per_second", 0.0),
        tokens_per_second=perf_data.get("tokens_per_second", 0.0),
        files_per_second=perf_data.get("files_per_second", 0),
        total_tokens=perf_data.get("total_tokens", 0),
        thread_count=perf_data.get("thread_count", 1),
        parallel_enabled=perf_data.get("parallel_enabled", False),
    )

    # Parse timing
    timing_data = data.get("timing", {})
    timing = SimilarityTiming(
        tokenize_ms=timing_data.get("tokenize_ms", 0),
        hash_ms=timing_data.get("hash_ms", 0),
        match_ms=timing_data.get("match_ms", 0),
        total_ms=timing_data.get("total_ms", 0),
    )

    # Parse metrics
    metrics_data = data.get("metrics", {})
    metrics = SimilarityMetrics(
        by_type=metrics_data.get("by_type", {}),
        by_language=metrics_data.get("by_language", {}),
    )

    # Parse hotspots
    hotspots = []
    for h in data.get("hotspots", []):
        hotspots.append(
            DuplicationHotspot(
                file=h.get("file", ""),
                clone_count=h.get("clone_count", 0),
                duplication_score=h.get("duplication_score", 0.0),
                duplicated_lines=h.get("duplicated_lines", 0),
                total_lines=h.get("total_lines", 0),
                recommendation=h.get("recommendation", ""),
            )
        )

    # Parse clones
    clones = []
    for c in data.get("clones", []):
        locations = []
        for loc in c.get("locations", []):
            locations.append(
                CloneLocation(
                    file=loc.get("file", ""),
                    start_line=loc.get("start_line", 0),
                    end_line=loc.get("end_line", 0),
                    snippet_preview=loc.get("snippet_preview", ""),
                )
            )
        clones.append(
            CloneEntry(
                id=c.get("id", ""),
                type=c.get("type", "Type-1"),
                similarity=c.get("similarity", 1.0),
                locations=locations,
                recommendation=c.get("recommendation", ""),
            )
        )

    return SimilarityReport(
        summary=summary,
        performance=performance,
        timing=timing,
        metrics=metrics,
        hotspots=hotspots,
        clones=clones,
    )


def report_to_dict(report: SimilarityReport) -> dict[str, Any]:
    """Convert SimilarityReport to dictionary for JSON serialization."""
    return {
        "summary": {
            "files_analyzed": report.summary.files_analyzed,
            "total_lines": report.summary.total_lines,
            "clone_pairs_found": report.summary.clone_pairs_found,
            "estimated_duplication": report.summary.estimated_duplication,
            "analysis_time_ms": report.summary.analysis_time_ms,
        },
        "performance": {
            "loc_per_second": report.performance.loc_per_second,
            "tokens_per_second": report.performance.tokens_per_second,
            "files_per_second": report.performance.files_per_second,
            "total_tokens": report.performance.total_tokens,
            "thread_count": report.performance.thread_count,
            "parallel_enabled": report.performance.parallel_enabled,
        },
        "timing": {
            "tokenize_ms": report.timing.tokenize_ms,
            "hash_ms": report.timing.hash_ms,
            "match_ms": report.timing.match_ms,
            "total_ms": report.timing.total_ms,
        },
        "metrics": {
            "by_type": report.metrics.by_type,
            "by_language": report.metrics.by_language,
        },
        "hotspots": [
            {
                "file": h.file,
                "clone_count": h.clone_count,
                "duplication_score": h.duplication_score,
                "duplicated_lines": h.duplicated_lines,
                "total_lines": h.total_lines,
                "recommendation": h.recommendation,
            }
            for h in report.hotspots
        ],
        "clones": [
            {
                "id": c.id,
                "type": c.type,
                "similarity": c.similarity,
                "locations": [
                    {
                        "file": loc.file,
                        "start_line": loc.start_line,
                        "end_line": loc.end_line,
                        "snippet_preview": loc.snippet_preview,
                    }
                    for loc in c.locations
                ],
                "recommendation": c.recommendation,
            }
            for c in report.clones
        ],
    }
