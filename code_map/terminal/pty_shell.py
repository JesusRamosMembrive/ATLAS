"""
PTY Shell process management for web terminal

Spawns and manages shell processes with pseudo-terminal support
"""

import os
import pty
import select
import subprocess
import struct
import fcntl
import termios
import signal
import threading
import re
from typing import Optional, Callable, Tuple
import asyncio
import logging

# Import agent parser for event detection
from .agent_parser import AgentOutputParser, AgentEvent

logger = logging.getLogger(__name__)


class PTYShell:
    """
    Manages a shell process with PTY (pseudo-terminal) support

    Provides async I/O handling for bidirectional communication
    with a shell process running in a PTY.
    """

    def __init__(self, cols: int = 80, rows: int = 24, enable_agent_parsing: bool = False):
        """
        Initialize PTY shell

        Args:
            cols: Terminal width in columns
            rows: Terminal height in rows
            enable_agent_parsing: Enable agent output parsing for event detection
        """
        self.cols = cols
        self.rows = rows
        self.master_fd: Optional[int] = None
        self.pid: Optional[int] = None
        self.running = False
        self.read_thread: Optional[threading.Thread] = None

        # Agent parsing
        self.enable_agent_parsing = enable_agent_parsing
        self.agent_parser: Optional[AgentOutputParser] = None
        self.agent_event_callback: Optional[Callable[[AgentEvent], None]] = None

        # Claude Code specific filtering
        self._is_claude_code_session = False
        self._claude_buffer = ""

        if enable_agent_parsing:
            self.agent_parser = AgentOutputParser()

    def spawn(self) -> None:
        """
        Spawn shell process with PTY

        Raises:
            OSError: If fork fails
        """
        # Determine shell to use
        shell = os.environ.get("SHELL", "/bin/bash")
        if not os.path.exists(shell):
            shell = "/bin/sh"  # Fallback to sh
        # Fork process with PTY
        self.pid, self.master_fd = pty.fork()

        if self.pid == 0:
            # Child process - execute shell in login + interactive mode
            # Set terminal environment
            os.environ.update({
                "TERM": "xterm-256color",
                "COLORTERM": "truecolor",
                "LANG": os.environ.get("LANG", "C.UTF-8"),
            })
            # Force login and interactive shell with -li flags
            os.execvp(shell, [shell, "-li"])
        else:
            # Parent process - set terminal size
            self.running = True
            self._set_winsize(self.cols, self.rows)

            # Make master FD non-blocking
            flags = fcntl.fcntl(self.master_fd, fcntl.F_GETFL)
            fcntl.fcntl(self.master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

            logger.info(f"Spawned shell process: pid={self.pid}, shell={shell}")

    def _filter_claude_code_output(self, text: str) -> str:
        """
        NO-OP filter - pass through all content unchanged.

        With two-layer architecture (read-only terminal display + separate input),
        we don't need to filter anything. The terminal shows raw output from Claude Code,
        and user input comes from a separate HTML input element.

        Args:
            text: Raw text from PTY

        Returns:
            Unmodified text
        """
        return text

    def _set_winsize(self, cols: int, rows: int) -> None:
        """
        Set terminal window size

        Args:
            cols: Terminal width
            rows: Terminal height
        """
        if self.master_fd is None:
            return

        winsize = struct.pack("HHHH", rows, cols, 0, 0)
        fcntl.ioctl(self.master_fd, termios.TIOCSWINSZ, winsize)

    def set_agent_event_callback(self, callback: Callable[[AgentEvent], None]) -> None:
        """
        Set callback for agent events

        Args:
            callback: Function to call with detected agent events
        """
        self.agent_event_callback = callback

    def resize(self, cols: int, rows: int) -> None:
        """
        Resize terminal

        Args:
            cols: New terminal width
            rows: New terminal height
        """
        self.cols = cols
        self.rows = rows
        self._set_winsize(cols, rows)
        logger.debug(f"Terminal resized to {cols}x{rows}")

    def write(self, data: str) -> None:
        """
        Write data to shell stdin

        Args:
            data: String to write to shell
        """
        if self.master_fd is None or not self.running:
            return

        try:
            os.write(self.master_fd, data.encode("utf-8"))
        except OSError as e:
            logger.error(f"Failed to write to shell: {e}")
            self.running = False

    async def read(self, callback: Callable[[str], None]) -> None:
        """
        Read shell output asynchronously

        Continuously reads from shell output and calls callback
        with received data. Runs until shell process exits.

        Args:
            callback: Function to call with output data
        """
        if self.master_fd is None:
            return

        def read_thread():
            """Thread function for reading PTY output"""
            logger.info("PTY read thread started")
            while self.running:
                try:
                    # Check if master_fd is still valid
                    if self.master_fd is None:
                        logger.info("PTY master_fd closed, exiting thread")
                        break

                    # Check if data is available with short timeout
                    readable, _, _ = select.select([self.master_fd], [], [], 0.1)

                    if readable:
                        # Double-check master_fd is still valid
                        if self.master_fd is None:
                            logger.info("PTY master_fd closed during read, exiting thread")
                            break
                        data = os.read(self.master_fd, 1024)
                        if not data:
                            # EOF - shell exited
                            logger.info("PTY read EOF - shell exited")
                            self.running = False
                            break

                        # Decode and call callback (thread-safe)
                        text = data.decode("utf-8", errors="replace")

                        # Two-layer architecture: No filtering needed
                        # Terminal is read-only display, input comes from separate HTML element

                        # Parse agent events if enabled
                        if self.enable_agent_parsing and self.agent_parser:
                            try:
                                events = self.agent_parser.parse_chunk(text)
                                if events and self.agent_event_callback:
                                    for event in events:
                                        self.agent_event_callback(event)
                            except Exception as e:
                                logger.error(f"Error parsing agent output: {e}")

                        # Always call raw text callback
                        callback(text)

                except OSError as e:
                    logger.error(f"Error reading from shell: {e}")
                    self.running = False
                    break
                except Exception as e:
                    logger.error(f"Unexpected error in read thread: {e}", exc_info=True)
                    self.running = False
                    break

            logger.info("PTY read thread exited")

        # Start read thread
        self.read_thread = threading.Thread(target=read_thread, daemon=True, name="PTYReadThread")
        self.read_thread.start()
        logger.info(f"Started PTY read thread: {self.read_thread.name}")

        # Wait for thread to finish
        while self.running and self.read_thread.is_alive():
            await asyncio.sleep(0.1)

        logger.info("Shell read loop exited")

    def close(self) -> None:
        """
        Close shell process and cleanup resources
        """
        if not self.running:
            return

        logger.info("Closing shell process...")
        self.running = False

        # Reset Claude Code detection
        self._is_claude_code_session = False
        self._claude_buffer = ""

        # Wait for read thread to exit cleanly (if it exists)
        if self.read_thread is not None and self.read_thread.is_alive():
            logger.debug("Waiting for read thread to exit...")
            self.read_thread.join(timeout=0.5)
            if self.read_thread.is_alive():
                logger.warning("Read thread did not exit cleanly within timeout")
            else:
                logger.debug("Read thread exited cleanly")

        # Terminate child process first
        if self.pid is not None:
            try:
                os.kill(self.pid, signal.SIGTERM)
                os.waitpid(self.pid, 0)
                logger.info(f"Terminated shell process PID={self.pid}")
            except (OSError, ChildProcessError) as e:
                logger.debug(f"Error terminating process: {e}")
            self.pid = None

        # Close master FD after process is terminated
        if self.master_fd is not None:
            try:
                os.close(self.master_fd)
                logger.info("Closed master FD")
            except OSError as e:
                logger.debug(f"Error closing master FD: {e}")
            self.master_fd = None

        logger.info("Shell process closed")

    def __del__(self):
        """Cleanup on garbage collection"""
        self.close()
