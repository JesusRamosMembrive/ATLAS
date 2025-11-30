# Audit Trail: Agent Monitoring Dashboard

## Objetivo (Actualizado 2025-11-23)
Transformar audit trail en **dashboard completo de monitoreo de agentes** con:
- 🖥️ Terminal en vivo mostrando comandos ejecutados
- 📊 Timeline visual de fases (Plan → Apply → Validate)
- 📝 Diffs en tiempo real con syntax highlighting
- 📤 Export para stakeholders no-técnicos
- 📈 Métricas de tiempo, LOC, costos

**Enfoque inicial**: Claude Code (extensible a Codex, Gemini, Ollama)
**Estrategia**: Captura híbrida (automática para comandos/diffs/git + manual para decisiones)

## Backend

### Almacenamiento (`code_map/audit/storage.py`) ✅
- Tablas SQLite `audit_runs` y `audit_events` (creación automática vía `open_database`)
- `create_run`, `close_run`, `append_event`, `list_runs`, `list_events`

### API REST (`code_map/api/audit.py`) ✅
- `POST /audit/runs` crea una sesión (campos: `name`, `notes`, `root_path?`)
- `GET /audit/runs?limit=` lista runs del workspace actual
- `GET /audit/runs/{id}` obtiene un run
- `POST /audit/runs/{id}/close` marca estado (default `closed`, soporta `status`, `notes`)
- `GET /audit/runs/{id}/events?limit=&after_id=` lista eventos en orden cronológico
- `POST /audit/runs/{id}/events` agrega evento (`type`, `title`, opcionales: `detail`, `actor`, `phase`, `status`, `ref`, `payload`)
- **Validación de workspace**: un run solo se puede leer/modificar si `root_path` coincide con el workspace activo

### Audit Hooks System (`code_map/audit/hooks.py`) ✅ NUEVO
Sistema de captura automática de eventos:

**`AuditContext`** - Context manager para tracking de bloques:
```python
with AuditContext(run_id=123, title="Analyze codebase", phase="plan"):
    # work here - automatically tracked
    pass
```

**`@audit_tracked`** - Decorator para funciones:
```python
@audit_tracked(event_type="command", phase="validate")
def run_tests():
    return subprocess.run(["pytest", "tests/"])
```

**`audit_run_command()`** - Wrapper de subprocess:
```python
result = audit_run_command(
    ["pytest", "tests/"],
    run_id=123,
    phase="validate"
)
# Auto-crea eventos: command (running) → command_result (ok/error)
```

**`audit_phase()`** - Context manager para fases:
```python
with audit_phase(run_id=123, phase_name="plan"):
    # Planning work - tracked with duration
    pass
```

### Integración con Linters ✅ NUEVO
`code_map/linters/pipeline.py` modificado:
- `run_linters_pipeline(audit_run_id=...)` acepta run_id
- Auto-detección de `ATLAS_AUDIT_RUN_ID` environment variable
- Cada linter tool ejecutado genera eventos automáticos
- Fallback graceful si audit no disponible

### Esquemas de eventos
- `type`: libre; sugeridos `intent`, `plan`, `command`, `command_result`, `diff`, `test`, `note`.
- `title`: etiqueta corta.
- `detail`: texto ampliado (stdout, diff resumido, reasoning).
- `actor`: `agent` o `human`.
- `phase`: `plan|apply|validate|explore`.
- `status`: `ok|error|pending|running|closed`.
- `ref`: archivo o recurso relacionado.
- `payload`: JSON estructurado (args, exit_code, paths, etc.).

## Frontend
- **Vista nueva**: `frontend/src/components/AuditSessionsView.tsx`, ruta `/audit`, tarjeta en Home y link en el header.  
  - Crea runs, cierra runs, lista eventos con filtros por tipo.  
  - Form para registrar eventos manuales (en espera de integrar hooks automáticos).  
  - Auto-refresco con React Query (polling corto).
- **Tipos/API**: `frontend/src/api/types.ts`, `frontend/src/api/client.ts`, `frontend/src/api/queryKeys.ts`.
- **Estilos**: `frontend/src/styles/audit.css`.

## Cómo usar ahora (manual)
1) Crear run: `POST /api/audit/runs` (`name`, `notes` opcional).  
2) Mientras trabajas, registra eventos: `POST /api/audit/runs/{id}/events` (usa `type`/`title` y añade `detail`, `ref`, `payload` si aplica).  
3) Al terminar: `POST /api/audit/runs/{id}/close` (opcional `status`, `notes`).  
4) Visualiza en `/audit` o consulta con `GET /api/audit/runs/{id}/events`.

## Roadmap de Desarrollo

### ✅ Fase 1 - Foundation (Semana 1) - 50% Completado
- [x] Audit hooks system (`code_map/audit/hooks.py`)
- [x] Linter pipeline integration
- [ ] Git operations auto-logging
- [ ] SSE event streaming endpoint
- [ ] Tests para audit hooks
- [ ] Frontend: useAuditEventStream hook
- [ ] Frontend: AuditSessionsView con SSE

### ⏳ Fase 2 - Terminal & Timeline (Semana 2)
- [ ] Agent bridge para Claude Code (`.claude/hooks/audit_bridge.py`)
- [ ] Terminal emulator component (xterm.js)
- [ ] Timeline visualization (Gantt chart)
- [ ] AgentMonitoringDashboard layout (3 columnas)

### ⏳ Fase 3 - Diffs en Tiempo Real (Semana 3)
- [ ] File watcher hook para diffs automáticos
- [ ] DiffViewer component (react-diff-view)
- [ ] Syntax highlighting (Prism.js)
- [ ] File tree navigation

### ⏳ Fase 4 - Export & Metrics (Semana 4)
- [ ] Export system (JSON/Markdown/HTML)
- [ ] MetricsPanel component
- [ ] Performance tracking (durations, LOC, costs)
- [ ] Analytics dashboard

## Notas de pruebas
- Test de API existente: `tests/test_api.py::test_audit_run_flow` (crea run, añade evento, cierra)
- Ejecutar: `pytest -k audit_run_flow`
- Pendiente: Tests para hooks system
