"""
MCP Proxy Runner - Claude CLI with Tool Approval via MCP Proxy.

This runner uses Claude CLI with the following configuration:
1. Disables native Write, Edit, Bash tools (--disallowed-tools)
2. Adds our MCP tool proxy server (--mcp-config)
3. Uses bypass permissions for MCP tools
4. The MCP proxy server requests approval via socket before executing

This allows full control over dangerous operations while using the user's
existing Claude CLI subscription (no separate API key needed).

Architecture:
    User Prompt
         │
         ▼
    Claude CLI (--disallowed-tools "Write,Edit,Bash")
         │
         ├── Safe tools: Read, Glob, Grep (execute directly)
         │
         └── Proxy tools: atlas_write, atlas_edit, atlas_bash
                  │
                  ▼
         MCP Tool Proxy Server
                  │
                  ├── Generate preview/diff
                  │
                  └── Request approval via socket
                           │
                           ▼
                  ATLAS Backend (socket server)
                           │
                           └── Send to frontend via WebSocket
                                    │
                                    ▼
                           User approves/rejects
                                    │
                                    ▼
                           Execute or deny tool
"""

import asyncio
import json
import logging
import os
import tempfile
from dataclasses import dataclass
from typing import Any, Callable, Optional

from .claude_runner import find_claude_cli
from ..mcp.constants import DEFAULT_SOCKET_PATH, CANCEL_TIMEOUT

logger = logging.getLogger(__name__)


@dataclass
class MCPProxyRunnerConfig:
    """Configuration for MCP Proxy Runner"""

    cwd: str
    model: str = "claude-sonnet-4-20250514"  # Default Claude model
    continue_session: bool = True
    verbose: bool = True
    timeout: Optional[float] = None
    socket_path: str = DEFAULT_SOCKET_PATH

    # Additional tools to allow/disallow
    extra_allowed_tools: list[str] | None = None
    extra_disallowed_tools: list[str] | None = None


class MCPProxyRunner:
    """
    Runs Claude CLI with MCP tool proxy for approval-based execution.

    Uses the user's Claude CLI subscription while providing full control
    over Write, Edit, and Bash operations.
    """

    # Tools that require approval (disabled in CLI, provided by MCP proxy)
    APPROVAL_REQUIRED_TOOLS = ["Write", "Edit", "Bash"]

    def __init__(self, config: MCPProxyRunnerConfig):
        self.config = config
        self.process: Optional[asyncio.subprocess.Process] = None
        self.running = False
        self._cancelled = False
        self._mcp_config_file: Optional[str] = None

    # -------------------------------------------------------------------------
    # Command Building
    # -------------------------------------------------------------------------

    def _build_command(self, mcp_config_path: str) -> list[str]:
        """Build the Claude CLI command with all necessary flags."""
        claude_bin = find_claude_cli()
        cmd = [
            claude_bin,
            "-p",
            "--output-format",
            "stream-json",
            "--input-format",
            "stream-json",
            "--verbose",
        ]

        if self.config.continue_session:
            cmd.append("--continue")

        # Add model flag if not using default
        if self.config.model and self.config.model != "claude-sonnet-4-20250514":
            cmd.extend(["--model", self.config.model])

        # Disable native dangerous tools
        disallowed = self.APPROVAL_REQUIRED_TOOLS.copy()
        if self.config.extra_disallowed_tools:
            disallowed.extend(self.config.extra_disallowed_tools)
        cmd.extend(["--disallowed-tools", ",".join(disallowed)])

        # Add MCP tool proxy and bypass permissions
        cmd.extend(["--mcp-config", mcp_config_path])
        cmd.append("--dangerously-skip-permissions")

        if self.config.extra_allowed_tools:
            cmd.extend(["--allowed-tools", ",".join(self.config.extra_allowed_tools)])

        return cmd

    # -------------------------------------------------------------------------
    # Process I/O
    # -------------------------------------------------------------------------

    async def _start_process(self, cmd: list[str]) -> asyncio.subprocess.Process:
        """Start the Claude subprocess."""
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self.config.cwd,
        )
        logger.info(f"Claude process started: PID={process.pid}")
        return process

    async def _send_initial_prompt(self, prompt: str) -> None:
        """Send the initial prompt to Claude."""
        if self.process is None or self.process.stdin is None:
            raise RuntimeError("Process not started")

        message = (
            json.dumps(
                {
                    "type": "user",
                    "message": {"role": "user", "content": prompt},
                    "session_id": "default",
                    "parent_tool_use_id": None,
                }
            )
            + "\n"
        )

        self.process.stdin.write(message.encode("utf-8"))
        await self.process.stdin.drain()
        logger.info("Initial prompt sent")

    def _create_stdout_reader(
        self, on_event: Callable[[dict], Any], on_error: Optional[Callable[[str], Any]]
    ) -> Callable[[], Any]:
        """Create coroutine for reading stdout."""

        async def read_stdout():
            if self.process is None or self.process.stdout is None:
                return

            while self.running and not self._cancelled:
                try:
                    line = await self.process.stdout.readline()
                    if not line:
                        break

                    line_str = line.decode("utf-8").strip()
                    if not line_str:
                        continue

                    try:
                        event = json.loads(line_str)
                        result = on_event(event)
                        if asyncio.iscoroutine(result):
                            await result
                    except json.JSONDecodeError:
                        logger.warning(f"Invalid JSON: {line_str[:100]}...")
                        if on_error:
                            result = on_error(f"[PARSE] {line_str}")
                            if asyncio.iscoroutine(result):
                                await result

                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Error reading stdout: {e}")
                    break

        return read_stdout

    def _create_stderr_reader(
        self, on_error: Optional[Callable[[str], Any]]
    ) -> Callable[[], Any]:
        """Create coroutine for reading stderr."""

        async def read_stderr():
            if self.process is None or self.process.stderr is None:
                return

            while self.running and not self._cancelled:
                try:
                    line = await self.process.stderr.readline()
                    if not line:
                        break

                    line_str = line.decode("utf-8").strip()
                    if line_str and on_error:
                        result = on_error(line_str)
                        if asyncio.iscoroutine(result):
                            await result

                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"Error reading stderr: {e}")
                    break

        return read_stderr

    # -------------------------------------------------------------------------
    # MCP Configuration
    # -------------------------------------------------------------------------

    def _create_mcp_config(self) -> str:
        """Create temporary MCP config file for the tool proxy server"""
        import sys

        # Get the path to our tool proxy server module
        proxy_module = "code_map.mcp.tool_proxy_server"

        # Use the same Python interpreter that's running this code
        # This ensures we use the venv with the MCP SDK installed
        python_path = sys.executable

        config = {
            "mcpServers": {
                "atlas-tools": {
                    "command": python_path,
                    "args": [
                        "-m",
                        proxy_module,
                        "--socket",
                        self.config.socket_path,
                        "--cwd",
                        self.config.cwd,
                    ],
                    "env": {
                        "ATLAS_TOOL_SOCKET": self.config.socket_path,
                        "ATLAS_CWD": self.config.cwd,
                    },
                }
            }
        }

        # Create temp file
        fd, path = tempfile.mkstemp(suffix=".json", prefix="atlas_mcp_")
        with os.fdopen(fd, "w") as f:
            json.dump(config, f)

        self._mcp_config_file = path
        logger.info(f"Created MCP config at {path}")
        return path

    def _cleanup_mcp_config(self):
        """Remove temporary MCP config file"""
        if self._mcp_config_file and os.path.exists(self._mcp_config_file):
            try:
                os.unlink(self._mcp_config_file)
                logger.info(f"Removed MCP config {self._mcp_config_file}")
            except Exception as e:
                logger.warning(f"Failed to remove MCP config: {e}")
            self._mcp_config_file = None

    async def run_prompt(
        self,
        prompt: str,
        on_event: Callable[[dict], Any],
        on_error: Optional[Callable[[str], Any]] = None,
        on_done: Optional[Callable[[], Any]] = None,
    ) -> int:
        """
        Execute a prompt with MCP proxy tool approval.

        Args:
            prompt: The prompt to send to Claude
            on_event: Callback for each JSON event from Claude
            on_error: Callback for stderr output
            on_done: Callback when process completes

        Returns:
            Exit code from the process
        """
        mcp_config_path = self._create_mcp_config()

        try:
            # Build command and start process
            cmd = self._build_command(mcp_config_path)
            logger.info(f"Starting Claude with MCP proxy: {' '.join(cmd[:8])}...")

            self.running = True
            self._cancelled = False
            self.process = await self._start_process(cmd)

            # Send initial prompt
            await self._send_initial_prompt(prompt)

            # Create and run I/O readers
            stdout_reader = self._create_stdout_reader(on_event, on_error)
            stderr_reader = self._create_stderr_reader(on_error)

            stdout_task = asyncio.create_task(stdout_reader())
            stderr_task = asyncio.create_task(stderr_reader())

            # Wait for process with optional timeout
            await self._wait_for_process()

            # Wait for readers to finish
            await asyncio.gather(stdout_task, stderr_task, return_exceptions=True)

            exit_code = self.process.returncode or 0
            logger.info(f"Process exited with code {exit_code}")

            # Call done callback
            if on_done:
                result = on_done()
                if asyncio.iscoroutine(result):
                    await result

            return exit_code

        except Exception as e:
            logger.error(f"Error running Claude: {e}", exc_info=True)
            if on_error:
                result = on_error(f"Error: {str(e)}")
                if asyncio.iscoroutine(result):
                    await result
            return -1

        finally:
            self.running = False
            self.process = None
            self._cleanup_mcp_config()

    async def _wait_for_process(self) -> None:
        """Wait for process to complete, handling timeout."""
        if self.process is None:
            return

        try:
            if self.config.timeout:
                await asyncio.wait_for(self.process.wait(), timeout=self.config.timeout)
            else:
                await self.process.wait()
        except asyncio.TimeoutError:
            logger.warning("Process timed out")
            await self.cancel()

    async def send_user_input(self, content: str):
        """Send additional user input to the running process"""
        if self.process is None or self.process.stdin is None:
            logger.error("Cannot send input: no process")
            return

        message = (
            json.dumps(
                {
                    "type": "user",
                    "message": {"role": "user", "content": content},
                    "session_id": "default",
                    "parent_tool_use_id": None,
                }
            )
            + "\n"
        )

        try:
            self.process.stdin.write(message.encode("utf-8"))
            await self.process.stdin.drain()
            logger.info("User input sent")
        except Exception as e:
            logger.error(f"Error sending input: {e}")

    async def cancel(self):
        """Cancel the running process"""
        self._cancelled = True

        if self.process is None:
            return

        logger.info("Cancelling process")

        try:
            if self.process.stdin:
                self.process.stdin.close()

            self.process.terminate()

            try:
                await asyncio.wait_for(self.process.wait(), timeout=CANCEL_TIMEOUT)
            except asyncio.TimeoutError:
                logger.warning("Force killing process")
                self.process.kill()
                await self.process.wait()

        except ProcessLookupError:
            pass
        except Exception as e:
            logger.error(f"Error cancelling: {e}")
        finally:
            self.running = False

    @property
    def is_running(self) -> bool:
        """Check if process is running"""
        return self.running and self.process is not None
