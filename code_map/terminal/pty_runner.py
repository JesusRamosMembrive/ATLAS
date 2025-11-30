#!/usr/bin/env python3
"""
PTY-based Claude Code Runner.

This module provides a PTY-based interface to Claude Code that:
1. Spawns Claude in a pseudo-terminal for proper Ink UI support
2. Parses output into structured events
3. Emits JSON events for the frontend
4. Handles permission prompts and tool approvals
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, AsyncIterator, Awaitable, Callable, Optional, Union

import pexpect

from .pty_parser import EventAggregator, EventType, ParsedEvent, PTYParser

logger = logging.getLogger(__name__)


class RunnerState(Enum):
    """State of the PTY runner."""

    IDLE = "idle"
    INITIALIZING = "initializing"
    RUNNING = "running"
    WAITING_PERMISSION = "waiting_permission"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class PTYRunnerConfig:
    """Configuration for the PTY runner."""

    working_directory: str = "."
    timeout: float = 300.0  # 5 minutes default
    pty_dimensions: tuple[int, int] = (50, 140)  # rows, cols
    init_wait: float = 2.0  # Wait for Claude to initialize (reduced from 5s)
    read_interval: float = 0.1  # How often to read output
    claude_binary: str = "claude"


class PTYClaudeRunner:
    """
    PTY-based Claude Code runner.

    Manages a Claude Code process running in a pseudo-terminal,
    parsing output and emitting structured events.
    """

    def __init__(self, config: Optional[PTYRunnerConfig] = None):
        """Initialize the runner."""
        self.config = config or PTYRunnerConfig()
        self._process: Optional[pexpect.spawn] = None
        self._parser = PTYParser()
        self._aggregator = EventAggregator()
        self._state = RunnerState.IDLE
        self._pending_permission: Optional[ParsedEvent] = None

        # Callbacks for events
        self._on_event: Optional[
            Callable[[dict[str, Any]], Union[None, asyncio.Task[Any]]]
        ] = None
        self._on_permission: Optional[
            Callable[
                [dict[str, Any]],
                Union[asyncio.Future[Any], Awaitable[asyncio.Future[Any]]],
            ]
        ] = None

    @property
    def state(self) -> RunnerState:
        """Get current runner state."""
        return self._state

    @property
    def is_running(self) -> bool:
        """Check if a session is active."""
        return self._state in (RunnerState.RUNNING, RunnerState.WAITING_PERMISSION)

    def set_event_callback(
        self, callback: Callable[[dict[str, Any]], Union[None, asyncio.Task[Any]]]
    ):
        """Set callback for event emissions."""
        self._on_event = callback

    def set_permission_callback(
        self,
        callback: Callable[
            [dict[str, Any]], Union[asyncio.Future[Any], Awaitable[asyncio.Future[Any]]]
        ],
    ):
        """Set callback for permission requests (should return Future with response)."""
        self._on_permission = callback

    async def start_session(self) -> bool:
        """
        Start a new Claude Code session.

        Returns:
            True if session started successfully
        """
        logger.info("PTYRunner: start_session called")
        if self._process is not None:
            logger.warning("Session already active, stopping first")
            await self.stop_session()

        self._state = RunnerState.INITIALIZING
        self._emit_event(
            {
                "type": "session_start",
                "timestamp": datetime.now().isoformat(),
                "working_directory": self.config.working_directory,
            }
        )

        try:
            # Build environment
            env = os.environ.copy()
            env["TERM"] = "xterm-256color"

            logger.info(
                f"PTYRunner: Spawning claude binary: {self.config.claude_binary}"
            )
            # Spawn Claude in PTY
            self._process = pexpect.spawn(
                self.config.claude_binary,
                encoding="utf-8",
                timeout=self.config.timeout,
                dimensions=self.config.pty_dimensions,
                cwd=self.config.working_directory,
                env=env,
            )
            logger.info(
                f"PTYRunner: Claude spawned, waiting {self.config.init_wait}s for initialization"
            )

            # Wait for initialization
            await asyncio.sleep(self.config.init_wait)
            logger.info("PTYRunner: Init wait complete, reading initial output")

            # Read initial output
            try:
                initial = self._process.read_nonblocking(32768, timeout=1)
                logger.info(f"PTYRunner: Read {len(initial)} chars of initial output")
                events = self._parse_output(initial)
                for event in events:
                    self._emit_event(event.to_dict())
            except pexpect.TIMEOUT:
                logger.info("PTYRunner: No initial output (timeout)")

            self._state = RunnerState.RUNNING
            logger.info("PTYRunner: Session ready, returning True")
            self._emit_event(
                {
                    "type": "session_ready",
                    "timestamp": datetime.now().isoformat(),
                }
            )
            return True

        except Exception as e:
            logger.error(f"Failed to start session: {e}", exc_info=True)
            self._state = RunnerState.ERROR
            self._emit_event(
                {
                    "type": "error",
                    "timestamp": datetime.now().isoformat(),
                    "content": str(e),
                }
            )
            return False

    async def stop_session(self):
        """Stop the current session."""
        if self._process is not None:
            try:
                self._process.sendcontrol("c")
                await asyncio.sleep(0.5)
                self._process.close(force=True)
            except Exception as e:
                logger.warning(f"Error stopping session: {e}")
            finally:
                self._process = None

        self._parser.reset()
        self._aggregator.reset()
        self._state = RunnerState.IDLE
        self._pending_permission = None

        self._emit_event(
            {
                "type": "session_end",
                "timestamp": datetime.now().isoformat(),
            }
        )

    async def send_prompt(self, prompt: str) -> AsyncIterator[dict[str, Any]]:
        """
        Send a prompt to Claude and yield events as they occur.

        Args:
            prompt: The prompt to send

        Yields:
            Event dictionaries as they are parsed from output
        """
        if self._process is None:
            raise RuntimeError("No active session")

        if self._state == RunnerState.WAITING_PERMISSION:
            raise RuntimeError("Waiting for permission response")

        self._state = RunnerState.RUNNING
        self._emit_event(
            {
                "type": "prompt_sent",
                "timestamp": datetime.now().isoformat(),
                "data": {"prompt": prompt[:200]},  # Truncate for logging
            }
        )

        # Send prompt using ESC+Enter method (proven to work with Ink UI)
        # The ESC clears any pending state, Enter submits
        self._process.send(prompt)
        await asyncio.sleep(0.3)
        self._process.send("\x1b")  # ESC
        await asyncio.sleep(0.1)
        self._process.send("\r")  # Enter to submit

        # Collect and yield output
        start_time = time.time()
        idle_count = 0
        max_idle = 30  # Exit after this many consecutive idle reads
        completion_seen = False

        while time.time() - start_time < self.config.timeout:
            try:
                chunk = self._process.read_nonblocking(
                    16384, timeout=self.config.read_interval
                )
                if chunk:
                    idle_count = 0  # Reset idle counter
                    events = self._parse_output(chunk)
                    for event in events:
                        yield event.to_dict()

                        # Handle special event types
                        if event.type == EventType.PERMISSION_REQUEST:
                            self._pending_permission = event
                            self._state = RunnerState.WAITING_PERMISSION
                            response = await self._handle_permission(event)
                            if response:
                                yield response
                            self._pending_permission = None
                            self._state = RunnerState.RUNNING

                        elif event.type == EventType.COMPLETION:
                            self._state = RunnerState.COMPLETED
                            completion_seen = True

                        elif event.type == EventType.PROMPT_READY:
                            # Session is ready for new input
                            return

            except pexpect.TIMEOUT:
                idle_count += 1
                # If we've seen a completion and we're idle, we're done
                if completion_seen and idle_count >= 5:
                    return
                # Max idle timeout
                if idle_count >= max_idle:
                    logger.warning(f"Max idle timeout after {idle_count} reads")
                    return
                await asyncio.sleep(self.config.read_interval)

            except pexpect.EOF:
                logger.warning("Claude process ended unexpectedly")
                self._state = RunnerState.ERROR
                yield {
                    "type": "error",
                    "timestamp": datetime.now().isoformat(),
                    "content": "Claude process ended unexpectedly",
                }
                return

    async def respond_permission(self, approved: bool, always: bool = False):
        """
        Respond to a pending permission request.

        Args:
            approved: Whether to allow the operation
            always: If True and approved, select "always allow"
        """
        if self._process is None or self._pending_permission is None:
            raise RuntimeError("No pending permission request")

        # Send the appropriate response
        if approved:
            if always:
                # Select "Always allow" option (typically 'a' or arrow down + enter)
                self._process.send("a")
            else:
                # Select "Allow once" (typically 'y' or enter)
                self._process.send("y")
        else:
            # Deny (typically 'n' or escape)
            self._process.send("n")

        await asyncio.sleep(0.3)
        self._pending_permission = None
        self._state = RunnerState.RUNNING

    def _parse_output(self, raw: str) -> list[ParsedEvent]:
        """Parse raw output through parser and aggregator."""
        events = self._parser.parse_chunk(raw)
        return self._aggregator.add_events(events)

    def _emit_event(self, event: dict[str, Any]):
        """Emit an event through the callback."""
        if self._on_event:
            try:
                self._on_event(event)
            except Exception as e:
                logger.error(f"Error in event callback: {e}")

    async def _handle_permission(self, event: ParsedEvent) -> Optional[dict[str, Any]]:
        """Handle a permission request."""
        if self._on_permission:
            try:
                future = self._on_permission(event.to_dict())
                response = await asyncio.wait_for(future, timeout=self.config.timeout)
                await self.respond_permission(
                    approved=response.get("approved", False),
                    always=response.get("always", False),
                )
                return {
                    "type": "permission_response",
                    "timestamp": datetime.now().isoformat(),
                    "data": response,
                }
            except asyncio.TimeoutError:
                logger.warning("Permission request timed out, denying")
                await self.respond_permission(approved=False)
                return {
                    "type": "permission_timeout",
                    "timestamp": datetime.now().isoformat(),
                    "content": "Permission request timed out",
                }
            except Exception as e:
                logger.error(f"Error handling permission: {e}")
                await self.respond_permission(approved=False)
                return {
                    "type": "permission_error",
                    "timestamp": datetime.now().isoformat(),
                    "content": str(e),
                }
        else:
            # No handler, auto-deny for safety
            logger.warning("No permission handler, auto-denying")
            await self.respond_permission(approved=False)
            return {
                "type": "permission_auto_denied",
                "timestamp": datetime.now().isoformat(),
                "content": "No permission handler configured",
            }


# Factory function for easy creation
def create_pty_runner(
    working_directory: str = ".",
    timeout: float = 300.0,
) -> PTYClaudeRunner:
    """
    Create a configured PTY runner.

    Args:
        working_directory: Directory to run Claude in
        timeout: Timeout for operations

    Returns:
        Configured PTYClaudeRunner instance
    """
    config = PTYRunnerConfig(
        working_directory=working_directory,
        timeout=timeout,
    )
    return PTYClaudeRunner(config)
