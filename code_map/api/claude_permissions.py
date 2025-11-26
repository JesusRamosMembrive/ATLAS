# SPDX-License-Identifier: MIT
"""
Claude Code permissions management API.

Provides endpoints to read and modify Claude Code permissions
in .claude/settings.local.json for the current project.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .deps import get_app_state

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/claude-permissions", tags=["claude-permissions"])


# =============================================================================
# Schemas
# =============================================================================


class ClaudePermissions(BaseModel):
    """Claude Code permissions structure"""
    allow: List[str] = []
    deny: List[str] = []
    ask: List[str] = []


class ClaudeSettings(BaseModel):
    """Claude Code settings.local.json structure"""
    permissions: ClaudePermissions = ClaudePermissions()


class PermissionsResponse(BaseModel):
    """Response for permissions endpoint"""
    settings_path: str
    exists: bool
    permissions: ClaudePermissions
    recommended_permissions: List[str]


class AddPermissionsRequest(BaseModel):
    """Request to add permissions"""
    permissions: List[str]


class AddPermissionsResponse(BaseModel):
    """Response after adding permissions"""
    success: bool
    added: List[str]
    already_present: List[str]
    current_permissions: ClaudePermissions


# =============================================================================
# Recommended permissions for Agent UI
# =============================================================================

RECOMMENDED_PERMISSIONS = [
    "Read",
    "Write",
    "Edit",
    "Glob",
    "Grep",
    "TodoWrite",
    "NotebookEdit",
    "WebFetch",
    "WebSearch",
    "Task",
]


# =============================================================================
# Helpers
# =============================================================================


def get_settings_path(root_path: Path) -> Path:
    """Get path to .claude/settings.local.json"""
    return root_path / ".claude" / "settings.local.json"


def read_settings(settings_path: Path) -> ClaudeSettings:
    """Read Claude settings from file"""
    if not settings_path.exists():
        return ClaudeSettings()

    try:
        with open(settings_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return ClaudeSettings(**data)
    except (json.JSONDecodeError, Exception) as e:
        logger.warning(f"Failed to parse settings file: {e}")
        return ClaudeSettings()


def write_settings(settings_path: Path, settings: ClaudeSettings) -> None:
    """Write Claude settings to file"""
    # Ensure .claude directory exists
    settings_path.parent.mkdir(parents=True, exist_ok=True)

    with open(settings_path, "w", encoding="utf-8") as f:
        json.dump(settings.model_dump(), f, indent=2)


# =============================================================================
# Endpoints
# =============================================================================


@router.get("", response_model=PermissionsResponse)
async def get_permissions() -> PermissionsResponse:
    """
    Get current Claude Code permissions for the project.

    Returns the current permissions from .claude/settings.local.json
    along with recommended permissions for the Agent UI.
    """
    state = get_app_state()
    root_path = Path(state.root_path)
    settings_path = get_settings_path(root_path)

    settings = read_settings(settings_path)

    # Calculate which recommended permissions are missing
    current_allow = set(settings.permissions.allow)
    missing_recommended = [
        p for p in RECOMMENDED_PERMISSIONS
        if p not in current_allow
    ]

    return PermissionsResponse(
        settings_path=str(settings_path),
        exists=settings_path.exists(),
        permissions=settings.permissions,
        recommended_permissions=missing_recommended,
    )


@router.post("/add", response_model=AddPermissionsResponse)
async def add_permissions(request: AddPermissionsRequest) -> AddPermissionsResponse:
    """
    Add permissions to Claude Code settings.

    Adds the specified permissions to the allow list in
    .claude/settings.local.json. Creates the file if it doesn't exist.
    """
    state = get_app_state()
    root_path = Path(state.root_path)
    settings_path = get_settings_path(root_path)

    settings = read_settings(settings_path)

    current_allow = set(settings.permissions.allow)
    added = []
    already_present = []

    for perm in request.permissions:
        if perm in current_allow:
            already_present.append(perm)
        else:
            added.append(perm)
            current_allow.add(perm)

    # Update settings with new permissions
    settings.permissions.allow = sorted(list(current_allow))

    # Write back
    write_settings(settings_path, settings)

    logger.info(f"Added permissions: {added}")

    return AddPermissionsResponse(
        success=True,
        added=added,
        already_present=already_present,
        current_permissions=settings.permissions,
    )


@router.post("/add-recommended", response_model=AddPermissionsResponse)
async def add_recommended_permissions() -> AddPermissionsResponse:
    """
    Add all recommended permissions for Agent UI.

    Convenience endpoint that adds all permissions needed for
    the Claude Agent UI to work properly.
    """
    return await add_permissions(AddPermissionsRequest(permissions=RECOMMENDED_PERMISSIONS))


@router.delete("/{permission}")
async def remove_permission(permission: str) -> AddPermissionsResponse:
    """
    Remove a specific permission.
    """
    state = get_app_state()
    root_path = Path(state.root_path)
    settings_path = get_settings_path(root_path)

    settings = read_settings(settings_path)

    if permission in settings.permissions.allow:
        settings.permissions.allow.remove(permission)
        write_settings(settings_path, settings)
        logger.info(f"Removed permission: {permission}")

    return AddPermissionsResponse(
        success=True,
        added=[],
        already_present=[],
        current_permissions=settings.permissions,
    )
