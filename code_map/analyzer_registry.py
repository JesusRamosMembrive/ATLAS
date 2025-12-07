# SPDX-License-Identifier: MIT
"""
Registro centralizado de analizadores por extensión y sus capacidades.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Protocol, Set

from .analyzer import FileAnalyzer, get_modified_time
from .c_analyzer import CAnalyzer
from .dependencies import OptionalDependencyRegistry, optional_dependencies
from .html_analyzer import HtmlAnalyzer
from .js_analyzer import JsAnalyzer
from .models import FileSummary
from .ts_analyzer import TsAnalyzer


@dataclass
class AnalyzerCapability:
    """Descripción de la disponibilidad de un analizador por dominio."""

    key: str
    description: str
    extensions: List[str]
    available: bool
    dependency: Optional[str] = None
    error: Optional[str] = None
    degraded_extensions: List[str] = field(default_factory=list)


class PlainTextAnalyzer:
    """Analizador de reserva cuando no existe soporte específico."""

    def parse(self, path: Path) -> FileSummary:
        """Genera un resumen vacío para un archivo de texto plano."""
        abs_path = path.resolve()
        return FileSummary(
            path=abs_path,
            symbols=[],
            errors=[],
            modified_at=get_modified_time(abs_path),
        )


class AnalyzerProtocol(Protocol):  # pragma: no cover - interfaz estructural
    def parse(self, path: Path) -> FileSummary: ...


class AnalyzerRegistry:
    """Agrupa los analizadores disponibles y proporciona sus capacidades."""

    JS_EXTENSIONS = {".js", ".jsx"}
    C_EXTENSIONS = {".c", ".h"}
    CPP_EXTENSIONS = {".cpp", ".hpp", ".cc", ".cxx", ".hxx"}

    def __init__(
        self,
        *,
        include_docstrings: bool,
        extensions: Iterable[str],
        overrides: Optional[Mapping[str, AnalyzerProtocol]] = None,
        dependency_registry: Optional[OptionalDependencyRegistry] = None,
    ) -> None:
        """Inicializa el registro de analizadores."""
        self._include_docstrings = include_docstrings
        self._extensions: Set[str] = {
            self._normalize_extension(ext) for ext in extensions
        }
        self._dependency_registry = dependency_registry or optional_dependencies

        self._python_analyzer = FileAnalyzer(include_docstrings=include_docstrings)
        self._js_analyzer = JsAnalyzer(include_docstrings=include_docstrings)
        self._ts_analyzer = TsAnalyzer(include_docstrings=include_docstrings)
        self._tsx_analyzer = TsAnalyzer(
            include_docstrings=include_docstrings, is_tsx=True
        )
        self._c_analyzer = CAnalyzer(include_docstrings=include_docstrings)
        self._cpp_analyzer = CAnalyzer(
            include_docstrings=include_docstrings, is_cpp=True
        )
        self._html_analyzer = HtmlAnalyzer()
        self._plain_text_analyzer = PlainTextAnalyzer()

        self._mapping: Dict[str, AnalyzerProtocol] = {}
        override_map = self._build_override_map(overrides or {})
        for extension in self._extensions:
            analyzer = override_map.get(extension) or self._default_analyzer_for(
                extension
            )
            self._mapping[extension] = analyzer

        self._capabilities = self._build_capabilities(override_map)

    def get(self, extension: str) -> Optional[AnalyzerProtocol]:
        """Obtiene el analizador para una extensión de archivo."""
        return self._mapping.get(self._normalize_extension(extension))

    def items(self):
        """Itera sobre los pares (extensión, analizador) registrados."""
        return self._mapping.items()

    @property
    def analyzers(self) -> Dict[str, AnalyzerProtocol]:
        """Diccionario de los analizadores registrados."""
        return dict(self._mapping)

    @property
    def capabilities(self) -> List[AnalyzerCapability]:
        """Lista de las capacidades de los analizadores."""
        return list(self._capabilities)

    def _build_override_map(
        self, overrides: Mapping[str, AnalyzerProtocol]
    ) -> Dict[str, AnalyzerProtocol]:
        """Construye un mapa de analizadores personalizados."""
        return {
            self._normalize_extension(extension): analyzer
            for extension, analyzer in overrides.items()
        }

    def _default_analyzer_for(self, extension: str) -> AnalyzerProtocol:
        """Obtiene el analizador por defecto para una extensión de archivo."""
        if extension == ".py":
            return self._python_analyzer
        if extension in self.JS_EXTENSIONS:
            return self._js_analyzer
        if extension == ".ts":
            return self._ts_analyzer
        if extension == ".tsx":
            return self._tsx_analyzer
        if extension in self.C_EXTENSIONS:
            return self._c_analyzer
        if extension in self.CPP_EXTENSIONS:
            return self._cpp_analyzer
        if extension == ".html":
            return self._html_analyzer
        return self._plain_text_analyzer

    def _build_capabilities(
        self, overrides: Mapping[str, object]
    ) -> List[AnalyzerCapability]:
        """Construye la lista de capacidades de los analizadores."""
        capabilities: List[AnalyzerCapability] = []

        if ".py" in self._extensions:
            capabilities.append(
                AnalyzerCapability(
                    key="python",
                    description="Análisis de símbolos Python",
                    extensions=[".py"],
                    available=True,
                )
            )

        js_extensions = sorted(
            ext
            for ext in self._extensions
            if ext in self.JS_EXTENSIONS and ext not in overrides
        )
        if js_extensions:
            status = self._dependency_registry.status("esprima")[0]
            available = bool(
                status.available and getattr(self._js_analyzer, "available", False)
            )
            degraded = [] if available else js_extensions
            capabilities.append(
                AnalyzerCapability(
                    key="javascript",
                    description="Análisis de símbolos JavaScript/JSX",
                    extensions=js_extensions,
                    available=available,
                    dependency="esprima",
                    error=status.error,
                    degraded_extensions=degraded,
                )
            )

        ts_extensions = sorted(
            ext for ext in self._extensions if ext in {".ts"} and ext not in overrides
        )
        if ts_extensions:
            status = self._dependency_registry.status("tree_sitter_languages")[0]
            available = bool(
                status.available and getattr(self._ts_analyzer, "available", False)
            )
            degraded = [] if available else ts_extensions
            capabilities.append(
                AnalyzerCapability(
                    key="typescript",
                    description="Análisis de símbolos TypeScript",
                    extensions=ts_extensions,
                    available=available,
                    dependency="tree_sitter_languages",
                    error=status.error,
                    degraded_extensions=degraded,
                )
            )

        tsx_extensions = sorted(
            ext for ext in self._extensions if ext in {".tsx"} and ext not in overrides
        )
        if tsx_extensions:
            status = self._dependency_registry.status("tree_sitter_languages")[0]
            available = bool(
                status.available and getattr(self._tsx_analyzer, "available", False)
            )
            degraded = [] if available else tsx_extensions
            capabilities.append(
                AnalyzerCapability(
                    key="tsx",
                    description="Análisis de símbolos TSX",
                    extensions=tsx_extensions,
                    available=available,
                    dependency="tree_sitter_languages",
                    error=status.error,
                    degraded_extensions=degraded,
                )
            )

        html_extensions = sorted(
            ext for ext in self._extensions if ext == ".html" and ext not in overrides
        )
        if html_extensions:
            status = self._dependency_registry.status("beautifulsoup4")[0]
            available = bool(
                status.available and getattr(self._html_analyzer, "available", False)
            )
            degraded = [] if available else html_extensions
            capabilities.append(
                AnalyzerCapability(
                    key="html",
                    description="Extracción de elementos HTML",
                    extensions=html_extensions,
                    available=available,
                    dependency="beautifulsoup4",
                    error=status.error,
                    degraded_extensions=degraded,
                )
            )

        c_extensions = sorted(
            ext
            for ext in self._extensions
            if ext in self.C_EXTENSIONS and ext not in overrides
        )
        if c_extensions:
            status = self._dependency_registry.status("tree_sitter_languages")[0]
            available = bool(
                status.available and getattr(self._c_analyzer, "available", False)
            )
            degraded = [] if available else c_extensions
            capabilities.append(
                AnalyzerCapability(
                    key="c",
                    description="Análisis de símbolos C",
                    extensions=c_extensions,
                    available=available,
                    dependency="tree_sitter_languages",
                    error=status.error,
                    degraded_extensions=degraded,
                )
            )

        cpp_extensions = sorted(
            ext
            for ext in self._extensions
            if ext in self.CPP_EXTENSIONS and ext not in overrides
        )
        if cpp_extensions:
            status = self._dependency_registry.status("tree_sitter_languages")[0]
            available = bool(
                status.available and getattr(self._cpp_analyzer, "available", False)
            )
            degraded = [] if available else cpp_extensions
            capabilities.append(
                AnalyzerCapability(
                    key="cpp",
                    description="Análisis de símbolos C++",
                    extensions=cpp_extensions,
                    available=available,
                    dependency="tree_sitter_languages",
                    error=status.error,
                    degraded_extensions=degraded,
                )
            )

        return capabilities

    @staticmethod
    def _normalize_extension(extension: str) -> str:
        """Normaliza una extensión de archivo."""
        ext = extension if extension.startswith(".") else f".{extension}"
        return ext.lower()
