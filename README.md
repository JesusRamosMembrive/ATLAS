# AEGIS

**Agent Execution, Guidance & Inspection System**

Sistema de análisis de código y ejecución de agentes AI (Claude, Codex, Gemini) con interfaz web.

---

## Qué es AEGIS

AEGIS es una aplicación de escritorio que combina:

- **Code Map**: Análisis estático de código (Python, JS/TS, HTML, C) con visualización de símbolos, dependencias y grafos de clases
- **Terminal de Agentes**: Ejecuta Claude Code, Codex CLI o Gemini CLI en terminales embebidas con Socket.IO
- **Pipeline de Linters**: Ejecuta ruff, mypy, bandit y pytest automáticamente
- **Integración Ollama**: Insights de código con modelos locales (opcional)

---

## Requisitos

### Para modo local (recomendado para agentes)

- Python 3.10+
- Node.js 18+
- Al menos un agente CLI instalado: `claude`, `codex`, o `gemini`

### Para modo Docker

- Docker Engine 20.10+ o Docker Desktop
- Google Chrome o Chromium (para modo kiosk)

---

## Instalación

### 1. Clonar repositorio

```bash
git clone <repo-url> AEGIS
cd AEGIS
```

### 2. Backend (Python)

```bash
# Crear entorno virtual
python -m venv .venv

# Activar (Linux/macOS)
source .venv/bin/activate

# Activar (Windows)
.venv\Scripts\activate

# Instalar dependencias
pip install -r requirements.txt
```

### 3. Frontend (Node.js)

```bash
cd frontend
npm install
cd ..
```

---

## Uso

### Opción A: Modo Local (con soporte de agentes)

Usa este modo si necesitas ejecutar Claude, Codex o Gemini.

#### Linux/macOS

```bash
./start-local.sh
```

#### Windows

```powershell
# Terminal 1: Backend
.venv\Scripts\activate
uvicorn code_map.server:app --host 0.0.0.0 --port 8010 --reload

# Terminal 2: Frontend
cd frontend
npm run dev
```

Abre http://localhost:5173 en tu navegador.

#### Comandos útiles

```bash
./start-local.sh              # Inicia backend + frontend
./start-local.sh --backend    # Solo backend
./start-local.sh --stop       # Detiene todo
./start-local.sh --status     # Muestra estado
```

---

### Opción B: Modo Docker (sin agentes)

Usa este modo para análisis de código sin ejecutar agentes AI.

> **Nota**: Los agentes CLI (Claude/Codex/Gemini) NO funcionan en Docker porque requieren acceso al sistema host.

#### Linux/macOS

```bash
# Modo kiosk (pantalla completa)
./start-app.sh

# Modo ventana
./start-app.sh --window

# Detener
./start-app.sh --stop
```

#### Windows

```cmd
REM Modo kiosk
start-app.bat

REM Detener
docker compose down
```

#### Comandos Docker manuales

```bash
# Construir e iniciar
docker compose up -d --build

# Ver logs
docker compose logs -f

# Detener
docker compose down

# Limpiar todo (incluyendo datos)
docker compose down -v

# Rebuild sin cache
docker compose build --no-cache
```

Abre http://localhost:8080 en tu navegador.

---

## Configuración

### Variables de entorno

| Variable | Descripción | Default |
|----------|-------------|---------|
| `CODE_MAP_ROOT` | Directorio raíz a analizar | `$HOME` |
| `CODE_MAP_INCLUDE_DOCSTRINGS` | Incluir docstrings en análisis | `1` |
| `CODE_MAP_DISABLE_LINTERS` | Deshabilitar pipeline de linters | `0` |
| `CODE_MAP_LINTERS_TOOLS` | Herramientas a ejecutar | `ruff,mypy,bandit,pytest` |
| `CODE_MAP_OLLAMA_BASE_URL` | URL de Ollama | - |
| `CODE_MAP_OLLAMA_MODEL` | Modelo de Ollama | `codellama` |

### Ollama (opcional)

Para habilitar insights con AI local:

```bash
# Instalar Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Descargar modelo
ollama pull codellama

# En docker-compose.yml, descomentar:
# - CODE_MAP_OLLAMA_BASE_URL=http://host.docker.internal:11434
# - CODE_MAP_OLLAMA_MODEL=codellama
```

---

## Estructura del proyecto

```
AEGIS/
├── code_map/           # Backend FastAPI
│   ├── api/            # Endpoints REST
│   ├── terminal/       # PTY + Socket.IO para agentes
│   ├── linters/        # Pipeline de linters
│   ├── integrations/   # Ollama, etc.
│   ├── analyzer.py     # Análisis Python
│   ├── ts_analyzer.py  # Análisis TypeScript/JavaScript
│   ├── c_analyzer.py   # Análisis C
│   └── server.py       # App FastAPI
├── frontend/           # UI React + Vite
│   └── src/
│       ├── components/ # Componentes React
│       └── stores/     # Estado Zustand
├── templates/          # Templates Stage-Aware
├── docs/               # Documentación adicional
├── start-local.sh      # Launcher modo local
├── start-app.sh        # Launcher modo Docker
├── docker-compose.yml  # Configuración Docker
└── requirements.txt    # Dependencias Python
```

---

## API

Una vez iniciado, la documentación de la API está disponible en:

- **Swagger UI**: http://localhost:8010/docs (local) o http://localhost:8080/docs (Docker)
- **ReDoc**: http://localhost:8010/redoc

### Endpoints principales

| Endpoint | Descripción |
|----------|-------------|
| `GET /api/tree` | Árbol de archivos y símbolos |
| `GET /api/files/{path}` | Detalle de un archivo |
| `GET /api/search` | Búsqueda de símbolos |
| `GET /api/linters/report` | Último reporte de linters |
| `POST /api/linters/run` | Ejecutar linters |
| `GET /api/settings` | Configuración actual |
| `WS /terminal/ws/{shell_id}` | Terminal PTY (legacy) |
| `Socket.IO /socket.io/` | Terminal Socket.IO |

---

## Solución de problemas

### Backend no arranca

```bash
# Verificar que el puerto está libre
lsof -i :8010

# Ver logs
cat /tmp/aegis-backend.log
```

### Frontend no conecta al backend

```bash
# Verificar que backend responde
curl http://localhost:8010/api/settings

# Verificar variable de entorno
echo $VITE_DEPLOY_BACKEND_URL
```

### Docker: puerto en uso

```bash
# Encontrar proceso
sudo lsof -i :8080

# Cambiar puerto en docker-compose.yml
ports:
  - "9000:8010"
```

### Agentes no aparecen

Los agentes CLI deben estar instalados y en el PATH:

```bash
# Verificar
which claude
which codex
which gemini
```

---

## Desarrollo

### Tests

```bash
# Backend
pytest

# Frontend
cd frontend && npm test
```

### Linting

```bash
# Backend
ruff check .
mypy code_map/

# Frontend
cd frontend && npm run lint
```

---

## Licencia

MIT
