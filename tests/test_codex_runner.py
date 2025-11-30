"""
Tests for Codex CLI Runner

Verifies configuration, command building, and event mapping functionality.
"""

import pytest
from code_map.terminal.codex_runner import (
    CodexAgentRunner,
    CodexRunnerConfig,
    CODEX_MODE_MAPPING,
    CODEX_TOOL_MAPPING,
)


class TestCodexRunnerConfig:
    """Test CodexRunnerConfig dataclass"""

    def test_default_config(self):
        """Test default configuration values"""
        config = CodexRunnerConfig(cwd="/tmp/test")

        assert config.cwd == "/tmp/test"
        assert config.model == "gpt-5.1-codex-max"
        assert config.permission_mode == "default"
        assert config.timeout is None
        assert config.auto_approve_safe_tools is False
        assert config.add_dirs == []
        assert config.skip_git_check is False
        assert config.enable_search is False

    def test_custom_config(self):
        """Test custom configuration"""
        config = CodexRunnerConfig(
            cwd="/workspace",
            model="gpt-4o",
            permission_mode="bypassPermissions",
            timeout=300.0,
            auto_approve_safe_tools=True,
            add_dirs=["/extra/dir"],
            skip_git_check=True,
            enable_search=True,
        )

        assert config.cwd == "/workspace"
        assert config.model == "gpt-4o"
        assert config.permission_mode == "bypassPermissions"
        assert config.timeout == 300.0
        assert config.auto_approve_safe_tools is True
        assert config.add_dirs == ["/extra/dir"]
        assert config.skip_git_check is True
        assert config.enable_search is True


class TestCodexModeMappings:
    """Test ATLAS to Codex mode mappings"""

    def test_default_mode(self):
        """Test default mode mapping - read-only sandbox"""
        mapping = CODEX_MODE_MAPPING["default"]
        assert mapping["sandbox"] == "read-only"
        assert "full_auto" not in mapping
        # Note: Codex CLI has no --ask-for-approval flag

    def test_accept_edits_mode(self):
        """Test acceptEdits mode mapping - workspace-write sandbox"""
        mapping = CODEX_MODE_MAPPING["acceptEdits"]
        assert mapping["sandbox"] == "workspace-write"

    def test_bypass_permissions_mode(self):
        """Test bypassPermissions mode mapping - full-auto flag"""
        mapping = CODEX_MODE_MAPPING["bypassPermissions"]
        assert mapping.get("full_auto") is True

    def test_dont_ask_mode(self):
        """Test dontAsk mode mapping - dangerous bypass flag"""
        mapping = CODEX_MODE_MAPPING["dontAsk"]
        assert mapping.get("dangerously_bypass") is True

    def test_plan_mode(self):
        """Test plan mode mapping - read-only sandbox"""
        mapping = CODEX_MODE_MAPPING["plan"]
        assert mapping["sandbox"] == "read-only"

    def test_tool_approval_mode(self):
        """Test toolApproval mode mapping - read-only sandbox"""
        mapping = CODEX_MODE_MAPPING["toolApproval"]
        assert mapping["sandbox"] == "read-only"


class TestCodexToolMappings:
    """Test Codex to Claude tool name mappings"""

    def test_command_execution_mapping(self):
        """Test command execution tools map to Bash"""
        assert CODEX_TOOL_MAPPING["command_execution"] == "Bash"
        assert CODEX_TOOL_MAPPING["shell"] == "Bash"
        assert CODEX_TOOL_MAPPING["run_shell_command"] == "Bash"

    def test_file_operation_mappings(self):
        """Test file operation tool mappings"""
        assert CODEX_TOOL_MAPPING["read_file"] == "Read"
        assert CODEX_TOOL_MAPPING["write_file"] == "Write"
        assert CODEX_TOOL_MAPPING["edit_file"] == "Edit"

    def test_search_mappings(self):
        """Test search tool mappings"""
        assert CODEX_TOOL_MAPPING["file_search"] == "Glob"
        assert CODEX_TOOL_MAPPING["code_search"] == "Grep"


class TestCodexAgentRunner:
    """Test CodexAgentRunner class"""

    def test_runner_initialization(self):
        """Test basic runner initialization"""
        config = CodexRunnerConfig(cwd="/tmp/test")
        runner = CodexAgentRunner(config)

        assert runner.config == config
        assert runner.process is None
        assert runner.running is False
        assert runner._cancelled is False
        assert runner._thread_id is None
        assert runner._tool_approval_manager is None

    def test_build_command_default_mode(self):
        """Test command building with default mode"""
        config = CodexRunnerConfig(cwd="/workspace")
        runner = CodexAgentRunner(config)

        cmd = runner._build_command("test prompt")

        # Should have: codex exec "prompt" --json --sandbox read-only --cd /workspace
        # Note: Codex CLI does NOT support --ask-for-approval flag
        assert "exec" in cmd
        assert "test prompt" in cmd
        assert "--json" in cmd
        assert "--sandbox" in cmd
        assert "read-only" in cmd
        assert "--cd" in cmd
        assert "/workspace" in cmd
        assert "--full-auto" not in cmd
        assert "--ask-for-approval" not in cmd  # This flag doesn't exist in Codex CLI

    def test_build_command_bypass_mode(self):
        """Test command building with bypassPermissions mode"""
        config = CodexRunnerConfig(cwd="/workspace", permission_mode="bypassPermissions")
        runner = CodexAgentRunner(config)

        cmd = runner._build_command("test prompt")

        assert "--full-auto" in cmd
        assert "--sandbox" not in cmd

    def test_build_command_dont_ask_mode(self):
        """Test command building with dontAsk mode"""
        config = CodexRunnerConfig(cwd="/workspace", permission_mode="dontAsk")
        runner = CodexAgentRunner(config)

        cmd = runner._build_command("test prompt")

        assert "--dangerously-bypass-approvals-and-sandbox" in cmd
        assert "--full-auto" not in cmd

    def test_build_command_custom_model(self):
        """Test command building with custom model"""
        config = CodexRunnerConfig(cwd="/workspace", model="gpt-4o")
        runner = CodexAgentRunner(config)

        cmd = runner._build_command("test prompt")

        assert "--model" in cmd
        assert "gpt-4o" in cmd

    def test_build_command_default_model_not_included(self):
        """Test default model is not included in command"""
        config = CodexRunnerConfig(cwd="/workspace", model="gpt-5.1-codex-max")
        runner = CodexAgentRunner(config)

        cmd = runner._build_command("test prompt")

        assert "--model" not in cmd

    def test_build_command_skip_git_check(self):
        """Test command building with skip_git_check"""
        config = CodexRunnerConfig(cwd="/workspace", skip_git_check=True)
        runner = CodexAgentRunner(config)

        cmd = runner._build_command("test prompt")

        assert "--skip-git-repo-check" in cmd

    def test_build_command_add_dirs(self):
        """Test command building with additional directories"""
        config = CodexRunnerConfig(
            cwd="/workspace",
            add_dirs=["/extra/dir1", "/extra/dir2"]
        )
        runner = CodexAgentRunner(config)

        cmd = runner._build_command("test prompt")

        assert cmd.count("--add-dir") == 2
        assert "/extra/dir1" in cmd
        assert "/extra/dir2" in cmd

    def test_build_command_enable_search(self):
        """Test command building with search enabled"""
        config = CodexRunnerConfig(cwd="/workspace", enable_search=True)
        runner = CodexAgentRunner(config)

        cmd = runner._build_command("test prompt")

        assert "--search" in cmd


class TestCodexEventMapping:
    """Test event mapping from Codex format to ATLAS format"""

    def setup_method(self):
        """Set up test runner"""
        config = CodexRunnerConfig(cwd="/tmp/test")
        self.runner = CodexAgentRunner(config)

    def test_map_reasoning_event(self):
        """Test mapping reasoning item to text event (with italic formatting)"""
        codex_event = {
            "type": "item.completed",
            "item": {
                "type": "reasoning",
                "text": "I need to analyze this..."
            }
        }

        mapped = self.runner._map_event(codex_event)

        assert len(mapped) == 1
        assert mapped[0]["type"] == "assistant"
        assert mapped[0]["subtype"] == "text"
        # Reasoning is wrapped in italics for visual distinction
        assert mapped[0]["content"] == "*I need to analyze this...*"

    def test_map_agent_message_event(self):
        """Test mapping agent_message item to text event"""
        codex_event = {
            "type": "item.completed",
            "item": {
                "type": "agent_message",
                "text": "Here's what I found..."
            }
        }

        mapped = self.runner._map_event(codex_event)

        assert len(mapped) == 1
        assert mapped[0]["type"] == "assistant"
        assert mapped[0]["subtype"] == "text"
        assert mapped[0]["content"] == "Here's what I found..."

    def test_map_command_execution_started(self):
        """Test mapping command_execution start to tool_use event"""
        codex_event = {
            "type": "item.started",
            "item": {
                "id": "item_1",
                "type": "command_execution",
                "command": "ls -la",
                "status": "in_progress"
            }
        }

        mapped = self.runner._map_event(codex_event)

        assert len(mapped) == 1
        assert mapped[0]["type"] == "assistant"
        assert mapped[0]["subtype"] == "tool_use"
        assert mapped[0]["content"]["name"] == "Bash"  # Mapped from command_execution
        assert mapped[0]["content"]["input"]["command"] == "ls -la"
        assert mapped[0]["content"]["id"] == "item_1"

    def test_map_command_execution_completed(self):
        """Test mapping command_execution completion to tool_result event"""
        codex_event = {
            "type": "item.completed",
            "item": {
                "id": "item_1",
                "type": "command_execution",
                "command": "ls -la",
                "aggregated_output": "file1.txt\nfile2.txt",
                "exit_code": 0
            }
        }

        mapped = self.runner._map_event(codex_event)

        assert len(mapped) == 1
        assert mapped[0]["type"] == "user"
        assert mapped[0]["subtype"] == "tool_result"
        assert mapped[0]["content"]["tool_use_id"] == "item_1"
        assert mapped[0]["content"]["content"] == "file1.txt\nfile2.txt"
        assert mapped[0]["content"]["is_error"] is False

    def test_map_command_execution_error(self):
        """Test mapping failed command_execution to error tool_result"""
        codex_event = {
            "type": "item.completed",
            "item": {
                "id": "item_1",
                "type": "command_execution",
                "command": "invalid_command",
                "aggregated_output": "command not found",
                "exit_code": 127
            }
        }

        mapped = self.runner._map_event(codex_event)

        assert len(mapped) == 1
        assert mapped[0]["type"] == "user"
        assert mapped[0]["subtype"] == "tool_result"
        assert mapped[0]["content"]["is_error"] is True

    def test_map_turn_completed_with_usage(self):
        """Test mapping turn.completed event with token usage"""
        codex_event = {
            "type": "turn.completed",
            "usage": {
                "input_tokens": 100,
                "output_tokens": 50
            }
        }

        mapped = self.runner._map_event(codex_event)

        assert len(mapped) == 1
        assert mapped[0]["type"] == "system"
        assert mapped[0]["subtype"] == "usage"
        # Token usage is in the content field
        assert mapped[0]["content"]["input_tokens"] == 100
        assert mapped[0]["content"]["output_tokens"] == 50

    def test_map_unknown_event_returns_empty(self):
        """Test that unknown events return empty list"""
        codex_event = {
            "type": "unknown.event"
        }

        mapped = self.runner._map_event(codex_event)

        assert mapped == []

    def test_map_thread_started_stores_id(self):
        """Test that thread.started event stores thread_id"""
        codex_event = {
            "type": "thread.started",
            "thread_id": "thread_abc123"
        }

        self.runner._map_event(codex_event)

        assert self.runner._thread_id == "thread_abc123"


class TestCodexToolNameMapping:
    """Test the _map_tool_name helper"""

    def setup_method(self):
        """Set up test runner"""
        config = CodexRunnerConfig(cwd="/tmp/test")
        self.runner = CodexAgentRunner(config)

    def test_map_known_tool(self):
        """Test mapping known Codex tool names"""
        assert self.runner._map_tool_name("command_execution") == "Bash"
        assert self.runner._map_tool_name("read_file") == "Read"
        assert self.runner._map_tool_name("write_file") == "Write"

    def test_map_unknown_tool_returns_original(self):
        """Test that unknown tool names return the original name"""
        assert self.runner._map_tool_name("custom_tool") == "custom_tool"
        assert self.runner._map_tool_name("some_new_tool") == "some_new_tool"


class TestCodexHelperMethods:
    """Test helper methods"""

    def setup_method(self):
        """Set up test runner"""
        config = CodexRunnerConfig(cwd="/tmp/test")
        self.runner = CodexAgentRunner(config)

    def test_is_tool_use_event(self):
        """Test tool_use event detection"""
        tool_use_event = {"type": "assistant", "subtype": "tool_use"}
        text_event = {"type": "assistant", "subtype": "text"}

        assert self.runner._is_tool_use_event(tool_use_event) is True
        assert self.runner._is_tool_use_event(text_event) is False

    def test_extract_tool_use_from_event(self):
        """Test extraction of tool use details"""
        event = {
            "type": "assistant",
            "subtype": "tool_use",
            "content": {
                "name": "Bash",
                "input": {"command": "ls"},
                "id": "tool_123"
            }
        }

        result = self.runner._extract_tool_use_from_event(event)

        assert result is not None
        assert result[0] == "Bash"
        assert result[1] == {"command": "ls"}
        assert result[2] == "tool_123"

    def test_extract_tool_use_from_non_tool_event(self):
        """Test extraction returns None for non-tool events"""
        event = {"type": "assistant", "subtype": "text"}

        result = self.runner._extract_tool_use_from_event(event)

        assert result is None
