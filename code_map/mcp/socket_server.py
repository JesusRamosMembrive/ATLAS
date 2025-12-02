# SPDX-License-Identifier: MIT
"""
Socket Server for MCP Permission Communication.

This server runs as part of the AEGIS backend and listens for
permission requests from the MCP Permission Server subprocess.

It bridges the MCP server (running as Claude Code subprocess) with
the frontend (via WebSocket).

Platform support:
- Unix: Uses Unix domain sockets
- Windows: Uses TCP sockets on localhost
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Optional, Callable, Awaitable, Any

from .approval_bridge import ApprovalBridge, ApprovalRequest
from .constants import (
    DEFAULT_SOCKET_PATH,
    DEFAULT_SOCKET_HOST,
    DEFAULT_SOCKET_PORT,
    APPROVAL_TIMEOUT,
    IS_WINDOWS,
)

logger = logging.getLogger(__name__)


class MCPSocketServer:
    """
    Socket server that receives permission requests from MCP server.

    This runs in the main AEGIS backend process and:
    1. Listens on a socket for requests from MCP Permission Server
       - Unix: Unix domain socket
       - Windows: TCP socket on localhost
    2. Forwards requests to the ApprovalBridge
    3. The bridge notifies the frontend and waits for user response
    4. Returns the response to the MCP server via socket
    """

    def __init__(
        self,
        socket_path: str = DEFAULT_SOCKET_PATH,
        cwd: str = ".",
        timeout: float = APPROVAL_TIMEOUT,
        auto_approve_safe: bool = False,
    ):
        self.socket_path = socket_path
        self.cwd = cwd

        # Parse socket address for TCP mode (Windows)
        self._use_tcp = IS_WINDOWS or socket_path.startswith("tcp://")
        if self._use_tcp:
            if socket_path.startswith("tcp://"):
                # Parse tcp://host:port format
                addr = socket_path[6:]  # Remove "tcp://"
                host, port = addr.rsplit(":", 1)
                self._tcp_host = host
                self._tcp_port = int(port)
            else:
                # Use defaults
                self._tcp_host = DEFAULT_SOCKET_HOST or "127.0.0.1"
                self._tcp_port = DEFAULT_SOCKET_PORT or 18010

        # Create approval bridge
        self.bridge = ApprovalBridge(
            cwd=cwd, timeout=timeout, auto_approve_safe=auto_approve_safe
        )

        # Server state
        self._server: Optional[asyncio.Server] = None
        self._running = False

    def set_frontend_callback(
        self, callback: Callable[[ApprovalRequest], Awaitable[None]]
    ) -> None:
        """
        Set callback to notify frontend of approval requests.

        The callback should send the ApprovalRequest to the frontend
        via WebSocket.
        """
        self.bridge.set_notify_callback(callback)

    async def start(self) -> None:
        """Start the socket server (Unix socket or TCP depending on platform)"""
        if self._use_tcp:
            # Windows/TCP mode: Use TCP socket on localhost
            self._server = await asyncio.start_server(
                self._handle_client,
                host=self._tcp_host,
                port=self._tcp_port,
            )
            self._running = True
            logger.info(f"MCP Socket Server started on tcp://{self._tcp_host}:{self._tcp_port}")
        else:
            # Unix mode: Use Unix domain socket
            socket_path = Path(self.socket_path)

            # Remove old socket if exists
            if socket_path.exists():
                socket_path.unlink()

            # Ensure parent directory exists
            socket_path.parent.mkdir(parents=True, exist_ok=True)

            # Start server
            self._server = await asyncio.start_unix_server(
                self._handle_client, path=self.socket_path
            )

            self._running = True
            logger.info(f"MCP Socket Server started on {self.socket_path}")

    async def stop(self) -> None:
        """Stop the socket server"""
        self._running = False

        if self._server:
            self._server.close()
            await self._server.wait_closed()

        # Remove socket file (only for Unix mode)
        if not self._use_tcp:
            socket_path = Path(self.socket_path)
            if socket_path.exists():
                socket_path.unlink()

        logger.info("MCP Socket Server stopped")

    async def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        """Handle a client connection from MCP server"""
        peer = writer.get_extra_info("peername")
        logger.debug(f"MCP client connected: {peer}")

        try:
            while self._running:
                # Read request line
                line = await reader.readline()
                if not line:
                    break

                try:
                    request = json.loads(line.decode())
                    logger.debug(f"Received request: {request.get('type')}")

                    # Process request
                    response = await self._process_request(request)

                    # Send response
                    response_json = json.dumps(response) + "\n"
                    writer.write(response_json.encode())
                    await writer.drain()

                    logger.debug(f"Sent response: approved={response.get('approved')}")

                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON from MCP client: {e}")
                    error_response = (
                        json.dumps(
                            {
                                "approved": False,
                                "message": f"Invalid request format: {e}",
                            }
                        )
                        + "\n"
                    )
                    writer.write(error_response.encode())
                    await writer.drain()

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error handling MCP client: {e}", exc_info=True)
        finally:
            writer.close()
            await writer.wait_closed()
            logger.debug(f"MCP client disconnected: {peer}")

    async def _process_request(self, request: dict[str, Any]) -> dict[str, Any]:
        """Process a request from MCP server"""
        request_type = request.get("type")

        # Handle legacy format (approval_request)
        if request_type == "approval_request":
            tool_name = request.get("tool_name", "unknown")
            tool_input = request.get("tool_input", {})
            context = request.get("context", "")

            logger.info(f"Processing approval request for {tool_name}")

            # Use bridge to get approval
            result = await self.bridge.request_approval(
                tool_name=tool_name, tool_input=tool_input, context=context
            )

            return result

        # Handle new tool proxy format (tool_approval_request)
        elif request_type == "tool_approval_request":
            request_id = request.get("request_id", "")
            tool = request.get("tool", "unknown")
            params = request.get("params", {})
            preview = request.get("preview", "")

            # Map tool proxy names to standard names
            tool_name_map = {
                "write": "Write",
                "edit": "Edit",
                "bash": "Bash",
            }
            tool_name = tool_name_map.get(tool, tool.title())

            logger.debug(
                f"Received tool_approval_request for {tool_name}, request_id={request_id}"
            )

            # Use bridge to get approval
            result = await self.bridge.request_approval(
                tool_name=tool_name,
                tool_input=params,
                context=f"Preview:\n{preview}" if preview else "",
            )

            # Return in format expected by tool proxy
            return {
                "approved": result.get("approved", False),
                "request_id": request_id,
                "feedback": result.get("message", ""),
            }

        else:
            logger.warning(f"Unknown request type: {request_type}")
            return {
                "approved": False,
                "message": f"Unknown request type: {request_type}",
            }

    def respond_to_approval(
        self,
        request_id: str,
        approved: bool,
        message: str = "",
        updated_input: Optional[dict[str, Any]] = None,
    ) -> bool:
        """
        Respond to a pending approval request.

        Called by the WebSocket handler when user responds via frontend.
        """
        return self.bridge.respond(request_id, approved, message, updated_input)

    def get_pending_requests(self) -> list[ApprovalRequest]:
        """Get all pending approval requests"""
        return self.bridge.get_pending_requests()


# Global instance for the backend
_socket_server: Optional[MCPSocketServer] = None


def get_socket_server() -> Optional[MCPSocketServer]:
    """Get the global socket server instance"""
    return _socket_server


def create_socket_server(
    socket_path: str = DEFAULT_SOCKET_PATH,
    cwd: str = ".",
    timeout: float = APPROVAL_TIMEOUT,
    auto_approve_safe: bool = False,
) -> MCPSocketServer:
    """Create and set the global socket server instance"""
    global _socket_server
    _socket_server = MCPSocketServer(
        socket_path=socket_path,
        cwd=cwd,
        timeout=timeout,
        auto_approve_safe=auto_approve_safe,
    )
    return _socket_server
