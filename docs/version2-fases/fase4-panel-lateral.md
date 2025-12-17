# Fase 4: Panel Lateral - Instancia vs Tipo

**Objetivo**: Mostrar información detallada del nodo seleccionado con navegación a código

---

## Diseño de UX

### Estructura del Panel

```
┌─────────────────────────────────────────────┐
│ [Instance] [Type]                    [×]    │  ← Tabs + Close
├─────────────────────────────────────────────┤
│                                             │
│  Contenido según tab activa                 │
│                                             │
└─────────────────────────────────────────────┘
```

---

## Tab: Instance

Muestra información del **wiring y configuración runtime**.

```
┌─────────────────────────────────────────────┐
│ m2                                          │
│ FilterModule                          🔗    │  ← Jump to creation
├─────────────────────────────────────────────┤
│ CREATION                                    │
│ ─────────                                   │
│ 📍 main.cpp:15                        🔗    │
│ Pattern: factory                            │
│                                             │
│ ARGUMENTS                                   │
│ ─────────                                   │
│ targetSequence: {0x00, 0x01, 0x02}          │
│                                             │
│ CONNECTIONS                                 │
│ ───────────                                 │
│ ← m1 (GeneratorModule)               🔗    │  ← Incoming
│ → m3 (PrinterModule)                 🔗    │  ← Outgoing
│                                             │
│ WIRING DETAILS                              │
│ ──────────────                              │
│ m1.setNext(m2)  @ main.cpp:18        🔗    │
│ m2.setNext(m3)  @ main.cpp:19        🔗    │
└─────────────────────────────────────────────┘
```

### Datos para Instance Tab

```typescript
interface InstanceTabData {
  name: string;
  typeName: string;
  role: InstanceRole;

  creation: {
    location: Location;
    pattern: 'factory' | 'direct' | 'make_unique' | 'other';
  };

  arguments: Record<string, string>;  // Nombre → valor (string repr)

  connections: {
    incoming: Array<{
      name: string;
      typeName: string;
      nodeId: string;
    }>;
    outgoing: Array<{
      name: string;
      typeName: string;
      nodeId: string;
    }>;
  };

  wiringDetails: Array<{
    expression: string;   // "m1.setNext(m2)"
    location: Location;
  }>;
}
```

---

## Tab: Type

Muestra información del **tipo (clase) y su contrato**.

```
┌─────────────────────────────────────────────┐
│ FilterModule                                │
│ IModule                               🔗    │  ← Jump to definition
├─────────────────────────────────────────────┤
│ LOCATION                                    │
│ ────────                                    │
│ 📍 FilterModule.h:12                  🔗    │
│                                             │
│ CONTRACT                         [Edit] ✅  │
│ ────────                                    │
│ Thread Safety: safe_after_start             │
│ Lifecycle: stopped → running → stopped      │
│                                             │
│ Invariants:                                 │
│  • pipeline must be started before process  │
│                                             │
│ Preconditions:                              │
│  • input != nullptr                         │
│                                             │
│ Errors:                                     │
│  • throws runtime_error if next not set     │
│                                             │
│ EVIDENCE                                    │
│ ────────                                    │
│ ✅ tests/filter_test.cpp::TestFilter        │
│ ✅ clang-tidy                               │
│                                             │
│ Confidence: 100% (AEGIS-owned)              │
│ Source: Level 1                             │
└─────────────────────────────────────────────┘
```

### Datos para Type Tab

```typescript
interface TypeTabData {
  typeName: string;
  baseTypes: string[];  // Interfaces/clases base
  location: Location;

  contract: ContractData | null;

  evidence: Array<{
    type: 'test' | 'lint' | 'typecheck';
    reference: string;
    status: 'pass' | 'fail' | 'not_run';
    lastRun?: string;
  }>;

  // Metadatos del contrato
  contractSource: {
    level: 1 | 2 | 3 | 4 | 5;
    confidence: number;
    needsReview: boolean;
  };
}
```

---

## Componentes React

### SidePanel

```tsx
// components/SidePanel.tsx

interface SidePanelProps {
  selectedNode: InstanceNode | null;
  onClose: () => void;
  onNavigateToCode: (location: Location) => void;
  onEditContract: (nodeId: string) => void;
}

export function SidePanel({
  selectedNode,
  onClose,
  onNavigateToCode,
  onEditContract,
}: SidePanelProps) {
  const [activeTab, setActiveTab] = useState<'instance' | 'type'>('instance');

  if (!selectedNode) return null;

  return (
    <div className="w-96 border-l bg-white h-full overflow-auto">
      {/* Header */}
      <div className="sticky top-0 bg-white border-b p-4">
        <div className="flex justify-between items-center">
          <h2 className="font-bold text-lg">{selectedNode.name}</h2>
          <button onClick={onClose}>×</button>
        </div>
        <div className="text-sm text-gray-500">{selectedNode.type_symbol}</div>

        {/* Tabs */}
        <div className="flex gap-2 mt-4">
          <TabButton
            active={activeTab === 'instance'}
            onClick={() => setActiveTab('instance')}
          >
            Instance
          </TabButton>
          <TabButton
            active={activeTab === 'type'}
            onClick={() => setActiveTab('type')}
          >
            Type
          </TabButton>
        </div>
      </div>

      {/* Content */}
      <div className="p-4">
        {activeTab === 'instance' ? (
          <InstanceTab
            node={selectedNode}
            onNavigate={onNavigateToCode}
          />
        ) : (
          <TypeTab
            node={selectedNode}
            onNavigate={onNavigateToCode}
            onEditContract={onEditContract}
          />
        )}
      </div>
    </div>
  );
}
```

### LocationLink

```tsx
// components/LocationLink.tsx

interface LocationLinkProps {
  location: Location;
  onNavigate: (loc: Location) => void;
}

export function LocationLink({ location, onNavigate }: LocationLinkProps) {
  return (
    <button
      className="text-blue-600 hover:underline flex items-center gap-1"
      onClick={() => onNavigate(location)}
    >
      <span>📍 {location.file}:{location.line}</span>
      <span>🔗</span>
    </button>
  );
}
```

### ContractDisplay

```tsx
// components/ContractDisplay.tsx

interface ContractDisplayProps {
  contract: ContractData;
  onEdit: () => void;
}

export function ContractDisplay({ contract, onEdit }: ContractDisplayProps) {
  const statusIcon = contract.confidence === 1.0 ? '✅' :
                     contract.confidence >= 0.8 ? '📋' :
                     contract.confidence >= 0.6 ? '🤖' : '⚡';

  return (
    <div className="space-y-4">
      <div className="flex justify-between items-center">
        <h3 className="font-semibold">CONTRACT</h3>
        <div className="flex items-center gap-2">
          <button
            className="text-sm text-blue-600 hover:underline"
            onClick={onEdit}
          >
            Edit
          </button>
          <span>{statusIcon}</span>
        </div>
      </div>

      {contract.thread_safety && (
        <div>
          <span className="text-gray-500">Thread Safety:</span>{' '}
          {contract.thread_safety}
        </div>
      )}

      {contract.lifecycle && (
        <div>
          <span className="text-gray-500">Lifecycle:</span>{' '}
          {contract.lifecycle}
        </div>
      )}

      {contract.invariants.length > 0 && (
        <div>
          <div className="text-gray-500">Invariants:</div>
          <ul className="list-disc list-inside">
            {contract.invariants.map((inv, i) => (
              <li key={i}>{inv}</li>
            ))}
          </ul>
        </div>
      )}

      {/* Similar para preconditions, postconditions, errors */}
    </div>
  );
}
```

---

## Navegación a Código

### Integración con Editor

```typescript
// utils/navigation.ts

export async function navigateToCode(location: Location): Promise<void> {
  // Opción 1: VS Code extension API
  if (window.vscode) {
    window.vscode.postMessage({
      type: 'openFile',
      file: location.file,
      line: location.line,
    });
    return;
  }

  // Opción 2: Backend abre en editor configurado
  await fetch('/api/editor/open', {
    method: 'POST',
    body: JSON.stringify(location),
  });
}
```

### API Backend

```yaml
POST /api/editor/open
  body:
    file: string
    line: number
    column?: number
  description: Abre archivo en editor del sistema
  implementation: Usa $EDITOR o código específico para VS Code/JetBrains
```

---

## API Endpoints

```yaml
GET /api/node/{node_id}/instance
  response:
    name: string
    typeName: string
    creation: CreationInfo
    arguments: Record<string, string>
    connections: ConnectionsInfo
    wiringDetails: WiringDetail[]

GET /api/node/{node_id}/type
  response:
    typeName: string
    baseTypes: string[]
    location: Location
    contract: ContractData | null
    evidence: EvidenceStatus[]
```

---

## Checklist

```
[ ] Crear SidePanel component
[ ] Crear InstanceTab component
[ ] Crear TypeTab component
[ ] Crear LocationLink component
[ ] Crear ContractDisplay component
[ ] Implementar navegación a código
[ ] API GET /api/node/{id}/instance
[ ] API GET /api/node/{id}/type
[ ] Integrar con ArchitectureGraph (selección)
[ ] Estilos responsive (panel colapsable en móvil)
```

---

## DoD

- [ ] Click en nodo → panel muestra datos de instancia
- [ ] Tab Type muestra contrato (si existe)
- [ ] Links 🔗 navegan al código (archivo:línea)
- [ ] Conexiones entrantes/salientes visibles
- [ ] Botón Edit abre editor de contrato (Fase 5)
- [ ] Evidence muestra estado pass/fail
