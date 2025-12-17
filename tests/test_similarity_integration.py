# SPDX-License-Identifier: MIT
"""Tests for Similarity integration in AppState."""

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from code_map.state import AppState
from code_map.scheduler import ChangeScheduler
from code_map.settings import AppSettings


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


@pytest.fixture
def mock_state(tmp_path: Path, monkeypatch):
    """Create a mocked AppState for testing."""
    monkeypatch.setattr("code_map.state.WatcherManager", _DummyWatcher)
    monkeypatch.setattr("code_map.services.watcher_manager.WatcherService", _DummyWatcher)
    monkeypatch.setattr(
        "code_map.services.insights_service.InsightsService.schedule",
        lambda self: None,
    )
    
    # Mock scanning to avoid disk I/O
    mock_scanner = MagicMock()
    mock_scanner.scan_and_update_index.return_value = []
    monkeypatch.setattr("code_map.state.ProjectScanner", lambda *args, **kwargs: mock_scanner)

    settings = AppSettings(
        root_path=tmp_path,
        exclude_dirs=(),
        include_docstrings=True,
    )
    state = AppState(settings=settings, scheduler=ChangeScheduler())
    # Override scanner instance
    state.scanner = mock_scanner
    return state


@pytest.mark.asyncio
async def test_state_initializes_similarity_none(mock_state):
    """Test that similarity_report is None on init."""
    assert mock_state.similarity_report is None


@pytest.mark.asyncio
async def test_run_similarity_bg_updates_state(mock_state):
    """Test that run_similarity_bg updates state.similarity_report."""
    
    mock_report = MagicMock()
    mock_report.summary.clone_pairs_found = 5
    mock_report_dict = {"hotspots": [], "clones": []}
    
    with patch("code_map.state.is_available", return_value=True), \
         patch("code_map.state.analyze_similarity", return_value=mock_report) as mock_analyze, \
         patch("code_map.state.report_to_dict", return_value=mock_report_dict):
        
        await mock_state.run_similarity_bg()
        
        mock_analyze.assert_called_once()
        assert mock_state.similarity_report == mock_report_dict


@pytest.mark.asyncio
async def test_perform_full_scan_triggers_similarity(mock_state):
    """Test that perform_full_scan triggers similarity analysis background task."""
    
    with patch("code_map.state.is_available", return_value=True), \
         patch.object(mock_state, "run_similarity_bg", new_callable=AsyncMock) as mock_run_bg:
        
        await mock_state.perform_full_scan()
        
        # We can't easily await the fire-and-forget task in perform_full_scan without generic sleep
        # But we can check if it was scheduled.
        # Since perform_full_scan calls asyncio.create_task(self.run_similarity_bg())
        # We can verify the mock was called.
        
        # Verify run_similarity_bg was called
        # Note: mocking run_similarity_bg on the instance requires care as it is bound.
        # using patch.object is usually safe.
        
        # However, perform_full_scan is async, and it creates a task. 
        # The task might not have started executing run_similarity_bg immediately, 
        # but the coroutine object should have been created.
        
        # Let's give the event loop a small tick to let the background task start
        await asyncio.sleep(0.01)
        
        mock_run_bg.assert_called_once()
