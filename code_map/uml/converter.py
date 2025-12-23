# SPDX-License-Identifier: MIT
"""
Converter: UML analysis data to UmlProjectDef format.

Transforms the analyzed code (Python + TypeScript + C++) into the UmlProjectDef
format used by the AEGIS UML Editor frontend.
"""
from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from .builder import build_uml_model
from .cpp_analyzer import UMLCppAnalyzer
from .ts_analyzer import UMLTsAnalyzer


def generate_id() -> str:
    """Generate a unique ID for UML entities."""
    return str(uuid.uuid4())[:8]


def convert_to_uml_project(
    root: Path,
    *,
    module_prefixes: Optional[Set[str]] = None,
    include_external: bool = False,
    project_name: Optional[str] = None,
    target_language: str = "python",
) -> Dict[str, Any]:
    """
    Convert analyzed code to UmlProjectDef format.

    Args:
        root: Root directory of the project to analyze
        module_prefixes: Optional set of module prefixes to filter
        include_external: Whether to include external dependencies
        project_name: Name for the project (defaults to directory name)
        target_language: Target language for type mapping

    Returns:
        UmlProjectDef compatible dictionary
    """
    root = root.expanduser().resolve()

    # Collect all classes and interfaces
    all_classes: List[Dict[str, Any]] = []
    all_interfaces: List[Dict[str, Any]] = []
    all_enums: List[Dict[str, Any]] = []
    relationships: List[Dict[str, Any]] = []

    # Track name to ID mapping for relationship resolution
    name_to_id: Dict[str, str] = {}

    # Analyze Python files
    python_data = build_uml_model(
        root,
        module_prefixes=module_prefixes,
        include_external=include_external,
    )

    for cls in python_data.get("classes", []):
        class_id = generate_id()
        class_name = cls["name"]
        name_to_id[class_name] = class_id
        name_to_id[cls["id"]] = class_id  # Also map qualified name

        uml_class = _convert_python_class(cls, class_id)
        all_classes.append(uml_class)

    # Analyze TypeScript/TSX files
    ts_classes, ts_interfaces = _analyze_typescript(root, module_prefixes)

    for cls in ts_classes:
        class_id = generate_id()
        name_to_id[cls["name"]] = class_id
        uml_class = _convert_ts_class(cls, class_id)
        all_classes.append(uml_class)

    for iface in ts_interfaces:
        iface_id = generate_id()
        name_to_id[iface["name"]] = iface_id
        uml_interface = _convert_ts_interface(iface, iface_id)
        all_interfaces.append(uml_interface)

    # Analyze C++ files
    cpp_classes, cpp_structs = _analyze_cpp(root, module_prefixes)

    for cls in cpp_classes:
        class_id = generate_id()
        name_to_id[cls["name"]] = class_id
        uml_class = _convert_cpp_class(cls, class_id)
        all_classes.append(uml_class)

    # C++ structs go to structs list (will be handled by frontend)
    all_structs: List[Dict[str, Any]] = []
    for struct in cpp_structs:
        struct_id = generate_id()
        name_to_id[struct["name"]] = struct_id
        uml_struct = _convert_cpp_struct(struct, struct_id)
        all_structs.append(uml_struct)

    # Generate relationships from inheritance/implementation
    relationships = _generate_relationships(
        python_data.get("classes", []) + ts_classes + cpp_classes,
        ts_interfaces,
        name_to_id,
    )

    # Calculate positions using grid layout
    _calculate_positions(all_classes, all_interfaces, all_enums, all_structs)

    # Build the UmlProjectDef
    return {
        "name": project_name or root.name,
        "version": "1.0",
        "description": f"Imported from {root.name}",
        "targetLanguage": target_language,
        "modules": [
            {
                "id": generate_id(),
                "name": "main",
                "description": "Imported from codebase",
                "classes": all_classes,
                "interfaces": all_interfaces,
                "enums": all_enums,
                "structs": all_structs,
                "relationships": relationships,
            }
        ],
    }


def _convert_python_class(cls: Dict[str, Any], class_id: str) -> Dict[str, Any]:
    """Convert Python class data to UmlClassDef format."""
    bases = cls.get("bases", [])
    extends = bases[0] if bases else None
    implements = bases[1:] if len(bases) > 1 else []

    return {
        "id": class_id,
        "name": cls["name"],
        "description": cls.get("docstring") or "",
        "isAbstract": cls.get("is_abstract", False),
        "extends": extends,
        "implements": implements,
        "attributes": [
            _convert_attribute(attr) for attr in cls.get("attributes", [])
        ],
        "methods": [_convert_method(method) for method in cls.get("methods", [])],
        "position": {"x": 0, "y": 0},  # Will be calculated later
    }


def _convert_ts_class(cls: Dict[str, Any], class_id: str) -> Dict[str, Any]:
    """Convert TypeScript class data to UmlClassDef format."""
    return {
        "id": class_id,
        "name": cls["name"],
        "description": cls.get("docstring") or "",
        "isAbstract": cls.get("is_abstract", False),
        "extends": cls.get("extends"),
        "implements": cls.get("implements", []),
        "attributes": [
            _convert_attribute(attr) for attr in cls.get("attributes", [])
        ],
        "methods": [_convert_method(method) for method in cls.get("methods", [])],
        "position": {"x": 0, "y": 0},
    }


def _convert_ts_interface(iface: Dict[str, Any], iface_id: str) -> Dict[str, Any]:
    """Convert TypeScript interface to UmlInterfaceDef format."""
    return {
        "id": iface_id,
        "name": iface["name"],
        "description": iface.get("docstring") or "",
        "extends": iface.get("extends", []),
        "methods": [
            {
                "id": generate_id(),
                "name": method.get("name", ""),
                "description": method.get("docstring") or "",
                "parameters": [
                    {
                        "name": p,
                        "type": "any",
                        "description": "",
                        "isOptional": False,
                        "defaultValue": None,
                    }
                    for p in method.get("parameters", [])
                ],
                "returnType": method.get("returns") or "void",
            }
            for method in iface.get("methods", [])
        ],
        "position": {"x": 0, "y": 0},
    }


def _convert_attribute(attr: Dict[str, Any]) -> Dict[str, Any]:
    """Convert attribute to UmlAttributeDef format."""
    return {
        "id": generate_id(),
        "name": attr.get("name", ""),
        "type": attr.get("type") or attr.get("annotation") or "any",
        "visibility": attr.get("visibility", "public"),
        "description": "",
        "defaultValue": attr.get("default_value"),
        "isStatic": attr.get("is_static", False),
        "isReadonly": attr.get("is_readonly", False),
    }


def _convert_method(method: Dict[str, Any]) -> Dict[str, Any]:
    """Convert method to UmlMethodDef format."""
    return {
        "id": generate_id(),
        "name": method.get("name", ""),
        "visibility": method.get("visibility", "public"),
        "description": method.get("docstring") or "",
        "isStatic": method.get("is_static", False),
        "isAsync": method.get("is_async", False),
        "parameters": [
            {
                "name": p,
                "type": "any",  # Type info not always available
                "description": "",
                "isOptional": False,
                "defaultValue": None,
            }
            for p in method.get("parameters", [])
        ],
        "returnType": method.get("returns") or "void",
        "returnDescription": "",
        "preconditions": [],
        "postconditions": [],
        "throws": [],
        "hints": {
            "edgeCases": [],
            "performance": [],
            "style": [],
            "custom": [],
        },
        "testCases": [],
    }


def _analyze_typescript(
    root: Path, module_prefixes: Optional[Set[str]] = None
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Analyze TypeScript/TSX files in the project.

    Returns tuple of (classes, interfaces).
    """
    classes: List[Dict[str, Any]] = []
    interfaces: List[Dict[str, Any]] = []

    excluded_dirs = {
        "node_modules",
        ".next",
        "dist",
        "build",
        ".git",
        "__pycache__",
        ".venv",
    }

    # Find all .ts and .tsx files
    for pattern in ["**/*.ts", "**/*.tsx"]:
        for path in root.glob(pattern):
            # Skip excluded directories
            if any(part in excluded_dirs for part in path.relative_to(root).parts):
                continue

            # Skip .d.ts files (type declarations)
            if path.name.endswith(".d.ts"):
                continue

            is_tsx = path.suffix == ".tsx"
            module_name = ".".join(path.relative_to(root).with_suffix("").parts)

            # Filter by module prefix if specified
            if module_prefixes:
                if not any(
                    module_name == prefix or module_name.startswith(f"{prefix}.")
                    for prefix in module_prefixes
                ):
                    continue

            try:
                analyzer = UMLTsAnalyzer(module_name, path, is_tsx=is_tsx)
                if not analyzer.available:
                    continue

                model = analyzer.parse()

                # Convert classes
                for name, cls_model in model.classes.items():
                    classes.append({
                        "name": name,
                        "module": module_name,
                        "file": str(path),
                        "docstring": cls_model.docstring,
                        "is_abstract": cls_model.is_abstract,
                        "extends": cls_model.bases[0] if cls_model.bases else None,
                        "implements": cls_model.bases[1:] if len(cls_model.bases) > 1 else [],
                        "attributes": [
                            {
                                "name": attr.name,
                                "type": attr.annotation,
                                "optional": attr.optional,
                                "visibility": attr.visibility,
                                "is_static": attr.is_static,
                                "is_readonly": attr.is_readonly,
                            }
                            for attr in cls_model.attributes
                        ],
                        "methods": [
                            {
                                "name": m.name,
                                "parameters": m.parameters,
                                "returns": m.returns,
                                "visibility": m.visibility,
                                "is_static": m.is_static,
                                "is_async": m.is_async,
                                "is_abstract": m.is_abstract,
                                "docstring": m.docstring,
                            }
                            for m in cls_model.methods
                        ],
                    })

                # Convert interfaces
                for name, iface_model in model.interfaces.items():
                    interfaces.append({
                        "name": name,
                        "module": module_name,
                        "file": str(path),
                        "docstring": iface_model.docstring,
                        "extends": iface_model.extends,
                        "methods": [
                            {
                                "name": m.name,
                                "parameters": m.parameters,
                                "returns": m.returns,
                                "docstring": m.docstring,
                            }
                            for m in iface_model.methods
                        ],
                    })

            except Exception:
                # Skip files that fail to parse
                continue

    return classes, interfaces


def _generate_relationships(
    classes: List[Dict[str, Any]],
    interfaces: List[Dict[str, Any]],
    name_to_id: Dict[str, str],
) -> List[Dict[str, Any]]:
    """Generate relationship definitions from class/interface data."""
    relationships: List[Dict[str, Any]] = []
    seen: Set[Tuple[str, str, str]] = set()

    def add_relationship(
        from_id: str, to_name: str, rel_type: str, description: str = ""
    ) -> None:
        to_id = name_to_id.get(to_name)
        if to_id and (from_id, to_id, rel_type) not in seen:
            seen.add((from_id, to_id, rel_type))
            relationships.append({
                "id": generate_id(),
                "type": rel_type,
                "from": from_id,
                "to": to_id,
                "description": description,
                "cardinality": None,
            })

    # Process classes
    for cls in classes:
        class_name = cls.get("name")
        class_id = name_to_id.get(class_name)
        if not class_id:
            continue

        # Inheritance
        bases = cls.get("bases", [])
        extends = cls.get("extends")
        if extends:
            add_relationship(class_id, extends, "inheritance")
        elif bases:
            add_relationship(class_id, bases[0], "inheritance")

        # Implementation
        implements = cls.get("implements", [])
        for iface in implements:
            add_relationship(class_id, iface, "implementation")

        # Associations (from type hints)
        for assoc in cls.get("associations", []):
            add_relationship(class_id, assoc, "association")

    # Process interfaces (extends)
    for iface in interfaces:
        iface_name = iface.get("name")
        iface_id = name_to_id.get(iface_name)
        if not iface_id:
            continue

        for ext in iface.get("extends", []):
            add_relationship(iface_id, ext, "inheritance")

    return relationships


def _analyze_cpp(
    root: Path, module_prefixes: Optional[Set[str]] = None
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Analyze C++ files in the project.

    Returns tuple of (classes, structs).
    """
    classes: List[Dict[str, Any]] = []
    structs: List[Dict[str, Any]] = []

    excluded_dirs = {
        "node_modules",
        ".next",
        "dist",
        "build",
        ".git",
        "__pycache__",
        ".venv",
        "vendor",
        "third_party",
    }

    # Find all C++ files
    cpp_extensions = ["**/*.cpp", "**/*.hpp", "**/*.h", "**/*.cc", "**/*.cxx"]
    for pattern in cpp_extensions:
        for path in root.glob(pattern):
            # Skip excluded directories
            if any(part in excluded_dirs for part in path.relative_to(root).parts):
                continue

            module_name = ".".join(path.relative_to(root).with_suffix("").parts)

            # Filter by module prefix if specified
            if module_prefixes:
                if not any(
                    module_name == prefix or module_name.startswith(f"{prefix}.")
                    for prefix in module_prefixes
                ):
                    continue

            try:
                analyzer = UMLCppAnalyzer(module_name, path)
                if not analyzer.available:
                    continue

                model = analyzer.parse()

                # Convert classes
                for name, cls_model in model.classes.items():
                    # Determine if class is abstract (has pure virtual methods)
                    is_abstract = any(
                        m.is_pure_virtual for m in cls_model.methods
                    )

                    classes.append({
                        "name": name,
                        "module": module_name,
                        "file": str(path),
                        "docstring": cls_model.docstring,
                        "is_abstract": is_abstract,
                        "extends": cls_model.bases[0] if cls_model.bases else None,
                        "implements": cls_model.bases[1:] if len(cls_model.bases) > 1 else [],
                        "attributes": [
                            {
                                "name": attr.name,
                                "type": attr.annotation,
                                "visibility": attr.visibility,
                                "is_static": attr.is_static,
                                "is_readonly": attr.is_const,
                            }
                            for attr in cls_model.attributes
                        ],
                        "methods": [
                            {
                                "name": m.name,
                                "parameters": m.parameters,
                                "returns": m.returns,
                                "visibility": m.visibility,
                                "is_static": m.is_static,
                                "is_async": False,  # C++ doesn't have async in the same way
                                "is_abstract": m.is_pure_virtual,
                                "is_virtual": m.is_virtual,
                                "docstring": m.docstring,
                            }
                            for m in cls_model.methods
                        ],
                    })

                # Convert structs
                for name, struct_model in model.structs.items():
                    structs.append({
                        "name": name,
                        "module": module_name,
                        "file": str(path),
                        "docstring": struct_model.docstring,
                        "extends": struct_model.bases[0] if struct_model.bases else None,
                        "attributes": [
                            {
                                "name": attr.name,
                                "type": attr.annotation,
                                "visibility": attr.visibility,
                                "is_static": attr.is_static,
                                "is_readonly": attr.is_const,
                            }
                            for attr in struct_model.attributes
                        ],
                        "methods": [
                            {
                                "name": m.name,
                                "parameters": m.parameters,
                                "returns": m.returns,
                                "visibility": m.visibility,
                                "is_static": m.is_static,
                                "docstring": m.docstring,
                            }
                            for m in struct_model.methods
                        ],
                    })

            except Exception:
                # Skip files that fail to parse
                continue

    return classes, structs


def _convert_cpp_class(cls: Dict[str, Any], class_id: str) -> Dict[str, Any]:
    """Convert C++ class data to UmlClassDef format."""
    return {
        "id": class_id,
        "name": cls["name"],
        "description": cls.get("docstring") or "",
        "isAbstract": cls.get("is_abstract", False),
        "extends": cls.get("extends"),
        "implements": cls.get("implements", []),
        "attributes": [
            _convert_attribute(attr) for attr in cls.get("attributes", [])
        ],
        "methods": [_convert_cpp_method(method) for method in cls.get("methods", [])],
        "position": {"x": 0, "y": 0},
    }


def _convert_cpp_struct(struct: Dict[str, Any], struct_id: str) -> Dict[str, Any]:
    """Convert C++ struct data to UmlStructDef format."""
    return {
        "id": struct_id,
        "name": struct["name"],
        "description": struct.get("docstring") or "",
        "extends": struct.get("extends"),
        "attributes": [
            _convert_attribute(attr) for attr in struct.get("attributes", [])
        ],
        "methods": [_convert_cpp_method(method) for method in struct.get("methods", [])],
        "position": {"x": 0, "y": 0},
    }


def _convert_cpp_method(method: Dict[str, Any]) -> Dict[str, Any]:
    """Convert C++ method to UmlMethodDef format."""
    return {
        "id": generate_id(),
        "name": method.get("name", ""),
        "visibility": method.get("visibility", "public"),
        "description": method.get("docstring") or "",
        "isStatic": method.get("is_static", False),
        "isAsync": False,  # C++ doesn't have async keyword like JS/Python
        "isVirtual": method.get("is_virtual", False),
        "isAbstract": method.get("is_abstract", False),
        "parameters": [
            {
                "name": p,
                "type": "auto",  # C++ type info would need more parsing
                "description": "",
                "isOptional": False,
                "defaultValue": None,
            }
            for p in method.get("parameters", [])
        ],
        "returnType": method.get("returns") or "void",
        "returnDescription": "",
        "preconditions": [],
        "postconditions": [],
        "throws": [],
        "hints": {
            "edgeCases": [],
            "performance": [],
            "style": [],
            "custom": [],
        },
        "testCases": [],
    }


def _calculate_positions(
    classes: List[Dict[str, Any]],
    interfaces: List[Dict[str, Any]],
    enums: List[Dict[str, Any]],
    structs: Optional[List[Dict[str, Any]]] = None,
) -> None:
    """
    Calculate positions for all entities using a grid layout.

    Groups entities by module and arranges in a grid pattern.
    """
    GRID_X = 300  # Horizontal spacing
    GRID_Y = 250  # Vertical spacing
    MAX_COLS = 4  # Maximum columns per row

    all_entities = classes + interfaces + enums + (structs or [])
    if not all_entities:
        return

    # Group by module (if available) or just layout sequentially
    modules: Dict[str, List[Dict[str, Any]]] = {}
    for entity in all_entities:
        # Try to get module from various sources
        module = "main"
        if "module" in entity:
            module = entity.get("module", "main").split(".")[0]
        if module not in modules:
            modules[module] = []
        modules[module].append(entity)

    # Layout each module group
    current_y = 0
    for module_name, entities in modules.items():
        for i, entity in enumerate(entities):
            col = i % MAX_COLS
            row = i // MAX_COLS
            entity["position"] = {
                "x": col * GRID_X,
                "y": current_y + row * GRID_Y,
            }
        # Move to next module section
        rows_used = (len(entities) + MAX_COLS - 1) // MAX_COLS
        current_y += rows_used * GRID_Y + GRID_Y  # Extra spacing between modules
