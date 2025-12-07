# SPDX-License-Identifier: MIT
"""
Construcción del modelo UML a partir del análisis de archivos.
"""
from __future__ import annotations

import ast
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set

from .analyzer import UMLModuleAnalyzer
from .models import ClassModel, ModuleModel


def build_uml_model(
    root: Path,
    *,
    module_prefixes: Optional[Set[str]] = None,
    include_external: bool = False,
) -> Dict[str, object]:
    root = root.expanduser().resolve()
    modules = list(_analyze(root))
    modules = _filter_modules(modules, module_prefixes)
    index = _collect_definitions(modules)

    classes = []
    inheritance_edges = 0
    association_edges = 0
    instantiation_edges = 0
    reference_edges = 0

    for module in modules:
        for class_model in module.classes.values():
            bases = _resolve_bases(class_model, module, index, include_external)
            associations = _resolve_associations(
                class_model, module, index, include_external
            )
            instantiates = _resolve_references(
                class_model.instantiates, module, index, include_external
            )
            references = _resolve_references(
                class_model.references, module, index, include_external
            )

            inheritance_edges += len(bases)
            association_edges += len(associations)
            instantiation_edges += len(instantiates)
            reference_edges += len(references)

            classes.append(
                {
                    "id": f"{class_model.module}.{class_model.name}",
                    "name": class_model.name,
                    "module": class_model.module,
                    "file": str(class_model.file),
                    "bases": bases,
                    "attributes": [
                        {
                            "name": attr.name,
                            "type": attr.annotation,
                            "optional": attr.optional,
                        }
                        for attr in class_model.attributes
                    ],
                    "methods": [
                        {
                            "name": method.name,
                            "parameters": method.parameters,
                            "returns": method.returns,
                        }
                        for method in class_model.methods
                    ],
                    "associations": list(associations),
                    "instantiates": list(instantiates),
                    "references": list(references),
                }
            )

    stats = {
        "classes": len(classes),
        "inheritance_edges": inheritance_edges,
        "association_edges": association_edges,
        "instantiation_edges": instantiation_edges,
        "reference_edges": reference_edges,
    }

    return {"classes": classes, "stats": stats}


def _analyze(
    root: Path, excluded_dirs: Optional[Set[str]] = None
) -> Iterable[ModuleModel]:
    """Analyze Python files in the root directory, excluding certain directories.

    Args:
        root: Root directory to scan
        excluded_dirs: Set of directory names to exclude (e.g., .venv, __pycache__)
    """
    if excluded_dirs is None:
        excluded_dirs = {
            "__pycache__",
            ".git",
            ".hg",
            ".mypy_cache",
            ".pytest_cache",
            ".ruff_cache",
            ".svn",
            ".tox",
            ".venv",
            "venv",
            "env",
            ".code-map",
            "node_modules",
            ".next",
            "dist",
            "build",
        }

    for path in root.rglob("*.py"):
        # Check if any part of the path is in excluded_dirs
        if any(part in excluded_dirs for part in path.relative_to(root).parts):
            continue

        try:
            module = ".".join(path.relative_to(root).with_suffix("").parts)
            tree = ast.parse(path.read_text(encoding="utf-8"))
            analyzer = UMLModuleAnalyzer(module, path)
            analyzer.visit(tree)
            yield analyzer.model
        except (SyntaxError, OSError):  # pragma: no cover
            continue


def _filter_modules(
    modules: List[ModuleModel], prefixes: Optional[Set[str]]
) -> List[ModuleModel]:
    if not prefixes:
        return modules
    normalized = {prefix.strip() for prefix in prefixes if prefix.strip()}
    if not normalized:
        return modules

    def matches(name: str) -> bool:
        return any(
            name == prefix or name.startswith(f"{prefix}.") for prefix in normalized
        )

    filtered = [module for module in modules if matches(module.name)]
    return filtered or modules


def _collect_definitions(modules: Iterable[ModuleModel]) -> Dict[str, ClassModel]:
    index: Dict[str, ClassModel] = {}
    for module in modules:
        for class_model in module.classes.values():
            key = f"{module.name}.{class_model.name}"
            index[key] = class_model
    return index


def _resolve_bases(
    class_model: ClassModel,
    module: ModuleModel,
    definitions: Dict[str, ClassModel],
    include_external: bool,
) -> List[str]:
    bases: List[str] = []
    for base in class_model.bases:
        if not base:
            continue
        target = _resolve_reference(base, module, definitions)
        if target or include_external:
            bases.append(target or base)
    return bases


def _resolve_associations(
    class_model: ClassModel,
    module: ModuleModel,
    definitions: Dict[str, ClassModel],
    include_external: bool,
) -> Set[str]:
    associations: Set[str] = set()
    for raw in class_model.associations:
        if not raw:
            continue
        target = _resolve_reference(raw, module, definitions)
        if target:
            associations.add(target)
        elif include_external:
            associations.add(raw)
    return associations


def _resolve_references(
    raw_refs: Set[str],
    module: ModuleModel,
    definitions: Dict[str, ClassModel],
    include_external: bool,
) -> Set[str]:
    """Resolve a set of raw class names to fully qualified names."""
    resolved: Set[str] = set()
    for raw in raw_refs:
        if not raw:
            continue
        target = _resolve_reference(raw, module, definitions)
        if target:
            resolved.add(target)
        elif include_external:
            resolved.add(raw)
    return resolved


def _resolve_reference(
    raw: str, module: ModuleModel, definitions: Dict[str, ClassModel]
) -> Optional[str]:
    for candidate in _possible_names(raw, module):
        if candidate in definitions:
            return candidate
    return None


def _possible_names(raw: str, module: ModuleModel) -> List[str]:
    if raw is None:
        return []
    if not isinstance(raw, str):
        raw = str(raw)
    if not raw:
        return []
    candidates: List[str] = []
    if raw in module.classes:
        candidates.append(f"{module.name}.{raw}")
    if raw in module.imports:
        candidates.append(module.imports[raw])
    if "." in raw:
        head, tail = raw.split(".", 1)
        target = module.imports.get(head, head)
        candidates.append(f"{target}.{tail}")
    else:
        candidates.append(f"{module.name}.{raw}")
    seen: Set[str] = set()
    unique: List[str] = []
    for candidate in candidates:
        if candidate not in seen:
            unique.append(candidate)
            seen.add(candidate)
    return unique
