"""
Terminal module for web-based shell access

Provides:
- PTY-based shell execution accessible via WebSocket
  - Unix: Uses native pty module
  - Windows: Uses pywinpty (ConPTY wrapper) or subprocess fallback
- Claude Code JSON streaming runner (cross-platform)
- Codex CLI JSON streaming runner (cross-platform)
- JSON event parser for Claude Code output
- PTY-based Claude runner with output parsing (Unix only)
"""

import sys

# Cross-platform imports (always available)
from .claude_runner import ClaudeAgentRunner, ClaudeRunnerConfig
from .codex_runner import CodexAgentRunner, CodexRunnerConfig
from .json_parser import JSONStreamParser, ClaudeEvent, EventType, EventSubtype
from .pty_parser import PTYParser, EventAggregator, ParsedEvent
from .pty_parser import EventType as PTYEventType

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
    # Claude runner (cross-platform)
    "ClaudeAgentRunner",
    "ClaudeRunnerConfig",
    # Codex runner (cross-platform)
    "CodexAgentRunner",
    "CodexRunnerConfig",
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
