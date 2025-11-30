"""
JSON Stream Parser for Claude Code output

Parses line-by-line JSON from `claude -p --output-format stream-json`
and extracts structured events for UI rendering.
"""

import json
import logging
from typing import Any, Optional, List
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class EventType(str, Enum):
    """Types of events from Claude Code JSON stream"""

    SYSTEM = "system"
    ASSISTANT = "assistant"
    USER = "user"
    RESULT = "result"
    UNKNOWN = "unknown"


class EventSubtype(str, Enum):
    """Subtypes for more specific event classification"""

    INIT = "init"
    TEXT = "text"
    TOOL_USE = "tool_use"
    TOOL_RESULT = "tool_result"
    THINKING = "thinking"
    ERROR = "error"
    UNKNOWN = "unknown"


@dataclass
class ClaudeEvent:
    """Parsed event from Claude Code JSON stream"""

    type: EventType
    subtype: EventSubtype
    content: Any
    raw: dict
    timestamp: Optional[str] = None

    # Additional metadata extracted from the event
    session_id: Optional[str] = None
    model: Optional[str] = None
    tool_name: Optional[str] = None
    tool_id: Optional[str] = None
    usage: Optional[dict] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        return {
            "type": self.type.value,
            "subtype": self.subtype.value,
            "content": self.content,
            "timestamp": self.timestamp,
            "session_id": self.session_id,
            "model": self.model,
            "tool_name": self.tool_name,
            "tool_id": self.tool_id,
            "usage": self.usage,
        }

    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict())


@dataclass
class ContentBlock:
    """A content block from assistant messages"""

    type: str  # "text", "tool_use", "tool_result"
    content: Any
    tool_id: Optional[str] = None
    tool_name: Optional[str] = None
    tool_input: Optional[dict] = None


class JSONStreamParser:
    """
    Parser for Claude Code JSON streaming output

    Handles the line-by-line JSON format:
    - system: init info (session_id, tools, model)
    - assistant: text or tool_use content
    - user: tool_result content
    """

    def __init__(self):
        self.session_id: Optional[str] = None
        self.model: Optional[str] = None
        self.tools: List[str] = []
        self.mcp_servers: List[dict] = []

    def parse_line(self, line: str) -> Optional[ClaudeEvent]:
        """
        Parse a single JSON line from Claude Code output

        Args:
            line: Raw JSON string (single line)

        Returns:
            ClaudeEvent or None if parsing fails
        """
        if not line.strip():
            return None

        try:
            data = json.loads(line)
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse JSON: {e}")
            return ClaudeEvent(
                type=EventType.UNKNOWN,
                subtype=EventSubtype.ERROR,
                content=f"Parse error: {line[:100]}",
                raw={"error": str(e), "line": line},
            )

        event_type = data.get("type", "unknown")

        if event_type == "system":
            return self._parse_system(data)
        elif event_type == "assistant":
            return self._parse_assistant(data)
        elif event_type == "user":
            return self._parse_user(data)
        elif event_type == "result":
            return self._parse_result(data)
        else:
            return ClaudeEvent(
                type=EventType.UNKNOWN,
                subtype=EventSubtype.UNKNOWN,
                content=data,
                raw=data,
            )

    def _parse_system(self, data: dict) -> ClaudeEvent:
        """Parse system events (init, config)"""
        subtype_str = data.get("subtype", "unknown")

        if subtype_str == "init":
            # Extract session info
            self.session_id = data.get("session_id")
            self.model = data.get("model")
            self.tools = data.get("tools", [])
            self.mcp_servers = data.get("mcp_servers", [])

            return ClaudeEvent(
                type=EventType.SYSTEM,
                subtype=EventSubtype.INIT,
                content={
                    "session_id": self.session_id,
                    "model": self.model,
                    "tools": self.tools,
                    "mcp_servers": self.mcp_servers,
                },
                raw=data,
                session_id=self.session_id,
                model=self.model,
            )

        return ClaudeEvent(
            type=EventType.SYSTEM,
            subtype=EventSubtype.UNKNOWN,
            content=data,
            raw=data,
            session_id=self.session_id,
        )

    def _parse_assistant(self, data: dict) -> ClaudeEvent:
        """Parse assistant messages (text, tool_use)"""
        message = data.get("message", {})
        content_blocks = message.get("content", [])
        usage = message.get("usage")

        # Process content blocks
        for block in content_blocks:
            block_type = block.get("type")

            if block_type == "text":
                return ClaudeEvent(
                    type=EventType.ASSISTANT,
                    subtype=EventSubtype.TEXT,
                    content=block.get("text", ""),
                    raw=data,
                    session_id=self.session_id,
                    usage=usage,
                )

            elif block_type == "tool_use":
                return ClaudeEvent(
                    type=EventType.ASSISTANT,
                    subtype=EventSubtype.TOOL_USE,
                    content={
                        "id": block.get("id"),
                        "name": block.get("name"),
                        "input": block.get("input", {}),
                    },
                    raw=data,
                    session_id=self.session_id,
                    tool_id=block.get("id"),
                    tool_name=block.get("name"),
                    usage=usage,
                )

            elif block_type == "thinking":
                return ClaudeEvent(
                    type=EventType.ASSISTANT,
                    subtype=EventSubtype.THINKING,
                    content=block.get("thinking", ""),
                    raw=data,
                    session_id=self.session_id,
                    usage=usage,
                )

        # If no recognized blocks, return raw content
        return ClaudeEvent(
            type=EventType.ASSISTANT,
            subtype=EventSubtype.UNKNOWN,
            content=content_blocks,
            raw=data,
            session_id=self.session_id,
            usage=usage,
        )

    def _parse_user(self, data: dict) -> ClaudeEvent:
        """Parse user messages (tool_result)"""
        message = data.get("message", {})
        content_blocks = message.get("content", [])

        for block in content_blocks:
            if block.get("type") == "tool_result":
                return ClaudeEvent(
                    type=EventType.USER,
                    subtype=EventSubtype.TOOL_RESULT,
                    content={
                        "tool_use_id": block.get("tool_use_id"),
                        "content": block.get("content", ""),
                        "is_error": block.get("is_error", False),
                    },
                    raw=data,
                    session_id=self.session_id,
                    tool_id=block.get("tool_use_id"),
                )

        return ClaudeEvent(
            type=EventType.USER,
            subtype=EventSubtype.UNKNOWN,
            content=content_blocks,
            raw=data,
            session_id=self.session_id,
        )

    def _parse_result(self, data: dict) -> ClaudeEvent:
        """Parse result events (final output)"""
        return ClaudeEvent(
            type=EventType.RESULT,
            subtype=EventSubtype.UNKNOWN,
            content=data.get("result"),
            raw=data,
            session_id=self.session_id,
            usage=data.get("usage"),
        )

    def get_session_info(self) -> dict:
        """Get current session information"""
        return {
            "session_id": self.session_id,
            "model": self.model,
            "tools": self.tools,
            "mcp_servers": self.mcp_servers,
        }

    def reset(self) -> None:
        """Reset parser state for new session"""
        self.session_id = None
        self.model = None
        self.tools = []
        self.mcp_servers = []
