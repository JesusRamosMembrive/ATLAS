# Estado Actual del Proyecto

**Última actualización**: 2025-12-02
**Etapa detectada**: Stage 3 (Production-Ready)
**Proyecto**: AEGIS - Stage-Aware Development Framework + Code Map Backend

---

## ESTADO ACTUAL

**Completado (esta sesión):**
- ✅ **Windows Compatibility - Primera fase**
  - Imports condicionales para módulos Unix-only (pexpect, pty)
  - Soporte TCP sockets en Windows (reemplaza Unix sockets)
  - Rutas de búsqueda CLI cross-platform (claude, codex)
  - Endpoints PTY con fallback gracioso en Windows

**En progreso:**
- Completar testing de features avanzados en Windows

**Bloqueado/Pendiente:**
- tree_sitter_languages no compatible con Python 3.14

---

## ÚLTIMA SESIÓN: Windows Compatibility (2025-12-02)

### Resumen de Cambios

Se implementó la primera fase de compatibilidad con Windows:

### 1. Imports Condicionales ✅
- **`code_map/terminal/__init__.py`**
  - Detección de plataforma con `sys.platform`
  - Imports de PTYShell, PTYClaudeRunner solo en Unix
  - Variables `_IS_WINDOWS`, `_PTY_AVAILABLE` exportadas

### 2. Socket Server Cross-Platform ✅
- **`code_map/mcp/constants.py`**
  - `IS_WINDOWS` detection
  - TCP socket config para Windows (`tcp://127.0.0.1:18010`)
  - Unix socket path para Linux/macOS

- **`code_map/mcp/socket_server.py`**
  - Detección automática TCP vs Unix socket
  - `asyncio.start_server()` para Windows
  - `asyncio.start_unix_server()` para Unix

### 3. CLI Path Detection ✅
- **`code_map/terminal/claude_runner.py`**
  - Rutas Windows: `%APPDATA%\npm`, scoop shims
  - Rutas Unix: `~/.local/bin`, `/usr/local/bin`
  - `USERPROFILE` para home en Windows

- **`code_map/terminal/codex_runner.py`**
  - Mismo patrón cross-platform

### 4. API Endpoints con Fallback ✅
- **`code_map/api/terminal.py`**
  - `/ws` endpoint: Error gracioso en Windows
  - `/ws/agent-pty` endpoint: Error gracioso en Windows
  - `/ws/agent` endpoint: Funciona cross-platform

### 5. Dependencies ✅
- **`requirements.txt`**
  - `click>=8.0` añadido explícitamente
  - `pexpect` marcado como Unix-only
  - `tree_sitter` comentado (incompatible Python 3.14)

### Archivos Modificados

| Archivo | Cambios |
|---------|---------|
| `code_map/terminal/__init__.py` | Imports condicionales |
| `code_map/mcp/constants.py` | TCP socket config Windows |
| `code_map/mcp/socket_server.py` | TCP support |
| `code_map/terminal/claude_runner.py` | Windows CLI paths |
| `code_map/terminal/codex_runner.py` | Windows CLI paths |
| `code_map/api/terminal.py` | PTY fallback gracioso |
| `requirements.txt` | click, pexpect conditional |

---

## SESIÓN ANTERIOR: Claude Agent UI Improvements (2025-11-26)

### Resumen de Cambios

Se implementaron las fases 2-4 del Claude Agent JSON Streaming:

### Fase 2: UI Mejorada ✅
- **MarkdownRenderer** (`frontend/src/components/MarkdownRenderer.tsx`)
  - react-markdown + remark-gfm para GFM completo
  - prism-react-renderer con tema Night Owl
  - Números de línea en code blocks
  - Botón "Copy" con feedback visual ("Copied!")
  - Soporte: headers, listas, blockquotes, tablas, inline code

### Fase 3: Gestión de Sesión ✅
- **SessionHistoryStore** (`frontend/src/stores/sessionHistoryStore.ts`)
  - Zustand con persist middleware
  - localStorage con max 50 sesiones
  - Serialización Date <-> string
  - Auto-save debounced (1 segundo)

- **SessionHistorySidebar** (`frontend/src/components/SessionHistorySidebar.tsx`)
  - Toggle colapsable
  - Lista con título, preview, fecha, modelo
  - Cargar/eliminar sesiones
  - Botón "New Session" y "Clear All"

- **Continue Toggle** en header
  - Indica modo Continue (⟳) o Fresh (○)
  - Controla flag `--continue` de Claude Code

### Fase 4: Features Avanzados ✅
- **Token Tracking** en `claudeSessionStore.ts`
  - `totalInputTokens`, `totalOutputTokens`
  - Se acumulan de eventos con `usage`

- **Token Display** en header
  - Total tokens + costo estimado
  - Pricing Sonnet: $3/M input, $15/M output

- **Keyboard Shortcuts**
  - `Esc` - Cancelar operación
  - `Ctrl+L` - Limpiar mensajes
  - `Ctrl+Shift+N` - Nueva sesión
  - `/` - Enfocar input

- **Progress Indicator** mejorado
  - Barra animada con gradiente
  - Badge "Running X tools"
  - Hint "Press Esc to cancel"

### Archivos Creados

| Archivo | Descripción |
|---------|-------------|
| `frontend/src/components/MarkdownRenderer.tsx` | Markdown + syntax highlighting |
| `frontend/src/components/SessionHistorySidebar.tsx` | Sidebar historial |
| `frontend/src/stores/sessionHistoryStore.ts` | Store persistencia |

### Archivos Modificados

| Archivo | Cambios |
|---------|---------|
| `frontend/src/components/ClaudeAgentView.tsx` | Sidebar integration, shortcuts, token display, progress bar |
| `frontend/src/components/HeaderBar.tsx` | Añadido link "Agent" a navegación |
| `frontend/src/stores/claudeSessionStore.ts` | Token tracking (totalInputTokens, totalOutputTokens) |
| `docs/claude-agent-streaming.md` | Documentación actualizada con progreso fases |

### Commit
```
876cf33 Implements Claude Agent UI improvements (Phases 2-4)
```

---

## PRÓXIMOS PASOS

1. **Agent Monitoring Dashboard** (próximo):
   - Continuar con SSE endpoint
   - Frontend: useAuditEventStream hook

2. **Posibles mejoras futuras:**
   - System mode para theming (seguir preferencia del sistema)
   - Persistencia de preferencia de tema en localStorage (ya implementado)
   - Más tests E2E

---

## CONTEXTO CRÍTICO

**Restricciones importantes:**
- Stage-aware: No sobre-ingenierizar más allá del stage actual (Stage 3)
- YAGNI enforcement: Solo añadir features cuando hay dolor real 3+ veces
- Separation of concerns: Workflow docs (.claude/doc/) vs Code analysis (frontend)

**Patrones establecidos:**
- Templates en `templates/basic/.claude/` para nuevos proyectos
- Backend FastAPI con async/await en `code_map/`
- Frontend React + Zustand + TanStack Query en `frontend/src/`

**No hacer:**
- No modificar templates sin actualizar test_full_flow.sh
- No añadir features al frontend sin evidencia de pain point real
- No saltarse el workflow de 3 fases (Planning → Implementation → Validation)

---

## RECURSOS

- **Documentación técnica completa**: `docs/claude-agent-streaming.md`
- **Historial completo**: Ver `.claude/01-session-history.md`
- **Arquitectura 3-phase**: Ver `.claude/doc/README.md`

---

*Última sesión: 2025-11-26*
*Branch: develop*
