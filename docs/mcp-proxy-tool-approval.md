# MCP Proxy Tool Approval Architecture

## Resumen Ejecutivo

Este documento describe la arquitectura del sistema de aprobación de herramientas basado en **MCP Tool Proxy**, que permite aprobar/rechazar operaciones de Write, Edit y Bash **usando tu suscripción existente de Claude CLI** (sin necesitar una API key separada).

### Problema Original

El modo `toolApproval` original usaba el CLI con `--permission-mode plan`, pero Claude describía las acciones en lugar de emitir eventos `tool_use`.

El modo `sdk` lo solucionaba usando el SDK de Anthropic directamente, pero **requiere una API key separada con facturación independiente** de la suscripción de Claude CLI.

### Solución: MCP Proxy

Usar el **CLI de Claude con un MCP Tool Proxy Server** que:

1. Deshabilita las tools nativas peligrosas (`--disallowed-tools "Write,Edit,Bash"`)
2. Expone tools proxy via MCP: `atlas_write`, `atlas_edit`, `atlas_bash`
3. Intercepta las llamadas y pide aprobación antes de ejecutar
4. **Usa tu suscripción existente de Claude CLI** (€108/mes o lo que pagues)

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
│  │                                                                      │ │
│  │  permission_mode == "mcpProxy":                                     │ │
│  │  ┌─────────────────┐    ┌─────────────────────────────────────────┐ │ │
│  │  │ MCPProxyRunner  │───▶│ MCPSocketServer ──▶ ApprovalBridge      │ │ │
│  │  └────────┬────────┘    └───────────────────────────────┬─────────┘ │ │
│  └───────────┼─────────────────────────────────────────────┼───────────┘ │
│              │                                              │             │
│              │ subprocess                                   │ Unix socket │
│              ▼                                              ▼             │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │         Claude CLI                    MCP Tool Proxy Server       │   │
│  │  ┌─────────────────────────────┐    ┌───────────────────────────┐│   │
│  │  │ --disallowed-tools          │    │ atlas_write()             ││   │
│  │  │   "Write,Edit,Bash"         │───▶│ atlas_edit()              ││   │
│  │  │                             │    │ atlas_bash()              ││   │
│  │  │ --mcp-config atlas.json     │    │                           ││   │
│  │  │ --dangerously-skip-         │    │ ┌───────────────────────┐ ││   │
│  │  │   permissions               │    │ │ request_approval()    │─┼┼───┘
│  │  └─────────────────────────────┘    │ └───────────────────────┘ ││
│  │                                      └───────────────────────────┘│
│  └───────────────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────────────────┘
```

---

## Componentes Principales

### 1. MCPProxyRunner (`code_map/terminal/mcp_proxy_runner.py`)

Runner que ejecuta Claude CLI con MCP tool proxy.

```python
class MCPProxyRunner:
    # Tools que requieren aprobación (deshabilitadas en CLI, provistas por MCP proxy)
    APPROVAL_REQUIRED_TOOLS = ["Write", "Edit", "Bash"]

    def _create_mcp_config(self) -> str:
        """Crea config MCP temporal para el tool proxy server"""
        config = {
            "mcpServers": {
                "atlas-tools": {
                    "command": "python",
                    "args": ["-m", "code_map.mcp.tool_proxy_server"],
                    "env": {
                        "ATLAS_TOOL_SOCKET": "/tmp/atlas_tool_approval.sock",
                        "ATLAS_CWD": self.config.cwd,
                    }
                }
            }
        }
        return temp_file_path
```

### 2. MCP Tool Proxy Server (`code_map/mcp/tool_proxy_server.py`)

MCP server que expone tools proxy que requieren aprobación.

```python
class ToolProxyServer:
    async def atlas_write(self, file_path: str, content: str) -> str:
        """Write con aprobación requerida"""
        preview = self._generate_write_preview(file_path, content)
        approved, feedback = await self._request_approval("write", params, preview)
        if not approved:
            return f"[DENIED] Write rejected: {feedback}"
        # Ejecutar el write real
        Path(file_path).write_text(content)
        return f"Successfully wrote to {file_path}"

    async def atlas_edit(self, file_path, old_string, new_string, replace_all=False):
        """Edit con aprobación requerida"""
        preview = self._generate_edit_preview(...)
        approved, feedback = await self._request_approval("edit", params, preview)
        # ...

    async def atlas_bash(self, command: str, timeout=120000, description=""):
        """Bash con aprobación requerida"""
        preview = self._generate_bash_preview(command)
        approved, feedback = await self._request_approval("bash", params, preview)
        # ...
```

### 3. Socket Server (`code_map/mcp/socket_server.py`)

Servidor Unix socket que conecta el MCP proxy con el backend.

```python
class MCPSocketServer:
    """
    Recibe solicitudes de aprobación del MCP proxy
    y las envía al frontend via WebSocket.
    """

    async def _process_request(self, request):
        if request["type"] == "tool_approval_request":
            # Usa ApprovalBridge para generar preview y esperar respuesta
            result = await self.bridge.request_approval(
                tool_name=request["tool"],
                tool_input=request["params"],
                context=request["preview"],
            )
            return {"approved": result["approved"], "feedback": result.get("message", "")}
```

### 4. Approval Bridge (`code_map/mcp/approval_bridge.py`)

Gestiona solicitudes de aprobación pendientes y genera diffs.

```python
class ApprovalBridge:
    async def request_approval(self, tool_name, tool_input, context=""):
        # Genera preview (diff para files, comando para bash)
        request = ApprovalRequest(...)
        await self._generate_preview(request)

        # Notifica al frontend
        await self._notify_callback(request)

        # Espera respuesta del usuario (timeout 5 min)
        return await asyncio.wait_for(future, timeout=300.0)
```

---

## Flujo de Ejecución

### 1. Usuario envía prompt

```
Frontend: sendPrompt("Crea un archivo test.py con hello world")
                │
                ▼
Backend (WebSocket): permission_mode == "mcpProxy"
                │
                ▼
Crea MCPProxyRunner → Crea config MCP temporal
                │
                ▼
Inicia Claude CLI:
  claude -p \
    --disallowed-tools "Write,Edit,Bash" \
    --mcp-config /tmp/atlas_xxx.json \
    --dangerously-skip-permissions \
    ...
```

### 2. Claude decide escribir archivo

```
Claude CLI: "Voy a crear el archivo..."
                │
                ▼
Claude emite tool_use: atlas_write
                │
                ▼
MCP Tool Proxy Server recibe la llamada
                │
                ▼
Genera preview: "CREATE /path/test.py\n+ print('hello world')"
                │
                ▼
Envía solicitud de aprobación via Unix socket
```

### 3. Backend recibe solicitud

```
MCPSocketServer recibe:
  {"type": "tool_approval_request", "tool": "write", ...}
                │
                ▼
ApprovalBridge genera diff completo
                │
                ▼
Envía a frontend via WebSocket:
  {"type": "tool_approval_request", "tool_name": "Write", "diff_lines": [...]}
```

### 4. Usuario responde

```
Frontend: ToolApprovalModal muestra diff
                │
                ▼
Usuario: "Aprobar" o "Rechazar"
                │
                ▼
WebSocket: {"command": "tool_approval_response", "approved": true}
                │
                ▼
MCPSocketServer.respond_to_approval(request_id, approved=True)
                │
                ▼
ApprovalBridge resuelve el Future
                │
                ▼
MCP Tool Proxy ejecuta el write real
                │
                ▼
Claude recibe el resultado y continúa
```

---

## Modos de Permiso Disponibles

| Modo | Descripción | API Key | Billing |
|------|-------------|---------|---------|
| `bypassPermissions` | Auto-ejecuta todo | CLI | Suscripción CLI |
| **`mcpProxy`** | **Review con MCP proxy** | **CLI** | **Suscripción CLI** |
| `toolApproval` | Review via plan mode (poco fiable) | CLI | Suscripción CLI |
| `sdk` | Review via SDK (recomendado solo si tienes API key) | API Key | Separado |

---

## Configuración Frontend

```typescript
export type PermissionMode = "bypassPermissions" | "mcpProxy" | "toolApproval" | "sdk";

export const PERMISSION_MODE_LABELS: Record<PermissionMode, string> = {
  bypassPermissions: "Auto Execute",
  mcpProxy: "Review & Approve (CLI)",           // ← RECOMENDADO
  toolApproval: "Review & Approve (Plan)",
  sdk: "Review & Approve (SDK)",
};
```

---

## Requisitos

1. **Python 3.10+** con dependencias instaladas
2. **Claude CLI** instalado y autenticado (`claude --version`)
3. **MCP SDK** para Python: `pip install 'mcp[cli]'`

---

## Testing

```bash
# Probar MCP server standalone
python -m code_map.mcp.tool_proxy_server --transport stdio

# Probar runner con prompt simple
python -c "
import asyncio
from code_map.terminal.mcp_proxy_runner import MCPProxyRunner, MCPProxyRunnerConfig

config = MCPProxyRunnerConfig(cwd='/tmp')
runner = MCPProxyRunner(config)

async def test():
    await runner.run_prompt(
        'Lee el archivo /etc/hostname',
        on_event=lambda e: print(e),
        on_error=lambda e: print(f'ERROR: {e}'),
        on_done=lambda: print('DONE'),
    )

asyncio.run(test())
"
```

---

## Comparación: SDK vs MCP Proxy

| Aspecto | SDK Mode | MCP Proxy Mode |
|---------|----------|----------------|
| **API Key** | Requiere API key separada | Usa suscripción CLI |
| **Billing** | Separado (~$15/M tokens) | Incluido en suscripción |
| **Herramientas** | Solo las definidas en código | Todas las del CLI + MCP |
| **Contexto** | Sin acceso a CLAUDE.md, MCP servers | Acceso completo |
| **Fiabilidad** | 100% - Control total del flujo | 99% - Depende del MCP proxy |
| **Complejidad** | Simple - Todo en Python | Media - Requiere socket IPC |

**Recomendación**: Usa `mcpProxy` si ya pagas por Claude Pro/Team. Usa `sdk` solo si necesitas control absoluto y tienes presupuesto para API.
