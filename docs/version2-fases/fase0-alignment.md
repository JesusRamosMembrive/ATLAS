# Fase 0: Alineación Técnica y Constraints

**Objetivo**: Establecer principios no negociables antes de implementar

---

## Principios Fundamentales

### 1. Instancias para el mapa, clases para la verdad

```
MAPA (Runtime)                    VERDAD (Estática)
──────────────                    ─────────────────
- Instancias concretas            - Clases/interfaces
- Wiring (conexiones)             - Contratos
- Configuración efectiva          - Invariantes
- Grafo visual                    - Evidencia (tests)
```

### 2. Código como fuente de verdad

- **NO existe archivo modelo paralelo**
- Contratos embebidos en comentarios/docstrings
- AEGIS es propietario de bloques delimitados `@aegis-contract`
- La UI edita el código, no un modelo

### 3. Control verificable del agente

```
Agente → PLAN → DIFF → GATES → APPLY
         ↓       ↓       ↓       ↓
      visible  visible  pass?  usuario
                                decide
```

---

## Constraints No Negociables

| Constraint | Razón |
|------------|-------|
| Sin segundo archivo de modelo | Evita drift código↔modelo |
| Contratos en código | Single source of truth |
| Gates obligatorios | Sin evidencia = sin apply |
| Diff antes de aplicar | Auditoría completa |
| Bloque delimitado | Rewriting seguro |

---

## Definiciones MVP

### Evidencia válida

| Tipo | Ejemplo | Política |
|------|---------|----------|
| Test unitario | `tests/test_module.py::test_x` | required/optional |
| Test integración | `tests/integration/test_flow.py` | required/optional |
| Lint | `clang-tidy`, `ruff` | required/optional |
| Typecheck | `mypy`, `pyright` | optional |

### Gates bloqueantes (MVP)

**C++:**
- `clang-tidy` (si configurado)
- `ctest` (tests)

**Python:**
- `ruff` (lint)
- `pytest` (tests)
- `mypy` (opcional)

---

## Checklist Fase 0

```
[ ] Documentar principio "instancias para mapa, clases para verdad"
[ ] Documentar "no second model file"
[ ] Definir tipos de evidencia válidos
[ ] Definir gates bloqueantes por lenguaje
[ ] Crear docs/version2-principles.md con todo lo anterior
```

---

## DoD (Definition of Done)

- [ ] Documento de principios revisado y aprobado
- [ ] Equipo alineado en constraints
- [ ] No hay ambigüedad sobre qué es evidencia válida
