# SPDX-License-Identifier: MIT
"""
Analizador AST para extraer información UML de módulos Python.
"""
from __future__ import annotations

import ast
from pathlib import Path
from typing import List, Optional, Set

from ..ast_utils import ImportResolver
from .models import AttributeInfo, ClassModel, MethodInfo, ModuleModel


class UMLModuleAnalyzer(ast.NodeVisitor):
    def __init__(self, module: str, file_path: Path) -> None:
        self.module = module
        self.file_path = file_path
        self.model = ModuleModel(name=module, file=file_path)
        self._current_class: Optional[ClassModel] = None

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            key = alias.asname or alias.name.split(".")[0]
            self.model.imports[key] = alias.name
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = node.module or ""
        for alias in node.names:
            if alias.name == "*":
                continue
            key = alias.asname or alias.name
            base = self._resolve_relative(module, node.level)
            full = f"{base}.{alias.name}" if base else alias.name
            self.model.imports[key] = full
        self.generic_visit(node)

    def _resolve_relative(self, module: str, level: int) -> str:
        """Resolve relative imports to absolute module paths."""
        return ImportResolver.resolve_relative_import(self.module, module, level)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        bases = [
            name
            for base in node.bases
            for name in [self._expr_to_name(base)]
            if name
        ]
        # Detect if class is abstract (inherits from ABC or has @abstractmethod)
        is_abstract = any(
            base in ("ABC", "abc.ABC", "ABCMeta") for base in bases
        ) or any(
            isinstance(d, ast.Name) and d.id == "abstractmethod"
            for d in node.decorator_list
        )
        # Extract docstring
        docstring = ast.get_docstring(node)

        model = ClassModel(
            name=node.name,
            module=self.module,
            file=self.file_path,
            bases=bases,
            is_abstract=is_abstract,
            docstring=docstring,
        )
        self.model.classes[node.name] = model
        previous = self._current_class
        self._current_class = model
        self.generic_visit(node)
        self._current_class = previous

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._process_function(node, is_async=False)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._process_function(node, is_async=True)

    def _process_function(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef, is_async: bool
    ) -> None:
        if self._current_class is None:
            return
        params = [arg.arg for arg in node.args.args]
        if params and params[0] in ("self", "cls"):
            params = params[1:]
        returns = self._expr_to_name(node.returns) if node.returns else None

        # Detect visibility from name convention
        visibility = _infer_visibility(node.name)

        # Detect decorators
        is_static = False
        is_abstract = False
        for decorator in node.decorator_list:
            dec_name = self._expr_to_name(decorator)
            if dec_name in ("staticmethod", "classmethod"):
                is_static = True
            if dec_name in ("abstractmethod", "abc.abstractmethod"):
                is_abstract = True
                # If method is abstract, class is abstract too
                if self._current_class:
                    self._current_class.is_abstract = True

        # Extract docstring
        docstring = ast.get_docstring(node)

        self._current_class.methods.append(
            MethodInfo(
                name=node.name,
                parameters=params,
                returns=returns,
                visibility=visibility,
                is_static=is_static,
                is_async=is_async,
                is_abstract=is_abstract,
                docstring=docstring,
            )
        )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        """Detect class instantiation: instance = SomeClass()"""
        if self._current_class is None:
            self.generic_visit(node)
            return
        target = self._expr_to_name(node.func)
        if target and target[0].isupper():  # Likely a class (PascalCase)
            self._current_class.instantiates.add(target)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if self._current_class is None:
            return
        if isinstance(node.target, ast.Name):
            attr_name = node.target.id
            annotation = self._expr_to_name(node.annotation)
            optional = _is_optional(node.annotation)
            visibility = _infer_visibility(attr_name)
            # Extract default value if present
            default_value = None
            if node.value is not None:
                default_value = _extract_default_value(node.value)

            self._current_class.attributes.append(
                AttributeInfo(
                    name=attr_name,
                    annotation=annotation,
                    optional=optional,
                    visibility=visibility,
                    default_value=default_value,
                )
            )
            if annotation:
                self._track_association(annotation)
            # Track type hints as references
            type_names = self._extract_type_names(node.annotation)
            self._current_class.references.update(type_names)
        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> None:
        if self._current_class is None:
            return
        for target in node.targets:
            if isinstance(target, ast.Name):
                self._current_class.attributes.append(AttributeInfo(name=target.id))
        if isinstance(node.value, ast.Call):
            func_name = self._expr_to_name(node.value.func)
            if func_name:
                lower = func_name.lower()
                if "relationship" in lower and node.value.args:
                    arg = node.value.args[0]
                    ref = None
                    if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                        ref = arg.value
                    else:
                        ref = self._expr_to_name(arg)
                    if ref:
                        self._track_association(ref)
        self.generic_visit(node)

    def _track_association(self, raw: str) -> None:
        if self._current_class is None:
            return
        name = raw.split("[")[0]
        if name:
            self._current_class.associations.add(name)

    def _expr_to_name(self, expr: Optional[ast.AST]) -> Optional[str]:
        if expr is None:
            return None
        if isinstance(expr, ast.Name):
            return expr.id
        if isinstance(expr, ast.Attribute):
            return ".".join(self._collect_attribute(expr))
        if isinstance(expr, ast.Subscript):
            return self._expr_to_name(expr.value)
        if isinstance(expr, ast.Constant) and isinstance(expr.value, str):
            return expr.value
        return None

    def _collect_attribute(self, node: ast.Attribute) -> List[str]:
        parts: List[str] = []
        current: ast.AST = node
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        if isinstance(current, ast.Name):
            parts.append(current.id)
        return list(reversed(parts))

    def _extract_type_names(self, node: Optional[ast.AST]) -> Set[str]:
        """Extract all class names from type annotation (handles Union, List, Optional, etc.)"""
        names: Set[str] = set()
        if node is None:
            return names

        # Simple name: foo: Bar
        if isinstance(node, ast.Name):
            if node.id[0].isupper():  # Likely a class (PascalCase)
                names.add(node.id)

        # Subscript: List[User], Optional[Product]
        elif isinstance(node, ast.Subscript):
            # Recurse into base and slice
            names.update(self._extract_type_names(node.value))
            names.update(self._extract_type_names(node.slice))

        # Tuple of types: Union[A, B] or tuple annotation
        elif isinstance(node, ast.Tuple):
            for elt in node.elts:
                names.update(self._extract_type_names(elt))

        # Binary or: A | B (Python 3.10+)
        elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
            names.update(self._extract_type_names(node.left))
            names.update(self._extract_type_names(node.right))

        # Attribute: module.ClassName
        elif isinstance(node, ast.Attribute):
            attr_name = self._expr_to_name(node)
            if attr_name and attr_name[0].isupper():
                names.add(attr_name)

        # String literal (forward reference)
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            if node.value and node.value[0].isupper():
                names.add(node.value)

        # Filter out built-in types
        builtin_types = {
            "List",
            "Dict",
            "Set",
            "Tuple",
            "Optional",
            "Union",
            "Any",
            "Callable",
            "Type",
            "Sequence",
            "Iterable",
        }
        return {name for name in names if name not in builtin_types}


def _is_optional(expr: Optional[ast.AST]) -> bool:
    if expr is None:
        return False
    if isinstance(expr, ast.Subscript):
        base = expr.value
        if isinstance(base, ast.Name) and base.id in {"Optional", "Union"}:
            return True
    if isinstance(expr, ast.BinOp) and isinstance(expr.op, ast.BitOr):
        return True
    return False


def _infer_visibility(name: str) -> str:
    """Infer visibility from Python naming convention."""
    if name.startswith("__") and not name.endswith("__"):
        return "private"  # Name mangled
    if name.startswith("_"):
        return "protected"  # Convention for internal use
    return "public"


def _extract_default_value(node: ast.AST) -> Optional[str]:
    """Extract a string representation of default value."""
    if isinstance(node, ast.Constant):
        if node.value is None:
            return "None"
        if isinstance(node.value, str):
            return f'"{node.value}"'
        return str(node.value)
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.List):
        return "[]"
    if isinstance(node, ast.Dict):
        return "{}"
    if isinstance(node, ast.Call):
        # For things like field(default_factory=list)
        return None  # Too complex to represent simply
    return None
