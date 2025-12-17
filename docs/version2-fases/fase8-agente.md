# Fase 8: Integración con Agente en Modo Controlable

**Objetivo**: Control tangible sobre cambios del agente con flujo plan→diff→gates→apply

---

## Principio

> **El agente puede tocar lo que quiera, pero el usuario decide si se aplica.**

El control se logra mediante:
1. **PLAN visible** antes de editar
2. **DIFF visible** de todos los cambios
3. **GATES obligatorios** antes de aplicar
4. **UI clara** de qué se afecta

---

## Protocolo de Ejecución

### Flujo Completo

```
┌─────────────────────────────────────────────────────────────┐
│  1. CONTEXTO                                                │
│  Usuario selecciona nodos + describe tarea                  │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  2. PLAN                                                    │
│  Agente genera plan de cambios                              │
│  - Lista de archivos a modificar                            │
│  - Símbolos afectados                                       │
│  - Razón de cada cambio                                     │
│  Usuario revisa y aprueba plan                              │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  3. DIFF                                                    │
│  Agente ejecuta cambios en sandbox                          │
│  Genera diff unificado                                      │
│  UI muestra:                                                │
│  - Diff por archivo                                         │
│  - Nodos afectados (highlight en grafo)                     │
│  - Contratos que podrían invalidarse                        │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  4. GATES                                                   │
│  Ejecutar tests/lints de símbolos afectados                 │
│  Mostrar resultados                                         │
│  Si falla required: BLOQUEAR apply                          │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│  5. APPLY                                                   │
│  Usuario click "Apply"                                      │
│  Backend aplica diff al filesystem                          │
│  Actualizar grafo y estados                                 │
└─────────────────────────────────────────────────────────────┘
```

---

## Inputs al Agente

### Contexto Estructurado

```python
@dataclass
class AgentContext:
    """Información que recibe el agente."""

    # Nodos seleccionados
    selected_nodes: List[InstanceNode]

    # Contratos de los nodos seleccionados
    contracts: Dict[str, ContractData]  # symbol → contract

    # Evidencia requerida
    required_evidence: List[EvidenceItem]

    # Grafo completo (para entender relaciones)
    graph: InstanceGraph

    # Tarea del usuario
    user_request: str

    # Restricciones
    constraints: List[str]  # e.g., "no modificar IModule.h"
```

### Formato para Prompt

```markdown
## SELECTED COMPONENTS

### m2 (FilterModule)
- Location: FilterModule.h:12
- Role: PROCESSING
- Contract:
  - thread_safety: safe_after_start
  - invariants:
    - pipeline must be started before process()
  - evidence (required):
    - tests/filter_test.cpp::TestFilter

### Connections
- ← m1 (GeneratorModule)
- → m3 (PrinterModule)

## REQUIRED EVIDENCE
These tests MUST pass after your changes:
- tests/filter_test.cpp::TestFilter
- tests/integration/pipeline_test.cpp

## USER REQUEST
{user_request}

## CONSTRAINTS
- Do not modify interface IModule.h
- Maintain thread-safety guarantees
```

---

## Outputs del Agente

### Plan

```python
@dataclass
class AgentPlan:
    """Plan generado por el agente."""

    summary: str  # Resumen de 1-2 líneas

    steps: List[PlanStep]

    files_to_modify: List[str]
    symbols_affected: List[str]

    risks: List[str]  # Riesgos identificados
    assumptions: List[str]  # Suposiciones hechas

@dataclass
class PlanStep:
    description: str
    file: str
    symbol: Optional[str]
    change_type: str  # 'add', 'modify', 'delete'
```

### Diff

```python
@dataclass
class AgentDiff:
    """Diff generado por el agente."""

    # Diff unificado completo
    unified_diff: str

    # Por archivo
    file_diffs: List[FileDiff]

    # Mapeo a grafo
    affected_nodes: List[str]  # IDs de nodos
    affected_edges: List[str]  # IDs de aristas

    # Contratos potencialmente afectados
    contracts_at_risk: List[str]  # Símbolos

@dataclass
class FileDiff:
    path: str
    additions: int
    deletions: int
    diff: str  # Unified diff de este archivo
```

---

## UI: Vista de Plan

```
┌─────────────────────────────────────────────────────────────┐
│ AGENT PLAN                              [Approve] [Reject]  │
├─────────────────────────────────────────────────────────────┤
│ Summary: Add logging to FilterModule process method         │
│                                                             │
│ STEPS                                                       │
│ ─────                                                       │
│ 1. Modify FilterModule.cpp                                  │
│    Add logging statements to process()                      │
│                                                             │
│ 2. Modify FilterModule.h                                    │
│    Add logger member variable                               │
│                                                             │
│ FILES TO MODIFY                                             │
│ ───────────────                                             │
│ • FilterModule.cpp                                          │
│ • FilterModule.h                                            │
│                                                             │
│ SYMBOLS AFFECTED                                            │
│ ────────────────                                            │
│ • FilterModule::process                                     │
│ • FilterModule (class)                                      │
│                                                             │
│ ⚠️ RISKS                                                    │
│ • May affect performance due to logging overhead            │
│                                                             │
│ 📝 ASSUMPTIONS                                              │
│ • Logger library already available                          │
└─────────────────────────────────────────────────────────────┘
```

---

## UI: Vista de Diff

```
┌─────────────────────────────────────────────────────────────┐
│ CHANGES                              [Apply] [Discard]      │
├─────────────────────────────────────────────────────────────┤
│ [FilterModule.cpp] [FilterModule.h]                         │
├─────────────────────────────────────────────────────────────┤
│  FilterModule.cpp (+12, -2)                                 │
│ ─────────────────────────────────────────────────────────── │
│  15   void FilterModule::process(const ByteArray& input) {  │
│  16 +   logger_.debug("Processing input of size {}",        │
│  17 +                 input.size());                        │
│  18                                                         │
│  19     std::unique_lock lock(mutex_);                      │
│  20     // ... existing code ...                            │
│  21                                                         │
│  22 +   logger_.debug("Processing complete");               │
│  23   }                                                     │
├─────────────────────────────────────────────────────────────┤
│ AFFECTED IN GRAPH                                           │
│ [Grafo pequeño con m2 highlighted en amarillo]              │
│                                                             │
│ GATES STATUS                                                │
│ ────────────                                                │
│ ⏳ tests/filter_test.cpp::TestFilter      [Run]             │
│ ⏳ clang-tidy                             [Run]             │
│                                                             │
│ [Run All Gates]                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## UI: Grafo con Cambios Destacados

Al visualizar diff, el grafo muestra:

| Estado del nodo | Visualización |
|-----------------|---------------|
| Sin cambios | Normal |
| Modificado | Borde amarillo pulsante |
| Añadido | Borde verde, icono ➕ |
| Eliminado | Borde rojo, semitransparente |

---

## API

```yaml
# Generar plan
POST /api/agent/plan
  body:
    context: AgentContext
  response:
    plan: AgentPlan
    session_id: string  # Para continuar

# Aprobar plan y generar diff
POST /api/agent/execute
  body:
    session_id: string
    approved_plan: AgentPlan
  response:
    diff: AgentDiff

# Ejecutar gates
POST /api/agent/gates
  body:
    session_id: string
    diff: AgentDiff
  response:
    results: GateResults
    can_apply: bool

# Aplicar cambios
POST /api/agent/apply
  body:
    session_id: string
    diff: AgentDiff
    bypass_gates: bool  # Solo admin
  response:
    applied: bool
    files_modified: string[]
    errors?: string[]

# Descartar sesión
DELETE /api/agent/session/{session_id}
```

---

## Sandbox de Ejecución

El agente ejecuta cambios en un sandbox antes de aplicar:

```python
class AgentSandbox:
    """Sandbox para cambios del agente."""

    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.temp_dir = tempfile.mkdtemp()
        self.changes: Dict[Path, str] = {}

    def write_file(self, path: Path, content: str):
        """Escribe archivo en sandbox (no en disco real)."""
        self.changes[path] = content

    def get_diff(self) -> str:
        """Genera diff unificado de todos los cambios."""
        diffs = []
        for path, new_content in self.changes.items():
            original = (self.project_root / path).read_text()
            diff = unified_diff(
                original.splitlines(),
                new_content.splitlines(),
                fromfile=f"a/{path}",
                tofile=f"b/{path}",
            )
            diffs.append("\n".join(diff))
        return "\n".join(diffs)

    def apply(self):
        """Aplica cambios al filesystem real."""
        for path, content in self.changes.items():
            (self.project_root / path).write_text(content)

    def discard(self):
        """Descarta todos los cambios."""
        self.changes.clear()
        shutil.rmtree(self.temp_dir, ignore_errors=True)
```

---

## Checklist

```
[ ] Definir AgentContext, AgentPlan, AgentDiff
[ ] Implementar AgentSandbox
[ ] API POST /api/agent/plan
[ ] API POST /api/agent/execute
[ ] API POST /api/agent/gates
[ ] API POST /api/agent/apply
[ ] UI: Vista de plan con approve/reject
[ ] UI: Vista de diff con syntax highlight
[ ] UI: Grafo con nodos afectados highlighted
[ ] UI: Panel de gates con run/status
[ ] Bloqueo de apply si gates required fallan
[ ] Integración con agente CLI existente
```

---

## DoD

- [ ] Usuario ve plan antes de que agente ejecute
- [ ] Usuario ve diff completo de cambios propuestos
- [ ] Nodos afectados visibles en grafo (highlight)
- [ ] Gates ejecutan y muestran resultados
- [ ] Apply bloqueado si gates fallan
- [ ] Apply escribe cambios al filesystem
- [ ] Discard descarta sin efectos
