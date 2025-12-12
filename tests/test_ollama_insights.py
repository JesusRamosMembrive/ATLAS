# SPDX-License-Identifier: MIT
"""Tests for insights ollama_service module."""

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from code_map.insights.ollama_service import (
    OLLAMA_DEFAULT_TIMEOUT,
    INSIGHTS_SYSTEM_PROMPT,
    INSIGHTS_FOCUS_PROMPTS,
    VALID_INSIGHTS_FOCUS,
    DEFAULT_INSIGHTS_FOCUS,
    _resolve_focus,
    build_insights_prompt,
    OllamaInsightResult,
    run_ollama_insights,
)
from code_map.integrations import OllamaChatError, OllamaChatResponse


class TestInsightsConfiguration:
    """Test insights configuration constants."""

    def test_default_timeout_is_reasonable(self) -> None:
        """Test that default timeout is a reasonable value."""
        assert OLLAMA_DEFAULT_TIMEOUT > 0
        assert OLLAMA_DEFAULT_TIMEOUT <= 600  # Max 10 minutes

    def test_system_prompt_exists(self) -> None:
        """Test that system prompt is defined."""
        assert INSIGHTS_SYSTEM_PROMPT
        assert len(INSIGHTS_SYSTEM_PROMPT) > 50  # Should be substantial

    def test_valid_focus_options_exist(self) -> None:
        """Test that focus options are defined."""
        assert len(VALID_INSIGHTS_FOCUS) >= 3
        assert "general" in VALID_INSIGHTS_FOCUS
        assert "refactors" in VALID_INSIGHTS_FOCUS
        assert "issues" in VALID_INSIGHTS_FOCUS

    def test_all_focus_options_have_prompts(self) -> None:
        """Test that all focus options have corresponding prompts."""
        for focus in VALID_INSIGHTS_FOCUS:
            assert focus in INSIGHTS_FOCUS_PROMPTS
            assert len(INSIGHTS_FOCUS_PROMPTS[focus]) > 50


class TestResolveFocus:
    """Test _resolve_focus function."""

    def test_resolve_none_returns_default(self) -> None:
        """Test that None returns default focus."""
        assert _resolve_focus(None) == DEFAULT_INSIGHTS_FOCUS

    def test_resolve_empty_string_returns_default(self) -> None:
        """Test that empty string returns default focus."""
        assert _resolve_focus("") == DEFAULT_INSIGHTS_FOCUS

    def test_resolve_valid_focus(self) -> None:
        """Test that valid focus strings are resolved correctly."""
        assert _resolve_focus("general") == "general"
        assert _resolve_focus("refactors") == "refactors"
        assert _resolve_focus("issues") == "issues"
        assert _resolve_focus("duplication") == "duplication"
        assert _resolve_focus("testing") == "testing"

    def test_resolve_focus_case_insensitive(self) -> None:
        """Test that focus resolution is case insensitive."""
        assert _resolve_focus("GENERAL") == "general"
        assert _resolve_focus("Refactors") == "refactors"
        assert _resolve_focus("ISSUES") == "issues"

    def test_resolve_focus_with_whitespace(self) -> None:
        """Test that focus resolution handles whitespace."""
        assert _resolve_focus("  general  ") == "general"
        assert _resolve_focus("\trefactors\n") == "refactors"

    def test_resolve_invalid_focus_returns_default(self) -> None:
        """Test that invalid focus returns default."""
        assert _resolve_focus("invalid") == DEFAULT_INSIGHTS_FOCUS
        assert _resolve_focus("unknown") == DEFAULT_INSIGHTS_FOCUS


class TestBuildInsightsPrompt:
    """Test build_insights_prompt function."""

    def test_build_prompt_with_default_focus(self, tmp_path: Path) -> None:
        """Test building prompt with default focus."""
        prompt = build_insights_prompt(tmp_path, None)
        assert prompt
        assert str(tmp_path) in prompt or tmp_path.as_posix() in prompt

    def test_build_prompt_with_specific_focus(self, tmp_path: Path) -> None:
        """Test building prompt with specific focus."""
        for focus in VALID_INSIGHTS_FOCUS:
            prompt = build_insights_prompt(tmp_path, focus)
            assert prompt
            # Each focus should produce a different prompt
            assert tmp_path.as_posix() in prompt

    def test_build_prompt_includes_root_path(self, tmp_path: Path) -> None:
        """Test that prompt includes root path."""
        prompt = build_insights_prompt(tmp_path, "general")
        assert tmp_path.as_posix() in prompt

    def test_build_prompt_refactors_focus(self, tmp_path: Path) -> None:
        """Test refactors focus prompt content."""
        prompt = build_insights_prompt(tmp_path, "refactors")
        assert "refactor" in prompt.lower()

    def test_build_prompt_issues_focus(self, tmp_path: Path) -> None:
        """Test issues focus prompt content."""
        prompt = build_insights_prompt(tmp_path, "issues")
        assert "fallo" in prompt.lower() or "error" in prompt.lower()

    def test_build_prompt_testing_focus(self, tmp_path: Path) -> None:
        """Test testing focus prompt content."""
        prompt = build_insights_prompt(tmp_path, "testing")
        assert "test" in prompt.lower() or "prueba" in prompt.lower()


class TestOllamaInsightResult:
    """Test OllamaInsightResult dataclass."""

    def test_result_is_frozen(self) -> None:
        """Test that result is immutable."""
        from datetime import datetime, timezone

        raw = OllamaChatResponse(
            model="test",
            message="test message",
            raw={},
            latency_ms=100.0,
            endpoint="http://localhost",
        )
        result = OllamaInsightResult(
            model="test-model",
            generated_at=datetime.now(timezone.utc),
            message="Test insight",
            raw=raw,
        )

        with pytest.raises(AttributeError):
            result.model = "changed"  # type: ignore

    def test_result_stores_all_fields(self) -> None:
        """Test that result stores all required fields."""
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        raw = OllamaChatResponse(
            model="llama3",
            message="Insight content",
            raw={"done": True},
            latency_ms=250.5,
            endpoint="http://localhost:11434",
        )
        result = OllamaInsightResult(
            model="llama3",
            generated_at=now,
            message="Insight content",
            raw=raw,
        )

        assert result.model == "llama3"
        assert result.generated_at == now
        assert result.message == "Insight content"
        assert result.raw == raw


class TestRunOllamaInsights:
    """Test run_ollama_insights function."""

    @patch("code_map.insights.ollama_service.chat_with_ollama")
    def test_run_insights_success(self, mock_chat: MagicMock, tmp_path: Path) -> None:
        """Test successful insights generation."""
        mock_response = OllamaChatResponse(
            model="codellama",
            message="Here are some improvements...",
            raw={"done": True},
            latency_ms=500.0,
            endpoint="http://localhost:11434",
        )
        mock_chat.return_value = mock_response

        result = run_ollama_insights(
            model="codellama",
            root_path=tmp_path,
        )

        assert result.model == "codellama"
        assert result.message == "Here are some improvements..."
        assert result.raw == mock_response
        mock_chat.assert_called_once()

    @patch("code_map.insights.ollama_service.chat_with_ollama")
    def test_run_insights_with_context(
        self, mock_chat: MagicMock, tmp_path: Path
    ) -> None:
        """Test insights generation with context."""
        mock_response = OllamaChatResponse(
            model="codellama",
            message="Based on the context...",
            raw={"done": True},
            latency_ms=300.0,
            endpoint="http://localhost:11434",
        )
        mock_chat.return_value = mock_response

        result = run_ollama_insights(
            model="codellama",
            root_path=tmp_path,
            context="Recent changes: added new API endpoint",
        )

        assert result.message == "Based on the context..."

        # Verify context was included in the prompt
        call_args = mock_chat.call_args
        messages = call_args.kwargs.get(
            "messages", call_args.args[1] if len(call_args.args) > 1 else []
        )
        user_message = next((m for m in messages if m.role == "user"), None)
        assert user_message is not None
        assert "Recent changes" in user_message.content

    @patch("code_map.insights.ollama_service.chat_with_ollama")
    def test_run_insights_with_focus(
        self, mock_chat: MagicMock, tmp_path: Path
    ) -> None:
        """Test insights generation with specific focus."""
        mock_response = OllamaChatResponse(
            model="codellama",
            message="Testing recommendations...",
            raw={"done": True},
            latency_ms=400.0,
            endpoint="http://localhost:11434",
        )
        mock_chat.return_value = mock_response

        result = run_ollama_insights(
            model="codellama",
            root_path=tmp_path,
            focus="testing",
        )

        assert result.message == "Testing recommendations..."

        # Verify focus was used in prompt
        call_args = mock_chat.call_args
        messages = call_args.kwargs.get(
            "messages", call_args.args[1] if len(call_args.args) > 1 else []
        )
        user_message = next((m for m in messages if m.role == "user"), None)
        assert user_message is not None
        # Testing focus should include test-related keywords
        assert (
            "test" in user_message.content.lower()
            or "prueba" in user_message.content.lower()
        )

    @patch("code_map.insights.ollama_service.chat_with_ollama")
    def test_run_insights_with_custom_endpoint(
        self, mock_chat: MagicMock, tmp_path: Path
    ) -> None:
        """Test insights generation with custom endpoint."""
        mock_response = OllamaChatResponse(
            model="codellama",
            message="Response from custom endpoint",
            raw={"done": True},
            latency_ms=200.0,
            endpoint="http://custom:11434",
        )
        mock_chat.return_value = mock_response

        result = run_ollama_insights(
            model="codellama",
            root_path=tmp_path,
            endpoint="http://custom:11434",
        )

        assert result.message == "Response from custom endpoint"
        mock_chat.assert_called_once()
        call_kwargs = mock_chat.call_args.kwargs
        assert call_kwargs.get("endpoint") == "http://custom:11434"

    @patch("code_map.insights.ollama_service.chat_with_ollama")
    def test_run_insights_with_custom_timeout(
        self, mock_chat: MagicMock, tmp_path: Path
    ) -> None:
        """Test insights generation with custom timeout."""
        mock_response = OllamaChatResponse(
            model="codellama",
            message="Quick response",
            raw={"done": True},
            latency_ms=50.0,
            endpoint="http://localhost:11434",
        )
        mock_chat.return_value = mock_response

        result = run_ollama_insights(
            model="codellama",
            root_path=tmp_path,
            timeout=60.0,
        )

        assert result.message == "Quick response"
        call_kwargs = mock_chat.call_args.kwargs
        assert call_kwargs.get("timeout") == 60.0

    @patch("code_map.insights.ollama_service.chat_with_ollama")
    def test_run_insights_error_handling(
        self, mock_chat: MagicMock, tmp_path: Path
    ) -> None:
        """Test insights generation error handling."""
        mock_chat.side_effect = OllamaChatError(
            message="Connection refused",
            endpoint="http://localhost:11434",
            original_error="Connection refused",
        )

        with pytest.raises(OllamaChatError) as exc_info:
            run_ollama_insights(
                model="codellama",
                root_path=tmp_path,
            )

        assert "Connection refused" in str(exc_info.value)

    @patch("code_map.insights.ollama_service.chat_with_ollama")
    def test_run_insights_includes_system_prompt(
        self, mock_chat: MagicMock, tmp_path: Path
    ) -> None:
        """Test that system prompt is included in messages."""
        mock_response = OllamaChatResponse(
            model="codellama",
            message="Response",
            raw={"done": True},
            latency_ms=100.0,
            endpoint="http://localhost:11434",
        )
        mock_chat.return_value = mock_response

        run_ollama_insights(
            model="codellama",
            root_path=tmp_path,
        )

        call_args = mock_chat.call_args
        messages = call_args.kwargs.get(
            "messages", call_args.args[1] if len(call_args.args) > 1 else []
        )

        # Should have system and user messages
        assert len(messages) == 2
        system_message = next((m for m in messages if m.role == "system"), None)
        assert system_message is not None
        assert system_message.content == INSIGHTS_SYSTEM_PROMPT


class TestInsightsFocusPrompts:
    """Test that all focus prompts are well-formed."""

    def test_all_prompts_have_root_placeholder(self) -> None:
        """Test that all prompts include {root} placeholder."""
        for focus, prompt in INSIGHTS_FOCUS_PROMPTS.items():
            assert "{root}" in prompt, f"Focus '{focus}' missing {{root}} placeholder"

    def test_all_prompts_are_spanish(self) -> None:
        """Test that prompts are in Spanish (contain Spanish words)."""
        spanish_indicators = [
            "analiza",
            "repositorio",
            "propón",
            "sugiere",
            "revisa",
            "evalúa",
        ]
        for focus, prompt in INSIGHTS_FOCUS_PROMPTS.items():
            has_spanish = any(word in prompt.lower() for word in spanish_indicators)
            assert has_spanish, f"Focus '{focus}' doesn't appear to be in Spanish"

    def test_prompts_are_distinct(self) -> None:
        """Test that each focus has a distinct prompt."""
        prompts = list(INSIGHTS_FOCUS_PROMPTS.values())
        unique_prompts = set(prompts)
        assert len(prompts) == len(unique_prompts), "Some focus prompts are duplicated"
