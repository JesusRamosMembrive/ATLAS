# SPDX-License-Identifier: MIT
"""
Rutas para análisis de trazabilidad de llamadas (Call Tracing).
"""

from __future__ import annotations

import logging
from typing import Dict, List, Set

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from ..call_tracer_v2 import CrossFileCallGraphExtractor, TREE_SITTER_AVAILABLE
from ..state import AppState
from .deps import get_app_state

router = APIRouter(prefix="/tracer", tags=["tracer"])
logger = logging.getLogger(__name__)


def _require_tree_sitter() -> None:
    """Valida disponibilidad de tree-sitter y responde con 503 si falta."""
    if TREE_SITTER_AVAILABLE:
        return
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="tree-sitter no disponible. Instalar con: pip install tree-sitter tree-sitter-python",
    )


# ==================== Request/Response Models ====================


class AnalyzeFileRequest(BaseModel):
    """Request para analizar un archivo y extraer su call graph."""

    file_path: str = Field(
        ...,
        description="Ruta relativa del archivo Python a analizar",
        examples=["code_map/server.py"],
    )


class CallChain(BaseModel):
    """Representa una cadena de llamadas."""

    depth: int = Field(..., description="Nivel de profundidad en la cadena")
    function: str = Field(..., description="Nombre de la función")
    callees: List[str] = Field(..., description="Funciones llamadas desde esta función")


class TraceChainRequest(BaseModel):
    """Request para trazar cadena desde una función específica."""

    file_path: str = Field(..., description="Ruta relativa del archivo Python")
    start_function: str = Field(
        ..., description="Nombre de la función desde donde iniciar el trace"
    )
    max_depth: int = Field(
        5, description="Profundidad máxima de la cadena", ge=1, le=20
    )


class CallGraphResponse(BaseModel):
    """Response con el call graph extraído."""

    file_path: str = Field(..., description="Archivo analizado")
    call_graph: Dict[str, List[str]] = Field(
        ...,
        description="Grafo de llamadas: {caller: [callees]}",
        examples=[
            {"create_app": ["configure_routes"], "configure_routes": ["include_router"]}
        ],
    )
    total_functions: int = Field(
        ..., description="Número total de funciones detectadas"
    )


class TraceChainResponse(BaseModel):
    """Response con la cadena de llamadas trazada."""

    start_function: str = Field(..., description="Función de inicio")
    chain: List[CallChain] = Field(..., description="Cadena de llamadas completa")
    max_depth_reached: bool = Field(
        ..., description="Si se alcanzó el límite de profundidad"
    )


class AllChainsResponse(BaseModel):
    """Response con todas las cadenas detectadas en un archivo."""

    file_path: str = Field(..., description="Archivo analizado")
    chains: List[List[str]] = Field(
        ...,
        description="Lista de todas las cadenas de llamadas",
        examples=[[["create_app", "configure_routes", "include_router"]]],
    )
    total_chains: int = Field(..., description="Número total de cadenas detectadas")


# ==================== Endpoints ====================


@router.post("/analyze", response_model=CallGraphResponse)
async def analyze_file(
    request: AnalyzeFileRequest,
    state: AppState = Depends(get_app_state),
) -> CallGraphResponse:
    """
    Analiza un archivo Python y extrae su call graph.

    El call graph muestra qué funciones llaman a qué otras funciones
    dentro del mismo archivo.

    **Stage 1 Limitations:**
    - Solo analiza llamadas dentro del mismo archivo
    - No resuelve imports cross-file
    - No maneja decorators complejos, lambdas o closures
    """
    _require_tree_sitter()

    # Resolver ruta completa
    try:
        target_path = state.resolve_path(request.file_path)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    # Verificar que sea archivo Python
    if target_path.suffix != ".py":
        raise HTTPException(
            status_code=400,
            detail=f"Solo se soportan archivos Python (.py). Recibido: {target_path.suffix}",
        )

    # Analizar archivo usando v2 con recursive=False para compatibilidad con v1
    try:
        extractor = CrossFileCallGraphExtractor(
            project_root=state.settings.root_path, use_cache=True
        )
        extractor.analyze_file(target_path, recursive=False)

        # Convertir nombres cualificados a nombres simples para compatibilidad v1
        # v2 usa: "path/file.py::function"
        # v1 esperaba: "function"
        simple_call_graph = {}
        for qualified_name, qualified_callees in extractor.call_graph.items():
            # Extraer solo el nombre de función del formato "file.py::function"
            if "::" in qualified_name:
                simple_name = qualified_name.split("::")[-1]
            else:
                simple_name = qualified_name

            # Convertir callees también
            simple_callees = []
            for callee in qualified_callees:
                if "::" in callee:
                    simple_callees.append(callee.split("::")[-1])
                else:
                    simple_callees.append(callee)

            simple_call_graph[simple_name] = simple_callees

        call_graph = simple_call_graph
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (ValueError, OSError, PermissionError) as exc:
        # Known errors: invalid file, access denied, etc.
        raise HTTPException(
            status_code=400, detail=f"Error al analizar archivo: {exc}"
        ) from exc
    except Exception as exc:
        # Unexpected errors: log with traceback for debugging
        logger.exception("Unexpected error in analyze_file endpoint")
        raise HTTPException(
            status_code=500, detail=f"Error inesperado al analizar archivo: {exc}"
        ) from exc

    return CallGraphResponse(
        file_path=request.file_path,
        call_graph=call_graph,
        total_functions=len(call_graph),
    )


@router.post("/trace", response_model=TraceChainResponse)
async def trace_chain(
    request: TraceChainRequest,
    state: AppState = Depends(get_app_state),
) -> TraceChainResponse:
    """
    Traza la cadena completa de llamadas desde una función específica.

    Sigue todas las llamadas recursivamente desde la función de inicio
    hasta la profundidad máxima especificada.

    **Ejemplo:**
    Si tienes `api_move_motors() -> internal_move() -> kinesis_move()`,
    el trace desde `api_move_motors` retornará toda la cadena.
    """
    _require_tree_sitter()

    # Resolver ruta
    try:
        target_path = state.resolve_path(request.file_path)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    # Analizar y trazar usando v2
    try:
        extractor = CrossFileCallGraphExtractor(
            project_root=state.settings.root_path, use_cache=True
        )
        extractor.analyze_file(target_path, recursive=False)

        # Convertir nombre simple a cualificado para buscar en v2
        # Buscar la función en el call_graph (puede tener prefijo de archivo)
        qualified_func = None
        for qname in extractor.call_graph.keys():
            if qname.endswith(f"::{request.start_function}"):
                qualified_func = qname
                break

        if not qualified_func:
            # Intentar buscar sin cualificación completa
            available_simple = [
                name.split("::")[-1] for name in extractor.call_graph.keys()
            ]
            raise HTTPException(
                status_code=404,
                detail=f"Función '{request.start_function}' no encontrada. "
                f"Funciones disponibles: {', '.join(set(available_simple))}",
            )

        chain_data = extractor.trace_chain_cross_file(
            qualified_func, max_depth=request.max_depth
        )

        # Convertir a modelo Pydantic, simplificando los nombres
        chain = []
        for depth, qualified_name, qualified_callees in chain_data:
            simple_func = (
                qualified_name.split("::")[-1]
                if "::" in qualified_name
                else qualified_name
            )
            simple_callees = [
                c.split("::")[-1] if "::" in c else c for c in qualified_callees
            ]
            chain.append(
                CallChain(depth=depth, function=simple_func, callees=simple_callees)
            )

        # Detectar si se alcanzó max_depth
        max_depth_reached = any(item.depth >= request.max_depth for item in chain)

    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except HTTPException:
        raise
    except (ValueError, KeyError) as exc:
        raise HTTPException(
            status_code=400, detail=f"Error al trazar cadena: {exc}"
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected error in trace_chain endpoint")
        raise HTTPException(
            status_code=500, detail=f"Error inesperado al trazar cadena: {exc}"
        ) from exc

    return TraceChainResponse(
        start_function=request.start_function,
        chain=chain,
        max_depth_reached=max_depth_reached,
    )


@router.post("/chains", response_model=AllChainsResponse)
async def get_all_chains(
    request: AnalyzeFileRequest,
    state: AppState = Depends(get_app_state),
) -> AllChainsResponse:
    """
    Obtiene todas las cadenas de llamadas posibles en un archivo.

    Detecta automáticamente funciones raíz (no llamadas por otras)
    y genera todas las cadenas desde esas raíces.

    **Útil para:**
    - Visualizar flujo completo de un módulo
    - Detectar endpoints y sus cadenas de ejecución
    - Identificar código no utilizado
    """
    _require_tree_sitter()

    # Resolver ruta
    try:
        target_path = state.resolve_path(request.file_path)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    # Analizar usando v2
    try:
        extractor = CrossFileCallGraphExtractor(
            project_root=state.settings.root_path, use_cache=True
        )
        extractor.analyze_file(target_path, recursive=False)

        # v2 no tiene get_all_chains(), pero podemos implementar la misma lógica
        # Encontrar entry points (funciones no llamadas por nadie)
        all_callees = set()
        for callees in extractor.call_graph.values():
            all_callees.update(callees)

        entry_points = set(extractor.call_graph.keys()) - all_callees

        # Para cada entry point, generar su cadena completa
        chains = []
        visited_global: Set[str] = set()

        def build_chain(func: str, visited: Set[str]) -> List[str]:
            """Construye cadena desde una función."""
            if func in visited:
                return [func.split("::")[-1] if "::" in func else func]

            visited.add(func)
            simple_func = func.split("::")[-1] if "::" in func else func
            callees = extractor.call_graph.get(func, [])

            if not callees:
                return [simple_func]

            # Para cada callee, construir su subcadena
            chain = [simple_func]
            for callee in callees:
                if callee not in visited:
                    subchain = build_chain(callee, visited.copy())
                    # Extender la cadena principal
                    if len(subchain) > 1:
                        chain.extend(subchain[1:])
            return chain

        for entry_point in entry_points:
            if entry_point not in visited_global:
                chain = build_chain(entry_point, visited_global.copy())
                chains.append(chain)
                visited_global.add(entry_point)

    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except (ValueError, OSError, PermissionError) as exc:
        raise HTTPException(
            status_code=400, detail=f"Error al extraer cadenas: {exc}"
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected error in get_all_chains endpoint")
        raise HTTPException(
            status_code=500, detail=f"Error inesperado al extraer cadenas: {exc}"
        ) from exc

    return AllChainsResponse(
        file_path=request.file_path,
        chains=chains,
        total_chains=len(chains),
    )


# ==================== Stage 2: Cross-File Analysis ====================


class AnalyzeCrossFileRequest(BaseModel):
    """Request para análisis cross-file (Stage 2)."""

    file_path: str = Field(
        ...,
        description="Archivo de inicio para análisis cross-file",
        examples=["code_map/server.py"],
    )
    recursive: bool = Field(
        True,
        description="Si True, analiza también archivos importados",
    )
    max_files: int = Field(
        50,
        description="Máximo número de archivos a analizar",
        ge=1,
        le=200,
    )


class CrossFileCallGraphResponse(BaseModel):
    """Response con call graph cross-file."""

    call_graph: Dict[str, List[str]] = Field(
        ...,
        description="Call graph con nombres cualificados (file.py::function)",
        examples=[
            {
                "server.py::create_app": [
                    "settings.py::load_settings",
                    "state.py::AppState",
                ],
                "settings.py::load_settings": [],
            }
        ],
    )
    entry_points: List[str] = Field(
        ...,
        description="Funciones que no son llamadas por nadie",
    )
    total_functions: int = Field(
        ...,
        description="Total de funciones analizadas",
    )
    analyzed_files: List[str] = Field(
        ...,
        description="Lista de archivos analizados",
    )


class TraceCrossFileRequest(BaseModel):
    """Request para trace cross-file."""

    start_function: str = Field(
        ...,
        description="Nombre cualificado de inicio (file.py::function)",
        examples=["code_map/server.py::create_app"],
    )
    max_depth: int = Field(
        10,
        description="Profundidad máxima",
        ge=1,
        le=50,
    )


class CrossFileCallChain(BaseModel):
    """Cadena de llamadas cross-file."""

    depth: int = Field(..., description="Nivel de profundidad")
    qualified_name: str = Field(..., description="Nombre cualificado (file::function)")
    callees: List[str] = Field(..., description="Funciones llamadas (cualificadas)")
    file_path: str = Field(..., description="Archivo donde está la función")
    function_name: str = Field(
        ..., description="Nombre de la función sin cualificación"
    )


class TraceCrossFileResponse(BaseModel):
    """Response con trace cross-file."""

    start_function: str = Field(..., description="Función de inicio")
    chain: List[CrossFileCallChain] = Field(..., description="Cadena completa")
    max_depth_reached: bool = Field(..., description="Si alcanzó el límite")
    total_depth: int = Field(..., description="Profundidad total alcanzada")


@router.post("/analyze-cross-file", response_model=CrossFileCallGraphResponse)
async def analyze_cross_file(
    request: AnalyzeCrossFileRequest,
    state: AppState = Depends(get_app_state),
) -> CrossFileCallGraphResponse:
    """
    Analiza call graph con resolución de imports (Stage 2).

    **Características Stage 2:**
    - Sigue imports entre archivos
    - Resuelve llamadas a funciones importadas
    - Detecta entry points del proyecto
    - Cachea resultados por archivo

    **Formato de nombres:**
    - Nombres cualificados: `path/to/file.py::function_name`
    - Métodos de clase: `path/to/file.py::ClassName.method_name`

    **Ejemplo:**
    ```
    {
      "call_graph": {
        "server.py::create_app": [
          "settings.py::load_settings",
          "state.py::AppState"
        ]
      }
    }
    ```
    """
    _require_tree_sitter()

    # Resolver ruta
    try:
        target_path = state.resolve_path(request.file_path)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    # Verificar que sea Python
    if target_path.suffix != ".py":
        raise HTTPException(
            status_code=400,
            detail=f"Solo archivos Python (.py). Recibido: {target_path.suffix}",
        )

    # Analizar cross-file
    try:
        extractor = CrossFileCallGraphExtractor(
            project_root=state.settings.root_path, use_cache=True
        )

        extractor.analyze_file(target_path, recursive=request.recursive)

        # Limitar archivos analizados
        if len(extractor.analyzed_files) > request.max_files:
            raise HTTPException(
                status_code=400,
                detail=f"Demasiados archivos ({len(extractor.analyzed_files)}). "
                f"Límite: {request.max_files}. Usa recursive=False o aumenta max_files.",
            )

        result = extractor.export_to_dict()

        return CrossFileCallGraphResponse(
            call_graph=result["call_graph"],
            entry_points=result["entry_points"],
            total_functions=result["total_functions"],
            analyzed_files=result["analyzed_files"],
        )

    except (ValueError, OSError, PermissionError) as exc:
        raise HTTPException(
            status_code=400, detail=f"Error en análisis cross-file: {exc}"
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected error in analyze_cross_file endpoint")
        raise HTTPException(
            status_code=500, detail=f"Error inesperado en análisis cross-file: {exc}"
        ) from exc


@router.post("/trace-cross-file", response_model=TraceCrossFileResponse)
async def trace_cross_file(
    request: TraceCrossFileRequest,
    state: AppState = Depends(get_app_state),
) -> TraceCrossFileResponse:
    """
    Traza cadena de llamadas cross-file (Stage 2).

    **Características:**
    - Sigue llamadas entre archivos diferentes
    - Muestra path completo de ejecución
    - Detecta ciclos

    **Input:**
    - `start_function`: Nombre cualificado `"path/file.py::function"`
    - `max_depth`: Profundidad máxima a trazar

    **Ejemplo:**
    ```
    POST /tracer/trace-cross-file
    {
      "start_function": "code_map/server.py::create_app",
      "max_depth": 10
    }
    ```
    """
    _require_tree_sitter()

    try:
        # Parsear el nombre cualificado
        if "::" not in request.start_function:
            raise HTTPException(
                status_code=400,
                detail=f"Formato inválido. Use 'file.py::function'. Recibido: {request.start_function}",
            )

        file_part, func_part = request.start_function.rsplit("::", 1)
        target_path = state.settings.root_path / file_part

        if not target_path.exists():
            raise HTTPException(
                status_code=404, detail=f"Archivo no encontrado: {file_part}"
            )

        # Analizar proyecto desde ese archivo
        extractor = CrossFileCallGraphExtractor(
            project_root=state.settings.root_path, use_cache=True
        )

        extractor.analyze_file(target_path, recursive=True)

        # Verificar que la función existe
        if request.start_function not in extractor.call_graph:
            available = ", ".join(list(extractor.call_graph.keys())[:10])
            raise HTTPException(
                status_code=404,
                detail=f"Función '{request.start_function}' no encontrada. "
                f"Disponibles: {available}...",
            )

        # Trazar cadena
        chain_data = extractor.trace_chain_cross_file(
            request.start_function, max_depth=request.max_depth
        )

        # Convertir a modelo Pydantic
        chain = []
        for depth, qualified_name, callees in chain_data:
            # Parsear nombre cualificado
            if "::" in qualified_name:
                file_str, func_str = qualified_name.rsplit("::", 1)
            else:
                file_str, func_str = "unknown", qualified_name

            chain.append(
                CrossFileCallChain(
                    depth=depth,
                    qualified_name=qualified_name,
                    callees=callees,
                    file_path=file_str,
                    function_name=func_str,
                )
            )

        max_depth_reached = any(item.depth >= request.max_depth for item in chain)
        total_depth = max(item.depth for item in chain) if chain else 0

        return TraceCrossFileResponse(
            start_function=request.start_function,
            chain=chain,
            max_depth_reached=max_depth_reached,
            total_depth=total_depth,
        )

    except HTTPException:
        raise
    except (ValueError, KeyError) as exc:
        raise HTTPException(
            status_code=400, detail=f"Error al trazar cross-file: {exc}"
        ) from exc
    except Exception as exc:
        logger.exception("Unexpected error in trace_cross_file endpoint")
        raise HTTPException(
            status_code=500, detail=f"Error inesperado al trazar cross-file: {exc}"
        ) from exc
