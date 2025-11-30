"""
Agent Output Parser for Terminal

Detects and extracts structured information from agent terminal output,
including commands, file operations, test results, and agent reasoning blocks.
"""

import re
import json
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum


class AgentEventType(Enum):
    """Types of events that can be detected in agent output"""

    # Command events
    COMMAND_START = "command_start"
    COMMAND_END = "command_end"
    COMMAND_OUTPUT = "command_output"

    # File events
    FILE_READ = "file_read"
    FILE_WRITE = "file_write"
    FILE_DELETE = "file_delete"
    FILE_DIFF = "file_diff"

    # Test events
    TEST_START = "test_start"
    TEST_RESULT = "test_result"
    TEST_SUMMARY = "test_summary"

    # Build/Install events
    INSTALL_START = "install_start"
    INSTALL_PROGRESS = "install_progress"
    INSTALL_END = "install_end"
    BUILD_START = "build_start"
    BUILD_END = "build_end"

    # Agent reasoning
    AGENT_THINKING = "agent_thinking"
    AGENT_PLANNING = "agent_planning"
    AGENT_DECISION = "agent_decision"
    AGENT_ERROR = "agent_error"

    # Git events
    GIT_STATUS = "git_status"
    GIT_DIFF = "git_diff"
    GIT_COMMIT = "git_commit"

    # General
    # General
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    PROMPT = "prompt"

    # Claude Code specific
    CLAUDE_RESPONSE = "claude_response"
    CLAUDE_TOOL_USE = "claude_tool_use"
    CLAUDE_THINKING = "claude_thinking"


@dataclass
class AgentEvent:
    """Structured agent event extracted from terminal output"""

    type: AgentEventType
    timestamp: str
    data: Dict[str, Any]
    raw_text: str
    line_number: Optional[int] = None
    confidence: float = 1.0

    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization"""
        result = asdict(self)
        result["type"] = self.type.value
        return result

    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict())


class AgentOutputParser:
    """Parser for detecting patterns in agent terminal output"""

    def __init__(self):
        """Initialize parser with pattern definitions"""

        # Command patterns
        self.command_patterns = {
            # Package managers
            r"^(npm|yarn|pnpm)\s+(install|i|add|remove|uninstall)": {
                "type": AgentEventType.INSTALL_START,
                "tool": "npm",
                "extract": self._extract_npm_command,
            },
            r"^(pip|pip3|pipenv|poetry)\s+(install|uninstall)": {
                "type": AgentEventType.INSTALL_START,
                "tool": "pip",
                "extract": self._extract_pip_command,
            },
            # Testing
            r"^(pytest|python -m pytest|py\.test)": {
                "type": AgentEventType.TEST_START,
                "tool": "pytest",
                "extract": self._extract_pytest_command,
            },
            r"^(npm|yarn|pnpm)\s+(test|run test)": {
                "type": AgentEventType.TEST_START,
                "tool": "jest",
                "extract": self._extract_npm_test,
            },
            # Git operations
            r"^git\s+status": {
                "type": AgentEventType.GIT_STATUS,
                "extract": self._extract_git_status,
            },
            r"^git\s+diff": {
                "type": AgentEventType.GIT_DIFF,
                "extract": self._extract_git_diff,
            },
            r"^git\s+(add|commit|push|pull)": {
                "type": AgentEventType.COMMAND_START,
                "tool": "git",
                "extract": self._extract_git_command,
            },
            # File operations
            r"^(cat|head|tail|less|more)\s+": {
                "type": AgentEventType.FILE_READ,
                "extract": self._extract_file_read,
            },
            r"^(echo|printf).+>\s*\S+": {
                "type": AgentEventType.FILE_WRITE,
                "extract": self._extract_file_write,
            },
            r"^rm\s+(-[rf]+\s+)?": {
                "type": AgentEventType.FILE_DELETE,
                "extract": self._extract_file_delete,
            },
            # Build commands
            r"^(make|cmake|cargo build|go build)": {
                "type": AgentEventType.BUILD_START,
                "extract": self._extract_build_command,
            },
        }

        # Test result patterns
        self.test_patterns = {
            # Pytest
            r"^=+\s*(\d+)\s+passed.*in\s+([\d.]+)s": self._parse_pytest_summary,
            r"^FAILED\s+(\S+)::(\S+)": self._parse_pytest_failure,
            # Jest/Mocha
            r"✓\s+(.+)\s+\((\d+)ms\)": self._parse_jest_pass,
            r"✕\s+(.+)\s+\((\d+)ms\)": self._parse_jest_fail,
            r"Tests:\s+(\d+)\s+passed,\s+(\d+)\s+total": self._parse_jest_summary,
        }

        # Agent thinking patterns
        self.agent_patterns = {
            r"^(Thinking|Planning|Analyzing|Considering)[:.]": AgentEventType.AGENT_THINKING,
            r"^(I will|I\'ll|Let me|Going to|Need to)": AgentEventType.AGENT_PLANNING,
            r"^(Decided to|Choosing|Selected|Using)": AgentEventType.AGENT_DECISION,
            r"^(Error|Failed|Cannot|Unable to)": AgentEventType.AGENT_ERROR,
        }

        # Error patterns
        self.error_patterns = {
            r"^(ERROR|ERRO|ERR)[:|\s]": AgentEventType.ERROR,
            r"^(WARNING|WARN)[:|\s]": AgentEventType.WARNING,
            r"^(INFO|DEBU|DEBUG)[:|\s]": AgentEventType.INFO,
            r"Traceback \(most recent call last\)": AgentEventType.ERROR,
            r"SyntaxError:|TypeError:|ValueError:|AttributeError:": AgentEventType.ERROR,
        }

        # Prompt patterns
        self.prompt_patterns = {
            r"\[Y/n\]": "yes_no",
            r"\(y/N\)": "yes_no",
            r"Continue\?": "continue",
            r"Enter (.+):": "input",
            r"Choose \[(\d+-\d+)\]": "choice",
        }

        # Claude Code specific patterns
        self.claude_patterns = {
            r"^Thinking\s+(off|on)": AgentEventType.CLAUDE_THINKING,
            r'^>\s+Try\s+"': AgentEventType.CLAUDE_TOOL_USE,  # Suggestion/Tool use
            r"^>\s+": AgentEventType.CLAUDE_TOOL_USE,  # General command execution
            r"^\s*─────": AgentEventType.CLAUDE_THINKING,  # Separator lines -> treat as thinking/TUI
            r"^\s*\? for shortcuts": AgentEventType.CLAUDE_THINKING,  # Footer help
            r"^\s*ctrl-g to edit": AgentEventType.CLAUDE_THINKING,  # Footer help
        }

        # State tracking
        self.current_command = None
        self.line_buffer = []
        self.line_number = 0

    def parse_line(self, line: str) -> Optional[List[AgentEvent]]:
        """
        Parse a single line of terminal output

        Args:
            line: Raw line from terminal

        Returns:
            List of detected events, or None if no events detected
        """
        self.line_number += 1
        events = []

        # Clean ANSI escape codes for pattern matching
        clean_line = self._strip_ansi(line)

        # Track if we've already matched to avoid duplicates
        pattern_matched = False

        # Check for command patterns (highest priority)
        if not pattern_matched:
            for pattern, config in self.command_patterns.items():
                if re.match(pattern, clean_line):
                    event = self._create_event(
                        event_type=config["type"],
                        line=line,
                        clean_line=clean_line,
                        extractor=config.get("extract"),
                    )
                    if event:
                        events.append(event)
                        self.current_command = clean_line
                    pattern_matched = True
                    break

        # Check for Claude Code patterns (high priority)
        if not pattern_matched:
            for pattern, event_type in self.claude_patterns.items():
                if re.search(pattern, clean_line):
                    events.append(
                        self._create_event(
                            event_type=event_type, line=line, clean_line=clean_line
                        )
                    )
                    pattern_matched = True
                    break

        # Check for test results
        if not pattern_matched:
            for pattern, parser in self.test_patterns.items():
                match = re.search(pattern, clean_line)
                if match:
                    event = parser(match, line)
                    if event:
                        events.append(event)
                        pattern_matched = True
                        break

        # Check for agent thinking (check before errors to avoid overlap)
        if not pattern_matched:
            for pattern, event_type in self.agent_patterns.items():
                if re.match(pattern, clean_line, re.IGNORECASE):
                    events.append(
                        self._create_event(
                            event_type=event_type, line=line, clean_line=clean_line
                        )
                    )
                    pattern_matched = True
                    break

        # Check for errors (lower priority to avoid conflicts)
        if not pattern_matched:
            for pattern, event_type in self.error_patterns.items():
                if re.search(pattern, clean_line):
                    events.append(
                        self._create_event(
                            event_type=event_type, line=line, clean_line=clean_line
                        )
                    )
                    pattern_matched = True
                    break

        # Check for prompts (lowest priority)
        if not pattern_matched:
            for pattern, prompt_type in self.prompt_patterns.items():
                if re.search(pattern, clean_line):
                    events.append(
                        AgentEvent(
                            type=AgentEventType.PROMPT,
                            timestamp=datetime.now().isoformat(),
                            data={"prompt_type": prompt_type, "text": clean_line},
                            raw_text=line,
                            line_number=self.line_number,
                        )
                    )
                    pattern_matched = True
                    break

        return events if events else None

    def parse_chunk(self, text: str) -> List[AgentEvent]:
        """
        Parse a chunk of terminal output

        Args:
            text: Multi-line terminal output

        Returns:
            List of all detected events
        """
        all_events = []

        for line in text.split("\n"):
            if line.strip():
                events = self.parse_line(line)
                if events:
                    all_events.extend(events)

        return all_events

    def _create_event(
        self,
        event_type: AgentEventType,
        line: str,
        clean_line: str,
        extractor: Optional[Callable[[str], Optional[Dict[str, Any]]]] = None,
    ) -> AgentEvent:
        """Create an event from parsed data"""

        data = {"command": clean_line}

        if extractor:
            extracted = extractor(clean_line)
            if extracted:
                data.update(extracted)

        return AgentEvent(
            type=event_type,
            timestamp=datetime.now().isoformat(),
            data=data,
            raw_text=line,
            line_number=self.line_number,
        )

    def _strip_ansi(self, text: str) -> str:
        """Remove ANSI escape codes from text"""
        ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
        return ansi_escape.sub("", text)

    # Extractors for specific command types

    def _extract_npm_command(self, line: str) -> Dict:
        """Extract details from npm commands"""
        parts = line.split()
        return {
            "tool": parts[0],
            "action": parts[1] if len(parts) > 1 else None,
            "packages": parts[2:] if len(parts) > 2 else [],
        }

    def _extract_pip_command(self, line: str) -> Dict:
        """Extract details from pip commands"""
        parts = line.split()
        return {
            "tool": parts[0],
            "action": parts[1] if len(parts) > 1 else None,
            "packages": parts[2:] if len(parts) > 2 else [],
        }

    def _extract_pytest_command(self, line: str) -> Dict:
        """Extract pytest command details"""
        return {"tool": "pytest", "arguments": line.replace("pytest", "").strip()}

    def _extract_npm_test(self, line: str) -> Dict:
        """Extract npm test command details"""
        parts = line.split()
        return {"tool": parts[0], "script": "test"}

    def _extract_git_status(self, line: str) -> Dict:
        """Extract git status command"""
        return {"tool": "git", "subcommand": "status"}

    def _extract_git_diff(self, line: str) -> Dict:
        """Extract git diff command"""
        return {"tool": "git", "subcommand": "diff"}

    def _extract_git_command(self, line: str) -> Dict:
        """Extract git command details"""
        parts = line.split()
        return {
            "tool": "git",
            "subcommand": parts[1] if len(parts) > 1 else None,
            "arguments": " ".join(parts[2:]) if len(parts) > 2 else None,
        }

    def _extract_file_read(self, line: str) -> Dict:
        """Extract file read operation"""
        parts = line.split()
        return {"command": parts[0], "file": parts[1] if len(parts) > 1 else None}

    def _extract_file_write(self, line: str) -> Dict:
        """Extract file write operation"""
        match = re.search(r">\s*(\S+)", line)
        return {"file": match.group(1) if match else None, "operation": "write"}

    def _extract_file_delete(self, line: str) -> Dict:
        """Extract file delete operation"""
        parts = line.split()
        files = [p for p in parts[1:] if not p.startswith("-")]
        return {"command": "rm", "files": files}

    def _extract_build_command(self, line: str) -> Dict:
        """Extract build command details"""
        parts = line.split()
        return {
            "tool": parts[0],
            "arguments": " ".join(parts[1:]) if len(parts) > 1 else None,
        }

    # Test result parsers

    def _parse_pytest_summary(self, match: re.Match, line: str) -> AgentEvent:
        """Parse pytest summary line"""
        return AgentEvent(
            type=AgentEventType.TEST_SUMMARY,
            timestamp=datetime.now().isoformat(),
            data={
                "tool": "pytest",
                "passed": int(match.group(1)),
                "duration": float(match.group(2)),
            },
            raw_text=line,
            line_number=self.line_number,
        )

    def _parse_pytest_failure(self, match: re.Match, line: str) -> AgentEvent:
        """Parse pytest failure"""
        return AgentEvent(
            type=AgentEventType.TEST_RESULT,
            timestamp=datetime.now().isoformat(),
            data={
                "tool": "pytest",
                "status": "failed",
                "file": match.group(1),
                "test": match.group(2),
            },
            raw_text=line,
            line_number=self.line_number,
        )

    def _parse_jest_pass(self, match: re.Match, line: str) -> AgentEvent:
        """Parse Jest passing test"""
        return AgentEvent(
            type=AgentEventType.TEST_RESULT,
            timestamp=datetime.now().isoformat(),
            data={
                "tool": "jest",
                "status": "passed",
                "test": match.group(1),
                "duration": int(match.group(2)),
            },
            raw_text=line,
            line_number=self.line_number,
        )

    def _parse_jest_fail(self, match: re.Match, line: str) -> AgentEvent:
        """Parse Jest failing test"""
        return AgentEvent(
            type=AgentEventType.TEST_RESULT,
            timestamp=datetime.now().isoformat(),
            data={
                "tool": "jest",
                "status": "failed",
                "test": match.group(1),
                "duration": int(match.group(2)),
            },
            raw_text=line,
            line_number=self.line_number,
        )

    def _parse_jest_summary(self, match: re.Match, line: str) -> AgentEvent:
        """Parse Jest test summary"""
        return AgentEvent(
            type=AgentEventType.TEST_SUMMARY,
            timestamp=datetime.now().isoformat(),
            data={
                "tool": "jest",
                "passed": int(match.group(1)),
                "total": int(match.group(2)),
            },
            raw_text=line,
            line_number=self.line_number,
        )
