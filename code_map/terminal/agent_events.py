"""
Agent Event System for Terminal

Manages event aggregation, session state, and event streaming for agent terminal overlay.
"""

import asyncio
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime, timedelta
from collections import defaultdict
from dataclasses import dataclass, field
import logging

from .agent_parser import AgentEvent, AgentEventType

logger = logging.getLogger(__name__)


@dataclass
class CommandExecution:
    """Track a command execution from start to end"""

    command: str
    start_time: datetime
    end_time: Optional[datetime] = None
    exit_code: Optional[int] = None
    output_lines: List[str] = field(default_factory=list)
    events: List[AgentEvent] = field(default_factory=list)
    status: str = "running"  # running, completed, failed

    @property
    def duration(self) -> Optional[timedelta]:
        """Get command execution duration"""
        if self.end_time:
            return self.end_time - self.start_time
        return None

    @property
    def duration_seconds(self) -> Optional[float]:
        """Get duration in seconds"""
        if self.duration:
            return self.duration.total_seconds()
        return None


@dataclass
class FileChange:
    """Track a file change during session"""

    file_path: str
    operation: str  # read, write, delete, modify
    timestamp: datetime
    line_count: Optional[int] = None
    diff: Optional[str] = None


@dataclass
class TestRun:
    """Track a test execution"""

    tool: str  # pytest, jest, etc.
    start_time: datetime
    end_time: Optional[datetime] = None
    total_tests: int = 0
    passed_tests: int = 0
    failed_tests: int = 0
    skipped_tests: int = 0
    failures: List[Dict] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        """Calculate test success rate"""
        if self.total_tests == 0:
            return 0.0
        return self.passed_tests / self.total_tests


@dataclass
class AgentSessionState:
    """Maintain state of an agent session"""

    session_id: str
    start_time: datetime
    current_phase: str = "idle"  # idle, thinking, planning, executing, verifying
    commands: List[CommandExecution] = field(default_factory=list)
    file_changes: List[FileChange] = field(default_factory=list)
    test_runs: List[TestRun] = field(default_factory=list)
    events: List[AgentEvent] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)

    # Current tracking
    current_command: Optional[CommandExecution] = None
    current_test_run: Optional[TestRun] = None

    def update_metrics(self):
        """Update session metrics"""
        self.metrics = {
            "total_commands": len(self.commands),
            "total_events": len(self.events),
            "total_files_changed": len(self.file_changes),
            "total_test_runs": len(self.test_runs),
            "session_duration": (datetime.now() - self.start_time).total_seconds(),
            "current_phase": self.current_phase,
            "error_count": sum(
                1 for e in self.events if e.type == AgentEventType.ERROR
            ),
            "warning_count": sum(
                1 for e in self.events if e.type == AgentEventType.WARNING
            ),
        }

        # Add test metrics if available
        if self.test_runs:
            total_tests = sum(run.total_tests for run in self.test_runs)
            passed_tests = sum(run.passed_tests for run in self.test_runs)
            self.metrics["total_tests"] = total_tests
            self.metrics["tests_passed"] = passed_tests
            self.metrics["test_success_rate"] = (
                passed_tests / total_tests if total_tests > 0 else 0
            )


class AgentEventManager:
    """Manages agent events and session state"""

    def __init__(self, session_id: str):
        """Initialize event manager for a session"""
        self.session_id = session_id
        self.state = AgentSessionState(session_id=session_id, start_time=datetime.now())
        self.event_handlers: Dict[AgentEventType, List[Callable]] = defaultdict(list)
        self.subscribers: List[Callable] = []

    def register_handler(self, event_type: AgentEventType, handler: Callable):
        """Register a handler for specific event type"""
        self.event_handlers[event_type].append(handler)

    def subscribe(self, callback: Callable):
        """Subscribe to all events"""
        self.subscribers.append(callback)

    async def process_event(self, event: AgentEvent):
        """
        Process an agent event and update state

        Args:
            event: The agent event to process
        """
        # Add to event history
        self.state.events.append(event)

        # Update state based on event type
        await self._update_state(event)

        # Call type-specific handlers
        for handler in self.event_handlers.get(event.type, []):
            try:
                await self._call_handler(handler, event)
            except Exception as e:
                logger.error(f"Error in event handler: {e}")

        # Notify all subscribers
        for subscriber in self.subscribers:
            try:
                await self._call_handler(subscriber, event)
            except Exception as e:
                logger.error(f"Error in subscriber: {e}")

        # Update metrics
        self.state.update_metrics()

    async def _call_handler(self, handler: Callable, event: AgentEvent):
        """Call a handler, supporting both sync and async functions"""
        if asyncio.iscoroutinefunction(handler):
            await handler(event, self.state)
        else:
            handler(event, self.state)

    async def _update_state(self, event: AgentEvent):
        """Update session state based on event"""

        # Command tracking
        if event.type == AgentEventType.COMMAND_START:
            command = CommandExecution(
                command=event.data.get("command", ""),
                start_time=datetime.fromisoformat(event.timestamp),
            )
            self.state.current_command = command
            self.state.commands.append(command)
            self.state.current_phase = "executing"

        elif event.type == AgentEventType.COMMAND_END:
            if self.state.current_command:
                self.state.current_command.end_time = datetime.fromisoformat(
                    event.timestamp
                )
                self.state.current_command.exit_code = event.data.get("exit_code", 0)
                self.state.current_command.status = (
                    "completed" if event.data.get("exit_code", 0) == 0 else "failed"
                )
                self.state.current_command = None

        # File tracking
        elif event.type in [
            AgentEventType.FILE_READ,
            AgentEventType.FILE_WRITE,
            AgentEventType.FILE_DELETE,
        ]:
            operation_map = {
                AgentEventType.FILE_READ: "read",
                AgentEventType.FILE_WRITE: "write",
                AgentEventType.FILE_DELETE: "delete",
            }

            files = event.data.get("files", [event.data.get("file")])
            if not isinstance(files, list):
                files = [files]

            for file_path in files:
                if file_path:
                    change = FileChange(
                        file_path=file_path,
                        operation=operation_map[event.type],
                        timestamp=datetime.fromisoformat(event.timestamp),
                    )
                    self.state.file_changes.append(change)

        # Test tracking
        elif event.type == AgentEventType.TEST_START:
            test_run = TestRun(
                tool=event.data.get("tool", "unknown"),
                start_time=datetime.fromisoformat(event.timestamp),
            )
            self.state.current_test_run = test_run
            self.state.test_runs.append(test_run)

        elif event.type == AgentEventType.TEST_RESULT:
            if self.state.current_test_run:
                status = event.data.get("status")
                if status == "passed":
                    self.state.current_test_run.passed_tests += 1
                elif status == "failed":
                    self.state.current_test_run.failed_tests += 1
                    self.state.current_test_run.failures.append(event.data)
                elif status == "skipped":
                    self.state.current_test_run.skipped_tests += 1

        elif event.type == AgentEventType.TEST_SUMMARY:
            if self.state.current_test_run:
                self.state.current_test_run.end_time = datetime.fromisoformat(
                    event.timestamp
                )
                self.state.current_test_run.total_tests = event.data.get("total", 0)
                if "passed" in event.data:
                    self.state.current_test_run.passed_tests = event.data["passed"]
                self.state.current_test_run = None

        # Phase tracking
        elif event.type == AgentEventType.AGENT_THINKING:
            self.state.current_phase = "thinking"
        elif event.type == AgentEventType.AGENT_PLANNING:
            self.state.current_phase = "planning"
        elif event.type == AgentEventType.AGENT_DECISION:
            self.state.current_phase = "deciding"

        # Add output to current command if running
        if self.state.current_command and event.raw_text:
            self.state.current_command.output_lines.append(event.raw_text)
            self.state.current_command.events.append(event)

    def get_timeline(self) -> List[Dict]:
        """
        Get timeline of session events

        Returns:
            List of timeline entries with timestamps and descriptions
        """
        timeline = []

        for event in self.state.events:
            entry = {
                "timestamp": event.timestamp,
                "type": event.type.value,
                "description": self._get_event_description(event),
                "data": event.data,
                "phase": self._get_event_phase(event),
            }
            timeline.append(entry)

        return sorted(timeline, key=lambda x: x["timestamp"])

    def _get_event_description(self, event: AgentEvent) -> str:
        """Generate human-readable description for event"""
        descriptions = {
            AgentEventType.COMMAND_START: f"Running: {event.data.get('command', 'command')}",
            AgentEventType.COMMAND_END: f"Completed: {event.data.get('command', 'command')}",
            AgentEventType.FILE_READ: f"Reading: {event.data.get('file', 'file')}",
            AgentEventType.FILE_WRITE: f"Writing: {event.data.get('file', 'file')}",
            AgentEventType.FILE_DELETE: f"Deleting: {', '.join(event.data.get('files', []))}",
            AgentEventType.TEST_START: f"Testing with {event.data.get('tool', 'test tool')}",
            AgentEventType.TEST_SUMMARY: f"Tests: {event.data.get('passed', 0)} passed",
            AgentEventType.AGENT_THINKING: "Agent is thinking...",
            AgentEventType.AGENT_PLANNING: "Agent is planning...",
            AgentEventType.AGENT_DECISION: "Agent made a decision",
            AgentEventType.ERROR: f"Error: {event.data.get('command', 'unknown')}",
            AgentEventType.WARNING: "Warning detected",
            AgentEventType.INSTALL_START: "Installing packages...",
            AgentEventType.BUILD_START: "Building project...",
        }

        return descriptions.get(event.type, event.type.value)

    def _get_event_phase(self, event: AgentEvent) -> str:
        """Get phase indicator for event"""
        phase_map = {
            AgentEventType.AGENT_THINKING: "thinking",
            AgentEventType.AGENT_PLANNING: "planning",
            AgentEventType.AGENT_DECISION: "deciding",
            AgentEventType.COMMAND_START: "executing",
            AgentEventType.TEST_START: "testing",
            AgentEventType.BUILD_START: "building",
            AgentEventType.INSTALL_START: "installing",
        }

        return phase_map.get(event.type, self.state.current_phase)

    def get_state_summary(self) -> Dict:
        """Get summary of current session state"""
        return {
            "session_id": self.session_id,
            "current_phase": self.state.current_phase,
            "metrics": self.state.metrics,
            "active_command": (
                self.state.current_command.command
                if self.state.current_command
                else None
            ),
            "active_test": (
                self.state.current_test_run.tool
                if self.state.current_test_run
                else None
            ),
            "recent_files": [fc.file_path for fc in self.state.file_changes[-5:]],
            "error_count": self.state.metrics.get("error_count", 0),
            "command_count": len(self.state.commands),
            "test_summary": self._get_test_summary(),
        }

    def _get_test_summary(self) -> Dict:
        """Get summary of all test runs"""
        if not self.state.test_runs:
            return {"total": 0, "passed": 0, "failed": 0, "success_rate": 0}

        total = sum(run.total_tests for run in self.state.test_runs)
        passed = sum(run.passed_tests for run in self.state.test_runs)
        failed = sum(run.failed_tests for run in self.state.test_runs)

        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "success_rate": passed / total if total > 0 else 0,
        }

    def export_session(self) -> Dict:
        """Export complete session data for persistence or analysis"""
        return {
            "session_id": self.session_id,
            "start_time": self.state.start_time.isoformat(),
            "duration": (datetime.now() - self.state.start_time).total_seconds(),
            "metrics": self.state.metrics,
            "timeline": self.get_timeline(),
            "commands": [
                {
                    "command": cmd.command,
                    "start_time": cmd.start_time.isoformat(),
                    "end_time": cmd.end_time.isoformat() if cmd.end_time else None,
                    "duration": cmd.duration_seconds,
                    "exit_code": cmd.exit_code,
                    "status": cmd.status,
                }
                for cmd in self.state.commands
            ],
            "file_changes": [
                {
                    "file": fc.file_path,
                    "operation": fc.operation,
                    "timestamp": fc.timestamp.isoformat(),
                }
                for fc in self.state.file_changes
            ],
            "test_runs": [
                {
                    "tool": run.tool,
                    "total": run.total_tests,
                    "passed": run.passed_tests,
                    "failed": run.failed_tests,
                    "success_rate": run.success_rate,
                }
                for run in self.state.test_runs
            ],
        }
