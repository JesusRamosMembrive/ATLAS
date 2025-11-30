"""
Stage detection and documentation helpers for project initialization.
"""

from __future__ import annotations

import logging
import re
import shutil
import subprocess  # nosec B404 - ejecución controlada de la CLI de Claude
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from stage_config import StageAssessment

logger = logging.getLogger(__name__)


@dataclass
class StageUpdateResult:
    """Captures information about stage detection and file updates."""

    assessment: Optional[StageAssessment]
    current_phase_updated: bool
    claude_cli_invoked: bool
    claude_instructions_appended: bool


def run_claude_init(
    project_path: Path,
    *,
    dry_run: bool = False,
    logger_override: Optional[logging.Logger] = None,
) -> bool:
    """Invoke `claude -p "/init"` within the project path to generate CLAUDE.md."""
    log = logger_override or logger
    if dry_run:
        log.info("[dry-run] Would run 'claude -p /init' in %s", project_path)
        return False

    claude_binary = shutil.which("claude")
    if not claude_binary:
        log.warning("'claude' command not found in PATH")
        return False

    try:
        exec_result = subprocess.run(  # nosec B603 - invocación explícita y validada
            [claude_binary, "-p", "/init"],
            cwd=str(project_path),
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )

        if exec_result.returncode != 0:
            log.warning("claude /init failed: %s", exec_result.stderr.strip())
            return False

        claude_md = project_path / "CLAUDE.md"
        if claude_md.exists():
            log.info("CLAUDE.md generated via claude /init")
            return True
        log.warning("claude /init completed but CLAUDE.md was not generated")
    except subprocess.TimeoutExpired:
        log.warning("claude /init timed out after 2 minutes")
    except Exception as exc:  # pragma: no cover - defensive
        log.warning("Failed to run claude /init: %s", exc)

    return False


def append_custom_instructions(
    claude_md_path: Path,
    instructions_template: Path,
    *,
    dry_run: bool = False,
    logger_override: Optional[logging.Logger] = None,
) -> bool:
    """Append custom instructions to CLAUDE.md if they are not already present."""

    log = logger_override or logger

    if dry_run:
        if claude_md_path.exists():
            log.info("[dry-run] Would append custom instructions to %s", claude_md_path)
        else:
            log.info(
                "[dry-run] Would append custom instructions once CLAUDE.md is created"
            )
        return True

    if not claude_md_path.exists():
        log.warning("CLAUDE.md not found at %s", claude_md_path)
        return False

    try:
        custom_content = instructions_template.read_text(encoding="utf-8")
    except OSError as exc:
        log.warning("Cannot read custom instructions template: %s", exc)
        return False

    try:
        current_content = claude_md_path.read_text(encoding="utf-8")
    except OSError as exc:
        log.warning("Cannot read CLAUDE.md: %s", exc)
        return False

    if "## Custom Workflow Instructions" in current_content:
        log.debug("Custom instructions already present in CLAUDE.md")
        return False

    separator = (
        "\n\n---\n\n# Custom Workflow Instructions\n\n"
        "<!-- Added by stage-aware initializer -->\n\n"
    )
    updated_content = current_content.rstrip() + separator + custom_content

    try:
        claude_md_path.write_text(updated_content, encoding="utf-8")
    except OSError as exc:
        log.warning("Failed to write CLAUDE.md after appending instructions: %s", exc)
        return False

    log.info("Custom instructions appended to %s", claude_md_path)
    return True


def detect_project_stage(
    root: Path, *, precomputed: Optional[StageAssessment] = None
) -> Optional[StageAssessment]:
    """Detect the stage for the given project root."""
    if precomputed is not None:
        return precomputed

    import assess_stage  # local import to avoid optional dependency noise at import time

    assessment = assess_stage.assess_stage(root, return_dataclass=True)
    return assessment


def update_current_phase_with_stage(
    current_phase_file: Path,
    assessment: StageAssessment,
    *,
    dry_run: bool = False,
    logger_override: Optional[logging.Logger] = None,
) -> bool:
    """Inject detected stage details into 01-current-phase.md."""

    log = logger_override or logger
    if dry_run:
        log.info("[dry-run] Would update %s with stage detection", current_phase_file)
        return True

    try:
        content = current_phase_file.read_text(encoding="utf-8")
    except OSError as exc:
        log.warning("Failed to read %s: %s", current_phase_file, exc)
        return False

    stage = assessment.recommended_stage
    confidence = assessment.confidence.title()
    reasons = assessment.reasons
    metrics = assessment.metrics

    stage_section = (
        f"\n\n## 🎯 Detected Stage: Stage {stage} ({confidence} Confidence)\n\n"
        f"**Auto-detected on:** {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
        "**Detection reasoning:**\n"
    )
    for reason in reasons[:5]:
        stage_section += f"- {reason}\n"

    stage_section += (
        "\n**Metrics:**\n"
        f"- Files: {metrics.file_count}\n"
        f"- LOC: ~{metrics.lines_of_code}\n"
        f"- Patterns: "
        f"{', '.join(metrics.patterns_found[:3]) if metrics.patterns_found else 'None'}\n"
        "\n**Recommended actions:**\n"
        f"- Follow rules in `.claude/02-stage{stage}-rules.md`\n"
        "- Use stage-aware agents for guidance\n"
        "- Re-assess stage after significant changes\n"
    )

    section_pattern = re.compile(r"## 🎯 Detected Stage:.*?(?=\n##|\Z)", re.DOTALL)
    if section_pattern.search(content):
        updated_content = section_pattern.sub(stage_section.strip(), content)
    else:
        updated_content = content.rstrip() + stage_section

    try:
        current_phase_file.write_text(updated_content, encoding="utf-8")
    except OSError as exc:
        log.warning("Failed to write %s: %s", current_phase_file, exc)
        return False

    log.info("Updated %s with detected stage information", current_phase_file)
    return True
