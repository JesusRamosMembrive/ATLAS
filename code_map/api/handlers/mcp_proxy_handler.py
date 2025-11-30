# SPDX-License-Identifier: MIT
"""
MCP Proxy Mode Handler - Claude CLI with MCP tool proxy for approval.

Uses Claude CLI with --disallowed-tools to disable native Write/Edit/Bash,
then provides proxy tools via MCP server that request approval before execution.
This mode uses the user's Claude CLI subscription (no separate API key needed).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from .base import BaseAgentHandler, HandlerConfig, HandlerCallbacks

logger = logging.getLogger(__name__)


class MCPProxyModeHandler(BaseAgentHandler):
    """
    Handler for MCP Proxy mode execution.

    Uses Claude CLI with MCP tool proxy for approval-based execution.
    The proxy tools (atlas_write, atlas_edit, atlas_bash) request
    user approval via socket before executing operations.
    """

    def __init__(
        self,
        config: HandlerConfig,
        callbacks: HandlerCallbacks,
        socket_server: Any,
    ):
        super().__init__(config, callbacks)
        self._mcp_proxy_runner: Optional[Any] = None
        self._socket_server = socket_server

    async def handle_run(self, prompt: str, message: dict) -> asyncio.Task:
        """
        Start MCP proxy mode prompt execution.

        Args:
            prompt: The user prompt
            message: Full message dict with options

        Returns:
            The asyncio Task running the prompt
        """
        from code_map.terminal.mcp_proxy_runner import (
            MCPProxyRunner,
            MCPProxyRunnerConfig,
        )
        from code_map.mcp.constants import DEFAULT_SOCKET_PATH

        logger.info("mcpProxy mode: using MCP tool proxy for approval")

        # Set the frontend callback for approval requests
        self._socket_server.set_frontend_callback(self._send_approval_request)

        # Create the MCP proxy runner
        mcp_proxy_config = MCPProxyRunnerConfig(
            cwd=self.config.cwd,
            model=self.config.model,
            continue_session=message.get("continue", self.config.continue_session),
            verbose=self.config.verbose,
            socket_path=DEFAULT_SOCKET_PATH,
        )
        self._mcp_proxy_runner = MCPProxyRunner(mcp_proxy_config)
        self.runner = self._mcp_proxy_runner
        self._running = True

        async def run_prompt_task():
            try:
                exit_code = await self._mcp_proxy_runner.run_prompt(
                    prompt=prompt,
                    on_event=self.callbacks.send_event,
                    on_error=self.callbacks.send_error,
                    on_done=self.callbacks.send_done,
                )
                logger.info(f"MCP proxy prompt completed with exit code {exit_code}")
            finally:
                self._running = False

        self._run_task = asyncio.create_task(run_prompt_task())
        return self._run_task

    async def _send_approval_request(self, request: Any) -> None:
        """
        Forward MCP proxy approval request to frontend via WebSocket.

        Args:
            request: ApprovalRequest from the MCP socket server
        """
        logger.debug(
            f"mcpProxy approval request for {request.tool_name}, request_id={request.request_id}"
        )

        if self.callbacks.on_tool_approval_request:
            await self.callbacks.on_tool_approval_request(request)

    async def handle_cancel(self) -> None:
        """Cancel MCP proxy runner."""
        if self._mcp_proxy_runner:
            await self._mcp_proxy_runner.cancel()
            self._running = False
            logger.info("MCP proxy mode cancelled")

    async def handle_tool_approval_response(
        self,
        request_id: str,
        approved: bool,
        feedback: str = "",
    ) -> bool:
        """
        Handle tool approval response for MCP proxy mode.

        Routes response through the socket server to the waiting MCP proxy.
        """
        if self._socket_server:
            logger.debug(
                f"MCP proxy approval response: request_id={request_id}, approved={approved}"
            )
            success = self._socket_server.respond_to_approval(
                request_id=request_id,
                approved=approved,
                message=feedback,
                updated_input=None,
            )
            if success:
                logger.debug(
                    f"Tool approval response (mcpProxy) processed: approved={approved}"
                )
            else:
                logger.warning(
                    f"Tool approval response (mcpProxy) failed: request_id={request_id}"
                )
            return success

        logger.warning("MCP socket server not available for approval response")
        return False
