# SPDX-License-Identifier: MIT
"""Funciones de soporte para generar insights con Ollama."""

from __future__ import annotations

from .ollama_service import (
    OllamaInsightResult,
    run_ollama_insights,
    DEFAULT_INSIGHTS_FOCUS,
    INSIGHTS_FOCUS_PROMPTS,
    VALID_INSIGHTS_FOCUS,
    build_insights_prompt,
    OLLAMA_DEFAULT_TIMEOUT,
)
from .storage import (
    StoredInsight,
    # Sync versions
    record_insight,
    list_insights,
    clear_insights,
    # Async versions
    record_insight_async,
    list_insights_async,
    clear_insights_async,
)

__all__ = [
    "OllamaInsightResult",
    "run_ollama_insights",
    "DEFAULT_INSIGHTS_FOCUS",
    "INSIGHTS_FOCUS_PROMPTS",
    "VALID_INSIGHTS_FOCUS",
    "build_insights_prompt",
    "OLLAMA_DEFAULT_TIMEOUT",
    "StoredInsight",
    # Sync
    "record_insight",
    "list_insights",
    "clear_insights",
    # Async
    "record_insight_async",
    "list_insights_async",
    "clear_insights_async",
]
