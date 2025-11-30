"""
Claude Code Runner - Async subprocess for JSON streaming mode

Executes Claude Code with --output-format stream-json for structured output.
Supports bidirectional communication for interactive permission handling.
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
    logger.warning(
        "Claude CLI not found in common locations, using 'claude' (may fail)"
    )
    return "claude"


# Permission modes supported by Claude CLI
PERMISSION_MODES = (
    "default",
    "acceptEdits",
    "bypassPermissions",
    "dontAsk",
    "plan",
    "toolApproval",
    "mcpApproval",
)


@dataclass
class ClaudeRunnerConfig:
    """Configuration for Claude Code runner"""

    cwd: str
    model: str = "claude-sonnet-4-20250514"  # Default Claude model
    continue_session: bool = True
    verbose: bool = True
    timeout: Optional[float] = None  # None = no timeout
    permission_mode: str = (
        "default"  # default, acceptEdits, bypassPermissions, dontAsk, plan, toolApproval, mcpApproval
    )
    auto_approve_safe_tools: bool = (
        False  # Only used with toolApproval/mcpApproval mode
    )
    mcp_socket_path: str = (
        "/tmp/atlas_mcp_approval.sock"  # Socket for MCP approval communication
    )


class ClaudeAgentRunner:
    """
    Executes Claude Code in JSON streaming mode with bidirectional communication.

    Runs `claude -p --output-format stream-json --input-format stream-json --verbose`
    and streams parsed JSON events line by line. Supports interactive permission handling.
    """

    def __init__(self, config: ClaudeRunnerConfig):
        self.config = config
        self.process: Optional[asyncio.subprocess.Process] = None
        self.running = False
        self._cancelled = False
        self._pending_permission: Optional[dict] = None
        self._permission_response: Optional[asyncio.Future] = None

        # Tool approval tracking
        self._pending_approval_tasks: list[asyncio.Task] = []

        # Session continuity tracking
        # When True, the Claude session cannot be continued because we executed
        # tools locally that Claude doesn't know about (in plan/toolApproval mode)
        self._session_broken = False

        # Tool approval manager for toolApproval mode
        self._tool_approval_manager = None
        if config.permission_mode == "toolApproval":
            from .tool_approval import ToolApprovalManager

            self._tool_approval_manager = ToolApprovalManager(
                cwd=config.cwd,
                auto_approve_safe=config.auto_approve_safe_tools,
            )

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
        Execute a prompt and stream JSON events

        Args:
            prompt: The prompt to send to Claude Code
            on_event: Callback for each parsed JSON event
            on_error: Optional callback for stderr output
            on_done: Optional callback when process completes
            on_permission_request: Optional callback for permission requests (returns Future)
            on_tool_approval_request: Optional callback for tool approval requests (toolApproval mode)

        Returns:
            Exit code from the process
        """
        # Build command - find claude CLI (handles sudo PATH issues)
        print(f"DEBUG: run_prompt called with prompt: {prompt[:50]}...")
        claude_bin = find_claude_cli()
        cmd = [
            claude_bin,
            "-p",
            "--output-format",
            "stream-json",
            "--input-format",
            "stream-json",
            "--include-partial-messages",
            "--verbose",  # Required for stream-json
        ]

        if self.config.continue_session:
            cmd.append("--continue")

        # Add model flag if not using default
        if self.config.model and self.config.model != "claude-sonnet-4-20250514":
            cmd.extend(["--model", self.config.model])

        # Add permission mode
        # NOTE: Claude Code stream-json mode does NOT support interactive permission prompts.
        # Permissions must be pre-approved in .claude/settings.local.json or bypassed entirely.
        # Available modes:
        # - default: Uses settings.local.json rules, blocks if not pre-approved
        # - acceptEdits: Auto-accepts file edits, asks for other actions (blocks in stream-json)
        # - bypassPermissions: Skips ALL permission checks (use with caution)
        # - dontAsk: Executes all actions without asking
        # - plan: Suggests actions without executing
        # - toolApproval: Custom mode - uses bypassPermissions but intercepts tool_use for approval
        if self.config.permission_mode:
            if self.config.permission_mode == "bypassPermissions":
                # Use the dangerously-skip-permissions flag for full bypass
                cmd.append("--dangerously-skip-permissions")
            elif self.config.permission_mode == "toolApproval":
                # toolApproval mode: use plan mode so Claude proposes but doesn't execute
                # We intercept tool_use events, show previews, and execute manually if approved
                #
                # IMPORTANT: When Claude is in "plan" mode, it knows it shouldn't execute tools.
                # Sometimes Claude will describe what it WOULD do instead of emitting tool_use events.
                # This is expected behavior - the user should re-prompt asking Claude to "execute"
                # or "go ahead" to trigger actual tool_use events in plan mode.
                #
                # For better UX, use mcpApproval mode which uses --permission-prompt-tool
                cmd.extend(["--permission-mode", "plan"])
                logger.info(
                    "Tool approval mode: using plan mode, will execute approved tools manually"
                )
            elif self.config.permission_mode == "mcpApproval":
                # mcpApproval mode: DEPRECATED - --permission-prompt-tool does not exist in Claude Code
                #
                # This mode was designed based on a proposed feature that was never implemented.
                # Claude Code v2.0.55 does not have --permission-prompt-tool option.
                #
                # Falling back to plan mode with a warning
                logger.warning(
                    "mcpApproval mode is not available - --permission-prompt-tool doesn't exist in Claude Code"
                )
                logger.warning(
                    "Falling back to plan mode. Claude will propose actions but not execute them."
                )
                cmd.extend(["--permission-mode", "plan"])
            elif (
                self.config.permission_mode != "default"
                and self.config.permission_mode in PERMISSION_MODES
            ):
                cmd.extend(["--permission-mode", self.config.permission_mode])
            # For "default" mode, rely on .claude/settings.local.json rules

        logger.info(f"Starting Claude Code: {' '.join(cmd[:6])}...")

        self.running = True
        self._cancelled = False

        try:
            # Create subprocess with stdin for bidirectional communication
            self.process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.config.cwd,
            )

            logger.info(f"Claude Code process started: PID={self.process.pid}")

            # Send the initial prompt as JSON (stream-json input format)
            # Format: {"type":"user","message":{"role":"user","content":"..."},"session_id":"default","parent_tool_use_id":null}
            initial_message = (
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
            if self.process.stdin is None:
                raise RuntimeError("Process stdin is None")
            self.process.stdin.write(initial_message.encode("utf-8"))
            await self.process.stdin.drain()
            logger.info("Initial prompt sent to Claude")

            # Read stdout line by line
            async def read_stdout():
                if self.process.stdout is None:
                    logger.warning("[read_stdout] No stdout available")
                    return

                logger.info("[read_stdout] Starting stdout reader loop")
                line_count = 0

                while self.running and not self._cancelled:
                    try:
                        logger.debug(
                            f"[read_stdout] Waiting for line {line_count + 1}..."
                        )
                        line = await self.process.stdout.readline()
                        if not line:
                            logger.info(
                                f"[read_stdout] EOF reached after {line_count} lines"
                            )
                            print("DEBUG: [read_stdout] EOF reached")
                            break

                        line_count += 1
                        line_str = line.decode("utf-8").strip()
                        if not line_str:
                            continue

                        logger.debug(
                            f"[read_stdout] Line {line_count}: {line_str[:100]}..."
                        )

                        # Parse JSON
                        try:
                            event = json.loads(line_str)

                            # DEBUG: Log tool_use events in toolApproval mode
                            if self._tool_approval_manager and self._is_tool_use_event(
                                event
                            ):
                                tool_info = self._extract_tool_use_from_event(event)
                                if tool_info:
                                    logger.info(
                                        f"[toolApproval] tool_use detected: {tool_info[0]} (id={tool_info[2]})"
                                    )

                            # Check for permission request
                            if self._is_permission_request(event):
                                logger.info(
                                    f"Permission request received: {event.get('type')}"
                                )
                                await self._handle_permission_request(
                                    event, on_permission_request
                                )
                            # Check for tool_use in toolApproval mode
                            elif (
                                self._is_tool_use_event(event)
                                and self._tool_approval_manager
                                and on_tool_approval_request
                            ):
                                logger.info(
                                    f"[toolApproval] Intercepting tool_use for approval (line {line_count})"
                                )
                                # Spawn approval as separate task to not block the reader
                                approval_task = asyncio.create_task(
                                    self._handle_tool_approval(
                                        event, on_event, on_tool_approval_request
                                    )
                                )
                                self._pending_approval_tasks.append(approval_task)
                                logger.info(
                                    f"[toolApproval] Spawned approval task for line {line_count}"
                                )
                            else:
                                # Call event callback
                                print(
                                    f"DEBUG: Emitting event: {event.get('type')} subtype={event.get('subtype')}"
                                )
                                result = on_event(event)
                                if asyncio.iscoroutine(result):
                                    await result

                        except json.JSONDecodeError as e:
                            logger.warning(
                                f"Invalid JSON line: {line_str[:100]}... Error: {e}"
                            )
                            # Still emit as raw text for debugging
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

                logger.info(
                    f"[read_stdout] Reader loop exited after {line_count} lines"
                )

            # Read stderr for errors
            async def read_stderr():
                if self.process.stderr is None:
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
                    print("DEBUG: [run_prompt] Waiting for process.wait()...")
                    await self.process.wait()
                    print("DEBUG: [run_prompt] process.wait() returned")
                logger.info(
                    f"[run_prompt] Process completed with returncode: {self.process.returncode}"
                )
            except asyncio.TimeoutError:
                logger.warning("[run_prompt] Claude Code process timed out")
                await self.cancel()

            # Wait for readers to finish
            logger.info("[run_prompt] Waiting for reader tasks to complete...")
            print("DEBUG: [run_prompt] Waiting for reader tasks...")
            results = await asyncio.gather(
                stdout_task, stderr_task, return_exceptions=True
            )
            print("DEBUG: [run_prompt] Reader tasks completed")
            logger.info(
                f"[run_prompt] Reader tasks completed: {[type(r).__name__ if isinstance(r, Exception) else 'OK' for r in results]}"
            )

            # Wait for any pending approval tasks
            if self._pending_approval_tasks:
                logger.info(
                    f"[run_prompt] Waiting for {len(self._pending_approval_tasks)} pending approval tasks..."
                )
                print(
                    f"DEBUG: [run_prompt] Waiting for {len(self._pending_approval_tasks)} approval tasks..."
                )
                approval_results = await asyncio.gather(
                    *self._pending_approval_tasks, return_exceptions=True
                )
                print("DEBUG: [run_prompt] Approval tasks completed")
                logger.info(
                    f"[run_prompt] Approval tasks completed: {[type(r).__name__ if isinstance(r, Exception) else 'OK' for r in approval_results]}"
                )
                self._pending_approval_tasks.clear()

            exit_code = self.process.returncode or 0
            logger.info(
                f"[run_prompt] Claude Code process exited with code {exit_code}"
            )

            # Call done callback
            logger.info("[run_prompt] Calling on_done callback...")
            print("DEBUG: [run_prompt] Calling on_done...")
            if on_done:
                result = on_done()
                if asyncio.iscoroutine(result):
                    await result
            logger.info("[run_prompt] on_done callback completed")

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

    def _is_tool_use_event(self, event: dict) -> bool:
        """
        Check if event is a tool_use event.

        Claude CLI emits tool_use in two formats:
        1. Simplified: {"type": "assistant", "subtype": "tool_use", "content": {...}}
        2. Full message: {"type": "assistant", "message": {"content": [{"type": "tool_use", ...}]}}
        """
        if event.get("type") != "assistant":
            return False

        # Check simplified format (subtype == tool_use)
        if event.get("subtype") == "tool_use":
            return True

        # Check full message format
        message = event.get("message", {})
        if isinstance(message, dict):
            content = message.get("content", [])
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "tool_use":
                        return True

        return False

    def _extract_tool_use_from_event(self, event: dict) -> tuple[str, dict, str] | None:
        """
        Extract tool_use info from event.

        Returns (tool_name, tool_input, tool_id) or None if not found.
        """
        # Check simplified format
        if event.get("subtype") == "tool_use":
            content = event.get("content", {})
            if isinstance(content, dict):
                return (
                    content.get("name", "unknown"),
                    content.get("input", {}),
                    content.get("id", ""),
                )

        # Check full message format
        message = event.get("message", {})
        if isinstance(message, dict):
            content = message.get("content", [])
            if isinstance(content, list):
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "tool_use":
                        return (
                            item.get("name", "unknown"),
                            item.get("input", {}),
                            item.get("id", ""),
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

        In plan mode, Claude proposes tool_use but doesn't execute.
        We intercept, show preview to user, and execute manually if approved.
        """
        if self._tool_approval_manager is None:
            # No manager, just forward the event
            result = on_event(event)
            if asyncio.iscoroutine(result):
                await result
            return

        # Extract tool info from event using new helper
        tool_info = self._extract_tool_use_from_event(event)
        if tool_info is None:
            # Couldn't extract tool info, forward as-is
            logger.warning(
                f"[toolApproval] Could not extract tool info from event: {event}"
            )
            result = on_event(event)
            if asyncio.iscoroutine(result):
                await result
            return

        tool_name, tool_input, tool_id = tool_info

        logger.info(f"[toolApproval] Intercepted {tool_name} (id={tool_id})")
        logger.info(
            f"[toolApproval] Process running: {self.process is not None and self.running}"
        )

        # Forward the tool_use event to frontend (so they see what Claude wants to do)
        print(f"DEBUG: Forwarding tool_use event to frontend: {tool_name}")
        result = on_event(event)
        if asyncio.iscoroutine(result):
            await result

        # Create approval request with preview/diff
        async def send_approval_request(request):
            """Callback to send approval request to frontend"""
            print(
                f"DEBUG: [send_approval_request] Entered callback for {request.tool_name} (id={request.request_id})",
                flush=True,
            )
            logger.info(
                f"[toolApproval] Sending approval request to frontend: {request.request_id}"
            )
            try:
                result = on_tool_approval_request(request)
                print(
                    f"DEBUG: [send_approval_request] Called on_tool_approval_request, result type: {type(result)}",
                    flush=True,
                )
                if asyncio.iscoroutine(result):
                    print(
                        "DEBUG: [send_approval_request] Awaiting coroutine...",
                        flush=True,
                    )
                    await result
                    print(
                        "DEBUG: [send_approval_request] Coroutine completed",
                        flush=True,
                    )
                print(
                    f"DEBUG: [send_approval_request] Callback completed successfully for {request.tool_name}",
                    flush=True,
                )
            except Exception as e:
                print(f"DEBUG: [send_approval_request] EXCEPTION: {e}", flush=True)
                logger.error(f"Error in send_approval_request: {e}", exc_info=True)
                raise

        # Process through approval manager (this blocks waiting for user)
        logger.info("[toolApproval] Waiting for user approval...")
        approved, feedback = await self._tool_approval_manager.process_tool_use(
            tool_name=tool_name,
            tool_input=tool_input,
            tool_use_id=tool_id,
            on_approval_request=send_approval_request,
        )
        logger.info(
            f"[toolApproval] User response: approved={approved}, feedback={feedback}"
        )
        print(f"DEBUG: User approval response: approved={approved}")

        if approved:
            # Execute the tool manually
            logger.info(f"[toolApproval] Tool {tool_name} approved, executing...")
            tool_result = await self._execute_tool(tool_name, tool_input)
            logger.info(
                f"[toolApproval] Tool execution result: error={tool_result.get('is_error')}, content_len={len(str(tool_result.get('content', '')))}"
            )

            # Send tool_result event to frontend
            # IMPORTANT: Mark as "local_execution" so frontend knows this was executed locally
            # and should NOT be included in conversation history for API calls.
            # This prevents "unexpected tool_use_id in tool_result" errors when continuing.
            result_event = {
                "type": "user",
                "subtype": "tool_result",
                "local_execution": True,  # Mark as locally executed, not from Claude API
                "content": {
                    "tool_use_id": tool_id,
                    "content": tool_result.get("content", ""),
                    "is_error": tool_result.get("is_error", False),
                },
            }
            result = on_event(result_event)
            if asyncio.iscoroutine(result):
                await result
            print("DEBUG: Sent local tool result event to frontend")

            # In toolApproval mode, we executed the tool locally.
            # We should NOT send the result back to Claude because:
            # 1. Claude might be in "plan" mode and has already exited or doesn't expect results.
            # 2. Even if running, sending a result for a tool use that Claude didn't strictly "ask" for
            #    (in the way it expects during execution) can cause "unexpected tool_use_id" errors.
            #
            # Instead, we just mark the session as broken so the next prompt starts a fresh session.
            logger.info(
                "[toolApproval] Tool executed locally. NOT sending result to Claude to avoid API errors."
            )
            self._session_broken = True

            # If the process is still running (e.g. we're not in plan mode but intercepting),
            # we should probably kill it or at least not try to talk to it anymore.
            if self.process and self.process.returncode is None:
                logger.info(
                    "[toolApproval] Process still running, terminating it to ensure clean state for next session."
                )
                try:
                    self.process.terminate()
                except Exception as e:
                    logger.warning(f"[toolApproval] Failed to terminate process: {e}")
        else:
            # Tool rejected - send error result
            logger.info(f"[toolApproval] Tool {tool_name} rejected: {feedback}")
            error_message = feedback or "Tool execution rejected by user"

            # Send rejection event to frontend
            # Mark as local_execution to exclude from conversation history
            result_event = {
                "type": "user",
                "subtype": "tool_result",
                "local_execution": True,  # Mark as locally executed
                "content": {
                    "tool_use_id": tool_id,
                    "content": f"[REJECTED] {error_message}",
                    "is_error": True,
                },
            }
            result = on_event(result_event)
            if asyncio.iscoroutine(result):
                await result

            # In toolApproval mode, we rejected the tool locally.
            # We should NOT send the rejection back to Claude for the same reasons as above.
            logger.info(
                "[toolApproval] Tool rejected locally. NOT sending rejection to Claude."
            )
            self._session_broken = True

            # Terminate process if still running
            if self.process and self.process.returncode is None:
                logger.info("[toolApproval] Process still running, terminating it.")
                try:
                    self.process.terminate()
                except Exception as e:
                    logger.warning(f"[toolApproval] Failed to terminate process: {e}")

    async def _execute_tool(self, tool_name: str, tool_input: dict) -> dict:
        """
        Execute a tool manually.

        Returns dict with "content" and "is_error" keys.
        """
        try:
            if tool_name == "Write":
                return await self._execute_write(tool_input)
            elif tool_name == "Edit":
                return await self._execute_edit(tool_input)
            elif tool_name == "Read":
                return await self._execute_read(tool_input)
            elif tool_name == "Bash":
                return await self._execute_bash(tool_input)
            elif tool_name == "Glob":
                return await self._execute_glob(tool_input)
            elif tool_name == "Grep":
                return await self._execute_grep(tool_input)
            else:
                # Unsupported tool - return error
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

    async def _execute_write(self, tool_input: dict) -> dict:
        """Execute Write tool"""
        file_path = tool_input.get("file_path", "")
        content = tool_input.get("content", "")

        path = Path(file_path)
        if not path.is_absolute():
            path = Path(self.config.cwd) / path

        try:
            # Ensure parent directory exists
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

            # Apply offset and limit
            selected_lines = lines[offset : offset + limit]

            # Format with line numbers (like cat -n)
            result_lines = []
            for i, line in enumerate(selected_lines, start=offset + 1):
                # Truncate long lines
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

    async def _execute_bash(self, tool_input: dict) -> dict:
        """Execute Bash tool"""
        command = tool_input.get("command", "")
        timeout_ms = tool_input.get("timeout", 120000)
        timeout_sec = timeout_ms / 1000

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

    async def _execute_glob(self, tool_input: dict) -> dict:
        """Execute Glob tool"""
        import glob as glob_module

        pattern = tool_input.get("pattern", "")
        search_path = tool_input.get("path", self.config.cwd)

        try:
            full_pattern = os.path.join(search_path, pattern)
            matches = glob_module.glob(full_pattern, recursive=True)
            matches.sort()

            if not matches:
                return {
                    "content": f"No files matching pattern: {pattern}",
                    "is_error": False,
                }

            return {
                "content": "\n".join(matches[:100]),  # Limit to 100 results
                "is_error": False,
            }
        except Exception as e:
            return {
                "content": f"Glob error: {str(e)}",
                "is_error": True,
            }

    async def _execute_grep(self, tool_input: dict) -> dict:
        """Execute Grep tool"""
        import re

        pattern = tool_input.get("pattern", "")
        search_path = tool_input.get("path", self.config.cwd)
        glob_pattern = tool_input.get("glob", "**/*")

        try:
            regex = re.compile(pattern)
        except re.error as e:
            return {
                "content": f"Invalid regex pattern: {str(e)}",
                "is_error": True,
            }

        try:
            import glob as glob_module

            files = glob_module.glob(
                os.path.join(search_path, glob_pattern), recursive=True
            )

            matches = []
            for file_path in files[:100]:  # Limit files
                if not os.path.isfile(file_path):
                    continue
                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        for line_num, line in enumerate(f, 1):
                            if regex.search(line):
                                matches.append(
                                    f"{file_path}:{line_num}:{line.rstrip()}"
                                )
                                if len(matches) >= 100:  # Limit matches
                                    break
                except Exception:
                    continue

                if len(matches) >= 100:
                    break

            if not matches:
                return {
                    "content": f"No matches for pattern: {pattern}",
                    "is_error": False,
                }

            return {
                "content": "\n".join(matches),
                "is_error": False,
            }
        except Exception as e:
            return {
                "content": f"Grep error: {str(e)}",
                "is_error": True,
            }

    async def _send_tool_result_to_claude(self, tool_id: str, result: dict):
        """Send tool result back to Claude via stdin"""
        logger.info(f"[toolApproval] _send_tool_result_to_claude called for {tool_id}")
        logger.info(
            f"[toolApproval] Process state: process={self.process is not None}, running={self.running}"
        )

        if self.process is None:
            logger.error("[toolApproval] Cannot send tool result: process is None")
            return

        if self.process.stdin is None:
            logger.error("[toolApproval] Cannot send tool result: stdin is None")
            return

        if self.process.returncode is not None:
            logger.error(
                f"[toolApproval] Cannot send tool result: process already exited with code {self.process.returncode}"
            )
            return

        # Format tool result message
        message = (
            json.dumps(
                {
                    "type": "user",
                    "message": {
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": tool_id,
                                "content": result.get("content", ""),
                                "is_error": result.get("is_error", False),
                            }
                        ],
                    },
                    "session_id": "default",
                    "parent_tool_use_id": tool_id,
                }
            )
            + "\n"
        )

        logger.info(f"[toolApproval] Sending message to stdin: {message[:200]}...")

        try:
            self.process.stdin.write(message.encode("utf-8"))
            await self.process.stdin.drain()
            logger.info(f"[toolApproval] Tool result sent to Claude for {tool_id}")
        except Exception as e:
            logger.error(
                f"[toolApproval] Error sending tool result: {e}", exc_info=True
            )

    async def _send_tool_rejection_to_claude(self, tool_id: str, reason: str):
        """Send tool rejection back to Claude"""
        await self._send_tool_result_to_claude(
            tool_id,
            {
                "content": f"[USER REJECTED] {reason}",
                "is_error": True,
            },
        )

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

    def _is_permission_request(self, event: dict) -> bool:
        """
        Check if an event is a permission request.

        Claude sends permission requests in stream-json mode in these ways:
        1. Explicit "permission_request" type event
        2. Tool use events may have "requires_permission" flag
        3. Events may contain permission prompts in the message
        """
        event_type = event.get("type", "")

        # Check for explicit permission request event type
        if event_type == "permission_request":
            return True

        # Check for tool permission flag in tool_use events
        if event_type == "assistant" and event.get("subtype") == "tool_use":
            content = event.get("content", {})
            if isinstance(content, dict):
                # Check for explicit permission flag
                if content.get("requires_permission"):
                    return True

        # Check for permission-related system messages
        # Claude may ask "Allow?" or similar prompts
        if event_type == "system":
            message = str(event.get("message", ""))
            if any(
                phrase in message.lower()
                for phrase in ["allow", "permit", "approve", "permission"]
            ):
                return True

        return False

    async def _handle_permission_request(
        self, event: dict, on_permission_request: Optional[Callable[[dict], Any]]
    ):
        """Handle a permission request from Claude"""
        if on_permission_request is None:
            # No handler, auto-deny
            logger.warning("No permission handler, auto-denying")
            await self._send_permission_response(False)
            return

        # Call the permission request handler
        result = on_permission_request(event)
        if asyncio.iscoroutine(result):
            result = await result

        # Result should be a boolean or a dict with the response
        if isinstance(result, bool):
            await self._send_permission_response(result)
        elif isinstance(result, dict):
            await self._send_permission_response(
                result.get("approved", False), result.get("always", False)
            )

    async def _send_permission_response(self, approved: bool, always: bool = False):
        """Send a permission response to Claude"""
        if self.process is None or self.process.stdin is None:
            logger.error("Cannot send permission response: no process")
            return

        response = {
            "type": "permission_response",
            "approved": approved,
            "always": always,
        }

        try:
            response_str = json.dumps(response) + "\n"
            self.process.stdin.write(response_str.encode("utf-8"))
            await self.process.stdin.drain()
            logger.info(
                f"Permission response sent: approved={approved}, always={always}"
            )
        except Exception as e:
            logger.error(f"Error sending permission response: {e}")

    async def send_user_input(self, content: str):
        """Send additional user input to the running process"""
        if self.process is None or self.process.stdin is None:
            logger.error("Cannot send input: no process")
            return

        # Use same format as initial prompt (stream-json input format)
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
            logger.info("User input sent to Claude")
        except Exception as e:
            logger.error(f"Error sending user input: {e}")

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

        logger.info("Cancelling Claude Code process")

        try:
            # Close stdin first
            if self.process.stdin:
                self.process.stdin.close()

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

    @property
    def session_broken(self) -> bool:
        """
        Check if the Claude session is broken and cannot be continued.

        This happens when we execute tools locally (in toolApproval mode with plan)
        after Claude has already exited. Claude doesn't know about our local execution,
        so continuing the session would cause API errors.
        """
        return self._session_broken
