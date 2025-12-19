# AEGIS v1.0.0

**Agent Execution, Guidance & Inspection System**

AEGIS is a developer workstation that unifies code intelligence with AI agent orchestration. It provides comprehensive static analysis, automated quality pipelines, and embedded terminals for the leading AI coding assistants—all within a single, cohesive interface designed for professional software development workflows.

---

## The Problem

Modern software development involves constant context-switching: jumping between your IDE, terminal windows, documentation browsers, and AI chat interfaces. Developers lose valuable time navigating between tools, and critical insights about code structure remain scattered across disconnected systems.

AI coding agents have transformed how we write software, but running them effectively requires understanding your codebase deeply—knowing where complexity lives, which modules depend on each other, and where technical debt accumulates. Without this context, even the most capable AI assistant operates partially blind.

---

## The Solution

AEGIS bridges this gap by combining deep codebase analysis with seamless AI agent integration. It continuously analyzes your code, maintains a searchable symbol index, visualizes architectural relationships, and provides this intelligence directly alongside embedded terminals where AI agents operate.

The result: AI agents work with full context, developers maintain situational awareness, and code quality improves through automated, continuous feedback.

---

## Core Capabilities

### Comprehensive Code Analysis

AEGIS includes a multi-language static analysis engine that extracts meaningful structure from your codebase. The analyzer supports Python, JavaScript, TypeScript, HTML, and C/C++, parsing source files to identify classes, functions, methods, variables, and their relationships.

The symbol index enables instant search across projects of any size. Find function definitions, trace call hierarchies, and discover dependencies without leaving your workspace. The index updates automatically as files change, ensuring your view of the codebase remains current.

For architectural understanding, AEGIS generates interactive dependency graphs showing how modules relate to each other. Circular dependencies, tightly coupled components, and isolated modules become immediately visible. Class diagrams render inheritance hierarchies, composition relationships, and interface implementations in standard UML notation.

### Embedded AI Agent Terminals

AEGIS provides native terminal emulation with full PTY support for running AI coding agents directly within the application. Claude Code, Codex CLI, and Gemini CLI integrate seamlessly, with real-time bidirectional communication via Socket.IO.

Unlike browser-based terminal emulators, AEGIS terminals support the complete feature set these agents require: proper signal handling, environment variable inheritance, working directory management, and shell integration. The terminal maintains command history, supports multiple concurrent sessions, and displays agent-specific status indicators showing operation progress.

Each agent session operates with access to the same codebase intelligence AEGIS provides to developers. When an agent needs to understand project structure or locate specific symbols, that information is immediately available through the integrated analysis layer.

### Automated Quality Pipeline

Code quality requires continuous attention, not periodic reviews. AEGIS runs a configurable pipeline of industry-standard tools automatically as you work, providing immediate feedback without manual intervention.

The pipeline integrates ruff for fast Python linting and formatting validation, mypy for static type checking, bandit for security vulnerability detection, and pytest for test execution. Each tool runs incrementally when relevant files change, with results aggregated into a unified report interface.

Developers configure which tools to enable, set severity thresholds for notifications, and define exclusion patterns for generated code or vendored dependencies. The pipeline respects project-specific configuration files, ensuring consistency with existing CI/CD workflows.

Results display with full context: the exact line and column of each issue, the rule that triggered it, severity classification, and when available, suggested fixes. Filtering by file, severity, or tool type helps developers focus on what matters most.

### Code Similarity Detection

Duplicate code creates maintenance burden and introduces inconsistency risk. AEGIS includes a high-performance similarity detection engine written in C++ that identifies code clones across your entire codebase.

The engine uses tokenization and fingerprinting algorithms to find exact copies, near-duplicates with minor variations, and structurally similar code that might benefit from abstraction. Results highlight specific line ranges, similarity percentages, and potential refactoring opportunities.

For large codebases, the analysis runs in seconds rather than minutes, enabling integration into regular development workflows rather than occasional cleanup sessions.

### Local AI Insights

For teams requiring data privacy or operating in air-gapped environments, AEGIS integrates with Ollama to provide AI-powered code analysis using locally-hosted models. This capability is entirely optional and requires no external network access once configured.

The integration supports any Ollama-compatible model, with CodeLlama recommended for code-focused tasks. Developers can request complexity analysis, documentation suggestions, refactoring recommendations, and natural language explanations of code behavior—all processed locally on their own hardware.

---

## Architecture and Technology

AEGIS follows a client-server architecture optimized for responsiveness and extensibility.

### Backend

The backend is implemented in Python using FastAPI, providing an async HTTP and WebSocket server. The analysis layer uses tree-sitter for robust, incremental parsing of multiple languages, with custom analyzers handling language-specific semantics.

Persistent state uses SQLModel with SQLite for zero-configuration deployment, while the file watcher monitors the project directory for changes and schedules incremental re-analysis. The terminal subsystem provides PTY management on Unix systems via pexpect and ConPTY support on Windows via pywinpty.

The codebase comprises approximately 21,000 lines of Python across 50 modules, organized by functional area: analyzers, API endpoints, linter integration, terminal management, and external service connectors.

### Frontend

The frontend is a React application built with Vite for fast development iteration and optimized production builds. State management uses Zustand for predictable, minimal-boilerplate global state.

Terminal emulation relies on xterm.js, the same library powering VS Code's integrated terminal, ensuring compatibility with complex terminal applications and proper escape sequence handling. Visualization components use D3.js for dependency graphs and Graphviz via WASM for UML diagram rendering.

The frontend comprises approximately 22,000 lines of TypeScript and TSX across 80 components, with clear separation between presentational components, data fetching logic, and application state.

### Communication

The frontend and backend communicate via REST endpoints for request-response operations and Socket.IO for real-time bidirectional streaming. Terminal I/O, file change notifications, and analysis progress updates all flow through the Socket.IO connection, providing immediate feedback without polling overhead.

---

## Requirements

### For Local Mode (recommended for agents)

- Python 3.10+
- Node.js 18+
- At least one agent CLI installed: `claude`, `codex`, or `gemini`

### For Docker Mode

- Docker Engine 20.10+ or Docker Desktop
- Google Chrome or Chromium (for kiosk mode)

---

## Installation

### 1. Clone repository

```bash
git clone <repo-url> AEGIS
cd AEGIS
```

### 2. Backend (Python)

**Option A: Using uv (recommended - faster)**

```bash
# Install uv (if not installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies (creates venv automatically)
uv sync --all-extras
```

**Option B: Using pip (legacy)**

```bash
# Create virtual environment
python -m venv .venv

# Activate (Linux/macOS)
source .venv/bin/activate

# Activate (Windows)
.venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Frontend (Node.js)

```bash
cd frontend
npm install
cd ..
```

---

## Usage

### Option A: Local Mode (with agent support)

Use this mode if you need to run Claude, Codex, or Gemini.

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

Open http://localhost:5173 in your browser.

#### Useful commands

```bash
./start-local.sh              # Start backend + frontend
./start-local.sh --backend    # Backend only
./start-local.sh --stop       # Stop all
./start-local.sh --status     # Show status
```

---

### Option B: Docker Mode (without agents)

Use this mode for code analysis without running AI agents.

> **Note**: CLI agents (Claude/Codex/Gemini) do NOT work in Docker because they require host system access.

#### Linux/macOS

```bash
# Kiosk mode (fullscreen)
./start-app.sh

# Window mode
./start-app.sh --window

# Stop
./start-app.sh --stop
```

#### Windows

```cmd
REM Kiosk mode
start-app.bat

REM Stop
docker compose down
```

#### Manual Docker commands

```bash
# Build and start
docker compose up -d --build

# View logs
docker compose logs -f

# Stop
docker compose down

# Clean everything (including data)
docker compose down -v

# Rebuild without cache
docker compose build --no-cache
```

Open http://localhost:8080 in your browser.

---

## Configuration

AEGIS respects both environment variables and in-application settings, allowing deployment-time configuration without code changes.

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `CODE_MAP_ROOT` | Root directory to analyze | `$HOME` |
| `CODE_MAP_INCLUDE_DOCSTRINGS` | Include docstrings in analysis | `1` |
| `CODE_MAP_DISABLE_LINTERS` | Disable linter pipeline | `0` |
| `CODE_MAP_LINTERS_TOOLS` | Tools to execute | `ruff,mypy,bandit,pytest` |
| `CODE_MAP_OLLAMA_BASE_URL` | Ollama URL | - |
| `CODE_MAP_OLLAMA_MODEL` | Ollama model | `codellama` |

### Ollama (optional)

To enable local AI insights:

```bash
# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Download model
ollama pull codellama

# In docker-compose.yml, uncomment:
# - CODE_MAP_OLLAMA_BASE_URL=http://host.docker.internal:11434
# - CODE_MAP_OLLAMA_MODEL=codellama
```

---

## Project Structure

```
AEGIS/
├── code_map/           # FastAPI backend
│   ├── api/            # REST endpoints
│   ├── terminal/       # PTY + Socket.IO for agents
│   ├── linters/        # Linter pipeline
│   ├── integrations/   # Ollama, etc.
│   ├── analyzer.py     # Python analysis
│   ├── ts_analyzer.py  # TypeScript/JavaScript analysis
│   ├── c_analyzer.py   # C analysis
│   └── server.py       # FastAPI app
├── frontend/           # React + Vite UI
│   └── src/
│       ├── components/ # React components
│       └── stores/     # Zustand state
├── templates/          # Stage-Aware templates
├── docs/               # Additional documentation
├── start-local.sh      # Local mode launcher
├── start-app.sh        # Docker mode launcher
├── docker-compose.yml  # Docker configuration
├── pyproject.toml      # Python project config (uv/pip)
├── uv.lock             # Locked dependencies (uv)
└── requirements.txt    # Python dependencies (legacy)
```

---

## API

Once started, API documentation is available at:

- **Swagger UI**: http://localhost:8010/docs (local) or http://localhost:8080/docs (Docker)
- **ReDoc**: http://localhost:8010/redoc

### Main Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/tree` | File and symbol tree |
| `GET /api/files/{path}` | File details |
| `GET /api/search` | Symbol search |
| `GET /api/linters/report` | Latest linter report |
| `POST /api/linters/run` | Run linters |
| `GET /api/settings` | Current configuration |
| `WS /terminal/ws/{shell_id}` | PTY terminal (legacy) |
| `Socket.IO /socket.io/` | Socket.IO terminal |

---

## Troubleshooting

### Backend won't start

```bash
# Check if port is free
lsof -i :8010

# View logs
cat /tmp/aegis-backend.log
```

### Frontend can't connect to backend

```bash
# Check if backend responds
curl http://localhost:8010/api/settings

# Check environment variable
echo $VITE_DEPLOY_BACKEND_URL
```

### Docker: port in use

```bash
# Find process
sudo lsof -i :8080

# Change port in docker-compose.yml
ports:
  - "9000:8010"
```

### Agents not appearing

CLI agents must be installed and in PATH:

```bash
# Verify
which claude
which codex
which gemini
```

---

## Development

### Tests

```bash
# Backend (with uv)
uv run pytest

# Backend (with activated venv)
pytest

# Frontend
cd frontend && npm test
```

### Linting

```bash
# Backend (with uv)
uv run ruff check .
uv run mypy code_map/

# Backend (with activated venv)
ruff check .
mypy code_map/

# Frontend
cd frontend && npm run lint
```

### Package Management

```bash
# Add dependency (with uv)
uv add package-name

# Add dev dependency
uv add --dev package-name

# Update lockfile
uv lock

# Sync environment
uv sync --all-extras
```

---

## System Requirements

### Minimum Requirements

- Python 3.10 or later
- Node.js 18 or later
- 4 GB RAM
- 500 MB disk space for application and dependencies

### Recommended for Large Projects

- Python 3.11 or later for improved performance
- 8 GB RAM for projects exceeding 100,000 lines of code
- SSD storage for faster initial analysis

### Optional Components

- Claude Code, Codex CLI, or Gemini CLI for AI agent terminals
- Ollama for local AI insights
- Docker for container deployment

### Platform Support

- Linux: Full support including PTY terminals
- macOS: Full support including PTY terminals
- Windows: Full support with ConPTY terminals

---

## About the Project

AEGIS emerged from the practical need to maintain code quality while leveraging AI coding assistants effectively. It embodies the principle that AI and human developers work best as collaborators, each contributing their strengths: AI providing rapid generation and pattern application, humans providing judgment, context, and architectural vision.

The project follows an evolutionary development methodology, adding complexity only when justified by actual usage patterns. Version 1.0.0 represents a stable foundation suitable for daily professional use, with a clear roadmap for continued enhancement based on community feedback.

---

## License

AEGIS is released under the MIT License, permitting use, modification, and distribution in both open source and commercial projects without restriction.
