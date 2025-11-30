"""
Terminal module for web-based shell access

Provides:
- PTY-based shell execution accessible via WebSocket
- Claude Code JSON streaming runner
- Codex CLI JSON streaming runner
- JSON event parser for Claude Code output
- PTY-based Claude runner with output parsing
"""

from .pty_shell import PTYShell
from .claude_runner import ClaudeAgentRunner, ClaudeRunnerConfig
from .codex_runner import CodexAgentRunner, CodexRunnerConfig
from .json_parser import JSONStreamParser, ClaudeEvent, EventType, EventSubtype
from .pty_parser import PTYParser, EventAggregator, ParsedEvent
from .pty_parser import EventType as PTYEventType
from .pty_runner import PTYClaudeRunner, PTYRunnerConfig, create_pty_runner

__all__ = [
    "PTYShell",
    # Claude runner
    "ClaudeAgentRunner",
    "ClaudeRunnerConfig",
    # Codex runner
    "CodexAgentRunner",
    "CodexRunnerConfig",
    # JSON parsing
    "JSONStreamParser",
    "ClaudeEvent",
    "EventType",
    "EventSubtype",
    # PTY-based runner
    "PTYParser",
    "EventAggregator",
    "ParsedEvent",
    "PTYEventType",
    "PTYClaudeRunner",
    "PTYRunnerConfig",
    "create_pty_runner",
]
