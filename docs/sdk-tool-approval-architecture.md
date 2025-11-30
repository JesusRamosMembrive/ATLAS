# SDK Tool Approval Architecture

## Resumen Ejecutivo

Este documento describe la arquitectura del nuevo sistema de aprobación de herramientas basado en el **SDK de Anthropic Python**, que reemplaza el enfoque anterior basado en el CLI de Claude Code para el modo de "Review & Approve".

### Problema Original

El modo `toolApproval` original usaba el CLI de Claude Code con `--permission-mode plan`, pero tenía un problema fundamental:

> **Claude en modo `plan` frecuentemente describe las acciones que haría en lugar de emitir eventos `tool_use` reales.**

Esto causaba que el modal de aprobación nunca apareciera porque no había eventos `tool_use` que interceptar.

### Solución

Usar el **SDK de Anthropic Python directamente** en lugar del CLI. El SDK nos da control total sobre el flujo de ejecución de herramientas:

1. Claude emite `tool_use` con `stop_reason: "tool_use"`
2. Nosotros decidimos si ejecutar o no
3. Enviamos `tool_result` de vuelta a Claude
4. Claude continúa o termina

---

## Arquitectura del Sistema

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           FRONTEND (React)                               │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────────┐  │
│  │ ClaudeAgentView │───▶│ claudeSessionStore │───▶│ ToolApprovalModal │  │
│  └────────┬────────┘    └────────┬────────┘    └─────────┬───────────┘  │
│           │                      │                       │               │
│           │ WebSocket            │ state                 │ approve/reject│
│           ▼                      ▼                       ▼               │
└───────────┼──────────────────────┼───────────────────────┼───────────────┘
            │                      │                       │
            │ JSON events          │                       │ tool_approval_response
            ▼                      │                       ▼
┌───────────┴──────────────────────┴───────────────────────┴───────────────┐
│                           BACKEND (FastAPI)                               │
│  ┌─────────────────────────────────────────────────────────────────────┐ │
│  │                    /api/terminal/ws/agent                           │ │
│  │  ┌─────────────────────────────────────────────────────────────┐   │ │
│  │  │                    permission_mode == "sdk"                  │   │ │
│  │  │  ┌─────────────────┐    ┌─────────────────────────────────┐ │   │ │
│  │  │  │ SDKAgentRunner  │───▶│ ToolApprovalManager             │ │   │ │
│  │  │  │                 │    │ (genera diffs/previews)         │ │   │ │
│  │  │  └────────┬────────┘    └─────────────────────────────────┘ │   │ │
│  │  └───────────┼─────────────────────────────────────────────────┘   │ │
│  └──────────────┼─────────────────────────────────────────────────────┘ │
│                 │                                                        │
│                 │ API calls                                              │
│                 ▼                                                        │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │                    Anthropic API                                  │   │
│  │  messages.create(model, tools, messages) → Message               │   │
│  │                                                                   │   │
│  │  stop_reason: "tool_use" | "end_turn"                            │   │
│  └──────────────────────────────────────────────────────────────────┘   │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## Componentes Principales

### 1. SDKAgentRunner (`code_map/terminal/sdk_runner.py`)

Runner principal que usa el SDK de Anthropic directamente.

```python
class SDKAgentRunner:
    """
    Claude Agent using Anthropic SDK with tool approval workflow.
    """

    # Herramientas seguras (solo lectura) - auto-aprobar
    SAFE_TOOLS = {"Read", "Glob", "Grep"}

    # Herramientas que requieren aprobación (modifican estado)
    APPROVAL_REQUIRED_TOOLS = {"Write", "Edit", "Bash"}
```

#### Configuración

```python
@dataclass
class SDKRunnerConfig:
    cwd: str                          # Directorio de trabajo
    model: str = "claude-sonnet-4-20250514"  # Modelo a usar
    max_tokens: int = 8192            # Máximo tokens por respuesta
    system_prompt: str | None = None  # Prompt del sistema adicional
    api_key: str | None = None        # API key (usa env var si None)
    auto_approve_read: bool = True    # Auto-aprobar herramientas de lectura
```

#### Herramientas Disponibles

```python
CLAUDE_TOOLS = [
    {
        "name": "Read",
        "description": "Read a file from the filesystem...",
        "input_schema": { ... }
    },
    {
        "name": "Write",
        "description": "Write content to a file...",
        "input_schema": { ... }
    },
    {
        "name": "Edit",
        "description": "Edit a file by replacing a string...",
        "input_schema": { ... }
    },
    {
        "name": "Bash",
        "description": "Execute a bash command...",
        "input_schema": { ... }
    },
    {
        "name": "Glob",
        "description": "Find files matching a glob pattern...",
        "input_schema": { ... }
    },
    {
        "name": "Grep",
        "description": "Search for a pattern in files...",
        "input_schema": { ... }
    },
]
```

### 2. ToolApprovalManager (`code_map/terminal/tool_approval.py`)

Genera previews y diffs para las herramientas que requieren aprobación.

```python
class ToolApprovalManager:
    """
    Manages tool approval workflow with preview generation.
    """

    # Herramientas que modifican archivos
    FILE_MODIFICATION_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}

    # Herramientas que ejecutan comandos
    COMMAND_TOOLS = {"Bash"}

    # Herramientas seguras
    SAFE_TOOLS = {"Read", "Glob", "Grep", "TodoWrite", "WebFetch", "WebSearch", "Task"}
```

#### Tipos de Preview

| Tipo | Herramientas | Contenido |
|------|--------------|-----------|
| `diff` | Write, Edit | Diff unificado mostrando cambios |
| `multi_diff` | MultiEdit | Múltiples diffs en un solo preview |
| `command` | Bash | Comando a ejecutar con warnings |
| `generic` | Otras | JSON del input de la herramienta |

### 3. API Endpoint (`code_map/api/terminal.py`)

El endpoint WebSocket `/api/terminal/ws/agent` maneja el modo SDK.

```python
if permission_mode == "sdk":
    # Crear runner SDK
    sdk_config = SDKRunnerConfig(
        cwd=cwd,
        auto_approve_read=message.get("auto_approve_safe", True),
    )
    sdk_runner = SDKAgentRunner(sdk_config)

    # Ejecutar prompt
    await sdk_runner.run_prompt(
        prompt=prompt,
        on_event=send_event,
        on_tool_approval_request=handle_sdk_tool_approval,
    )
```

### 4. Frontend Store (`frontend/src/stores/claudeSessionStore.ts`)

Maneja el estado de la sesión y los modos de permiso.

```typescript
export type PermissionMode = "bypassPermissions" | "toolApproval" | "sdk";

export const PERMISSION_MODE_LABELS: Record<PermissionMode, string> = {
  bypassPermissions: "Auto Execute",
  sdk: "Review & Approve (SDK)",          // RECOMENDADO
  toolApproval: "Review & Approve (CLI)", // Puede ser unreliable
};
```

### 5. ToolApprovalModal (`frontend/src/components/ToolApprovalModal.tsx`)

Modal que muestra el preview/diff y permite aprobar o rechazar.

```tsx
<ToolApprovalModal
  approval={pendingToolApproval}
  onApprove={() => respondToToolApproval(true)}
  onReject={(feedback) => respondToToolApproval(false, feedback)}
/>
```

---

## Flujo de Ejecución Detallado

### Flujo Principal

```
Usuario                Frontend              Backend               Anthropic API
   │                      │                     │                        │
   │ 1. Selecciona "SDK"  │                     │                        │
   │ 2. Envía prompt      │                     │                        │
   │─────────────────────▶│                     │                        │
   │                      │ WebSocket: run      │                        │
   │                      │────────────────────▶│                        │
   │                      │                     │ 3. messages.create()   │
   │                      │                     │───────────────────────▶│
   │                      │                     │                        │
   │                      │                     │◀───────────────────────│
   │                      │                     │ 4. Response:           │
   │                      │                     │    stop_reason=tool_use│
   │                      │                     │    tool_use: Edit      │
   │                      │                     │                        │
   │                      │ 5. tool_approval_   │                        │
   │                      │    request (con diff)│                       │
   │                      │◀────────────────────│                        │
   │                      │                     │                        │
   │ 6. Ve modal con diff │                     │                        │
   │◀──────────────────────│                    │                        │
   │                      │                     │                        │
   │ 7. Aprueba           │                     │                        │
   │─────────────────────▶│                     │                        │
   │                      │ tool_approval_      │                        │
   │                      │ response: approved  │                        │
   │                      │────────────────────▶│                        │
   │                      │                     │ 8. Ejecuta Edit        │
   │                      │                     │    localmente          │
   │                      │                     │                        │
   │                      │                     │ 9. messages.create()   │
   │                      │                     │    con tool_result     │
   │                      │                     │───────────────────────▶│
   │                      │                     │                        │
   │                      │                     │◀───────────────────────│
   │                      │                     │ 10. Response:          │
   │                      │                     │     stop_reason=end_turn│
   │                      │                     │     text: "Done!"      │
   │                      │ 11. text event      │                        │
   │                      │◀────────────────────│                        │
   │                      │ 12. done event      │                        │
   │                      │◀────────────────────│                        │
   │ 13. Ve respuesta     │                     │                        │
   │◀──────────────────────│                    │                        │
```

### Flujo de Rechazo

```
Usuario              Frontend              Backend
   │                    │                     │
   │ Rechaza con        │                     │
   │ feedback           │                     │
   │───────────────────▶│                     │
   │                    │ tool_approval_      │
   │                    │ response: rejected  │
   │                    │ feedback: "Use X"   │
   │                    │────────────────────▶│
   │                    │                     │
   │                    │                     │ Envía tool_result
   │                    │                     │ con is_error: true
   │                    │                     │ content: "User rejected: Use X"
   │                    │                     │───────────────────▶ Anthropic
   │                    │                     │
   │                    │                     │◀─────────────────── Claude ajusta
   │                    │                     │ Claude puede intentar
   │                    │                     │ otra herramienta o
   │                    │                     │ preguntar al usuario
```

### Flujo de Auto-Aprobación (Read/Glob/Grep)

```
Backend                          Anthropic API
   │                                  │
   │ messages.create()                │
   │─────────────────────────────────▶│
   │                                  │
   │◀─────────────────────────────────│
   │ Response: tool_use: Read         │
   │                                  │
   │ auto_approve_read == true        │
   │ && tool_name in SAFE_TOOLS       │
   │                                  │
   │ Ejecuta Read inmediatamente      │
   │ (sin mostrar modal)              │
   │                                  │
   │ messages.create() con result     │
   │─────────────────────────────────▶│
   │                                  │
   │ Claude continúa...               │
```

---

## Formato de Mensajes WebSocket

### Cliente → Servidor

#### Ejecutar Prompt (SDK mode)
```json
{
  "command": "run",
  "prompt": "Create a file called test.txt with 'hello world'",
  "continue": false,
  "permission_mode": "sdk",
  "auto_approve_safe": true
}
```

#### Respuesta de Aprobación
```json
{
  "command": "tool_approval_response",
  "request_id": "uuid-del-request",
  "approved": true
}
```

#### Respuesta de Rechazo
```json
{
  "command": "tool_approval_response",
  "request_id": "uuid-del-request",
  "approved": false,
  "feedback": "Don't modify that file, use a different approach"
}
```

### Servidor → Cliente

#### Evento de Texto
```json
{
  "type": "assistant",
  "subtype": "text",
  "content": {
    "text": "I'll create that file for you."
  }
}
```

#### Evento de Tool Use
```json
{
  "type": "assistant",
  "subtype": "tool_use",
  "content": {
    "id": "toolu_01ABC123",
    "name": "Write",
    "input": {
      "file_path": "/path/to/test.txt",
      "content": "hello world"
    }
  }
}
```

#### Request de Aprobación
```json
{
  "type": "tool_approval_request",
  "request_id": "uuid-generado",
  "tool_name": "Write",
  "tool_input": {
    "file_path": "/path/to/test.txt",
    "content": "hello world"
  },
  "tool_use_id": "toolu_01ABC123",
  "preview_type": "diff",
  "preview_data": {
    "file_path": "/path/to/test.txt",
    "is_new_file": true,
    "original_lines": 0,
    "new_lines": 1
  },
  "file_path": "/path/to/test.txt",
  "original_content": "",
  "new_content": "hello world",
  "diff_lines": [
    "--- a//path/to/test.txt",
    "+++ b//path/to/test.txt",
    "@@ -0,0 +1 @@",
    "+hello world"
  ]
}
```

#### Evento de Tool Result
```json
{
  "type": "user",
  "subtype": "tool_result",
  "content": {
    "tool_use_id": "toolu_01ABC123",
    "content": "Wrote 11 characters to /path/to/test.txt",
    "is_error": false
  }
}
```

#### Evento de Finalización
```json
{
  "type": "result",
  "subtype": "success",
  "content": {
    "message": "Conversation complete"
  }
}
```

---

## Estructura de Datos

### ToolApprovalRequest

```python
@dataclass
class ToolApprovalRequest:
    request_id: str           # UUID único
    tool_name: str            # "Write", "Edit", "Bash", etc.
    tool_input: dict          # Parámetros de la herramienta
    tool_use_id: str          # ID del tool_use de Claude

    # Preview data
    preview_type: str         # "diff", "command", "generic"
    preview_data: dict        # Metadata del preview

    # File context (para Write/Edit)
    file_path: str | None
    original_content: str | None
    new_content: str | None
    diff_lines: list[str]

    # Status
    status: ApprovalStatus    # PENDING, APPROVED, REJECTED, TIMEOUT
    user_feedback: str | None
```

### Conversation Management

```python
class SDKAgentRunner:
    def __init__(self, config):
        self.conversation: list[dict] = []  # Historial de mensajes

    # Estructura de cada mensaje en conversation:
    # {"role": "user", "content": "prompt text"}
    # {"role": "assistant", "content": [TextBlock, ToolUseBlock, ...]}
    # {"role": "user", "content": [{"type": "tool_result", ...}]}
```

---

## Comparación: SDK vs CLI

| Aspecto | SDK Mode | CLI Mode (toolApproval) |
|---------|----------|------------------------|
| **Fiabilidad** | ✅ Siempre emite tool_use | ❌ A veces solo describe |
| **Control** | ✅ Control total del flujo | ❌ Dependemos del CLI |
| **Sesión** | ✅ Manejada internamente | ❌ Problemas de estado |
| **Streaming** | ⚠️ No streaming real | ✅ Streaming JSON |
| **Performance** | ⚠️ Llamadas síncronas | ✅ Async subprocess |
| **Dependencias** | `anthropic` package | Claude CLI instalado |
| **API Key** | Requerida | Usa sesión del CLI |

### Cuándo usar cada modo

- **SDK Mode**: Recomendado para workflow de aprobación de herramientas
- **CLI Mode (bypassPermissions)**: Para ejecución automática sin aprobación
- **CLI Mode (toolApproval)**: Deprecated, puede ser unreliable

---

## Configuración

### Variables de Entorno

```bash
# API Key de Anthropic (requerida para SDK mode)
export ANTHROPIC_API_KEY="sk-ant-..."

# El SDK usa esta variable automáticamente si no se pasa api_key en config
```

### Instalación de Dependencias

```bash
# En el virtualenv del proyecto
pip install anthropic
```

### Frontend Settings

El modo se selecciona desde el dropdown en la UI:

```typescript
// claudeSessionStore.ts
export const PERMISSION_MODES: PermissionMode[] = [
  "bypassPermissions",  // Auto Execute
  "sdk",                // Review & Approve (SDK) - RECOMENDADO
  "toolApproval",       // Review & Approve (CLI) - Puede ser unreliable
];
```

---

## Limitaciones Conocidas

### 1. Sin Streaming Real

El SDK mode no tiene streaming real de tokens. Claude responde completamente antes de que podamos procesar.

**Mitigación**: Los eventos se envían en cuanto Claude responde, incluyendo todo el texto de una vez.

### 2. Sin Continuación de Sesión CLI

El SDK mode maneja su propia conversación internamente. No se puede "continuar" una sesión del CLI.

**Mitigación**: Cada prompt en SDK mode empieza una conversación fresca (pero con contexto de la herramienta del sistema).

### 3. Herramientas Limitadas

Solo están implementadas las herramientas básicas: Read, Write, Edit, Bash, Glob, Grep.

**Extensión futura**: Agregar más herramientas siguiendo el patrón existente en `CLAUDE_TOOLS`.

### 4. Timeout de Aprobación

Por defecto, las solicitudes de aprobación tienen timeout de 5 minutos.

**Configuración**: Ajustable en `ToolApprovalManager.__init__(approval_timeout=300.0)`

---

## Extensión: Agregar Nueva Herramienta

### 1. Definir la herramienta en `CLAUDE_TOOLS`

```python
{
    "name": "NewTool",
    "description": "Description of what the tool does",
    "input_schema": {
        "type": "object",
        "properties": {
            "param1": {"type": "string", "description": "..."},
            "param2": {"type": "integer", "description": "..."},
        },
        "required": ["param1"]
    }
}
```

### 2. Implementar la ejecución

```python
async def _execute_newtool(self, tool_input: dict) -> dict:
    """Execute NewTool"""
    param1 = tool_input.get("param1", "")
    param2 = tool_input.get("param2", 0)

    try:
        # Implementar lógica
        result = do_something(param1, param2)
        return {"content": result, "is_error": False}
    except Exception as e:
        return {"content": f"Error: {str(e)}", "is_error": True}
```

### 3. Agregar al dispatch en `_execute_tool`

```python
async def _execute_tool(self, tool_name: str, tool_input: dict) -> dict:
    if tool_name == "Read":
        return await self._execute_read(tool_input)
    # ... otras herramientas ...
    elif tool_name == "NewTool":
        return await self._execute_newtool(tool_input)
    else:
        return {"content": f"Unknown tool: {tool_name}", "is_error": True}
```

### 4. Decidir categoría de aprobación

```python
# Si es solo lectura:
SAFE_TOOLS = {"Read", "Glob", "Grep", "NewTool"}

# Si modifica estado:
APPROVAL_REQUIRED_TOOLS = {"Write", "Edit", "Bash", "NewTool"}
```

### 5. (Opcional) Agregar preview personalizado

En `ToolApprovalManager._create_approval_request()`:

```python
elif tool_name == "NewTool":
    self._generate_newtool_preview(request)
```

---

## Testing

### Test Manual

1. Iniciar backend:
```bash
cd /home/jesusramos/Workspace/ATLAS
.venv/bin/python -m code_map.cli run --root .
```

2. Abrir frontend en `/agent`

3. Seleccionar "Review & Approve (SDK)" en el dropdown

4. Enviar prompt:
```
Create a new file called test_sdk.txt with the content "Hello from SDK mode!"
```

5. Verificar:
   - Aparece modal con diff
   - El diff muestra el nuevo contenido
   - Al aprobar, el archivo se crea
   - Al rechazar, Claude recibe el error

### Test Automatizado

```python
# tests/test_sdk_runner.py
import pytest
from code_map.terminal.sdk_runner import SDKAgentRunner, SDKRunnerConfig

@pytest.mark.asyncio
async def test_sdk_runner_read():
    config = SDKRunnerConfig(cwd="/tmp", auto_approve_read=True)
    runner = SDKAgentRunner(config)

    events = []
    await runner.run_prompt(
        prompt="Read the file /etc/hostname",
        on_event=lambda e: events.append(e),
    )

    # Verificar que hubo tool_use y tool_result
    assert any(e.get("subtype") == "tool_use" for e in events)
    assert any(e.get("subtype") == "tool_result" for e in events)
```

---

## Troubleshooting

### Error: "ANTHROPIC_API_KEY not set"

**Solución**: Exportar la variable de entorno:
```bash
export ANTHROPIC_API_KEY="sk-ant-api03-..."
```

### Error: "anthropic module not found"

**Solución**: Instalar el paquete:
```bash
.venv/bin/pip install anthropic
```

### Modal no aparece para herramientas de escritura

**Verificar**:
1. Que `permission_mode` sea `"sdk"`
2. Que `auto_approve_safe` no incluya la herramienta
3. Logs del backend para ver si hay errores

### Claude solo describe pero no ejecuta

**Esto NO debería pasar en SDK mode**. Si pasa:
1. Verificar que el mode sea `"sdk"` (no `"toolApproval"`)
2. Revisar logs para ver `stop_reason` de la respuesta
3. Verificar que las herramientas estén correctamente definidas

---

## Referencias

- [Anthropic Python SDK](https://github.com/anthropics/anthropic-sdk-python)
- [Tool Use Documentation](https://docs.anthropic.com/en/docs/build-with-claude/tool-use)
- [Messages API Reference](https://docs.anthropic.com/en/api/messages)
