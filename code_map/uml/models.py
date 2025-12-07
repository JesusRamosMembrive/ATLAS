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


@dataclass
class MethodInfo:
    name: str
    parameters: List[str] = field(default_factory=list)
    returns: Optional[str] = None


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


@dataclass
class ModuleModel:
    name: str
    file: Path
    imports: Dict[str, str] = field(default_factory=dict)
    classes: Dict[str, ClassModel] = field(default_factory=dict)
