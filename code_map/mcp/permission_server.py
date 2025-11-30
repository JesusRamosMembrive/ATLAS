#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
MCP Permission Server for Claude Code Tool Approval.

This server implements the --permission-prompt-tool interface for Claude Code.
It receives permission requests from Claude Code and coordinates with the
ATLAS backend to get user approval via the frontend UI.

Usage with Claude Code:
    claude -p --permission-prompt-tool mcp__atlas_approval__check_permission "prompt"

The server communicates with the ATLAS backend via Unix socket to:
1. Receive permission requests from Claude Code
2. Forward them to the frontend for user approval
3. Return the user's decision to Claude Code

Response format (per Claude Code spec):
    Allow:  {"behavior": "allow", "updatedInput": {...}}
    Deny:   {"behavior": "deny", "message": "..."}
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Socket path for communication with ATLAS backend
DEFAULT_SOCKET_PATH = "/tmp/atlas_mcp_approval.sock"


class PermissionServer:
    """
    MCP Permission Server that handles tool approval requests.

    This can run in two modes:
    1. Standalone: Communicates with ATLAS backend via Unix socket
    2. Embedded: Uses ApprovalBridge directly (for testing)
    """

    def __init__(
        self,
        socket_path: str = DEFAULT_SOCKET_PATH,
        timeout: float = 300.0,
        auto_approve_safe: bool = False,
    ):
        self.socket_path = socket_path
        self.timeout = timeout
        self.auto_approve_safe = auto_approve_safe

        # For embedded mode
        self._bridge: Optional[Any] = None

        # Safe tools that can be auto-approved
        self.SAFE_TOOLS = {
            "Read",
            "Glob",
            "Grep",
            "TodoWrite",
            "WebFetch",
            "WebSearch",
            "Task",
        }

    def set_bridge(self, bridge: Any) -> None:
        """Set ApprovalBridge for embedded mode"""
        self._bridge = bridge
        logger.info("PermissionServer: Using embedded bridge")

    async def check_permission(
        self, tool_name: str, tool_input: dict[str, Any], context: str = ""
    ) -> dict[str, Any]:
        """
        Check if a tool execution should be allowed.

        This is the main entry point called by Claude Code via MCP.

        Args:
            tool_name: Name of the tool (e.g., "Edit", "Bash")
            tool_input: Input parameters for the tool
            context: Additional context

        Returns:
            {"behavior": "allow", "updatedInput": {...}} or
            {"behavior": "deny", "message": "..."}
        """
        print(
            f"DEBUG: [PermissionServer] check_permission called for {tool_name}",
            flush=True,
        )
        logger.info(f"Permission check requested for tool: {tool_name}")

        # Auto-approve safe tools if configured
        if self.auto_approve_safe and tool_name in self.SAFE_TOOLS:
            logger.info(f"Auto-approving safe tool: {tool_name}")
            return {"behavior": "allow", "updatedInput": tool_input}

        try:
            # Use embedded bridge if available
            if self._bridge:
                result = await self._request_via_bridge(tool_name, tool_input, context)
            else:
                # Use socket communication
                result = await self._request_via_socket(tool_name, tool_input, context)

            if result.get("approved", False):
                return {
                    "behavior": "allow",
                    "updatedInput": result.get("updated_input", tool_input),
                }
            else:
                return {
                    "behavior": "deny",
                    "message": result.get("message", "User denied the operation"),
                }

        except Exception as e:
            logger.error(f"Error in permission check: {e}", exc_info=True)
            print(f"DEBUG: [PermissionServer] Error: {e}", flush=True)
            # On error, deny for safety
            return {"behavior": "deny", "message": f"Permission check failed: {e}"}

    async def _request_via_bridge(
        self, tool_name: str, tool_input: dict[str, Any], context: str
    ) -> dict[str, Any]:
        """Request approval via embedded ApprovalBridge"""
        print("DEBUG: [PermissionServer] Using embedded bridge", flush=True)
        if self._bridge is None:
            raise RuntimeError("Bridge not set - call set_bridge() first")
        return await self._bridge.request_approval(tool_name, tool_input, context)

    async def _request_via_socket(
        self, tool_name: str, tool_input: dict[str, Any], context: str
    ) -> dict[str, Any]:
        """Request approval via Unix socket to ATLAS backend"""
        print(
            f"DEBUG: [PermissionServer] Connecting to socket {self.socket_path}",
            flush=True,
        )

        try:
            # Connect to ATLAS backend
            reader, writer = await asyncio.open_unix_connection(self.socket_path)

            # Send request
            request = {
                "type": "approval_request",
                "tool_name": tool_name,
                "tool_input": tool_input,
                "context": context,
            }
            request_json = json.dumps(request) + "\n"
            writer.write(request_json.encode())
            await writer.drain()

            print(
                "DEBUG: [PermissionServer] Request sent, waiting for response...",
                flush=True,
            )

            # Wait for response with timeout
            try:
                response_line = await asyncio.wait_for(
                    reader.readline(), timeout=self.timeout
                )
                response = json.loads(response_line.decode())
                print(f"DEBUG: [PermissionServer] Got response: {response}", flush=True)
                return response

            except asyncio.TimeoutError:
                print("DEBUG: [PermissionServer] Socket timeout", flush=True)
                return {"approved": False, "message": "Approval timeout"}

            finally:
                writer.close()
                await writer.wait_closed()

        except FileNotFoundError:
            print(
                f"DEBUG: [PermissionServer] Socket not found: {self.socket_path}",
                flush=True,
            )
            logger.warning(f"Socket not found: {self.socket_path}, auto-approving")
            # If backend not running, auto-approve (development mode)
            return {"approved": True, "message": "Backend not connected"}

        except Exception as e:
            print(f"DEBUG: [PermissionServer] Socket error: {e}", flush=True)
            logger.error(f"Socket communication error: {e}")
            return {"approved": False, "message": f"Communication error: {e}"}


# Global server instance for MCP
_server: Optional[PermissionServer] = None


def get_server() -> PermissionServer:
    """Get or create the global PermissionServer instance"""
    global _server
    if _server is None:
        socket_path = os.environ.get("ATLAS_MCP_SOCKET", DEFAULT_SOCKET_PATH)
        auto_approve = os.environ.get("ATLAS_MCP_AUTO_APPROVE", "").lower() == "true"
        _server = PermissionServer(
            socket_path=socket_path, auto_approve_safe=auto_approve
        )
    return _server


def set_server(server: PermissionServer) -> None:
    """Set the global PermissionServer instance"""
    global _server
    _server = server


# ============================================================================
# MCP Tool Definition (for FastMCP)
# ============================================================================


def create_mcp_server():
    """
    Create FastMCP server with the check_permission tool.

    This is used when running as a standalone MCP server.
    """
    try:
        from mcp.server.fastmcp import FastMCP
    except ImportError:
        logger.error("MCP SDK not installed. Run: pip install 'mcp[cli]'")
        raise

    mcp = FastMCP("atlas_approval")

    @mcp.tool()
    async def check_permission(
        tool_name: str, tool_input: dict, context: str = ""
    ) -> str:
        """
        Check if a tool execution should be allowed.

        This tool is called by Claude Code via --permission-prompt-tool
        to request approval for tool executions.

        Args:
            tool_name: Name of the tool to execute
            tool_input: Input parameters for the tool
            context: Additional context about the operation

        Returns:
            JSON string with behavior (allow/deny) and details
        """
        server = get_server()
        result = await server.check_permission(tool_name, tool_input, context)
        return json.dumps(result)

    return mcp


# ============================================================================
# Standalone Entry Point
# ============================================================================


def main():
    """Run the MCP server in standalone mode"""
    import argparse

    parser = argparse.ArgumentParser(description="ATLAS MCP Permission Server")
    parser.add_argument(
        "--socket",
        default=DEFAULT_SOCKET_PATH,
        help="Unix socket path for communication with ATLAS backend",
    )
    parser.add_argument(
        "--auto-approve-safe",
        action="store_true",
        help="Auto-approve safe tools (Read, Glob, etc.)",
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse", "streamable-http"],
        default="stdio",
        help="MCP transport type",
    )
    parser.add_argument(
        "--port", type=int, default=8011, help="Port for HTTP transport"
    )

    args = parser.parse_args()

    # Configure server
    os.environ["ATLAS_MCP_SOCKET"] = args.socket
    if args.auto_approve_safe:
        os.environ["ATLAS_MCP_AUTO_APPROVE"] = "true"

    # Create and run MCP server
    mcp = create_mcp_server()

    print("Starting ATLAS MCP Permission Server", file=sys.stderr)
    print(f"  Socket: {args.socket}", file=sys.stderr)
    print(f"  Transport: {args.transport}", file=sys.stderr)
    print(f"  Auto-approve safe: {args.auto_approve_safe}", file=sys.stderr)

    if args.transport == "stdio":
        mcp.run(transport="stdio")
    elif args.transport == "sse":
        mcp.run(transport="sse", port=args.port)
    else:
        mcp.run(transport="streamable-http", port=args.port)


if __name__ == "__main__":
    main()
