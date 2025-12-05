# Estado Actual del Proyecto

**Última actualización**: 2025-12-05
**Etapa detectada**: Stage 3 (High Confidence)
**Versión**: 1.2

---

## 📍 ESTADO ACTUAL

**Completado:**
- ✅ Migración completa de terminal a Socket.IO (basada en pyxtermjs)
- ✅ Eliminado código WebSocket legacy del frontend
- ✅ Simplificado RemoteTerminalView (solo Socket.IO)
- ✅ Corregido problema de escritura en TerminalSocketIO (listener closure fix)

**Archivos modificados:**
- `code_map/terminal/socketio_pty.py`: Servidor PTY con Socket.IO
- `code_map/server.py`: Integración Socket.IO con FastAPI vía ASGI
- `frontend/src/components/TerminalSocketIO.tsx`: Componente React con socket.io-client (corregido onData listener)
- `frontend/src/components/RemoteTerminalView.tsx`: Solo Socket.IO, sin toggle
- `frontend/src/components/ClaudeAgentView.tsx`: Usa TerminalSocketIO para Codex/Gemini
- `ELIMINADO: frontend/src/components/TerminalEmbed.tsx` (WebSocket legacy)

**Pendiente de pruebas:**
- Probar terminal con `gemini` CLI para validar que no hay saltos de línea
- Probar terminal con `codex` CLI

---

## 🎯 PRÓXIMOS PASOS

1. **Inmediato** (Esta sesión):
   - ✅ Migrar terminal a Socket.IO
   - ✅ Eliminar WebSocket legacy del frontend
   - Probar con `gemini` CLI para validar funcionamiento

2. **Corto plazo** (Próximas 1-3 sesiones):
   - Documentar la arquitectura Socket.IO
   - Considerar eliminar endpoint WebSocket legacy del backend (mantenerlo como fallback por ahora)

3. **Mediano plazo** (Cuando sea necesario):
   - Soporte Windows con ConPTY + Socket.IO

---

## 📝 DECISIONES RECIENTES

### Migración a Socket.IO (2025-12-05)
**Qué**: Reemplazar WebSocket nativo por python-socketio + socket.io-client
**Por qué**: pyxtermjs usa este patrón y funciona perfectamente con agentes TUI. La diferencia clave:
- Buffer 20KB (vs 1KB) para escape sequences
- Eventos tipados (pty-input, pty-output, resize)
- Debounce 50ms (vs 200ms)
- Reconexión automática
**Impacto**:
- Backend: `socketio_pty.py`, `server.py`, `cli.py`
- Frontend: `TerminalSocketIO.tsx`, `RemoteTerminalView.tsx`
- Deps: `python-socketio[asyncio]`, `socket.io-client`

---

## 🚨 CONTEXTO CRÍTICO

**Restricciones importantes:**
- [Constraint #1 que afecta decisiones de diseño]
- [Constraint #2]

**Patrones establecidos:**
- [Patrón #1 que debe seguirse en nuevo código]
- [Patrón #2]

**No hacer:**
- [Anti-patrón o decisión explícitamente rechazada]

---

## 📚 RECURSOS

- **Historial completo**: Ver `.claude/01-session-history.md` para contexto profundo
- **Arquitectura**: Ver `docs/{feature}/architecture.md` para planes detallados
- **Documentación**: Ver `docs/` para guías técnicas

---

## 🔄 TEMPLATE DE ACTUALIZACIÓN

**Al final de cada sesión, actualiza esta sección:**

```markdown
## Sesión: [YYYY-MM-DD]

**Implementado:**
- [Archivo]: [Cambio específico]
- [Archivo]: [Cambio específico]

**Decisiones:**
- [Decisión técnica tomada y por qué]

**Próxima sesión debe:**
- [Acción prioritaria #1]
- [Acción prioritaria #2]

**Movido a historial:** ✅ (Copiar detalle completo a 01-session-history.md)
```

---

**💡 TIP**: Mantén este archivo <150 líneas. Mueve detalles antiguos a `01-session-history.md` regularmente.

## 🎯 Detected Stage: Stage 3 (High Confidence)

**Auto-detected on:** 2025-12-03 17:47

**Detection reasoning:**
- Large or complex codebase (221 files, ~57384 LOC)
- Multiple patterns detected: Factory Pattern, Repository, Service Layer

**Metrics:**
- Files: 221
- LOC: ~57384
- Patterns: Factory Pattern, Repository, Service Layer

**Recommended actions:**
- Follow rules in `.claude/02-stage3-rules.md`
- Use stage-aware agents for guidance
- Re-assess stage after significant changes