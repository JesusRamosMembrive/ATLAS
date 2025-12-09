# SPDX-License-Identifier: MIT
"""
Lógica de análisis individual de archivos Python usando AST.
"""

from __future__ import annotations

import ast
import tokenize
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Optional, Union

from .models import AnalysisError, FileSummary, SymbolInfo, SymbolKind


def get_modified_time(path: Path) -> Optional[datetime]:
    """
    Obtiene la última modificación del archivo en UTC.

    Args:
        path (Path): Ruta al archivo del cual obtener la fecha de modificación

    Returns:
        Optional[datetime]: Fecha de última modificación en UTC, o None si hay error
                           al acceder al archivo (permisos, archivo no existe, etc.)

    Notes:
        - Usa stat().st_mtime del sistema de archivos
        - Convierte automáticamente a timezone UTC
        - Maneja OSError silenciosamente retornando None
    """
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    except OSError:
        return None


AstFunction = Union[ast.FunctionDef, ast.AsyncFunctionDef]


class ComplexityVisitor(ast.NodeVisitor):
    """
    Calcula la complejidad ciclomática (McCabe) de un nodo AST.
    """

    def __init__(self) -> None:
        self.complexity = 1

    def visit_If(self, node: ast.If) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_While(self, node: ast.While) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        self.complexity += 1
        self.generic_visit(node)

    def visit_MatchCase(self, node: ast.AST) -> None:
        # Soporte para Python 3.10+
        self.complexity += 1
        self.generic_visit(node)


def calculate_complexity(node: ast.AST) -> int:
    visitor = ComplexityVisitor()
    visitor.visit(node)
    return visitor.complexity

class FileAnalyzer:
    """
    Extrae símbolos soportados (funciones, clases, métodos) de un archivo Python.

    Utiliza el módulo AST (Abstract Syntax Tree) de Python para parsear archivos
    de código fuente y extraer información estructural sobre funciones, clases y
    métodos, incluyendo sus docstrings y ubicaciones.

    Attributes:
        include_docstrings (bool): Si True, incluye los docstrings de los símbolos
                                   en la información extraída

    Notes:
        - Maneja errores de sintaxis gracefully (continúa el análisis)
        - Detecta automáticamente la codificación del archivo
        - Soporta funciones síncronas y asíncronas
        - Extrae jerarquía completa de clases y sus métodos
    """

    def __init__(self, *, include_docstrings: bool = False) -> None:
        """
        Inicializa el analizador de archivos.

        Args:
            include_docstrings (bool): Si True, los docstrings serán incluidos en
                                       los símbolos extraídos. Default: False

        Notes:
            - Keyword-only argument para claridad
            - include_docstrings=False ahorra memoria en proyectos grandes
        """
        self.include_docstrings = include_docstrings

    def parse(self, path: Path) -> FileSummary:
        """
        Analiza un archivo Python y devuelve los símbolos detectados.

        Args:
            path: Ruta del archivo a inspeccionar.

        Returns:
            Un resumen con símbolos y errores asociados al archivo.
        """
        abs_path = Path(path).resolve()
        try:
            source = self._read_source(abs_path)
            tree = ast.parse(source, filename=str(abs_path))
        except SyntaxError as exc:  # análisis continúa pese a errores
            error = AnalysisError(
                message=str(exc.msg),
                lineno=exc.lineno,
                col_offset=exc.offset,
            )
            return FileSummary(
                path=abs_path,
                symbols=[],
                errors=[error],
                modified_at=get_modified_time(abs_path),
            )
        except OSError as exc:
            error = AnalysisError(message=f"No se pudo leer el archivo: {exc}")
            return FileSummary(path=abs_path, errors=[error])

        symbols: List[SymbolInfo] = []

        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                symbols.append(self._build_function_symbol(node, abs_path))
            elif isinstance(node, ast.ClassDef):
                symbols.append(self._build_class_symbol(node, abs_path))
                symbols.extend(self._build_method_symbols(node, abs_path))

        return FileSummary(
            path=abs_path,
            symbols=symbols,
            modified_at=get_modified_time(abs_path),
        )

    def _read_source(self, path: Path) -> str:
        """
        Lee el archivo detectando la codificación declarada.

        Utiliza tokenize.detect_encoding() para respetar las declaraciones de
        codificación en el archivo (PEP 263: # -*- coding: utf-8 -*-).

        Args:
            path (Path): Ruta al archivo a leer

        Returns:
            str: Contenido completo del archivo decodificado

        Raises:
            UnicodeDecodeError: Si la codificación detectada es incorrecta
            OSError: Si el archivo no puede ser leído

        Notes:
            - Respeta declaraciones de encoding en la primera o segunda línea
            - Fallback a UTF-8 si no hay declaración explícita
            - Abre en modo binario para detección correcta
        """
        with path.open("rb") as buffer:
            encoding, _ = tokenize.detect_encoding(buffer.readline)
            buffer.seek(0)
            data = buffer.read()
        return data.decode(encoding)

    def _build_function_symbol(self, node: AstFunction, path: Path) -> SymbolInfo:
        """
        Crea la representación de símbolo para una función o corrutina.

        Args:
            node (AstFunction): Nodo AST de tipo FunctionDef o AsyncFunctionDef
            path (Path): Ruta del archivo donde se encuentra la función

        Returns:
            SymbolInfo: Información estructurada del símbolo función

        Notes:
            - Soporta tanto funciones síncronas como asíncronas (async def)
            - Extrae nombre, ubicación (lineno) y opcionalmente docstring
            - No distingue entre función sync y async en el tipo retornado
        """
        return SymbolInfo(
            name=node.name,
            kind=SymbolKind.FUNCTION,
            path=path,
            lineno=node.lineno,
            docstring=self._docstring_for(node),
            metrics={
                "loc": (node.end_lineno or node.lineno) - node.lineno + 1,
                "complexity": calculate_complexity(node),
            },
        )

    def _build_class_symbol(self, node: ast.ClassDef, path: Path) -> SymbolInfo:
        """
        Crea la representación de símbolo para una clase.

        Args:
            node (ast.ClassDef): Nodo AST de tipo ClassDef
            path (Path): Ruta del archivo donde se encuentra la clase

        Returns:
            SymbolInfo: Información estructurada del símbolo clase

        Notes:
            - Solo procesa la definición de la clase (no sus métodos)
            - Los métodos se procesan por separado en _build_method_symbols()
            - Extrae docstring de clase si include_docstrings=True
        """
        return SymbolInfo(
            name=node.name,
            kind=SymbolKind.CLASS,
            path=path,
            lineno=node.lineno,
            docstring=self._docstring_for(node),
        )

    def _build_method_symbols(
        self, class_node: ast.ClassDef, path: Path
    ) -> Iterable[SymbolInfo]:
        """Genera símbolos para los métodos definidos dentro de una clase."""
        for item in class_node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                yield SymbolInfo(
                    name=item.name,
                    kind=SymbolKind.METHOD,
                    path=path,
                    lineno=item.lineno,
                    parent=class_node.name,
                    docstring=self._docstring_for(item),
                    metrics={
                        "loc": (item.end_lineno or item.lineno) - item.lineno + 1,
                        "complexity": calculate_complexity(item),
                    },
                )

    def _docstring_for(self, node: ast.AST) -> Optional[str]:
        """Recupera el docstring del nodo si está habilitado."""
        if not self.include_docstrings:
            return None
        if not isinstance(
            node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Module)
        ):
            return None
        return ast.get_docstring(node)
