# SPDX-License-Identifier: MIT
"""
Dataclasses y tipos para representar la información del análisis.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Union


class SymbolKind(str, Enum):
    """
    Tipos de símbolos soportados por el motor de análisis.

    Enum de tipo string para facilitar serialización a JSON y comparaciones.

    Valores:
        FUNCTION: Función o corrutina de nivel módulo
        CLASS: Definición de clase
        METHOD: Método dentro de una clase (incluye métodos estáticos/clase)
        ELEMENT: Elemento HTML/DOM (para análisis de templates/HTML)

    Notes:
        - Hereda de str para compatibilidad con JSON
        - Extensible: agregar nuevos tipos (VARIABLE, CONSTANT, etc.)
        - Usado en SymbolInfo.kind para clasificación
    """

    FUNCTION = "function"
    CLASS = "class"
    METHOD = "method"
    ELEMENT = "element"


@dataclass(slots=True)
class SymbolInfo:
    """
    Representa una función libre, una clase o un método detectado en un archivo.

    Estructura optimizada (slots=True) para representar símbolos extraídos del
    código fuente. `parent` se utiliza para enlazar métodos con la clase que
    los contiene, permitiendo reconstruir la jerarquía.

    Attributes:
        name (str): Nombre del símbolo (función, clase, método)
        kind (SymbolKind): Tipo de símbolo (FUNCTION, CLASS, METHOD, ELEMENT)
        path (Path): Ruta absoluta al archivo que contiene el símbolo
        lineno (int): Número de línea donde inicia la definición (1-indexed)
        parent (Optional[str]): Nombre de la clase padre (solo para métodos)
        docstring (Optional[str]): Docstring del símbolo (si include_docstrings=True)

    Examples:
        >>> # Función de nivel módulo
        >>> SymbolInfo(name="parse", kind=SymbolKind.FUNCTION, path=Path("parser.py"), lineno=42)

        >>> # Método de clase
        >>> SymbolInfo(name="connect", kind=SymbolKind.METHOD, path=Path("db.py"),
        ...            lineno=15, parent="Database")

    Notes:
        - slots=True reduce uso de memoria (sin __dict__)
        - parent=None indica símbolo de nivel módulo
        - lineno sigue convención Python (empieza en 1)
        - docstring=None si include_docstrings=False o no hay docstring
    """

    name: str
    kind: SymbolKind
    path: Path
    lineno: int
    parent: Optional[str] = None
    docstring: Optional[str] = None
    metrics: Dict[str, Union[int, float]] = field(default_factory=dict)


@dataclass(slots=True)
class AnalysisError:
    """
    Errores asociados al procesamiento de un archivo.

    Representa errores de sintaxis, encoding, o lectura encontrados durante
    el análisis de un archivo de código fuente.

    Attributes:
        message (str): Descripción del error
        lineno (Optional[int]): Número de línea donde ocurrió el error (si aplica)
        col_offset (Optional[int]): Columna donde ocurrió el error (si aplica)

    Notes:
        - lineno/col_offset son None para errores de lectura de archivo
        - Para SyntaxError, lineno/col_offset vienen del parser de Python
        - Permite continuar el análisis pese a errores en archivos individuales
        - Usado en FileSummary.errors
    """

    message: str
    lineno: Optional[int] = None
    col_offset: Optional[int] = None


@dataclass(slots=True)
class FileSummary:
    """
    Resumen de símbolos y errores de un archivo concreto.

    Agrupa toda la información extraída de un único archivo de código fuente,
    incluyendo símbolos detectados, errores encontrados y metadata.

    Attributes:
        path (Path): Ruta absoluta al archivo analizado
        symbols (List[SymbolInfo]): Lista de símbolos extraídos (funciones, clases, métodos)
        errors (List[AnalysisError]): Lista de errores encontrados durante el análisis
        modified_at (Optional[datetime]): Fecha de última modificación del archivo (UTC)

    Methods:
        has_errors(): Verifica si el análisis encontró errores

    Notes:
        - symbols puede estar vacío si el archivo no contiene definiciones
        - errors vacío indica análisis exitoso
        - modified_at=None indica que no se pudo obtener metadata del archivo
        - Usado por ProjectScanner como unidad básica de análisis
    """

    path: Path
    symbols: List[SymbolInfo] = field(default_factory=list)
    errors: List[AnalysisError] = field(default_factory=list)
    modified_at: Optional[datetime] = None

    def has_errors(self) -> bool:
        """
        Indica si el archivo contiene errores asociados al análisis.

        Returns:
            bool: True si hay al menos un error, False si el análisis fue exitoso

        Notes:
            - Útil para filtrar archivos con problemas
            - No distingue entre tipos de error (sintaxis, encoding, lectura)
        """
        return bool(self.errors)


@dataclass(slots=True)
class ProjectTreeNode:
    """
    Nodo de la jerarquía carpeta → archivo → símbolos.

    Representa un elemento en el árbol de estructura del proyecto. Puede ser
    un directorio (con hijos) o un archivo (con FileSummary).

    Attributes:
        name (str): Nombre del archivo o directorio (sin path completo)
        path (Path): Ruta absoluta al archivo o directorio
        is_dir (bool): True si es directorio, False si es archivo
        children (Dict[str, ProjectTreeNode]): Diccionario de nodos hijos (solo si is_dir=True)
        file_summary (Optional[FileSummary]): Resumen de análisis (solo si is_dir=False)

    Methods:
        add_child(): Añade un nodo hijo a la colección
        ensure_child(): Obtiene o crea un nodo hijo

    Notes:
        - Estructura recursiva para representar árbol de directorios
        - children solo tiene contenido si is_dir=True
        - file_summary solo tiene contenido si is_dir=False
        - Usado para construir representación jerárquica del proyecto
    """

    name: str
    path: Path
    is_dir: bool
    children: Dict[str, "ProjectTreeNode"] = field(default_factory=dict)
    file_summary: Optional[FileSummary] = None

    def add_child(self, node: "ProjectTreeNode") -> None:
        """
        Añade un nodo hijo a la colección actual.

        Args:
            node (ProjectTreeNode): Nodo hijo a añadir

        Notes:
            - Sobrescribe si ya existe un hijo con el mismo nombre
            - Solo tiene sentido llamar en nodos con is_dir=True
        """
        self.children[node.name] = node

    def ensure_child(self, name: str, path: Path, is_dir: bool) -> "ProjectTreeNode":
        """
        Obtiene un hijo existente o lo crea si aún no está registrado.

        Args:
            name (str): Nombre del nodo hijo
            path (Path): Ruta absoluta al elemento
            is_dir (bool): Si el elemento es un directorio

        Returns:
            ProjectTreeNode: El nodo hijo (existente o recién creado)

        Notes:
            - Operación idempotente: safe para llamar múltiples veces
            - No valida consistencia de is_dir con filesystem
            - Usado durante construcción incremental del árbol
        """
        child = self.children.get(name)
        if child is None:
            child = ProjectTreeNode(name=name, path=path, is_dir=is_dir)
            self.children[name] = child
        return child
