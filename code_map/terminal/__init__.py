"""
Terminal module for web-based shell access

Provides:
- PTY-based shell execution accessible via Socket.IO
  - Unix: Uses native pty module
  - Windows: Uses pywinpty (ConPTY wrapper) or subprocess fallback
- Socket.IO PTY server for real-time terminal communication
"""

import sys

# Cross-platform imports
from .json_parser import JSONStreamParser, ClaudeEvent, EventType, EventSubtype
from .pty_parser import PTYParser, EventAggregator, ParsedEvent
from .pty_parser import EventType as PTYEventType
from .socketio_pty import get_pty_server, create_combined_app

# Platform detection
_IS_WINDOWS = sys.platform == "win32"

# Shell class - platform-specific
if _IS_WINDOWS:
    # Windows: Try pywinpty, fall back to subprocess
    try:
        from .winpty_shell import WinPTYShell, WINPTY_AVAILABLE, SubprocessShell

        if WINPTY_AVAILABLE:
            PTYShell = WinPTYShell
            _PTY_AVAILABLE = True
        else:
            # Fall back to subprocess-based shell
            PTYShell = SubprocessShell  # type: ignore
            _PTY_AVAILABLE = True  # Subprocess always works (limited features)
    except ImportError:
        _PTY_AVAILABLE = False
        PTYShell = None  # type: ignore

    # PTY runner not available on Windows (uses pexpect)
    PTYClaudeRunner = None  # type: ignore
    PTYRunnerConfig = None  # type: ignore
    create_pty_runner = None  # type: ignore
else:
    # Unix: Use native pty
    try:
        from .pty_shell import PTYShell
        from .pty_runner import PTYClaudeRunner, PTYRunnerConfig, create_pty_runner
        _PTY_AVAILABLE = True
    except ImportError:
        _PTY_AVAILABLE = False
        PTYShell = None  # type: ignore
        PTYClaudeRunner = None  # type: ignore
        PTYRunnerConfig = None  # type: ignore
        create_pty_runner = None  # type: ignore

__all__ = [
    # Platform detection
    "_IS_WINDOWS",
    "_PTY_AVAILABLE",
    # PTY Shell (cross-platform with platform-specific implementation)
    "PTYShell",
    # Socket.IO PTY server
    "get_pty_server",
    "create_combined_app",
    # JSON parsing (cross-platform)
    "JSONStreamParser",
    "ClaudeEvent",
    "EventType",
    "EventSubtype",
    # PTY-based runner (Unix only)
    "PTYParser",
    "EventAggregator",
    "ParsedEvent",
    "PTYEventType",
    "PTYClaudeRunner",
    "PTYRunnerConfig",
    "create_pty_runner",
]
