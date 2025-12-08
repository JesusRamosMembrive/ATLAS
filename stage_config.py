"""
Shared configuration, thresholds, and helpers for stage detection logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import (
    Dict,
    Any,
    Iterable,
    Iterator,
    List,
    Optional,
    Sequence,
    Set,
    Tuple,
    TYPE_CHECKING,
)

if TYPE_CHECKING:
    from code_map.index import SymbolIndex
    from code_map.models import FileSummary

# ---------------------------------------------------------------------------
# Stage Detection Constants
# ---------------------------------------------------------------------------

# Stage 2 sub-stage boundaries for progress tracking
STAGE2_EARLY_MAX_FILES = 8
STAGE2_EARLY_MAX_LOC = 1000
STAGE2_MID_MAX_FILES = 15
STAGE2_MID_MAX_LOC = 2000

# Warning thresholds for confidence adjustment
HIGH_LOC_WARNING_MIN_FILES = 5  # Few files but high LOC suggests refactoring needed
HIGH_LOC_WARNING_THRESHOLD = 1500  # LOC threshold for the warning
MANY_FILES_NO_PATTERNS_THRESHOLD = (
    30  # Many files without patterns suggests missing structure
)

# ---------------------------------------------------------------------------
# Stage metadata


@dataclass(frozen=True)
class StageThresholds:
    """Thresholds that describe boundaries for a project stage."""

    max_files: Optional[int]
    max_loc: Optional[int]
    max_patterns: Optional[int]
    max_arch_layers: Optional[int]


@dataclass(frozen=True)
class StageDefinition:
    """Declarative metadata for a stage."""

    number: int
    label: str
    description: str
    thresholds: StageThresholds


STAGE_DEFINITIONS: Tuple[StageDefinition, ...] = (
    StageDefinition(
        number=1,
        label="Prototyping",
        description="Mantén todo simple. Una sola pieza de código para validar la idea.",
        thresholds=StageThresholds(
            max_files=3,  # Proof of concept fits in 1-3 files
            max_loc=500,  # Under 500 LOC total keeps it simple and easy to iterate
            max_patterns=0,  # No design patterns yet - keep it straightforward
            max_arch_layers=0,  # No architectural layers - single-level code structure
        ),
    ),
    StageDefinition(
        number=2,
        label="Structuring",
        description="Divide el código cuando duela. Añade estructura ligera y máximo 1–2 patrones.",
        thresholds=StageThresholds(
            max_files=20,  # Enough files for basic organization (models, services, utils)
            max_loc=3000,  # ~3K LOC allows meaningful structure without complexity
            max_patterns=3,  # 1-3 design patterns (e.g., Factory, Strategy, Observer)
            max_arch_layers=3,  # Basic layering (presentation, business, data)
        ),
    ),
    StageDefinition(
        number=3,
        label="Scaling",
        description="Patrones y arquitectura completa son válidos si resuelven dolores reales.",
        thresholds=StageThresholds(
            max_files=None,  # No limit - full production scale
            max_loc=None,  # No limit - enterprise-level codebase
            max_patterns=None,  # Full pattern usage when justified by real pain points
            max_arch_layers=None,  # Complete architectural freedom (microservices, DDD, etc.)
        ),
    ),
)

# ---------------------------------------------------------------------------
# Pattern and structure heuristics

PATTERN_KEYWORDS: Dict[str, Tuple[str, ...]] = {
    "Factory Pattern": ("factory", "Factory", "create_"),
    "Singleton": ("singleton", "Singleton", "getInstance"),
    "Observer": ("observer", "Observer", "subscribe", "emit"),
    "Strategy": ("strategy", "Strategy"),
    "Repository": ("repository", "Repository", "repo"),
    "Service Layer": ("service", "Service", "services/"),
    "Adapter": ("adapter", "Adapter", "adapters/"),
    "Middleware": ("middleware", "Middleware"),
}

ARCHITECTURE_FOLDERS: Tuple[str, ...] = (
    "models",
    "views",
    "controllers",
    "services",
    "repositories",
    "middleware",
    "adapters",
    "interfaces",
    "handlers",
    "routers",
    "api",
    "core",
    "domain",
    "infrastructure",
    "application",
    "presentation",
)

IGNORE_DIRS: Set[str] = {
    ".venv",
    "venv",
    "env",
    "ENV",
    "node_modules",
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    "build",
    "dist",
    ".eggs",
    "*.egg-info",
    ".tox",
    ".nox",
    "htmlcov",
    ".coverage",
    ".idea",
    ".vscode",
    "target",
    "bin",
    "obj",
    "CMakeFiles",
    "cmake-build-debug",
    "cmake-build-release",
    ".qmake.stash",
}

DEFAULT_CODE_EXTENSIONS: Tuple[str, ...] = (
    ".py",
    ".js",
    ".ts",
    ".jsx",
    ".tsx",
    ".java",
    ".go",
    ".rs",
    ".rb",
    ".php",
    ".cpp",
    ".cc",
    ".cxx",
    ".c",
    ".h",
    ".hpp",
    ".hxx",
)

# ---------------------------------------------------------------------------
# Metrics and diagnostics


@dataclass(frozen=True)
class StageMetrics:
    """Aggregated metrics used to evaluate which stage fits best."""

    file_count: int
    lines_of_code: int
    complexity: Dict[str, int]
    complexity_distribution: Dict[str, int]
    top_complex_functions: List[Dict[str, Any]]
    problematic_functions: List[Dict[str, Any]]
    directory_count: int
    patterns_found: List[str]
    architectural_folders: List[str]


@dataclass(frozen=True)
class StageDiagnostics:
    """Additional data explaining how a stage recommendation was produced."""

    applied_stage: StageDefinition
    warnings: Tuple[str, ...]


@dataclass(frozen=True)
class StageAssessment:
    """Final evaluation result with metrics and justification."""

    recommended_stage: int
    confidence: str
    reasons: List[str]
    metrics: StageMetrics
    diagnostics: StageDiagnostics


# ---------------------------------------------------------------------------
# Public helpers


def should_ignore(path: Path) -> bool:
    """Return True when any segment of the path is an ignored folder."""

    return any(part.startswith(".") or part in IGNORE_DIRS for part in path.parts)


def collect_metrics(
    root: Path,
    *,
    symbol_index: Optional["SymbolIndex"] = None,
    extensions: Sequence[str] = DEFAULT_CODE_EXTENSIONS,
) -> StageMetrics:
    """
    Collect project metrics needed for stage evaluation.

    If `symbol_index` is provided, it will be used as the primary source for files.
    """

    root = root.expanduser().resolve()
    extension_set = {ext if ext.startswith(".") else f".{ext}" for ext in extensions}

    files: List[Path] = []
    if symbol_index:
        summaries = _filter_summaries(symbol_index.get_all(), root, extension_set)
        files = [summary.path for summary in summaries]

    if not files:
        files = list(_iter_code_files(root, extension_set))

    unique_files = sorted(set(files))
    file_count = len(unique_files)
    loc = sum(_count_file_lines(path) for path in unique_files)

    complexity_stats = {"total": 0, "max": 0, "avg": 0}
    complexity_dist = {"low": 0, "medium": 0, "high": 0, "extreme": 0}
    top_complex = []
    problematic = []

    if symbol_index:
        total_complexity = 0
        max_complexity = 0
        count_functions = 0
        
        all_functions = []

        for summary in summaries:
            for symbol in summary.symbols:
                c = symbol.metrics.get("complexity", 1) if symbol.metrics else 1
                # Ensure it's an int
                if isinstance(c, (int, float)):
                    c = int(c)
                else:
                    c = 1
                
                total_complexity += c
                max_complexity = max(max_complexity, c)
                
                if symbol.kind in ("function", "method"):
                    count_functions += 1
                    
                    # Distribution
                    if c <= 5:
                        complexity_dist["low"] += 1
                    elif c <= 10:
                        complexity_dist["medium"] += 1
                    elif c <= 25:
                        complexity_dist["high"] += 1
                    else:
                        complexity_dist["extreme"] += 1
                    
                    entry = {
                        "name": symbol.name,
                        "complexity": c,
                        "path": str(summary.path),
                        "lineno": symbol.lineno
                    }
                    all_functions.append(entry)
                    
                    if c > 5:
                        problematic.append(entry)
        
        complexity_stats["total"] = total_complexity
        complexity_stats["max"] = max_complexity
        if count_functions > 0:
            complexity_stats["avg"] = int(total_complexity / count_functions)
            
        # Get top 5 complex functions
        top_complex = sorted(all_functions, key=lambda x: x["complexity"], reverse=True)[:5]
        
        # Sort problematic by complexity desc
        problematic.sort(key=lambda x: x["complexity"], reverse=True)

    directories: Set[Path] = set()
    for path in unique_files:
        try:
            path.relative_to(root)
        except ValueError:
            continue
        directories.add(path.parent)
    directory_count = len(directories)

    patterns = detect_patterns(unique_files, root)
    architecture = detect_architectural_folders(root, directories)

    return StageMetrics(
        file_count=file_count,
        lines_of_code=loc,
        complexity=complexity_stats,
        complexity_distribution=complexity_dist,
        top_complex_functions=top_complex,
        problematic_functions=problematic,
        directory_count=directory_count,
        patterns_found=patterns,
        architectural_folders=architecture,
    )


def evaluate_stage(metrics: StageMetrics) -> StageAssessment:
    """Evaluate the provided metrics and return a stage recommendation."""

    reasons: List[str] = []
    warnings: List[str] = []

    definition = _select_stage_definition(metrics, reasons)
    confidence = _determine_confidence(metrics, definition, warnings, reasons)

    _append_substage_hint(metrics, definition, reasons)

    diagnostics = StageDiagnostics(applied_stage=definition, warnings=tuple(warnings))
    return StageAssessment(
        recommended_stage=definition.number,
        confidence=confidence,
        reasons=reasons,
        metrics=metrics,
        diagnostics=diagnostics,
    )


def detect_patterns(files: Iterable[Path], root: Path) -> List[str]:
    """Detect design patterns using simple filename heuristics."""

    root = root.expanduser().resolve()
    matches: Set[str] = set()

    for pattern, keywords in PATTERN_KEYWORDS.items():
        for keyword in keywords:
            keyword_lower = keyword.lower()
            if any(
                keyword_lower in segment.lower()
                for path in files
                for segment in path.parts
            ):
                matches.add(pattern)
                break

    return sorted(matches)


def detect_architectural_folders(root: Path, directories: Iterable[Path]) -> List[str]:
    """Detect architectural folder names inside the project."""

    found: Set[str] = set()
    for directory in directories:
        try:
            relative = directory.relative_to(root)
        except ValueError:
            relative = directory
        if should_ignore(relative):
            continue
        dirname = directory.name.lower()
        for marker in ARCHITECTURE_FOLDERS:
            if marker in dirname:
                found.add(marker)
                break
    return sorted(found)


# ---------------------------------------------------------------------------
# Internal helpers


def _filter_summaries(
    summaries: Iterable["FileSummary"],
    root: Path,
    extensions: Set[str],
) -> List["FileSummary"]:
    filtered: List["FileSummary"] = []
    for summary in summaries:
        path = summary.path.resolve()
        if not path.suffix or path.suffix.lower() not in extensions:
            continue
        try:
            relative = path.relative_to(root)
        except ValueError:
            # File is outside root; ignore it for stage heuristics
            continue
        if should_ignore(relative):
            continue
        filtered.append(summary)
    return filtered


def _iter_code_files(root: Path, extensions: Set[str]) -> Iterator[Path]:
    for ext in extensions:
        yield from (
            path
            for path in root.rglob(f"*{ext}")
            if _path_within_root(path, root)
            and not should_ignore(path.relative_to(root))
        )


def _count_file_lines(path: Path) -> int:
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            return sum(1 for _ in handle)
    except OSError:
        return 0


def _path_within_root(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _select_stage_definition(
    metrics: StageMetrics, reasons: List[str]
) -> StageDefinition:
    files = metrics.file_count
    loc = metrics.lines_of_code
    patterns = len(metrics.patterns_found)
    layers = len(metrics.architectural_folders)

    # Scoring system: cada métrica contribuye a un score para cada stage
    # Stage is selected when score >= threshold (2 out of 4 metrics must fit)
    stage = STAGE_DEFINITIONS[-1]  # Default to Stage 3

    for definition in STAGE_DEFINITIONS:
        thresholds = definition.thresholds
        score = 0

        files_ok = thresholds.max_files is None or files <= thresholds.max_files
        loc_ok = thresholds.max_loc is None or loc < thresholds.max_loc
        patterns_ok = (
            thresholds.max_patterns is None or patterns <= thresholds.max_patterns
        )
        layers_ok = (
            thresholds.max_arch_layers is None or layers <= thresholds.max_arch_layers
        )

        if files_ok:
            score += 1
        if loc_ok:
            score += 1
        if patterns_ok:
            score += 1
        if layers_ok:
            score += 1

        # Stage fits if at least 3 out of 4 metrics are within bounds
        # This filters out single-metric spikes (like high LOC with simple structure)
        if score >= 3:
            stage = definition
            break

    if stage.number == 1:
        reasons.append(f"Very small codebase ({files} files, ~{loc} LOC)")
        reasons.append("Appropriate for prototyping stage")
    elif stage.number == 2:
        reasons.append(f"Medium codebase ({files} files, ~{loc} LOC)")
        if metrics.architectural_folders:
            arch_count = len(metrics.architectural_folders)
            reasons.append(f"Basic architecture present: {arch_count} layer(s)")
            if arch_count > 3:
                reasons.append("⚠️  Consider if architecture is justified")
            else:
                reasons.append("Structure is appropriate for Stage 2")
        else:
            reasons.append("No clear architecture yet - good for Stage 2")

        if metrics.patterns_found:
            joined = ", ".join(metrics.patterns_found[:2])
            reasons.append(f"Some patterns in use: {joined}")
            if len(metrics.patterns_found) > 2:
                reasons.append("⚠️  Multiple patterns - ensure they're justified")
        else:
            reasons.append("No design patterns detected yet")
    else:
        reasons.append(f"Large or complex codebase ({files} files, ~{loc} LOC)")
        if metrics.patterns_found:
            reasons.append(
                f"Multiple patterns detected: {', '.join(metrics.patterns_found[:4])}"
            )
        if len(metrics.architectural_folders) > 4:
            reasons.append(
                f"Complex architecture: {len(metrics.architectural_folders)} layers"
            )

    return stage


def _determine_confidence(
    metrics: StageMetrics,
    definition: StageDefinition,
    warnings: List[str],
    reasons: List[str],
) -> str:
    confidence = "high"

    if (
        metrics.file_count <= HIGH_LOC_WARNING_MIN_FILES
        and metrics.lines_of_code > HIGH_LOC_WARNING_THRESHOLD
    ):
        confidence = "medium"
        warnings.append(
            "Few files but high LOC - consider refactoring into smaller modules"
        )
        reasons.append("⚠️  Few files but high LOC - consider refactoring")

    if (
        metrics.file_count > MANY_FILES_NO_PATTERNS_THRESHOLD
        and not metrics.patterns_found
    ):
        confidence = "medium"
        warnings.append(
            "Many files without clear patterns - structure might be missing"
        )
        reasons.append("⚠️  Many files but no patterns - may need structure")

    return confidence


def _append_substage_hint(
    metrics: StageMetrics, definition: StageDefinition, reasons: List[str]
) -> None:
    if definition.number != 2:
        return

    files = metrics.file_count
    loc = metrics.lines_of_code

    if files <= STAGE2_EARLY_MAX_FILES and loc < STAGE2_EARLY_MAX_LOC:
        reasons.append("📍 Early Stage 2 - just starting to structure")
    elif files <= STAGE2_MID_MAX_FILES and loc < STAGE2_MID_MAX_LOC:
        reasons.append("📍 Mid Stage 2 - structure emerging")
    else:
        reasons.append("📍 Late Stage 2 - consider Stage 3 transition")
