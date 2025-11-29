# SPDX-License-Identifier: MIT
"""
Analizador para archivos TypeScript / TSX usando tree-sitter.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from .analyzer import get_modified_time
from .dependencies import optional_dependencies
from .models import AnalysisError, FileSummary, SymbolInfo, SymbolKind


@dataclass
class _TsParser:
    """Wrapper ligero sobre el parser de tree-sitter."""

    parser: Any

    @classmethod
    def for_language(cls, modules: Dict[str, Any], name: str) -> "_TsParser":
        """Construye un parser configurado para el lenguaje indicado."""
        parser_cls = getattr(modules.get("tree_sitter"), "Parser", None)
        get_language = getattr(
            modules.get("tree_sitter_languages"), "get_language", None
        )
        if parser_cls is None or get_language is None:
            raise RuntimeError("tree_sitter_languages no disponible")
        language = get_language(name)
        parser = parser_cls()
        parser.set_language(language)
        return cls(parser=parser)


class TsAnalyzer:
    """Analizador basado en tree-sitter para archivos TypeScript/TSX."""

    def __init__(
        self, *, include_docstrings: bool = False, is_tsx: bool = False
    ) -> None:
        """Inicializa el parser adecuado y comprueba la disponibilidad de dependencias."""
        self.include_docstrings = include_docstrings
        self._modules = optional_dependencies.load("tree_sitter_languages")
        status = optional_dependencies.status("tree_sitter_languages")[0]
        self.parser_wrapper = None
        if self._modules:
            try:
                self.parser_wrapper = _TsParser.for_language(
                    self._modules,
                    "tsx" if is_tsx else "typescript",
                )
            except Exception:  # pragma: no cover
                self.parser_wrapper = None
        self.available = bool(status.available and self.parser_wrapper)

    def parse(self, path: Path) -> FileSummary:
        """
        Analiza un archivo TypeScript/TSX y devuelve los símbolos detectados.

        Args:
            path: Ruta del archivo a analizar.
        """
        abs_path = path.resolve()
        try:
            source = abs_path.read_text(encoding="utf-8")
        except OSError as exc:
            error = AnalysisError(message=f"No se pudo leer el archivo: {exc}")
            return FileSummary(
                path=abs_path, symbols=[], errors=[error], modified_at=None
            )

        if not self.parser_wrapper:
            error = AnalysisError(
                message="tree_sitter_languages no disponible; análisis TS/TSX degradado."
            )
            return FileSummary(
                path=abs_path,
                symbols=[],
                errors=[error],
                modified_at=get_modified_time(abs_path),
            )

        tree = self.parser_wrapper.parser.parse(bytes(source, "utf-8"))
        symbols: List[SymbolInfo] = []
        root = tree.root_node
        self._collect_from_children(root, path, symbols, source.splitlines())

        return FileSummary(
            path=abs_path,
            symbols=symbols,
            errors=[],
            modified_at=get_modified_time(abs_path),
        )

    def _collect_from_children(
        self,
        node: Any,
        file_path: Path,
        symbols: List[SymbolInfo],
        lines: List[str],
        parent: Optional[str] = None,
    ) -> None:
        """Recorre recursivamente el árbol sintáctico para extraer símbolos."""
        for child in node.children:
            if child.type in {"function_declaration", "method_definition"}:
                name = self._extract_identifier(child)
                if not name:
                    continue
                lineno = child.start_point[0] + 1
                doc = (
                    self._find_leading_comment(child, lines)
                    if self.include_docstrings
                    else None
                )
                kind = (
                    SymbolKind.METHOD
                    if parent and child.type == "method_definition"
                    else SymbolKind.FUNCTION
                )
                symbols.append(
                    SymbolInfo(
                        name=name,
                        kind=kind,
                        parent=parent if kind is SymbolKind.METHOD else None,
                        path=file_path,
                        lineno=lineno,
                        docstring=doc,
                    )
                )
                if child.type == "method_definition":
                    continue
            elif child.type == "class_declaration":
                class_name = self._extract_identifier(child)
                if class_name:
                    lineno = child.start_point[0] + 1
                    doc = (
                        self._find_leading_comment(child, lines)
                        if self.include_docstrings
                        else None
                    )
                    symbols.append(
                        SymbolInfo(
                            name=class_name,
                            kind=SymbolKind.CLASS,
                            path=file_path,
                            lineno=lineno,
                            docstring=doc,
                        )
                    )
                    body = self._find_child(child, "class_body")
                    if body:
                        self._collect_from_children(
                            body, file_path, symbols, lines, parent=class_name
                        )
                    continue
            elif child.type == "lexical_declaration":
                self._handle_lexical_declaration(child, file_path, symbols, lines)

            self._collect_from_children(child, file_path, symbols, lines, parent)

    def _extract_identifier(self, node: Any) -> Optional[str]:
        """Obtiene el identificador asociado a un nodo, si existe."""
        ident = self._find_child(node, "identifier")
        if ident:
            return ident.text.decode("utf-8")
        name = node.child_by_field_name("name")
        if name and name.type in {
            "identifier",
            "type_identifier",
            "property_identifier",
        }:
            return name.text.decode("utf-8")
        type_ident = self._find_child(node, "type_identifier")
        if type_ident:
            return type_ident.text.decode("utf-8")
        return None

    def _find_child(self, node: Any, type_name: str) -> Optional[Any]:
        """Busca el primer hijo del tipo indicado dentro de un nodo."""
        for child in node.children:
            if child.type == type_name:
                return child
        return None

    def _handle_lexical_declaration(
        self,
        node: Any,
        file_path: Path,
        symbols: List[SymbolInfo],
        lines: List[str],
    ) -> None:
        """Detecta asignaciones con funciones flecha o estándar y las registra."""
        for child in node.children:
            if child.type == "variable_declarator":
                ident = child.child_by_field_name("name")
                initializer = child.child_by_field_name("value")
                if (
                    ident
                    and initializer
                    and initializer.type in {"arrow_function", "function"}
                ):
                    name = ident.text.decode("utf-8")
                    lineno = initializer.start_point[0] + 1
                    doc = (
                        self._find_leading_comment(child, lines)
                        if self.include_docstrings
                        else None
                    )
                    symbols.append(
                        SymbolInfo(
                            name=name,
                            kind=SymbolKind.FUNCTION,
                            path=file_path,
                            lineno=lineno,
                            docstring=doc,
                        )
                    )

    def _find_leading_comment(self, node: Any, lines: List[str]) -> Optional[str]:
        """Localiza comentarios inmediatamente anteriores a un nodo."""
        start_line = node.start_point[0]
        for offset in range(1, 4):
            index = start_line - offset
            if index < 0:
                break
            text = lines[index].strip()
            if text.startswith("//"):
                return text[2:].strip()
            if text.startswith("/*"):
                comment_lines: List[str] = []
                j = index
                while j >= 0:
                    line = lines[j].strip()
                    comment_lines.insert(0, line)
                    if "/*" in line:
                        break
                    j -= 1
                cleaned = [segment.strip("/* ") for segment in comment_lines]
                return " ".join(cleaned).strip()
            if text:
                break
        return None
