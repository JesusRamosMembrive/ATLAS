"""
Terminal API endpoints

Provides:
- REST endpoint for opening native terminal with agents
- WebSocket endpoint for remote shell access (legacy, use Socket.IO instead)

Socket.IO PTY is the primary terminal interface, configured in socketio_pty.py
"""

import asyncio
import logging
import sys
from typing import Optional, Literal
from fastapi import APIRouter, WebSocket
from pydantic import BaseModel

from code_map.exceptions import ValidationError, ServiceUnavailableError, InternalError
from code_map.terminal import _PTY_AVAILABLE
from code_map.settings import load_settings

# Platform detection
_IS_WINDOWS = sys.platform == "win32"

# PTYShell for legacy WebSocket endpoint
if _PTY_AVAILABLE:
    from code_map.terminal import PTYShell
else:
    PTYShell = None  # type: ignore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/terminal", tags=["terminal"])


# ============================================================================
# REST Endpoints for Native Terminal Launch
# ============================================================================


class OpenNativeTerminalRequest(BaseModel):
    """Request body for opening a native system terminal with an agent."""
    agent_type: Literal["claude", "codex", "gemini"]
    working_directory: Optional[str] = None


class OpenNativeTerminalResponse(BaseModel):
    """Response from opening a native terminal."""
    success: bool
    message: str
    terminal: Optional[str] = None


@router.post("/open-native", response_model=OpenNativeTerminalResponse)
async def open_native_terminal(request: OpenNativeTerminalRequest):
    """
    Open a native system terminal with the specified agent launched.

    Supports Linux (gnome-terminal, konsole, xfce4-terminal, xterm),
    macOS (Terminal.app, iTerm.app), and Windows (cmd, powershell, Windows Terminal).

    The terminal will be opened in the specified working directory (or project root)
    with the appropriate agent CLI command ready.
    """
    import platform
    import subprocess
    import shutil

    # Get working directory
    settings = load_settings()
    cwd = request.working_directory or str(settings.root_path)

    # Determine agent command
    agent_commands = {
        "claude": "claude",
        "codex": "codex",
        "gemini": "gemini",
    }
    agent_cmd = agent_commands.get(request.agent_type, "claude")

    # Check if agent CLI is available
    agent_path = shutil.which(agent_cmd)
    if not agent_path:
        raise ValidationError(
            f"Agent CLI '{agent_cmd}' not found in PATH. Please install it first."
        )

    system = platform.system()
    terminal_found = None

    try:
        if system == "Linux":
            # Try different Linux terminal emulators
            linux_terminals = [
                ("gnome-terminal", ["gnome-terminal", "--working-directory", cwd, "--", agent_cmd]),
                ("konsole", ["konsole", "--workdir", cwd, "-e", agent_cmd]),
                ("xfce4-terminal", ["xfce4-terminal", "--working-directory", cwd, "-e", agent_cmd]),
                ("tilix", ["tilix", "--working-directory", cwd, "-e", agent_cmd]),
                ("terminator", ["terminator", "--working-directory", cwd, "-e", agent_cmd]),
                ("alacritty", ["alacritty", "--working-directory", cwd, "-e", agent_cmd]),
                ("kitty", ["kitty", "--directory", cwd, agent_cmd]),
                ("xterm", ["xterm", "-e", f"cd {cwd} && {agent_cmd}"]),
            ]

            for term_name, term_cmd in linux_terminals:
                if shutil.which(term_name):
                    terminal_found = term_name
                    logger.info(f"Opening {term_name} with {agent_cmd} in {cwd}")
                    subprocess.Popen(
                        term_cmd,
                        start_new_session=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    break

            if not terminal_found:
                raise ServiceUnavailableError(
                    "No supported terminal emulator found on Linux. Install gnome-terminal, konsole, or xterm."
                )

        elif system == "Darwin":
            # macOS - use osascript to open Terminal.app or iTerm
            terminal_found = "Terminal.app"

            # Check for iTerm first (preferred by many developers)
            iterm_script = f'''
                tell application "iTerm"
                    activate
                    tell current window
                        create tab with default profile
                        tell current session
                            write text "cd {cwd} && {agent_cmd}"
                        end tell
                    end tell
                end tell
            '''

            terminal_script = f'''
                tell application "Terminal"
                    activate
                    do script "cd {cwd} && {agent_cmd}"
                end tell
            '''

            # Try iTerm first, fallback to Terminal.app
            try:
                # Check if iTerm exists
                result = subprocess.run(
                    ["osascript", "-e", 'tell application "System Events" to get name of processes'],
                    capture_output=True, text=True
                )
                if "iTerm" in result.stdout:
                    terminal_found = "iTerm.app"
                    subprocess.Popen(
                        ["osascript", "-e", iterm_script],
                        start_new_session=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                else:
                    subprocess.Popen(
                        ["osascript", "-e", terminal_script],
                        start_new_session=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
            except Exception:
                # Fallback to Terminal.app
                subprocess.Popen(
                    ["osascript", "-e", terminal_script],
                    start_new_session=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )

        elif system == "Windows":
            # Windows - try Windows Terminal first, fallback to cmd
            terminal_found = "cmd"

            # Windows Terminal (wt)
            if shutil.which("wt"):
                terminal_found = "Windows Terminal"
                subprocess.Popen(
                    ["wt", "-d", cwd, agent_cmd],
                    start_new_session=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    shell=True,
                )
            else:
                # Fallback to cmd
                subprocess.Popen(
                    f'start cmd /k "cd /d {cwd} && {agent_cmd}"',
                    shell=True,
                    start_new_session=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
        else:
            raise ServiceUnavailableError(f"Unsupported operating system: {system}")

        return OpenNativeTerminalResponse(
            success=True,
            message=f"Opened {terminal_found} with {agent_cmd}",
            terminal=terminal_found,
        )

    except (ValidationError, ServiceUnavailableError, InternalError):
        raise
    except Exception as e:
        logger.error(f"Error opening native terminal: {e}", exc_info=True)
        raise InternalError(f"Failed to open terminal: {str(e)}") from e


# ============================================================================
# Legacy WebSocket Terminal (use Socket.IO /pty namespace instead)
# ============================================================================


@router.websocket("/ws")
async def terminal_websocket(websocket: WebSocket):
    """
    Legacy WebSocket endpoint for remote terminal access.

    NOTE: For new implementations, use Socket.IO with the /pty namespace instead.
    This endpoint is maintained for backwards compatibility.

    Spawns a shell process and provides bidirectional communication using text protocol.
    """
    # Check PTY availability
    if not _PTY_AVAILABLE or PTYShell is None:
        await websocket.accept()
        await websocket.send_text(
            "ERROR: Shell support is not available.\r\n"
            "Please install pywinpty (Windows) or check system dependencies.\r\n"
        )
        await websocket.close()
        return

    try:
        await websocket.accept()
        logger.info("Terminal WebSocket connection accepted")

        # Spawn shell process
        shell = PTYShell(cols=80, rows=24, enable_agent_parsing=False)

        try:
            shell.spawn()
            logger.info(f"Shell spawned successfully: PID={shell.pid}")
        except Exception as e:
            logger.error(f"Failed to spawn shell: {e}", exc_info=True)
            await websocket.send_text(f"Failed to spawn shell: {str(e)}\r\n")
            await websocket.close()
            return

        # Create queue for shell output
        output_queue: asyncio.Queue[str | None] = asyncio.Queue()
        loop = asyncio.get_running_loop()

        async def read_output():
            """Read shell output and send to WebSocket"""

            def send_output(data: str):
                try:
                    if loop.is_running():
                        loop.call_soon_threadsafe(output_queue.put_nowait, data)
                except Exception as e:
                    logger.error(f"Error queueing output: {e}")

            await shell.read(send_output)
            logger.info("Shell process exited")
            try:
                if loop.is_running():
                    loop.call_soon_threadsafe(output_queue.put_nowait, None)
            except Exception:
                pass

        read_task = asyncio.create_task(read_output())
        await websocket.send_text("Connected to shell. Type commands.\r\n")

        try:
            while True:
                recv_task = asyncio.create_task(websocket.receive_text())
                pty_task = asyncio.create_task(output_queue.get())

                done, pending = await asyncio.wait(
                    [recv_task, pty_task],
                    return_when=asyncio.FIRST_COMPLETED,
                )

                for task in pending:
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass

                for task in done:
                    if task is recv_task:
                        try:
                            data = task.result()
                            # Handle resize command
                            if data.startswith("__RESIZE__:"):
                                parts = data.split(":")
                                if len(parts) == 3:
                                    try:
                                        cols = int(parts[1])
                                        rows = int(parts[2])
                                        shell.resize(cols, rows)
                                    except (ValueError, TypeError):
                                        pass
                            else:
                                shell.write(data)
                        except Exception:
                            raise

                    elif task is pty_task:
                        output = task.result()
                        if output is None:
                            await websocket.send_text("\r\nShell exited.\r\n")
                            return
                        await websocket.send_text(output)

        except Exception as e:
            logger.error(f"WebSocket error: {e}")
        finally:
            read_task.cancel()
            try:
                await read_task
            except asyncio.CancelledError:
                pass

            shell.terminate()
            logger.info("Terminal session ended")

    except Exception as e:
        logger.error(f"Error during WebSocket initialization: {e}", exc_info=True)
        try:
            await websocket.close()
        except Exception:
            pass
