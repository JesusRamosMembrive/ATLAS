# SPDX-License-Identifier: MIT
"""
SDK Mode Handler - Direct Anthropic SDK with tool interception.

Uses the Anthropic SDK directly for full control over tool execution,
allowing frontend approval before each dangerous operation.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from .base import BaseAgentHandler, HandlerConfig, HandlerCallbacks

logger = logging.getLogger(__name__)


class SDKModeHandler(BaseAgentHandler):
    """
    Handler for SDK mode execution.

    Uses Anthropic SDK directly (requires API key) with tool interception
    for frontend approval before executing dangerous operations.
    """

    def __init__(self, config: HandlerConfig, callbacks: HandlerCallbacks):
        super().__init__(config, callbacks)
        self._sdk_runner: Optional[Any] = None

    async def handle_run(self, prompt: str, message: dict) -> asyncio.Task:
        """
        Start SDK mode prompt execution.

        Args:
            prompt: The user prompt
            message: Full message dict with options

        Returns:
            The asyncio Task running the prompt
        """
        from code_map.terminal.sdk_runner import SDKAgentRunner, SDKRunnerConfig

        logger.info("SDK mode: using Anthropic SDK with tool interception")

        # SDK mode always uses fresh sessions (conversation history managed internally)
        sdk_config = SDKRunnerConfig(
            cwd=self.config.cwd,
            model=self.config.model,
            auto_approve_read=self.config.auto_approve_safe,
        )
        self._sdk_runner = SDKAgentRunner(sdk_config)
        self.runner = self._sdk_runner
        self._running = True

        async def run_prompt_task():
            try:
                exit_code = await self._sdk_runner.run_prompt(
                    prompt=prompt,
                    on_event=self.callbacks.send_event,
                    on_error=self.callbacks.send_error,
                    on_done=self.callbacks.send_done,
                    on_tool_approval_request=self._handle_sdk_tool_approval,
                )
                logger.info(f"SDK prompt completed with exit code {exit_code}")
            finally:
                self._running = False

        self._run_task = asyncio.create_task(run_prompt_task())
        return self._run_task

    async def _handle_sdk_tool_approval(self, request: Any) -> None:
        """Forward SDK tool approval request to frontend via callback."""
        logger.debug(f"SDK tool approval request for {request.tool_name}")

        if self.callbacks.on_tool_approval_request:
            await self.callbacks.on_tool_approval_request(request)

    async def handle_cancel(self) -> None:
        """Cancel SDK runner."""
        if self._sdk_runner:
            # SDK runner may not have cancel method
            if hasattr(self._sdk_runner, "cancel"):
                await self._sdk_runner.cancel()
            self._running = False
            logger.info("SDK mode cancelled")

    async def handle_tool_approval_response(
        self,
        request_id: str,
        approved: bool,
        feedback: str = "",
    ) -> bool:
        """Handle tool approval response for SDK mode."""
        if self._sdk_runner and hasattr(self._sdk_runner, "respond_to_tool_approval"):
            return self._sdk_runner.respond_to_tool_approval(
                request_id, approved, feedback
            )
        logger.warning("SDK runner not available for approval response")
        return False
