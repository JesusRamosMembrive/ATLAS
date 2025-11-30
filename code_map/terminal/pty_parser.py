#!/usr/bin/env python3
"""
PTY Output Parser for Claude Code.

This module provides parsing and filtering of Claude Code's terminal output
to extract meaningful events and package them as structured JSON.

The parser handles:
- ANSI escape code stripping
- Ink refresh pattern filtering (aggressive screen updates)
- Event extraction (thinking, tool calls, completions, errors)
- Permission prompt detection
- Progress indicator extraction
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class EventType(Enum):
    """Types of events that can be extracted from Claude Code output."""

    INITIALIZING = "initializing"
    THINKING = "thinking"  # Claude is processing
    TOOL_START = "tool_start"  # Tool execution begins
    TOOL_RESULT = "tool_result"  # Tool execution result
    PERMISSION_REQUEST = "permission_request"  # Needs user approval
    MESSAGE = "message"  # Claude's response text
    COMPLETION = "completion"  # Task completed
    ERROR = "error"  # Error occurred
    STATUS = "status"  # Status update (MCP, etc.)
    PROMPT_READY = "prompt_ready"  # Ready for new input


@dataclass
class ParsedEvent:
    """A parsed event from Claude Code output."""

    type: EventType
    timestamp: datetime
    data: dict[str, Any] = field(default_factory=dict)
    raw_text: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        return {
            "type": self.type.value,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
            "raw_text": self.raw_text[:500] if self.raw_text else "",
        }


class PTYParser:
    """
    Parser for Claude Code PTY output.

    Extracts structured events from the raw terminal output, filtering out
    Ink's aggressive refresh patterns and ANSI escape codes.
    """

    # ANSI escape code pattern
    ANSI_PATTERN = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

    # Thinking/processing indicators
    THINKING_INDICATORS = [
        r"[✽✶●✢·◦◉○].*?(?:Osmosing|Ideating|Tinkering|Waddling|Nucleating|"
        r"Mulling|Thinking|Pondering|Processing|Orchestrating|Considering)…",
        r"\(esc to interrupt\)",
    ]

    # Permission request patterns
    PERMISSION_PATTERNS = [
        (r"Allow\s+Write\s+to\s+(.+)", "write"),
        (r"Allow\s+Edit\s+(?:in\s+)?(.+)", "edit"),
        (r"Allow\s+Bash:\s*(.+)", "bash"),
        (r"Allow\s+Read\s+from\s+(.+)", "read"),
        (r"Press\s+.*?to\s+allow", "generic"),
        (r"\[y/n\]", "confirm"),
        (r"Allow\s+once", "allow_once"),
        (r"Always\s+allow", "always_allow"),
        (r"Deny", "deny"),
    ]

    # Tool execution patterns
    TOOL_PATTERNS = [
        (r"●\s*(?:Done|Completed)[.:]?\s*(.*)", "completion"),
        (r"✓\s*(.+)", "success"),
        (r"✗\s*(.+)", "failure"),
        (r"Writing\s+to\s+(.+)", "write"),
        (r"Reading\s+(.+)", "read"),
        (r"Running\s+(.+)", "bash"),
        (r"Editing\s+(.+)", "edit"),
    ]

    # Error patterns
    ERROR_PATTERNS = [
        r"ERROR[:\s]+(.+)",
        r"Error[:\s]+(.+)",
        r"Failed[:\s]+(.+)",
        r"\d+\s+MCP\s+server[s]?\s+failed",
    ]

    # Noise patterns to filter out
    NOISE_PATTERNS = [
        r"^─+$",  # Separator lines
        r"^\s*$",  # Empty lines
        r"^\?\s+for\s+shortcuts",  # UI hints
        r"^\s*\d+\s*$",  # Lone numbers (token counts)
        r"Opus 4\.5\s+ATLAS",  # Header info
    ]

    def __init__(self):
        """Initialize the parser."""
        self._buffer = ""
        self._last_event_type: Optional[EventType] = None
        self._thinking_detected = False

        # Compile patterns
        self._thinking_re = [re.compile(p) for p in self.THINKING_INDICATORS]
        self._permission_re = [(re.compile(p), t) for p, t in self.PERMISSION_PATTERNS]
        self._tool_re = [(re.compile(p), t) for p, t in self.TOOL_PATTERNS]
        self._error_re = [re.compile(p) for p in self.ERROR_PATTERNS]
        self._noise_re = [re.compile(p) for p in self.NOISE_PATTERNS]

    def strip_ansi(self, text: str) -> str:
        """Remove ANSI escape codes from text."""
        return self.ANSI_PATTERN.sub("", text)

    def is_noise(self, line: str) -> bool:
        """Check if a line is noise that should be filtered out."""
        clean = line.strip()
        for pattern in self._noise_re:
            if pattern.match(clean):
                return True
        return False

    def parse_chunk(self, raw_chunk: str) -> list[ParsedEvent]:
        """
        Parse a chunk of raw PTY output.

        Args:
            raw_chunk: Raw bytes/text from PTY

        Returns:
            List of parsed events
        """
        # Strip ANSI codes
        clean = self.strip_ansi(raw_chunk)

        # Add to buffer and process lines
        self._buffer += clean
        events = []

        # Process complete lines
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            line_events = self._parse_line(line)
            events.extend(line_events)

        return events

    def _parse_line(self, line: str) -> list[ParsedEvent]:
        """Parse a single line of output."""
        events: list[ParsedEvent] = []
        clean = line.strip()

        if not clean or self.is_noise(line):
            return events

        now = datetime.now()

        # Check for thinking indicators
        for pattern in self._thinking_re:
            if pattern.search(clean):
                if not self._thinking_detected:
                    self._thinking_detected = True
                    events.append(
                        ParsedEvent(
                            type=EventType.THINKING,
                            timestamp=now,
                            data={"indicator": clean[:50]},
                            raw_text=clean,
                        )
                    )
                return events

        # Check for permission requests
        for pattern, perm_type in self._permission_re:
            match = pattern.search(clean)
            if match:
                events.append(
                    ParsedEvent(
                        type=EventType.PERMISSION_REQUEST,
                        timestamp=now,
                        data={
                            "permission_type": perm_type,
                            "target": match.group(1) if match.lastindex else None,
                            "full_text": clean,
                        },
                        raw_text=clean,
                    )
                )
                return events

        # Check for tool execution
        for pattern, tool_type in self._tool_re:
            match = pattern.search(clean)
            if match:
                event_type = (
                    EventType.COMPLETION
                    if tool_type == "completion"
                    else EventType.TOOL_RESULT
                )
                events.append(
                    ParsedEvent(
                        type=event_type,
                        timestamp=now,
                        data={
                            "tool_type": tool_type,
                            "message": match.group(1) if match.lastindex else clean,
                        },
                        raw_text=clean,
                    )
                )
                self._thinking_detected = False  # Reset thinking state
                return events

        # Check for errors
        for pattern in self._error_re:
            match = pattern.search(clean)
            if match:
                events.append(
                    ParsedEvent(
                        type=EventType.ERROR,
                        timestamp=now,
                        data={
                            "message": match.group(1) if match.lastindex else clean,
                        },
                        raw_text=clean,
                    )
                )
                return events

        # Check for prompt ready (back to input mode)
        # Must be just ">" or "> " not followed by actual content (like echoed prompt)
        if re.match(r"^>\s*$", clean):
            events.append(
                ParsedEvent(
                    type=EventType.PROMPT_READY,
                    timestamp=now,
                    data={},
                    raw_text=clean,
                )
            )
            self._thinking_detected = False
            return events

        # Generic message if we have content
        if len(clean) > 5 and not self.is_noise(clean):
            events.append(
                ParsedEvent(
                    type=EventType.MESSAGE,
                    timestamp=now,
                    data={"content": clean},
                    raw_text=clean,
                )
            )

        return events

    def reset(self):
        """Reset parser state for new session."""
        self._buffer = ""
        self._last_event_type = None
        self._thinking_detected = False


class EventAggregator:
    """
    Aggregates parsed events into higher-level structures.

    Combines related events (like multiple thinking indicators) and
    deduplicates repeated events from Ink's refresh patterns.
    """

    def __init__(self):
        """Initialize the aggregator."""
        self._recent_events: list[ParsedEvent] = []
        self._max_recent = 50

    def add_events(self, events: list[ParsedEvent]) -> list[ParsedEvent]:
        """
        Add events and return deduplicated/aggregated results.

        Args:
            events: New events to process

        Returns:
            Filtered and aggregated events suitable for emitting
        """
        result = []

        for event in events:
            # Skip duplicate thinking events
            if event.type == EventType.THINKING:
                if self._has_recent_thinking():
                    continue

            # Skip duplicate permission events
            if event.type == EventType.PERMISSION_REQUEST:
                if self._has_recent_permission(event.data.get("full_text", "")):
                    continue

            result.append(event)
            self._recent_events.append(event)

        # Trim recent events list
        if len(self._recent_events) > self._max_recent:
            self._recent_events = self._recent_events[-self._max_recent :]

        return result

    def _has_recent_thinking(self) -> bool:
        """Check if we have a recent thinking event."""
        for event in reversed(self._recent_events[-5:]):
            if event.type == EventType.THINKING:
                return True
            if event.type in (EventType.COMPLETION, EventType.PROMPT_READY):
                return False
        return False

    def _has_recent_permission(self, text: str) -> bool:
        """Check if we have a recent identical permission event."""
        for event in reversed(self._recent_events[-3:]):
            if event.type == EventType.PERMISSION_REQUEST:
                if event.data.get("full_text") == text:
                    return True
        return False

    def reset(self):
        """Reset aggregator state."""
        self._recent_events.clear()


# Convenience function for simple usage
def parse_pty_output(raw_output: str) -> list[dict[str, Any]]:
    """
    Parse raw PTY output into a list of event dictionaries.

    Args:
        raw_output: Raw PTY output with ANSI codes

    Returns:
        List of event dictionaries ready for JSON serialization
    """
    parser = PTYParser()
    aggregator = EventAggregator()

    events = parser.parse_chunk(raw_output)
    filtered = aggregator.add_events(events)

    return [e.to_dict() for e in filtered]
