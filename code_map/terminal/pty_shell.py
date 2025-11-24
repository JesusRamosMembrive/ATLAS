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
from typing import Optional, Callable
import asyncio
import logging

logger = logging.getLogger(__name__)


class PTYShell:
    """
    Manages a shell process with PTY (pseudo-terminal) support

    Provides async I/O handling for bidirectional communication
    with a shell process running in a PTY.
    """

    def __init__(self, cols: int = 80, rows: int = 24):
        """
        Initialize PTY shell

        Args:
            cols: Terminal width in columns
            rows: Terminal height in rows
        """
        self.cols = cols
        self.rows = rows
        self.master_fd: Optional[int] = None
        self.pid: Optional[int] = None
        self.running = False

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
            # Child process - execute shell
            os.execvp(shell, [shell])
        else:
            # Parent process - set terminal size
            self.running = True
            self._set_winsize(self.cols, self.rows)

            # Make master FD non-blocking
            flags = fcntl.fcntl(self.master_fd, fcntl.F_GETFL)
            fcntl.fcntl(self.master_fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

            logger.info(f"Spawned shell process: pid={self.pid}, shell={shell}")

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

        loop = asyncio.get_event_loop()

        while self.running:
            # Check if data is available
            readable, _, _ = select.select([self.master_fd], [], [], 0.1)

            if readable:
                try:
                    # Read available data
                    data = os.read(self.master_fd, 1024)
                    if not data:
                        # EOF - shell exited
                        self.running = False
                        break

                    # Decode and send to callback
                    text = data.decode("utf-8", errors="replace")
                    await loop.run_in_executor(None, callback, text)

                except OSError as e:
                    logger.error(f"Error reading from shell: {e}")
                    self.running = False
                    break
            else:
                # No data available, yield control
                await asyncio.sleep(0.01)

        logger.info("Shell read loop exited")

    def close(self) -> None:
        """
        Close shell process and cleanup resources
        """
        if not self.running:
            return

        self.running = False

        # Close master FD
        if self.master_fd is not None:
            try:
                os.close(self.master_fd)
            except OSError:
                pass
            self.master_fd = None

        # Terminate child process
        if self.pid is not None:
            try:
                os.kill(self.pid, signal.SIGTERM)
                os.waitpid(self.pid, 0)
            except (OSError, ChildProcessError):
                pass
            self.pid = None

        logger.info("Shell process closed")

    def __del__(self):
        """Cleanup on garbage collection"""
        self.close()
