# SPDX-License-Identifier: MIT
"""
Call Graph Tracer - Stage 2

Análisis cross-file completo con resolución de imports.
Soporta:
- Análisis multi-archivo
- Resolución de imports (absolutos y relativos)
- Detección de métodos de clase
- Cache de resultados para performance
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
import hashlib

try:
    from tree_sitter import Parser, Node
    from tree_sitter_languages import get_language

    TREE_SITTER_AVAILABLE = True
except ImportError:
    TREE_SITTER_AVAILABLE = False

from .import_resolver import ImportResolver


class CrossFileCallGraphExtractor:
    """
    Extractor de call graphs con análisis cross-file.

    Características Stage 2:
    - Sigue imports entre archivos
    - Resuelve llamadas a funciones importadas
    - Cachea resultados por archivo
    - Detecta métodos de clase

    Example:
        >>> extractor = CrossFileCallGraphExtractor(project_root=Path("/project"))
        >>> graph = extractor.analyze_project(entry_point="main.py")
        >>> print(graph)
        {
            'main.py::main': ['utils.py::helper', 'process.py::run'],
            'utils.py::helper': ['config.py::load_config']
        }
    """

    def __init__(self, project_root: Path, use_cache: bool = True):
        """
        Inicializa el extractor cross-file.

        Args:
            project_root: Raíz del proyecto
            use_cache: Si True, cachea resultados por archivo
        """
        if not TREE_SITTER_AVAILABLE:
            raise ImportError(
                "tree-sitter not available. Install with: "
                "pip install tree-sitter tree-sitter-python"
            )

        self.project_root = project_root.resolve()
        self.parser = Parser()
        self.parser.set_language(get_language("python"))
        self.import_resolver = ImportResolver(project_root)
        self.use_cache = use_cache

        # Cache: {file_path: {hash: call_graph}}
        self._file_cache: Dict[
            Path, Tuple[str, Dict[str, List[Tuple[str, bool, Optional[str]]]]]
        ] = {}

        # Global call graph: {qualified_name: [qualified_callees]}
        # qualified_name format: "file.py::function_name"
        self.call_graph: Dict[str, List[str]] = {}

        # Set de archivos ya analizados (para evitar ciclos)
        self.analyzed_files: Set[Path] = set()

        # Instance attribute types: {filepath: {class_name: {attr_name: type_name}}}
        # e.g., {"endpoint.py": {"endpointClass": {"middleware": "middlewareAPI"}}}
        self.instance_attrs: Dict[Path, Dict[str, Dict[str, str]]] = {}

    def _get_file_hash(self, filepath: Path) -> str:
        """Calcula hash MD5 del contenido del archivo para cache."""
        with open(filepath, "rb") as f:
            return hashlib.md5(f.read(), usedforsecurity=False).hexdigest()

    def _get_qualified_name(self, filepath: Path, function_name: str) -> str:
        """
        Genera nombre cualificado para una función.

        Args:
            filepath: Path del archivo
            function_name: Nombre de la función

        Returns:
            Nombre cualificado: "relative/path/file.py::function_name"
        """
        try:
            relative = filepath.relative_to(self.project_root)
        except ValueError:
            relative = filepath

        return f"{relative}::{function_name}"

    def analyze_file(
        self, filepath: Path, recursive: bool = True
    ) -> Dict[str, List[Tuple[str, bool, Optional[str]]]]:
        """
        Analiza un archivo y opcionalmente sus dependencias.

        Args:
            filepath: Archivo a analizar
            recursive: Si True, analiza también archivos importados

        Returns:
            Call graph local del archivo
        """
        filepath = filepath.resolve()

        # Verificar cache
        if self.use_cache and filepath in self._file_cache:
            cached_hash, cached_graph = self._file_cache[filepath]
            current_hash = self._get_file_hash(filepath)
            if cached_hash == current_hash:
                return cached_graph

        # Marcar como analizado para evitar ciclos
        if filepath in self.analyzed_files:
            return {}

        self.analyzed_files.add(filepath)

        # Leer archivo
        with open(filepath, "rb") as f:
            source = f.read()

        tree = self.parser.parse(source)

        # Extraer definiciones de funciones y sus llamadas
        local_graph: Dict[str, List[Tuple[str, bool, Optional[str]]]] = {}
        self._extract_functions_and_calls(tree.root_node, source, filepath, local_graph)

        # Resolver imports
        import_map = self.import_resolver.build_import_map(filepath)

        # Actualizar call graph con nombres cualificados
        for func_name, callees in local_graph.items():
            qualified_func = self._get_qualified_name(filepath, func_name)

            qualified_callees = []
            for callee_data in callees:
                # Desempaquetar tupla (callee, is_instance_method, instance_attr)
                callee, is_instance_method, instance_attr = callee_data

                # Caso especial: llamada a método de instancia (self.middleware.apiMethod)
                if is_instance_method and instance_attr:
                    # Obtener la clase actual del qualified_func
                    # e.g., "endpointExampleClass.endpointMethod" -> "endpointExampleClass"
                    if "." in func_name:
                        class_name = func_name.split(".")[0]

                        # Buscar el tipo del atributo de instancia
                        if (
                            filepath in self.instance_attrs
                            and class_name in self.instance_attrs[filepath]
                            and instance_attr
                            in self.instance_attrs[filepath][class_name]
                        ):

                            # e.g., self.middleware -> middlewareAPI
                            type_name = self.instance_attrs[filepath][class_name][
                                instance_attr
                            ]

                            # Buscar en imports para encontrar el archivo
                            if type_name in import_map:
                                target_file, _ = import_map[type_name]
                                # Cualificar: middlewareExample.py::middlewareAPI.apiDriveMethod
                                qualified_callee = self._get_qualified_name(
                                    target_file, f"{type_name}.{callee}"
                                )
                                qualified_callees.append(qualified_callee)

                                # Recursivamente analizar archivo importado
                                if recursive and target_file not in self.analyzed_files:
                                    self.analyze_file(target_file, recursive=True)
                                continue

                # Verificar si es un import
                if callee in import_map:
                    target_file, symbol = import_map[callee]

                    if symbol:
                        # from utils import helper → helper es la función
                        qualified_callee = self._get_qualified_name(target_file, symbol)
                    else:
                        # import utils → puede ser utils.function
                        # Por ahora, marcar como externa
                        qualified_callee = f"{target_file}::*"

                    qualified_callees.append(qualified_callee)

                    # Recursivamente analizar archivo importado
                    if recursive and target_file not in self.analyzed_files:
                        self.analyze_file(target_file, recursive=True)
                else:
                    # Llamada local (dentro del mismo archivo)
                    qualified_callee = self._get_qualified_name(filepath, callee)
                    qualified_callees.append(qualified_callee)

            self.call_graph[qualified_func] = qualified_callees

        # Cachear resultado
        if self.use_cache:
            file_hash = self._get_file_hash(filepath)
            self._file_cache[filepath] = (file_hash, local_graph)

        return local_graph

    def _extract_functions_and_calls(
        self,
        node: Node,
        source: bytes,
        filepath: Path,
        local_graph: Dict[str, List[Tuple[str, bool, Optional[str]]]],
        current_func: Optional[str] = None,
        current_class: Optional[str] = None,
    ):
        """
        Extrae funciones y llamadas del AST.

        Args:
            node: Nodo actual
            source: Código fuente
            filepath: Archivo siendo analizado
            local_graph: Grafo local a llenar
            current_func: Función actual (contexto)
            current_class: Clase actual (contexto)
        """
        # Handle different node types via extracted methods
        if node.type == "class_definition":
            current_class = self._handle_class_definition(
                node, source, filepath, current_class
            )
        elif node.type == "function_definition":
            current_func = self._handle_function_definition(
                node, source, local_graph, current_func, current_class
            )
        elif node.type == "assignment":
            self._handle_assignment(node, source, filepath, current_class, current_func)
        elif node.type == "call":
            self._handle_call(
                node, source, filepath, local_graph, current_func, current_class
            )

        # Recursión
        for child in node.children:
            self._extract_functions_and_calls(
                child, source, filepath, local_graph, current_func, current_class
            )

    def _handle_class_definition(
        self, node: Node, source: bytes, filepath: Path, current_class: Optional[str]
    ) -> Optional[str]:
        """Detecta y registra definición de clase."""
        name_node = node.child_by_field_name("name")
        if not name_node:
            return current_class

        class_name = self._get_node_text(name_node, source)

        # Inicializar estructura para atributos de esta clase
        if filepath not in self.instance_attrs:
            self.instance_attrs[filepath] = {}
        if class_name not in self.instance_attrs[filepath]:
            self.instance_attrs[filepath][class_name] = {}

        return class_name

    def _handle_function_definition(
        self,
        node: Node,
        source: bytes,
        local_graph: Dict[str, List[Tuple[str, bool, Optional[str]]]],
        current_func: Optional[str],
        current_class: Optional[str],
    ) -> Optional[str]:
        """Detecta y registra definición de función."""
        name_node = node.child_by_field_name("name")
        if not name_node:
            return current_func

        func_name = self._get_node_text(name_node, source)

        # Si está en una clase, prefixar con nombre de clase
        qualified_func_name = (
            f"{current_class}.{func_name}" if current_class else func_name
        )

        # Inicializar en el grafo
        if qualified_func_name not in local_graph:
            local_graph[qualified_func_name] = []

        return qualified_func_name

    def _handle_assignment(
        self,
        node: Node,
        source: bytes,
        filepath: Path,
        current_class: Optional[str],
        current_func: Optional[str],
    ) -> None:
        """
        Detecta asignación de atributo de instancia en __init__.
        Ejemplo: self.middleware = middlewareAPI()
        """
        # Solo procesar si estamos en __init__ de una clase
        if not (current_class and current_func and current_func.endswith(".__init__")):
            return

        left_node = node.child_by_field_name("left")
        right_node = node.child_by_field_name("right")

        if not (left_node and right_node and left_node.type == "attribute"):
            return

        # Verificar patrón: self.attr
        obj_node = left_node.child_by_field_name("object")
        attr_node = left_node.child_by_field_name("attribute")

        if not (
            obj_node and attr_node and self._get_node_text(obj_node, source) == "self"
        ):
            return

        attr_name = self._get_node_text(attr_node, source)

        # Verificar que right es una llamada: SomeClass()
        if right_node.type == "call":
            func_node = right_node.child_by_field_name("function")
            if func_node and func_node.type == "identifier":
                type_name = self._get_node_text(func_node, source)
                # Guardar: self.middleware -> middlewareAPI
                self.instance_attrs[filepath][current_class][attr_name] = type_name

    def _handle_call(
        self,
        node: Node,
        source: bytes,
        filepath: Path,
        local_graph: Dict[str, List[Tuple[str, bool, Optional[str]]]],
        current_func: Optional[str],
        current_class: Optional[str],
    ) -> None:
        """Detecta y registra llamadas a funciones."""
        if not current_func:
            return

        function_node = node.child_by_field_name("function")
        if not function_node:
            return

        callee_info = self._extract_callee_name(
            function_node, source, current_class, filepath
        )
        if not callee_info:
            return

        callee, is_instance_method, instance_attr = callee_info

        # Verificar si ya existe (evitar duplicados)
        already_exists = any(c[0] == callee for c in local_graph[current_func])

        if callee and not already_exists:
            local_graph[current_func].append(
                (callee, is_instance_method, instance_attr)
            )

    def _extract_callee_name(
        self, node: Node, source: bytes, current_class: Optional[str], filepath: Path
    ) -> Optional[Tuple[str, bool, Optional[str]]]:
        """
        Extrae nombre de función llamada.

        Maneja:
        - foo() → ("foo", False, None)
        - obj.method() → ("method", False, None)
        - self.helper() → ("helper", False, None)
        - module.func() → ("module", False, None) para imports
        - self.middleware.apiMethod() → ("apiMethod", True, "middleware")

        Returns:
            Tuple of (callee_name, is_instance_method, instance_attr_name)
        """
        if node.type == "identifier":
            return (self._get_node_text(node, source), False, None)

        if node.type == "attribute":
            # Extraer el método
            attr_node = node.child_by_field_name("attribute")
            if not attr_node:
                return None

            method_name = self._get_node_text(attr_node, source)

            # Extraer el objeto
            obj_node = node.child_by_field_name("object")
            if not obj_node:
                return (method_name, False, None)

            # Caso 1: Simple identifier - module.func() o self.method()
            if obj_node.type == "identifier":
                obj_name = self._get_node_text(obj_node, source)
                # Si es self.method(), retornar el método
                if obj_name == "self":
                    return (method_name, False, None)
                # Si es module.func(), retornar el módulo (para resolución de import)
                return (obj_name, False, None)

            # Caso 2: Nested attribute - self.middleware.apiMethod()
            if obj_node.type == "attribute":
                # Extraer self.middleware
                nested_obj = obj_node.child_by_field_name("object")
                nested_attr = obj_node.child_by_field_name("attribute")

                if (
                    nested_obj
                    and nested_attr
                    and nested_obj.type == "identifier"
                    and self._get_node_text(nested_obj, source) == "self"
                ):
                    # Es self.X.method() - X es un atributo de instancia
                    instance_attr = self._get_node_text(nested_attr, source)
                    return (method_name, True, instance_attr)

            return (method_name, False, None)

        text = self._get_node_text(node, source)
        return (text, False, None) if text else None

    def _get_node_text(self, node: Node, source: bytes) -> str:
        """Extrae texto de un nodo."""
        return source[node.start_byte : node.end_byte].decode("utf-8")

    def trace_chain_cross_file(
        self, start_function: str, max_depth: int = 10
    ) -> List[Tuple[int, str, List[str]]]:
        """
        Traza cadena de llamadas cross-file.

        Args:
            start_function: Nombre cualificado ("file.py::function")
            max_depth: Profundidad máxima

        Returns:
            Lista de (depth, qualified_name, callees)
        """
        chain: List[Tuple[int, str, List[str]]] = []
        visited: Set[str] = set()

        def dfs(func: str, depth: int = 0):
            if depth > max_depth or func in visited:
                return

            visited.add(func)
            callees = self.call_graph.get(func, [])
            chain.append((depth, func, callees.copy()))

            for callee in callees:
                dfs(callee, depth + 1)

        dfs(start_function)
        return chain

    def find_entry_points(self) -> List[str]:
        """
        Encuentra funciones que no son llamadas por nadie (entry points).

        Returns:
            Lista de nombres cualificados de entry points
        """
        all_callees = set()
        for callees in self.call_graph.values():
            all_callees.update(callees)

        entry_points = set(self.call_graph.keys()) - all_callees
        return list(entry_points)

    def export_to_dict(self) -> Dict[str, Any]:
        """
        Exporta el call graph a un diccionario serializable.

        Returns:
            Dict con estructura del call graph
        """
        return {
            "call_graph": self.call_graph,
            "entry_points": self.find_entry_points(),
            "total_functions": len(self.call_graph),
            "analyzed_files": [
                str(f.relative_to(self.project_root)) for f in self.analyzed_files
            ],
        }
