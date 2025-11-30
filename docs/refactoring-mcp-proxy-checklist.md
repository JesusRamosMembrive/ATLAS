# Plan de Refactorización: MCP Proxy Tool Approval System

**Fecha**: 2025-11-28
**Estado**: En progreso
**Tiempo estimado total**: ~5 horas

---

## Resumen Ejecutivo

Auditoría completada del sistema MCP Proxy Tool Approval. El código es funcional y seguro, pero tiene problemas de mantenibilidad que deben abordarse para un proyecto Stage 3 (Production-Ready).

---

## Hallazgos Principales

### Problemas Críticos (3)

| # | Problema | Archivos | Impacto |
|---|----------|----------|---------|
| 1 | **Debug prints mezclados con logging** | Todos los archivos MCP + terminal.py | 60+ print() statements en código de producción |
| 2 | **Funciones demasiado largas** | `terminal.py:agent_websocket` (540 líneas), `mcp_proxy_runner.py:run_prompt` (182 líneas), `approval_bridge.py:request_approval` (97 líneas) | Complejidad ciclomática alta, difícil de testear |
| 3 | **Type assertions inseguras (frontend)** | `claudeSessionStore.ts`, `ToolApprovalModal.tsx` | `as unknown as`, `as boolean` bypassing TypeScript safety |

### Problemas Mayores (5)

| # | Problema | Ubicación |
|---|----------|-----------|
| 4 | Store de Zustand demasiado grande | `claudeSessionStore.ts` (1172 líneas) |
| 5 | Código duplicado en approval handlers | 4 funciones casi idénticas en `terminal.py` |
| 6 | Constantes duplicadas (socket path) | 3 archivos definen `DEFAULT_SOCKET_PATH` |
| 7 | Interfaces duplicadas | `PendingToolApproval` vs `PendingMCPApproval` |
| 8 | console.log en producción | 24+ llamadas en frontend |

### Problemas Menores (8)

- Magic numbers sin constantes nombradas
- Imports dentro de funciones (`difflib`, `uuid`)
- Parámetros no usados (`lineNumber` en DiffLine)
- Código deprecado no eliminado
- `LEGACY_SOCKET_PATH` no usado
- `_pending` dict no usado en ToolProxyServer
- Patrón `await_if_coro` repetido 5 veces
- `substr` deprecado (usar `substring`)

---

## Fase 1: Limpieza Inmediata (Debug/Logging)

**Objetivo**: Eliminar debug prints y estandarizar logging
**Esfuerzo estimado**: 30 min
**Impacto**: Alto - código listo para producción

### Backend (Python)

- [x] `code_map/mcp/approval_bridge.py` - 12 prints → logger.debug ✅
- [x] `code_map/mcp/socket_server.py` - 7 prints → logger.debug ✅
- [x] `code_map/mcp/tool_proxy_server.py` - 5 prints → logger.debug ✅
- [x] `code_map/api/terminal.py` - 40+ prints → logger.debug ✅

### Frontend (TypeScript)

- [x] Crear `frontend/src/utils/logger.ts` con helper condicional ✅
- [x] `frontend/src/stores/claudeSessionStore.ts` - 24 console.log → debug() ✅
- [x] `frontend/src/components/ToolApprovalModal.tsx` - 2 console.log → debug() ✅

### Patrón a aplicar (Python)
```python
# Antes
print(f"DEBUG: [MCPSocketServer] Started on {self.socket_path}", flush=True)

# Después
logger.debug(f"[MCPSocketServer] Started on {self.socket_path}")
```

### Patrón a aplicar (TypeScript)
```typescript
// utils/logger.ts
const isDev = import.meta.env.DEV;
export const debug = (msg: string, ...args: unknown[]) => {
  if (isDev) console.log(msg, ...args);
};

// Uso
debug("[ClaudeSession] WebSocket connected");
```

---

## Fase 2: Constantes Compartidas

**Objetivo**: Eliminar duplicación de constantes
**Esfuerzo estimado**: 15 min
**Impacto**: Medio - elimina duplicación

- [x] Crear `code_map/mcp/constants.py` ✅
- [x] Actualizar imports en `socket_server.py` ✅
- [x] Actualizar imports en `tool_proxy_server.py` ✅
- [x] Actualizar imports en `mcp_proxy_runner.py` ✅
- [x] Actualizar imports en `approval_bridge.py` ✅

---

## Fase 3: Extraer Handlers de terminal.py

**Objetivo**: Reducir `agent_websocket` de 540 líneas a ~320 líneas
**Esfuerzo estimado**: 2 horas
**Impacto**: Alto - mejora mantenibilidad

### Estructura de archivos

- [x] Crear directorio `code_map/api/handlers/` ✅
- [x] Crear `code_map/api/handlers/__init__.py` ✅
- [x] Crear `code_map/api/handlers/base.py` - BaseAgentHandler ABC ✅
- [x] Crear `code_map/api/handlers/sdk_handler.py` - SDKModeHandler ✅
- [x] Crear `code_map/api/handlers/mcp_proxy_handler.py` - MCPProxyModeHandler ✅
- [x] Crear `code_map/api/handlers/cli_handler.py` - CLIModeHandler ✅
- [x] Crear `code_map/api/handlers/approval.py` - Shared approval utilities ✅
- [x] Crear `code_map/api/handlers/factory.py` - Handler factory function ✅

### Implementación

- [x] Implementar `BaseAgentHandler` ABC con métodos abstractos ✅
- [x] Migrar lógica SDK a `SDKModeHandler` ✅
- [x] Migrar lógica MCP proxy a `MCPProxyModeHandler` ✅
- [x] Migrar lógica CLI a `CLIModeHandler` ✅
- [x] Crear función factory `create_handler(mode, websocket, cwd)` ✅
- [x] Refactorizar `agent_websocket` para usar handlers ✅
- [x] Unificar código duplicado de approval en `approval.py` ✅

### Estructura implementada
```python
# handlers/base.py
class BaseAgentHandler(ABC):
    def __init__(self, config: HandlerConfig, callbacks: HandlerCallbacks):
        self.config = config
        self.callbacks = callbacks
        self.runner = None
        self._running = False

    @abstractmethod
    async def handle_run(self, prompt: str, message: dict) -> asyncio.Task: ...

    @abstractmethod
    async def handle_cancel(self) -> None: ...

    async def handle_tool_approval_response(...) -> bool: ...
    async def cleanup(self) -> None: ...
```

---

## Fase 4: Refactorizar Métodos Largos

**Objetivo**: Mejorar testabilidad y legibilidad
**Esfuerzo estimado**: 1 hora
**Impacto**: Medio - mejora testabilidad

### 4.1 `run_prompt` en mcp_proxy_runner.py (182 → ~65 líneas)

- [x] Extraer `_build_command() -> list[str]` ✅
- [x] Extraer `_start_process() -> Process` ✅
- [x] Extraer `_create_stdout_reader() -> Coroutine` ✅
- [x] Extraer `_create_stderr_reader() -> Coroutine` ✅
- [x] Extraer `_send_initial_prompt()` ✅
- [x] Extraer `_wait_for_process()` ✅
- [x] Refactorizar `run_prompt` para usar métodos extraídos ✅

### 4.2 `request_approval` en approval_bridge.py (97 → ~45 líneas)

- [x] Extraer `_create_approval_request() -> ApprovalRequest` ✅
- [x] Extraer `_auto_approve_response() -> dict` ✅
- [x] Extraer `_denial_response() -> dict` ✅
- [x] Extraer `_notify_and_wait() -> dict` ✅
- [x] Refactorizar `request_approval` para usar métodos extraídos ✅

---

## Fase 5: Mejoras TypeScript

**Objetivo**: Type safety y eliminación de type assertions inseguras
**Esfuerzo estimado**: 1 hora
**Impacto**: Medio - type safety

### 5.1 Crear tipos seguros para preview data

- [x] Crear `frontend/src/types/approval.ts` ✅
- [x] Definir `DiffPreviewData` interface ✅
- [x] Definir `CommandPreviewData` interface ✅
- [x] Definir `MultiDiffPreviewData` interface ✅
- [x] Añadir type guards y helper functions ✅

### 5.2 Refactorizar componentes

- [x] Actualizar `ToolApprovalModal.tsx` para usar tipos seguros ✅
- [x] Eliminar `as boolean` assertions con `extractCommandPreview()` ✅
- [x] Eliminar `as Array<...>` assertions con `extractMultiDiffEdits()` ✅
- [x] Mejorar extracción de errores legacy en `claudeSessionStore.ts` ✅
- [x] Mejorar extracción de errores legacy en `geminiSessionStore.ts` ✅

### Tipos esperados
```typescript
// types/approval.ts
interface DiffPreviewData {
  is_new_file: boolean;
  original_lines: number;
  new_lines: number;
}

interface CommandPreviewData {
  command: string;
  description?: string;
  has_sudo: boolean;
  has_rm: boolean;
  has_pipe: boolean;
  has_redirect: boolean;
}

type PreviewData =
  | { type: "diff"; data: DiffPreviewData }
  | { type: "command"; data: CommandPreviewData }
  | { type: "generic"; data: Record<string, unknown> };

interface BasePendingApproval {
  requestId: string;
  toolName: string;
  toolInput: Record<string, unknown>;
  previewType: "diff" | "multi_diff" | "command" | "generic";
  previewData: Record<string, unknown>;
  filePath?: string;
  originalContent?: string;
  newContent?: string;
  diffLines: string[];
  timestamp: Date;
}
```

---

## Fase 6: Limpieza de Código Muerto

**Objetivo**: Housekeeping y eliminación de código no usado
**Esfuerzo estimado**: 15 min
**Impacto**: Bajo - housekeeping

### Eliminar código muerto

- [x] Eliminar `LEGACY_SOCKET_PATH` no usado en `constants.py` ✅
- [x] Eliminar `_pending` dict no usado en `tool_proxy_server.py` ✅
- [x] Evaluar código MCP deprecado - no hay más código muerto ✅

### Mover imports al top

- [x] Mover `import difflib` al top en `approval_bridge.py` ✅

### Corregir deprecaciones

- [x] Cambiar `substr` → `substring` en `claude-events.ts:587` ✅

---

## Orden de Ejecución Recomendado

| Prioridad | Fase | Esfuerzo | Impacto | Estado |
|-----------|------|----------|---------|--------|
| 1 | Fase 1: Debug/Logging | 30 min | Alto | [x] Completada ✅ |
| 2 | Fase 2: Constantes | 15 min | Medio | [x] Completada ✅ |
| 3 | Fase 6: Limpieza | 15 min | Bajo | [x] Completada ✅ |
| 4 | Fase 3: Handlers | 2 horas | Alto | [x] Completada ✅ |
| 5 | Fase 4: Métodos largos | 1 hora | Medio | [x] Completada ✅ |
| 6 | Fase 5: TypeScript | 1 hora | Medio | [x] Completada ✅ |

---

## Notas Importantes

- El sistema es **funcional y seguro** - estas mejoras son de calidad de código
- Las Fases 1-2-6 pueden hacerse juntas en un solo commit
- La Fase 3 es el cambio más grande pero el de mayor impacto
- Considerar dividir `claudeSessionStore.ts` en slices (futuro)
- Ejecutar tests después de cada fase para verificar que no se rompe nada

---

## Registro de Progreso

| Fecha | Fase | Cambios | Commit |
|-------|------|---------|--------|
| 2025-11-28 | Fase 1 | Debug/Logging cleanup - 60+ prints eliminados | 0ed2973 |
| 2025-11-28 | Fase 2 | Constantes compartidas - constants.py creado, 4 archivos actualizados | ead73be |
| 2025-11-28 | Fase 6 | Limpieza código muerto - LEGACY_SOCKET_PATH, _pending, difflib imports, substr | c00c2bd |
| 2025-11-28 | Fase 3 | Handler extraction - 7 archivos creados, terminal.py reducido ~40% | 81edc75 |
| 2025-11-28 | Fase 4 | Refactor métodos largos - run_prompt (~65%), request_approval (~55%) | cd5dd6c |
| 2025-11-28 | Fase 5 | TypeScript types - approval.ts, type guards, helper functions | Pendiente |

