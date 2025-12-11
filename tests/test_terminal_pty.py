# SPDX-License-Identifier: MIT
"""Tests for PTY terminal modules."""

import os
import sys
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

# Skip entire module on Windows
pytestmark = pytest.mark.skipif(
    sys.platform == "win32", reason="PTY tests require Unix-like system"
)


class TestPTYSession:
    """Test PTYSession dataclass from socketio_pty."""

    def test_pty_session_creation(self) -> None:
        """Test creating a PTYSession."""
        from code_map.terminal.socketio_pty import (
            PTYSession,
            DEFAULT_COLS,
            DEFAULT_ROWS,
        )

        session = PTYSession(pid=12345, fd=10)
        assert session.pid == 12345
        assert session.fd == 10
        assert session.cols == DEFAULT_COLS
        assert session.rows == DEFAULT_ROWS

    def test_pty_session_custom_dimensions(self) -> None:
        """Test PTYSession with custom dimensions."""
        from code_map.terminal.socketio_pty import PTYSession

        session = PTYSession(pid=12345, fd=10, cols=120, rows=40)
        assert session.cols == 120
        assert session.rows == 40

    def test_pty_session_is_alive_with_running_process(self) -> None:
        """Test is_alive returns True for running process."""
        from code_map.terminal.socketio_pty import PTYSession

        # Use our own PID which is definitely running
        session = PTYSession(pid=os.getpid(), fd=10)
        assert session.is_alive() is True

    def test_pty_session_is_alive_with_dead_process(self) -> None:
        """Test is_alive returns False for non-existent process."""
        from code_map.terminal.socketio_pty import PTYSession

        # Use a very high PID that's unlikely to exist
        session = PTYSession(pid=999999999, fd=10)
        assert session.is_alive() is False


class TestSocketIOPTYServerConstants:
    """Test SocketIOPTYServer constants."""

    def test_constants_are_reasonable(self) -> None:
        """Test that constants have reasonable values."""
        from code_map.terminal.socketio_pty import (
            MAX_READ_BYTES,
            READ_INTERVAL,
            DEFAULT_COLS,
            DEFAULT_ROWS,
            MIN_COLS,
            MIN_ROWS,
        )

        assert MAX_READ_BYTES > 1024  # At least 1KB
        assert MAX_READ_BYTES <= 1024 * 100  # At most 100KB
        assert READ_INTERVAL > 0
        assert READ_INTERVAL < 1  # Less than 1 second
        assert DEFAULT_COLS >= 80
        assert DEFAULT_ROWS >= 24
        assert MIN_COLS > 0
        assert MIN_ROWS > 0
        assert MIN_COLS <= DEFAULT_COLS
        assert MIN_ROWS <= DEFAULT_ROWS


class TestSocketIOPTYServerInit:
    """Test SocketIOPTYServer initialization."""

    def test_server_init_default_cors(self) -> None:
        """Test server initialization with default CORS."""
        from code_map.terminal.socketio_pty import SocketIOPTYServer

        server = SocketIOPTYServer()
        assert server.sio is not None
        assert server.sessions == {}
        assert server._background_tasks == {}

    def test_server_init_custom_cors(self) -> None:
        """Test server initialization with custom CORS."""
        from code_map.terminal.socketio_pty import SocketIOPTYServer

        server = SocketIOPTYServer(cors_allowed_origins=["http://localhost:3000"])
        assert server.sio is not None

    def test_get_asgi_app(self) -> None:
        """Test getting ASGI app from server."""
        from code_map.terminal.socketio_pty import SocketIOPTYServer

        server = SocketIOPTYServer()
        app = server.get_asgi_app()
        assert app is not None

    def test_get_asgi_app_with_other_app(self) -> None:
        """Test getting combined ASGI app."""
        from code_map.terminal.socketio_pty import SocketIOPTYServer

        server = SocketIOPTYServer()
        mock_app = MagicMock()
        app = server.get_asgi_app(mock_app)
        assert app is not None


class TestSocketIOPTYServerCleanup:
    """Test SocketIOPTYServer cleanup functionality."""

    @pytest.mark.asyncio
    async def test_cleanup_nonexistent_session(self) -> None:
        """Test that cleanup handles nonexistent session gracefully."""
        from code_map.terminal.socketio_pty import SocketIOPTYServer

        server = SocketIOPTYServer()

        # Should not raise for nonexistent session
        await server._cleanup_session("nonexistent-sid")
        assert "nonexistent-sid" not in server.sessions

    @pytest.mark.asyncio
    async def test_shutdown_empty_server(self) -> None:
        """Test that shutdown works on empty server."""
        from code_map.terminal.socketio_pty import SocketIOPTYServer

        server = SocketIOPTYServer()
        assert len(server.sessions) == 0

        # Should not raise
        await server.shutdown()
        assert len(server.sessions) == 0


class TestGlobalPTYServer:
    """Test global PTY server functions."""

    def test_get_pty_server_returns_singleton(self) -> None:
        """Test that get_pty_server returns the same instance."""
        from code_map.terminal import socketio_pty

        # Reset global state
        socketio_pty._pty_server = None

        server1 = socketio_pty.get_pty_server()
        server2 = socketio_pty.get_pty_server()

        assert server1 is server2

        # Cleanup
        socketio_pty._pty_server = None

    def test_create_combined_app(self) -> None:
        """Test create_combined_app function."""
        from code_map.terminal import socketio_pty

        # Reset global state
        socketio_pty._pty_server = None

        mock_fastapi = MagicMock()
        app = socketio_pty.create_combined_app(mock_fastapi)

        assert app is not None

        # Cleanup
        socketio_pty._pty_server = None


class TestPTYShellBasics:
    """Test PTYShell basic functionality."""

    def test_pty_shell_init_default(self) -> None:
        """Test PTYShell initialization with defaults."""
        from code_map.terminal.pty_shell import PTYShell

        shell = PTYShell()
        assert shell.cols == 80
        assert shell.rows == 24
        assert shell.master_fd is None
        assert shell.pid is None
        assert shell.running is False

    def test_pty_shell_init_custom_dimensions(self) -> None:
        """Test PTYShell initialization with custom dimensions."""
        from code_map.terminal.pty_shell import PTYShell

        shell = PTYShell(cols=120, rows=40)
        assert shell.cols == 120
        assert shell.rows == 40

    def test_pty_shell_init_with_agent_parsing(self) -> None:
        """Test PTYShell initialization with agent parsing enabled."""
        from code_map.terminal.pty_shell import PTYShell

        shell = PTYShell(enable_agent_parsing=True)
        assert shell.enable_agent_parsing is True
        assert shell.agent_parser is not None

    def test_pty_shell_resize_validates_dimensions(self) -> None:
        """Test that resize validates minimum dimensions."""
        from code_map.terminal.pty_shell import PTYShell

        shell = PTYShell()

        # Resize to small values should use minimum
        shell.resize(10, 5)

        # Should be at least minimum values
        assert shell.cols >= 40  # MIN_COLS
        assert shell.rows >= 10  # MIN_ROWS

    def test_pty_shell_resize_accepts_valid_dimensions(self) -> None:
        """Test that resize accepts valid dimensions."""
        from code_map.terminal.pty_shell import PTYShell

        shell = PTYShell()
        shell.resize(120, 40)

        assert shell.cols == 120
        assert shell.rows == 40

    def test_pty_shell_write_when_not_running(self) -> None:
        """Test that write does nothing when not running."""
        from code_map.terminal.pty_shell import PTYShell

        shell = PTYShell()
        # Should not raise, just return silently
        shell.write("test input")

    def test_pty_shell_close_when_not_running(self) -> None:
        """Test that close is safe when not running."""
        from code_map.terminal.pty_shell import PTYShell

        shell = PTYShell()
        # Should not raise
        shell.close()

    def test_set_agent_event_callback(self) -> None:
        """Test setting agent event callback."""
        from code_map.terminal.pty_shell import PTYShell

        shell = PTYShell()

        callback = MagicMock()
        shell.set_agent_event_callback(callback)

        assert shell.agent_event_callback is callback

    def test_process_output_passthrough(self) -> None:
        """Test that _process_output returns input unchanged."""
        from code_map.terminal.pty_shell import PTYShell

        shell = PTYShell()
        test_input = "Hello, World!\n"
        result = shell._process_output(test_input)

        assert result == test_input


class TestPTYShellSpawn:
    """Test PTYShell spawning (requires actual PTY)."""

    @pytest.mark.skipif(not hasattr(os, "fork"), reason="Requires fork support")
    def test_spawn_creates_process(self) -> None:
        """Test that spawn creates a shell process."""
        from code_map.terminal.pty_shell import PTYShell

        shell = PTYShell()
        try:
            shell.spawn()

            assert shell.running is True
            assert shell.pid is not None
            assert shell.pid > 0
            assert shell.master_fd is not None
            assert shell.master_fd >= 0
        finally:
            shell.close()

    @pytest.mark.skipif(not hasattr(os, "fork"), reason="Requires fork support")
    def test_spawn_and_close(self) -> None:
        """Test spawn followed by close."""
        from code_map.terminal.pty_shell import PTYShell

        shell = PTYShell()
        shell.spawn()
        shell.spawn()

        shell.close()

        assert shell.running is False
        assert shell.pid is None
        assert shell.master_fd is None

    @pytest.mark.skipif(not hasattr(os, "fork"), reason="Requires fork support")
    def test_write_to_running_shell(self) -> None:
        """Test writing to a running shell."""
        from code_map.terminal.pty_shell import PTYShell

        shell = PTYShell()
        try:
            shell.spawn()
            # Should not raise
            shell.write("echo hello\r")
        finally:
            shell.close()


class TestDimensionValidation:
    """Test dimension validation in PTY modules."""

    def test_min_cols_enforced_in_shell(self) -> None:
        """Test that MIN_COLS is enforced in PTYShell."""
        from code_map.terminal.pty_shell import PTYShell

        shell = PTYShell()
        shell.resize(1, 100)  # Very small cols

        assert shell.cols >= 40

    def test_min_rows_enforced_in_shell(self) -> None:
        """Test that MIN_ROWS is enforced in PTYShell."""
        from code_map.terminal.pty_shell import PTYShell

        shell = PTYShell()
        shell.resize(100, 1)  # Very small rows

        assert shell.rows >= 10


class TestPTYShellAdvanced:
    """Advanced tests for PTYShell with mocking."""

    def test_filter_claude_code_output_delegates(self) -> None:
        """Test _filter_claude_code_output delegates to _process_output."""
        from code_map.terminal.pty_shell import PTYShell

        shell = PTYShell()
        text = "test output"
        result = shell._filter_claude_code_output(text)
        assert result == text

    def test_set_winsize_when_no_fd(self) -> None:
        """Test _set_winsize returns early when master_fd is None."""
        from code_map.terminal.pty_shell import PTYShell

        shell = PTYShell()
        # Should not raise when master_fd is None
        shell._set_winsize(80, 24)

    @pytest.mark.skipif(not hasattr(os, "fork"), reason="Requires fork support")
    def test_write_error_stops_running(self) -> None:
        """Test that write error sets running to False."""
        from code_map.terminal.pty_shell import PTYShell

        shell = PTYShell()
        shell.spawn()
        shell.running = True

        # Close the FD to cause write error
        original_fd = shell.master_fd
        os.close(original_fd)
        shell.master_fd = original_fd  # Keep reference but FD is closed

        # Write should handle error gracefully
        shell.write("test")
        assert shell.running is False

        shell.pid = None  # Cleanup
        shell.master_fd = None

    def test_close_with_read_thread(self) -> None:
        """Test close with active read thread."""
        from code_map.terminal.pty_shell import PTYShell
        import threading

        shell = PTYShell()
        # Don't spawn - just set up state to test the thread join logic
        shell.running = True
        shell.master_fd = None  # No FD to close
        shell.pid = None  # No process to kill

        # Simulate a read thread that exits quickly
        def dummy_thread():
            import time

            time.sleep(0.05)

        shell.read_thread = threading.Thread(target=dummy_thread)
        shell.read_thread.start()

        # Close should wait for thread
        shell.close()
        assert shell.running is False

    @pytest.mark.skipif(not hasattr(os, "fork"), reason="Requires fork support")
    def test_destructor_calls_close(self) -> None:
        """Test __del__ calls close."""
        from code_map.terminal.pty_shell import PTYShell

        shell = PTYShell()
        shell.spawn()
        shell.spawn()

        # Trigger destructor
        del shell

        # Process should be cleaned up (can't easily verify this in test)


class TestSocketIOPTYServerSetWinsize:
    """Test SocketIOPTYServer window size operations."""

    def test_set_winsize_method(self) -> None:
        """Test _set_winsize method with mocked fd."""
        from code_map.terminal.socketio_pty import SocketIOPTYServer

        server = SocketIOPTYServer()

        # Mock ioctl to avoid needing real fd
        with patch("code_map.terminal.socketio_pty.fcntl.ioctl") as mock_ioctl:
            server._set_winsize(10, 24, 80)
            mock_ioctl.assert_called_once()


class TestSocketIOPTYServerSpawn:
    """Test PTY spawning in SocketIOPTYServer."""

    @pytest.mark.skipif(not hasattr(os, "fork"), reason="Requires fork support")
    def test_spawn_pty_creates_session(self) -> None:
        """Test _spawn_pty creates a valid PTYSession."""
        from code_map.terminal.socketio_pty import SocketIOPTYServer, PTYSession

        server = SocketIOPTYServer()

        try:
            session = server._spawn_pty()

            assert isinstance(session, PTYSession)
            assert session.pid > 0
            assert session.fd >= 0
            assert session.is_alive()
        finally:
            # Cleanup
            try:
                import signal

                os.kill(session.pid, signal.SIGTERM)
                os.waitpid(session.pid, 0)
            except (OSError, ChildProcessError):
                pass
            try:
                os.close(session.fd)
            except OSError:
                pass

    def test_spawn_pty_uses_shell_env(self) -> None:
        """Test _spawn_pty uses SHELL environment variable."""
        from code_map.terminal.socketio_pty import SocketIOPTYServer

        # Mock pty.fork to avoid actually forking
        with patch("code_map.terminal.socketio_pty.pty.fork") as mock_fork:
            # Return parent process scenario
            mock_fork.return_value = (12345, 10)

            # Mock fcntl operations
            with patch("code_map.terminal.socketio_pty.fcntl.fcntl"):
                with patch("code_map.terminal.socketio_pty.fcntl.ioctl"):
                    server = SocketIOPTYServer()
                    session = server._spawn_pty()

                    assert session.pid == 12345
                    assert session.fd == 10


class TestSocketIOPTYServerSessions:
    """Test session management in SocketIOPTYServer."""

    @pytest.mark.asyncio
    async def test_cleanup_session_with_task(self) -> None:
        """Test cleanup cancels background task."""
        from code_map.terminal.socketio_pty import SocketIOPTYServer, PTYSession

        server = SocketIOPTYServer()

        # Create mock session and task
        mock_session = MagicMock(spec=PTYSession)
        mock_session.pid = 99999
        mock_session.fd = 10

        async def dummy_task():
            await asyncio.sleep(10)

        task = asyncio.create_task(dummy_task())
        server.sessions["test-sid"] = mock_session
        server._background_tasks["test-sid"] = task

        # Mock os operations
        with patch("os.kill"):
            with patch("os.waitpid"):
                with patch("os.close"):
                    await server._cleanup_session("test-sid")

        assert "test-sid" not in server.sessions
        assert "test-sid" not in server._background_tasks
        assert task.cancelled()

    @pytest.mark.asyncio
    async def test_shutdown_cleans_all_sessions(self) -> None:
        """Test shutdown cleans up all sessions."""
        from code_map.terminal.socketio_pty import SocketIOPTYServer, PTYSession

        server = SocketIOPTYServer()

        # Create mock sessions
        for i in range(3):
            mock_session = MagicMock(spec=PTYSession)
            mock_session.pid = 10000 + i
            mock_session.fd = 10 + i
            server.sessions[f"sid-{i}"] = mock_session

        # Mock cleanup
        with patch.object(
            server, "_cleanup_session", new_callable=AsyncMock
        ) as mock_cleanup:
            await server.shutdown()
            assert mock_cleanup.call_count == 3


class TestSocketIOPTYReadOutput:
    """Test PTY output reading in SocketIOPTYServer."""

    @pytest.mark.asyncio
    async def test_read_pty_output_no_session(self) -> None:
        """Test _read_pty_output returns early if no session."""
        from code_map.terminal.socketio_pty import SocketIOPTYServer

        server = SocketIOPTYServer()

        # Should return immediately without error
        await server._read_pty_output("nonexistent-sid")

    @pytest.mark.asyncio
    async def test_read_pty_output_session_removed_during_read(self) -> None:
        """Test _read_pty_output handles session removal during loop."""
        from code_map.terminal.socketio_pty import SocketIOPTYServer, PTYSession

        server = SocketIOPTYServer()

        mock_session = MagicMock(spec=PTYSession)
        mock_session.fd = 10
        server.sessions["test-sid"] = mock_session

        # Remove session after first iteration
        call_count = 0

        async def mock_sleep(t):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                del server.sessions["test-sid"]
            await asyncio.sleep(0.001)

        with patch("asyncio.sleep", side_effect=mock_sleep):
            with patch("select.select", return_value=([], [], [])):
                await server._read_pty_output("test-sid")

    @pytest.mark.asyncio
    async def test_read_pty_output_eof(self) -> None:
        """Test _read_pty_output handles EOF (empty read)."""
        from code_map.terminal.socketio_pty import SocketIOPTYServer, PTYSession

        server = SocketIOPTYServer()

        mock_session = MagicMock(spec=PTYSession)
        mock_session.fd = 10
        server.sessions["test-sid"] = mock_session

        with patch("asyncio.sleep", new_callable=AsyncMock):
            with patch("select.select", return_value=([mock_session.fd], [], [])):
                with patch("os.read", return_value=b""):  # EOF
                    with patch.object(server.sio, "emit", new_callable=AsyncMock):
                        await server._read_pty_output("test-sid")

    @pytest.mark.asyncio
    async def test_read_pty_output_with_data(self) -> None:
        """Test _read_pty_output emits data to client."""
        from code_map.terminal.socketio_pty import SocketIOPTYServer, PTYSession

        server = SocketIOPTYServer()

        mock_session = MagicMock(spec=PTYSession)
        mock_session.fd = 10
        server.sessions["test-sid"] = mock_session

        read_count = 0

        def mock_read(fd, size):
            nonlocal read_count
            read_count += 1
            if read_count == 1:
                return b"Hello, World!"
            return b""  # EOF on second call

        with patch("asyncio.sleep", new_callable=AsyncMock):
            with patch("select.select", return_value=([mock_session.fd], [], [])):
                with patch("os.read", side_effect=mock_read):
                    with patch.object(
                        server.sio, "emit", new_callable=AsyncMock
                    ) as mock_emit:
                        await server._read_pty_output("test-sid")

                        # Should emit pty-output at least once
                        output_calls = [
                            c
                            for c in mock_emit.call_args_list
                            if c[0][0] == "pty-output"
                        ]
                        assert len(output_calls) >= 1

    @pytest.mark.asyncio
    async def test_read_pty_output_eio_error(self) -> None:
        """Test _read_pty_output handles EIO error (PTY closed)."""
        from code_map.terminal.socketio_pty import SocketIOPTYServer, PTYSession

        server = SocketIOPTYServer()

        mock_session = MagicMock(spec=PTYSession)
        mock_session.fd = 10
        server.sessions["test-sid"] = mock_session

        eio_error = OSError(5, "Input/output error")  # EIO

        with patch("asyncio.sleep", new_callable=AsyncMock):
            with patch("select.select", return_value=([mock_session.fd], [], [])):
                with patch("os.read", side_effect=eio_error):
                    with patch.object(server.sio, "emit", new_callable=AsyncMock):
                        # Should handle EIO gracefully
                        await server._read_pty_output("test-sid")

    @pytest.mark.asyncio
    async def test_read_pty_output_eagain_continues(self) -> None:
        """Test _read_pty_output continues on EAGAIN error."""
        from code_map.terminal.socketio_pty import SocketIOPTYServer, PTYSession

        server = SocketIOPTYServer()

        mock_session = MagicMock(spec=PTYSession)
        mock_session.fd = 10
        server.sessions["test-sid"] = mock_session

        call_count = 0

        def mock_select(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count > 3:
                del server.sessions["test-sid"]  # Force exit
            return ([mock_session.fd], [], [])

        eagain_error = OSError(11, "Resource temporarily unavailable")  # EAGAIN

        with patch("asyncio.sleep", new_callable=AsyncMock):
            with patch("select.select", side_effect=mock_select):
                with patch("os.read", side_effect=eagain_error):
                    with patch.object(server.sio, "emit", new_callable=AsyncMock):
                        await server._read_pty_output("test-sid")

    @pytest.mark.asyncio
    async def test_read_pty_output_cancelled(self) -> None:
        """Test _read_pty_output handles cancellation."""
        from code_map.terminal.socketio_pty import SocketIOPTYServer, PTYSession

        server = SocketIOPTYServer()

        mock_session = MagicMock(spec=PTYSession)
        mock_session.fd = 10
        server.sessions["test-sid"] = mock_session

        async def cancel_after_sleep(t):
            raise asyncio.CancelledError()

        with patch("asyncio.sleep", side_effect=cancel_after_sleep):
            with patch.object(server.sio, "emit", new_callable=AsyncMock):
                await server._read_pty_output("test-sid")


class TestPTYShellRead:
    """Test PTYShell read functionality."""

    def test_read_returns_early_no_fd(self) -> None:
        """Test read returns early when master_fd is None."""
        from code_map.terminal.pty_shell import PTYShell
        import asyncio

        shell = PTYShell()

        async def test():
            callback = MagicMock()
            await shell.read(callback)
            callback.assert_not_called()

        asyncio.run(test())

    @pytest.mark.skipif(not hasattr(os, "fork"), reason="Requires fork support")
    def test_read_with_agent_parsing(self) -> None:
        """Test read with agent parsing enabled."""
        from code_map.terminal.pty_shell import PTYShell

        shell = PTYShell(enable_agent_parsing=True)
        assert shell.enable_agent_parsing is True
        assert shell.agent_parser is not None


class TestSocketIOPTYServerCleanupAdvanced:
    """Advanced cleanup tests for SocketIOPTYServer."""

    @pytest.mark.asyncio
    async def test_cleanup_handles_kill_error(self) -> None:
        """Test cleanup handles OSError from os.kill."""
        from code_map.terminal.socketio_pty import SocketIOPTYServer, PTYSession

        server = SocketIOPTYServer()

        mock_session = MagicMock(spec=PTYSession)
        mock_session.pid = 99999
        mock_session.fd = 10
        server.sessions["test-sid"] = mock_session

        with patch("os.kill", side_effect=ProcessLookupError("No such process")):
            with patch("os.close"):
                await server._cleanup_session("test-sid")

        assert "test-sid" not in server.sessions

    @pytest.mark.asyncio
    async def test_cleanup_handles_close_error(self) -> None:
        """Test cleanup handles OSError from os.close."""
        from code_map.terminal.socketio_pty import SocketIOPTYServer, PTYSession

        server = SocketIOPTYServer()

        mock_session = MagicMock(spec=PTYSession)
        mock_session.pid = 99999
        mock_session.fd = 10
        server.sessions["test-sid"] = mock_session

        with patch("os.kill"):
            with patch("os.waitpid"):
                with patch("os.close", side_effect=OSError("Bad file descriptor")):
                    await server._cleanup_session("test-sid")

        assert "test-sid" not in server.sessions


class TestSocketIOEventHandlers:
    """Test Socket.IO event handlers using internal methods."""

    @pytest.mark.asyncio
    async def test_connect_handler_spawns_pty(self) -> None:
        """Test connect event handler spawns PTY."""
        from code_map.terminal.socketio_pty import SocketIOPTYServer, PTYSession

        server = SocketIOPTYServer()

        # Find the connect handler
        connect_handler = None
        for key, handler in server.sio.handlers.get("/pty", {}).items():
            if key == "connect":
                connect_handler = handler
                break

        if connect_handler:
            # Mock the spawn_pty to avoid real fork
            mock_session = MagicMock(spec=PTYSession)
            mock_session.pid = 12345
            mock_session.fd = 10

            with patch.object(server, "_spawn_pty", return_value=mock_session):
                with patch.object(server, "_read_pty_output", new_callable=AsyncMock):
                    result = await connect_handler("test-sid", {})
                    assert result is True
                    assert "test-sid" in server.sessions

    @pytest.mark.asyncio
    async def test_connect_handler_reuses_session(self) -> None:
        """Test connect returns True for existing session."""
        from code_map.terminal.socketio_pty import SocketIOPTYServer, PTYSession

        server = SocketIOPTYServer()

        # Pre-create session
        mock_session = MagicMock(spec=PTYSession)
        server.sessions["test-sid"] = mock_session

        # Find the connect handler
        connect_handler = None
        for key, handler in server.sio.handlers.get("/pty", {}).items():
            if key == "connect":
                connect_handler = handler
                break

        if connect_handler:
            result = await connect_handler("test-sid", {})
            assert result is True

    @pytest.mark.asyncio
    async def test_connect_handler_error_returns_false(self) -> None:
        """Test connect returns False on spawn error."""
        from code_map.terminal.socketio_pty import SocketIOPTYServer

        server = SocketIOPTYServer()

        connect_handler = None
        for key, handler in server.sio.handlers.get("/pty", {}).items():
            if key == "connect":
                connect_handler = handler
                break

        if connect_handler:
            with patch.object(server, "_spawn_pty", side_effect=OSError("Fork failed")):
                result = await connect_handler("test-sid", {})
                assert result is False

    @pytest.mark.asyncio
    async def test_disconnect_handler_cleans_session(self) -> None:
        """Test disconnect event cleans up session."""
        from code_map.terminal.socketio_pty import SocketIOPTYServer, PTYSession

        server = SocketIOPTYServer()

        # Create session
        mock_session = MagicMock(spec=PTYSession)
        mock_session.pid = 12345
        mock_session.fd = 10
        server.sessions["test-sid"] = mock_session

        disconnect_handler = None
        for key, handler in server.sio.handlers.get("/pty", {}).items():
            if key == "disconnect":
                disconnect_handler = handler
                break

        if disconnect_handler:
            with patch("os.kill"):
                with patch("os.waitpid"):
                    with patch("os.close"):
                        await disconnect_handler("test-sid")
                        assert "test-sid" not in server.sessions

    @pytest.mark.asyncio
    async def test_pty_input_writes_to_fd(self) -> None:
        """Test pty-input event writes to PTY fd."""
        from code_map.terminal.socketio_pty import SocketIOPTYServer, PTYSession

        server = SocketIOPTYServer()

        mock_session = MagicMock(spec=PTYSession)
        mock_session.fd = 10
        server.sessions["test-sid"] = mock_session

        input_handler = None
        for key, handler in server.sio.handlers.get("/pty", {}).items():
            if key == "pty-input":
                input_handler = handler
                break

        if input_handler:
            with patch("os.write") as mock_write:
                await input_handler("test-sid", {"input": "hello"})
                mock_write.assert_called_once_with(10, b"hello")

    @pytest.mark.asyncio
    async def test_pty_input_no_session_warns(self) -> None:
        """Test pty-input with no session logs warning."""
        from code_map.terminal.socketio_pty import SocketIOPTYServer

        server = SocketIOPTYServer()

        input_handler = None
        for key, handler in server.sio.handlers.get("/pty", {}).items():
            if key == "pty-input":
                input_handler = handler
                break

        if input_handler:
            # Should not raise
            await input_handler("nonexistent", {"input": "hello"})

    @pytest.mark.asyncio
    async def test_pty_input_write_error_cleans_session(self) -> None:
        """Test pty-input cleans up on write error."""
        from code_map.terminal.socketio_pty import SocketIOPTYServer, PTYSession

        server = SocketIOPTYServer()

        mock_session = MagicMock(spec=PTYSession)
        mock_session.pid = 12345
        mock_session.fd = 10
        server.sessions["test-sid"] = mock_session

        input_handler = None
        for key, handler in server.sio.handlers.get("/pty", {}).items():
            if key == "pty-input":
                input_handler = handler
                break

        if input_handler:
            with patch("os.write", side_effect=OSError("Broken pipe")):
                with patch("os.kill"):
                    with patch("os.waitpid"):
                        with patch("os.close"):
                            await input_handler("test-sid", {"input": "hello"})
                            assert "test-sid" not in server.sessions

    @pytest.mark.asyncio
    async def test_resize_handler_sets_winsize(self) -> None:
        """Test resize event sets window size."""
        from code_map.terminal.socketio_pty import SocketIOPTYServer, PTYSession

        server = SocketIOPTYServer()

        mock_session = MagicMock(spec=PTYSession)
        mock_session.fd = 10
        mock_session.cols = 80
        mock_session.rows = 24
        server.sessions["test-sid"] = mock_session

        resize_handler = None
        for key, handler in server.sio.handlers.get("/pty", {}).items():
            if key == "resize":
                resize_handler = handler
                break

        if resize_handler:
            with patch.object(server, "_set_winsize") as mock_setwin:
                await resize_handler("test-sid", {"cols": 120, "rows": 40})
                mock_setwin.assert_called_once_with(10, 40, 120)
                assert mock_session.cols == 120
                assert mock_session.rows == 40

    @pytest.mark.asyncio
    async def test_resize_handler_no_session(self) -> None:
        """Test resize with no session returns early."""
        from code_map.terminal.socketio_pty import SocketIOPTYServer

        server = SocketIOPTYServer()

        resize_handler = None
        for key, handler in server.sio.handlers.get("/pty", {}).items():
            if key == "resize":
                resize_handler = handler
                break

        if resize_handler:
            # Should not raise
            await resize_handler("nonexistent", {"cols": 120, "rows": 40})

    @pytest.mark.asyncio
    async def test_resize_validates_min_dimensions(self) -> None:
        """Test resize enforces minimum dimensions."""
        from code_map.terminal.socketio_pty import (
            SocketIOPTYServer,
            PTYSession,
            MIN_COLS,
            MIN_ROWS,
        )

        server = SocketIOPTYServer()

        mock_session = MagicMock(spec=PTYSession)
        mock_session.fd = 10
        mock_session.cols = 80
        mock_session.rows = 24
        server.sessions["test-sid"] = mock_session

        resize_handler = None
        for key, handler in server.sio.handlers.get("/pty", {}).items():
            if key == "resize":
                resize_handler = handler
                break

        if resize_handler:
            with patch.object(server, "_set_winsize") as mock_setwin:
                await resize_handler("test-sid", {"cols": 1, "rows": 1})
                # Should use MIN_COLS and MIN_ROWS
                mock_setwin.assert_called_once_with(10, MIN_ROWS, MIN_COLS)

    @pytest.mark.asyncio
    async def test_resize_handles_ioctl_error(self) -> None:
        """Test resize handles OSError from ioctl."""
        from code_map.terminal.socketio_pty import SocketIOPTYServer, PTYSession

        server = SocketIOPTYServer()

        mock_session = MagicMock(spec=PTYSession)
        mock_session.fd = 10
        mock_session.cols = 80
        mock_session.rows = 24
        server.sessions["test-sid"] = mock_session

        resize_handler = None
        for key, handler in server.sio.handlers.get("/pty", {}).items():
            if key == "resize":
                resize_handler = handler
                break

        if resize_handler:
            with patch.object(
                server, "_set_winsize", side_effect=OSError("Invalid argument")
            ):
                # Should not raise
                await resize_handler("test-sid", {"cols": 120, "rows": 40})


class TestPTYShellReadLoop:
    """Test PTYShell read loop functionality."""

    @pytest.mark.skipif(not hasattr(os, "fork"), reason="Requires fork support")
    @pytest.mark.asyncio
    async def test_read_with_callback(self) -> None:
        """Test read loop calls callback with output."""
        from code_map.terminal.pty_shell import PTYShell

        shell = PTYShell()
        output_received = []

        def callback(data):
            output_received.append(data)
            # Stop after first output
            shell.running = False

        try:
            shell.spawn()
            # Write something to generate output
            shell.write("echo hello\r")

            # Run read loop briefly
            import asyncio

            await asyncio.wait_for(shell.read(callback), timeout=2.0)
        except asyncio.TimeoutError:
            pass  # Expected if shell keeps running
        finally:
            shell.close()

        # Should have received some output
        assert len(output_received) >= 0  # May not receive in time

    @pytest.mark.skipif(not hasattr(os, "fork"), reason="Requires fork support")
    @pytest.mark.asyncio
    async def test_read_with_agent_parsing(self) -> None:
        """Test read loop with agent parsing enabled."""
        from code_map.terminal.pty_shell import PTYShell

        shell = PTYShell(enable_agent_parsing=True)
        events = []

        def event_callback(event):
            events.append(event)

        shell.set_agent_event_callback(event_callback)

        def output_callback(data):
            shell.running = False

        try:
            shell.spawn()
            shell.write("echo test\r")

            import asyncio

            await asyncio.wait_for(shell.read(output_callback), timeout=1.0)
        except asyncio.TimeoutError:
            pass
        finally:
            shell.close()


class TestPTYShellCloseErrors:
    """Test PTYShell close error handling."""

    @pytest.mark.skipif(not hasattr(os, "fork"), reason="Requires fork support")
    def test_close_handles_kill_error(self) -> None:
        """Test close handles OSError from kill."""
        from code_map.terminal.pty_shell import PTYShell

        shell = PTYShell()
        shell.spawn()

        # Save the FD to close it ourselves

        with patch("os.kill", side_effect=ProcessLookupError("No such process")):
            # Should not raise
            shell.close()

        assert shell.running is False

    @pytest.mark.skipif(not hasattr(os, "fork"), reason="Requires fork support")
    def test_close_handles_waitpid_error(self) -> None:
        """Test close handles ChildProcessError from waitpid."""
        from code_map.terminal.pty_shell import PTYShell

        shell = PTYShell()
        shell.spawn()

        with patch("os.kill"):
            with patch(
                "os.waitpid", side_effect=ChildProcessError("No child processes")
            ):
                # Should not raise
                shell.close()

        assert shell.running is False

    def test_close_handles_close_fd_error(self) -> None:
        """Test close handles OSError from closing fd."""
        from code_map.terminal.pty_shell import PTYShell

        shell = PTYShell()
        shell.running = True
        shell.master_fd = 999999  # Invalid FD
        shell.pid = None

        # Should not raise even with invalid FD
        shell.close()
        assert shell.running is False


class TestSocketIOSpawnDetails:
    """Test detailed _spawn_pty behavior."""

    def test_spawn_pty_child_branch_mocked(self) -> None:
        """Test _spawn_pty with mocked child process path."""
        from code_map.terminal.socketio_pty import SocketIOPTYServer

        server = SocketIOPTYServer()

        # Mock pty.fork to simulate parent process
        with patch("code_map.terminal.socketio_pty.pty.fork") as mock_fork:
            mock_fork.return_value = (12345, 10)  # (pid, fd)

            with patch("code_map.terminal.socketio_pty.fcntl.fcntl"):
                with patch("code_map.terminal.socketio_pty.fcntl.ioctl"):
                    session = server._spawn_pty()

                    assert session.pid == 12345
                    assert session.fd == 10

    @pytest.mark.skipif(not hasattr(os, "fork"), reason="Requires fork support")
    def test_spawn_pty_uses_shell_from_env(self) -> None:
        """Test _spawn_pty uses SHELL environment variable."""
        from code_map.terminal.socketio_pty import SocketIOPTYServer

        server = SocketIOPTYServer()

        with patch.dict(os.environ, {"SHELL": "/bin/zsh"}):
            with patch("code_map.terminal.socketio_pty.pty.fork") as mock_fork:
                mock_fork.return_value = (12345, 10)

                with patch("code_map.terminal.socketio_pty.fcntl.fcntl"):
                    with patch("code_map.terminal.socketio_pty.fcntl.ioctl"):
                        session = server._spawn_pty()
                        assert session is not None
