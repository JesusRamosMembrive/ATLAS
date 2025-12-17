# Fase 6: Evidencia Obligatoria y Gates

**Objetivo**: Verificar contratos con tests/linters como gates bloqueantes

---

## Concepto

> **Un contrato sin evidencia es solo documentación. Con evidencia es una garantía.**

Los gates aseguran que:
- Contratos `required` tienen evidencia que pasa
- No se puede aplicar patch si gates fallan
- El estado de evidencia es visible en el grafo

---

## Tipos de Evidencia (MVP)

| Tipo | Descripción | Herramientas |
|------|-------------|--------------|
| `test` | Test unitario/integración | pytest, ctest, jest |
| `lint` | Análisis estático | ruff, clang-tidy, eslint |
| `typecheck` | Verificación de tipos | mypy, pyright, tsc |

---

## Schema de Evidencia

```python
class EvidencePolicy(Enum):
    REQUIRED = "required"    # Bloqueante
    OPTIONAL = "optional"    # Informativo
    WARNING = "warning"      # Aviso pero no bloquea

@dataclass
class EvidenceItem:
    type: str                # 'test', 'lint', 'typecheck'
    reference: str           # path::test_name o tool_name
    policy: EvidencePolicy
    last_result: Optional[bool] = None
    last_run: Optional[datetime] = None
    last_output: Optional[str] = None

@dataclass
class EvidenceResult:
    item: EvidenceItem
    passed: bool
    duration_ms: float
    output: str
    run_at: datetime
```

---

## Referencia de Evidencia en Contratos

```yaml
# @aegis-contract-begin
invariants:
  - pipeline must be started before process()
evidence:
  - test: tests/module_test.cpp::TestProcessFlow
    policy: required
  - test: tests/integration/pipeline_test.cpp::TestFullPipeline
    policy: optional
  - lint: clang-tidy
    policy: required
# @aegis-contract-end
```

---

## Ejecución de Gates

### Pipeline de Ejecución

```
Trigger (patch, manual, schedule)
        ↓
┌─────────────────────────────────┐
│  Recopilar evidencia requerida  │
│  del contrato                   │
└─────────────────────────────────┘
        ↓
┌─────────────────────────────────┐
│  Ejecutar tests                 │  ← pytest, ctest
│  (en paralelo si posible)       │
└─────────────────────────────────┘
        ↓
┌─────────────────────────────────┐
│  Ejecutar linters               │  ← ruff, clang-tidy
└─────────────────────────────────┘
        ↓
┌─────────────────────────────────┐
│  Ejecutar typecheck             │  ← mypy (opcional)
└─────────────────────────────────┘
        ↓
┌─────────────────────────────────┐
│  Agregar resultados             │
│  Determinar pass/fail global    │
└─────────────────────────────────┘
        ↓
    Pass? ──No──→ BLOQUEAR + mostrar errores
        │
       Yes
        ↓
    PERMITIR acción
```

### Integración con Linter Pipeline

Reutilizar `code_map/linters/pipeline.py`:

```python
from code_map.linters.pipeline import LinterPipeline

async def run_lint_evidence(reference: str) -> EvidenceResult:
    """Ejecuta linter específico como evidencia."""
    pipeline = LinterPipeline()

    if reference == "ruff":
        result = await pipeline.run_ruff()
    elif reference == "clang-tidy":
        result = await pipeline.run_clang_tidy()
    # ...

    return EvidenceResult(
        passed=result.exit_code == 0,
        output=result.output,
        duration_ms=result.duration,
        run_at=datetime.now(),
    )
```

### Ejecución de Tests Específicos

```python
import subprocess

async def run_test_evidence(reference: str) -> EvidenceResult:
    """Ejecuta test específico como evidencia."""
    # reference = "tests/module_test.cpp::TestProcessFlow"
    file_path, test_name = reference.rsplit("::", 1)

    if file_path.endswith(".py"):
        cmd = ["pytest", file_path, "-k", test_name, "-v"]
    elif file_path.endswith(".cpp"):
        # Asume ctest o ejecutable de test
        cmd = ["ctest", "-R", test_name, "-V"]

    start = time.perf_counter()
    result = subprocess.run(cmd, capture_output=True, text=True)
    duration = (time.perf_counter() - start) * 1000

    return EvidenceResult(
        passed=result.returncode == 0,
        output=result.stdout + result.stderr,
        duration_ms=duration,
        run_at=datetime.now(),
    )
```

---

## UI: Visualización de Estados

### Badges en Nodos

| Estado | Badge | Color | Significado |
|--------|-------|-------|-------------|
| all_pass | ✅ | Verde | Toda evidencia required pasa |
| some_fail | ❌ | Rojo | Al menos una required falla |
| not_run | ⏳ | Gris | Evidencia no ejecutada |
| no_evidence | ⚠️ | Amarillo | Contrato sin evidencia |

### Panel de Evidencia

```
┌─────────────────────────────────────────────┐
│ EVIDENCE                           [Run All]│
├─────────────────────────────────────────────┤
│ ✅ tests/module_test.cpp::TestFlow          │
│    Passed in 45ms (2 min ago)               │
│                                             │
│ ❌ tests/integration/test.cpp::TestPipeline │
│    FAILED: assertion at line 42      [View] │
│    Run 5 min ago                            │
│                                             │
│ ✅ clang-tidy                               │
│    No issues found (1 min ago)              │
├─────────────────────────────────────────────┤
│ Status: 1/2 required passing                │
│ ⚠️ Cannot apply patch until all pass        │
└─────────────────────────────────────────────┘
```

---

## Gate en Apply

### Flujo de Patch

```
Usuario hace cambios con agente
        ↓
Agente genera DIFF
        ↓
UI muestra preview del diff
        ↓
Usuario click "Apply"
        ↓
┌─────────────────────────────────────────────┐
│  Backend ejecuta gates                      │
│  - Extrae símbolos afectados del diff       │
│  - Obtiene contratos de esos símbolos       │
│  - Ejecuta evidencia required               │
└─────────────────────────────────────────────┘
        ↓
    Gates pass? ──No──→ Mostrar errores
        │                 "Fix issues before applying"
       Yes
        ↓
    Aplicar diff
        ↓
    Confirmar éxito
```

### API

```yaml
POST /api/gates/run
  body:
    symbols: string[]        # Símbolos a validar
    scope: "required" | "all"
  response:
    passed: bool
    results: EvidenceResult[]
    blocking_failures: EvidenceResult[]  # Solo required que fallan

POST /api/patch/apply
  body:
    diff: string
    bypass_gates: bool       # Solo para admin/emergencias
  response:
    applied: bool
    gate_results?: GateResults
    error?: string
```

---

## Configuración de Gates por Proyecto

```yaml
# .aegis/gates.yaml

default_policy: required  # Para evidencia sin policy explícita

tools:
  python:
    lint:
      - ruff
      - mypy
    test: pytest

  cpp:
    lint:
      - clang-tidy
    test: ctest

# Override por archivo/símbolo
overrides:
  - pattern: "tests/*"
    policy: optional  # Tests no necesitan sus propios gates

  - pattern: "*_experimental.*"
    policy: warning   # Código experimental solo warning
```

---

## Checklist

```
[ ] Definir EvidenceItem y EvidenceResult
[ ] Integrar con linters/pipeline.py
[ ] Implementar run_test_evidence()
[ ] Implementar run_lint_evidence()
[ ] Crear endpoint POST /api/gates/run
[ ] UI: Badges de estado en nodos
[ ] UI: Panel de evidencia con resultados
[ ] Bloquear Apply si gates required fallan
[ ] Configuración .aegis/gates.yaml
[ ] Tests de integración
```

---

## DoD

- [ ] Ejecutar test específico como evidencia
- [ ] Ejecutar lint como evidencia
- [ ] Nodo muestra badge según estado de evidencia
- [ ] Panel muestra resultados detallados
- [ ] Apply bloqueado si hay required failing
- [ ] Mensaje claro de qué falla y cómo arreglar
