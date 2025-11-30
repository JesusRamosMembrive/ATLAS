# SPDX-License-Identifier: MIT
"""
Servicios auxiliares para serializar settings y estado de la aplicación.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, Optional

from .analyzer_registry import AnalyzerCapability
from .scanner import ProjectScanner
from .settings import AppSettings
from .index import SymbolIndex


def _serialize_capability(cap: AnalyzerCapability) -> Dict[str, Any]:
    """Serializa un objeto AnalyzerCapability a un diccionario."""
    return {
        "key": cap.key,
        "description": cap.description,
        "extensions": cap.extensions,
        "available": cap.available,
        "dependency": cap.dependency,
        "error": cap.error,
        "degraded_extensions": cap.degraded_extensions,
    }


@dataclass
class StateReporter:
    """Encapsula la construcción de payloads derivados del estado global."""

    settings: AppSettings
    scanner: ProjectScanner
    index: SymbolIndex

    def settings_payload(self, *, watcher_active: bool) -> Dict[str, Any]:
        """
        Construye el payload de settings para la API.

        Args:
            watcher_active: True si el observador de archivos está activo.

        Returns:
            Un diccionario con la configuración actual de la aplicación.
        """
        return {
            "root_path": self.settings.root_path.as_posix(),
            "exclude_dirs": list(self.settings.exclude_dirs),
            "include_docstrings": self.settings.include_docstrings,
            "ollama_insights_enabled": self.settings.ollama_insights_enabled,
            "ollama_insights_model": self.settings.ollama_insights_model,
            "ollama_insights_frequency_minutes": self.settings.ollama_insights_frequency_minutes,
            "ollama_insights_focus": self.settings.ollama_insights_focus or "general",
            "backend_url": self.settings.backend_url,
            "watcher_active": watcher_active,
            "absolute_root": str(self.settings.root_path),
        }

    def status_payload(
        self,
        *,
        watcher_active: bool,
        last_full_scan: Optional[datetime],
        last_event_batch: Optional[datetime],
        pending_events: int,
        insights_last_run: Optional[datetime],
        insights_next_run: Optional[datetime],
        insights_last_model: Optional[str],
        insights_last_message: Optional[str],
        insights_last_error: Optional[str],
    ) -> Dict[str, Any]:
        """
        Construye el payload de estado para la API.

        Args:
            watcher_active: True si el observador de archivos está activo.
            last_full_scan: Fecha y hora del último escaneo completo.
            last_event_batch: Fecha y hora del último lote de eventos procesado.
            pending_events: Número de eventos de archivo pendientes de procesar.

        Returns:
            Un diccionario con el estado actual de la aplicación.
        """
        summaries = self.index.get_all()
        total_files = len(summaries)
        total_symbols = sum(len(summary.symbols) for summary in summaries)
        capabilities = [
            _serialize_capability(cap) for cap in self.scanner.registry.capabilities
        ]
        degraded = [
            cap
            for cap in capabilities
            if (not cap["available"]) or (cap.get("degraded_extensions"))
        ]

        return {
            "root_path": self.settings.root_path.as_posix(),
            "absolute_root": str(self.settings.root_path),
            "watcher_active": watcher_active,
            "include_docstrings": self.settings.include_docstrings,
            "ollama_insights_enabled": self.settings.ollama_insights_enabled,
            "ollama_insights_model": self.settings.ollama_insights_model,
            "ollama_insights_frequency_minutes": self.settings.ollama_insights_frequency_minutes,
            "ollama_insights_focus": self.settings.ollama_insights_focus or "general",
            "ollama_insights_last_run": insights_last_run,
            "ollama_insights_next_run": insights_next_run,
            "ollama_insights_last_model": insights_last_model,
            "ollama_insights_last_message": insights_last_message,
            "ollama_insights_last_error": insights_last_error,
            "last_full_scan": last_full_scan,
            "last_event_batch": last_event_batch,
            "files_indexed": total_files,
            "symbols_indexed": total_symbols,
            "pending_events": pending_events,
            "capabilities": capabilities,
            "analyzers_degraded": bool(degraded),
            "degraded_capabilities": [cap["key"] for cap in degraded],
        }
