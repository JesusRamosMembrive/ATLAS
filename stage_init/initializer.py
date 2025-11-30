"""
High-level orchestration for stage-aware project initialization.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from .templates import TemplateSummary, copy_templates
from .stage_update import (
    StageUpdateResult,
    append_custom_instructions,
    detect_project_stage,
    run_claude_init,
    update_current_phase_with_stage,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class InitializationConfig:
    """User-provided configuration for initializing a project."""

    project_path: Path
    existing_project: bool
    agent_selection: str  # claude | codex | both
    dry_run: bool = False
    run_claude_init: bool = True


@dataclass
class InitializationResult:
    """Outcome of running the project initializer."""

    dest_dir: Path
    template_summaries: Dict[str, TemplateSummary] = field(default_factory=dict)
    stage_update: Optional[StageUpdateResult] = None
    claude_md_created: bool = False


class ProjectInitializer:
    """Coordinates template installation, stage detection, and reporting."""

    def __init__(
        self,
        config: InitializationConfig,
        *,
        logger_override: Optional[logging.Logger] = None,
    ) -> None:
        self.config = config
        self.log = logger_override or logger
        self.repo_root = Path(__file__).resolve().parents[1]
        self.template_root = self.repo_root / "templates"
        self.now = datetime.now()

    def run(self) -> InitializationResult:
        dest_dir = self._resolve_destination()
        self._ensure_directory(dest_dir)

        placeholders = self._build_placeholders(dest_dir)
        template_sources, template_destinations = self._prepare_template_mappings(
            dest_dir
        )

        summaries = copy_templates(
            template_sources,
            template_destinations,
            placeholders=placeholders,
            dry_run=self.config.dry_run,
            logger_override=self.log,
        )

        if self._should_prepare_claude():
            self._ensure_agents_directory(dest_dir / ".claude")

        claude_cli_invoked = False
        claude_md_created = False
        claude_instructions_appended = False

        if self._should_prepare_claude():
            claude_md_path = dest_dir / "CLAUDE.md"
            claude_templates = template_sources.get("claude")
            instructions_template = (
                claude_templates / "CUSTOM_INSTRUCTIONS.md"
                if claude_templates
                else None
            )

            if self.config.run_claude_init and not self.config.dry_run:
                claude_cli_invoked = True
                claude_md_created = run_claude_init(
                    dest_dir, dry_run=False, logger_override=self.log
                )
            elif self.config.run_claude_init and self.config.dry_run:
                claude_cli_invoked = True
                run_claude_init(dest_dir, dry_run=True, logger_override=self.log)

            if not self.config.dry_run and not claude_md_path.exists():
                claude_md_created = self._write_basic_claude_md(
                    claude_md_path, dest_dir.name
                )

            if instructions_template and instructions_template.exists():
                claude_instructions_appended = append_custom_instructions(
                    claude_md_path,
                    instructions_template,
                    dry_run=self.config.dry_run,
                    logger_override=self.log,
                )

        assessment = detect_project_stage(dest_dir)
        current_phase_file = dest_dir / ".claude" / "01-current-phase.md"
        current_phase_updated = False
        if assessment and current_phase_file.exists():
            current_phase_updated = update_current_phase_with_stage(
                current_phase_file,
                assessment,
                dry_run=self.config.dry_run,
                logger_override=self.log,
            )

        stage_result = StageUpdateResult(
            assessment=assessment,
            current_phase_updated=current_phase_updated,
            claude_cli_invoked=claude_cli_invoked,
            claude_instructions_appended=claude_instructions_appended,
        )

        return InitializationResult(
            dest_dir=dest_dir,
            template_summaries=summaries,
            stage_update=stage_result,
            claude_md_created=claude_md_created,
        )

    # ------------------------------------------------------------------ #
    # Internal helpers

    def _resolve_destination(self) -> Path:
        raw_path = self.config.project_path.expanduser()
        if not self.config.existing_project and not raw_path.is_absolute():
            return (Path.cwd() / raw_path).resolve()
        return raw_path.resolve()

    def _ensure_directory(self, path: Path) -> None:
        if path.exists():
            return
        if self.config.dry_run:
            self.log.info("[dry-run] Would create project directory: %s", path)
            return
        path.mkdir(parents=True, exist_ok=True)

    def _build_placeholders(self, dest_dir: Path) -> Dict[str, str]:
        project_name = dest_dir.name
        return {
            "{{PROJECT_NAME}}": project_name,
            "{{DATE}}": self.now.strftime("%Y-%m-%d"),
            "{{YEAR}}": str(self.now.year),
        }

    def _prepare_template_mappings(
        self, dest_dir: Path
    ) -> tuple[Dict[str, Path], Dict[str, Path]]:
        template_sources: Dict[str, Path] = {
            "claude": self.template_root / "basic" / ".claude",
            "docs": self.template_root / "docs",
        }
        template_destinations: Dict[str, Path] = {
            "claude": dest_dir / ".claude",
            "docs": dest_dir / "docs",
        }

        if self._should_prepare_codex():
            template_sources["codex"] = self.template_root / "basic" / ".codex"
            template_destinations["codex"] = dest_dir / ".codex"

        for category, path in template_sources.items():
            if not path.exists():
                raise FileNotFoundError(
                    f"Template directory for {category} not found: {path}"
                )

        return template_sources, template_destinations

    def _ensure_agents_directory(self, claude_dir: Path) -> None:
        if self.config.dry_run:
            return

        subagents_dir = claude_dir / "agents"
        agents_dir = claude_dir / "agents"

        if subagents_dir.exists():
            if agents_dir.exists():
                for entry in subagents_dir.iterdir():
                    target = agents_dir / entry.name
                    if target.exists():
                        self.log.warning(
                            "Agent file already exists, leaving original in place: %s",
                            target,
                        )
                        continue
                    entry.rename(target)
                try:
                    subagents_dir.rmdir()
                except OSError:
                    self.log.warning(
                        "Could not remove deprecated agents directory (not empty): %s",
                        subagents_dir,
                    )
            else:
                subagents_dir.rename(agents_dir)
        elif not agents_dir.exists() and claude_dir.exists():
            agents_dir.mkdir(parents=True, exist_ok=True)

    def _should_prepare_claude(self) -> bool:
        return self.config.agent_selection in {"claude", "both"}

    def _should_prepare_codex(self) -> bool:
        return self.config.agent_selection in {"codex", "both"}

    def _write_basic_claude_md(self, claude_md_path: Path, project_name: str) -> bool:
        content = (
            f"# {project_name}\n\n"
            "This file contains project context and instructions for Claude Code.\n\n"
            "## Project Overview\n\n"
            "*Add project description here*\n\n"
            "## Tech Stack\n\n"
            "*Add technologies used here*\n\n"
            "## Getting Started\n\n"
            "*Add setup instructions here*\n"
        )
        try:
            claude_md_path.write_text(content, encoding="utf-8")
            self.log.info("Created basic CLAUDE.md fallback at %s", claude_md_path)
            return True
        except OSError as exc:
            self.log.warning("Failed to create fallback CLAUDE.md: %s", exc)
            return False
