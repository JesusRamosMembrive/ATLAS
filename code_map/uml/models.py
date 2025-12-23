# SPDX-License-Identifier: MIT
"""
Modelos de datos para el grafo UML.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set


@dataclass
class AttributeInfo:
    name: str
    annotation: Optional[str] = None
    optional: bool = False
    visibility: str = "public"  # public | private | protected
    is_static: bool = False
    is_readonly: bool = False
    default_value: Optional[str] = None
    # C++ specific field
    is_const: bool = False


@dataclass
class MethodInfo:
    name: str
    parameters: List[str] = field(default_factory=list)
    returns: Optional[str] = None
    visibility: str = "public"  # public | private | protected
    is_static: bool = False
    is_async: bool = False
    is_abstract: bool = False
    docstring: Optional[str] = None
    # C++ specific fields
    is_virtual: bool = False
    is_pure_virtual: bool = False
    is_const: bool = False  # const method


@dataclass
class ClassModel:
    name: str
    module: str
    file: Path
    bases: List[str] = field(default_factory=list)
    attributes: List[AttributeInfo] = field(default_factory=list)
    methods: List[MethodInfo] = field(default_factory=list)
    associations: Set[str] = field(default_factory=set)
    instantiates: Set[str] = field(
        default_factory=set
    )  # Classes created via SomeClass()
    references: Set[str] = field(default_factory=set)  # Classes in type hints
    # New fields for UML export
    is_abstract: bool = False
    docstring: Optional[str] = None


@dataclass
class ModuleModel:
    name: str
    file: Path
    imports: Dict[str, str] = field(default_factory=dict)
    classes: Dict[str, ClassModel] = field(default_factory=dict)
