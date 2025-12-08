# SPDX-License-Identifier: MIT
"""
Analizador para archivos C/C++ usando tree-sitter.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from .analyzer import get_modified_time
from .dependencies import optional_dependencies
from .models import AnalysisError, FileSummary, SymbolInfo, SymbolKind


@dataclass
class _CParser:
    """Wrapper ligero sobre el parser de tree-sitter para C/C++."""

    parser: Any

    @classmethod
    def for_language(cls, modules: Dict[str, Any], name: str) -> "_CParser":
        """Construye un parser configurado para el lenguaje indicado (c o cpp)."""
        import warnings

        parser_cls = getattr(modules.get("tree_sitter"), "Parser", None)
        get_language = getattr(
            modules.get("tree_sitter_languages"), "get_language", None
        )
        if parser_cls is None or get_language is None:
            raise RuntimeError("tree_sitter_languages no disponible")
            
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=FutureWarning)
            language = get_language(name)
            
        parser = parser_cls()
        parser.set_language(language)
        return cls(parser=parser)


class CAnalyzer:
    """Analizador basado en tree-sitter para archivos C/C++."""

    def __init__(
        self, *, include_docstrings: bool = False, is_cpp: bool = False
    ) -> None:
        """Inicializa el parser adecuado y comprueba la disponibilidad de dependencias."""
        self.include_docstrings = include_docstrings
        self.is_cpp = is_cpp
        self._modules = optional_dependencies.load("tree_sitter_languages")
        status = optional_dependencies.status("tree_sitter_languages")[0]
        self.parser_wrapper = None
        if self._modules:
            try:
                self.parser_wrapper = _CParser.for_language(
                    self._modules,
                    "cpp" if is_cpp else "c",
                )
            except Exception:  # pragma: no cover
                self.parser_wrapper = None
        self.available = bool(status.available and self.parser_wrapper)

    def parse(self, path: Path) -> FileSummary:
        """
        Analiza un archivo C/C++ y devuelve los símbolos detectados.

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

        lang_name = "C++" if self.is_cpp else "C"
        if not self.parser_wrapper:
            error = AnalysisError(
                message=f"tree_sitter_languages no disponible; análisis {lang_name} degradado."
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


    def _calculate_complexity(self, node: Any) -> int:
        """Calcula la complejidad ciclomática de un nodo (función)."""
        count = 0
        to_visit = [node]
        while to_visit:
            curr = to_visit.pop()
            if curr.type in {
                "if_statement",
                "while_statement",
                "for_statement",
                "case_statement",
                "catch_clause",
                "conditional_expression",
            }:
                count += 1
            to_visit.extend(curr.children)
        return 1 + count

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
            # Funciones (C y C++)
            if child.type == "function_definition":
                name = self._extract_function_name(child)
                if name:
                    lineno = child.start_point[0] + 1
                    doc = (
                        self._find_leading_comment(child, lines)
                        if self.include_docstrings
                        else None
                    )
                    kind = SymbolKind.METHOD if parent else SymbolKind.FUNCTION
                    symbols.append(
                        SymbolInfo(
                            name=name,
                            kind=kind,
                            parent=parent if kind is SymbolKind.METHOD else None,
                            path=file_path,
                            lineno=lineno,
                            docstring=doc,
                            metrics={
                                "loc": child.end_point[0] - child.start_point[0] + 1,
                                "complexity": self._calculate_complexity(child),
                            },
                        )
                    )
                    continue

            # Declaraciones de funciones (prototipos)
            elif child.type == "declaration":
                func_name = self._extract_function_declaration_name(child)
                if func_name:
                    lineno = child.start_point[0] + 1
                    doc = (
                        self._find_leading_comment(child, lines)
                        if self.include_docstrings
                        else None
                    )
                    symbols.append(
                        SymbolInfo(
                            name=func_name,
                            kind=SymbolKind.FUNCTION,
                            path=file_path,
                            lineno=lineno,
                            docstring=doc,
                        )
                    )

            # Structs (C y C++)
            elif child.type == "struct_specifier":
                struct_name = self._extract_type_name(child)
                if struct_name:
                    lineno = child.start_point[0] + 1
                    doc = (
                        self._find_leading_comment(child, lines)
                        if self.include_docstrings
                        else None
                    )
                    symbols.append(
                        SymbolInfo(
                            name=struct_name,
                            kind=SymbolKind.CLASS,
                            path=file_path,
                            lineno=lineno,
                            docstring=doc,
                        )
                    )

            # Clases (C++ solamente)
            elif child.type == "class_specifier":
                class_name = self._extract_type_name(child)
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
                    # Procesar métodos dentro de la clase
                    body = self._find_child(child, "field_declaration_list")
                    if body:
                        self._collect_from_children(
                            body, file_path, symbols, lines, parent=class_name
                        )
                    continue

            # Enums
            elif child.type == "enum_specifier":
                enum_name = self._extract_type_name(child)
                if enum_name:
                    lineno = child.start_point[0] + 1
                    doc = (
                        self._find_leading_comment(child, lines)
                        if self.include_docstrings
                        else None
                    )
                    symbols.append(
                        SymbolInfo(
                            name=enum_name,
                            kind=SymbolKind.CLASS,  # Usamos CLASS para enums
                            path=file_path,
                            lineno=lineno,
                            docstring=doc,
                        )
                    )

            # Namespaces (C++ solamente)
            elif child.type == "namespace_definition":
                ns_name = self._extract_identifier(child)
                if ns_name:
                    lineno = child.start_point[0] + 1
                    symbols.append(
                        SymbolInfo(
                            name=ns_name,
                            kind=SymbolKind.CLASS,  # Usamos CLASS para namespaces
                            path=file_path,
                            lineno=lineno,
                        )
                    )
                    # Procesar contenido del namespace
                    body = self._find_child(child, "declaration_list")
                    if body:
                        self._collect_from_children(
                            body, file_path, symbols, lines, parent=ns_name
                        )
                    continue

            # Typedef (C y C++)
            elif child.type == "type_definition":
                typedef_name = self._extract_typedef_name(child)
                if typedef_name:
                    lineno = child.start_point[0] + 1
                    symbols.append(
                        SymbolInfo(
                            name=typedef_name,
                            kind=SymbolKind.CLASS,
                            path=file_path,
                            lineno=lineno,
                        )
                    )

            # Continuar recursivamente para otros nodos
            self._collect_from_children(child, file_path, symbols, lines, parent)

    def _extract_function_name(self, node: Any) -> Optional[str]:
        """Extrae el nombre de una definición de función."""
        declarator = node.child_by_field_name("declarator")
        if not declarator:
            return None

        # Buscar el identificador dentro del declarador
        return self._find_declarator_name(declarator)

    def _find_declarator_name(self, declarator: Any) -> Optional[str]:
        """Busca recursivamente el nombre en un declarador."""
        if declarator.type == "identifier":
            return declarator.text.decode("utf-8")

        if declarator.type == "function_declarator":
            inner = declarator.child_by_field_name("declarator")
            if inner:
                return self._find_declarator_name(inner)

        if declarator.type == "pointer_declarator":
            inner = declarator.child_by_field_name("declarator")
            if inner:
                return self._find_declarator_name(inner)

        # Para qualified_identifier en C++ (e.g., ClassName::methodName)
        if declarator.type == "qualified_identifier":
            name = declarator.child_by_field_name("name")
            if name:
                return name.text.decode("utf-8")

        # Buscar identifier en los hijos
        for child in declarator.children:
            if child.type == "identifier":
                return child.text.decode("utf-8")
            if child.type in {
                "function_declarator",
                "pointer_declarator",
                "qualified_identifier",
            }:
                result = self._find_declarator_name(child)
                if result:
                    return result

        return None

    def _extract_function_declaration_name(self, node: Any) -> Optional[str]:
        """Extrae el nombre de una declaración de función (prototipo)."""
        declarator = node.child_by_field_name("declarator")
        if not declarator:
            return None

        # Solo es una declaración de función si tiene function_declarator
        if declarator.type == "function_declarator":
            return self._find_declarator_name(declarator)

        # Buscar function_declarator en los hijos
        func_decl = self._find_child(declarator, "function_declarator")
        if func_decl:
            return self._find_declarator_name(func_decl)

        return None

    def _extract_type_name(self, node: Any) -> Optional[str]:
        """Extrae el nombre de un struct, class o enum."""
        name = node.child_by_field_name("name")
        if name and name.type == "type_identifier":
            return name.text.decode("utf-8")

        # Buscar type_identifier directo en los hijos
        for child in node.children:
            if child.type == "type_identifier":
                return child.text.decode("utf-8")

        return None

    def _extract_typedef_name(self, node: Any) -> Optional[str]:
        """Extrae el nombre del tipo definido por typedef."""
        declarator = node.child_by_field_name("declarator")
        if declarator:
            if declarator.type == "type_identifier":
                return declarator.text.decode("utf-8")
            return self._find_declarator_name(declarator)
        return None

    def _extract_identifier(self, node: Any) -> Optional[str]:
        """Obtiene el identificador asociado a un nodo, si existe."""
        name = node.child_by_field_name("name")
        if name and name.type == "identifier":
            return name.text.decode("utf-8")

        for child in node.children:
            if child.type == "identifier":
                return child.text.decode("utf-8")

        return None

    def _find_child(self, node: Any, type_name: str) -> Optional[Any]:
        """Busca el primer hijo del tipo indicado dentro de un nodo."""
        for child in node.children:
            if child.type == type_name:
                return child
        return None

    def _find_leading_comment(self, node: Any, lines: List[str]) -> Optional[str]:
        """Localiza comentarios inmediatamente anteriores a un nodo."""
        start_line = node.start_point[0]
        for offset in range(1, 4):
            index = start_line - offset
            if index < 0:
                break
            text = lines[index].strip()
            # Comentario de una línea estilo C++
            if text.startswith("//"):
                return text[2:].strip()
            # Comentario de bloque
            if text.endswith("*/"):
                comment_lines: List[str] = []
                j = index
                while j >= 0:
                    line = lines[j].strip()
                    comment_lines.insert(0, line)
                    if line.startswith("/*"):
                        break
                    j -= 1
                cleaned = [
                    segment.strip("/* ").strip("* ") for segment in comment_lines
                ]
                return " ".join(c for c in cleaned if c).strip()
            if text:
                break
        return None
