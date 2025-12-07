# SPDX-License-Identifier: MIT
"""
Paquete UML para análisis y generación de diagramas.
"""
from .builder import build_uml_model
from .models import AttributeInfo, ClassModel, MethodInfo, ModuleModel
from .renderer import GraphvizStyleOptions, build_uml_dot, render_uml_svg

__all__ = [
    "build_uml_model",
    "build_uml_dot",
    "render_uml_svg",
    "GraphvizStyleOptions",
    "ClassModel",
    "ModuleModel",
    "AttributeInfo",
    "MethodInfo",
]
