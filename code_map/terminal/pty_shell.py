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
        thread = threading.Thread(target=read_thread, daemon=True, name="PTYReadThread")
        thread.start()
        logger.info(f"Started PTY read thread: {thread.name}")

        # Wait for thread to finish
        while self.running and thread.is_alive():
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
