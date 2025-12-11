# SPDX-License-Identifier: MIT
"""
Utilidades para inicializar y verificar los archivos Stage-Aware
que consumen Claude Code y Codex CLI.
"""

from __future__ import annotations

import asyncio
import shutil
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Literal, Optional, Sequence, Tuple

from stage_config import StageMetrics, collect_metrics

if TYPE_CHECKING:  # pragma: no cover
    from .index import SymbolIndex

AgentSelection = Literal["claude", "codex", "gemini", "both", "all"]

CLAUDE_REQUIRED: Tuple[str, ...] = (
    ".claude/00-project-brief.md",
    ".claude/01-current-phase.md",
    ".claude/02-stage1-rules.md",
    ".claude/02-stage2-rules.md",
    ".claude/02-stage3-rules.md",
    ".claude/agents/architect-generic.md",
    ".claude/agents/code-reviewer-optimized.md",
    ".claude/agents/implementer.md",
    ".claude/agents/stage-keeper-architecture.md",
)

CLAUDE_OPTIONAL: Tuple[str, ...] = (
    "CLAUDE.md",
    ".claude/settings.local.json",
)

CODEX_REQUIRED: Tuple[str, ...] = (
    ".codex/AGENTS.md",
    ".codex/stage1-rules.md",
    ".codex/stage2-rules.md",
    ".codex/stage3-rules.md",
)

GEMINI_REQUIRED: Tuple[str, ...] = (
    ".gemini/CUSTOM_INSTRUCTIONS.md",
    ".gemini/00-project-brief.md",
    ".gemini/01-current-phase.md",
    ".gemini/02-stage1-rules.md",
    ".gemini/02-stage2-rules.md",
    ".gemini/02-stage3-rules.md",
)

DOCS_REQUIRED: Tuple[str, ...] = (
    "docs/QUICK_START.md",
    "docs/STAGES_COMPARISON.md",
    "docs/STAGE_CRITERIA.md",
    "docs/GUIDE.md",
    "docs/CLAUDE_CODE_REFERENCE.md",
    "docs/CODEX_CLI_REFERENCE.md",
)

SUPERCLAUDE_REPO_URL = "https://github.com/SuperClaude-Org/SuperClaude_Framework.git"
SUPERCLAUDE_BRANCH = "master"
SUPERCLAUDE_REFERENCE_COUNTS: Dict[str, int] = {
    "plugin_commands": 3,
    "specialist_agents": 16,
    "behavior_modes": 7,
    "mcp_servers": 8,
}
SUPERCLAUDE_DOC_EXPORTS: Tuple[Tuple[str, str], ...] = (
    ("README.md", "docs/superclaude/README.md"),
    ("AGENTS.md", "docs/superclaude/AGENTS.md"),
    ("docs/user-guide/commands.md", "docs/superclaude/commands.md"),
    ("docs/user-guide/agents.md", "docs/superclaude/agents.md"),
    ("docs/user-guide/modes.md", "docs/superclaude/modes.md"),
    ("docs/user-guide/mcp-servers.md", "docs/superclaude/mcp-servers.md"),
)


@dataclass
class FileStatus:
    """Representa el estado de un conjunto de archivos esperados."""

    expected: Tuple[str, ...]
    present: List[str]
    missing: List[str]

    @property
    def complete(self) -> bool:
        return not self.missing


def _collect_file_status(root: Path, required: Sequence[str]) -> FileStatus:
    present: List[str] = []
    missing: List[str] = []
    for relative in required:
        path = (root / relative).resolve()
        if path.exists():
            present.append(relative)
        else:
            missing.append(relative)
    return FileStatus(expected=tuple(required), present=present, missing=missing)


def _build_agent_payload(
    root: Path, required: Tuple[str, ...], optional: Tuple[str, ...] = ()
) -> Dict[str, object]:
    mandatory = _collect_file_status(root, required)
    optional_status = (
        _collect_file_status(root, optional)
        if optional
        else FileStatus(optional, [], [])
    )
    return {
        "expected": list(mandatory.expected),
        "present": mandatory.present,
        "missing": mandatory.missing,
        "optional": {
            "expected": list(optional_status.expected),
            "present": optional_status.present,
            "missing": optional_status.missing,
        },
        "installed": mandatory.complete,
    }


def _detect_stage(
    root: Path, *, metrics: Optional[StageMetrics] = None
) -> Dict[str, object]:
    try:
        import assess_stage  # noqa: WPS433 (import at runtime)
    except Exception as exc:  # pragma: no cover - fallback path
        return {
            "available": False,
            "error": f"assess_stage no disponible: {exc}",
            "recommended_stage": None,
            "confidence": None,
            "reasons": [],
            "metrics": None,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

    try:
        assessment = assess_stage.assess_stage(root, metrics=metrics)
    except Exception as exc:  # pragma: no cover - runtime errors
        return {
            "available": False,
            "error": f"Error al evaluar la etapa: {exc}",
            "recommended_stage": None,
            "confidence": None,
            "reasons": [],
            "metrics": None,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

    if not assessment:
        return {
            "available": False,
            "error": "No se pudo determinar la etapa del proyecto.",
            "recommended_stage": None,
            "confidence": None,
            "reasons": [],
            "metrics": None,
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

    return {
        "available": True,
        "error": None,
        "recommended_stage": assessment.get("recommended_stage"),
        "confidence": assessment.get("confidence"),
        "reasons": assessment.get("reasons", [])[:5],
        "metrics": assessment.get("metrics"),
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }


def _compute_status(
    root: Path, metrics: Optional[StageMetrics] = None
) -> Dict[str, object]:
    resolved_root = root.expanduser().resolve()
    claude_payload = _build_agent_payload(
        resolved_root, CLAUDE_REQUIRED, CLAUDE_OPTIONAL
    )
    codex_payload = _build_agent_payload(resolved_root, CODEX_REQUIRED)
    gemini_payload = _build_agent_payload(resolved_root, GEMINI_REQUIRED)
    docs_status = _collect_file_status(resolved_root, DOCS_REQUIRED)

    return {
        "root_path": str(resolved_root),
        "claude": claude_payload,
        "codex": codex_payload,
        "gemini": gemini_payload,
        "docs": {
            "expected": list(docs_status.expected),
            "present": docs_status.present,
            "missing": docs_status.missing,
            "complete": docs_status.complete,
        },
        "detection": _detect_stage(resolved_root, metrics=metrics),
    }


async def stage_status(
    root: Path, *, index: Optional["SymbolIndex"] = None
) -> Dict[str, object]:
    """Obtiene el estado actual de los archivos stage-aware para un root dado."""
    metrics: Optional[StageMetrics] = None
    if index is not None:
        metrics = await asyncio.to_thread(collect_metrics, root, symbol_index=index)
    return await asyncio.to_thread(_compute_status, root, metrics)


def _run_initializer_sync(command: List[str], cwd: str) -> Tuple[int, str, str]:
    """Run initializer subprocess synchronously (for use in thread)."""
    import subprocess

    result = subprocess.run(
        command,
        capture_output=True,
        cwd=cwd,
        text=True,
        errors="replace",
    )
    return result.returncode, result.stdout, result.stderr


async def run_initializer(
    root: Path, agents: AgentSelection, *, force: bool = False
) -> Dict[str, object]:
    """
    Ejecuta init_project.py contra el root indicado para instalar instrucciones.

    Args:
        root: Directorio raíz del proyecto
        agents: Selección de agentes a instalar
        force: Si True, fuerza reinstalación limpia (elimina archivos existentes)
    """
    repo_root = Path(__file__).resolve().parents[1]
    script_path = repo_root / "init_project.py"
    target = root.expanduser().resolve()

    command = [sys.executable, str(script_path), str(target), "--existing"]

    # Mapear selección de agente al argumento CLI
    if agents == "all":
        # "all" significa Claude + Codex + Gemini, pero el CLI usa "both" para Claude+Codex
        # y necesitamos ejecutar separadamente para Gemini
        command.extend(["--agent", "both"])
    elif agents in {"claude", "codex", "gemini"}:
        command.extend(["--agent", agents])
    else:
        # "both" = Claude + Codex (comportamiento original)
        command.extend(["--agent", "both"])

    if force:
        command.append("--force")

    command.append("--skip-claude-init")

    try:
        # Use subprocess.run in a thread to avoid Windows asyncio subprocess issues
        returncode, stdout, stderr = await asyncio.to_thread(
            _run_initializer_sync, command, str(repo_root)
        )

        status_payload = await stage_status(target)

        return {
            "success": returncode == 0,
            "exit_code": returncode,
            "command": command,
            "stdout": stdout,
            "stderr": stderr,
            "status": status_payload,
        }
    except Exception as exc:
        # Return error as structured response rather than raising
        status_payload = await stage_status(target)
        return {
            "success": False,
            "exit_code": -1,
            "command": command,
            "stdout": "",
            "stderr": f"Error executing subprocess: {exc}",
            "status": status_payload,
        }


def _run_command_sync(
    command: Sequence[str], cwd: Optional[str] = None
) -> Tuple[int, str, str]:
    """Run command synchronously (for use in thread)."""
    import subprocess

    result = subprocess.run(
        list(command),
        capture_output=True,
        cwd=cwd,
        text=True,
        errors="replace",
    )
    return result.returncode, result.stdout, result.stderr


async def install_superclaude_framework(root: Path) -> Dict[str, object]:
    """
    Clona o actualiza SuperClaude Framework y sincroniza sus assets principales.
    """
    workspace = root.expanduser().resolve()
    cache_root = workspace / ".stage-cache"
    clone_dir = cache_root / "superclaude-framework"

    logs: List[Dict[str, object]] = []
    copied_paths: List[str] = []
    source_commit: Optional[str] = None
    component_counts: Dict[str, int] = {}
    error_message: Optional[str] = None

    async def run_command(
        command: Sequence[str], *, cwd: Optional[Path] = None
    ) -> Dict[str, object]:
        # Use subprocess.run in a thread to avoid Windows asyncio subprocess issues
        returncode, stdout, stderr = await asyncio.to_thread(
            _run_command_sync, command, str(cwd) if cwd else None
        )
        entry: Dict[str, object] = {
            "command": list(command),
            "stdout": stdout,
            "stderr": stderr,
            "exit_code": returncode,
        }
        logs.append(entry)
        if returncode != 0:
            raise RuntimeError(
                f"El comando {' '.join(command)} terminó con código {returncode}",
            )
        return entry

    def _record_copy(dest: Path) -> None:
        try:
            copied_paths.append(str(dest.relative_to(workspace)))
        except ValueError:  # pragma: no cover - defensive
            copied_paths.append(str(dest))

    def _copytree_sync(src: Path, dest: Path) -> None:
        if dest.exists():
            shutil.rmtree(dest)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src, dest)

    def _copyfile_sync(src: Path, dest: Path) -> None:
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)

    async def copy_tree(relative_src: str, relative_dest: str) -> None:
        src = (clone_dir / relative_src).resolve()
        dest = (workspace / relative_dest).resolve()
        if not src.exists():
            return
        await asyncio.to_thread(_copytree_sync, src, dest)
        logs.append(
            {
                "command": ["copytree", str(src), str(dest)],
                "stdout": f"Copiado {relative_src} → {relative_dest}",
                "stderr": "",
                "exit_code": 0,
            }
        )
        _record_copy(dest)

    async def copy_file(relative_src: str, relative_dest: str) -> None:
        src = (clone_dir / relative_src).resolve()
        dest = (workspace / relative_dest).resolve()
        if not src.exists():
            return
        await asyncio.to_thread(_copyfile_sync, src, dest)
        logs.append(
            {
                "command": ["copyfile", str(src), str(dest)],
                "stdout": f"Copiado {relative_src} → {relative_dest}",
                "stderr": "",
                "exit_code": 0,
            }
        )
        _record_copy(dest)

    try:
        cache_root.mkdir(parents=True, exist_ok=True)
        if clone_dir.exists() and (clone_dir / ".git").exists():
            await run_command(
                [
                    "git",
                    "-C",
                    str(clone_dir),
                    "fetch",
                    "--depth",
                    "1",
                    "origin",
                    SUPERCLAUDE_BRANCH,
                ]
            )
            await run_command(
                [
                    "git",
                    "-C",
                    str(clone_dir),
                    "reset",
                    "--hard",
                    f"origin/{SUPERCLAUDE_BRANCH}",
                ]
            )
        else:
            if clone_dir.exists():
                await asyncio.to_thread(shutil.rmtree, clone_dir)
            await run_command(
                [
                    "git",
                    "clone",
                    "--depth",
                    "1",
                    "--branch",
                    SUPERCLAUDE_BRANCH,
                    SUPERCLAUDE_REPO_URL,
                    str(clone_dir),
                ]
            )

        rev_entry = await run_command(
            ["git", "-C", str(clone_dir), "rev-parse", "HEAD"]
        )
        stdout = rev_entry["stdout"]
        source_commit = str(stdout).strip() if stdout else None

        await copy_tree("plugins/superclaude", ".claude/plugins/superclaude")
        await copy_tree(".claude/skills", ".claude/skills/superclaude")

        for relative_src, relative_dest in SUPERCLAUDE_DOC_EXPORTS:
            await copy_file(relative_src, relative_dest)

        plugin_commands_dir = (
            workspace / ".claude" / "plugins" / "superclaude" / "commands"
        )
        plugin_command_count = (
            len(list(plugin_commands_dir.glob("*.md")))
            if plugin_commands_dir.exists()
            else 0
        )
        component_counts = dict(SUPERCLAUDE_REFERENCE_COUNTS)
        if plugin_command_count:
            component_counts["plugin_commands"] = plugin_command_count

    except Exception as exc:  # pragma: no cover - runtime protection
        error_message = str(exc)

    success = error_message is None
    timestamp = datetime.now(timezone.utc).isoformat() if success else None

    if not component_counts:
        component_counts = dict(SUPERCLAUDE_REFERENCE_COUNTS)

    return {
        "success": success,
        "error": error_message,
        "installed_at": timestamp,
        "source_repo": SUPERCLAUDE_REPO_URL,
        "source_commit": source_commit,
        "component_counts": component_counts,
        "copied_paths": copied_paths,
        "logs": logs,
    }
