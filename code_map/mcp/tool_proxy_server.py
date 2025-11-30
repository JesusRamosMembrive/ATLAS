#!/usr/bin/env python3
"""
MCP Tool Proxy Server for ATLAS Tool Approval.

This server provides proxy tools (atlas_write, atlas_edit, atlas_bash) that
require user approval before execution. When Claude uses these tools, the
server communicates with the ATLAS backend to get user approval.

Architecture:
1. Claude CLI runs with --disallowed-tools "Write,Edit,Bash"
2. This MCP server provides atlas_write, atlas_edit, atlas_bash
3. Claude uses proxy tools instead of native tools
4. Proxy tools request approval via Unix socket to ATLAS backend
5. If approved, proxy executes the operation and returns result
6. If denied, proxy returns error to Claude

Usage with Claude Code:
    claude -p \\
        --disallowed-tools "Write,Edit,Bash" \\
        --mcp-config /path/to/atlas_proxy.json \\
        --dangerously-skip-permissions \\
        "your prompt"

Socket Communication Protocol:
    Request: {"type": "approval_request", "tool": "write", "params": {...}, "request_id": "..."}
    Response: {"approved": true/false, "request_id": "...", "feedback": "..."}
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import uuid
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Import shared constants
try:
    from .constants import (
        DEFAULT_SOCKET_PATH,
        APPROVAL_TIMEOUT,
        PREVIEW_LINE_LIMIT,
        PREVIEW_CHAR_LIMIT,
        COMMAND_TIMEOUT_MS,
        ENV_TOOL_SOCKET,
        ENV_CWD,
    )
except ImportError:
    # Fallback for standalone execution
    DEFAULT_SOCKET_PATH = "/tmp/atlas_tool_approval.sock"
    APPROVAL_TIMEOUT = 300.0
    PREVIEW_LINE_LIMIT = 50
    PREVIEW_CHAR_LIMIT = 200
    COMMAND_TIMEOUT_MS = 120000
    ENV_TOOL_SOCKET = "ATLAS_TOOL_SOCKET"
    ENV_CWD = "ATLAS_CWD"


class ToolProxyServer:
    """
    MCP Tool Proxy Server that requires approval for dangerous operations.

    Provides proxy implementations of Write, Edit, and Bash that:
    1. Generate diff previews for file operations
    2. Request user approval via socket
    3. Execute only if approved
    """

    def __init__(
        self,
        socket_path: str = DEFAULT_SOCKET_PATH,
        timeout: float = APPROVAL_TIMEOUT,
        cwd: str = "",
    ):
        self.socket_path = socket_path
        self.timeout = timeout
        self.cwd = cwd or os.getcwd()

    async def _request_approval(
        self,
        tool: str,
        params: dict[str, Any],
        preview: str = "",
    ) -> tuple[bool, str]:
        """
        Request approval from ATLAS backend.

        Returns (approved, feedback) tuple.
        """
        request_id = str(uuid.uuid4())

        request = {
            "type": "tool_approval_request",
            "request_id": request_id,
            "tool": tool,
            "params": params,
            "preview": preview,
            "cwd": self.cwd,
        }

        try:
            logger.debug(f"Connecting to socket {self.socket_path}")
            reader, writer = await asyncio.open_unix_connection(self.socket_path)
            logger.debug("Connected to socket")

            # Send request
            writer.write((json.dumps(request) + "\n").encode())
            await writer.drain()

            logger.debug(f"Sent approval request {request_id} for {tool}")

            # Wait for response
            try:
                response_line = await asyncio.wait_for(
                    reader.readline(), timeout=self.timeout
                )
                response = json.loads(response_line.decode())

                approved = response.get("approved", False)
                feedback = response.get("feedback", "")

                logger.debug(f"Got response for {request_id}: approved={approved}")
                return (approved, feedback)

            except asyncio.TimeoutError:
                logger.warning(f"Approval timeout for {request_id}")
                return (False, "Approval request timed out")

            finally:
                writer.close()
                await writer.wait_closed()

        except FileNotFoundError:
            # Socket not found - ATLAS backend not running
            # In development, we could auto-approve, but for safety we deny
            logger.warning(f"Socket not found: {self.socket_path}")
            return (False, "ATLAS backend not connected. Cannot approve tools.")

        except Exception as e:
            logger.error(f"Error requesting approval: {e}")
            return (False, f"Error: {e}")

    def _generate_write_preview(self, file_path: str, content: str) -> str:
        """Generate preview for Write operation"""
        path = Path(file_path)
        if not path.is_absolute():
            path = Path(self.cwd) / path

        lines = content.split("\n")
        preview_lines = lines[:PREVIEW_LINE_LIMIT]
        if len(lines) > PREVIEW_LINE_LIMIT:
            preview_lines.append(f"... ({len(lines) - PREVIEW_LINE_LIMIT} more lines)")

        if path.exists():
            return f"OVERWRITE {file_path}\n\n" + "\n".join(
                f"+ {line}" for line in preview_lines
            )
        else:
            return f"CREATE {file_path}\n\n" + "\n".join(
                f"+ {line}" for line in preview_lines
            )

    def _generate_edit_preview(
        self,
        file_path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,
    ) -> str:
        """Generate diff preview for Edit operation"""
        path = Path(file_path)
        if not path.is_absolute():
            path = Path(self.cwd) / path

        if not path.exists():
            return f"ERROR: File does not exist: {file_path}"

        try:
            content = path.read_text()
            if old_string not in content:
                return f"ERROR: String not found in {file_path}"

            # Count occurrences
            count = content.count(old_string)
            replace_count = count if replace_all else 1

            # Generate unified diff style preview
            old_lines = old_string.split("\n")
            new_lines = new_string.split("\n")

            preview = f"EDIT {file_path} ({replace_count} replacement{'s' if replace_count > 1 else ''})\n\n"
            preview += "--- old\n+++ new\n"

            for line in old_lines:
                preview += f"- {line}\n"
            for line in new_lines:
                preview += f"+ {line}\n"

            return preview

        except Exception as e:
            return f"ERROR: Could not read file: {e}"

    def _generate_bash_preview(self, command: str) -> str:
        """Generate preview for Bash command"""
        return f"EXECUTE COMMAND:\n$ {command}"

    async def atlas_write(self, file_path: str, content: str) -> str:
        """
        Write content to a file (requires approval).

        Args:
            file_path: Absolute or relative path to the file
            content: Content to write to the file

        Returns:
            Success message or error description
        """
        preview = self._generate_write_preview(file_path, content)

        approved, feedback = await self._request_approval(
            tool="write",
            params={"file_path": file_path, "content": content},
            preview=preview,
        )

        if not approved:
            return f"[DENIED] Write operation rejected: {feedback}"

        # Execute the write
        try:
            path = Path(file_path)
            if not path.is_absolute():
                path = Path(self.cwd) / path

            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")

            return f"Successfully wrote {len(content)} characters to {file_path}"

        except Exception as e:
            return f"[ERROR] Failed to write file: {e}"

    async def atlas_edit(
        self,
        file_path: str,
        old_string: str,
        new_string: str,
        replace_all: bool = False,
    ) -> str:
        """
        Edit a file by replacing text (requires approval).

        Args:
            file_path: Path to the file to edit
            old_string: Text to find and replace
            new_string: Replacement text
            replace_all: If True, replace all occurrences

        Returns:
            Success message or error description
        """
        preview = self._generate_edit_preview(
            file_path, old_string, new_string, replace_all
        )

        if preview.startswith("ERROR:"):
            return preview

        approved, feedback = await self._request_approval(
            tool="edit",
            params={
                "file_path": file_path,
                "old_string": old_string,
                "new_string": new_string,
                "replace_all": replace_all,
            },
            preview=preview,
        )

        if not approved:
            return f"[DENIED] Edit operation rejected: {feedback}"

        # Execute the edit
        try:
            path = Path(file_path)
            if not path.is_absolute():
                path = Path(self.cwd) / path

            content = path.read_text(encoding="utf-8")

            if replace_all:
                new_content = content.replace(old_string, new_string)
                count = content.count(old_string)
            else:
                new_content = content.replace(old_string, new_string, 1)
                count = 1

            path.write_text(new_content, encoding="utf-8")

            return f"Successfully replaced {count} occurrence(s) in {file_path}"

        except Exception as e:
            return f"[ERROR] Failed to edit file: {e}"

    async def atlas_bash(
        self, command: str, timeout: int = COMMAND_TIMEOUT_MS, description: str = ""
    ) -> str:
        """
        Execute a bash command (requires approval).

        Args:
            command: The bash command to execute
            timeout: Timeout in milliseconds (default 2 minutes)
            description: Optional description of what the command does

        Returns:
            Command output or error description
        """
        preview = self._generate_bash_preview(command)
        if description:
            preview += f"\n\nDescription: {description}"

        approved, feedback = await self._request_approval(
            tool="bash",
            params={
                "command": command,
                "timeout": timeout,
                "description": description,
            },
            preview=preview,
        )

        if not approved:
            return f"[DENIED] Command execution rejected: {feedback}"

        # Execute the command
        try:
            timeout_sec = timeout / 1000

            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.cwd,
            )

            try:
                stdout, stderr = await asyncio.wait_for(
                    proc.communicate(), timeout=timeout_sec
                )
            except asyncio.TimeoutError:
                proc.kill()
                return f"[ERROR] Command timed out after {timeout_sec}s"

            output = stdout.decode("utf-8", errors="replace")
            error = stderr.decode("utf-8", errors="replace")

            if proc.returncode != 0:
                return f"[ERROR] Exit code {proc.returncode}\n{output}\n{error}".strip()

            return output or "(no output)"

        except Exception as e:
            return f"[ERROR] Failed to execute command: {e}"


# Global server instance
_server: Optional[ToolProxyServer] = None


def get_server() -> ToolProxyServer:
    """Get or create the global ToolProxyServer instance"""
    global _server
    if _server is None:
        socket_path = os.environ.get(ENV_TOOL_SOCKET, DEFAULT_SOCKET_PATH)
        cwd = os.environ.get(ENV_CWD, os.getcwd())
        _server = ToolProxyServer(socket_path=socket_path, cwd=cwd)
    return _server


def create_mcp_server():
    """Create FastMCP server with proxy tools"""
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError:
        logger.error("MCP SDK not installed. Run: pip install 'mcp[cli]'")
        raise

    mcp = FastMCP("atlas_tools")

    @mcp.tool()
    async def atlas_write(file_path: str, content: str) -> str:
        """
        Write content to a file. Creates parent directories if needed.
        This tool requires user approval before execution.

        Args:
            file_path: Absolute path to the file to write
            content: Content to write to the file
        """
        server = get_server()
        return await server.atlas_write(file_path, content)

    @mcp.tool()
    async def atlas_edit(
        file_path: str, old_string: str, new_string: str, replace_all: bool = False
    ) -> str:
        """
        Edit a file by replacing text. Performs exact string replacement.
        This tool requires user approval before execution.

        Args:
            file_path: Path to the file to edit
            old_string: The exact text to find and replace
            new_string: The replacement text
            replace_all: If True, replace all occurrences (default False)
        """
        server = get_server()
        return await server.atlas_edit(file_path, old_string, new_string, replace_all)

    @mcp.tool()
    async def atlas_bash(
        command: str, timeout: int = 120000, description: str = ""
    ) -> str:
        """
        Execute a bash command in the current working directory.
        This tool requires user approval before execution.

        Args:
            command: The bash command to execute
            timeout: Timeout in milliseconds (default 120000 = 2 minutes)
            description: Optional description of what the command does
        """
        server = get_server()
        return await server.atlas_bash(command, timeout, description)

    # Also provide read-only tools that don't need approval
    @mcp.tool()
    async def atlas_read(file_path: str, offset: int = 0, limit: int = 2000) -> str:
        """
        Read content from a file. Does not require approval.

        Args:
            file_path: Path to the file to read
            offset: Line number to start from (0-based)
            limit: Maximum number of lines to read
        """
        server = get_server()
        path = Path(file_path)
        if not path.is_absolute():
            path = Path(server.cwd) / path

        try:
            if not path.exists():
                return f"File does not exist: {file_path}"

            content = path.read_text(encoding="utf-8")
            lines = content.splitlines()

            selected = lines[offset : offset + limit]

            result = []
            for i, line in enumerate(selected, start=offset + 1):
                if len(line) > 2000:
                    line = line[:2000] + "..."
                result.append(f"{i:>6}\t{line}")

            return "\n".join(result)

        except Exception as e:
            return f"Error reading file: {e}"

    return mcp


def main():
    """Run the MCP Tool Proxy Server"""
    import argparse

    parser = argparse.ArgumentParser(description="ATLAS MCP Tool Proxy Server")
    parser.add_argument(
        "--socket",
        default=DEFAULT_SOCKET_PATH,
        help="Unix socket path for approval requests",
    )
    parser.add_argument(
        "--cwd", default="", help="Working directory for file operations"
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default="stdio",
        help="MCP transport type",
    )
    parser.add_argument("--port", type=int, default=8012, help="Port for SSE transport")

    args = parser.parse_args()

    # Configure environment
    os.environ["ATLAS_TOOL_SOCKET"] = args.socket
    if args.cwd:
        os.environ["ATLAS_CWD"] = args.cwd

    # Create and run server
    mcp = create_mcp_server()

    print("Starting ATLAS MCP Tool Proxy Server", file=sys.stderr)
    print(f"  Socket: {args.socket}", file=sys.stderr)
    print(f"  CWD: {args.cwd or os.getcwd()}", file=sys.stderr)
    print(f"  Transport: {args.transport}", file=sys.stderr)

    if args.transport == "stdio":
        mcp.run(transport="stdio")
    else:
        mcp.run(transport="sse", port=args.port)


if __name__ == "__main__":
    main()
