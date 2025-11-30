# SPDX-License-Identifier: MIT
"""
Shared Approval Utilities - Common helpers for tool approval requests.

Provides reusable functions for formatting and sending approval events
to the frontend via WebSocket.
"""

from __future__ import annotations

import logging
from typing import Any, Protocol

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ApprovalRequestProtocol(Protocol):
    """Protocol for approval request objects."""

    request_id: str
    tool_name: str
    tool_input: dict
    preview_type: str
    preview_data: dict
    file_path: str | None
    original_content: str | None
    new_content: str | None
    diff_lines: list[str]


async def send_tool_approval_event(
    websocket: WebSocket,
    request: ApprovalRequestProtocol,
    tool_use_id: str | None = None,
    context: str | None = None,
    event_type: str = "tool_approval_request",
) -> None:
    """
    Send a tool approval request event to the frontend.

    Args:
        websocket: WebSocket connection to frontend
        request: Approval request object with tool details
        tool_use_id: Optional tool use ID (for SDK/CLI modes)
        context: Optional context string (for MCP modes)
        event_type: Event type name (default: "tool_approval_request")
    """
    try:
        approval_event = {
            "type": event_type,
            "request_id": request.request_id,
            "tool_name": request.tool_name,
            "tool_input": request.tool_input,
            "preview_type": request.preview_type,
            "preview_data": request.preview_data,
            "file_path": request.file_path,
            "original_content": request.original_content,
            "new_content": request.new_content,
            "diff_lines": request.diff_lines,
        }

        # Add optional fields
        if tool_use_id is not None:
            approval_event["tool_use_id"] = tool_use_id
        if context is not None:
            approval_event["context"] = context

        await websocket.send_json(approval_event)
        logger.debug(f"{event_type} sent: {request.tool_name}")

    except Exception as e:
        logger.error(f"Error sending {event_type}: {e}")
        raise


def create_approval_event_sender(
    websocket: WebSocket,
    event_type: str = "tool_approval_request",
    include_tool_use_id: bool = True,
    include_context: bool = False,
):
    """
    Factory to create an approval event sender callback.

    Args:
        websocket: WebSocket connection to frontend
        event_type: Event type name
        include_tool_use_id: Whether to include tool_use_id field
        include_context: Whether to include context field

    Returns:
        Async callback function for sending approval events
    """

    async def sender(request: Any) -> None:
        """Send approval event to frontend."""
        tool_use_id = None
        context = None

        if include_tool_use_id and hasattr(request, "tool_use_id"):
            tool_use_id = request.tool_use_id
        elif include_tool_use_id:
            # Use request_id as fallback for MCP proxy
            tool_use_id = request.request_id

        if include_context and hasattr(request, "context"):
            context = request.context

        await send_tool_approval_event(
            websocket=websocket,
            request=request,
            tool_use_id=tool_use_id,
            context=context,
            event_type=event_type,
        )

    return sender
