# Fase 2: Modelo Interno del Grafo

**Objetivo**: Definir estructuras de datos para representar el grafo de instancias

---

## Estructuras Principales

### InstanceNode

```python
@dataclass
class InstanceNode:
    """Nodo del grafo: una instancia concreta."""

    id: str                    # UUID único
    name: str                  # Nombre de variable ("m1", "generator")
    type_symbol: str           # Clase/tipo ("GeneratorModule")
    role: InstanceRole         # SOURCE, PROCESSING, SINK
    location: Location         # Archivo:línea de creación

    # Metadata
    args: Dict[str, Any]       # Argumentos de construcción
    config: Dict[str, Any]     # Configuración efectiva (si detectable)

    # Referencias
    type_location: Optional[Location]  # Dónde está definida la clase
    contract: Optional[ContractData]   # Contrato del tipo (lazy load)
```

### WiringEdge

```python
@dataclass
class WiringEdge:
    """Arista del grafo: conexión entre instancias."""

    id: str                    # UUID único
    source_id: str             # ID del nodo origen
    target_id: str             # ID del nodo destino
    method: str                # Método de conexión ("setNext")
    location: Location         # Call-site exacto

    # Metadata
    channel: Optional[str]     # Canal/puerto si aplica
    metadata: Dict[str, Any]   # Info adicional
```

### InstanceRole

```python
class InstanceRole(Enum):
    """Rol heurístico de una instancia en el pipeline."""

    SOURCE = "source"          # Genera datos, no recibe
    PROCESSING = "processing"  # Recibe y envía
    SINK = "sink"              # Recibe, no envía
    UNKNOWN = "unknown"        # No determinado
```

---

## Inferencia de Roles

### Heurísticas automáticas

| Condición | Rol inferido |
|-----------|--------------|
| No tiene aristas entrantes | SOURCE |
| No tiene aristas salientes | SINK |
| Tiene entrantes y salientes | PROCESSING |
| `receive()` es no-op | SOURCE |
| No llama a `next_->receive()` | SINK |

### Override manual

```python
# En código (futuro)
# @aegis-role: source

# En UI (MVP)
# Click derecho → Set Role → Source
```

El override se almacena en el bloque `@aegis-contract`:

```yaml
# @aegis-contract-begin
role: source  # Override manual
# @aegis-contract-end
```

---

## Grafo Completo

```python
@dataclass
class InstanceGraph:
    """Grafo completo de un composition root."""

    root_id: str                      # ID del composition root
    root_location: Location           # Ubicación del root
    nodes: Dict[str, InstanceNode]    # id → node
    edges: List[WiringEdge]           # Lista de conexiones

    # Índices para búsqueda rápida
    _nodes_by_name: Dict[str, str]    # name → id
    _nodes_by_type: Dict[str, List[str]]  # type → [ids]
    _outgoing: Dict[str, List[str]]   # node_id → [edge_ids]
    _incoming: Dict[str, List[str]]   # node_id → [edge_ids]

    def get_node(self, node_id: str) -> Optional[InstanceNode]:
        ...

    def get_node_by_name(self, name: str) -> Optional[InstanceNode]:
        ...

    def get_outgoing_edges(self, node_id: str) -> List[WiringEdge]:
        ...

    def get_incoming_edges(self, node_id: str) -> List[WiringEdge]:
        ...

    def get_connected_nodes(self, node_id: str) -> List[InstanceNode]:
        """Nodos conectados (entrantes + salientes)."""
        ...

    def topological_sort(self) -> List[InstanceNode]:
        """Ordenación topológica (source → sink)."""
        ...

    def find_sources(self) -> List[InstanceNode]:
        """Nodos sin aristas entrantes."""
        ...

    def find_sinks(self) -> List[InstanceNode]:
        """Nodos sin aristas salientes."""
        ...
```

---

## Persistencia

### MVP: Sin persistencia

- Recalcular desde código al refrescar
- No mantener modelo paralelo
- Estado vive solo en memoria durante sesión

### Futuro: Cache opcional

```python
# .aegis/cache/graph_{root_id}.json
{
    "root_id": "...",
    "computed_at": "2025-01-15T10:30:00Z",
    "source_hash": "abc123...",  # Hash del archivo fuente
    "nodes": [...],
    "edges": [...]
}
```

Invalidar cache si `source_hash` cambia.

---

## Integración con UI

El grafo se serializa para React Flow:

```python
def to_react_flow(self) -> dict:
    return {
        "nodes": [
            {
                "id": node.id,
                "type": "moduleInstance",
                "position": {"x": 0, "y": 0},  # Layout calcula
                "data": {
                    "name": node.name,
                    "typeName": node.type_symbol,
                    "role": node.role.value,
                    "location": str(node.location),
                    "hasContract": node.contract is not None,
                    "contractStatus": self._get_contract_status(node),
                }
            }
            for node in self.nodes.values()
        ],
        "edges": [
            {
                "id": edge.id,
                "source": edge.source_id,
                "target": edge.target_id,
                "type": "wiring",
                "data": {
                    "method": edge.method,
                    "location": str(edge.location),
                }
            }
            for edge in self.edges
        ]
    }
```

---

## Checklist

```
[ ] Definir InstanceNode dataclass
[ ] Definir WiringEdge dataclass
[ ] Definir InstanceRole enum
[ ] Implementar InstanceGraph con índices
[ ] Implementar inferencia de roles
[ ] Implementar to_react_flow()
[ ] Tests unitarios para grafo
```

---

## DoD

- [ ] Estructuras definidas y documentadas
- [ ] Grafo construible desde output de Fase 1
- [ ] Serialización a formato React Flow funciona
- [ ] Inferencia de roles correcta para Actia (m1=SOURCE, m2=PROCESSING, m3=SINK)
