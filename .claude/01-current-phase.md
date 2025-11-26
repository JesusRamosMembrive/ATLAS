# Estado Actual del Proyecto

**Última actualización**: 2025-11-26
**Etapa detectada**: Stage 3 (Production-Ready)
**Proyecto**: ATLAS - Stage-Aware Development Framework + Code Map Backend

---

## ESTADO ACTUAL

**Completado (esta sesión):**
- ✅ **Claude Agent JSON Streaming** - Nueva página `/agent` con UI estructurada
  - Reemplaza el problemático terminal PTY para Claude Code
  - Usa `claude -p --output-format stream-json` para output estructurado
  - Backend WebSocket + Frontend React completamente funcional

**En progreso:**
- 🔥 **Agent Monitoring Dashboard** - Visión completa (4 semanas)
  - Fase 1 (Semana 1): Foundation - Audit hooks + SSE streaming (50% completado)
  - Terminal en vivo + Timeline visual + Diffs en tiempo real

**Bloqueado/Pendiente:**
- Ninguno actualmente

---

## ÚLTIMA SESIÓN: Claude Agent JSON Streaming (2025-11-26)

### Problema Resuelto
El terminal PTY para Claude Code tenía problemas:
- Claude Code emitía raw line breaks haciendo el agente inmanejable desde shell
- El botón Send enviaba comandos con line breaks extra

### Solución Implementada
Nueva página `/agent` que usa JSON streaming en lugar de TUI:

```
claude -p --output-format stream-json --verbose "prompt"
```

### Archivos Creados/Modificados

#### Backend (Python)
| Archivo | Tipo | Descripción |
|---------|------|-------------|
| `code_map/terminal/claude_runner.py` | NUEVO | Async subprocess runner para Claude Code |
| `code_map/terminal/json_parser.py` | NUEVO | Parser de eventos JSON línea por línea |
| `code_map/terminal/__init__.py` | MODIFICADO | Exports actualizados |
| `code_map/api/terminal.py` | MODIFICADO | Añadido endpoint `/ws/agent` |

#### Frontend (TypeScript/React)
| Archivo | Tipo | Descripción |
|---------|------|-------------|
| `frontend/src/types/claude-events.ts` | NUEVO | Tipos TypeScript para eventos Claude |
| `frontend/src/stores/claudeSessionStore.ts` | NUEVO | Zustand store para sesión |
| `frontend/src/components/ClaudeAgentView.tsx` | NUEVO | Componente UI principal |
| `frontend/src/App.tsx` | MODIFICADO | Ruta `/agent` añadida |
| `frontend/src/components/HomeView.tsx` | MODIFICADO | Card de navegación añadida |

### Arquitectura

```
┌─────────────────────────────────────────────────────────────┐
│                     Frontend (React)                         │
│  ┌─────────────────┐  ┌──────────────────────────────────┐  │
│  │ ClaudeAgentView │◄─┤ claudeSessionStore (Zustand)     │  │
│  │   - Messages    │  │   - WebSocket connection         │  │
│  │   - Tool Cards  │  │   - Message processing           │  │
│  │   - Input       │  │   - Tool call tracking           │  │
│  └─────────────────┘  └──────────────────────────────────┘  │
└─────────────────────────────┬───────────────────────────────┘
                              │ WebSocket
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     Backend (FastAPI)                        │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ /api/terminal/ws/agent                                  ││
│  │   - Recibe prompts del frontend                         ││
│  │   - Spawns claude subprocess                            ││
│  │   - Streams parsed JSON events                          ││
│  └─────────────────────────────────────────────────────────┘│
│  ┌─────────────────┐  ┌──────────────────────────────────┐  │
│  │ ClaudeRunner    │  │ JSONStreamParser                 │  │
│  │   - subprocess  │──┤   - Parse line-by-line JSON      │  │
│  │   - async I/O   │  │   - Typed events                 │  │
│  └─────────────────┘  └──────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     Claude Code CLI                          │
│  claude -p --output-format stream-json --verbose "prompt"   │
└─────────────────────────────────────────────────────────────┘
```

### Protocolo WebSocket

**Endpoint:** `ws://localhost:8010/api/terminal/ws/agent`

**Cliente envía:**
```json
{"command": "run", "prompt": "tu prompt aquí", "continue": true}
```

**Servidor envía (streaming, uno por línea):**
```json
{"type": "system", "subtype": "init", "session_id": "...", "model": "..."}
{"type": "assistant", "subtype": "text", "content": "respuesta"}
{"type": "assistant", "subtype": "tool_use", "tool_name": "...", "tool_input": {...}}
{"type": "result", "subtype": "success", "duration_ms": 1234}
{"type": "done"}
```

### Tipos de Eventos

| Tipo | Subtipo | Descripción |
|------|---------|-------------|
| `system` | `init` | Inicio de sesión con session_id y model |
| `assistant` | `text` | Respuesta de texto |
| `assistant` | `tool_use` | Uso de herramienta (Read, Edit, Bash, etc.) |
| `user` | `tool_result` | Resultado de herramienta |
| `result` | `success`/`error` | Fin de operación con métricas |
| `done` | - | Marca fin del stream |

### Cómo Probar

1. **Iniciar Backend:**
```bash
cd /home/jesusramos/Workspace/ATLAS
python -m code_map.cli run --root .
# Corre en http://localhost:8010
```

2. **Iniciar Frontend:**
```bash
cd /home/jesusramos/Workspace/ATLAS/frontend
npm run dev
# Corre en http://localhost:5173
```

3. **Navegar a Agent:**
Abrir `http://localhost:5173/agent`

4. **Probar interacción:**
- Escribir prompt (ej: "What is 2+2?")
- Click Send o Ctrl+Enter
- Ver respuestas estructuradas aparecer

### Test Solo Backend (sin frontend)
```bash
python3 -c "
import asyncio
import websockets
import json

async def test():
    uri = 'ws://localhost:8010/api/terminal/ws/agent'
    async with websockets.connect(uri) as ws:
        await ws.send(json.dumps({'command': 'run', 'prompt': 'What is 2+2?'}))
        while True:
            msg = await ws.recv()
            data = json.loads(msg)
            print(json.dumps(data, indent=2))
            if data.get('type') == 'done':
                break

asyncio.run(test())
"
```

### Decisiones Técnicas

1. **Ruta separada `/agent`** en lugar de modificar terminal existente - mantiene shell intacto
2. **Zustand sobre Redux** - gestión de estado más simple para este caso
3. **Estilos inline en componente** - iteración rápida, extraer a CSS modules después
4. **WebSocket sobre HTTP polling** - streaming real-time es esencial
5. **JSON línea por línea** - Claude output es objetos JSON independientes, no array

### Fases Futuras

**Fase 2: UI Mejorada**
- [ ] Renderizado markdown para respuestas
- [ ] Syntax highlighting para código
- [ ] Botones de copiar código
- [ ] Mejorar estilos de tool cards

**Fase 3: Gestión de Sesión**
- [ ] Implementar flag `--continue` para continuidad
- [ ] Sidebar de historial de sesiones
- [ ] Opción de limpiar/resetear sesión

**Fase 4: Features Avanzados**
- [ ] Botón cancelar (kill subprocess)
- [ ] Animación de texto streaming
- [ ] Display de costo/tokens
- [ ] Atajos de teclado

**Fase 5: Polish**
- [ ] Estados de loading
- [ ] UI de manejo de errores
- [ ] Lógica de reconexión
- [ ] Diseño responsive móvil

### Issues Conocidos

1. **Warning de bundle grande:** Frontend ~875KB. Considerar code-splitting.
2. **Sin botón cancelar:** Si Claude tarda mucho, necesita subprocess kill.
3. **Sin persistencia de sesión:** Cada refresh de página inicia nueva sesión.

---

## PRÓXIMOS PASOS

1. **Inmediato** (Testing):
   - Probar integración completa frontend-backend
   - Verificar que tool cards se muestran correctamente
   - Probar con prompts que usen herramientas

2. **Siguiente** (Mejoras UI):
   - Añadir markdown rendering
   - Añadir syntax highlighting
   - Mejorar estilos visuales

3. **Después** (Agent Monitoring Dashboard - Fase 1):
   - Continuar con SSE endpoint
   - Crear tests para audit hooks
   - Frontend: useAuditEventStream hook

---

## CONTEXTO CRÍTICO

**Restricciones importantes:**
- Stage-aware: No sobre-ingenierizar más allá del stage actual (Stage 3)
- YAGNI enforcement: Solo añadir features cuando hay dolor real 3+ veces
- Separation of concerns: Workflow docs (.claude/doc/) vs Code analysis (frontend)

**Patrones establecidos:**
- Templates en `templates/basic/.claude/` para nuevos proyectos
- Backend FastAPI con async/await en `code_map/`
- Frontend React + TanStack Query en `frontend/src/`
- Agents en `.claude/subagents/` con 3-phase coordination

**No hacer:**
- No modificar templates sin actualizar test_full_flow.sh
- No añadir features al frontend sin evidencia de pain point real
- No saltarse el workflow de 3 fases (Planning → Implementation → Validation)
- No mantener 01-current-phase.md >150 líneas (mover a historial)

---

## RECURSOS

- **Historial completo**: Ver `.claude/01-session-history.md`
- **Arquitectura 3-phase**: Ver `.claude/doc/README.md`
- **Documentación técnica**: Ver `docs/`
- **Templates actualizados**: `templates/basic/.claude/`

---

*Última sesión: 2025-11-26*
*Branch: develop*
