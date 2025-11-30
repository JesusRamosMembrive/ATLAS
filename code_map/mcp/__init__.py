# SPDX-License-Identifier: MIT
"""
MCP (Model Context Protocol) module for ATLAS.

Provides MCP server implementation for tool approval workflow
with Claude Code's --permission-prompt-tool feature.
"""

from .permission_server import PermissionServer
from .approval_bridge import ApprovalBridge, ApprovalRequest

__all__ = ["PermissionServer", "ApprovalBridge", "ApprovalRequest"]
