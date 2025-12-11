"""
Windows PTY Shell process management for web terminal

Spawns and manages shell processes with pseudo-terminal support on Windows
using the winpty library (ConPTY wrapper).
"""

import os
import sys
import threading
import queue
from typing import Optional, Callable
import asyncio
import logging
import subprocess

# Windows-specific imports
if sys.platform == "win32":
    try:
        from winpty import PtyProcess  # type: ignore

        WINPTY_AVAILABLE = True
    except ImportError:
        WINPTY_AVAILABLE = False
        PtyProcess = None
else:
    WINPTY_AVAILABLE = False
    PtyProcess = None

# Import agent parser for event detection
from .agent_parser import AgentOutputParser, AgentEvent

logger = logging.getLogger(__name__)


class WinPTYShell:
    """
    Manages a shell process with PTY (pseudo-terminal) support on Windows

    Uses pywinpty (ConPTY) for proper terminal emulation on Windows.
    Provides async I/O handling for bidirectional communication.
    """

    def __init__(
        self, cols: int = 80, rows: int = 24, enable_agent_parsing: bool = False
    ):
        """
        Initialize Windows PTY shell

        Args:
            cols: Terminal width in columns
            rows: Terminal height in rows
            enable_agent_parsing: Enable agent output parsing for event detection
        """
        if not WINPTY_AVAILABLE:
            raise RuntimeError(
                "pywinpty is not installed. Install with: pip install pywinpty"
            )

        self.cols = cols
        self.rows = rows
        self._process: Optional[PtyProcess] = None
        self.pid: Optional[int] = None
        self.master_fd: Optional[int] = None  # For API compatibility
        self.running = False
        self.read_thread: Optional[threading.Thread] = None

        # Agent parsing
        self.enable_agent_parsing = enable_agent_parsing
        self.agent_parser: Optional[AgentOutputParser] = None
        self.agent_event_callback: Optional[Callable[[AgentEvent], None]] = None

        # Always enable parser for filtering
        if not self.agent_parser:
            self.agent_parser = AgentOutputParser()

    def spawn(self) -> None:
        """
        Spawn shell process with Windows PTY

        Raises:
            OSError: If spawn fails
        """
        # Determine shell to use on Windows
        shell = os.environ.get("COMSPEC", r"C:\Windows\System32\cmd.exe")

        # Check for PowerShell preference
        powershell_paths = [
            r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
            r"C:\Program Files\PowerShell\7\pwsh.exe",
        ]

        # Use PowerShell if available
        for ps_path in powershell_paths:
            if os.path.exists(ps_path):
                shell = ps_path
                break

        try:
            # Spawn process with PTY
            self._process = PtyProcess.spawn(
                shell,
                dimensions=(self.rows, self.cols),
                env=os.environ.copy(),
            )

            self.pid = self._process.pid
            self.master_fd = self.pid  # For API compatibility
            self.running = True

            logger.info(f"Spawned Windows shell process: pid={self.pid}, shell={shell}")

        except Exception as e:
            logger.error(f"Failed to spawn Windows PTY: {e}")
            raise OSError(f"Failed to spawn Windows PTY: {e}")

    def _process_output(self, text: str) -> str:
        """
        Process output before sending to frontend.
        """
        return text

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

        if self._process is not None:
            try:
                self._process.setwinsize(rows, cols)
                logger.debug(f"Terminal resized to {cols}x{rows}")
            except Exception as e:
                logger.error(f"Failed to resize terminal: {e}")

    def write(self, data: str) -> None:
        """
        Write data to shell stdin

        Args:
            data: String to write to shell
        """
        if self._process is None or not self.running:
            return

        try:
            self._process.write(data)
        except Exception as e:
            logger.error(f"Failed to write to shell: {e}")
            self.running = False

    async def read(self, callback: Callable[[str], None]) -> None:
        """
        Read shell output asynchronously

        Continuously reads from shell output and calls callback
        with received data. Runs until shell process exits.

        Uses a queue-based approach because pywinpty's read() is blocking.

        Args:
            callback: Function to call with output data
        """
        if self._process is None:
            return

        # Queue for passing data from blocking read thread to async consumer
        data_queue: queue.Queue[Optional[str]] = queue.Queue()

        def blocking_read_thread():
            """Thread that does blocking reads and puts data in queue"""
            logger.info("Windows PTY blocking read thread started")

            try:
                while self.running and self._process is not None:
                    try:
                        # Check if process is still alive
                        if not self._process.isalive():
                            logger.info("Windows PTY process exited")
                            break

                        # Blocking read - pywinpty doesn't support timeout
                        # Read small chunks for responsiveness
                        data = self._process.read(1024)

                        if data:
                            text = (
                                data
                                if isinstance(data, str)
                                else data.decode("utf-8", errors="replace")
                            )
                            data_queue.put(text)
                        else:
                            # Empty read might mean EOF or just no data yet
                            # Small sleep to prevent busy loop
                            import time

                            time.sleep(0.01)

                    except EOFError:
                        logger.info("Windows PTY read EOF")
                        break
                    except Exception as e:
                        if self.running:
                            logger.debug(f"Read error: {e}")
                        break

            except Exception as e:
                logger.error(f"Error in Windows PTY read thread: {e}", exc_info=True)
            finally:
                # Signal end of data
                data_queue.put(None)
                logger.info("Windows PTY blocking read thread exited")

        # Start blocking read thread
        self.read_thread = threading.Thread(
            target=blocking_read_thread, daemon=True, name="WinPTYReadThread"
        )
        self.read_thread.start()
        logger.info(f"Started Windows PTY read thread: {self.read_thread.name}")

        # Async consumer loop - process data from queue
        while self.running:
            try:
                # Non-blocking get with small timeout
                try:
                    text = data_queue.get(timeout=0.05)
                except queue.Empty:
                    # No data available, check if thread is still alive
                    if not self.read_thread.is_alive():
                        logger.info("Read thread died, exiting consumer loop")
                        break
                    await asyncio.sleep(0.01)
                    continue

                if text is None:
                    # End signal from read thread
                    logger.info("Received end signal from read thread")
                    break

                # Process output
                processed_text = self._process_output(text)

                # Parse agent events if enabled
                if self.enable_agent_parsing and self.agent_parser:
                    try:
                        events = self.agent_parser.parse_chunk(text)
                        if events and self.agent_event_callback:
                            for event in events:
                                self.agent_event_callback(event)
                    except Exception as e:
                        logger.error(f"Error parsing agent output: {e}")

                # Call raw text callback
                if processed_text:
                    callback(processed_text)

            except Exception as e:
                logger.error(f"Error in consumer loop: {e}", exc_info=True)
                break

        self.running = False
        logger.info("Windows shell read loop exited")

    def close(self) -> None:
        """
        Close shell process and cleanup resources
        """
        if not self.running and self._process is None:
            return

        logger.info("Closing Windows shell process...")
        self.running = False

        # Wait for read thread to exit
        if self.read_thread is not None and self.read_thread.is_alive():
            logger.debug("Waiting for read thread to exit...")
            self.read_thread.join(timeout=0.5)
            if self.read_thread.is_alive():
                logger.warning("Read thread did not exit cleanly within timeout")

        # Terminate process
        if self._process is not None:
            try:
                if self._process.isalive():
                    self._process.terminate(force=True)
                logger.info(f"Terminated Windows shell process PID={self.pid}")
            except Exception as e:
                logger.debug(f"Error terminating process: {e}")
            finally:
                self._process = None
                self.pid = None
                self.master_fd = None

        logger.info("Windows shell process closed")

    def __del__(self):
        """Cleanup on garbage collection"""
        self.close()


# Fallback implementation using subprocess (no PTY features)
class SubprocessShell:
    """
    Fallback shell implementation using subprocess.

    This provides basic shell functionality without PTY features
    when pywinpty is not available.
    """

    def __init__(
        self, cols: int = 80, rows: int = 24, enable_agent_parsing: bool = False
    ):
        self.cols = cols
        self.rows = rows
        self._process: Optional[subprocess.Popen] = None
        self.pid: Optional[int] = None
        self.master_fd: Optional[int] = None
        self.running = False
        self.read_thread: Optional[threading.Thread] = None

        # Agent parsing
        self.enable_agent_parsing = enable_agent_parsing
        self.agent_parser: Optional[AgentOutputParser] = None
        self.agent_event_callback: Optional[Callable[[AgentEvent], None]] = None

    def spawn(self) -> None:
        """Spawn shell process without PTY"""
        shell = os.environ.get("COMSPEC", r"C:\Windows\System32\cmd.exe")

        self._process = subprocess.Popen(
            shell,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            creationflags=(
                subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
            ),
        )

        self.pid = self._process.pid
        self.running = True
        logger.info(f"Spawned subprocess shell: pid={self.pid}")

    def resize(self, cols: int, rows: int) -> None:
        """Resize is not supported in subprocess mode"""
        self.cols = cols
        self.rows = rows
        logger.debug("Resize not supported in subprocess mode")

    def write(self, data: str) -> None:
        """Write to shell stdin"""
        if self._process is None or self._process.stdin is None:
            return
        try:
            self._process.stdin.write(data)
            self._process.stdin.flush()
        except Exception as e:
            logger.error(f"Failed to write to shell: {e}")
            self.running = False

    def set_agent_event_callback(self, callback: Callable[[AgentEvent], None]) -> None:
        self.agent_event_callback = callback

    async def read(self, callback: Callable[[str], None]) -> None:
        """Read shell output"""
        if self._process is None or self._process.stdout is None:
            return

        def read_thread():
            while self.running and self._process and self._process.poll() is None:
                try:
                    line = self._process.stdout.readline()
                    if line:
                        callback(line)
                except Exception as e:
                    logger.error(f"Read error: {e}")
                    break
            self.running = False

        self.read_thread = threading.Thread(target=read_thread, daemon=True)
        self.read_thread.start()

        while self.running and self.read_thread.is_alive():
            await asyncio.sleep(0.1)

    def close(self) -> None:
        """Close shell process"""
        self.running = False
        if self._process:
            try:
                self._process.terminate()
                self._process.wait(timeout=1)
            except Exception:
                self._process.kill()
            self._process = None

    def __del__(self):
        self.close()
