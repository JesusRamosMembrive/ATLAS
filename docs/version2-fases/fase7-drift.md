# Fase 7: Drift Detection

**Objetivo**: Detectar desalineaciones entre código, contratos y evidencia

---

## Tipos de Drift

### 1. Drift Estructural

Cambios en el código que invalidan el contrato.

| Situación | Ejemplo | Severidad |
|-----------|---------|-----------|
| Firma cambiada | Método añade parámetro no documentado | Alta |
| Tipo cambiado | Return type cambia sin actualizar contrato | Alta |
| Método eliminado | Contrato referencia método que no existe | Crítica |

### 2. Drift de Evidencia

Evidencia referenciada que no existe o está desactualizada.

| Situación | Ejemplo | Severidad |
|-----------|---------|-----------|
| Test no existe | `tests/foo_test.py::test_bar` no existe | Crítica |
| Test renombrado | Test movido a otro archivo | Alta |
| Test desactualizado | Test no cubre cambios recientes | Media |

### 3. Drift de Wiring

Cambios en el composition root que alteran el grafo.

| Situación | Ejemplo | Severidad |
|-----------|---------|-----------|
| Conexión eliminada | `m1.setNext(m2)` ya no existe | Alta |
| Conexión añadida | Nueva conexión no documentada | Media |
| Instancia eliminada | Nodo del grafo ya no existe | Alta |

### 4. Drift Semántico (Heurístico)

Contradicciones entre contrato e implementación.

| Situación | Ejemplo | Severidad |
|-----------|---------|-----------|
| Thread-safety falsa | Contrato dice "safe", código usa shared state sin lock | Crítica |
| Precondición no verificada | Contrato requiere `input != null`, código no valida | Alta |

---

## Detección Automática

### Trigger de Análisis

```
Cambio en archivo
        ↓
¿Archivo tiene símbolos con contratos?
        ↓ Sí
Ejecutar análisis de drift
        ↓
Comparar estado anterior vs actual
        ↓
Generar DriftReport
        ↓
Notificar UI
```

### Algoritmo de Detección

```python
@dataclass
class DriftItem:
    type: str              # 'structural', 'evidence', 'wiring', 'semantic'
    severity: str          # 'critical', 'high', 'medium', 'low'
    symbol: str            # Símbolo afectado
    description: str       # Descripción del drift
    location: Location     # Dónde ocurre
    suggested_fix: str     # Sugerencia de corrección

@dataclass
class DriftReport:
    file_path: Path
    analyzed_at: datetime
    items: List[DriftItem]

    @property
    def has_critical(self) -> bool:
        return any(d.severity == 'critical' for d in self.items)

def detect_drift(file_path: Path, previous_state: FileState) -> DriftReport:
    items = []

    # 1. Drift estructural
    items.extend(detect_structural_drift(file_path, previous_state))

    # 2. Drift de evidencia
    items.extend(detect_evidence_drift(file_path))

    # 3. Drift de wiring (si es composition root)
    if is_composition_root(file_path):
        items.extend(detect_wiring_drift(file_path, previous_state))

    # 4. Drift semántico (heurístico)
    items.extend(detect_semantic_drift(file_path))

    return DriftReport(
        file_path=file_path,
        analyzed_at=datetime.now(),
        items=items
    )
```

---

## Drift Estructural: Implementación

```python
def detect_structural_drift(file_path: Path, previous: FileState) -> List[DriftItem]:
    items = []
    current_symbols = analyze_file(file_path)

    for symbol in get_symbols_with_contracts(file_path):
        prev_symbol = previous.get_symbol(symbol.name)
        contract = get_contract(symbol)

        if prev_symbol is None:
            continue  # Símbolo nuevo, no hay drift

        # Comparar firmas
        if symbol.signature != prev_symbol.signature:
            items.append(DriftItem(
                type='structural',
                severity='high',
                symbol=symbol.name,
                description=f"Signature changed: {prev_symbol.signature} → {symbol.signature}",
                location=symbol.location,
                suggested_fix="Update contract to reflect new signature"
            ))

        # Verificar que precondiciones siguen siendo válidas
        for pre in contract.preconditions:
            if not is_precondition_checkable(symbol, pre):
                items.append(DriftItem(
                    type='structural',
                    severity='medium',
                    symbol=symbol.name,
                    description=f"Precondition may be invalid: {pre}",
                    location=symbol.location,
                    suggested_fix="Verify precondition still applies"
                ))

    return items
```

---

## Drift de Evidencia: Implementación

```python
def detect_evidence_drift(file_path: Path) -> List[DriftItem]:
    items = []

    for symbol in get_symbols_with_contracts(file_path):
        contract = get_contract(symbol)

        for evidence in contract.evidence:
            if evidence.type == 'test':
                test_path, test_name = parse_test_reference(evidence.reference)

                if not Path(test_path).exists():
                    items.append(DriftItem(
                        type='evidence',
                        severity='critical',
                        symbol=symbol.name,
                        description=f"Test file not found: {test_path}",
                        location=symbol.location,
                        suggested_fix=f"Create test or update evidence reference"
                    ))
                elif not test_exists_in_file(test_path, test_name):
                    items.append(DriftItem(
                        type='evidence',
                        severity='critical',
                        symbol=symbol.name,
                        description=f"Test not found: {evidence.reference}",
                        location=symbol.location,
                        suggested_fix=f"Test may have been renamed or deleted"
                    ))

    return items
```

---

## Drift de Wiring: Implementación

```python
def detect_wiring_drift(file_path: Path, previous: FileState) -> List[DriftItem]:
    items = []

    current_graph = extract_instance_graph(file_path)
    previous_graph = previous.instance_graph

    # Nodos eliminados
    for node_id in previous_graph.nodes:
        if node_id not in current_graph.nodes:
            node = previous_graph.nodes[node_id]
            items.append(DriftItem(
                type='wiring',
                severity='high',
                symbol=node.name,
                description=f"Instance removed from composition root",
                location=previous_graph.root_location,
                suggested_fix="Instance no longer exists in pipeline"
            ))

    # Conexiones eliminadas
    for edge in previous_graph.edges:
        if not edge_exists(current_graph, edge):
            items.append(DriftItem(
                type='wiring',
                severity='high',
                symbol=f"{edge.source} → {edge.target}",
                description=f"Connection removed: {edge.method}",
                location=edge.location,
                suggested_fix="Wiring changed, update documentation"
            ))

    # Conexiones añadidas (informativo)
    for edge in current_graph.edges:
        if not edge_exists(previous_graph, edge):
            items.append(DriftItem(
                type='wiring',
                severity='medium',
                symbol=f"{edge.source} → {edge.target}",
                description=f"New connection added: {edge.method}",
                location=edge.location,
                suggested_fix="Document new connection in architecture"
            ))

    return items
```

---

## Drift Semántico: Heurísticas

```python
def detect_semantic_drift(file_path: Path) -> List[DriftItem]:
    items = []
    source = file_path.read_text()

    for symbol in get_symbols_with_contracts(file_path):
        contract = get_contract(symbol)
        body = get_symbol_body(source, symbol)

        # Thread-safety check
        if contract.thread_safety == ThreadSafety.SAFE:
            if has_shared_state_without_lock(body):
                items.append(DriftItem(
                    type='semantic',
                    severity='critical',
                    symbol=symbol.name,
                    description="Contract claims thread-safe but code has unprotected shared state",
                    location=symbol.location,
                    suggested_fix="Add synchronization or update contract"
                ))

        # Precondition verification check
        for pre in contract.preconditions:
            if "!= null" in pre or "!= nullptr" in pre:
                param = extract_param_name(pre)
                if not has_null_check(body, param):
                    items.append(DriftItem(
                        type='semantic',
                        severity='high',
                        symbol=symbol.name,
                        description=f"Precondition '{pre}' not verified in code",
                        location=symbol.location,
                        suggested_fix=f"Add null check for {param}"
                    ))

    return items


def has_shared_state_without_lock(body: str) -> bool:
    """Heurística: detecta acceso a miembros sin lock visible."""
    # Buscar patrones como: member_ = value (sin mutex cerca)
    has_member_write = re.search(r'\w+_\s*=', body)
    has_lock = 'lock_guard' in body or 'unique_lock' in body or 'mutex' in body
    return bool(has_member_write and not has_lock)
```

---

## UI: Visualización de Drift

### Badge en Nodo

| Estado | Badge | Significado |
|--------|-------|-------------|
| No drift | (ninguno) | Todo OK |
| Drift warning | ⚠️ | Drift medium/low |
| Drift critical | 🔴 | Drift critical/high |

### Panel de Drift

```
┌─────────────────────────────────────────────┐
│ DRIFT DETECTED                    [Refresh] │
├─────────────────────────────────────────────┤
│ 🔴 CRITICAL                                 │
│ ──────────                                  │
│ Test not found: tests/old_test.py::test_x   │
│ Symbol: ProcessingModule                    │
│ Fix: Update evidence reference        [→]   │
│                                             │
│ ⚠️ WARNING                                  │
│ ─────────                                   │
│ New connection added: m2 → m4               │
│ Symbol: main.cpp composition root           │
│ Fix: Document new connection          [→]   │
├─────────────────────────────────────────────┤
│ 1 critical, 1 warning                       │
└─────────────────────────────────────────────┘
```

---

## API

```yaml
GET /api/drift/{file_path}
  response:
    report: DriftReport
    has_critical: bool

POST /api/drift/scan
  body:
    scope: "file" | "project"
    path: string
  response:
    reports: DriftReport[]
    summary:
      total_items: int
      critical: int
      high: int
      medium: int
```

---

## Checklist

```
[ ] Definir DriftItem y DriftReport
[ ] Implementar detect_structural_drift()
[ ] Implementar detect_evidence_drift()
[ ] Implementar detect_wiring_drift()
[ ] Implementar detect_semantic_drift() (heurísticas básicas)
[ ] Trigger automático en cambio de archivo
[ ] API GET /api/drift/{file}
[ ] UI: Badge de drift en nodos
[ ] UI: Panel de drift con detalles
[ ] Navegación a código desde drift item
```

---

## DoD

- [ ] Detectar test eliminado/renombrado
- [ ] Detectar cambio de firma en método con contrato
- [ ] Detectar conexión añadida/eliminada en wiring
- [ ] Badge visible en nodo con drift
- [ ] Panel muestra detalles y sugerencia de fix
- [ ] Click en drift navega al código
