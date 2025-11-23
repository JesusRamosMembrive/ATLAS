# Audit Trail: Pair Programming Auditable

## Objetivo
Registrar, en tiempo real, cada paso de una sesión con el agente (intenciones, comandos, salidas, diffs, pruebas) y ofrecer una vista exportable que explique qué hizo el agente, por qué y cómo seguir.

## Backend
- **Almacenamiento** (`code_map/audit/storage.py`):  
  - Tablas SQLite `audit_runs` y `audit_events` (creación automática vía `open_database`).  
  - `create_run`, `close_run`, `append_event`, `list_runs`, `list_events`.
- **Rutas FastAPI** (`/api/audit/*`, ver `code_map/api/audit.py`):  
  - `POST /audit/runs` crea una sesión (campos: `name`, `notes`, `root_path?`).  
  - `GET /audit/runs?limit=` lista runs del workspace actual.  
  - `GET /audit/runs/{id}` obtiene un run.  
  - `POST /audit/runs/{id}/close` marca estado (default `closed`, soporta `status`, `notes`).  
  - `GET /audit/runs/{id}/events?limit=&after_id=` lista eventos en orden cronológico.  
  - `POST /audit/runs/{id}/events` agrega evento (`type`, `title`, opcionales: `detail`, `actor`, `phase`, `status`, `ref`, `payload`).
- **Validación de workspace**: un run solo se puede leer/modificar si `root_path` coincide con el workspace activo.

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

## Integración pendiente (hooks automáticos)
- Envolver el executor de comandos/patches/tests para enviar eventos tipo `command`/`command_result` (con `exit_code`, `stdout_excerpt`), `diff` (paths y resumen), `test` (suite, resultado).  
- Enlazar planificador/“stage runner” para emitir `intent`/`plan`/`phase change`.  
- Añadir export a JSON/Markdown desde la UI para compartir con managers.

## Notas de pruebas
- Test de API añadido en `tests/test_api.py::test_audit_run_flow` (crea run, añade evento, cierra). Ejecutar con `pytest -k audit_run_flow`.
