# SPDX-License-Identifier: MIT
"""
Tool Approval System for Claude Agent

Intercepts tool_use events and generates previews/diffs before execution.
Supports approve/reject workflow with user feedback.
"""

from __future__ import annotations

import asyncio
import difflib
import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional, Awaitable
from uuid import uuid4

logger = logging.getLogger(__name__)


class ApprovalStatus(str, Enum):
    """Status of a tool approval request"""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    TIMEOUT = "timeout"


@dataclass
class ToolApprovalRequest:
    """
    Represents a pending tool approval request with preview data.
    """

    request_id: str
    tool_name: str
    tool_input: dict[str, Any]
    tool_use_id: str

    # Preview data
    preview_type: str = "generic"  # "diff", "file_content", "command", "generic"
    preview_data: dict[str, Any] = field(default_factory=dict)

    # File context for Write/Edit
    file_path: Optional[str] = None
    original_content: Optional[str] = None
    new_content: Optional[str] = None
    diff_lines: list[str] = field(default_factory=list)

    # Status
    status: ApprovalStatus = ApprovalStatus.PENDING
    user_feedback: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "request_id": self.request_id,
            "tool_name": self.tool_name,
            "tool_input": self.tool_input,
            "tool_use_id": self.tool_use_id,
            "preview_type": self.preview_type,
            "preview_data": self.preview_data,
            "file_path": self.file_path,
            "original_content": self.original_content,
            "new_content": self.new_content,
            "diff_lines": self.diff_lines,
            "status": self.status.value,
        }


class ToolApprovalManager:
    """
    Manages tool approval workflow with preview generation.

    Intercepts tool_use events, generates previews/diffs, and waits
    for user approval before allowing execution.
    """

    # Tools that modify files and require approval with diff preview
    FILE_MODIFICATION_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}

    # Tools that execute commands and require approval
    COMMAND_TOOLS = {"Bash"}

    # Tools that are generally safe and can be auto-approved
    SAFE_TOOLS = {"Read", "Glob", "Grep", "TodoWrite", "WebFetch", "WebSearch", "Task"}

    def __init__(
        self,
        cwd: str,
        approval_timeout: float = 300.0,  # 5 minutes
        auto_approve_safe: bool = False,  # Don't auto-approve anything by default
    ):
        self.cwd = cwd
        self.approval_timeout = approval_timeout
        self.auto_approve_safe = auto_approve_safe

        # Pending approvals
        self._pending: dict[str, ToolApprovalRequest] = {}
        self._approval_futures: dict[str, asyncio.Future] = {}

        # Lock to ensure sequential processing of approval requests
        self._lock = asyncio.Lock()

    async def process_tool_use(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
        tool_use_id: str,
        on_approval_request: Callable[[ToolApprovalRequest], Awaitable[None]],
    ) -> tuple[bool, Optional[str]]:
        """
        Process a tool_use event and wait for approval.

        Args:
            tool_name: Name of the tool being invoked
            tool_input: Input parameters for the tool
            tool_use_id: Unique ID for this tool use
            on_approval_request: Callback to send approval request to frontend

        Returns:
            Tuple of (approved: bool, user_feedback: Optional[str])
        """
        # Check if tool should be auto-approved
        if self.auto_approve_safe and tool_name in self.SAFE_TOOLS:
            logger.info(f"Auto-approving safe tool: {tool_name}")
            return (True, None)

        # Acquire lock to ensure we only show one approval modal at a time
        async with self._lock:
            # Generate preview/diff
            request = await self._create_approval_request(
                tool_name, tool_input, tool_use_id
            )

            # Store pending request
            self._pending[request.request_id] = request

            # Create future for response
            loop = asyncio.get_event_loop()
            future = loop.create_future()
            self._approval_futures[request.request_id] = future

            try:
                # Send request to frontend

                logger.info(
                    f"Sending approval request for {tool_name} (id={request.request_id})"
                )
                print(
                    f"DEBUG: [ToolApproval] Added pending request: {request.request_id} for tool {tool_name}",
                    flush=True,
                )
                print(
                    "DEBUG: [ToolApproval] About to call on_approval_request callback...",
                    flush=True,
                )
                try:
                    await on_approval_request(request)
                    print(
                        "DEBUG: [ToolApproval] on_approval_request callback completed successfully",
                        flush=True,
                    )
                except Exception as callback_error:
                    print(
                        f"DEBUG: [ToolApproval] on_approval_request callback FAILED: {callback_error}",
                        flush=True,
                    )
                    logger.error(
                        f"Error in on_approval_request callback: {callback_error}",
                        exc_info=True,
                    )
                    raise

                # Wait for response with timeout
                try:
                    result = await asyncio.wait_for(
                        future, timeout=self.approval_timeout
                    )
                    approved = result.get("approved", False)
                    feedback = result.get("feedback")

                    request.status = (
                        ApprovalStatus.APPROVED if approved else ApprovalStatus.REJECTED
                    )
                    request.user_feedback = feedback

                    logger.info(
                        f"Tool {tool_name} {'approved' if approved else 'rejected'}"
                    )
                    return (approved, feedback)

                except asyncio.TimeoutError:
                    logger.warning(f"Approval request timed out for {tool_name}")
                    request.status = ApprovalStatus.TIMEOUT
                    return (False, "Approval timeout")

            finally:
                # Cleanup
                self._pending.pop(request.request_id, None)
                self._approval_futures.pop(request.request_id, None)
                print(
                    f"DEBUG: [ToolApproval] Removed pending request: {request.request_id}"
                )

    def respond_to_approval(
        self,
        request_id: str,
        approved: bool,
        feedback: Optional[str] = None,
    ) -> bool:
        """
        Respond to a pending approval request.

        Args:
            request_id: ID of the approval request
            approved: Whether to approve the tool use
            feedback: Optional feedback from user (for rejection)

        Returns:
            True if response was processed, False if request not found
        """
        future = self._approval_futures.get(request_id)
        if future is None or future.done():
            logger.warning(f"No pending approval for request_id={request_id}")
            print(
                f"DEBUG: [ToolApproval] Response failed. ID={request_id} not found in {list(self._approval_futures.keys())}"
            )
            return False

        future.set_result(
            {
                "approved": approved,
                "feedback": feedback,
            }
        )

        logger.info(f"Approval response set: approved={approved}, feedback={feedback}")
        return True

    async def _create_approval_request(
        self,
        tool_name: str,
        tool_input: dict[str, Any],
        tool_use_id: str,
    ) -> ToolApprovalRequest:
        """Create an approval request with preview data"""

        request = ToolApprovalRequest(
            request_id=str(uuid4()),
            tool_name=tool_name,
            tool_input=tool_input,
            tool_use_id=tool_use_id,
        )

        # Generate preview based on tool type
        if tool_name in self.FILE_MODIFICATION_TOOLS:
            await self._generate_file_preview(request)
        elif tool_name in self.COMMAND_TOOLS:
            self._generate_command_preview(request)
        else:
            self._generate_generic_preview(request)

        return request

    async def _generate_file_preview(self, request: ToolApprovalRequest) -> None:
        """Generate diff preview for file modification tools"""

        tool_input = request.tool_input

        # Handle different file tools
        if request.tool_name == "Write":
            file_path = tool_input.get("file_path", "")
            new_content = tool_input.get("content", "")

            request.file_path = file_path
            request.new_content = new_content
            request.preview_type = "diff"

            # Read original content if file exists
            full_path = self._resolve_path(file_path)
            if full_path.exists():
                try:
                    request.original_content = full_path.read_text(encoding="utf-8")
                except Exception as e:
                    logger.warning(f"Could not read original file: {e}")
                    request.original_content = ""
            else:
                request.original_content = ""  # New file

            # Generate diff
            request.diff_lines = self._generate_diff(
                request.original_content,
                new_content,
                file_path,
            )

            request.preview_data = {
                "file_path": file_path,
                "is_new_file": not full_path.exists(),
                "original_lines": (
                    len(request.original_content.splitlines())
                    if request.original_content
                    else 0
                ),
                "new_lines": len(new_content.splitlines()),
            }

        elif request.tool_name == "Edit":
            file_path = tool_input.get("file_path", "")
            old_string = tool_input.get("old_string", "")
            new_string = tool_input.get("new_string", "")
            replace_all = tool_input.get("replace_all", False)

            request.file_path = file_path
            request.preview_type = "diff"

            # Read original content
            full_path = self._resolve_path(file_path)
            if full_path.exists():
                try:
                    original_content = full_path.read_text(encoding="utf-8")
                    request.original_content = original_content

                    # Apply edit to generate new content
                    if replace_all:
                        new_content = original_content.replace(old_string, new_string)
                    else:
                        new_content = original_content.replace(
                            old_string, new_string, 1
                        )

                    request.new_content = new_content

                    # Generate diff
                    request.diff_lines = self._generate_diff(
                        original_content,
                        new_content,
                        file_path,
                    )

                    # Count occurrences
                    occurrences = original_content.count(old_string)

                    request.preview_data = {
                        "file_path": file_path,
                        "old_string_preview": old_string[:200]
                        + ("..." if len(old_string) > 200 else ""),
                        "new_string_preview": new_string[:200]
                        + ("..." if len(new_string) > 200 else ""),
                        "replace_all": replace_all,
                        "occurrences": occurrences,
                        "will_replace": (
                            occurrences if replace_all else min(1, occurrences)
                        ),
                    }

                except Exception as e:
                    logger.warning(f"Could not read file for Edit: {e}")
                    request.preview_data = {
                        "error": str(e),
                        "file_path": file_path,
                    }
            else:
                request.preview_data = {
                    "error": f"File does not exist: {file_path}",
                    "file_path": file_path,
                }

        elif request.tool_name == "MultiEdit":
            # Handle multiple edits
            edits = tool_input.get("edits", [])
            request.preview_type = "multi_diff"
            request.preview_data = {
                "edit_count": len(edits),
                "edits": [],
            }

            all_diff_lines = []
            for edit in edits:
                file_path = edit.get("file_path", "")
                old_string = edit.get("old_string", "")
                new_string = edit.get("new_string", "")

                full_path = self._resolve_path(file_path)
                if full_path.exists():
                    try:
                        original = full_path.read_text(encoding="utf-8")
                        modified = original.replace(old_string, new_string, 1)
                        diff = self._generate_diff(original, modified, file_path)
                        all_diff_lines.extend(diff)
                        all_diff_lines.append("")  # Separator

                        request.preview_data["edits"].append(
                            {
                                "file_path": file_path,
                                "diff": diff,
                            }
                        )
                    except Exception as e:
                        request.preview_data["edits"].append(
                            {
                                "file_path": file_path,
                                "error": str(e),
                            }
                        )

            request.diff_lines = all_diff_lines

    def _generate_command_preview(self, request: ToolApprovalRequest) -> None:
        """Generate preview for command execution tools"""

        command = request.tool_input.get("command", "")
        description = request.tool_input.get("description", "")
        timeout = request.tool_input.get("timeout", 120000)

        request.preview_type = "command"
        request.preview_data = {
            "command": command,
            "description": description,
            "timeout_ms": timeout,
            "cwd": self.cwd,
            # Warning flags
            "has_sudo": "sudo" in command,
            "has_rm": "rm " in command or "rm\n" in command,
            "has_pipe": "|" in command,
            "has_redirect": ">" in command or ">>" in command,
        }

    def _generate_generic_preview(self, request: ToolApprovalRequest) -> None:
        """Generate generic preview for other tools"""

        request.preview_type = "generic"
        request.preview_data = {
            "tool_name": request.tool_name,
            "input_summary": self._summarize_input(request.tool_input),
        }

    def _generate_diff(
        self,
        original: str,
        modified: str,
        file_path: str,
    ) -> list[str]:
        """Generate unified diff between two strings"""

        original_lines = original.splitlines(keepends=True)
        modified_lines = modified.splitlines(keepends=True)

        diff = list(
            difflib.unified_diff(
                original_lines,
                modified_lines,
                fromfile=f"a/{file_path}",
                tofile=f"b/{file_path}",
                lineterm="",
            )
        )

        return diff

    def _resolve_path(self, file_path: str) -> Path:
        """Resolve file path relative to cwd"""
        path = Path(file_path)
        if path.is_absolute():
            return path
        return Path(self.cwd) / path

    def _summarize_input(
        self, tool_input: dict[str, Any], max_length: int = 200
    ) -> str:
        """Create a summary of tool input for display"""
        try:
            json_str = json.dumps(tool_input, indent=2)
            if len(json_str) <= max_length:
                return json_str
            return json_str[:max_length] + "..."
        except Exception:
            return str(tool_input)[:max_length]

    def get_pending_requests(self) -> list[ToolApprovalRequest]:
        """Get all pending approval requests"""
        return list(self._pending.values())

    def has_pending_requests(self) -> bool:
        """Check if there are pending approval requests"""
        return len(self._pending) > 0
