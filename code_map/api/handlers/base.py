# SPDX-License-Identifier: MIT
"""
Base Agent Handler - Abstract base class for agent execution modes.

Defines the interface that all handler modes must implement for
consistent handling of prompts, approvals, and cancellation.
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Awaitable

from fastapi import WebSocket

logger = logging.getLogger(__name__)


@dataclass
class HandlerCallbacks:
    """Container for handler callbacks to frontend via WebSocket."""

    send_event: Callable[[dict], Awaitable[None]]
    send_error: Callable[[str], Awaitable[None]]
    send_done: Callable[[], Awaitable[None]]

    # Optional callbacks for specific modes
    on_tool_approval_request: Optional[Callable[[Any], Awaitable[None]]] = None
    on_permission_request: Optional[Callable[[dict], Awaitable[dict]]] = None


@dataclass
class HandlerConfig:
    """Base configuration for all handlers."""

    cwd: str
    websocket: WebSocket
    model: str = "claude-sonnet-4-20250514"  # Default Claude model
    continue_session: bool = True
    verbose: bool = True
    auto_approve_safe: bool = False

    # Mode-specific options (optional)
    extra_options: dict[str, Any] = field(default_factory=dict)


class BaseAgentHandler(ABC):
    """
    Abstract base class for Claude agent execution modes.

    Each handler encapsulates the logic for a specific execution mode:
    - SDK Mode: Direct Anthropic SDK with tool interception
    - MCP Proxy Mode: Claude CLI with MCP tool proxy
    - CLI Mode: Standard Claude CLI subprocess

    Handlers manage their own runner lifecycle and provide
    consistent interfaces for the WebSocket endpoint.
    """

    def __init__(self, config: HandlerConfig, callbacks: HandlerCallbacks):
        self.config = config
        self.callbacks = callbacks
        self.runner: Any = None
        self._running = False
        self._run_task: Optional[asyncio.Task] = None

    @property
    def is_running(self) -> bool:
        """Check if handler has an active runner."""
        return self._running and self.runner is not None

    @abstractmethod
    async def handle_run(self, prompt: str, message: dict) -> asyncio.Task:
        """
        Handle a 'run' command by starting prompt execution.

        Args:
            prompt: The user prompt to execute
            message: Full message dict with additional options

        Returns:
            The asyncio Task running the prompt
        """
        pass

    @abstractmethod
    async def handle_cancel(self) -> None:
        """Cancel the currently running operation."""
        pass

    async def handle_tool_approval_response(
        self,
        request_id: str,
        approved: bool,
        feedback: str = "",
    ) -> bool:
        """
        Handle tool approval response from frontend.

        Args:
            request_id: The approval request ID
            approved: Whether the tool was approved
            feedback: Optional feedback message

        Returns:
            True if response was processed, False otherwise
        """
        # Default implementation - can be overridden by subclasses
        if self.runner and hasattr(self.runner, "respond_to_tool_approval"):
            return self.runner.respond_to_tool_approval(request_id, approved, feedback)
        return False

    async def cleanup(self) -> None:
        """Cleanup handler resources."""
        if self._run_task and not self._run_task.done():
            self._run_task.cancel()
            try:
                await self._run_task
            except asyncio.CancelledError:
                pass

        if (
            self.runner
            and hasattr(self.runner, "is_running")
            and self.runner.is_running
        ):
            await self.handle_cancel()

        self._running = False
        self.runner = None
        logger.debug(f"{self.__class__.__name__} cleaned up")
