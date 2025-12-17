# Fase 5: Integración y Persistencia del Instance Graph

**Objetivo**: Persistir el grafo de instancias, integrarlo con el sistema existente de Code Map, y soportar actualización incremental cuando cambian archivos.

---

## Resumen Ejecutivo

Esta fase añade:
1. **Persistencia del grafo** en `.code-map/instance-graphs.json`
2. **Servicio centralizado** que gestiona el ciclo de vida del grafo
3. **Actualización incremental** via integración con el watcher existente
4. **API mejorada** con cache inteligente y consultas sobre grafos persistidos

---

## Arquitectura

### Diagrama de Componentes

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              AppState                                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────────┐  │
│  │ ProjectScanner│  │ SymbolIndex  │  │   InstanceGraphService       │  │
│  │              │  │              │  │  ┌────────────────────────┐  │  │
│  └──────────────┘  └──────────────┘  │  │  Cache (memory)        │  │  │
│  ┌──────────────┐  ┌──────────────┐  │  └────────────────────────┘  │  │
│  │WatcherManager│  │ChangeScheduler│  │  ┌────────────────────────┐  │  │
│  └──────────────┘  └──────────────┘  │  │  InstanceGraphStore    │  │  │
│         │                 │          │  │  (JSON persistence)    │  │  │
│         │                 │          │  └────────────────────────┘  │  │
│         │                 │          └──────────────────────────────┘  │
│         │                 │                        ▲                    │
│         ▼                 ▼                        │                    │
│  ┌─────────────────────────────────────────────────┴───────────────┐   │
│  │                    _scheduler_loop()                              │   │
│  │  - Procesa batches de cambios                                     │   │
│  │  - Actualiza SymbolIndex                                          │   │
│  │  - Notifica InstanceGraphService de cambios C++                   │   │
│  └───────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

### Flujo de Datos

```
1. Startup:
   AppState.startup()
       → InstanceGraphService.startup()
           → InstanceGraphStore.load()
               → Carga grafos desde .code-map/instance-graphs.json

2. Request GET /api/instance-graph/{path}:
   API endpoint
       → InstanceGraphService.get_graph(path)
           → Check cache validity (mtime comparison)
           → Si válido: return cached graph
           → Si inválido: re-analyze → update cache → persist

3. File Change Detected:
   WatcherManager detecta cambio en main.cpp
       → ChangeScheduler.enqueue()
       → AppState._scheduler_loop() drains batch
           → InstanceGraphService.handle_file_changes([main.cpp])
               → Re-analyze affected composition root
               → Update memory cache
               → Persist to disk
               → Notify via event_queue

4. Shutdown:
   AppState.shutdown()
       → InstanceGraphService.shutdown()
           → InstanceGraphStore.save()
```

---

## Componentes Nuevos

### 1. InstanceGraphStore (`code_map/v2/storage.py`)

Gestiona la persistencia del grafo en disco.

```python
@dataclass
class StoredInstanceGraph:
    """Representa un grafo de instancias persistido con metadata."""
    id: str                      # UUID del grafo
    project_path: str            # Ruta normalizada del proyecto
    source_file: str             # Archivo composition root (main.cpp)
    function_name: str           # "main"
    graph: InstanceGraph         # El grafo en sí
    analyzed_at: datetime        # Timestamp de análisis
    source_modified_at: datetime # mtime del source file
    node_count: int
    edge_count: int


class InstanceGraphStore:
    """Gestiona snapshots en `.code-map/instance-graphs.json`."""

    def __init__(self, root: Path):
        self.root = root
        self.store_path = root / ".code-map" / "instance-graphs.json"

    def load(self) -> List[StoredInstanceGraph]:
        """Carga grafos desde disco."""

    def save(self, graphs: List[StoredInstanceGraph]) -> None:
        """Persiste grafos a disco."""
```

**Formato JSON:**
```json
{
    "version": "1.0",
    "project_path": "/home/user/project",
    "updated_at": "2024-01-15T10:30:00Z",
    "graphs": [
        {
            "id": "uuid-1234",
            "source_file": "main.cpp",
            "function_name": "main",
            "analyzed_at": "2024-01-15T10:30:00Z",
            "source_modified_at": "2024-01-15T10:00:00Z",
            "nodes": [
                {
                    "id": "node-uuid",
                    "name": "m1",
                    "type_symbol": "GeneratorModule",
                    "role": "source",
                    "location": {...},
                    "args": [],
                    "config": {}
                }
            ],
            "edges": [
                {
                    "id": "edge-uuid",
                    "source_id": "node-uuid-1",
                    "target_id": "node-uuid-2",
                    "method": "setNext",
                    "location": {...}
                }
            ]
        }
    ]
}
```

### 2. InstanceGraphService (`code_map/v2/service.py`)

Servicio central que coordina análisis, cache y persistencia.

```python
class InstanceGraphService:
    """
    Gestiona el ciclo de vida del grafo de instancias.

    Responsabilidades:
    - Cache en memoria de grafos
    - Coordinación con InstanceGraphStore para persistencia
    - Actualización incremental cuando cambian archivos
    - API para consultas
    """

    def __init__(
        self,
        root_path: Path,
        store: InstanceGraphStore,
        extractor: CppCompositionExtractor,
        builder: GraphBuilder,
    ):
        pass

    async def startup(self) -> None:
        """Carga grafos persistidos al iniciar."""

    async def shutdown(self) -> None:
        """Persiste estado actual al cerrar."""

    async def get_graph(
        self,
        project_path: Path,
        force_refresh: bool = False
    ) -> Optional[InstanceGraph]:
        """Obtiene el grafo, usando cache si válido."""

    async def handle_file_changes(
        self,
        changed_files: List[Path]
    ) -> List[str]:
        """
        Procesa cambios de archivos.

        Returns:
            Lista de source_files que fueron re-analizados
        """

    def list_graphs(self) -> List[StoredInstanceGraph]:
        """Lista todos los grafos conocidos."""

    def get_status(self) -> Dict[str, Any]:
        """Estado del servicio para API."""
```

---

## Modificaciones a Código Existente

### 1. Añadir `from_dict()` a Modelos (`code_map/v2/models.py`)

La serialización `to_dict()` ya existe. Necesitamos deserialización:

```python
# En Location
@classmethod
def from_dict(cls, data: Dict[str, Any]) -> "Location":
    return cls(
        file_path=Path(data["file_path"]),
        line=data["line"],
        column=data.get("column", 0),
        end_line=data.get("end_line"),
        end_column=data.get("end_column"),
    )

# En InstanceNode
@classmethod
def from_dict(cls, data: Dict[str, Any]) -> "InstanceNode":
    return cls(
        id=data["id"],
        name=data["name"],
        type_symbol=data["type_symbol"],
        role=InstanceRole(data["role"]),
        location=Location.from_dict(data["location"]),
        args=data.get("args", []),
        config=data.get("config", {}),
        type_location=Location.from_dict(data["type_location"]) if data.get("type_location") else None,
        contract=data.get("contract"),
    )

# En WiringEdge
@classmethod
def from_dict(cls, data: Dict[str, Any]) -> "WiringEdge":
    return cls(
        id=data["id"],
        source_id=data["source_id"],
        target_id=data["target_id"],
        method=data["method"],
        location=Location.from_dict(data["location"]),
        channel=data.get("channel"),
        metadata=data.get("metadata", {}),
    )

# En InstanceGraph
@classmethod
def from_dict(cls, data: Dict[str, Any]) -> "InstanceGraph":
    graph = cls(
        source_file=Path(data["source_file"]) if data.get("source_file") else None,
        function_name=data.get("function_name"),
    )
    for node_data in data.get("nodes", []):
        graph.add_node(InstanceNode.from_dict(node_data))
    for edge_data in data.get("edges", []):
        graph.add_edge(WiringEdge.from_dict(edge_data))
    return graph
```

### 2. Integración con AppState (`code_map/state.py`)

```python
@dataclass
class AppState:
    # ... campos existentes ...
    instance_graph: InstanceGraphService = field(init=False)

    def _build_components(self) -> None:
        # ... código existente ...

        # NEW: Instance Graph Service
        from code_map.v2 import GraphBuilder, InstanceGraphStore, InstanceGraphService
        from code_map.v2.composition import CppCompositionExtractor

        instance_graph_store = InstanceGraphStore(self.settings.root_path)
        instance_graph_extractor = CppCompositionExtractor()
        instance_graph_builder = GraphBuilder()

        self.instance_graph = InstanceGraphService(
            root_path=self.settings.root_path,
            store=instance_graph_store,
            extractor=instance_graph_extractor,
            builder=instance_graph_builder,
        )

    async def startup(self) -> None:
        # ... código existente ...
        await self.instance_graph.startup()

    async def shutdown(self) -> None:
        # ... código existente ...
        await self.instance_graph.shutdown()

    async def _scheduler_loop(self) -> None:
        while not self._stop_event.is_set():
            batch = await asyncio.to_thread(self.scheduler.drain, force=True)
            if batch:
                # Existing: Update symbol index
                changes = await asyncio.to_thread(
                    self.scanner.apply_change_batch, ...
                )

                # NEW: Update instance graphs for C++ files
                cpp_extensions = {".cpp", ".h", ".hpp", ".cc", ".cxx"}
                cpp_changes = [
                    f for f in batch.all_paths()
                    if f.suffix.lower() in cpp_extensions
                ]
                if cpp_changes:
                    updated = await self.instance_graph.handle_file_changes(cpp_changes)
                    if updated:
                        await self.event_queue.put({
                            "type": "instance_graph_updated",
                            "files": updated
                        })

            await asyncio.sleep(self.scheduler.debounce_seconds)
```

### 3. Extensiones del Watcher (`code_map/settings.py`)

```python
@dataclass
class AppSettings:
    # ... campos existentes ...

    # NEW: C++ extensions for instance graph analysis
    cpp_extensions: Set[str] = field(
        default_factory=lambda: {".cpp", ".h", ".hpp", ".cc", ".cxx"}
    )
```

### 4. API Endpoints Actualizados (`code_map/api/instance_graph.py`)

```python
from fastapi import APIRouter, HTTPException, Depends
from code_map.api.deps import get_app_state
from code_map.state import AppState

router = APIRouter(prefix="/instance-graph", tags=["instance-graph"])


@router.get("/")
async def list_instance_graphs(state: AppState = Depends(get_app_state)):
    """Lista todos los grafos de instancias conocidos."""
    graphs = state.instance_graph.list_graphs()
    return {
        "graphs": [
            {
                "id": g.id,
                "source_file": g.source_file,
                "function_name": g.function_name,
                "analyzed_at": g.analyzed_at.isoformat(),
                "node_count": g.node_count,
                "edge_count": g.edge_count,
            }
            for g in graphs
        ]
    }


@router.get("/status")
async def get_instance_graph_status(state: AppState = Depends(get_app_state)):
    """Estado del servicio de instance graph."""
    return state.instance_graph.get_status()


@router.get("/{project_path:path}")
async def get_instance_graph(
    project_path: str,
    force_refresh: bool = False,
    state: AppState = Depends(get_app_state),
):
    """
    Obtiene el grafo de instancias para un proyecto.

    Usa cache si está disponible y válido, a menos que force_refresh=True.
    """
    graph = await state.instance_graph.get_graph(
        Path(project_path),
        force_refresh=force_refresh
    )
    if graph is None:
        raise HTTPException(404, "No composition root found")

    return InstanceGraphResponse(
        nodes=graph.to_react_flow()["nodes"],
        edges=graph.to_react_flow()["edges"],
        metadata={...}
    )


@router.post("/{project_path:path}/refresh")
async def refresh_instance_graph(
    project_path: str,
    state: AppState = Depends(get_app_state),
):
    """Fuerza re-análisis del grafo."""
    return await get_instance_graph(project_path, force_refresh=True, state=state)
```

---

## Estructura de Archivos

```
code_map/v2/
├── __init__.py           # Exports actualizados
├── models.py             # + from_dict() methods
├── builder.py            # Sin cambios
├── storage.py            # NEW: InstanceGraphStore, StoredInstanceGraph
├── service.py            # NEW: InstanceGraphService
└── composition/
    ├── __init__.py
    ├── base.py
    └── cpp.py

code_map/api/
├── instance_graph.py     # MODIFICADO: usa InstanceGraphService
├── deps.py               # Sin cambios (get_app_state ya existe)

code_map/
├── state.py              # MODIFICADO: añade instance_graph
├── settings.py           # MODIFICADO: cpp_extensions

tests/
├── test_instance_graph_storage.py    # NEW
├── test_instance_graph_service.py    # NEW
├── test_instance_graph_integration.py # NEW
```

---

## Plan de Implementación

| Sub-fase | Duración | Entregable |
|----------|----------|------------|
| 5.1 Storage | 0.5 días | `storage.py` con load/save |
| 5.2 Serialización | 0.5 días | `from_dict()` methods |
| 5.3 Service | 1 día | `service.py` completo |
| 5.4 AppState | 0.5 días | Integración con scheduler |
| 5.5 API | 0.5 días | Endpoints actualizados |
| 5.6 Tests | 1 día | Tests unitarios e integración |

**Total estimado: ~4 días**

---

## Criterios de Aceptación (DoD)

- [ ] El grafo se persiste en `.code-map/instance-graphs.json`
- [ ] Al reiniciar el servidor, el grafo se carga desde disco
- [ ] Cuando cambia `main.cpp`, el grafo se actualiza automáticamente
- [ ] GET `/api/instance-graph/{path}` usa cache si válido
- [ ] POST `/api/instance-graph/{path}/refresh` fuerza re-análisis
- [ ] GET `/api/instance-graph/` lista grafos conocidos
- [ ] Tests pasan: storage, service, API
- [ ] TypeScript compila sin errores
- [ ] 365+ tests siguen pasando

---

## Riesgos y Mitigaciones

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|--------------|---------|------------|
| Race conditions en actualización | Media | Alto | Locks en el servicio |
| Cache stale no detectado | Baja | Medio | Invalidar por mtime + force refresh |
| JSON corruption | Baja | Alto | Backup antes de escribir |
| Proyecto sin main.cpp | Alta | Bajo | Error claro, no crash |
| Performance con grafos grandes | Baja | Medio | Lazy loading, pagination |

---

## Extensiones Futuras (No en MVP)

1. **Múltiples composition roots**: Ya soportado en el modelo
2. **Notificaciones SSE**: Event queue ya existe, solo añadir tipo de evento
3. **Python extractor**: Arquitectura lista, solo implementar extractor
4. **Incremental update de nodos**: Solo actualizar nodos afectados vs re-construir todo
5. **Histórico de cambios**: Versionar grafos en disco
