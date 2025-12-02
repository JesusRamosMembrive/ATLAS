"""
Codex CLI Runner - Async subprocess for JSON streaming mode

Executes OpenAI Codex CLI with --json for structured JSONL output.
Supports bidirectional communication for interactive permission handling.

Codex CLI event format (JSONL):
- {"type": "thread.started", "thread_id": "..."}
- {"type": "turn.started"}
- {"type": "item.completed", "item": {"type": "reasoning", "text": "..."}}
- {"type": "item.started", "item": {"type": "command_execution", "command": "...", "status": "in_progress"}}
- {"type": "item.completed", "item": {"type": "command_execution", "command": "...", "aggregated_output": "...", "exit_code": 0}}
- {"type": "item.completed", "item": {"type": "agent_message", "text": "..."}}
- {"type": "turn.completed", "usage": {"input_tokens": N, "output_tokens": N}}
"""

import asyncio
import json
import logging
import os
import shutil
from pathlib import Path
from typing import Optional, Callable, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


def find_codex_cli() -> str:
    """
    Find the Codex CLI executable.

    Checks multiple locations since running with sudo may have different PATH.
    Supports both Unix and Windows platforms.

    Returns:
        Full path to codex CLI, or "codex" if not found (will fail at runtime)
    """
    import sys

    is_windows = sys.platform == "win32"

    # Check if codex is in PATH
    codex_path = shutil.which("codex")
    if codex_path:
        return codex_path

    # Get home directory (works on both platforms)
    home = os.environ.get("HOME") or os.environ.get("USERPROFILE") or os.path.expanduser("~")

    if is_windows:
        # Windows-specific paths
        appdata = os.environ.get("APPDATA", "")
        localappdata = os.environ.get("LOCALAPPDATA", "")
        common_paths = [
            # npm global installations
            Path(appdata) / "npm" / "codex.cmd" if appdata else None,
            Path(appdata) / "npm" / "codex" if appdata else None,
            # Local npm installations
            Path(home) / ".npm-global" / "codex.cmd",
            Path(home) / ".npm-global" / "codex",
            # Scoop installations
            Path(home) / "scoop" / "shims" / "codex.cmd",
            Path(home) / "scoop" / "shims" / "codex.exe",
        ]
        # Filter out None values
        common_paths = [p for p in common_paths if p is not None]
    else:
        # Unix-specific paths
        common_paths = [
            Path(home) / ".npm-global" / "bin" / "codex",
            Path(home) / ".nvm" / "versions" / "node" / "v24.11.1" / "bin" / "codex",
            Path("/usr/local/bin/codex"),
            Path("/usr/bin/codex"),
        ]

        # Also check NVM installations
        nvm_dir = Path(home) / ".nvm" / "versions" / "node"
        if nvm_dir.exists():
            for node_version in nvm_dir.iterdir():
                codex_bin = node_version / "bin" / "codex"
                if codex_bin.exists():
                    common_paths.insert(0, codex_bin)
                    break

    for path in common_paths:
        if path.exists() and os.access(path, os.X_OK if not is_windows else os.R_OK):
            logger.info(f"Found Codex CLI at: {path}")
            return str(path)

    # Fallback - will likely fail but let it try
    logger.warning(
        "Codex CLI not found in common locations, using 'codex' (may fail)"
    )
    return "codex"


# Permission mode mapping from AEGIS modes to Codex CLI flags
# Codex CLI only supports:
#   --sandbox <MODE>: read-only, workspace-write, danger-full-access
#   --full-auto: auto-approve and use workspace-write sandbox
#   --dangerously-bypass-approvals-and-sandbox: no sandbox, no approval
CODEX_MODE_MAPPING = {
    "default": {
        "sandbox": "read-only",
    },
    "acceptEdits": {
        "sandbox": "workspace-write",
    },
    "bypassPermissions": {
        "full_auto": True,
    },
    "dontAsk": {
        "dangerously_bypass": True,
    },
    "plan": {
        "sandbox": "read-only",
    },
    "toolApproval": {
        "sandbox": "read-only",
    },
}

# Tool name mapping from Codex to Claude equivalents for UI consistency
CODEX_TOOL_MAPPING = {
    "command_execution": "Bash",
    "shell": "Bash",
    "run_shell_command": "Bash",
    "read_file": "Read",
    "write_file": "Write",
    "edit_file": "Edit",
    "file_search": "Glob",
    "code_search": "Grep",
}


@dataclass
class CodexRunnerConfig:
    """Configuration for Codex CLI runner"""

    cwd: str
    model: str = "gpt-5.1-codex-max"  # Default Codex model
    permission_mode: str = "default"
    timeout: Optional[float] = None  # None = no timeout
    auto_approve_safe_tools: bool = False
    add_dirs: list[str] = field(default_factory=list)
    skip_git_check: bool = False
    enable_search: bool = False  # Enable web search tool


class CodexAgentRunner:
    """
    Executes Codex CLI in JSON streaming mode with event mapping.

    Runs `codex exec "prompt" --json` and streams parsed JSON events,
    mapping them to the normalized AEGIS event format for frontend compatibility.
    """

    def __init__(self, config: CodexRunnerConfig):
        self.config = config
        self.process: Optional[asyncio.subprocess.Process] = None
        self.running = False
        self._cancelled = False
        self._thread_id: Optional[str] = None
        self._pending_approval_tasks: list[asyncio.Task] = []
        self._session_broken = False

        # Tool approval manager for toolApproval mode
        self._tool_approval_manager = None
        if config.permission_mode == "toolApproval":
            from .tool_approval import ToolApprovalManager

            self._tool_approval_manager = ToolApprovalManager(
                cwd=config.cwd,
                auto_approve_safe=config.auto_approve_safe_tools,
            )

    def _build_command(self, prompt: str) -> list[str]:
        """
        Build Codex CLI command with appropriate flags.

        Args:
            prompt: The user prompt to execute

        Returns:
            List of command arguments
        """
        codex_bin = find_codex_cli()
        cmd = [codex_bin, "exec", prompt, "--json"]

        # Get mode configuration
        mode_config = CODEX_MODE_MAPPING.get(
            self.config.permission_mode,
            CODEX_MODE_MAPPING["default"]
        )

        # Apply mode-specific flags
        # Note: Codex CLI does NOT have --ask-for-approval flag
        # Approval is implicit based on sandbox mode
        if mode_config.get("full_auto"):
            cmd.append("--full-auto")
        elif mode_config.get("dangerously_bypass"):
            cmd.append("--dangerously-bypass-approvals-and-sandbox")
        elif "sandbox" in mode_config:
            cmd.extend(["--sandbox", mode_config["sandbox"]])

        # Model override (only add flag if not using default)
        if self.config.model and self.config.model != "gpt-5.1-codex-max":
            cmd.extend(["--model", self.config.model])

        # Working directory
        if self.config.cwd:
            cmd.extend(["--cd", self.config.cwd])

        # Skip git check if needed
        if self.config.skip_git_check:
            cmd.append("--skip-git-repo-check")

        # Additional writable directories
        for dir_path in self.config.add_dirs:
            cmd.extend(["--add-dir", dir_path])

        # Enable web search
        if self.config.enable_search:
            cmd.append("--search")

        return cmd

    async def run_prompt(
        self,
        prompt: str,
        on_event: Callable[[dict], Any],
        on_error: Optional[Callable[[str], Any]] = None,
        on_done: Optional[Callable[[], Any]] = None,
        on_permission_request: Optional[Callable[[dict], Any]] = None,
        on_tool_approval_request: Optional[Callable[[Any], Any]] = None,
    ) -> int:
        """
        Execute a prompt and stream JSON events.

        Args:
            prompt: The prompt to send to Codex
            on_event: Callback for each parsed JSON event (normalized format)
            on_error: Optional callback for stderr output
            on_done: Optional callback when process completes
            on_permission_request: Optional callback for permission requests
            on_tool_approval_request: Optional callback for tool approval (toolApproval mode)

        Returns:
            Exit code from the process
        """
        cmd = self._build_command(prompt)
        logger.info(f"Starting Codex CLI: {' '.join(cmd[:4])}...")

        self.running = True
        self._cancelled = False

        try:
            # Create subprocess
            self.process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.config.cwd,
            )

            logger.info(f"Codex CLI process started: PID={self.process.pid}")

            # Send initial system event
            init_event = {
                "type": "system",
                "subtype": "init",
                "content": {
                    "session_id": "codex-session",
                    "model": self.config.model,
                    "tools": ["Bash", "Read", "Write", "Edit"],
                    "agent_type": "codex",
                },
            }
            result = on_event(init_event)
            if asyncio.iscoroutine(result):
                await result

            # Read stdout line by line (JSONL format)
            async def read_stdout():
                if self.process.stdout is None:
                    logger.warning("[read_stdout] No stdout available")
                    return

                logger.info("[read_stdout] Starting stdout reader loop")
                line_count = 0

                while self.running and not self._cancelled:
                    try:
                        line = await self.process.stdout.readline()
                        if not line:
                            logger.info(f"[read_stdout] EOF reached after {line_count} lines")
                            break

                        line_count += 1
                        line_str = line.decode("utf-8").strip()
                        if not line_str:
                            continue

                        logger.debug(f"[read_stdout] Line {line_count}: {line_str[:100]}...")

                        # Parse JSON
                        try:
                            event = json.loads(line_str)

                            # Map to normalized format
                            mapped_events = self._map_event(event)

                            for mapped_event in mapped_events:
                                if mapped_event:
                                    # Check for tool_use in toolApproval mode
                                    if (
                                        self._is_tool_use_event(mapped_event)
                                        and self._tool_approval_manager
                                        and on_tool_approval_request
                                    ):
                                        logger.info("[toolApproval] Intercepting tool_use for approval")
                                        approval_task = asyncio.create_task(
                                            self._handle_tool_approval(
                                                mapped_event,
                                                on_event,
                                                on_tool_approval_request,
                                            )
                                        )
                                        self._pending_approval_tasks.append(approval_task)
                                    else:
                                        result = on_event(mapped_event)
                                        if asyncio.iscoroutine(result):
                                            await result

                        except json.JSONDecodeError as e:
                            logger.warning(f"Invalid JSON line: {line_str[:100]}... Error: {e}")
                            if on_error:
                                result = on_error(f"[PARSE ERROR] {line_str}")
                                if asyncio.iscoroutine(result):
                                    await result

                    except asyncio.CancelledError:
                        logger.info("[read_stdout] Reader cancelled")
                        break
                    except Exception as e:
                        logger.error(f"[read_stdout] Error reading stdout: {e}")
                        break

                logger.info(f"[read_stdout] Reader loop exited after {line_count} lines")

            # Read stderr for errors
            async def read_stderr():
                if self.process.stderr is None:
                    return

                # Informational messages from CLI that should not be shown as errors
                info_patterns = [
                    "loaded cached credentials",
                    "authenticating",
                    "loading",
                    "initializing",
                    "connecting",
                    "codex cli",
                ]

                while self.running and not self._cancelled:
                    try:
                        line = await self.process.stderr.readline()
                        if not line:
                            break

                        line_str = line.decode("utf-8").strip()
                        if line_str and on_error:
                            # Skip informational messages that aren't real errors
                            line_lower = line_str.lower()
                            if any(pattern in line_lower for pattern in info_patterns):
                                logger.debug(f"[Codex stderr info] {line_str}")
                                continue

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
            logger.info("[run_prompt] Reader tasks created")

            # Wait for process to complete
            logger.info("[run_prompt] Waiting for process to complete...")
            try:
                if self.config.timeout:
                    await asyncio.wait_for(
                        self.process.wait(), timeout=self.config.timeout
                    )
                else:
                    await self.process.wait()
                logger.info(f"[run_prompt] Process completed with returncode: {self.process.returncode}")
            except asyncio.TimeoutError:
                logger.warning("[run_prompt] Codex CLI process timed out")
                await self.cancel()

            # Wait for readers to finish
            logger.info("[run_prompt] Waiting for reader tasks to complete...")
            await asyncio.gather(stdout_task, stderr_task, return_exceptions=True)

            # Wait for any pending approval tasks
            if self._pending_approval_tasks:
                logger.info(f"[run_prompt] Waiting for {len(self._pending_approval_tasks)} pending approval tasks...")
                await asyncio.gather(*self._pending_approval_tasks, return_exceptions=True)
                self._pending_approval_tasks.clear()

            exit_code = self.process.returncode or 0
            logger.info(f"[run_prompt] Codex CLI process exited with code {exit_code}")

            # Call done callback
            if on_done:
                result = on_done()
                if asyncio.iscoroutine(result):
                    await result

            return exit_code

        except Exception as e:
            logger.error(f"Error running Codex CLI: {e}", exc_info=True)
            if on_error:
                result = on_error(f"Error: {str(e)}")
                if asyncio.iscoroutine(result):
                    await result
            return -1
        finally:
            self.running = False
            self.process = None

    def _map_event(self, event: dict) -> list[dict]:
        """
        Map Codex event to normalized AEGIS event format.

        Codex events are different from Claude events, so we need to translate them.

        Args:
            event: Raw Codex event from JSONL output

        Returns:
            List of normalized events (can be empty or multiple)
        """
        event_type = event.get("type", "")
        mapped_events = []

        # Thread started - session initialization
        if event_type == "thread.started":
            self._thread_id = event.get("thread_id")
            # Already sent init event, skip
            return []

        # Turn started
        elif event_type == "turn.started":
            # Could emit a "thinking started" event if needed
            return []

        # Item events (main content)
        elif event_type in ("item.started", "item.completed"):
            item = event.get("item", {})
            item_type = item.get("type", "")
            item_id = item.get("id", "")

            # Reasoning (thinking)
            if item_type == "reasoning":
                text = item.get("text", "")
                if text and event_type == "item.completed":
                    mapped_events.append({
                        "type": "assistant",
                        "subtype": "text",
                        "content": f"*{text}*",  # Italicize reasoning
                    })

            # Agent message (text response)
            elif item_type == "agent_message":
                text = item.get("text", "")
                if text:
                    mapped_events.append({
                        "type": "assistant",
                        "subtype": "text",
                        "content": text,
                    })

            # Command execution (tool use)
            elif item_type == "command_execution":
                command = item.get("command", "")
                status = item.get("status", "")

                if event_type == "item.started":
                    # Tool use started
                    mapped_events.append({
                        "type": "assistant",
                        "subtype": "tool_use",
                        "content": {
                            "name": "Bash",
                            "input": {"command": command},
                            "id": item_id,
                        },
                    })
                elif event_type == "item.completed":
                    # Tool result
                    output = item.get("aggregated_output", "")
                    exit_code = item.get("exit_code", 0)
                    is_error = exit_code != 0

                    mapped_events.append({
                        "type": "user",
                        "subtype": "tool_result",
                        "content": {
                            "tool_use_id": item_id,
                            "content": output or "(no output)",
                            "is_error": is_error,
                        },
                    })

            # File operations
            elif item_type in ("file_read", "read_file"):
                file_path = item.get("file_path", "") or item.get("path", "")
                if event_type == "item.started":
                    mapped_events.append({
                        "type": "assistant",
                        "subtype": "tool_use",
                        "content": {
                            "name": "Read",
                            "input": {"file_path": file_path},
                            "id": item_id,
                        },
                    })
                elif event_type == "item.completed":
                    content = item.get("content", "") or item.get("text", "")
                    mapped_events.append({
                        "type": "user",
                        "subtype": "tool_result",
                        "content": {
                            "tool_use_id": item_id,
                            "content": content[:5000] if content else "(empty file)",
                            "is_error": False,
                        },
                    })

            elif item_type in ("file_write", "write_file"):
                file_path = item.get("file_path", "") or item.get("path", "")
                if event_type == "item.started":
                    mapped_events.append({
                        "type": "assistant",
                        "subtype": "tool_use",
                        "content": {
                            "name": "Write",
                            "input": {
                                "file_path": file_path,
                                "content": item.get("content", "")[:500] + "...",
                            },
                            "id": item_id,
                        },
                    })
                elif event_type == "item.completed":
                    mapped_events.append({
                        "type": "user",
                        "subtype": "tool_result",
                        "content": {
                            "tool_use_id": item_id,
                            "content": f"Successfully wrote to {file_path}",
                            "is_error": False,
                        },
                    })

        # Turn completed - usage stats
        elif event_type == "turn.completed":
            usage = event.get("usage", {})
            if usage:
                mapped_events.append({
                    "type": "system",
                    "subtype": "usage",
                    "content": {
                        "input_tokens": usage.get("input_tokens", 0),
                        "output_tokens": usage.get("output_tokens", 0),
                        "cached_input_tokens": usage.get("cached_input_tokens", 0),
                    },
                })

        return mapped_events

    def _map_tool_name(self, codex_name: str) -> str:
        """Map Codex tool names to Claude equivalents for UI consistency."""
        return CODEX_TOOL_MAPPING.get(codex_name, codex_name)

    def _is_tool_use_event(self, event: dict) -> bool:
        """Check if event is a tool_use event."""
        return event.get("type") == "assistant" and event.get("subtype") == "tool_use"

    def _extract_tool_use_from_event(self, event: dict) -> tuple[str, dict, str] | None:
        """
        Extract tool_use info from event.

        Returns (tool_name, tool_input, tool_id) or None if not found.
        """
        if event.get("subtype") == "tool_use":
            content = event.get("content", {})
            if isinstance(content, dict):
                return (
                    content.get("name", "unknown"),
                    content.get("input", {}),
                    content.get("id", ""),
                )
        return None

    async def _handle_tool_approval(
        self,
        event: dict,
        on_event: Callable[[dict], Any],
        on_tool_approval_request: Callable[[Any], Any],
    ):
        """
        Handle tool approval flow for toolApproval mode.

        In read-only sandbox mode, Codex doesn't execute commands.
        We intercept, show preview to user, and execute manually if approved.
        """
        if self._tool_approval_manager is None:
            result = on_event(event)
            if asyncio.iscoroutine(result):
                await result
            return

        tool_info = self._extract_tool_use_from_event(event)
        if tool_info is None:
            logger.warning(f"[toolApproval] Could not extract tool info from event: {event}")
            result = on_event(event)
            if asyncio.iscoroutine(result):
                await result
            return

        tool_name, tool_input, tool_id = tool_info
        logger.info(f"[toolApproval] Intercepted {tool_name} (id={tool_id})")

        # Forward tool_use event to frontend
        result = on_event(event)
        if asyncio.iscoroutine(result):
            await result

        async def send_approval_request(request):
            """Callback to send approval request to frontend"""
            logger.info(f"[toolApproval] Sending approval request: {request.request_id}")
            try:
                result = on_tool_approval_request(request)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error(f"Error in send_approval_request: {e}", exc_info=True)
                raise

        # Process through approval manager
        logger.info("[toolApproval] Waiting for user approval...")
        approved, feedback = await self._tool_approval_manager.process_tool_use(
            tool_name=tool_name,
            tool_input=tool_input,
            tool_use_id=tool_id,
            on_approval_request=send_approval_request,
        )
        logger.info(f"[toolApproval] User response: approved={approved}, feedback={feedback}")

        if approved:
            # Execute tool manually
            logger.info(f"[toolApproval] Tool {tool_name} approved, executing...")
            tool_result = await self._execute_tool(tool_name, tool_input)

            # Send tool_result event to frontend
            result_event = {
                "type": "user",
                "subtype": "tool_result",
                "local_execution": True,
                "content": {
                    "tool_use_id": tool_id,
                    "content": tool_result.get("content", ""),
                    "is_error": tool_result.get("is_error", False),
                },
            }
            result = on_event(result_event)
            if asyncio.iscoroutine(result):
                await result

            self._session_broken = True
        else:
            # Tool rejected
            logger.info(f"[toolApproval] Tool {tool_name} rejected: {feedback}")
            result_event = {
                "type": "user",
                "subtype": "tool_result",
                "local_execution": True,
                "content": {
                    "tool_use_id": tool_id,
                    "content": f"[REJECTED] {feedback or 'Tool execution rejected by user'}",
                    "is_error": True,
                },
            }
            result = on_event(result_event)
            if asyncio.iscoroutine(result):
                await result

            self._session_broken = True

    async def _execute_tool(self, tool_name: str, tool_input: dict) -> dict:
        """
        Execute a tool manually.

        Returns dict with "content" and "is_error" keys.
        """
        try:
            if tool_name == "Bash":
                return await self._execute_bash(tool_input)
            elif tool_name == "Read":
                return await self._execute_read(tool_input)
            elif tool_name == "Write":
                return await self._execute_write(tool_input)
            elif tool_name == "Edit":
                return await self._execute_edit(tool_input)
            else:
                return {
                    "content": f"Tool {tool_name} is not supported for manual execution",
                    "is_error": True,
                }
        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {e}")
            return {
                "content": f"Error executing {tool_name}: {str(e)}",
                "is_error": True,
            }

    async def _execute_bash(self, tool_input: dict) -> dict:
        """Execute Bash tool"""
        command = tool_input.get("command", "")
        timeout_sec = tool_input.get("timeout", 120000) / 1000

        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.config.cwd,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(),
                    timeout=timeout_sec,
                )
            except asyncio.TimeoutError:
                proc.kill()
                return {
                    "content": f"Command timed out after {timeout_sec}s",
                    "is_error": True,
                }

            output = stdout.decode("utf-8", errors="replace")
            error_output = stderr.decode("utf-8", errors="replace")

            if proc.returncode != 0:
                return {
                    "content": f"Exit code {proc.returncode}\n{output}\n{error_output}".strip(),
                    "is_error": True,
                }

            return {
                "content": output or "(no output)",
                "is_error": False,
            }
        except Exception as e:
            return {
                "content": f"Failed to execute command: {str(e)}",
                "is_error": True,
            }

    async def _execute_read(self, tool_input: dict) -> dict:
        """Execute Read tool"""
        file_path = tool_input.get("file_path", "")
        offset = tool_input.get("offset", 0)
        limit = tool_input.get("limit", 2000)

        path = Path(file_path)
        if not path.is_absolute():
            path = Path(self.config.cwd) / path

        try:
            if not path.exists():
                return {
                    "content": f"File does not exist: {file_path}",
                    "is_error": True,
                }

            content = path.read_text(encoding="utf-8")
            lines = content.splitlines()

            selected_lines = lines[offset : offset + limit]
            result_lines = []
            for i, line in enumerate(selected_lines, start=offset + 1):
                if len(line) > 2000:
                    line = line[:2000] + "..."
                result_lines.append(f"{i:>6}\t{line}")

            return {
                "content": "\n".join(result_lines),
                "is_error": False,
            }
        except Exception as e:
            return {
                "content": f"Failed to read {file_path}: {str(e)}",
                "is_error": True,
            }

    async def _execute_write(self, tool_input: dict) -> dict:
        """Execute Write tool"""
        file_path = tool_input.get("file_path", "")
        content = tool_input.get("content", "")

        path = Path(file_path)
        if not path.is_absolute():
            path = Path(self.config.cwd) / path

        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            return {
                "content": f"Successfully wrote {len(content)} characters to {file_path}",
                "is_error": False,
            }
        except Exception as e:
            return {
                "content": f"Failed to write to {file_path}: {str(e)}",
                "is_error": True,
            }

    async def _execute_edit(self, tool_input: dict) -> dict:
        """Execute Edit tool"""
        file_path = tool_input.get("file_path", "")
        old_string = tool_input.get("old_string", "")
        new_string = tool_input.get("new_string", "")
        replace_all = tool_input.get("replace_all", False)

        path = Path(file_path)
        if not path.is_absolute():
            path = Path(self.config.cwd) / path

        try:
            if not path.exists():
                return {
                    "content": f"File does not exist: {file_path}",
                    "is_error": True,
                }

            content = path.read_text(encoding="utf-8")

            if old_string not in content:
                return {
                    "content": f"String not found in {file_path}",
                    "is_error": True,
                }

            if replace_all:
                new_content = content.replace(old_string, new_string)
                count = content.count(old_string)
            else:
                new_content = content.replace(old_string, new_string, 1)
                count = 1

            path.write_text(new_content, encoding="utf-8")
            return {
                "content": f"Successfully replaced {count} occurrence(s) in {file_path}",
                "is_error": False,
            }
        except Exception as e:
            return {
                "content": f"Failed to edit {file_path}: {str(e)}",
                "is_error": True,
            }

    async def cancel(self) -> None:
        """Cancel the running process"""
        self._cancelled = True

        # Cancel any pending approval tasks
        for task in self._pending_approval_tasks:
            if not task.done():
                task.cancel()
        self._pending_approval_tasks.clear()

        if self.process is None:
            return

        logger.info("Cancelling Codex CLI process")

        try:
            if self.process.stdin:
                self.process.stdin.close()

            self.process.terminate()

            try:
                await asyncio.wait_for(self.process.wait(), timeout=2.0)
            except asyncio.TimeoutError:
                logger.warning("Process didn't terminate, force killing")
                self.process.kill()
                await self.process.wait()

        except ProcessLookupError:
            pass
        except Exception as e:
            logger.error(f"Error cancelling process: {e}")
        finally:
            self.running = False

    def respond_to_tool_approval(
        self, request_id: str, approved: bool, feedback: str | None = None
    ) -> bool:
        """
        Respond to a pending tool approval request.

        Args:
            request_id: ID of the approval request
            approved: Whether to approve the tool use
            feedback: Optional feedback (for rejection)

        Returns:
            True if response was processed, False if request not found
        """
        if self._tool_approval_manager is None:
            logger.warning("No tool approval manager")
            return False

        return self._tool_approval_manager.respond_to_approval(
            request_id, approved, feedback
        )

    @property
    def is_running(self) -> bool:
        """Check if process is currently running"""
        return self.running and self.process is not None

    @property
    def session_broken(self) -> bool:
        """
        Check if the session is broken and cannot be continued.

        This happens when we execute tools locally in toolApproval mode.
        """
        return self._session_broken

    @property
    def thread_id(self) -> Optional[str]:
        """Get the current Codex thread ID"""
        return self._thread_id
