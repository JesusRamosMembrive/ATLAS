"""
Terminal module for web-based shell access

Provides PTY-based shell execution accessible via WebSocket
"""

from .pty_shell import PTYShell

__all__ = ["PTYShell"]
