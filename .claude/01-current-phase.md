# Estado Actual del Proyecto

**Última actualización**: 2025-11-23
**Etapa detectada**: Stage 3 (Production-Ready)
**Proyecto**: ATLAS - Stage-Aware Development Framework + Code Map Backend

---

## 📍 ESTADO ACTUAL

**En progreso:**
- 🔥 **Agent Monitoring Dashboard** - Visión completa (4 semanas)
  - Fase 1 (Semana 1): Foundation - Audit hooks + SSE streaming (50% completado)
  - Terminal en vivo + Timeline visual + Diffs en tiempo real

**Completado recientemente:**
- ✅ Audit hooks system (`code_map/audit/hooks.py`)
- ✅ Linter pipeline integration con audit tracking
- ✅ Sistema de 3 fases (Architect → Implementer → Code-Reviewer)
- ✅ Frontend básico de Audit Sessions (manual)

**Bloqueado/Pendiente:**
- Ninguno actualmente

---

## 🎯 PRÓXIMOS PASOS

1. **Inmediato** (Continuar Fase 1):
   - Modificar git_history para auto-log operations
   - Añadir SSE endpoint para event streaming
   - Crear tests para audit hooks
   - Frontend: useAuditEventStream hook
   - Frontend: Actualizar AuditSessionsView para SSE

2. **Fase 2** (Semana 2):
   - Agent bridge para Claude Code
   - Terminal emulator (xterm.js)
   - Timeline visual (Gantt chart)

3. **Fase 3-4** (Semanas 3-4):
   - Diffs en tiempo real
   - Export system
   - Metrics dashboard

---

## 📝 DECISIONES RECIENTES

### Agent Monitoring Dashboard - Visión Completa (2025-11-23)
**Qué**: Transformar Audit Trail en dashboard completo de monitoreo de agentes en tiempo real
**Por qué**: Control total sobre Claude Code - ver comandos, diffs, timeline de fases, evitar dejarse seducir por potencia del agente
**Alcance**: 4 semanas, 3 features core (terminal vivo, timeline, diffs), enfoque inicial Claude Code
**Impacto**:
- Audit hooks system completo (`code_map/audit/hooks.py`)
- Linter pipeline auto-logging integrado
- SSE streaming para eventos en tiempo real (pendiente)
- Frontend dashboard con 3 columnas (terminal | timeline | diffs)

### Captura Híbrida de Eventos (2025-11-23)
**Qué**: Automática para diffs/git/tests + manual para intents/decisiones
**Por qué**: Balance entre automatización y control humano
**Implementación**:
- `audit_run_command()`: Wrapper de subprocess con auto-logging
- `AuditContext`: Context manager para bloques de trabajo
- `@audit_tracked`: Decorator para funciones
- Environment var `ATLAS_AUDIT_RUN_ID` para integración externa

---

## 🚨 CONTEXTO CRÍTICO

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

## 📚 RECURSOS

- **Historial completo**: Ver `.claude/01-session-history.md` (760+ líneas de contexto profundo)
- **Arquitectura 3-phase**: Ver `.claude/doc/README.md` para templates y guías
- **Documentación técnica**: Ver `docs/` para stage criteria, quick start, etc.
- **Templates actualizados**: `templates/basic/.claude/` con sistema compacto

---

## 🔄 ÚLTIMA SESIÓN

### Sesión 9: Agent Terminal Overlay - Fase 1 Completada (2025-11-25)

**Implementación completada:**
- ✅ **Parser de patrones de agente** (`code_map/terminal/agent_parser.py`)
  - Detecta 15+ tipos de eventos (comandos, tests, archivos, git, errores)
  - Extrae datos estructurados del output del terminal
  - Priorización de patrones para evitar duplicados

- ✅ **Sistema de eventos y estado de sesión** (`code_map/terminal/agent_events.py`)
  - AgentEventManager para gestión de sesión
  - Tracking de comandos, archivos, tests, métricas
  - Timeline y exportación de sesión

- ✅ **Integración en PTY Shell** (`code_map/terminal/pty_shell.py`)
  - Modo de parsing opcional con `enable_agent_parsing`
  - Callback para eventos detectados
  - Compatible con terminal existente

- ✅ **Protocolo WebSocket extendido** (`code_map/api/terminal.py`)
  - Comandos: `__AGENT__:enable/disable/summary`
  - Mensajes: `__AGENT__:event:{json}`, `__AGENT__:status:{enabled|disabled}`
  - Envío asíncrono de eventos al frontend

- ✅ **Tipos TypeScript** (`frontend/src/types/agent.ts`)
  - Definiciones completas de eventos, estado, métricas
  - Helpers para parsing de mensajes
  - Iconos y colores para UI

- ✅ **Store Zustand** (`frontend/src/stores/agentStore.ts`)
  - Gestión de estado de sesión del agente
  - Procesamiento de eventos en tiempo real
  - Timeline, métricas, getters útiles

- ✅ **UI en RemoteTerminalView** (`frontend/src/components/RemoteTerminalView.tsx`)
  - Botones para activar/desactivar modo agente
  - Parsing de mensajes del protocolo
  - Integración con agentStore

- ✅ **Tests completos** (`tests/test_agent_parser.py`)
  - 13 tests pasando, cobertura de todos los patterns
  - Validación de serialización y line tracking

**Arquitectura implementada:**
```
Terminal Output → PTY Shell → Parser → Events → WebSocket → Frontend → Store → UI
                                ↓                      ↓
                           Agent Events          Protocol Messages
```

**Próximos pasos (Fase 2 - Timeline UI):**
- [ ] Crear componente AgentOverlay para visualización
- [ ] Timeline vertical con estados y timestamps
- [ ] Status bar con fase actual
- [ ] Command widgets básicos (progress bars, test dashboard)

### Sesión 8: Fix Terminal Reconnection Bug (2025-11-24)

**Problema inicial identificado:**
- ❌ Terminal funciona en primera conexión, pero falla al recargar página
- ❌ Necesario reiniciar backend para recuperar funcionalidad
- 🔍 Root cause: Event loop reference capturada queda obsoleta tras reload, causando race condition

**Fixes aplicados (Backend):**
- ✅ **code_map/api/terminal.py** (modificado):
  - Validación de `loop.is_running()` antes de encolar output (líneas 61-65)
  - Mejorado orden de cleanup: shell.close() → sleep(0.1) → read_task.cancel() (líneas 142-146)
  - Agregado try-catch en inicialización de WebSocket para capturar errores silenciosos (líneas 32-53)
  - Previene intentos de encolar a event loop cerrado

- ✅ **code_map/terminal/pty_shell.py** (modificado):
  - Agregado `self.read_thread` como atributo de clase (línea 44)
  - Modificado método `read()` para almacenar referencia al thread (líneas 187-188)
  - Agregado `thread.join(timeout=0.5)` en `close()` (líneas 207-214)
  - Asegura terminación limpia de thread antes de liberar recursos

**Fixes aplicados (Frontend):**
- ✅ **frontend/src/main.tsx** (modificado):
  - Deshabilitado React StrictMode temporalmente (líneas 16-22)
  - StrictMode causa double-mount que cierra WebSocket antes de conectarse
  - Solo afecta desarrollo, producción no tiene StrictMode effects

- ✅ **frontend/src/components/RemoteTerminalView.tsx** (modificado - FIX FINAL):
  - **Root cause real**: Zustand persist middleware rehydration cambiaba `wsBaseUrl`, triggering useEffect cleanup
  - Agregado `prevUrlRef` para trackear URL anterior (línea 24)
  - Agregada lógica de skip en useEffect (líneas 134-141):
    - Si URL no cambió Y socket está OPEN o CONNECTING → skip reconnect
    - Previene cierre de WebSocket durante rehydration de Zustand
  - Debug logs mantienen visibilidad del comportamiento

**Solución final TanStack Query + Zustand:**
- ✅ Problema real: `useSettingsQuery()` en App.tsx actualizaba Zustand DESPUÉS de mount
- ✅ Secuencia del bug:
  1. Page load → `useSettingsQuery()` inicia (data: undefined)
  2. RemoteTerminalView mount → Lee `wsBaseUrl` desde Zustand (localStorage)
  3. useEffect crea WebSocket (state=CONNECTING)
  4. `useSettingsQuery()` completa → `{ data: { backend_url: "..." } }`
  5. App.tsx useEffect detecta cambio → `setBackendUrl()` → Actualiza Zustand
  6. Zustand update trigger RemoteTerminalView re-render → useEffect dependency change
  7. useEffect cleanup cierra WebSocket mientras state=0 (CONNECTING, code=1006)
  8. useEffect re-ejecuta, crea nuevo WebSocket
- ✅ Fix: `isInitializedRef` previene reconexión si socket ya está activo (OPEN o CONNECTING)
- ✅ Permite reconexión real cuando usuario cambia URL en settings

- ✅ **tests/test_terminal_reconnect.md** (nuevo):
  - Documentación completa del bug, fix y testing strategy
  - Manual de pruebas para validar reconexiones múltiples
  - Criterios de éxito y monitoreo de logs

**Decisiones técnicas:**
1. **Loop validation**: Prevenir encolado a loops obsoletos
2. **Cleanup order**: Shell → wait → task, evita race conditions
3. **Thread join**: Timeout de 0.5s para terminación explícita
4. **Logging mejorado**: Warnings para debugging de reconexiones

**Resultado esperado:**
- ✅ Recargas de página funcionan sin reiniciar backend
- ✅ Cleanup limpio de recursos (threads, shells, loops)
- ✅ Sin procesos zombie acumulados
- ✅ Sin errores en logs de encolado
- ✅ React Strict Mode no interfiere con conexiones

**Testing requerido ahora:**
- ✅ CRÍTICO: Usuario debe probar recarga de página (F5/Ctrl+R) para confirmar fix funciona
- Manual: Seguir procedimiento en `tests/test_terminal_reconnect.md`
- Validar: Recargas simples, recargas rápidas, múltiples tabs
- Monitorear: Logs de backend y procesos shell (ya no debería haber errores)

**Próxima sesión debe:**
- Si fix funciona: Remover debug print() statements del backend
- Si fix funciona: Continuar con Fase 1 del Agent Monitoring Dashboard
- Si persiste problema: Investigar más a fondo el comportamiento de React Strict Mode

---

**💡 Recordatorio**: Ver `.claude/01-session-history.md` y `docs/audit-trail.md` para contexto completo.