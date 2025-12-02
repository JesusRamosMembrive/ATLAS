# SPDX-License-Identifier: MIT
"""
MCP Constants - Shared constants for MCP tool approval system.

Centralizes configuration values used across multiple MCP modules
to eliminate duplication and ensure consistency.
"""

import sys
import os

# ============================================================================
# Platform Detection
# ============================================================================

IS_WINDOWS = sys.platform == "win32"

# ============================================================================
# Socket Paths
# ============================================================================

# Primary socket path for tool approval communication
# On Windows, Unix sockets are not available, so we use a named pipe path
# or fall back to TCP localhost
if IS_WINDOWS:
    # Windows: Use temp directory with a named pipe-style path
    # Note: Windows Named Pipes use \\.\pipe\name format
    # For asyncio compatibility, we'll use TCP localhost instead
    DEFAULT_SOCKET_PATH = "tcp://127.0.0.1:18010"
    DEFAULT_SOCKET_HOST = "127.0.0.1"
    DEFAULT_SOCKET_PORT = 18010
else:
    # Unix: Use Unix socket
    DEFAULT_SOCKET_PATH = "/tmp/aegis_tool_approval.sock"
    DEFAULT_SOCKET_HOST = None
    DEFAULT_SOCKET_PORT = None

# Environment variable names for socket configuration
ENV_TOOL_SOCKET = "AEGIS_TOOL_SOCKET"
ENV_MCP_SOCKET = "AEGIS_MCP_SOCKET"
ENV_CWD = "AEGIS_CWD"

# ============================================================================
# Timeouts (seconds unless otherwise noted)
# ============================================================================

# User approval timeout - how long to wait for user response
APPROVAL_TIMEOUT = 7200.0  # 2 hours

# Process cancellation timeout
CANCEL_TIMEOUT = 2.0

# Default command execution timeout (milliseconds)
COMMAND_TIMEOUT_MS = 120000  # 2 minutes

# ============================================================================
# Preview Limits
# ============================================================================

# Maximum lines to show in file preview
PREVIEW_LINE_LIMIT = 50

# Maximum characters for string previews (old_string, new_string)
PREVIEW_CHAR_LIMIT = 200

# Maximum characters for JSON input summary
SUMMARY_CHAR_LIMIT = 500

# Maximum line length before truncation
FILE_LINE_CHAR_LIMIT = 2000

# ============================================================================
# Tool Categories
# ============================================================================

# Tools that modify files (require approval in safe modes)
FILE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}

# Tools that execute commands (require approval in safe modes)
COMMAND_TOOLS = {"Bash"}

# Tools that are generally safe (read-only operations)
SAFE_TOOLS = {"Read", "Glob", "Grep", "TodoWrite", "WebFetch", "WebSearch", "Task"}

# All tools that require approval
DANGEROUS_TOOLS = FILE_TOOLS | COMMAND_TOOLS
