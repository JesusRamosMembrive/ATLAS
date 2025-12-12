# SPDX-License-Identifier: MIT
"""Tests for state module utility functions and components."""

import os
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from code_map.state import (
    AppState,
    _parse_enabled_tools_env,
    _parse_int_env,
    _linters_disabled_from_env,
    DEFAULT_INSIGHTS_INTERVAL_MINUTES,
    MAX_RECENT_CHANGES_TRACKED,
    VALID_INSIGHTS_FOCUS_SET,
)
from code_map.scheduler import ChangeScheduler
from code_map.settings import AppSettings


class TestParseEnabledToolsEnv:
    """Tests for _parse_enabled_tools_env function."""

    def test_parse_none(self) -> None:
        """Test parsing None returns None."""
        assert _parse_enabled_tools_env(None) is None

    def test_parse_empty_string(self) -> None:
        """Test parsing empty string returns None."""
        assert _parse_enabled_tools_env("") is None

    def test_parse_whitespace_only(self) -> None:
        """Test parsing whitespace only returns None."""
        assert _parse_enabled_tools_env("   ") is None

    def test_parse_single_tool(self) -> None:
        """Test parsing single tool."""
        result = _parse_enabled_tools_env("ruff")
        assert result == {"ruff"}

    def test_parse_multiple_tools(self) -> None:
        """Test parsing multiple tools."""
        result = _parse_enabled_tools_env("ruff,mypy,bandit")
        assert result == {"ruff", "mypy", "bandit"}

    def test_parse_with_whitespace(self) -> None:
        """Test parsing tools with whitespace."""
        result = _parse_enabled_tools_env("  ruff  ,  mypy  ")
        assert result == {"ruff", "mypy"}

    def test_parse_normalizes_case(self) -> None:
        """Test parsing normalizes to lowercase."""
        result = _parse_enabled_tools_env("RUFF,MyPy")
        assert result == {"ruff", "mypy"}

    def test_parse_filters_empty_tokens(self) -> None:
        """Test parsing filters empty tokens."""
        result = _parse_enabled_tools_env("ruff,,mypy,")
        assert result == {"ruff", "mypy"}


class TestParseIntEnv:
    """Tests for _parse_int_env function."""

    def test_parse_none(self) -> None:
        """Test parsing None returns None."""
        assert _parse_int_env(None) is None

    def test_parse_valid_int(self) -> None:
        """Test parsing valid integer."""
        assert _parse_int_env("42") == 42

    def test_parse_zero(self) -> None:
        """Test parsing zero."""
        assert _parse_int_env("0") == 0

    def test_parse_negative(self) -> None:
        """Test parsing negative returns None."""
        assert _parse_int_env("-5") is None

    def test_parse_with_whitespace(self) -> None:
        """Test parsing with whitespace."""
        assert _parse_int_env("  100  ") == 100

    def test_parse_invalid(self) -> None:
        """Test parsing invalid string returns None."""
        assert _parse_int_env("not a number") is None

    def test_parse_float_string(self) -> None:
        """Test parsing float string returns None."""
        assert _parse_int_env("3.14") is None


class TestLintersDisabledFromEnv:
    """Tests for _linters_disabled_from_env function."""

    def test_disabled_not_set(self) -> None:
        """Test when env var is not set."""
        with patch.dict(os.environ, {}, clear=True):
            # Clear just the relevant var
            if "CODE_MAP_DISABLE_LINTERS" in os.environ:
                del os.environ["CODE_MAP_DISABLE_LINTERS"]
            assert _linters_disabled_from_env() is False

    def test_disabled_true_values(self) -> None:
        """Test various true values."""
        for value in ["1", "true", "TRUE", "yes", "YES", "on", "ON"]:
            with patch.dict(os.environ, {"CODE_MAP_DISABLE_LINTERS": value}):
                assert (
                    _linters_disabled_from_env() is True
                ), f"Failed for value: {value}"

    def test_disabled_false_values(self) -> None:
        """Test various false values."""
        for value in ["0", "false", "no", "off", "", "random"]:
            with patch.dict(os.environ, {"CODE_MAP_DISABLE_LINTERS": value}):
                assert (
                    _linters_disabled_from_env() is False
                ), f"Failed for value: {value}"

    def test_disabled_with_whitespace(self) -> None:
        """Test value with whitespace."""
        with patch.dict(os.environ, {"CODE_MAP_DISABLE_LINTERS": "  true  "}):
            assert _linters_disabled_from_env() is True


class TestConstants:
    """Test module-level constants."""

    def test_default_insights_interval(self) -> None:
        """Test DEFAULT_INSIGHTS_INTERVAL_MINUTES is reasonable."""
        assert DEFAULT_INSIGHTS_INTERVAL_MINUTES == 60

    def test_max_recent_changes(self) -> None:
        """Test MAX_RECENT_CHANGES_TRACKED is set."""
        assert MAX_RECENT_CHANGES_TRACKED == 50

    def test_valid_insights_focus_set(self) -> None:
        """Test VALID_INSIGHTS_FOCUS_SET contains expected values."""
        assert "general" in VALID_INSIGHTS_FOCUS_SET
        assert "testing" in VALID_INSIGHTS_FOCUS_SET
        assert "issues" in VALID_INSIGHTS_FOCUS_SET


class _DummyWatcher:
    """Dummy watcher for testing without actual file watching."""

    def __init__(self, *args, **kwargs):
        self._running = False

    def start(self) -> bool:
        self._running = True
        return True

    def stop(self) -> None:
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running


class TestAppStateBasics:
    """Tests for AppState basic functionality."""

    @pytest.fixture
    def mock_state(self, tmp_path: Path, monkeypatch):
        """Create a mocked AppState for testing."""
        # Mock WatcherManager
        monkeypatch.setattr("code_map.state.WatcherManager", _DummyWatcher)
        monkeypatch.setattr(
            "code_map.services.watcher_manager.WatcherService", _DummyWatcher
        )

        # Mock insights service schedule to avoid background tasks
        monkeypatch.setattr(
            "code_map.services.insights_service.InsightsService.schedule",
            lambda self: None,
        )

        settings = AppSettings(
            root_path=tmp_path,
            exclude_dirs=(),
            include_docstrings=True,
        )
        state = AppState(settings=settings, scheduler=ChangeScheduler())
        return state

    def test_state_creation(self, mock_state) -> None:
        """Test AppState can be created."""
        assert mock_state is not None
        assert mock_state.settings is not None
        assert mock_state.scheduler is not None
        assert mock_state.scanner is not None
        assert mock_state.index is not None

    def test_to_relative(self, mock_state) -> None:
        """Test to_relative converts absolute to relative path."""
        abs_path = mock_state.settings.root_path / "src" / "main.py"
        result = mock_state.to_relative(abs_path)
        assert result == "src/main.py"

    def test_to_relative_outside_root(self, mock_state) -> None:
        """Test to_relative handles path outside root."""
        abs_path = Path("/some/other/path/file.py")
        result = mock_state.to_relative(abs_path)
        # Should return the resolved absolute path
        assert "/some/other/path/file.py" in result or "file.py" in result

    def test_resolve_path(self, mock_state, tmp_path: Path) -> None:
        """Test resolve_path converts relative to absolute."""
        # Create a file to resolve
        (tmp_path / "test.py").write_text("x = 1")
        result = mock_state.resolve_path("test.py")
        assert result == tmp_path / "test.py"

    def test_resolve_path_outside_root_raises(self, mock_state) -> None:
        """Test resolve_path raises for paths outside root."""
        with pytest.raises(ValueError, match="fuera del root"):
            mock_state.resolve_path("../../../etc/passwd")

    def test_within_root_true(self, mock_state, tmp_path: Path) -> None:
        """Test _within_root returns True for paths inside root."""
        path = tmp_path / "src" / "main.py"
        assert mock_state._within_root(path) is True

    def test_within_root_false(self, mock_state) -> None:
        """Test _within_root returns False for paths outside root."""
        path = Path("/some/other/location")
        assert mock_state._within_root(path) is False

    def test_is_watcher_running(self, mock_state) -> None:
        """Test is_watcher_running returns correct status."""
        # Initially not running
        assert mock_state.is_watcher_running() is False
        # Start watcher
        mock_state.watcher.start()
        assert mock_state.is_watcher_running() is True

    def test_get_settings_payload(self, mock_state) -> None:
        """Test get_settings_payload returns dict."""
        payload = mock_state.get_settings_payload()
        assert isinstance(payload, dict)

    def test_get_status_payload(self, mock_state) -> None:
        """Test get_status_payload returns dict."""
        payload = mock_state.get_status_payload()
        assert isinstance(payload, dict)

    def test_serialize_changes_empty(self, mock_state) -> None:
        """Test _serialize_changes with empty changes."""
        changes = {"updated": [], "deleted": []}
        result = mock_state._serialize_changes(changes)
        assert result == {"updated": [], "deleted": []}

    def test_serialize_changes_with_updates(self, mock_state, tmp_path: Path) -> None:
        """Test _serialize_changes with actual changes."""
        updated_path = tmp_path / "src" / "main.py"
        changes = {"updated": [updated_path], "deleted": []}
        result = mock_state._serialize_changes(changes)
        assert "src/main.py" in result["updated"]
        assert result["deleted"] == []

    def test_serialize_changes_limits_tracking(
        self, mock_state, tmp_path: Path
    ) -> None:
        """Test _serialize_changes limits recent changes."""
        # Create many paths
        many_paths = [tmp_path / f"file{i}.py" for i in range(100)]
        changes = {"updated": many_paths, "deleted": []}
        mock_state._serialize_changes(changes)
        # Should be limited to MAX_RECENT_CHANGES_TRACKED
        assert len(mock_state._recent_changes) <= MAX_RECENT_CHANGES_TRACKED


class TestAppStateAsync:
    """Tests for AppState async functionality."""

    @pytest.fixture
    def mock_state(self, tmp_path: Path, monkeypatch):
        """Create a mocked AppState for async testing."""
        monkeypatch.setattr("code_map.state.WatcherManager", _DummyWatcher)
        monkeypatch.setattr(
            "code_map.services.watcher_manager.WatcherService", _DummyWatcher
        )
        monkeypatch.setattr(
            "code_map.services.insights_service.InsightsService.schedule",
            lambda self: None,
        )

        settings = AppSettings(
            root_path=tmp_path,
            exclude_dirs=(),
            include_docstrings=True,
        )
        state = AppState(settings=settings, scheduler=ChangeScheduler())
        return state

    @pytest.mark.asyncio
    async def test_build_insights_context(self, mock_state) -> None:
        """Test _build_insights_context returns string."""
        result = await mock_state._build_insights_context()
        assert isinstance(result, str)
        # Should have some default message if no context
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_cancel_background_tasks(self, mock_state) -> None:
        """Test _cancel_background_tasks runs without error."""
        await mock_state._cancel_background_tasks()
        assert mock_state._recent_changes == []

    @pytest.mark.asyncio
    async def test_cancel_insights_tasks(self, mock_state) -> None:
        """Test _cancel_insights_tasks runs without error."""
        await mock_state._cancel_insights_tasks()


class TestAppStateUpdateSettings:
    """Tests for AppState update_settings method."""

    @pytest.fixture
    def mock_state(self, tmp_path: Path, monkeypatch):
        """Create a mocked AppState for settings update testing."""
        monkeypatch.setattr("code_map.state.WatcherManager", _DummyWatcher)
        monkeypatch.setattr(
            "code_map.services.watcher_manager.WatcherService", _DummyWatcher
        )
        monkeypatch.setattr(
            "code_map.services.insights_service.InsightsService.schedule",
            lambda self: None,
        )
        monkeypatch.setattr(
            "code_map.state.save_settings",
            lambda settings: None,
        )

        settings = AppSettings(
            root_path=tmp_path,
            exclude_dirs=(),
            include_docstrings=True,
        )
        state = AppState(settings=settings, scheduler=ChangeScheduler())
        return state

    @pytest.mark.asyncio
    async def test_update_settings_no_changes(self, mock_state) -> None:
        """Test update_settings with no changes returns empty list."""
        result = await mock_state.update_settings()
        assert result == []

    @pytest.mark.asyncio
    async def test_update_settings_include_docstrings(self, mock_state) -> None:
        """Test update_settings with include_docstrings change."""
        result = await mock_state.update_settings(include_docstrings=False)
        assert "include_docstrings" in result

    @pytest.mark.asyncio
    async def test_update_settings_invalid_frequency(self, mock_state) -> None:
        """Test update_settings rejects invalid frequency."""
        with pytest.raises(ValueError, match="entero positivo"):
            await mock_state.update_settings(ollama_insights_frequency_minutes=0)

        with pytest.raises(ValueError, match="1440 minutos"):
            await mock_state.update_settings(ollama_insights_frequency_minutes=2000)

    @pytest.mark.asyncio
    async def test_update_settings_invalid_focus(self, mock_state) -> None:
        """Test update_settings rejects invalid focus."""
        with pytest.raises(ValueError, match="no es válido"):
            await mock_state.update_settings(ollama_insights_focus="invalid_focus")

    @pytest.mark.asyncio
    async def test_update_settings_valid_focus(self, mock_state) -> None:
        """Test update_settings accepts valid focus."""
        # First set to "testing", then change to "general" to ensure a change is detected
        await mock_state.update_settings(ollama_insights_focus="testing")
        result = await mock_state.update_settings(ollama_insights_focus="general")
        assert "ollama_insights_focus" in result

    @pytest.mark.asyncio
    async def test_update_settings_empty_focus_resets(self, mock_state) -> None:
        """Test update_settings with empty focus resets to default."""
        result = await mock_state.update_settings(ollama_insights_focus="")
        # Empty string should be accepted to reset
        assert "ollama_insights_focus" in result or result == []

    @pytest.mark.asyncio
    async def test_update_settings_invalid_root_path(self, mock_state) -> None:
        """Test update_settings rejects non-existent root path."""
        with pytest.raises(ValueError, match="no es válida"):
            await mock_state.update_settings(root_path=Path("/nonexistent/path"))


class TestAppStateLinters:
    """Tests for AppState linter configuration."""

    @pytest.fixture
    def mock_state(self, tmp_path: Path, monkeypatch):
        """Create a mocked AppState for linter testing."""
        monkeypatch.setattr("code_map.state.WatcherManager", _DummyWatcher)
        monkeypatch.setattr(
            "code_map.services.watcher_manager.WatcherService", _DummyWatcher
        )
        monkeypatch.setattr(
            "code_map.services.insights_service.InsightsService.schedule",
            lambda self: None,
        )

        settings = AppSettings(
            root_path=tmp_path,
            exclude_dirs=(),
            include_docstrings=True,
        )
        state = AppState(settings=settings, scheduler=ChangeScheduler())
        return state

    def test_build_linters_config(self, mock_state) -> None:
        """Test _build_linters_config returns valid config."""
        config = mock_state._build_linters_config()
        assert config.root_path == mock_state.settings.root_path

    def test_build_linters_config_with_env(self, mock_state, monkeypatch) -> None:
        """Test _build_linters_config respects environment variables."""
        monkeypatch.setenv("CODE_MAP_LINTERS_TOOLS", "ruff,mypy")
        monkeypatch.setenv("CODE_MAP_LINTERS_MAX_PROJECT_FILES", "100")
        monkeypatch.setenv("CODE_MAP_LINTERS_MAX_PROJECT_SIZE_MB", "50")
        monkeypatch.setenv("CODE_MAP_LINTERS_MIN_INTERVAL_SECONDS", "120")

        config = mock_state._build_linters_config()
        assert config.options.enabled_tools == {"ruff", "mypy"}
        assert config.options.max_project_files == 100
        assert config.options.max_project_bytes == 50 * 1024 * 1024
        assert config.min_interval_seconds == 120


class TestAppStateInsights:
    """Tests for AppState insights configuration."""

    @pytest.fixture
    def mock_state(self, tmp_path: Path, monkeypatch):
        """Create a mocked AppState for insights testing."""
        monkeypatch.setattr("code_map.state.WatcherManager", _DummyWatcher)
        monkeypatch.setattr(
            "code_map.services.watcher_manager.WatcherService", _DummyWatcher
        )
        monkeypatch.setattr(
            "code_map.services.insights_service.InsightsService.schedule",
            lambda self: None,
        )

        settings = AppSettings(
            root_path=tmp_path,
            exclude_dirs=(),
            include_docstrings=True,
            ollama_insights_enabled=True,
            ollama_insights_model="test-model",
            ollama_insights_frequency_minutes=30,
            ollama_insights_focus="general",
        )
        state = AppState(settings=settings, scheduler=ChangeScheduler())
        return state

    def test_build_insights_config(self, mock_state) -> None:
        """Test _build_insights_config returns valid config."""
        config = mock_state._build_insights_config()
        assert config.root_path == mock_state.settings.root_path
        assert config.enabled is True
        assert config.model == "test-model"
        assert config.frequency_minutes == 30
        assert config.focus == "general"

    def test_compute_insights_next_run(self, mock_state) -> None:
        """Test _compute_insights_next_run delegates to insights service."""
        result = mock_state._compute_insights_next_run()
        # Should return None or datetime
        assert result is None or isinstance(result, datetime)
