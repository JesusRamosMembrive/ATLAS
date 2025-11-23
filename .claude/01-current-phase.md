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

### Sesión 7: Agent Monitoring Dashboard - Fase 1 Inicio (2025-11-23)

**Implementado:**
- ✅ **code_map/audit/hooks.py** (330 líneas): Sistema completo de audit hooks
  - `AuditContext`: Context manager para tracking de bloques
  - `@audit_tracked`: Decorator para auto-tracking de funciones
  - `audit_run_command()`: Wrapper de subprocess con eventos automáticos
  - `audit_phase()`: Context manager para fases (plan/apply/validate)

- ✅ **code_map/linters/pipeline.py** (modificado): Integración con audit
  - Modificado `_execute_tool()` para usar `audit_run_command()` cuando `audit_run_id` presente
  - Modificado `run_linters_pipeline()` para aceptar y propagar `audit_run_id`
  - Auto-detección de `ATLAS_AUDIT_RUN_ID` desde environment variables
  - Fallback graceful si audit module no disponible

**Decisiones:**
- Hooks system como foundation para captura automática
- Environment-based activation (`ATLAS_AUDIT_RUN_ID`)
- Graceful degradation si audit no está habilitado

**Próxima sesión debe:**
- Continuar Fase 1: git_history integration, SSE endpoint, tests
- Mantener momentum hacia dashboard completo

---

**💡 Recordatorio**: Ver `.claude/01-session-history.md` y `docs/audit-trail.md` para contexto completo.