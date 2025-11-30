# Claude Agent JSON Streaming - Documentación Completa

**Fecha de implementación:** 2025-11-26
**Última actualización:** 2025-11-26
**Estado:** ✅ Fases 1-4 Completas
**Branch:** develop

---

## Índice

1. [Resumen del Problema](#resumen-del-problema)
2. [Solución Implementada](#solución-implementada)
3. [Arquitectura](#arquitectura)
4. [Archivos Implementados](#archivos-implementados)
5. [Protocolo WebSocket](#protocolo-websocket)
6. [Tipos de Eventos Claude](#tipos-de-eventos-claude)
7. [Guía de Testing](#guía-de-testing)
8. [Código de Referencia](#código-de-referencia)
9. [Fases Futuras](#fases-futuras)
10. [Troubleshooting](#troubleshooting)

---

## Resumen del Problema

### Síntomas
El terminal PTY existente para Claude Code tenía problemas graves:

1. **Raw line breaks:** Claude Code emitía caracteres de control y line breaks que el terminal PTY no manejaba bien, haciendo el output inlegible y el agente inmanejable desde shell.

2. **Send button buggy:** El botón Send enviaba comandos con line breaks extra, causando comportamiento inesperado.

3. **TUI incompatible:** Claude Code usa una TUI (Text User Interface) rica que no se renderiza bien en un emulador de terminal web básico.

### Causa Raíz
Claude Code está diseñado para terminales interactivos reales (iTerm, gnome-terminal, etc.), no para PTY emulados via web. Su output incluye:
- Secuencias de escape ANSI
- Spinners y progress bars
- Clearing de líneas y posicionamiento de cursor
- Colores y estilos

### Descubrimiento Clave
Claude Code tiene un modo `--print` (o `-p`) que:
- Desactiva la TUI interactiva
- Soporta `--output-format stream-json` para output estructurado
- Emite eventos JSON línea por línea (cada línea es un objeto JSON independiente)
- Perfecto para integración programática

---

## Solución Implementada

### Enfoque
En lugar de arreglar el terminal PTY, creamos una **nueva página `/agent`** que:

1. Usa `claude -p --output-format stream-json` para recibir JSON estructurado
2. Parsea eventos línea por línea
3. Renderiza una UI personalizada con:
   - Mensajes de texto formateados
   - Cards colapsables para tool calls
   - Resultados de herramientas
   - Input para nuevos prompts

### Comando Claude Code
```bash
claude -p --output-format stream-json --verbose "tu prompt aquí"

# Opciones:
# -p, --print         Modo no interactivo (sin TUI)
# --output-format     Formato de salida: stream-json, json, text
# --verbose           Incluir más detalles en eventos
# --continue          Continuar sesión anterior
```

### Ventajas
- ✅ Output estructurado y predecible
- ✅ Sin problemas de line breaks o escape sequences
- ✅ UI personalizable y rica
- ✅ Fácil de extender con más features
- ✅ Terminal shell existente permanece intacto

---

## Arquitectura

### Diagrama de Flujo

```
┌─────────────────────────────────────────────────────────────────────┐
│                         FRONTEND (React)                             │
│                                                                      │
│  ┌────────────────────┐      ┌─────────────────────────────────┐   │
│  │  ClaudeAgentView   │      │  claudeSessionStore (Zustand)   │   │
│  │                    │◄────►│                                  │   │
│  │  - Header          │      │  Estado:                        │   │
│  │  - MessagesList    │      │  - connected: boolean           │   │
│  │  - ToolCards       │      │  - running: boolean             │   │
│  │  - InputArea       │      │  - messages: ClaudeMessage[]    │   │
│  │                    │      │  - activeToolCalls: Map         │   │
│  └────────────────────┘      │  - sessionId: string | null     │   │
│                              │                                  │   │
│                              │  Acciones:                       │   │
│                              │  - connect(wsUrl)                │   │
│                              │  - disconnect()                  │   │
│                              │  - sendPrompt(prompt)            │   │
│                              │  - processEvent(event)           │   │
│                              └─────────────────────────────────┘   │
│                                           │                         │
└───────────────────────────────────────────┼─────────────────────────┘
                                            │
                                            │ WebSocket
                                            │ ws://localhost:8010/api/terminal/ws/agent
                                            │
┌───────────────────────────────────────────┼─────────────────────────┐
│                         BACKEND (FastAPI) │                          │
│                                           ▼                          │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  /api/terminal/ws/agent (WebSocket Endpoint)                 │   │
│  │                                                              │   │
│  │  1. Acepta conexión WebSocket                                │   │
│  │  2. Espera mensaje: {"command": "run", "prompt": "..."}      │   │
│  │  3. Crea ClaudeAgentRunner con config                        │   │
│  │  4. Ejecuta runner.run_prompt() con callback                 │   │
│  │  5. Callback envía cada evento parseado al frontend          │   │
│  │  6. Envía {"type": "done"} al finalizar                      │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              │                                      │
│              ┌───────────────┴───────────────┐                     │
│              ▼                               ▼                      │
│  ┌─────────────────────┐      ┌─────────────────────────────┐     │
│  │  ClaudeAgentRunner  │      │  JSONStreamParser           │     │
│  │                     │      │                             │     │
│  │  - config           │      │  - parse_line(line)         │     │
│  │  - process          │─────►│  - _parse_system()          │     │
│  │  - running          │      │  - _parse_assistant()       │     │
│  │                     │      │  - _parse_user()            │     │
│  │  Métodos:           │      │  - _parse_result()          │     │
│  │  - run_prompt()     │      │                             │     │
│  │  - cancel()         │      │  Retorna: ClaudeEvent       │     │
│  └─────────────────────┘      └─────────────────────────────┘     │
│              │                                                      │
└──────────────┼──────────────────────────────────────────────────────┘
               │
               │ subprocess (async)
               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         CLAUDE CODE CLI                              │
│                                                                      │
│  Comando ejecutado:                                                  │
│  claude -p --output-format stream-json --verbose "prompt"           │
│                                                                      │
│  Output (stdout, línea por línea):                                  │
│  {"type":"system","subtype":"init","session_id":"abc123",...}       │
│  {"type":"assistant","subtype":"text","content":"Respuesta..."}     │
│  {"type":"assistant","subtype":"tool_use","tool_name":"Read",...}   │
│  {"type":"user","subtype":"tool_result","content":"..."}            │
│  {"type":"result","subtype":"success","duration_ms":1234,...}       │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Flujo de Datos

```
1. Usuario escribe prompt en UI
   │
   ▼
2. claudeSessionStore.sendPrompt(prompt)
   │
   ├─► Actualiza estado: running = true
   │
   └─► WebSocket.send({"command": "run", "prompt": "..."})
       │
       ▼
3. Backend recibe mensaje en /ws/agent
   │
   ▼
4. ClaudeAgentRunner.run_prompt(prompt, on_event_callback)
   │
   ├─► Construye comando: ["claude", "-p", "--output-format", "stream-json", ...]
   │
   └─► asyncio.create_subprocess_exec(...)
       │
       ▼
5. Lee stdout línea por línea (async)
   │
   ├─► JSONStreamParser.parse_line(line)
   │   │
   │   └─► Retorna ClaudeEvent tipado
   │
   └─► on_event_callback(event)
       │
       └─► WebSocket.send(json.dumps(event))
           │
           ▼
6. Frontend recibe evento
   │
   └─► claudeSessionStore.processEvent(event)
       │
       ├─► Si type="system" subtype="init": guarda sessionId
       ├─► Si type="assistant" subtype="text": añade mensaje
       ├─► Si type="assistant" subtype="tool_use": añade tool call
       ├─► Si type="user" subtype="tool_result": completa tool call
       └─► Si type="result": marca como completado, running = false
           │
           ▼
7. React re-renderiza ClaudeAgentView con nuevos datos
```

---

## Archivos Implementados

### Backend (Python)

#### `code_map/terminal/claude_runner.py` (NUEVO)

```python
"""
Async subprocess runner para Claude Code JSON streaming.
Ejecuta claude -p --output-format stream-json y procesa output.
"""

@dataclass
class ClaudeRunnerConfig:
    working_dir: str = "."
    verbose: bool = True
    continue_session: bool = False
    timeout: float = 300.0  # 5 minutos default

class ClaudeAgentRunner:
    def __init__(self, config: ClaudeRunnerConfig):
        self.config = config
        self.process: Optional[asyncio.subprocess.Process] = None
        self.running = False
        self._cancelled = False

    async def run_prompt(
        self,
        prompt: str,
        on_event: Callable[[dict], Any],
        on_error: Optional[Callable[[str], Any]] = None,
        on_complete: Optional[Callable[[], Any]] = None
    ) -> None:
        """
        Ejecuta un prompt y llama callbacks para cada evento.

        Args:
            prompt: El prompt a enviar a Claude
            on_event: Callback llamado para cada evento parseado
            on_error: Callback para errores
            on_complete: Callback cuando termina
        """
        # ... implementación

    async def cancel(self) -> None:
        """Cancela el proceso actual si está corriendo."""
        # ... implementación
```

**Funcionalidad:**
- Construye comando con flags apropiados
- Ejecuta subprocess asíncrono
- Lee stdout línea por línea
- Parsea JSON y llama callbacks
- Maneja timeout y cancelación
- Limpieza de proceso al finalizar

---

#### `code_map/terminal/json_parser.py` (NUEVO)

```python
"""
Parser de eventos JSON de Claude Code.
Cada línea de output es un objeto JSON independiente.
"""

class EventType(str, Enum):
    SYSTEM = "system"
    ASSISTANT = "assistant"
    USER = "user"
    RESULT = "result"
    UNKNOWN = "unknown"

class EventSubtype(str, Enum):
    INIT = "init"
    TEXT = "text"
    TOOL_USE = "tool_use"
    TOOL_RESULT = "tool_result"
    SUCCESS = "success"
    ERROR = "error"
    UNKNOWN = "unknown"

@dataclass
class ClaudeEvent:
    type: EventType
    subtype: EventSubtype
    data: Dict[str, Any]
    raw: Dict[str, Any]
    timestamp: str

class JSONStreamParser:
    def parse_line(self, line: str) -> Optional[ClaudeEvent]:
        """Parsea una línea de JSON y retorna un ClaudeEvent tipado."""
        # ... implementación

    def _parse_system(self, data: dict) -> ClaudeEvent: ...
    def _parse_assistant(self, data: dict) -> ClaudeEvent: ...
    def _parse_user(self, data: dict) -> ClaudeEvent: ...
    def _parse_result(self, data: dict) -> ClaudeEvent: ...
```

**Funcionalidad:**
- Parsea JSON línea por línea
- Clasifica eventos por tipo y subtipo
- Extrae datos relevantes según tipo
- Maneja errores de parsing gracefully
- Añade timestamps a eventos

---

#### `code_map/api/terminal.py` (MODIFICADO)

```python
# Añadido nuevo endpoint WebSocket

@router.websocket("/ws/agent")
async def agent_websocket(websocket: WebSocket):
    """
    WebSocket endpoint para Claude Agent JSON streaming.

    Protocolo:
    - Cliente envía: {"command": "run", "prompt": "...", "continue": bool}
    - Servidor envía: eventos JSON de Claude uno por uno
    - Servidor envía: {"type": "done"} al finalizar
    """
    await websocket.accept()

    try:
        while True:
            # Esperar comando del cliente
            message = await websocket.receive_json()

            if message.get("command") == "run":
                prompt = message.get("prompt", "")
                continue_session = message.get("continue", False)

                # Configurar runner
                config = ClaudeRunnerConfig(
                    working_dir=str(state.project_root or "."),
                    verbose=True,
                    continue_session=continue_session
                )
                runner = ClaudeAgentRunner(config)

                # Callback para enviar eventos
                async def send_event(event: dict):
                    await websocket.send_json(event)

                # Ejecutar prompt
                await runner.run_prompt(
                    prompt=prompt,
                    on_event=send_event,
                    on_error=lambda e: websocket.send_json({"type": "error", "message": e}),
                    on_complete=lambda: None
                )

                # Marcar fin
                await websocket.send_json({"type": "done"})

    except WebSocketDisconnect:
        pass
```

---

#### `code_map/terminal/__init__.py` (MODIFICADO)

```python
# Añadidos exports para nuevos módulos
from .claude_runner import ClaudeAgentRunner, ClaudeRunnerConfig
from .json_parser import JSONStreamParser, ClaudeEvent, EventType, EventSubtype
```

---

### Frontend (TypeScript/React)

#### `frontend/src/types/claude-events.ts` (NUEVO)

```typescript
/**
 * Tipos TypeScript para eventos de Claude Code JSON streaming.
 */

// Tipos de eventos
export type ClaudeEventType = 'system' | 'assistant' | 'user' | 'result' | 'done' | 'error';
export type ClaudeEventSubtype = 'init' | 'text' | 'tool_use' | 'tool_result' | 'success' | 'error';

// Evento base
export interface ClaudeEvent {
  type: ClaudeEventType;
  subtype?: ClaudeEventSubtype;
  [key: string]: unknown;
}

// Eventos específicos
export interface SystemInitEvent extends ClaudeEvent {
  type: 'system';
  subtype: 'init';
  session_id: string;
  model: string;
  cwd?: string;
  tools?: string[];
}

export interface AssistantTextEvent extends ClaudeEvent {
  type: 'assistant';
  subtype: 'text';
  content: string;
}

export interface AssistantToolUseEvent extends ClaudeEvent {
  type: 'assistant';
  subtype: 'tool_use';
  tool_use_id: string;
  tool_name: string;
  tool_input: Record<string, unknown>;
}

export interface UserToolResultEvent extends ClaudeEvent {
  type: 'user';
  subtype: 'tool_result';
  tool_use_id: string;
  content: string;
  is_error?: boolean;
}

export interface ResultEvent extends ClaudeEvent {
  type: 'result';
  subtype: 'success' | 'error';
  duration_ms?: number;
  cost_usd?: number;
  tokens_input?: number;
  tokens_output?: number;
}

// Type guards
export function isSystemInitEvent(event: ClaudeEvent): event is SystemInitEvent { ... }
export function isTextEvent(event: ClaudeEvent): event is AssistantTextEvent { ... }
export function isToolUseEvent(event: ClaudeEvent): event is AssistantToolUseEvent { ... }
export function isToolResultEvent(event: ClaudeEvent): event is UserToolResultEvent { ... }
export function isResultEvent(event: ClaudeEvent): event is ResultEvent { ... }

// Helpers
export function getToolIcon(toolName: string): string { ... }
export function formatToolInput(input: Record<string, unknown>): string { ... }
export function generateMessageId(): string { ... }

// Tipos para UI
export interface ClaudeMessage {
  id: string;
  type: 'text' | 'tool_use' | 'tool_result' | 'system' | 'error';
  content: string;
  timestamp: Date;
  toolName?: string;
  toolInput?: Record<string, unknown>;
  toolUseId?: string;
  isError?: boolean;
}

export interface ToolCall {
  id: string;
  toolName: string;
  toolInput: Record<string, unknown>;
  status: 'pending' | 'running' | 'completed' | 'error';
  result?: string;
  startTime: Date;
  endTime?: Date;
}
```

---

#### `frontend/src/stores/claudeSessionStore.ts` (NUEVO)

```typescript
/**
 * Zustand store para gestión de sesión de Claude Agent.
 */

interface ClaudeSessionState {
  // Estado de conexión
  connected: boolean;
  connecting: boolean;
  error: string | null;

  // Estado de sesión
  sessionId: string | null;
  model: string | null;
  running: boolean;

  // Mensajes y herramientas
  messages: ClaudeMessage[];
  activeToolCalls: Map<string, ToolCall>;

  // WebSocket
  ws: WebSocket | null;
}

interface ClaudeSessionActions {
  // Conexión
  connect: (wsUrl: string) => void;
  disconnect: () => void;

  // Comandos
  sendPrompt: (prompt: string, continueSession?: boolean) => void;

  // Procesamiento de eventos
  processEvent: (event: ClaudeEvent) => void;

  // Utilidades
  clearMessages: () => void;
  getLastToolCall: () => ToolCall | undefined;
}

export const useClaudeSessionStore = create<ClaudeSessionState & ClaudeSessionActions>(
  (set, get) => ({
    // Estado inicial
    connected: false,
    connecting: false,
    error: null,
    sessionId: null,
    model: null,
    running: false,
    messages: [],
    activeToolCalls: new Map(),
    ws: null,

    // Implementación de acciones...
    connect: (wsUrl) => { ... },
    disconnect: () => { ... },
    sendPrompt: (prompt, continueSession = false) => { ... },
    processEvent: (event) => {
      // Procesa cada tipo de evento y actualiza estado
      if (isSystemInitEvent(event)) {
        set({ sessionId: event.session_id, model: event.model });
      } else if (isTextEvent(event)) {
        // Añade mensaje de texto
      } else if (isToolUseEvent(event)) {
        // Añade tool call activo
      } else if (isToolResultEvent(event)) {
        // Completa tool call
      } else if (isResultEvent(event)) {
        set({ running: false });
      }
    },
    clearMessages: () => { ... },
    getLastToolCall: () => { ... },
  })
);
```

---

#### `frontend/src/components/ClaudeAgentView.tsx` (NUEVO)

```tsx
/**
 * Componente principal para interacción con Claude Agent.
 * Renderiza mensajes, tool cards, y área de input.
 */

export function ClaudeAgentView() {
  const {
    connected,
    connecting,
    running,
    messages,
    activeToolCalls,
    sessionId,
    model,
    connect,
    disconnect,
    sendPrompt,
    clearMessages,
  } = useClaudeSessionStore();

  const [input, setInput] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const { wsBaseUrl } = useSettingsStore();

  // Auto-connect al montar
  useEffect(() => {
    const wsUrl = `${wsBaseUrl.replace('http', 'ws')}/api/terminal/ws/agent`;
    connect(wsUrl);
    return () => disconnect();
  }, [wsBaseUrl]);

  // Auto-scroll a nuevos mensajes
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = () => {
    if (input.trim() && !running) {
      sendPrompt(input.trim());
      setInput('');
    }
  };

  return (
    <div className="claude-agent-view">
      {/* Header con estado de conexión */}
      <Header connected={connected} sessionId={sessionId} model={model} />

      {/* Lista de mensajes */}
      <MessagesList messages={messages} activeToolCalls={activeToolCalls} />

      {/* Área de input */}
      <InputArea
        input={input}
        setInput={setInput}
        onSend={handleSend}
        running={running}
        connected={connected}
      />
    </div>
  );
}

// Subcomponentes para mensajes de texto, tool cards, etc.
function TextMessage({ message }: { message: ClaudeMessage }) { ... }
function ToolUseCard({ toolCall }: { toolCall: ToolCall }) { ... }
function ToolResultCard({ message }: { message: ClaudeMessage }) { ... }
```

**Características UI:**
- Header con estado de conexión (●/○), session ID, modelo
- Lista scrolleable de mensajes con auto-scroll
- Mensajes de texto con formato
- Tool cards colapsables con icono, nombre, input JSON
- Results de tools con estado (éxito/error)
- Input area con textarea y botón Send
- Keyboard shortcut: Ctrl+Enter para enviar
- Estados de loading y disabled apropiados

---

#### `frontend/src/App.tsx` (MODIFICADO)

```tsx
// Añadido import
import { ClaudeAgentView } from "./components/ClaudeAgentView";

// Añadida ruta
<Route
  path="/agent"
  element={withLayout("Claude Agent", <ClaudeAgentView />)}
/>
```

---

#### `frontend/src/components/HomeView.tsx` (MODIFICADO)

```tsx
// Añadida card de navegación
<Link to="/agent" className="home-card">
  <div className="home-card-body">
    <h3>Claude Agent</h3>
    <p>Interact with Claude Code through a structured UI with JSON streaming for reliable output.</p>
  </div>
  <span className="home-card-cta">Open Agent →</span>
</Link>
```

---

## Protocolo WebSocket

### Endpoint
```
ws://localhost:8010/api/terminal/ws/agent
```

### Mensajes Cliente → Servidor

#### Run Prompt
```json
{
  "command": "run",
  "prompt": "What files are in this directory?",
  "continue": false
}
```

| Campo | Tipo | Requerido | Descripción |
|-------|------|-----------|-------------|
| command | string | ✅ | Siempre "run" |
| prompt | string | ✅ | El prompt a enviar a Claude |
| continue | boolean | ❌ | Si true, continúa sesión anterior |

### Mensajes Servidor → Cliente

El servidor envía eventos JSON uno por uno. Cada mensaje es un objeto JSON independiente.

#### System Init
```json
{
  "type": "system",
  "subtype": "init",
  "session_id": "abc123-def456",
  "model": "claude-sonnet-4-20250514",
  "cwd": "/home/user/project",
  "tools": ["Read", "Write", "Edit", "Bash", "Glob", "Grep"]
}
```

#### Assistant Text
```json
{
  "type": "assistant",
  "subtype": "text",
  "content": "I'll help you list the files in this directory."
}
```

#### Assistant Tool Use
```json
{
  "type": "assistant",
  "subtype": "tool_use",
  "tool_use_id": "tool_123",
  "tool_name": "Bash",
  "tool_input": {
    "command": "ls -la",
    "description": "List files in current directory"
  }
}
```

#### User Tool Result
```json
{
  "type": "user",
  "subtype": "tool_result",
  "tool_use_id": "tool_123",
  "content": "total 48\ndrwxr-xr-x  5 user user 4096 Nov 26 10:00 .\n...",
  "is_error": false
}
```

#### Result (Success)
```json
{
  "type": "result",
  "subtype": "success",
  "duration_ms": 2345,
  "cost_usd": 0.0023,
  "tokens_input": 150,
  "tokens_output": 89
}
```

#### Result (Error)
```json
{
  "type": "result",
  "subtype": "error",
  "error": "Process timed out after 300 seconds"
}
```

#### Done (Fin de stream)
```json
{
  "type": "done"
}
```

#### Error (Error de sistema)
```json
{
  "type": "error",
  "message": "WebSocket connection lost"
}
```

---

## Tipos de Eventos Claude

### Tabla de Referencia Rápida

| Tipo | Subtipo | Descripción | Datos Clave |
|------|---------|-------------|-------------|
| `system` | `init` | Inicio de sesión | session_id, model, cwd, tools |
| `assistant` | `text` | Respuesta de texto | content |
| `assistant` | `tool_use` | Llamada a herramienta | tool_use_id, tool_name, tool_input |
| `user` | `tool_result` | Resultado de herramienta | tool_use_id, content, is_error |
| `result` | `success` | Fin exitoso | duration_ms, cost_usd, tokens |
| `result` | `error` | Fin con error | error message |
| `done` | - | Fin del stream | - |
| `error` | - | Error de sistema | message |

### Herramientas Comunes

| Tool Name | Descripción | Input Keys |
|-----------|-------------|------------|
| `Read` | Leer archivo | file_path, offset, limit |
| `Write` | Escribir archivo | file_path, content |
| `Edit` | Editar archivo | file_path, old_string, new_string |
| `Bash` | Ejecutar comando | command, description, timeout |
| `Glob` | Buscar archivos | pattern, path |
| `Grep` | Buscar en contenido | pattern, path, include |
| `Task` | Delegar a subagente | description, prompt |
| `TodoWrite` | Actualizar todos | todos (array) |

---

## Guía de Testing

### 1. Test Backend Solo (sin frontend)

```bash
# Terminal 1: Iniciar backend
cd /home/jesusramos/Workspace/ATLAS
python -m code_map.cli run --root .

# Terminal 2: Test con Python
python3 -c "
import asyncio
import websockets
import json

async def test():
    uri = 'ws://localhost:8010/api/terminal/ws/agent'
    async with websockets.connect(uri) as ws:
        print('Connected!')

        # Enviar prompt
        await ws.send(json.dumps({
            'command': 'run',
            'prompt': 'What is 2+2? Answer briefly.'
        }))
        print('Sent prompt, waiting for events...')

        # Recibir eventos
        while True:
            msg = await ws.recv()
            data = json.loads(msg)
            print(f'Event: {data.get(\"type\")} / {data.get(\"subtype\", \"-\")}')
            print(json.dumps(data, indent=2))
            print('---')

            if data.get('type') == 'done':
                print('Stream complete!')
                break

asyncio.run(test())
"
```

**Output esperado:**
```
Connected!
Sent prompt, waiting for events...
Event: system / init
{
  "type": "system",
  "subtype": "init",
  "session_id": "...",
  "model": "claude-sonnet-4-20250514"
}
---
Event: assistant / text
{
  "type": "assistant",
  "subtype": "text",
  "content": "Four."
}
---
Event: result / success
{
  "type": "result",
  "subtype": "success",
  "duration_ms": 1234
}
---
Event: done / -
{
  "type": "done"
}
---
Stream complete!
```

### 2. Test Frontend Completo

```bash
# Terminal 1: Backend
cd /home/jesusramos/Workspace/ATLAS
python -m code_map.cli run --root .

# Terminal 2: Frontend
cd /home/jesusramos/Workspace/ATLAS/frontend
npm run dev

# Terminal 3 (opcional): Logs
tail -f ~/.claude/logs/*.log
```

**Pasos de prueba:**
1. Abrir `http://localhost:5173/agent`
2. Verificar indicador de conexión (● verde)
3. Escribir prompt simple: "What is 2+2?"
4. Click Send o Ctrl+Enter
5. Verificar que aparece respuesta
6. Probar prompt con tool: "List files in current directory"
7. Verificar que aparece tool card con resultado

### 3. Test de Tool Cards

Prompts que disparan diferentes tools:

```
# Read file
"Read the first 10 lines of package.json"

# Bash command
"Run ls -la in the current directory"

# Grep search
"Search for 'TODO' in all Python files"

# Multi-step
"Find all test files and count how many tests exist"
```

### 4. Test de Errores

```bash
# Test con prompt que causa error
python3 -c "
import asyncio, websockets, json

async def test():
    async with websockets.connect('ws://localhost:8010/api/terminal/ws/agent') as ws:
        await ws.send(json.dumps({
            'command': 'run',
            'prompt': ''  # Prompt vacío
        }))
        while True:
            msg = await ws.recv()
            data = json.loads(msg)
            print(json.dumps(data, indent=2))
            if data.get('type') in ['done', 'error']:
                break

asyncio.run(test())
"
```

---

## Código de Referencia

### Ejemplo: Procesar eventos en frontend

```typescript
function processEvent(event: ClaudeEvent) {
  if (isSystemInitEvent(event)) {
    console.log(`Session started: ${event.session_id}`);
    console.log(`Model: ${event.model}`);
  }
  else if (isTextEvent(event)) {
    console.log(`Claude says: ${event.content}`);
    addMessage({
      id: generateMessageId(),
      type: 'text',
      content: event.content,
      timestamp: new Date()
    });
  }
  else if (isToolUseEvent(event)) {
    console.log(`Using tool: ${event.tool_name}`);
    addToolCall({
      id: event.tool_use_id,
      toolName: event.tool_name,
      toolInput: event.tool_input,
      status: 'running',
      startTime: new Date()
    });
  }
  else if (isToolResultEvent(event)) {
    console.log(`Tool result: ${event.content.slice(0, 100)}...`);
    completeToolCall(event.tool_use_id, event.content, event.is_error);
  }
  else if (isResultEvent(event)) {
    console.log(`Completed in ${event.duration_ms}ms`);
    setRunning(false);
  }
}
```

### Ejemplo: Ejecutar Claude desde Python

```python
import asyncio
from code_map.terminal import ClaudeAgentRunner, ClaudeRunnerConfig

async def main():
    config = ClaudeRunnerConfig(
        working_dir="/path/to/project",
        verbose=True,
        continue_session=False,
        timeout=300.0
    )

    runner = ClaudeAgentRunner(config)

    def on_event(event: dict):
        print(f"Event: {event.get('type')} / {event.get('subtype')}")
        if event.get('type') == 'assistant' and event.get('subtype') == 'text':
            print(f"  Content: {event.get('content')}")

    def on_error(error: str):
        print(f"Error: {error}")

    def on_complete():
        print("Done!")

    await runner.run_prompt(
        prompt="What is 2+2?",
        on_event=on_event,
        on_error=on_error,
        on_complete=on_complete
    )

asyncio.run(main())
```

---

## Progreso de Fases

### Fase 2: UI Mejorada ✅ COMPLETADA
- [x] Markdown rendering para respuestas (react-markdown + remark-gfm)
- [x] Syntax highlighting para código (prism-react-renderer con tema Night Owl)
- [x] Botones de copiar para bloques de código con feedback visual
- [x] Números de línea en bloques de código
- [x] Soporte GFM: tablas, task lists, strikethrough

**Archivos creados:**
- `frontend/src/components/MarkdownRenderer.tsx` - Componente de rendering markdown

### Fase 3: Gestión de Sesión ✅ COMPLETADA
- [x] Implementar flag `--continue` para continuidad de sesión (toggle en header)
- [x] Sidebar con historial de sesiones (colapsable)
- [x] Opción de limpiar/resetear sesión
- [x] Persistencia de sesiones en localStorage (máx 50 sesiones)
- [x] Auto-save debounced cuando los mensajes cambian
- [x] Cargar sesiones anteriores desde sidebar

**Archivos creados:**
- `frontend/src/stores/sessionHistoryStore.ts` - Store Zustand con persist middleware
- `frontend/src/components/SessionHistorySidebar.tsx` - Componente sidebar

### Fase 4: Features Avanzados ✅ COMPLETADA
- [x] Botón cancelar (kill subprocess) - funciona con Esc
- [x] Display de costo/tokens desde result events (header)
- [x] Atajos de teclado:
  - `Esc` - Cancelar operación en curso
  - `Ctrl+L` - Limpiar mensajes
  - `Ctrl+Shift+N` - Nueva sesión
  - `/` - Enfocar input (cuando no está en textarea)
- [x] Barra de progreso animada durante "thinking"
- [x] Badge visual para tools activos
- [x] Hint "Press Esc to cancel" durante ejecución
- [x] Token usage display con estimación de costo (Sonnet pricing: $3/M in, $15/M out)

**Archivos modificados:**
- `frontend/src/stores/claudeSessionStore.ts` - Añadido tracking de tokens
- `frontend/src/components/ClaudeAgentView.tsx` - UI mejorada, shortcuts, token display

### Fase 5: Polish (PENDIENTE)
- [ ] UI de manejo de errores mejorada
- [ ] Lógica de reconexión automática
- [ ] Diseño responsive para móvil
- [ ] Accesibilidad (ARIA labels, keyboard nav)
- [ ] Theming (dark/light mode)

---

## Troubleshooting

### Problema: WebSocket no conecta

**Síntomas:** Indicador de conexión rojo, error en consola

**Soluciones:**
1. Verificar que backend está corriendo en puerto 8010
2. Verificar URL: debe ser `ws://localhost:8010/api/terminal/ws/agent`
3. Revisar logs del backend para errores
4. Verificar que no hay firewall bloqueando

```bash
# Verificar backend
curl http://localhost:8010/api/health

# Verificar WebSocket con wscat
npx wscat -c ws://localhost:8010/api/terminal/ws/agent
```

### Problema: Claude no responde

**Síntomas:** Se envía prompt pero no hay respuesta

**Soluciones:**
1. Verificar que `claude` CLI está instalado y en PATH
2. Verificar autenticación de Claude Code
3. Revisar logs de Claude: `~/.claude/logs/`

```bash
# Verificar CLI
which claude
claude --version

# Test directo
claude -p --output-format stream-json "Hello"
```

### Problema: JSON parse error

**Síntomas:** Errores de parsing en logs

**Soluciones:**
1. Claude puede emitir líneas no-JSON (warnings, etc.)
2. El parser ignora líneas que no son JSON válido
3. Revisar output raw de Claude para debugging

```bash
# Ver output raw
claude -p --output-format stream-json "test" 2>&1 | cat -A
```

### Problema: Tool cards no se muestran

**Síntomas:** Solo aparecen mensajes de texto, no tool calls

**Soluciones:**
1. Verificar que `--verbose` está habilitado en runner
2. Algunos prompts simples no usan tools
3. Probar prompt que requiera tool: "List files in this directory"

### Problema: Frontend no compila

**Síntomas:** Errores de TypeScript

**Soluciones:**
```bash
# Verificar tipos
cd frontend
npm run typecheck

# Limpiar y reinstalar
rm -rf node_modules
npm install
npm run build
```

---

## Comandos Útiles

```bash
# Backend
python -m code_map.cli run --root /path/to/project  # Iniciar
python -m code_map.cli --help                        # Ayuda

# Frontend
cd frontend
npm run dev         # Desarrollo
npm run build       # Producción
npm run typecheck   # Verificar tipos
npm run lint        # Lint

# Claude Code
claude -p "prompt"                                    # Modo print
claude -p --output-format stream-json "prompt"       # JSON streaming
claude -p --output-format stream-json --verbose "prompt"  # Con detalles
claude -p --continue "prompt"                        # Continuar sesión

# Testing
pytest tests/                                        # Tests Python
npm test                                             # Tests frontend (si existen)

# Logs
tail -f ~/.claude/logs/*.log                         # Logs de Claude
```

---

## Referencias

- [Claude Code CLI Documentation](https://docs.anthropic.com/claude-code)
- [FastAPI WebSockets](https://fastapi.tiangolo.com/advanced/websockets/)
- [Zustand Documentation](https://docs.pmnd.rs/zustand)
- [React TypeScript Cheatsheet](https://react-typescript-cheatsheet.netlify.app/)

---

## Resumen de Archivos (Actualizado)

### Frontend - Nuevos
| Archivo | Descripción |
|---------|-------------|
| `src/components/MarkdownRenderer.tsx` | Rendering markdown con syntax highlighting |
| `src/components/SessionHistorySidebar.tsx` | Sidebar historial de sesiones |
| `src/stores/sessionHistoryStore.ts` | Store persistencia sesiones |

### Frontend - Modificados
| Archivo | Cambios |
|---------|---------|
| `src/components/ClaudeAgentView.tsx` | Sidebar, shortcuts, token display, progress bar |
| `src/components/HeaderBar.tsx` | Añadido link a `/agent` |
| `src/stores/claudeSessionStore.ts` | Token tracking (input/output) |

---

*Documentación generada: 2025-11-26*
*Última actualización: 2025-11-26*
*Versión: 1.4*
