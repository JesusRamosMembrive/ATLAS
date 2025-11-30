# SPDX-License-Identifier: MIT
"""
Claude SDK Runner - Direct Anthropic API with Tool Interception

Uses the Anthropic Python SDK directly instead of Claude CLI.
Provides full control over tool execution flow:
1. Claude emits tool_use → we intercept
2. Show approval modal with diff preview
3. Execute only if user approves
4. Send tool_result back to Claude
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional, Awaitable
import glob as glob_module
import re

from anthropic import Anthropic, APIError
from anthropic.types import Message, ContentBlock, ToolUseBlock, TextBlock

from .tool_approval import ToolApprovalManager, ToolApprovalRequest

logger = logging.getLogger(__name__)


# Tool definitions for Claude
CLAUDE_TOOLS = [
    {
        "name": "Read",
        "description": "Read a file from the filesystem. Returns file contents with line numbers.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Absolute path to the file to read",
                },
                "offset": {
                    "type": "integer",
                    "description": "Line number to start reading from (0-indexed). Default: 0",
                },
                "limit": {
                    "type": "integer",
                    "description": "Number of lines to read. Default: 2000",
                },
            },
            "required": ["file_path"],
        },
    },
    {
        "name": "Write",
        "description": "Write content to a file. Creates parent directories if needed.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Absolute path to the file to write",
                },
                "content": {
                    "type": "string",
                    "description": "Content to write to the file",
                },
            },
            "required": ["file_path", "content"],
        },
    },
    {
        "name": "Edit",
        "description": "Edit a file by replacing a string with another string.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Absolute path to the file to edit",
                },
                "old_string": {
                    "type": "string",
                    "description": "The exact string to find and replace",
                },
                "new_string": {
                    "type": "string",
                    "description": "The string to replace it with",
                },
                "replace_all": {
                    "type": "boolean",
                    "description": "Replace all occurrences. Default: false (replace first only)",
                },
            },
            "required": ["file_path", "old_string", "new_string"],
        },
    },
    {
        "name": "Bash",
        "description": "Execute a bash command and return the output.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The bash command to execute",
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in milliseconds. Default: 120000 (2 minutes)",
                },
            },
            "required": ["command"],
        },
    },
    {
        "name": "Glob",
        "description": "Find files matching a glob pattern.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Glob pattern to match (e.g., '**/*.py')",
                },
                "path": {
                    "type": "string",
                    "description": "Directory to search in. Default: current working directory",
                },
            },
            "required": ["pattern"],
        },
    },
    {
        "name": "Grep",
        "description": "Search for a pattern in files using regex.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pattern": {
                    "type": "string",
                    "description": "Regular expression pattern to search for",
                },
                "path": {
                    "type": "string",
                    "description": "Directory to search in. Default: current working directory",
                },
                "glob": {
                    "type": "string",
                    "description": "Glob pattern to filter files. Default: **/*",
                },
            },
            "required": ["pattern"],
        },
    },
]


@dataclass
class SDKRunnerConfig:
    """Configuration for SDK-based Claude runner"""

    cwd: str
    model: str = "claude-sonnet-4-20250514"
    max_tokens: int = 8192
    system_prompt: str | None = None
    api_key: str | None = None  # Uses ANTHROPIC_API_KEY env var if None
    auto_approve_read: bool = True  # Auto-approve Read/Glob/Grep tools


@dataclass
class ConversationMessage:
    """A message in the conversation"""

    role: str  # "user" or "assistant"
    content: Any  # str or list of content blocks


class SDKAgentRunner:
    """
    Claude Agent using Anthropic SDK with tool approval workflow.

    Flow:
    1. Send user prompt to Claude API
    2. If Claude returns tool_use, intercept and request approval
    3. If approved, execute tool and send result back
    4. Repeat until Claude returns text-only response (end_turn)
    """

    # Tools that are safe to auto-approve (read-only)
    SAFE_TOOLS = {"Read", "Glob", "Grep"}

    # Tools that require explicit approval (modify state)
    APPROVAL_REQUIRED_TOOLS = {"Write", "Edit", "Bash"}

    def __init__(self, config: SDKRunnerConfig):
        self.config = config
        self.client = Anthropic(api_key=config.api_key)
        self.conversation: list[dict] = []
        self.running = False
        self._cancelled = False

        # Tool approval manager for generating previews/diffs
        self._tool_approval_manager = ToolApprovalManager(
            cwd=config.cwd,
            auto_approve_safe=config.auto_approve_read,
        )

        # Build system prompt with cwd context
        self._system_prompt = self._build_system_prompt()

    def _build_system_prompt(self) -> str:
        """Build the system prompt with working directory context"""
        base_prompt = self.config.system_prompt or ""

        cwd_context = f"""
You are a helpful coding assistant. You have access to tools to read, write, and edit files, execute bash commands, and search the codebase.

Current working directory: {self.config.cwd}

When working with files:
- Always use absolute paths
- The current working directory is: {self.config.cwd}
- You can use relative paths from this directory

When executing commands:
- Commands will run in: {self.config.cwd}
- Be careful with destructive commands

Important: When you need to make changes to files, ALWAYS use the tools. Do not just describe what you would do - actually execute the tools to make the changes.
"""
        return cwd_context + ("\n\n" + base_prompt if base_prompt else "")

    async def run_prompt(
        self,
        prompt: str,
        on_event: Callable[[dict], Any],
        on_error: Optional[Callable[[str], Any]] = None,
        on_done: Optional[Callable[[], Any]] = None,
        on_tool_approval_request: Optional[
            Callable[[ToolApprovalRequest], Awaitable[None]]
        ] = None,
    ) -> int:
        """
        Execute a prompt with tool approval workflow.

        Args:
            prompt: User prompt
            on_event: Callback for streaming events to frontend
            on_error: Callback for errors
            on_done: Callback when complete
            on_tool_approval_request: Callback to request tool approval from user

        Returns:
            0 on success, -1 on error
        """
        self.running = True
        self._cancelled = False

        try:
            # Add user message to conversation
            self.conversation.append({"role": "user", "content": prompt})

            # Send initial user message event
            await self._emit_event(
                on_event,
                {"type": "user", "subtype": "text", "content": {"text": prompt}},
            )

            # Main conversation loop
            while self.running and not self._cancelled:
                # Call Claude API
                logger.info(
                    f"[SDKRunner] Calling Claude API with {len(self.conversation)} messages"
                )

                try:
                    response = await self._call_claude_api()
                except APIError as e:
                    logger.error(f"[SDKRunner] API error: {e}")
                    if on_error:
                        result = on_error(f"API Error: {str(e)}")
                        if asyncio.iscoroutine(result):
                            await result
                    return -1

                if self._cancelled:
                    break

                # Process response
                stop_reason = response.stop_reason
                logger.info(f"[SDKRunner] Response stop_reason: {stop_reason}")

                # Emit assistant message events
                await self._process_response_content(response, on_event)

                # Check if we need to handle tool use
                if stop_reason == "tool_use":
                    # Extract tool uses from response
                    tool_uses = [
                        block
                        for block in response.content
                        if isinstance(block, ToolUseBlock)
                    ]

                    if not tool_uses:
                        logger.warning(
                            "[SDKRunner] tool_use stop_reason but no tool blocks found"
                        )
                        break

                    # Process each tool use
                    tool_results = []
                    for tool_use in tool_uses:
                        tool_result = await self._handle_tool_use(
                            tool_use, on_event, on_tool_approval_request
                        )
                        tool_results.append(tool_result)

                        if self._cancelled:
                            break

                    if self._cancelled:
                        break

                    # Add assistant message and tool results to conversation
                    self.conversation.append(
                        {
                            "role": "assistant",
                            "content": [
                                self._content_block_to_dict(block)
                                for block in response.content
                            ],
                        }
                    )

                    self.conversation.append({"role": "user", "content": tool_results})

                    # Continue the loop to get Claude's next response
                    continue

                elif stop_reason == "end_turn":
                    # Claude finished naturally - add response to conversation and exit
                    self.conversation.append(
                        {
                            "role": "assistant",
                            "content": [
                                self._content_block_to_dict(block)
                                for block in response.content
                            ],
                        }
                    )
                    break

                else:
                    # Other stop reasons (max_tokens, etc.)
                    logger.warning(f"[SDKRunner] Unexpected stop_reason: {stop_reason}")
                    self.conversation.append(
                        {
                            "role": "assistant",
                            "content": [
                                self._content_block_to_dict(block)
                                for block in response.content
                            ],
                        }
                    )
                    break

            # Done
            logger.info("[SDKRunner] Conversation complete")

            # Emit done event
            await self._emit_event(
                on_event,
                {
                    "type": "result",
                    "subtype": "success",
                    "content": {"message": "Conversation complete"},
                },
            )

            if on_done:
                result = on_done()
                if asyncio.iscoroutine(result):
                    await result

            return 0

        except Exception as e:
            logger.error(f"[SDKRunner] Error: {e}", exc_info=True)
            if on_error:
                result = on_error(str(e))
                if asyncio.iscoroutine(result):
                    await result
            return -1
        finally:
            self.running = False

    async def _call_claude_api(self) -> Message:
        """Call Claude API with current conversation"""
        # Run in thread pool to not block event loop
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.client.messages.create(
                model=self.config.model,
                max_tokens=self.config.max_tokens,
                system=self._system_prompt,
                tools=CLAUDE_TOOLS,  # type: ignore[arg-type]
                messages=self.conversation,  # type: ignore[arg-type]
            ),
        )

    async def _process_response_content(
        self, response: Message, on_event: Callable[[dict], Any]
    ):
        """Process and emit events for response content blocks"""
        for block in response.content:
            if isinstance(block, TextBlock):
                # Emit text content
                await self._emit_event(
                    on_event,
                    {
                        "type": "assistant",
                        "subtype": "text",
                        "content": {"text": block.text},
                    },
                )
            elif isinstance(block, ToolUseBlock):
                # Emit tool_use event
                await self._emit_event(
                    on_event,
                    {
                        "type": "assistant",
                        "subtype": "tool_use",
                        "content": {
                            "id": block.id,
                            "name": block.name,
                            "input": block.input,
                        },
                    },
                )

    async def _handle_tool_use(
        self,
        tool_use: ToolUseBlock,
        on_event: Callable[[dict], Any],
        on_tool_approval_request: Optional[
            Callable[[ToolApprovalRequest], Awaitable[None]]
        ],
    ) -> dict:
        """
        Handle a tool use block - request approval and execute if approved.

        Returns tool_result dict for the API.
        """
        tool_name = tool_use.name
        tool_input = tool_use.input
        tool_id = tool_use.id

        logger.info(f"[SDKRunner] Handling tool_use: {tool_name} (id={tool_id})")

        # Check if this is a safe tool that can be auto-approved
        if self.config.auto_approve_read and tool_name in self.SAFE_TOOLS:
            logger.info(f"[SDKRunner] Auto-approving safe tool: {tool_name}")
            result = await self._execute_tool(tool_name, tool_input)

            # Emit tool result event
            await self._emit_event(
                on_event,
                {
                    "type": "user",
                    "subtype": "tool_result",
                    "content": {
                        "tool_use_id": tool_id,
                        "content": result.get("content", ""),
                        "is_error": result.get("is_error", False),
                    },
                },
            )

            return {
                "type": "tool_result",
                "tool_use_id": tool_id,
                "content": result.get("content", ""),
                "is_error": result.get("is_error", False),
            }

        # Tool requires approval
        if on_tool_approval_request is None:
            # No approval handler - auto-reject
            logger.warning(f"[SDKRunner] No approval handler, rejecting {tool_name}")
            error_msg = f"Tool {tool_name} requires approval but no handler provided"

            await self._emit_event(
                on_event,
                {
                    "type": "user",
                    "subtype": "tool_result",
                    "content": {
                        "tool_use_id": tool_id,
                        "content": error_msg,
                        "is_error": True,
                    },
                },
            )

            return {
                "type": "tool_result",
                "tool_use_id": tool_id,
                "content": error_msg,
                "is_error": True,
            }

        # Request approval through the manager
        logger.info(f"[SDKRunner] Requesting approval for {tool_name}")

        approved, feedback = await self._tool_approval_manager.process_tool_use(
            tool_name=tool_name,
            tool_input=tool_input,
            tool_use_id=tool_id,
            on_approval_request=on_tool_approval_request,
        )

        logger.info(
            f"[SDKRunner] Approval result: approved={approved}, feedback={feedback}"
        )

        if approved:
            # Execute the tool
            result = await self._execute_tool(tool_name, tool_input)

            # Emit tool result event
            await self._emit_event(
                on_event,
                {
                    "type": "user",
                    "subtype": "tool_result",
                    "content": {
                        "tool_use_id": tool_id,
                        "content": result.get("content", ""),
                        "is_error": result.get("is_error", False),
                    },
                },
            )

            return {
                "type": "tool_result",
                "tool_use_id": tool_id,
                "content": result.get("content", ""),
                "is_error": result.get("is_error", False),
            }
        else:
            # Rejected
            error_msg = (
                f"User rejected tool execution: {feedback or 'No reason provided'}"
            )

            await self._emit_event(
                on_event,
                {
                    "type": "user",
                    "subtype": "tool_result",
                    "content": {
                        "tool_use_id": tool_id,
                        "content": error_msg,
                        "is_error": True,
                    },
                },
            )

            return {
                "type": "tool_result",
                "tool_use_id": tool_id,
                "content": error_msg,
                "is_error": True,
            }

    async def _execute_tool(self, tool_name: str, tool_input: dict) -> dict:
        """Execute a tool and return result"""
        try:
            if tool_name == "Read":
                return await self._execute_read(tool_input)
            elif tool_name == "Write":
                return await self._execute_write(tool_input)
            elif tool_name == "Edit":
                return await self._execute_edit(tool_input)
            elif tool_name == "Bash":
                return await self._execute_bash(tool_input)
            elif tool_name == "Glob":
                return await self._execute_glob(tool_input)
            elif tool_name == "Grep":
                return await self._execute_grep(tool_input)
            else:
                return {"content": f"Unknown tool: {tool_name}", "is_error": True}
        except Exception as e:
            logger.error(f"[SDKRunner] Tool execution error: {e}", exc_info=True)
            return {
                "content": f"Error executing {tool_name}: {str(e)}",
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

            return {"content": "\n".join(result_lines), "is_error": False}
        except Exception as e:
            return {"content": f"Error reading {file_path}: {str(e)}", "is_error": True}

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
                "content": f"Wrote {len(content)} characters to {file_path}",
                "is_error": False,
            }
        except Exception as e:
            return {"content": f"Error writing {file_path}: {str(e)}", "is_error": True}

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
                return {"content": f"String not found in {file_path}", "is_error": True}

            if replace_all:
                new_content = content.replace(old_string, new_string)
                count = content.count(old_string)
            else:
                new_content = content.replace(old_string, new_string, 1)
                count = 1

            path.write_text(new_content, encoding="utf-8")
            return {
                "content": f"Replaced {count} occurrence(s) in {file_path}",
                "is_error": False,
            }
        except Exception as e:
            return {"content": f"Error editing {file_path}: {str(e)}", "is_error": True}

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
                    proc.communicate(), timeout=timeout_sec
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

            return {"content": output or "(no output)", "is_error": False}
        except Exception as e:
            return {"content": f"Error executing command: {str(e)}", "is_error": True}

    async def _execute_glob(self, tool_input: dict) -> dict:
        """Execute Glob tool"""
        pattern = tool_input.get("pattern", "")
        search_path = tool_input.get("path", self.config.cwd)

        try:
            full_pattern = os.path.join(search_path, pattern)
            matches = glob_module.glob(full_pattern, recursive=True)
            matches.sort()

            if not matches:
                return {"content": f"No files matching: {pattern}", "is_error": False}

            return {"content": "\n".join(matches[:100]), "is_error": False}
        except Exception as e:
            return {"content": f"Glob error: {str(e)}", "is_error": True}

    async def _execute_grep(self, tool_input: dict) -> dict:
        """Execute Grep tool"""
        pattern = tool_input.get("pattern", "")
        search_path = tool_input.get("path", self.config.cwd)
        glob_pattern = tool_input.get("glob", "**/*")

        try:
            regex = re.compile(pattern)
        except re.error as e:
            return {"content": f"Invalid regex: {str(e)}", "is_error": True}

        try:
            files = glob_module.glob(
                os.path.join(search_path, glob_pattern), recursive=True
            )

            matches = []
            for file_path in files[:100]:
                if not os.path.isfile(file_path):
                    continue
                try:
                    with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                        for line_num, line in enumerate(f, 1):
                            if regex.search(line):
                                matches.append(
                                    f"{file_path}:{line_num}:{line.rstrip()}"
                                )
                                if len(matches) >= 100:
                                    break
                except Exception:
                    continue

                if len(matches) >= 100:
                    break

            if not matches:
                return {"content": f"No matches for: {pattern}", "is_error": False}

            return {"content": "\n".join(matches), "is_error": False}
        except Exception as e:
            return {"content": f"Grep error: {str(e)}", "is_error": True}

    def _content_block_to_dict(self, block: ContentBlock) -> dict:
        """Convert a content block to a dict for the API"""
        if isinstance(block, TextBlock):
            return {"type": "text", "text": block.text}
        elif isinstance(block, ToolUseBlock):
            return {
                "type": "tool_use",
                "id": block.id,
                "name": block.name,
                "input": block.input,
            }
        else:
            # Unknown block type
            return {"type": "text", "text": str(block)}

    async def _emit_event(self, on_event: Callable[[dict], Any], event: dict):
        """Emit an event to the callback"""
        try:
            result = on_event(event)
            if asyncio.iscoroutine(result):
                await result
        except Exception as e:
            logger.error(f"[SDKRunner] Error emitting event: {e}")

    def respond_to_tool_approval(
        self, request_id: str, approved: bool, feedback: str | None = None
    ) -> bool:
        """
        Respond to a pending tool approval request.

        This is called by the API when the user approves/rejects in the frontend.
        """
        return self._tool_approval_manager.respond_to_approval(
            request_id, approved, feedback
        )

    async def cancel(self):
        """Cancel the running conversation"""
        self._cancelled = True
        self.running = False

    @property
    def is_running(self) -> bool:
        """Check if conversation is running"""
        return self.running

    def clear_conversation(self):
        """Clear the conversation history"""
        self.conversation = []
