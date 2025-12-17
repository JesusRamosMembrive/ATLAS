# Fases 9-10: Escalabilidad y Documentación

**Objetivo**: Preparar para proyectos grandes y documentar el workflow completo

---

# Fase 9: Escalabilidad y Extensibilidad

## 9.1 Caching Incremental

### Problema

Re-parsear todo el proyecto en cada cambio es costoso para repos grandes.

### Solución: Cache por Archivo

```python
@dataclass
class FileCache:
    path: Path
    content_hash: str
    last_modified: datetime
    symbols: List[SymbolInfo]
    contracts: Dict[str, ContractData]
    ast_data: Any

class IncrementalAnalyzer:
    """Analizador con cache incremental."""

    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        self.cache: Dict[Path, FileCache] = {}

    def analyze(self, path: Path) -> FileCache:
        current_hash = self._hash_file(path)
        cached = self.cache.get(path)

        if cached and cached.content_hash == current_hash:
            return cached  # Cache hit

        # Cache miss: re-analizar
        result = self._full_analyze(path)
        result.content_hash = current_hash
        self.cache[path] = result
        self._persist_cache(path, result)

        return result

    def invalidate(self, path: Path):
        """Invalida cache de un archivo."""
        self.cache.pop(path, None)

    def invalidate_dependents(self, path: Path):
        """Invalida archivos que dependen del cambiado."""
        for dep_path in self._find_dependents(path):
            self.invalidate(dep_path)
```

### Persistencia de Cache

```
.aegis/cache/
├── analysis/
│   ├── {file_hash}.json     # Análisis de símbolos
│   └── {file_hash}.contracts.json
├── graph/
│   └── {root_id}.json       # Grafo de instancias
└── evidence/
    └── {symbol_hash}.json   # Resultados de tests
```

---

## 9.2 Múltiples Composition Roots

### Problema

Proyectos grandes tienen múltiples executables/pipelines.

### Solución: Vista por Root

```python
@dataclass
class ProjectRoots:
    roots: List[CompositionRoot]
    default_root: Optional[str]

    def get_root(self, root_id: str) -> CompositionRoot:
        ...

    def list_roots(self) -> List[str]:
        ...

# UI permite seleccionar root activo
GET /api/roots
  response:
    roots: [
      { id: "main", name: "Main Pipeline", file: "main.cpp" },
      { id: "test_runner", name: "Test Runner", file: "test_main.cpp" },
    ]

GET /api/graph?root=main
  # Grafo del root seleccionado
```

### UI: Selector de Root

```
┌─────────────────────────────────────────────┐
│ Root: [Main Pipeline ▼]                     │
│       ├── Main Pipeline                     │
│       ├── Test Runner                       │
│       └── + Add Root...                     │
└─────────────────────────────────────────────┘
```

---

## 9.3 Plugins de Wiring

### Problema

Wiring indirecto (DI, config files, builders) no se detecta automáticamente.

### Solución: Sistema de Plugins

```python
class WiringPlugin(ABC):
    """Plugin para detectar wiring no estándar."""

    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def detect_instances(self, file: Path) -> List[InstanceInfo]:
        """Detecta instancias creadas por este mecanismo."""
        pass

    @abstractmethod
    def detect_wiring(self, file: Path) -> List[WiringInfo]:
        """Detecta conexiones creadas por este mecanismo."""
        pass

# Ejemplo: Plugin para Spring DI
class SpringDIPlugin(WiringPlugin):
    @property
    def name(self) -> str:
        return "spring_di"

    def detect_instances(self, file: Path) -> List[InstanceInfo]:
        # Buscar @Bean, @Component, etc.
        ...

    def detect_wiring(self, file: Path) -> List[WiringInfo]:
        # Buscar @Autowired, constructor injection
        ...
```

### Registro de Plugins

```python
class WiringPluginRegistry:
    plugins: Dict[str, WiringPlugin] = {}

    @classmethod
    def register(cls, plugin: WiringPlugin):
        cls.plugins[plugin.name] = plugin

    @classmethod
    def detect_all(cls, file: Path) -> Tuple[List[InstanceInfo], List[WiringInfo]]:
        instances = []
        wiring = []
        for plugin in cls.plugins.values():
            instances.extend(plugin.detect_instances(file))
            wiring.extend(plugin.detect_wiring(file))
        return instances, wiring
```

---

## 9.4 Role Inference Mejorado

### Persistencia de Roles Manuales

Guardar en contrato:

```yaml
# @aegis-contract-begin
role: source  # Manual override, no inferir
# @aegis-contract-end
```

### Heurísticas Mejoradas

```python
def infer_role(node: InstanceNode, graph: InstanceGraph) -> InstanceRole:
    # 1. Override manual en contrato
    if node.contract and node.contract.role:
        return node.contract.role

    # 2. Por conexiones
    incoming = len(graph.get_incoming_edges(node.id))
    outgoing = len(graph.get_outgoing_edges(node.id))

    if incoming == 0 and outgoing > 0:
        return InstanceRole.SOURCE
    if outgoing == 0 and incoming > 0:
        return InstanceRole.SINK
    if incoming > 0 and outgoing > 0:
        return InstanceRole.PROCESSING

    # 3. Por análisis de código
    if has_noop_receive(node):
        return InstanceRole.SOURCE
    if not_calls_next(node):
        return InstanceRole.SINK

    return InstanceRole.UNKNOWN
```

---

## 9.5 Performance Targets

| Métrica | Target | Medición |
|---------|--------|----------|
| Análisis inicial (<1000 archivos) | <30s | Tiempo total |
| Análisis incremental (1 archivo) | <500ms | Con cache |
| Renderizado de grafo (<100 nodos) | <100ms | Hasta interactive |
| Búsqueda de símbolos | <200ms | Con índice |
| Ejecución de gate individual | Variable | Depende del test |

---

# Fase 10: Documentación y Criterios de Aceptación

## 10.1 Workflow End-to-End

### Documento: docs/WORKFLOW.md

```markdown
# AEGIS v2 Workflow

## 1. Descubrir Pipeline

1. Abrir proyecto en AEGIS
2. AEGIS detecta composition roots automáticamente
3. Seleccionar root a visualizar
4. Ver grafo de instancias

## 2. Añadir Contrato

1. Click en nodo del grafo
2. Tab "Type" → "Edit Contract"
3. Definir:
   - Thread safety
   - Invariantes
   - Precondiciones
   - Evidencia requerida
4. Save → Bloque @aegis-contract insertado en código

## 3. Vincular Evidencia

1. En editor de contrato, sección "Evidence"
2. Click "Add Evidence"
3. Seleccionar tipo (test/lint)
4. Buscar test existente o crear referencia
5. Definir policy (required/optional)
6. Save

## 4. Ejecutar Agente con Control

1. Seleccionar nodos a modificar
2. Describir tarea
3. Revisar PLAN generado
4. Aprobar plan
5. Revisar DIFF
6. Ejecutar GATES
7. Si gates pasan → Apply
8. Si gates fallan → Fix o Discard
```

---

## 10.2 Checklist de Calidad

### Para Usuarios

```markdown
## Checklist Pre-Apply

- [ ] Plan revisado y aprobado
- [ ] Diff revisado línea por línea
- [ ] Nodos afectados identificados en grafo
- [ ] Gates ejecutados
- [ ] Todos los gates required pasan
- [ ] No hay drift crítico nuevo
```

### Para Desarrollo

```markdown
## Checklist de Release

- [ ] Todos los tests pasan
- [ ] Documentación actualizada
- [ ] CHANGELOG actualizado
- [ ] Performance targets cumplidos
- [ ] No hay TODOs críticos
- [ ] Review de seguridad completado
```

---

## 10.3 Guía de Estilo para Contratos

### Documento: docs/CONTRACT_STYLE.md

```markdown
# Guía de Estilo para Contratos AEGIS

## Formato

- Usar YAML válido dentro del bloque
- Indentación: 2 espacios
- Strings sin comillas (excepto si contienen caracteres especiales)

## Contenido

### Thread Safety
Valores permitidos:
- `not_safe`: No usar desde múltiples threads
- `safe`: Usar desde cualquier thread
- `safe_after_start`: Safe solo después de inicialización
- `immutable`: Objeto no cambia después de construcción

### Invariantes
- Escribir como afirmaciones positivas
- Ser específico sobre el estado
- Ejemplo: "pipeline must be started before process()"

### Precondiciones
- Usar formato: "<param> <condición>"
- Ejemplo: "input != nullptr"

### Evidence
- Referencia completa: "path/to/test.cpp::TestName"
- Policy explícita para required
```

---

## 10.4 Criterios de Aceptación Global

### MVP Completado Cuando

| Criterio | Verificación |
|----------|--------------|
| Detecta composition root | main.cpp de Actia detectado |
| Extrae instancias | m1, m2, m3 visibles en grafo |
| Detecta wiring | m1→m2, m2→m3 como aristas |
| Muestra contratos | Tab Type muestra contrato de IModule |
| Crea contratos | Usuario puede añadir contrato nuevo |
| Ejecuta gates | Tests y lints ejecutan correctamente |
| Bloquea si falla | Apply deshabilitado con gates rojos |
| Detecta drift | Cambio en código genera warning |
| Control de agente | Flujo plan→diff→gates→apply funciona |

### Métricas de Éxito

| Métrica | Target |
|---------|--------|
| Tiempo para entender pipeline | <5 min (nuevo usuario) |
| Tiempo para añadir contrato | <2 min |
| Confianza en aplicar cambios | >80% (encuesta) |
| Reducción de bugs post-agente | >50% |

---

## Checklist Fase 9-10

```
[ ] Implementar cache incremental
[ ] Soporte para múltiples roots
[ ] UI selector de root
[ ] Sistema de plugins de wiring
[ ] Role inference mejorado
[ ] Performance profiling
[ ] Documento WORKFLOW.md
[ ] Documento CONTRACT_STYLE.md
[ ] Checklist de calidad
[ ] Criterios de aceptación verificados
[ ] Release notes
```

---

## DoD

- [ ] Cache reduce tiempo de análisis >50%
- [ ] Múltiples roots seleccionables
- [ ] Documentación completa y revisada
- [ ] Usuario puede replicar workflow sin ayuda
- [ ] Todos los criterios de aceptación cumplidos
