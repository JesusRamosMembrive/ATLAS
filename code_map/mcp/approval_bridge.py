# SPDX-License-Identifier: MIT
"""
Approval Bridge - Communication between MCP Server and Backend.

Manages pending approval requests and coordinates with the frontend
via the existing WebSocket infrastructure.
"""

from __future__ import annotations

import asyncio
import difflib
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional, Awaitable
from uuid import uuid4

from .constants import (
    APPROVAL_TIMEOUT,
    PREVIEW_CHAR_LIMIT,
    SUMMARY_CHAR_LIMIT,
    FILE_TOOLS,
    COMMAND_TOOLS,
    SAFE_TOOLS,
)

logger = logging.getLogger(__name__)


@dataclass
class ApprovalRequest:
    """
    Represents a pending tool approval request.

    Contains all information needed for the frontend to display
    a meaningful approval dialog.
    """

    request_id: str
    tool_name: str
    tool_input: dict[str, Any]
    context: str = ""

    # Preview data (populated by bridge)
    preview_type: str = "generic"  # "diff", "command", "generic"
    preview_data: dict[str, Any] = field(default_factory=dict)

    # File info for Write/Edit tools
    file_path: Optional[str] = None
    original_content: Optional[str] = None
    new_content: Optional[str] = None
    diff_lines: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "request_id": self.request_id,
            "tool_name": self.tool_name,
            "tool_input": self.tool_input,
            "context": self.context,
            "preview_type": self.preview_type,
            "preview_data": self.preview_data,
            "file_path": self.file_path,
            "original_content": self.original_content,
            "new_content": self.new_content,
            "diff_lines": self.diff_lines,
        }


class ApprovalBridge:
    """
    Bridge between MCP Permission Server and the main backend.

    Manages pending approval requests and notifies the frontend
    when user input is needed.

    Communication flow:
    1. MCP Server calls request_approval()
    2. Bridge generates preview and notifies frontend
    3. Frontend shows modal and user responds
    4. Backend calls respond() with user's decision
    5. Bridge resolves the future, MCP Server gets result
    """

    def __init__(
        self,
        cwd: str = ".",
        timeout: float = APPROVAL_TIMEOUT,
        auto_approve_safe: bool = False,
    ):
        self.cwd = cwd
        self.timeout = timeout
        self.auto_approve_safe = auto_approve_safe

        # Pending requests and their futures
        self._pending: dict[str, ApprovalRequest] = {}
        self._futures: dict[str, asyncio.Future] = {}

        # Callback to notify frontend
        self._notify_callback: Optional[
            Callable[[ApprovalRequest], Awaitable[None]]
        ] = None

        # Lock for sequential processing
        self._lock = asyncio.Lock()

    def set_notify_callback(
        self, callback: Callable[[ApprovalRequest], Awaitable[None]]
    ) -> None:
        """
        Set callback to notify frontend of new approval requests.

        The callback receives an ApprovalRequest and should send it
        to the frontend via WebSocket.
        """
        self._notify_callback = callback
        logger.debug(f"Approval bridge notify callback set: {callback}")

    # -------------------------------------------------------------------------
    # Request Creation
    # -------------------------------------------------------------------------

    def _create_approval_request(
        self, tool_name: str, tool_input: dict[str, Any], context: str
    ) -> ApprovalRequest:
        """Create an ApprovalRequest with a unique ID."""
        return ApprovalRequest(
            request_id=str(uuid4()),
            tool_name=tool_name,
            tool_input=tool_input,
            context=context,
        )

    def _auto_approve_response(self, tool_input: dict[str, Any]) -> dict[str, Any]:
        """Create auto-approve response for safe tools."""
        return {"approved": True, "message": "", "updated_input": tool_input}

    def _denial_response(
        self, tool_input: dict[str, Any], message: str
    ) -> dict[str, Any]:
        """Create denial response."""
        return {"approved": False, "message": message, "updated_input": tool_input}

    # -------------------------------------------------------------------------
    # Response Handling
    # -------------------------------------------------------------------------

    async def _notify_and_wait(
        self,
        request: ApprovalRequest,
        future: asyncio.Future,
    ) -> dict[str, Any]:
        """Notify frontend and wait for response."""
        if self._notify_callback:
            logger.debug(f"Calling notify callback for {request.request_id}")
            try:
                await self._notify_callback(request)
                logger.debug(f"Notify callback completed for {request.request_id}")
            except Exception as e:
                logger.error(f"Error in notify callback: {e}", exc_info=True)
                return self._denial_response(
                    request.tool_input, f"Failed to notify frontend: {e}"
                )
        else:
            logger.warning("No notify callback set, auto-approving")
            return self._auto_approve_response(request.tool_input)

        # Wait for response with timeout
        logger.debug(f"Waiting for user response (timeout={self.timeout}s)")
        try:
            result = await asyncio.wait_for(future, timeout=self.timeout)
            logger.debug(
                f"Got response for {request.request_id}: approved={result.get('approved')}"
            )
            return result
        except asyncio.TimeoutError:
            logger.warning(f"Approval request {request.request_id} timed out")
            return self._denial_response(
                request.tool_input, "Approval timeout - no response from user"
            )

    # -------------------------------------------------------------------------
    # Main API
    # -------------------------------------------------------------------------

    async def request_approval(
        self, tool_name: str, tool_input: dict[str, Any], context: str = ""
    ) -> dict[str, Any]:
        """
        Request approval from the user for a tool execution.

        This method blocks until the user responds or timeout occurs.

        Args:
            tool_name: Name of the tool (e.g., "Edit", "Bash")
            tool_input: Input parameters for the tool
            context: Additional context about the operation

        Returns:
            dict with keys:
                - approved: bool
                - message: str (reason if denied)
                - updated_input: dict (possibly modified input)
        """
        # Auto-approve safe tools if configured
        if self.auto_approve_safe and tool_name in SAFE_TOOLS:
            logger.info(f"Auto-approving safe tool: {tool_name}")
            return self._auto_approve_response(tool_input)

        async with self._lock:
            # Create request with preview
            request = self._create_approval_request(tool_name, tool_input, context)
            await self._generate_preview(request)

            # Store request and create future
            self._pending[request.request_id] = request
            future = asyncio.get_event_loop().create_future()
            self._futures[request.request_id] = future

            logger.debug(
                f"Created approval request {request.request_id} for {tool_name}"
            )

            try:
                return await self._notify_and_wait(request, future)
            finally:
                # Cleanup
                self._pending.pop(request.request_id, None)
                self._futures.pop(request.request_id, None)
                logger.debug(f"Cleaned up request {request.request_id}")

    def respond(
        self,
        request_id: str,
        approved: bool,
        message: str = "",
        updated_input: Optional[dict[str, Any]] = None,
    ) -> bool:
        """
        Respond to a pending approval request.

        Called by the backend when the user responds via frontend.

        Args:
            request_id: ID of the approval request
            approved: Whether to approve the tool execution
            message: Optional message (reason for denial)
            updated_input: Optional modified input parameters

        Returns:
            True if response was processed, False if request not found
        """
        future = self._futures.get(request_id)
        request = self._pending.get(request_id)

        if future is None or future.done():
            logger.warning(f"No pending approval for request_id={request_id}")
            return False

        # Use original input if no updated input provided
        original_input = request.tool_input if request else {}

        future.set_result(
            {
                "approved": approved,
                "message": message,
                "updated_input": updated_input or original_input,
            }
        )

        logger.debug(f"Approval response for {request_id}: approved={approved}")
        return True

    def get_pending_requests(self) -> list[ApprovalRequest]:
        """Get all pending approval requests"""
        return list(self._pending.values())

    def has_pending(self) -> bool:
        """Check if there are pending approval requests"""
        return len(self._pending) > 0

    async def _generate_preview(self, request: ApprovalRequest) -> None:
        """Generate preview data based on tool type"""

        tool_name = request.tool_name

        if tool_name in FILE_TOOLS:
            await self._generate_file_preview(request)
        elif tool_name in COMMAND_TOOLS:
            self._generate_command_preview(request)
        else:
            self._generate_generic_preview(request)

    async def _generate_file_preview(self, request: ApprovalRequest) -> None:
        """Generate diff preview for file modification tools"""
        tool_input = request.tool_input

        if request.tool_name == "Write":
            file_path = tool_input.get("file_path", "")
            new_content = tool_input.get("content", "")

            request.file_path = file_path
            request.new_content = new_content
            request.preview_type = "diff"

            # Read original if exists
            full_path = self._resolve_path(file_path)
            if full_path.exists():
                try:
                    request.original_content = full_path.read_text(encoding="utf-8")
                except Exception as e:
                    logger.warning(f"Could not read file: {e}")
                    request.original_content = ""
            else:
                request.original_content = ""

            # Generate diff
            request.diff_lines = self._generate_diff(
                request.original_content or "", new_content, file_path
            )

            request.preview_data = {
                "file_path": file_path,
                "is_new_file": not full_path.exists(),
                "original_lines": len((request.original_content or "").splitlines()),
                "new_lines": len(new_content.splitlines()),
            }

        elif request.tool_name == "Edit":
            file_path = tool_input.get("file_path", "")
            old_string = tool_input.get("old_string", "")
            new_string = tool_input.get("new_string", "")
            replace_all = tool_input.get("replace_all", False)

            request.file_path = file_path
            request.preview_type = "diff"

            full_path = self._resolve_path(file_path)
            if full_path.exists():
                try:
                    original = full_path.read_text(encoding="utf-8")
                    request.original_content = original

                    # Apply edit
                    if replace_all:
                        new_content = original.replace(old_string, new_string)
                    else:
                        new_content = original.replace(old_string, new_string, 1)

                    request.new_content = new_content
                    request.diff_lines = self._generate_diff(
                        original, new_content, file_path
                    )

                    occurrences = original.count(old_string)
                    request.preview_data = {
                        "file_path": file_path,
                        "old_string_preview": old_string[:PREVIEW_CHAR_LIMIT]
                        + ("..." if len(old_string) > PREVIEW_CHAR_LIMIT else ""),
                        "new_string_preview": new_string[:PREVIEW_CHAR_LIMIT]
                        + ("..." if len(new_string) > PREVIEW_CHAR_LIMIT else ""),
                        "replace_all": replace_all,
                        "occurrences": occurrences,
                        "will_replace": (
                            occurrences if replace_all else min(1, occurrences)
                        ),
                    }
                except Exception as e:
                    request.preview_data = {"error": str(e), "file_path": file_path}
            else:
                request.preview_data = {
                    "error": f"File not found: {file_path}",
                    "file_path": file_path,
                }

    def _generate_command_preview(self, request: ApprovalRequest) -> None:
        """Generate preview for command execution"""
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
            "has_rm": "rm " in command or command.startswith("rm"),
            "has_pipe": "|" in command,
            "has_redirect": ">" in command,
            "is_dangerous": any(
                x in command for x in ["sudo", "rm -rf", "dd ", "mkfs", "> /dev/"]
            ),
        }

    def _generate_generic_preview(self, request: ApprovalRequest) -> None:
        """Generate generic preview for other tools"""
        request.preview_type = "generic"
        request.preview_data = {
            "tool_name": request.tool_name,
            "input_summary": self._summarize_input(request.tool_input),
        }

    def _generate_diff(self, original: str, modified: str, file_path: str) -> list[str]:
        """Generate unified diff"""
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
        self, tool_input: dict[str, Any], max_length: int = SUMMARY_CHAR_LIMIT
    ) -> str:
        """Create summary of tool input"""
        try:
            json_str = json.dumps(tool_input, indent=2)
            if len(json_str) <= max_length:
                return json_str
            return json_str[:max_length] + "..."
        except Exception:
            return str(tool_input)[:max_length]
