# SPDX-License-Identifier: MIT
"""
CLI Mode Handler - Standard Claude CLI subprocess with various permission modes.

Supports multiple permission modes:
- default: Normal Claude CLI behavior
- acceptEdits: Auto-accept file edits
- bypassPermissions: Skip all permission prompts
- dontAsk: Don't ask for permissions
- plan: Planning mode
- mcpApproval: MCP-based approval via socket server
- toolApproval: Local tool execution with approval
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Optional, Awaitable

from .base import BaseAgentHandler, HandlerConfig, HandlerCallbacks

logger = logging.getLogger(__name__)


class CLIModeHandler(BaseAgentHandler):
    """
    Handler for CLI mode execution.

    Uses Claude CLI subprocess with configurable permission modes
    and optional MCP approval integration.
    """

    def __init__(
        self,
        config: HandlerConfig,
        callbacks: HandlerCallbacks,
        permission_mode: str = "default",
        socket_server: Optional[Any] = None,
        parser: Optional[Any] = None,
        on_permission_request: Optional[Callable[[dict], Awaitable[dict]]] = None,
    ):
        super().__init__(config, callbacks)
        self._cli_runner: Optional[Any] = None
        self._permission_mode = permission_mode
        self._socket_server = socket_server
        self._parser = parser
        self._on_permission_request = on_permission_request
        self._session_broken = False

    @property
    def session_broken(self) -> bool:
        """Check if session is broken due to local tool execution."""
        return self._session_broken

    async def handle_run(self, prompt: str, message: dict) -> asyncio.Task:
        """
        Start CLI mode prompt execution.

        Args:
            prompt: The user prompt
            message: Full message dict with options

        Returns:
            The asyncio Task running the prompt
        """
        from code_map.terminal.claude_runner import (
            ClaudeAgentRunner,
            ClaudeRunnerConfig,
        )
        from code_map.mcp.constants import DEFAULT_SOCKET_PATH

        # Determine if should continue session
        should_continue = message.get("continue", self.config.continue_session)

        # IMPORTANT: In toolApproval mode, we execute tools locally after
        # Claude exits. This means Claude's session state doesn't match reality.
        # To avoid "unexpected tool_use_id in tool_result" errors, we MUST
        # start a fresh session each time in toolApproval mode.
        if self._permission_mode == "toolApproval":
            logger.info(
                "toolApproval mode: forcing new session to avoid state mismatch"
            )
            should_continue = False

        # Setup MCP approval mode if selected
        if self._permission_mode == "mcpApproval" and self._socket_server:
            logger.info("mcpApproval mode: setting up MCP socket server callback")
            self._socket_server.set_frontend_callback(self._send_mcp_approval_request)

        # Create runner with current settings
        config = ClaudeRunnerConfig(
            cwd=self.config.cwd,
            model=self.config.model,
            continue_session=should_continue,
            verbose=self.config.verbose,
            permission_mode=self._permission_mode,
            auto_approve_safe_tools=self.config.auto_approve_safe,
            mcp_socket_path=(
                DEFAULT_SOCKET_PATH if self._permission_mode == "mcpApproval" else ""
            ),
        )
        self._cli_runner = ClaudeAgentRunner(config)
        self.runner = self._cli_runner
        self._running = True

        # Reset parser for potentially new session
        if not should_continue and self._parser:
            self._parser.reset()

        logger.info(
            f"Running prompt (continue={should_continue}, permission_mode={self._permission_mode}): {prompt[:50]}..."
        )

        async def run_prompt_task():
            try:
                exit_code = await self._cli_runner.run_prompt(
                    prompt=prompt,
                    on_event=self.callbacks.send_event,
                    on_error=self.callbacks.send_error,
                    on_done=self.callbacks.send_done,
                    on_permission_request=self._on_permission_request,
                    on_tool_approval_request=self._handle_tool_approval_request,
                )
                logger.info(f"Prompt completed with exit code {exit_code}")

                # Check if session is broken (tools executed locally in plan mode)
                if self._cli_runner.session_broken:
                    self._session_broken = True
                    logger.info(
                        "Session broken due to local tool execution, notifying frontend"
                    )
                    try:
                        await self.config.websocket.send_json(
                            {
                                "type": "session_broken",
                                "reason": "Tools were executed locally after Claude exited. Start a new session for the next prompt.",
                            }
                        )
                    except Exception as e:
                        logger.error(f"Error sending session_broken event: {e}")

            finally:
                self._running = False

        self._run_task = asyncio.create_task(run_prompt_task())
        return self._run_task

    async def _handle_tool_approval_request(self, request: Any) -> None:
        """Forward tool approval request to frontend via callback."""
        logger.debug(f"Tool approval request for {request.tool_name}")

        if self.callbacks.on_tool_approval_request:
            await self.callbacks.on_tool_approval_request(request)

    async def _send_mcp_approval_request(self, request: Any) -> None:
        """
        Forward MCP approval request to frontend via WebSocket (mcpApproval mode).

        This is used when permission_mode is 'mcpApproval' with the CLI runner.
        """
        logger.debug(f"MCP approval request for {request.tool_name}")

        try:
            approval_event = {
                "type": "mcp_approval_request",
                "request_id": request.request_id,
                "tool_name": request.tool_name,
                "tool_input": request.tool_input,
                "context": request.context,
                "preview_type": request.preview_type,
                "preview_data": request.preview_data,
                "file_path": request.file_path,
                "original_content": request.original_content,
                "new_content": request.new_content,
                "diff_lines": request.diff_lines,
            }
            await self.config.websocket.send_json(approval_event)
            logger.debug(f"MCP approval request sent to frontend: {request.tool_name}")
        except Exception as e:
            logger.error(f"Error sending MCP approval request: {e}")
            raise

    async def handle_cancel(self) -> None:
        """Cancel CLI runner."""
        if self._cli_runner and self._cli_runner.is_running:
            await self._cli_runner.cancel()
            self._running = False
            logger.info("CLI mode cancelled")

    async def handle_tool_approval_response(
        self,
        request_id: str,
        approved: bool,
        feedback: str = "",
    ) -> bool:
        """
        Handle tool approval response for CLI mode.

        Routes to either MCP socket server (mcpApproval) or runner (toolApproval).
        """
        # Try MCP approval mode first (via socket server)
        if self._permission_mode == "mcpApproval" and self._socket_server:
            logger.debug("Using MCP socket server for approval response")
            return self._socket_server.respond_to_approval(
                request_id=request_id,
                approved=approved,
                message=feedback,
                updated_input=None,
            )

        # Fallback to toolApproval mode (via runner)
        if self._cli_runner and hasattr(self._cli_runner, "respond_to_tool_approval"):
            logger.debug("Using runner for approval response")
            return self._cli_runner.respond_to_tool_approval(
                request_id, approved, feedback
            )

        logger.warning("No handler available for CLI approval response")
        return False

    def handle_mcp_approval_response(
        self,
        request_id: str,
        approved: bool,
        message: str = "",
        updated_input: Optional[dict] = None,
    ) -> bool:
        """
        Handle MCP approval response (mcpApproval mode only).

        This is a separate method for the specific mcp_approval_response command.
        """
        if self._socket_server:
            logger.debug(
                f"MCP approval response: request_id={request_id}, approved={approved}"
            )
            return self._socket_server.respond_to_approval(
                request_id=request_id,
                approved=approved,
                message=message,
                updated_input=updated_input,
            )
        logger.warning("MCP socket server not available for approval response")
        return False
