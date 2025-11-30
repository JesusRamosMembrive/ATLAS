# SPDX-License-Identifier: MIT
"""
Handler Factory - Create appropriate handler based on permission mode.

Provides a factory function to instantiate the correct handler class
based on the requested execution mode.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional, Awaitable

from fastapi import WebSocket

from .base import BaseAgentHandler, HandlerConfig, HandlerCallbacks
from .sdk_handler import SDKModeHandler
from .mcp_proxy_handler import MCPProxyModeHandler
from .cli_handler import CLIModeHandler
from .approval import create_approval_event_sender

logger = logging.getLogger(__name__)

# Valid permission modes
PERMISSION_MODES = (
    "default",
    "acceptEdits",
    "bypassPermissions",
    "dontAsk",
    "plan",
    "mcpApproval",
    "toolApproval",
)

# Extended modes including SDK and mcpProxy
EXTENDED_MODES = PERMISSION_MODES + ("sdk", "mcpProxy")


def create_handler(
    permission_mode: str,
    websocket: WebSocket,
    cwd: str,
    continue_session: bool = True,
    auto_approve_safe: bool = False,
    socket_server: Optional[Any] = None,
    parser: Optional[Any] = None,
    on_permission_request: Optional[Callable[[dict], Awaitable[dict]]] = None,
) -> BaseAgentHandler:
    """
    Create appropriate handler based on permission mode.

    Args:
        permission_mode: Execution mode (sdk, mcpProxy, or CLI modes)
        websocket: WebSocket connection to frontend
        cwd: Working directory for operations
        continue_session: Whether to continue previous session (CLI modes)
        auto_approve_safe: Whether to auto-approve safe tools
        socket_server: MCP socket server instance (for mcpProxy/mcpApproval)
        parser: JSON stream parser (for CLI modes)
        on_permission_request: Callback for permission requests (CLI modes)

    Returns:
        Configured handler instance
    """
    # Validate permission mode
    if permission_mode not in EXTENDED_MODES:
        logger.warning(f"Invalid permission mode: {permission_mode}, using default")
        permission_mode = "default"

    # Create base config
    config = HandlerConfig(
        cwd=cwd,
        websocket=websocket,
        continue_session=continue_session,
        auto_approve_safe=auto_approve_safe,
    )

    # Create approval event sender
    approval_sender = create_approval_event_sender(
        websocket=websocket,
        event_type="tool_approval_request",
        include_tool_use_id=True,
        include_context=(permission_mode in ("mcpProxy", "mcpApproval")),
    )

    # Create callbacks container
    # Note: send_event, send_error, send_done are set by the caller
    # We just set up the approval callback here
    callbacks = HandlerCallbacks(
        send_event=_placeholder_send_event,
        send_error=_placeholder_send_error,
        send_done=_placeholder_send_done,
        on_tool_approval_request=approval_sender,
    )

    # Create appropriate handler
    if permission_mode == "sdk":
        logger.info("Creating SDK mode handler")
        return SDKModeHandler(config, callbacks)

    elif permission_mode == "mcpProxy":
        if socket_server is None:
            raise ValueError("mcpProxy mode requires socket_server")
        logger.info("Creating MCP proxy mode handler")
        return MCPProxyModeHandler(config, callbacks, socket_server)

    else:
        logger.info(f"Creating CLI mode handler (mode={permission_mode})")
        return CLIModeHandler(
            config=config,
            callbacks=callbacks,
            permission_mode=permission_mode,
            socket_server=socket_server,
            parser=parser,
            on_permission_request=on_permission_request,
        )


# Placeholder callbacks - these should be replaced by the caller
async def _placeholder_send_event(event_data: dict) -> None:
    logger.warning("send_event callback not configured")


async def _placeholder_send_error(message: str) -> None:
    logger.warning("send_error callback not configured")


async def _placeholder_send_done() -> None:
    logger.warning("send_done callback not configured")
