# Fase 3: React Flow - Visualización del Grafo

**Objetivo**: Renderizar el grafo de instancias con React Flow

---

## Stack Tecnológico

- **React Flow** (`@xyflow/react`) - Canvas de grafos
- **React** - UI framework
- **TypeScript** - Tipado
- **Tailwind CSS** - Estilos (si ya está en el proyecto)

---

## Node Types

### ModuleInstance Node

```tsx
// components/nodes/ModuleInstanceNode.tsx

interface ModuleInstanceData {
  name: string;
  typeName: string;
  role: 'source' | 'processing' | 'sink' | 'unknown';
  location: string;
  hasContract: boolean;
  contractStatus: 'verified' | 'inferred' | 'missing' | 'failing';
}

export function ModuleInstanceNode({ data }: NodeProps<ModuleInstanceData>) {
  const roleColors = {
    source: 'border-green-500 bg-green-50',
    processing: 'border-blue-500 bg-blue-50',
    sink: 'border-purple-500 bg-purple-50',
    unknown: 'border-gray-500 bg-gray-50',
  };

  const statusBadge = {
    verified: { icon: '✅', color: 'text-green-600' },
    inferred: { icon: '🤖', color: 'text-yellow-600' },
    missing: { icon: '❓', color: 'text-red-600' },
    failing: { icon: '❌', color: 'text-red-600' },
  };

  return (
    <div className={`px-4 py-2 rounded-lg border-2 ${roleColors[data.role]}`}>
      {/* Handle de entrada */}
      <Handle type="target" position={Position.Left} />

      {/* Contenido */}
      <div className="flex items-center gap-2">
        <span className="font-mono font-bold">{data.name}</span>
        <span className={statusBadge[data.contractStatus].color}>
          {statusBadge[data.contractStatus].icon}
        </span>
      </div>
      <div className="text-xs text-gray-500">{data.typeName}</div>

      {/* Handle de salida */}
      <Handle type="source" position={Position.Right} />
    </div>
  );
}
```

### Registro de Node Types

```tsx
const nodeTypes = {
  moduleInstance: ModuleInstanceNode,
};
```

---

## Edge Types

### Wiring Edge

```tsx
// components/edges/WiringEdge.tsx

interface WiringEdgeData {
  method: string;
  location: string;
}

export function WiringEdge({
  sourceX, sourceY,
  targetX, targetY,
  data,
  selected,
}: EdgeProps<WiringEdgeData>) {
  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX, sourceY,
    targetX, targetY,
  });

  return (
    <>
      <path
        className={`stroke-2 fill-none ${
          selected ? 'stroke-blue-600' : 'stroke-gray-400'
        }`}
        d={edgePath}
      />
      {data?.method && (
        <foreignObject
          x={labelX - 30}
          y={labelY - 10}
          width={60}
          height={20}
        >
          <div className="text-xs bg-white px-1 rounded border text-center">
            {data.method}
          </div>
        </foreignObject>
      )}
    </>
  );
}
```

---

## Layout

### Pipeline Layout (izquierda → derecha)

```tsx
// utils/layout.ts

import dagre from 'dagre';

export function layoutPipeline(
  nodes: Node[],
  edges: Edge[]
): { nodes: Node[]; edges: Edge[] } {
  const g = new dagre.graphlib.Graph();

  g.setGraph({
    rankdir: 'LR',      // Left to Right
    nodesep: 50,        // Separación vertical
    ranksep: 100,       // Separación horizontal
  });

  g.setDefaultEdgeLabel(() => ({}));

  // Añadir nodos
  nodes.forEach((node) => {
    g.setNode(node.id, { width: 150, height: 60 });
  });

  // Añadir aristas
  edges.forEach((edge) => {
    g.setEdge(edge.source, edge.target);
  });

  // Calcular layout
  dagre.layout(g);

  // Aplicar posiciones
  const layoutedNodes = nodes.map((node) => {
    const nodeWithPosition = g.node(node.id);
    return {
      ...node,
      position: {
        x: nodeWithPosition.x - 75,  // Centrar
        y: nodeWithPosition.y - 30,
      },
    };
  });

  return { nodes: layoutedNodes, edges };
}
```

---

## Componente Principal

```tsx
// components/ArchitectureGraph.tsx

import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  useNodesState,
  useEdgesState,
} from '@xyflow/react';

interface ArchitectureGraphProps {
  graphData: {
    nodes: Node[];
    edges: Edge[];
  };
  onNodeSelect: (nodeId: string | null) => void;
  onEdgeSelect: (edgeId: string | null) => void;
}

export function ArchitectureGraph({
  graphData,
  onNodeSelect,
  onEdgeSelect,
}: ArchitectureGraphProps) {
  const [nodes, setNodes, onNodesChange] = useNodesState(graphData.nodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(graphData.edges);

  // Aplicar layout al montar
  useEffect(() => {
    const { nodes: layouted } = layoutPipeline(graphData.nodes, graphData.edges);
    setNodes(layouted);
  }, [graphData]);

  return (
    <div className="w-full h-full">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        onNodeClick={(_, node) => onNodeSelect(node.id)}
        onEdgeClick={(_, edge) => onEdgeSelect(edge.id)}
        onPaneClick={() => {
          onNodeSelect(null);
          onEdgeSelect(null);
        }}
        fitView
      >
        <Background />
        <Controls />
        <MiniMap />
      </ReactFlow>
    </div>
  );
}
```

---

## Interacciones MVP

| Acción | Resultado |
|--------|-----------|
| Click en nodo | Selecciona, abre panel lateral |
| Click en arista | Selecciona, muestra call-site |
| Click en canvas | Deselecciona todo |
| Scroll | Zoom in/out |
| Drag en canvas | Pan |
| Drag en nodo | Mover nodo (temporal) |
| Botón "Fit View" | Ajustar vista a contenido |

---

## Estilos por Estado

### Contract Status

| Estado | Badge | Borde | Significado |
|--------|-------|-------|-------------|
| verified | ✅ | Verde | Contrato AEGIS con evidencia OK |
| inferred | 🤖 | Amarillo | Inferido, necesita revisión |
| missing | ❓ | Rojo | Sin contrato |
| failing | ❌ | Rojo parpadeante | Evidencia fallando |

### Role

| Rol | Color fondo | Icono |
|-----|-------------|-------|
| source | Verde claro | ▶️ |
| processing | Azul claro | ⚙️ |
| sink | Morado claro | 🎯 |

---

## API Endpoints

```yaml
GET /api/graph/{root_id}
  response:
    nodes: List[ReactFlowNode]
    edges: List[ReactFlowEdge]
    metadata:
      root_location: string
      last_analyzed: datetime

POST /api/graph/{root_id}/refresh
  description: Forzar re-análisis del composition root
  response:
    nodes: List[ReactFlowNode]
    edges: List[ReactFlowEdge]
```

---

## Checklist

```
[ ] Instalar dependencias: @xyflow/react, dagre
[ ] Crear ModuleInstanceNode component
[ ] Crear WiringEdge component
[ ] Implementar layout con dagre
[ ] Crear ArchitectureGraph component
[ ] Integrar con panel lateral (eventos de selección)
[ ] Implementar fit view / zoom / pan
[ ] Estilos por contract status
[ ] Estilos por role
[ ] API endpoint GET /api/graph/{root_id}
```

---

## DoD

- [ ] Se visualiza pipeline de Actia (3 nodos, 2 aristas)
- [ ] Click en nodo dispara evento con node_id
- [ ] Click en arista dispara evento con edge_id
- [ ] Layout automático izquierda→derecha
- [ ] Zoom y pan funcionan
- [ ] Fit view ajusta correctamente
