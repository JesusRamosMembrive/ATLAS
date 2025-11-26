"""
Claude Code Runner - Async subprocess for JSON streaming mode

Executes Claude Code with --output-format stream-json for structured output
"""

import asyncio
import json
import logging
import os
import shutil
from pathlib import Path
from typing import Optional, Callable, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


def find_claude_cli() -> str:
    """
    Find the Claude CLI executable.

    Checks multiple locations since running with sudo may have different PATH.

    Returns:
        Full path to claude CLI, or "claude" if not found (will fail at runtime)
    """
    # Check if claude is in PATH
    claude_path = shutil.which("claude")
    if claude_path:
        return claude_path

    # Common installation locations
    home = os.environ.get("HOME") or os.path.expanduser("~")
    common_paths = [
        Path(home) / ".local" / "bin" / "claude",
        Path(home) / ".npm-global" / "bin" / "claude",
        Path("/usr/local/bin/claude"),
        Path("/usr/bin/claude"),
    ]

    # Also check SUDO_USER's home if running as sudo
    sudo_user = os.environ.get("SUDO_USER")
    if sudo_user:
        sudo_home = Path("/home") / sudo_user
        common_paths.insert(0, sudo_home / ".local" / "bin" / "claude")

    for path in common_paths:
        if path.exists() and os.access(path, os.X_OK):
            logger.info(f"Found Claude CLI at: {path}")
            return str(path)

    # Fallback - will likely fail but let it try
    logger.warning("Claude CLI not found in common locations, using 'claude' (may fail)")
    return "claude"


@dataclass
class ClaudeRunnerConfig:
    """Configuration for Claude Code runner"""
    cwd: str
    continue_session: bool = True
    verbose: bool = True
    timeout: Optional[float] = None  # None = no timeout


class ClaudeAgentRunner:
    """
    Executes Claude Code in JSON streaming mode

    Runs `claude -p --output-format stream-json --verbose` and streams
    parsed JSON events line by line.
    """

    def __init__(self, config: ClaudeRunnerConfig):
        self.config = config
        self.process: Optional[asyncio.subprocess.Process] = None
        self.running = False
        self._cancelled = False

    async def run_prompt(
        self,
        prompt: str,
        on_event: Callable[[dict], Any],
        on_error: Optional[Callable[[str], Any]] = None,
        on_done: Optional[Callable[[], Any]] = None
    ) -> int:
        """
        Execute a prompt and stream JSON events

        Args:
            prompt: The prompt to send to Claude Code
            on_event: Callback for each parsed JSON event
            on_error: Optional callback for stderr output
            on_done: Optional callback when process completes

        Returns:
            Exit code from the process
        """
        # Build command - find claude CLI (handles sudo PATH issues)
        claude_bin = find_claude_cli()
        cmd = [claude_bin, "-p", "--output-format", "stream-json"]

        if self.config.verbose:
            cmd.append("--verbose")

        if self.config.continue_session:
            cmd.append("--continue")

        # Add the prompt as final argument
        cmd.append(prompt)

        logger.info(f"Starting Claude Code: {' '.join(cmd[:4])}... [prompt truncated]")

        self.running = True
        self._cancelled = False

        try:
            # Create subprocess
            self.process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.config.cwd
            )

            logger.info(f"Claude Code process started: PID={self.process.pid}")

            # Read stdout line by line
            async def read_stdout():
                if self.process.stdout is None:
                    return

                while self.running and not self._cancelled:
                    try:
                        line = await self.process.stdout.readline()
                        if not line:
                            break

                        line_str = line.decode('utf-8').strip()
                        if not line_str:
                            continue

                        # Parse JSON
                        try:
                            event = json.loads(line_str)

                            # Call event callback
                            result = on_event(event)
                            if asyncio.iscoroutine(result):
                                await result

                        except json.JSONDecodeError as e:
                            logger.warning(f"Invalid JSON line: {line_str[:100]}... Error: {e}")
                            # Still emit as raw text for debugging
                            if on_error:
                                result = on_error(f"[PARSE ERROR] {line_str}")
                                if asyncio.iscoroutine(result):
                                    await result

                    except asyncio.CancelledError:
                        logger.info("Stdout reader cancelled")
                        break
                    except Exception as e:
                        logger.error(f"Error reading stdout: {e}")
                        break

            # Read stderr for errors
            async def read_stderr():
                if self.process.stderr is None:
                    return

                while self.running and not self._cancelled:
                    try:
                        line = await self.process.stderr.readline()
                        if not line:
                            break

                        line_str = line.decode('utf-8').strip()
                        if line_str and on_error:
                            result = on_error(line_str)
                            if asyncio.iscoroutine(result):
                                await result

                    except asyncio.CancelledError:
                        break
                    except Exception as e:
                        logger.error(f"Error reading stderr: {e}")
                        break

            # Run both readers concurrently
            stdout_task = asyncio.create_task(read_stdout())
            stderr_task = asyncio.create_task(read_stderr())

            # Wait for process to complete
            try:
                if self.config.timeout:
                    await asyncio.wait_for(
                        self.process.wait(),
                        timeout=self.config.timeout
                    )
                else:
                    await self.process.wait()
            except asyncio.TimeoutError:
                logger.warning("Claude Code process timed out")
                await self.cancel()

            # Wait for readers to finish
            await asyncio.gather(stdout_task, stderr_task, return_exceptions=True)

            exit_code = self.process.returncode or 0
            logger.info(f"Claude Code process exited with code {exit_code}")

            # Call done callback
            if on_done:
                result = on_done()
                if asyncio.iscoroutine(result):
                    await result

            return exit_code

        except Exception as e:
            logger.error(f"Error running Claude Code: {e}", exc_info=True)
            if on_error:
                result = on_error(f"Error: {str(e)}")
                if asyncio.iscoroutine(result):
                    await result
            return -1
        finally:
            self.running = False
            self.process = None

    async def cancel(self) -> None:
        """Cancel the running process"""
        self._cancelled = True

        if self.process is None:
            return

        logger.info("Cancelling Claude Code process")

        try:
            # Try graceful termination first
            self.process.terminate()

            try:
                await asyncio.wait_for(self.process.wait(), timeout=2.0)
            except asyncio.TimeoutError:
                # Force kill if still running
                logger.warning("Process didn't terminate, force killing")
                self.process.kill()
                await self.process.wait()

        except ProcessLookupError:
            # Process already exited
            pass
        except Exception as e:
            logger.error(f"Error cancelling process: {e}")
        finally:
            self.running = False

    @property
    def is_running(self) -> bool:
        """Check if process is currently running"""
        return self.running and self.process is not None
