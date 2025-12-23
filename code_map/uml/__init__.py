# SPDX-License-Identifier: MIT
"""
Paquete UML para análisis y generación de diagramas.
"""
from .builder import build_uml_model
from .converter import convert_to_uml_project
from .cpp_analyzer import CppModuleModel, CppStructModel, UMLCppAnalyzer
from .models import AttributeInfo, ClassModel, MethodInfo, ModuleModel
from .renderer import GraphvizStyleOptions, build_uml_dot, render_uml_svg
from .ts_analyzer import InterfaceModel, TsModuleModel, UMLTsAnalyzer

__all__ = [
    "build_uml_model",
    "build_uml_dot",
    "render_uml_svg",
    "convert_to_uml_project",
    "GraphvizStyleOptions",
    "ClassModel",
    "ModuleModel",
    "AttributeInfo",
    "MethodInfo",
    "InterfaceModel",
    "TsModuleModel",
    "UMLTsAnalyzer",
    "CppStructModel",
    "CppModuleModel",
    "UMLCppAnalyzer",
]
