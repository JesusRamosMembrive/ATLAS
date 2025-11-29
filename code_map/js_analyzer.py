# SPDX-License-Identifier: MIT
"""
Analizador para archivos JavaScript/TypeScript usando esprima.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any, Dict, List, Optional

from .analyzer import get_modified_time
from .models import AnalysisError
from .dependencies import optional_dependencies
from .models import FileSummary, SymbolInfo, SymbolKind

logger = logging.getLogger(__name__)


def _node_get(node: Any, key: str, default: Any = None) -> Any:
    """Obtiene una propiedad desde dict o nodo de esprima."""
    if node is None:
        return default
    if isinstance(node, Mapping):
        return node.get(key, default)
    value = getattr(node, key, default)
    if callable(value):
        try:
            return value()
        except TypeError:
            return default
    return value


def _ensure_list(value: Any) -> List[Any]:
    """Normaliza cualquier iterable en lista estándar."""
    if not value:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
        return list(value)
    return [value]


class JsAnalyzer:
    """Analizador que extrae símbolos JavaScript/JSX usando esprima."""

    def __init__(self, *, include_docstrings: bool = True) -> None:
        """Inicializa el analizador y carga esprima si está disponible."""
        self.include_docstrings = include_docstrings
        self._module = optional_dependencies.require("esprima")
        status = optional_dependencies.status("esprima")[0]
        self.available = status.available

    def parse(self, path: Path) -> FileSummary:
        """
        Analiza un archivo JavaScript/JSX y devuelve los símbolos encontrados.

        Args:
            path: Ruta del archivo a analizar.
        """
        abs_path = path.resolve()
        if not self._module:
            error = AnalysisError(
                message="esprima no disponible; análisis de JS degradado.",
                lineno=None,
                col_offset=None,
            )
            return FileSummary(
                path=abs_path,
                symbols=[],
                errors=[error],
                modified_at=get_modified_time(abs_path),
            )

        try:
            source = abs_path.read_text(encoding="utf-8")
        except OSError as exc:
            error = AnalysisError(
                message=f"No se pudo leer el archivo: {exc}",
                lineno=None,
                col_offset=None,
            )
            return FileSummary(
                path=abs_path,
                symbols=[],
                errors=[error],
                modified_at=None,
            )

        try:
            module = self._module.parseModule(  # type: ignore[attr-defined]
                source, comment=True, range=True, loc=True, tolerant=True
            )
        except Exception as exc:  # pragma: no cover
            # Intentional broad exception: graceful degradation for any parser error
            # (malformed JS, unsupported syntax, encoding issues, etc.)
            logger.debug("Error parseando %s: %s", abs_path, exc)
            error = AnalysisError(
                message=f"No se pudo parsear el archivo: {exc}",
                lineno=None,
                col_offset=None,
            )
            return FileSummary(
                path=abs_path,
                symbols=[],
                errors=[error],
                modified_at=get_modified_time(abs_path),
            )

        comments = _ensure_list(_node_get(module, "comments", []))
        body = _ensure_list(_node_get(module, "body", []))
        if not body and hasattr(module, "toDict"):
            try:
                data = module.toDict()  # type: ignore[attr-defined]
                comments = _ensure_list(data.get("comments", []) or comments)
                body = _ensure_list(data.get("body", []))
            except Exception:  # pragma: no cover
                # Intentional broad exception: fallback for esprima API variations
                body = body or []

        comment_map = self._build_comment_map(comments)

        symbols: List[SymbolInfo] = []
        for node in body:
            self._collect_from_node(
                node, symbols, comment_map, parent=None, file_path=abs_path
            )

        return FileSummary(
            path=abs_path,
            symbols=symbols,
            errors=[],
            modified_at=get_modified_time(abs_path),
        )

    def _collect_from_node(
        self,
        node: Dict[str, Any],
        symbols: List[SymbolInfo],
        comment_map: Dict[int, str],
        parent: Optional[str],
        file_path: Path,
    ) -> None:
        """Recorre un nodo del AST y acumula símbolos relevantes."""
        node_type = _node_get(node, "type")

        if node_type == "FunctionDeclaration":
            name = _node_get(_node_get(node, "id", {}), "name")
            if name:
                line = _node_get(
                    _node_get(_node_get(node, "loc", {}), "start", {}), "line"
                )
                doc = self._docstring_for(line, comment_map)
                symbols.append(
                    SymbolInfo(
                        name=name,
                        kind=SymbolKind.FUNCTION,
                        path=file_path,
                        lineno=line or 0,
                        docstring=doc,
                    )
                )
        elif node_type == "ClassDeclaration":
            class_name = _node_get(_node_get(node, "id", {}), "name")
            line = _node_get(_node_get(_node_get(node, "loc", {}), "start", {}), "line")
            doc = self._docstring_for(line, comment_map)
            if class_name:
                symbols.append(
                    SymbolInfo(
                        name=class_name,
                        kind=SymbolKind.CLASS,
                        path=file_path,
                        lineno=line or 0,
                        docstring=doc,
                    )
                )
                body = _node_get(node, "body", {}) or {}
                for item in _ensure_list(_node_get(body, "body", [])):
                    if _node_get(item, "type") == "MethodDefinition":
                        method_name = self._method_name(item)
                        if method_name:
                            method_line = _node_get(
                                _node_get(_node_get(item, "value", {}), "loc", {}),
                                "start",
                                {},
                            )
                            method_line = _node_get(method_line, "line")
                            method_doc = self._docstring_for(method_line, comment_map)
                            symbols.append(
                                SymbolInfo(
                                    name=method_name,
                                    kind=SymbolKind.METHOD,
                                    parent=class_name,
                                    path=file_path,
                                    lineno=method_line or 0,
                                    docstring=method_doc,
                                )
                            )
        elif node_type in {"ExportNamedDeclaration", "ExportDefaultDeclaration"}:
            declaration = _node_get(node, "declaration")
            if declaration:
                self._collect_from_node(
                    declaration, symbols, comment_map, parent=None, file_path=file_path
                )
        elif node_type == "VariableDeclaration":
            for declarator in _ensure_list(_node_get(node, "declarations", [])):
                self._handle_variable_declarator(
                    declarator, symbols, comment_map, file_path
                )

    def _handle_variable_declarator(
        self,
        declarator: Dict[str, Any],
        symbols: List[SymbolInfo],
        comment_map: Dict[int, str],
        file_path: Path,
    ) -> None:
        """Registra funciones declaradas mediante asignaciones de variables."""
        id_node = _node_get(declarator, "id")
        init = _node_get(declarator, "init")
        if not id_node or not init:
            return

        name = _node_get(id_node, "name")
        init_type = _node_get(init, "type")
        if name and init_type in {"FunctionExpression", "ArrowFunctionExpression"}:
            line = _node_get(_node_get(_node_get(init, "loc", {}), "start", {}), "line")
            doc = self._docstring_for(line, comment_map)
            symbols.append(
                SymbolInfo(
                    name=name,
                    kind=SymbolKind.FUNCTION,
                    path=file_path,
                    lineno=line or 0,
                    docstring=doc,
                )
            )

    def _method_name(self, node: Dict[str, Any]) -> Optional[str]:
        """Obtiene el nombre legible de un método de clase."""
        key = _node_get(node, "key")
        if not key:
            return None
        key_type = _node_get(key, "type")
        if key_type == "Identifier":
            return _node_get(key, "name")
        if key_type == "Literal":
            return str(_node_get(key, "value"))
        return None

    def _build_comment_map(self, comments: List[Any]) -> Dict[int, str]:
        """Asocia comentarios finales con la línea donde finalizan."""
        if not self.include_docstrings:
            return {}
        result: Dict[int, str] = {}
        for comment in comments:
            loc = _node_get(comment, "loc")
            if not loc:
                continue
            end_line = _node_get(_node_get(loc, "end", {}), "line")
            if end_line is None:
                continue
            value = _node_get(comment, "value", "")
            cleaned = self._clean_comment(value)
            result[end_line] = cleaned
        return result

    def _docstring_for(
        self, line: Optional[int], comment_map: Dict[int, str]
    ) -> Optional[str]:
        """Busca un comentario inmediatamente anterior a la línea indicada."""
        if not self.include_docstrings or line is None:
            return None
        # Buscar comentario inmediatamente anterior (línea anterior o dos líneas antes).
        for offset in (1, 2):
            doc = comment_map.get(line - offset)
            if doc:
                return doc
        return None

    def _clean_comment(self, value: str) -> str:
        """Limpia anotaciones JSDoc y devuelve texto plano."""
        stripped = value.strip()
        # Eliminar asteriscos de bloque JSDoc
        lines = [line.strip(" *") for line in stripped.splitlines()]
        return " ".join(line for line in lines if line).strip()
