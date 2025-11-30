# MCP Permission Server Design for Tool Approval

## Resumen Ejecutivo

Este documento describe la arquitectura para implementar un sistema de Tool Approval usando `--permission-prompt-tool` de Claude Code con un MCP Server custom que se comunica con el frontend de ATLAS.

## El Problema Actual

El sistema actual usa `--permission-mode plan`, lo que hace que Claude Code:
1. "Sepa" que está en modo plan y decida NO proponer herramientas
2. Describa lo que haría en lugar de emitir `tool_use` events
3. No permita interceptar herramientas antes de su ejecución

## La Solución: MCP Permission Server

### Arquitectura de Alto Nivel

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│                 │     │                  │     │                 │
│  Claude Code    │────▶│  MCP Permission  │────▶│    Frontend     │
│  CLI            │◀────│  Server          │◀────│    (React)      │
│                 │     │                  │     │                 │
└─────────────────┘     └──────────────────┘     └─────────────────┘
        │                       │                        │
        │ --permission-prompt-  │ WebSocket              │
        │ tool mcp__approval    │ (internal)             │
        │                       │                        │
        ▼                       ▼                        ▼
   Ejecuta tools          Recibe requests         Muestra modal
   si approved            de permiso y            de aprobación
                          espera respuesta
```

### Flujo de Comunicación

```
1. Usuario envía prompt al Frontend
2. Backend (terminal.py) inicia Claude Code con:
   - --permission-prompt-tool mcp__approval__check_permission
   - MCP server configurado en .mcp.json o inline

3. Claude Code procesa el prompt y quiere usar una herramienta (ej: Edit)

4. Claude Code llama al MCP tool "check_permission" con:
   {
     "tool_name": "Edit",
     "tool_input": {...},
     "context": "..."
   }

5. MCP Server recibe la request y:
   a. Genera preview/diff del cambio
   b. Envía notificación al Frontend via WebSocket interno
   c. Espera respuesta del usuario (con timeout)

6. Frontend muestra modal de aprobación con:
   - Nombre de la herramienta
   - Preview/diff del cambio
   - Botones Aprobar/Rechazar

7. Usuario responde → Frontend envía a MCP Server

8. MCP Server responde a Claude Code:
   - Si aprobado: {"behavior": "allow", "updatedInput": {...}}
   - Si rechazado: {"behavior": "deny", "message": "User rejected"}

9. Claude Code ejecuta o no la herramienta según la respuesta
```

## Diseño Detallado

### 1. MCP Permission Server (Python)

```python
# code_map/mcp/permission_server.py
from mcp.server.fastmcp import FastMCP
import asyncio

mcp = FastMCP("ATLASPermissions")

# Singleton para comunicación con el backend principal
_approval_bridge = None

def set_approval_bridge(bridge):
    global _approval_bridge
    _approval_bridge = bridge

@mcp.tool()
async def check_permission(
    tool_name: str,
    tool_input: dict,
    context: str = ""
) -> dict:
    """
    Check if a tool execution should be allowed.

    Returns:
        {"behavior": "allow", "updatedInput": {...}} or
        {"behavior": "deny", "message": "..."}
    """
    if _approval_bridge is None:
        # No bridge = auto-approve (fallback)
        return {"behavior": "allow", "updatedInput": tool_input}

    # Enviar request al frontend y esperar respuesta
    result = await _approval_bridge.request_approval(
        tool_name=tool_name,
        tool_input=tool_input,
        context=context
    )

    if result["approved"]:
        return {
            "behavior": "allow",
            "updatedInput": result.get("updated_input", tool_input)
        }
    else:
        return {
            "behavior": "deny",
            "message": result.get("message", "User rejected the operation")
        }
```

### 2. Approval Bridge (Comunicación Backend ↔ MCP Server)

```python
# code_map/mcp/approval_bridge.py
import asyncio
from dataclasses import dataclass
from typing import Optional, Callable, Any
from uuid import uuid4

@dataclass
class ApprovalRequest:
    request_id: str
    tool_name: str
    tool_input: dict
    context: str
    preview_data: dict  # Generated diff/preview

class ApprovalBridge:
    """
    Bridge between MCP Permission Server and the main backend.
    Manages pending approval requests and notifies the frontend.
    """

    def __init__(self):
        self._pending: dict[str, asyncio.Future] = {}
        self._notify_callback: Optional[Callable] = None
        self._timeout = 300.0  # 5 minutes

    def set_notify_callback(self, callback: Callable[[ApprovalRequest], Any]):
        """Set callback to notify frontend of new approval requests"""
        self._notify_callback = callback

    async def request_approval(
        self,
        tool_name: str,
        tool_input: dict,
        context: str = ""
    ) -> dict:
        """
        Request approval from the user.

        Blocks until user responds or timeout.
        """
        request_id = str(uuid4())

        # Generate preview based on tool type
        preview_data = await self._generate_preview(tool_name, tool_input)

        request = ApprovalRequest(
            request_id=request_id,
            tool_name=tool_name,
            tool_input=tool_input,
            context=context,
            preview_data=preview_data
        )

        # Create future for response
        future = asyncio.get_event_loop().create_future()
        self._pending[request_id] = future

        try:
            # Notify frontend
            if self._notify_callback:
                await self._notify_callback(request)

            # Wait for response
            result = await asyncio.wait_for(future, timeout=self._timeout)
            return result

        except asyncio.TimeoutError:
            return {"approved": False, "message": "Approval timeout"}
        finally:
            self._pending.pop(request_id, None)

    def respond(self, request_id: str, approved: bool, message: str = "", updated_input: dict = None):
        """Respond to a pending approval request"""
        future = self._pending.get(request_id)
        if future and not future.done():
            future.set_result({
                "approved": approved,
                "message": message,
                "updated_input": updated_input
            })
            return True
        return False

    async def _generate_preview(self, tool_name: str, tool_input: dict) -> dict:
        """Generate preview data for the tool operation"""
        # Reuse existing preview logic from tool_approval.py
        from code_map.terminal.tool_approval import ToolApprovalManager
        # ... generate diff, command preview, etc.
        return {}
```

### 3. Integración con Claude Runner

```python
# Modificar claude_runner.py

class ClaudeAgentRunner:
    def __init__(self, config: ClaudeRunnerConfig):
        # ...existing code...

        # Para modo toolApproval con MCP
        self._mcp_server_process = None
        self._approval_bridge = None

        if config.permission_mode == "toolApproval":
            self._setup_mcp_approval_server()

    def _setup_mcp_approval_server(self):
        """Setup MCP server for permission handling"""
        from code_map.mcp.approval_bridge import ApprovalBridge
        from code_map.mcp import permission_server

        self._approval_bridge = ApprovalBridge()
        permission_server.set_approval_bridge(self._approval_bridge)

    async def run_prompt(self, ...):
        # Build command
        cmd = [claude_bin, "-p", "--output-format", "stream-json", ...]

        if self.config.permission_mode == "toolApproval":
            # Use --permission-prompt-tool instead of --permission-mode plan
            cmd.extend([
                "--permission-prompt-tool",
                "mcp__atlas_approval__check_permission"
            ])

            # Start MCP server as subprocess or use stdio
            # Option A: Inline MCP server via stdio
            # Option B: HTTP MCP server running separately
```

### 4. Opciones de Transporte para MCP Server

#### Opción A: Stdio (Recomendada para este caso)

El MCP server se ejecuta como subproceso de Claude Code usando stdio.

**Pros:**
- Comunicación directa sin red
- Más simple de configurar
- No requiere puerto adicional

**Cons:**
- Necesitamos comunicar MCP server ↔ Backend principal de alguna manera

**Solución para comunicación:**
- MCP server escribe a un socket Unix o named pipe
- Backend principal escucha ese socket
- Cuando llega approval request, backend notifica al frontend via WebSocket existente

#### Opción B: HTTP MCP Server (Más complejo pero más flexible)

```python
# El MCP server corre como servicio HTTP separado
# en un puerto diferente (ej: 8011)

# En claude_runner.py:
cmd.extend([
    "--permission-prompt-tool",
    "http://localhost:8011/mcp/tools/check_permission"
])
```

### 5. Arquitectura Recomendada (Opción A con Socket)

```
┌─────────────────────────────────────────────────────────────────┐
│                        Backend Principal (8010)                  │
│  ┌─────────────┐    ┌──────────────┐    ┌───────────────────┐   │
│  │ terminal.py │───▶│ ApprovalBrdg │───▶│ Unix Socket       │   │
│  │ (WebSocket) │◀───│              │◀───│ /tmp/atlas_mcp.sock│  │
│  └─────────────┘    └──────────────┘    └─────────┬─────────┘   │
│         │                                         │              │
│         ▼                                         │              │
│  ┌─────────────────┐                              │              │
│  │ Frontend WS     │                              │              │
│  │ (approval modal)│                              │              │
│  └─────────────────┘                              │              │
└───────────────────────────────────────────────────┼──────────────┘
                                                    │
                    ┌───────────────────────────────┘
                    │
                    ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Claude Code Process                           │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                   MCP Permission Server                      ││
│  │  (subprocess comunicando via stdio con Claude Code,          ││
│  │   y via Unix Socket con Backend Principal)                   ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
```

## Configuración MCP

### .mcp.json (Project-level)

```json
{
  "mcpServers": {
    "atlas_approval": {
      "command": "python",
      "args": ["-m", "code_map.mcp.permission_server"],
      "env": {
        "ATLAS_SOCKET": "/tmp/atlas_mcp.sock"
      }
    }
  }
}
```

### Invocación de Claude Code

```bash
claude -p \
  --output-format stream-json \
  --input-format stream-json \
  --permission-prompt-tool mcp__atlas_approval__check_permission \
  "your prompt here"
```

## Plan de Implementación

### Fase 1: MCP Server Básico
1. Crear `code_map/mcp/permission_server.py` con FastMCP
2. Implementar tool `check_permission` que auto-aprueba todo
3. Probar que Claude Code lo llama correctamente

### Fase 2: Comunicación Socket
1. Crear `code_map/mcp/approval_bridge.py`
2. Implementar comunicación via Unix socket
3. Backend principal escucha el socket

### Fase 3: Integración Frontend
1. Conectar ApprovalBridge con WebSocket existente
2. Modificar `claudeSessionStore.ts` para manejar nuevos eventos
3. Reutilizar `ToolApprovalModal` existente

### Fase 4: Preview/Diff
1. Integrar lógica de preview de `tool_approval.py`
2. Generar diffs para Edit/Write
3. Mostrar previews en modal

## Consideraciones

### Seguridad
- El MCP server solo debe aceptar conexiones del socket local
- Timeout para prevenir bloqueos indefinidos
- Sanitizar inputs antes de generar previews

### Rendimiento
- Reutilizar conexión socket
- Cache de previews para operaciones repetidas
- Async en todo el flujo

### Fallbacks
- Si el socket no está disponible → auto-aprobar (con warning)
- Si timeout → rechazar (más seguro)
- Si error en preview → mostrar input raw

## Referencias

- [GitHub Issue #1175](https://github.com/anthropics/claude-code/issues/1175) - Feature request con formato de respuesta
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) - SDK oficial
- [Claude Code Playbook](https://www.vibesparking.com/en/blog/ai/claude-code/docs/cli/2025-08-28-outsourcing-permissions-with-claude-code-permission-prompt-tool/) - Tutorial de --permission-prompt-tool
- [CLIAI/mcp_permission_server](https://github.com/CLIAI/mcp_permission_server_claude_code) - Intento de la comunidad

## Formato de Respuesta MCP (Confirmado)

```json
// Allow
{
  "behavior": "allow",
  "updatedInput": { /* original or modified input */ }
}

// Deny
{
  "behavior": "deny",
  "message": "Reason for denial"
}
```
