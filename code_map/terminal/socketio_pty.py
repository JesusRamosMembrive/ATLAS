"""
Socket.IO PTY Terminal Server

Based on pyxtermjs pattern for reliable terminal communication.
Uses python-socketio with ASGI for integration with FastAPI.

Cross-platform support:
- Unix: Uses native pty module
- Windows: Uses pywinpty via WinPTYShell

Key differences from WebSocket approach:
1. Socket.IO handles reconnection automatically
2. Typed events (pty-input, pty-output, resize) instead of text protocol
3. Larger read buffer (20KB) for better handling of TUI escape sequences
4. Non-blocking select with small sleep for responsive output
"""

import os
import sys
import struct
import signal
import asyncio
import logging
from typing import Optional, Dict, Any, Union
from dataclasses import dataclass, field

import socketio

# Platform detection
_IS_WINDOWS = sys.platform == "win32"

# Unix-only imports (pty, fcntl, termios, select)
if not _IS_WINDOWS:
    import pty
    import select
    import fcntl
    import termios
else:
    # Windows: Import WinPTYShell
    pty = None  # type: ignore
    select = None  # type: ignore
    fcntl = None  # type: ignore
    termios = None  # type: ignore

# Import Windows PTY shell if available
_WINPTY_AVAILABLE = False
WinPTYShell = None
if _IS_WINDOWS:
    try:
        from .winpty_shell import WinPTYShell, WINPTY_AVAILABLE as _WINPTY_AVAILABLE
    except ImportError:
        pass

logger = logging.getLogger(__name__)

# Constants matching pyxtermjs
MAX_READ_BYTES = 1024 * 20  # 20KB buffer like pyxtermjs
READ_INTERVAL = 0.01  # 10ms between reads like pyxtermjs
DEFAULT_COLS = 80
DEFAULT_ROWS = 24
MIN_COLS = 40
MIN_ROWS = 10


@dataclass
class PTYSession:
    """Represents an active PTY session (Unix)"""

    pid: int
    fd: int
    cols: int = DEFAULT_COLS
    rows: int = DEFAULT_ROWS

    def is_alive(self) -> bool:
        """Check if the PTY process is still running"""
        try:
            os.kill(self.pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False


@dataclass
class WinPTYSession:
    """Represents an active PTY session (Windows)"""

    shell: Any  # WinPTYShell instance
    cols: int = DEFAULT_COLS
    rows: int = DEFAULT_ROWS
    # For compatibility with PTYSession interface
    pid: int = field(default=0, init=False)
    fd: int = field(default=0, init=False)

    def __post_init__(self):
        if self.shell:
            self.pid = self.shell.pid or 0
            self.fd = self.pid  # Use pid as fd for compatibility

    def is_alive(self) -> bool:
        """Check if the PTY process is still running"""
        return self.shell is not None and self.shell.running


class SocketIOPTYServer:
    """
    Socket.IO server for PTY terminal access.

    Follows pyxtermjs pattern:
    - One PTY session per Socket.IO connection
    - Background task for continuous output reading
    - Typed events for input/output/resize

    Cross-platform:
    - Unix: Uses native pty.fork()
    - Windows: Uses pywinpty via WinPTYShell
    """

    def __init__(self, cors_allowed_origins: list[str] | str = "*"):
        """
        Initialize Socket.IO server for PTY.

        Args:
            cors_allowed_origins: CORS origins for Socket.IO
        """
        self.sio = socketio.AsyncServer(
            async_mode="asgi",
            cors_allowed_origins=cors_allowed_origins,
            logger=False,  # Use our own logging
            engineio_logger=False,
        )

        # Track sessions by socket ID
        self.sessions: Dict[str, Union[PTYSession, WinPTYSession]] = {}
        self._background_tasks: Dict[str, asyncio.Task] = {}

        # Platform availability
        if _IS_WINDOWS:
            self._pty_available = _WINPTY_AVAILABLE
            if _WINPTY_AVAILABLE:
                logger.info("[SocketIO PTY] Windows PTY available via pywinpty")
            else:
                logger.warning(
                    "[SocketIO PTY] Running on Windows - pywinpty not installed. "
                    "Install with: pip install pywinpty"
                )
        else:
            self._pty_available = True
            logger.info("[SocketIO PTY] Unix PTY available")

        # Register event handlers
        self._register_handlers()

    def _register_handlers(self):
        """Register Socket.IO event handlers"""

        @self.sio.on("connect", namespace="/pty")
        async def connect(sid, environ):
            """Handle new client connection - spawn PTY"""
            logger.info(f"[SocketIO PTY] Client connected: {sid}")

            # Check platform availability
            if not self._pty_available:
                logger.error("[SocketIO PTY] PTY not available on this platform")
                await self.sio.emit(
                    "pty-error",
                    {
                        "error": "PTY terminal not available. Install pywinpty on Windows."
                    },
                    namespace="/pty",
                    to=sid,
                )
                return False

            # Check if already has a session (reconnection)
            if sid in self.sessions:
                logger.info(f"[SocketIO PTY] Reusing existing session for {sid}")
                return True

            try:
                # Spawn PTY process
                session = self._spawn_pty()
                self.sessions[sid] = session

                logger.info(f"[SocketIO PTY] Spawned PTY for {sid}: pid={session.pid}")

                # Start background task for reading PTY output
                task = asyncio.create_task(
                    self._read_pty_output(sid), name=f"pty-reader-{sid}"
                )
                self._background_tasks[sid] = task

                return True

            except Exception as e:
                logger.error(f"[SocketIO PTY] Failed to spawn PTY for {sid}: {e}")
                await self.sio.emit(
                    "pty-error",
                    {"error": f"Failed to spawn terminal: {e}"},
                    namespace="/pty",
                    to=sid,
                )
                return False

        @self.sio.on("disconnect", namespace="/pty")
        async def disconnect(sid):
            """Handle client disconnection - cleanup PTY"""
            logger.info(f"[SocketIO PTY] Client disconnected: {sid}")
            await self._cleanup_session(sid)

        @self.sio.on("pty-input", namespace="/pty")
        async def pty_input(sid, data):
            """
            Handle input from browser terminal.

            Data format: {"input": "string"}
            """
            session = self.sessions.get(sid)
            if not session:
                logger.warning(f"[SocketIO PTY] No session for input from {sid}")
                return

            try:
                input_data = data.get("input", "")
                if input_data:
                    if _IS_WINDOWS and isinstance(session, WinPTYSession):
                        # Windows: Use WinPTYShell.write()
                        session.shell.write(input_data)
                    else:
                        # Unix: Write to fd
                        os.write(session.fd, input_data.encode("utf-8"))
                    logger.debug(
                        f"[SocketIO PTY] Wrote {len(input_data)} bytes to PTY {sid}"
                    )
            except OSError as e:
                logger.error(f"[SocketIO PTY] Failed to write to PTY {sid}: {e}")
                await self._cleanup_session(sid)

        @self.sio.on("resize", namespace="/pty")
        async def resize(sid, data):
            """
            Handle terminal resize from browser.

            Data format: {"cols": int, "rows": int}
            """
            session = self.sessions.get(sid)
            if not session:
                logger.warning(f"[SocketIO PTY] No session for resize from {sid}")
                return

            cols = data.get("cols", DEFAULT_COLS)
            rows = data.get("rows", DEFAULT_ROWS)

            # Validate dimensions
            if cols < MIN_COLS:
                logger.warning(f"[SocketIO PTY] Invalid cols={cols}, using {MIN_COLS}")
                cols = MIN_COLS
            if rows < MIN_ROWS:
                logger.warning(f"[SocketIO PTY] Invalid rows={rows}, using {MIN_ROWS}")
                rows = MIN_ROWS

            try:
                if _IS_WINDOWS and isinstance(session, WinPTYSession):
                    # Windows: Use WinPTYShell.resize()
                    session.shell.resize(cols, rows)
                else:
                    # Unix: Use ioctl
                    self._set_winsize(session.fd, rows, cols)
                session.cols = cols
                session.rows = rows
                logger.debug(f"[SocketIO PTY] Resized {sid} to {cols}x{rows}")
            except OSError as e:
                logger.error(f"[SocketIO PTY] Failed to resize PTY {sid}: {e}")

    def _spawn_pty(self) -> Union[PTYSession, WinPTYSession]:
        """
        Spawn a new PTY process with shell.

        Returns:
            PTYSession (Unix) or WinPTYSession (Windows)
        """
        if _IS_WINDOWS:
            return self._spawn_pty_windows()
        else:
            return self._spawn_pty_unix()

    def _spawn_pty_windows(self) -> WinPTYSession:
        """Spawn PTY on Windows using WinPTYShell"""
        if not _WINPTY_AVAILABLE or WinPTYShell is None:
            raise RuntimeError("pywinpty not available")

        shell = WinPTYShell(cols=DEFAULT_COLS, rows=DEFAULT_ROWS)
        shell.spawn()

        return WinPTYSession(shell=shell, cols=DEFAULT_COLS, rows=DEFAULT_ROWS)

    def _spawn_pty_unix(self) -> PTYSession:
        """Spawn PTY on Unix using pty.fork()"""
        # Determine shell
        shell = os.environ.get("SHELL", "/bin/bash")
        if not os.path.exists(shell):
            shell = "/bin/sh"

        # Fork with PTY
        pid, fd = pty.fork()

        if pid == 0:
            # Child process
            os.environ.update(
                {
                    "TERM": "xterm-256color",
                    "COLORTERM": "truecolor",
                    "LANG": os.environ.get("LANG", "C.UTF-8"),
                }
            )
            # Execute shell in interactive login mode
            os.execvp(shell, [shell, "-li"])
        else:
            # Parent process
            # Set initial window size
            self._set_winsize(fd, DEFAULT_ROWS, DEFAULT_COLS)

            # Make FD non-blocking
            flags = fcntl.fcntl(fd, fcntl.F_GETFL)
            fcntl.fcntl(fd, fcntl.F_SETFL, flags | os.O_NONBLOCK)

            return PTYSession(pid=pid, fd=fd)

    def _set_winsize(self, fd: int, rows: int, cols: int, xpix: int = 0, ypix: int = 0):
        """Set terminal window size using ioctl (Unix only)"""
        if _IS_WINDOWS:
            return  # No-op on Windows (handled by WinPTYShell)
        winsize = struct.pack("HHHH", rows, cols, xpix, ypix)
        fcntl.ioctl(fd, termios.TIOCSWINSZ, winsize)

    async def _read_pty_output(self, sid: str):
        """
        Background task to continuously read PTY output and send to client.
        """
        session = self.sessions.get(sid)
        if not session:
            return

        if _IS_WINDOWS and isinstance(session, WinPTYSession):
            await self._read_pty_output_windows(sid, session)
        else:
            await self._read_pty_output_unix(sid, session)

    async def _read_pty_output_windows(self, sid: str, session: WinPTYSession):
        """Read PTY output on Windows using WinPTYShell"""
        import queue

        logger.info(f"[SocketIO PTY] Starting Windows output reader for {sid}")

        # Queue for data from blocking read
        data_queue: queue.Queue[Optional[str]] = queue.Queue()

        def output_callback(text: str):
            """Callback for PTY output"""
            data_queue.put(text)

        try:
            # Start the read loop in background thread via WinPTYShell
            read_task = asyncio.create_task(session.shell.read(output_callback))

            while sid in self.sessions and session.shell.running:
                try:
                    # Non-blocking get with small timeout
                    try:
                        text = data_queue.get(timeout=0.05)
                    except queue.Empty:
                        await asyncio.sleep(READ_INTERVAL)
                        continue

                    if text is None:
                        break

                    # Send to client
                    await self.sio.emit(
                        "pty-output", {"output": text}, namespace="/pty", to=sid
                    )

                except Exception as e:
                    logger.error(f"[SocketIO PTY] Error reading Windows PTY {sid}: {e}")
                    break

            read_task.cancel()

        except asyncio.CancelledError:
            logger.info(f"[SocketIO PTY] Windows reader task cancelled for {sid}")
        except Exception as e:
            logger.error(
                f"[SocketIO PTY] Unexpected error in Windows reader for {sid}: {e}"
            )
        finally:
            logger.info(f"[SocketIO PTY] Windows reader exiting for {sid}")
            try:
                await self.sio.emit(
                    "pty-exit",
                    {"reason": "Shell process exited"},
                    namespace="/pty",
                    to=sid,
                )
            except Exception:
                pass

    async def _read_pty_output_unix(self, sid: str, session: PTYSession):
        """Read PTY output on Unix using select()"""
        logger.info(f"[SocketIO PTY] Starting Unix output reader for {sid}")

        try:
            while sid in self.sessions:
                await asyncio.sleep(READ_INTERVAL)  # 10ms like pyxtermjs

                session = self.sessions.get(sid)
                if not session or not isinstance(session, PTYSession):
                    break

                try:
                    # Non-blocking select (timeout=0) like pyxtermjs
                    readable, _, _ = select.select([session.fd], [], [], 0)

                    if readable:
                        output = os.read(session.fd, MAX_READ_BYTES)

                        if not output:
                            # EOF - shell exited
                            logger.info(f"[SocketIO PTY] EOF for {sid} - shell exited")
                            break

                        # Decode and send to client
                        text = output.decode("utf-8", errors="ignore")
                        await self.sio.emit(
                            "pty-output", {"output": text}, namespace="/pty", to=sid
                        )

                except OSError as e:
                    if e.errno == 5:  # EIO - PTY closed
                        logger.info(f"[SocketIO PTY] PTY closed for {sid}")
                        break
                    elif e.errno == 11:  # EAGAIN - no data available
                        continue
                    else:
                        logger.error(f"[SocketIO PTY] Read error for {sid}: {e}")
                        break

        except asyncio.CancelledError:
            logger.info(f"[SocketIO PTY] Unix reader task cancelled for {sid}")
        except Exception as e:
            logger.error(
                f"[SocketIO PTY] Unexpected error in Unix reader for {sid}: {e}"
            )
        finally:
            logger.info(f"[SocketIO PTY] Unix reader exiting for {sid}")
            # Notify client that session ended
            try:
                await self.sio.emit(
                    "pty-exit",
                    {"reason": "Shell process exited"},
                    namespace="/pty",
                    to=sid,
                )
            except Exception:
                pass

    async def _cleanup_session(self, sid: str):
        """Clean up PTY session and associated resources"""
        # Cancel background task
        task = self._background_tasks.pop(sid, None)
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        # Get and remove session
        session = self.sessions.pop(sid, None)
        if not session:
            return

        logger.info(f"[SocketIO PTY] Cleaning up session {sid}: pid={session.pid}")

        if _IS_WINDOWS and isinstance(session, WinPTYSession):
            # Windows: Close WinPTYShell
            try:
                session.shell.close()
            except Exception as e:
                logger.debug(f"[SocketIO PTY] Error closing Windows PTY: {e}")
        else:
            # Unix: Kill process and close fd
            try:
                os.kill(session.pid, signal.SIGTERM)
                await asyncio.sleep(0.1)
                try:
                    os.waitpid(session.pid, os.WNOHANG)
                except ChildProcessError:
                    pass
            except (OSError, ProcessLookupError):
                pass

            try:
                os.close(session.fd)
            except OSError:
                pass

    def get_asgi_app(self, other_app: Any = None) -> Any:
        """
        Get ASGI application that combines Socket.IO with another ASGI app.

        Args:
            other_app: Another ASGI app (e.g., FastAPI) to combine with

        Returns:
            Combined ASGI application
        """
        return socketio.ASGIApp(self.sio, other_app)

    async def shutdown(self):
        """Clean up all sessions on server shutdown"""
        logger.info(
            f"[SocketIO PTY] Shutting down, cleaning {len(self.sessions)} sessions"
        )

        for sid in list(self.sessions.keys()):
            await self._cleanup_session(sid)


# Global instance for the application
_pty_server: Optional[SocketIOPTYServer] = None


def get_pty_server(cors_allowed_origins: list[str] | str = "*") -> SocketIOPTYServer:
    """Get or create the global PTY server instance"""
    global _pty_server
    if _pty_server is None:
        _pty_server = SocketIOPTYServer(cors_allowed_origins=cors_allowed_origins)
    return _pty_server


def create_combined_app(
    fastapi_app: Any, cors_allowed_origins: list[str] | str = "*"
) -> Any:
    """
    Create a combined ASGI app with Socket.IO PTY server and FastAPI.

    Args:
        fastapi_app: The FastAPI application
        cors_allowed_origins: CORS origins for Socket.IO

    Returns:
        Combined ASGI application
    """
    pty_server = get_pty_server(cors_allowed_origins)
    return pty_server.get_asgi_app(fastapi_app)
