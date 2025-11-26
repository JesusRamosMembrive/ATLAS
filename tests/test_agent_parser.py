"""
Tests for Agent Output Parser

Verifies pattern detection and event extraction from terminal output.
"""

import pytest
from datetime import datetime
from code_map.terminal.agent_parser import AgentOutputParser, AgentEvent, AgentEventType


class TestAgentOutputParser:
    """Test agent output parser functionality"""

    def setup_method(self):
        """Set up test parser"""
        self.parser = AgentOutputParser()

    def test_command_detection(self):
        """Test detection of command execution"""
        # Test npm install
        events = self.parser.parse_line("npm install express")
        assert events is not None
        assert len(events) == 1
        assert events[0].type == AgentEventType.INSTALL_START
        assert events[0].data["tool"] == "npm"
        assert "express" in events[0].data["packages"]

        # Test pip install
        events = self.parser.parse_line("pip install requests numpy")
        assert events is not None
        assert len(events) == 1
        assert events[0].type == AgentEventType.INSTALL_START
        assert events[0].data["tool"] == "pip"
        assert "requests" in events[0].data["packages"]
        assert "numpy" in events[0].data["packages"]

        # Test git status
        events = self.parser.parse_line("git status")
        assert events is not None
        assert len(events) == 1
        assert events[0].type == AgentEventType.GIT_STATUS

    def test_test_result_detection(self):
        """Test detection of test results"""
        # Pytest summary
        events = self.parser.parse_line("======== 45 passed in 12.34s ========")
        assert events is not None
        assert len(events) == 1
        assert events[0].type == AgentEventType.TEST_SUMMARY
        assert events[0].data["tool"] == "pytest"
        assert events[0].data["passed"] == 45
        assert events[0].data["duration"] == 12.34

        # Pytest failure - will be detected as TEST_RESULT, not AGENT_ERROR
        events = self.parser.parse_line("FAILED tests/test_example.py::test_function")
        assert events is not None
        assert len(events) == 1
        assert events[0].type == AgentEventType.TEST_RESULT
        assert events[0].data["status"] == "failed"
        assert events[0].data["file"] == "tests/test_example.py"
        assert events[0].data["test"] == "test_function"

        # Jest pass
        events = self.parser.parse_line("✓ should handle async operations (123ms)")
        assert events is not None
        assert len(events) == 1
        assert events[0].type == AgentEventType.TEST_RESULT
        assert events[0].data["status"] == "passed"
        assert events[0].data["tool"] == "jest"
        assert events[0].data["duration"] == 123

        # Jest summary
        events = self.parser.parse_line("Tests: 10 passed, 10 total")
        assert events is not None
        assert len(events) == 1
        assert events[0].type == AgentEventType.TEST_SUMMARY
        assert events[0].data["passed"] == 10
        assert events[0].data["total"] == 10

    def test_agent_reasoning_detection(self):
        """Test detection of agent thinking patterns"""
        # Thinking
        events = self.parser.parse_line("Thinking: I need to analyze this code")
        assert events is not None
        assert len(events) == 1
        assert events[0].type == AgentEventType.AGENT_THINKING

        # Planning
        events = self.parser.parse_line("I will first check the dependencies")
        assert events is not None
        assert len(events) == 1
        assert events[0].type == AgentEventType.AGENT_PLANNING

        # Decision
        events = self.parser.parse_line("Decided to use async approach")
        assert events is not None
        assert len(events) == 1
        assert events[0].type == AgentEventType.AGENT_DECISION

    def test_error_detection(self):
        """Test detection of errors and warnings"""
        # Error with label - will be detected as AGENT_ERROR due to pattern priority
        events = self.parser.parse_line("ERROR: Failed to connect to database")
        assert events is not None
        assert len(events) == 1
        # Agent patterns have higher priority than generic error patterns
        assert events[0].type in [AgentEventType.ERROR, AgentEventType.AGENT_ERROR]

        # Python traceback
        events = self.parser.parse_line("Traceback (most recent call last)")
        assert events is not None
        assert len(events) == 1
        assert events[0].type == AgentEventType.ERROR

        # Python exception
        events = self.parser.parse_line("ValueError: invalid literal for int()")
        assert events is not None
        assert len(events) == 1
        assert events[0].type == AgentEventType.ERROR

        # Warning
        events = self.parser.parse_line("WARNING: Deprecated function used")
        assert events is not None
        assert len(events) == 1
        assert events[0].type == AgentEventType.WARNING

    def test_file_operations(self):
        """Test detection of file operations"""
        # File read
        events = self.parser.parse_line("cat /etc/passwd")
        assert events is not None
        assert len(events) == 1
        assert events[0].type == AgentEventType.FILE_READ
        assert events[0].data["file"] == "/etc/passwd"

        # File write with echo
        events = self.parser.parse_line("echo 'test' > output.txt")
        assert events is not None
        assert len(events) == 1
        assert events[0].type == AgentEventType.FILE_WRITE
        assert events[0].data["file"] == "output.txt"

        # File delete
        events = self.parser.parse_line("rm -rf temp/")
        assert events is not None
        assert len(events) == 1
        assert events[0].type == AgentEventType.FILE_DELETE
        assert "temp/" in events[0].data["files"]

    def test_prompt_detection(self):
        """Test detection of interactive prompts"""
        # Yes/No prompt
        events = self.parser.parse_line("Continue? [Y/n]")
        assert events is not None
        assert len(events) == 1
        assert events[0].type == AgentEventType.PROMPT
        assert events[0].data["prompt_type"] == "yes_no"

        # Input prompt
        events = self.parser.parse_line("Enter password:")
        assert events is not None
        assert len(events) == 1
        assert events[0].type == AgentEventType.PROMPT
        assert events[0].data["prompt_type"] == "input"

    def test_ansi_stripping(self):
        """Test that ANSI codes are stripped for pattern matching"""
        # Command with color codes
        colored_line = "\x1b[32mnpm\x1b[0m install \x1b[33mexpress\x1b[0m"
        events = self.parser.parse_line(colored_line)
        assert events is not None
        assert len(events) == 1
        assert events[0].type == AgentEventType.INSTALL_START

    def test_parse_chunk(self):
        """Test parsing multiple lines at once"""
        chunk = """
npm install express
✓ test passed (50ms)
ERROR: Something went wrong
Thinking: I need to fix this
        """.strip()

        events = self.parser.parse_chunk(chunk)
        assert len(events) == 4

        # Check event types (one per line due to priority)
        types = [e.type for e in events]
        assert AgentEventType.INSTALL_START in types
        assert AgentEventType.TEST_RESULT in types
        # ERROR line will be AGENT_ERROR due to pattern starting with "Error"
        assert AgentEventType.AGENT_ERROR in types or AgentEventType.ERROR in types
        assert AgentEventType.AGENT_THINKING in types

    def test_event_serialization(self):
        """Test event JSON serialization"""
        events = self.parser.parse_line("npm install express")
        assert events is not None

        event = events[0]
        # Test to_dict
        event_dict = event.to_dict()
        assert "type" in event_dict
        assert "timestamp" in event_dict
        assert "data" in event_dict
        assert event_dict["type"] == "install_start"

        # Test to_json
        json_str = event.to_json()
        assert isinstance(json_str, str)
        assert "install_start" in json_str

    def test_build_command_detection(self):
        """Test detection of build commands"""
        # Make
        events = self.parser.parse_line("make clean all")
        assert events is not None
        assert len(events) == 1
        assert events[0].type == AgentEventType.BUILD_START
        assert events[0].data["tool"] == "make"

        # Cargo
        events = self.parser.parse_line("cargo build --release")
        assert events is not None
        assert len(events) == 1
        assert events[0].type == AgentEventType.BUILD_START

    def test_line_number_tracking(self):
        """Test that line numbers are tracked"""
        self.parser.parse_line("line 1")
        self.parser.parse_line("line 2")
        events = self.parser.parse_line("npm install")

        assert events is not None
        assert events[0].line_number == 3

    def test_no_match_returns_none(self):
        """Test that non-matching lines return None"""
        events = self.parser.parse_line("This is just regular output")
        assert events is None

        events = self.parser.parse_line("")
        assert events is None

    def test_multiple_events_per_line(self):
        """Test lines that can trigger multiple event types"""
        # Error that's also agent-related
        events = self.parser.parse_line("Error: Cannot find module")
        assert events is not None
        # Should detect as AGENT_ERROR due to pattern priority
        assert len(events) == 1
        assert events[0].type == AgentEventType.AGENT_ERROR


if __name__ == "__main__":
    pytest.main([__file__, "-v"])