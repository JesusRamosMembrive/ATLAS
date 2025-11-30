# SPDX-License-Identifier: MIT
"""
Agent Handlers Module

Provides handler classes for different Claude agent execution modes:
- SDKModeHandler: Direct Anthropic SDK with tool interception
- MCPProxyModeHandler: Claude CLI with MCP tool proxy for approval
- CLIModeHandler: Standard Claude CLI subprocess with various permission modes
"""

from .base import BaseAgentHandler
from .sdk_handler import SDKModeHandler
from .mcp_proxy_handler import MCPProxyModeHandler
from .cli_handler import CLIModeHandler
from .factory import create_handler

__all__ = [
    "BaseAgentHandler",
    "SDKModeHandler",
    "MCPProxyModeHandler",
    "CLIModeHandler",
    "create_handler",
]
