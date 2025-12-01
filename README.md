# ATLAS: Automated Tracing, Linting And Source-mapping

**Prevent over-engineering. Guide evolution. Analyze your code. Stay in control.**

A comprehensive toolkit combining:
1. **Stage-Aware Framework** - Evolutionary development methodology with automatic stage detection
2. **ATLAS Backend** - FastAPI service for code analysis, call tracing, and quality tooling

Automatically detects your project's maturity and provides deep insights into your codebase structure.

---

## 🎯 The Problem

**Development Challenges:**
- ✗ Too easy to over-engineer early prototypes
- ✗ AI suggests enterprise patterns for 100-line scripts
- ✗ Hard to understand complex codebases quickly
- ✗ Context loss between sessions breaks momentum
- ✗ Manual code analysis is time-consuming

## 💡 The Solution

### Stage-Aware Framework
Enforces evolutionary development through:
1. **Automatic Stage Detection** - Analyzes codebase and recommends Stage 1/2/3
2. **Stage-Specific Rules** - Prevents complexity until justified
3. **3-Phase Development Workflow** - Separates planning, implementation, and validation
4. **Specialized Subagents** - Architect, implementer, reviewer that understand stage context
5. **Session Continuity** - Tracking files preserve decisions and progress

#### 3-Phase Development Workflow

Projects initialized with ATLAS follow a structured workflow:

**Phase 1: Planning** (@architect, @stage-keeper)
- Design stage-appropriate architecture
- Select technology stack with rationale
- Create implementation roadmap
- **Output**: `.claude/doc/{feature}/architecture.md`

**Phase 2: Implementation** (@implementer)
- Execute architectural plan
- Track progress and document blockers
- **Output**: Code + `.claude/doc/{feature}/implementation.md`

**Phase 3: Validation** (@code-reviewer, @stage-keeper)
- Validate against plan
- Check security, correctness, stage compliance
- **Output**: `.claude/doc/{feature}/qa-report.md`

### ATLAS Backend
Provides deep code analysis via REST API:
1. **Call Tracing** - Track function calls within and across files
2. **Dependency Graphs** - Visualize module and class relationships
3. **Linter Pipeline** - Automated code quality checks (ruff, mypy, bandit, pytest)
4. **AI Insights** - Optional Ollama integration for code analysis
5. **Multi-Language Support** - Python, JavaScript/TypeScript, HTML

---

## 🚀 Quick Start

### Stage-Aware Framework

**New Project:**
```bash
# Initialize with stage-aware framework
python init_project.py my-new-project

# Claude only
python init_project.py my-new-project --agent=claude

# Codex only
python init_project.py my-new-project --agent=codex

# Preview without changes
python init_project.py my-new-project --dry-run

cd my-new-project
```

**Existing Project:**
```bash
# Add framework + auto-detect stage
python init_project.py --existing /path/to/project
```

**Check Stage Only:**
```bash
# Analyze without modifications
python init_project.py --detect-only /path/to/project
```

### ATLAS Backend

**Start the API server:**
```bash
# Run development server
python -m code_map.cli run --root /path/to/your/project

# Or using short form
python -m code_map --root /path/to/your/project

# Access API docs at: http://localhost:8010/docs
```

**Frontend (React UI):**
```bash
cd frontend
npm install  # or your package manager
npm run dev
# Access UI at: http://localhost:5173
```

**Environment Configuration:**
```bash
# API server
export CODE_MAP_HOST=0.0.0.0      # Default: 127.0.0.1
export CODE_MAP_PORT=8080          # Default: 8010

# Ollama integration (optional)
export OLLAMA_HOST=http://localhost:11434
```

---

## 📊 How It Works

### 1. Stage Detection

Analyzes your codebase:
- File count & lines of code
- Design patterns present
- Architecture complexity
- Directory structure

**Example output:**
```
📊 Recommended Stage: 2
✅ Confidence: HIGH

📈 Metrics:
  - Files: 15
  - LOC: ~2500
  - Patterns: Repository, Service

💡 Reasoning:
  • Medium codebase (15 files, ~2500 LOC)
  • Basic architecture: 3 layers
  • 📍 Mid Stage 2 - structure emerging
```

### 2. Stage Rules

Projects get `.claude/02-stageX-rules.md` files that Claude Code enforces:

**Stage 1 (Prototyping):**
- One file preferred
- No abstractions
- Hardcoded values OK
- Prove concept works

**Stage 2 (Structuring):**
- Multiple files when helpful
- Simple classes allowed
- 1-2 patterns max
- Add structure for real pain

**Stage 3 (Production):**
- Patterns appropriate
- Architecture matters
- Optimization justified
- Design for scale

### 3. Specialized Subagents

Four agents understand stage context:

- **architect** - Designs architecture appropriate for stage
- **implementer** - Writes code enforcing stage rules
- **code-reviewer** - Validates complexity matches stage
- **stage-keeper** - Documents framework itself

### 4. Session Tracking

Progress tracked in `.claude/01-current-phase.md`:
- What was implemented
- Decisions made and why
- What was deferred
- Next steps

Prevents context loss between Claude Code sessions.

---

## 🎓 Core Philosophy

### YAGNI with Evidence

**You Aren't Gonna Need It** - Until you prove you do.

- Stage 1: Prove the concept
- Stage 2: Add structure when refactoring hurts
- Stage 3: Scale when usage demands it

### Evolutionary Architecture

Don't design for scale at the start. Design to evolve easily.

### Maintain Control

AI executes. Human decides. Framework enforces.

---

## 📁 Project Structure

```
atlas/
├── init_project.py              # Stage framework CLI entry point
├── assess_stage.py              # Stage detection CLI
├── stage_config.py              # Detection algorithms
├── templates/                   # Project initialization templates
│   ├── basic/.claude/           # Tracking files, rules, subagents
│   └── docs/                    # Reference documentation
├── code_map/                    # FastAPI backend
│   ├── server.py                # Application factory
│   ├── call_tracer.py           # Single-file call tracing (Stage 1)
│   ├── call_tracer_v2.py        # Cross-file call tracing (Stage 2)
│   ├── import_resolver.py       # Python import resolution
│   ├── analyzer.py              # Python code parsing
│   ├── ts_analyzer.py           # TypeScript/JavaScript parsing
│   ├── html_analyzer.py         # HTML parsing
│   ├── linters/                 # Linter pipeline
│   │   ├── pipeline.py          # Orchestration
│   │   └── discovery.py         # Tool detection
│   ├── integrations/            # External services
│   │   └── ollama_service.py    # Ollama AI integration
│   └── api/                     # REST endpoints
│       ├── routes.py            # Main router
│       ├── analysis.py          # Code analysis
│       ├── tracer.py            # Call tracing
│       ├── linters.py           # Linter reports
│       └── stage.py             # Stage assessment
├── frontend/                    # React UI
│   └── src/
│       ├── components/
│       │   ├── CallTracerView.tsx    # Call tracing UI
│       │   ├── ClassUMLView.tsx      # UML visualization
│       │   └── DependencyGraph.tsx   # Dependency graph
│       └── App.tsx
└── tests/                       # Test suite
```

**After initializing a project:**
```
your-project/
├── .claude/
│   ├── 00-project-brief.md        # Scope
│   ├── 01-current-phase.md        # Progress + stage detection
│   ├── 02-stage1-rules.md         # Prototyping rules
│   ├── 02-stage2-rules.md         # Structuring rules
│   ├── 02-stage3-rules.md         # Production rules
│   └── subagents/                 # 4 specialized agents
├── docs/                          # Reference docs
└── CLAUDE.md                      # Project context
```

---

## 🔧 Commands Reference

### Stage Framework

**init_project.py:**
```bash
# New project
python init_project.py my-app

# Existing project (auto-detects stage)
python init_project.py --existing /path/to/project

# Detect only
python init_project.py --detect-only /path/to/project

# Preview without changes
python init_project.py my-app --dry-run

# Configure specific agent
python init_project.py my-app --agent=claude

# Verbose logging
python init_project.py --existing /path/to/project --log-level DEBUG
```

**assess_stage.py:**
```bash
# Detailed stage analysis
python assess_stage.py /path/to/project
```

**claude_assess.py:**
```bash
# Deep analysis with tree visualization
python claude_assess.py /path/to/project
```

### ATLAS Backend

**Run API server:**
```bash
# Start server
python -m code_map.cli run --root /path/to/project

# Custom host/port
python -m code_map.cli run --root . --host 0.0.0.0 --port 8080

# Enable auto-reload during development
python -m code_map.cli run --root . --reload
```

**API Endpoints:**
- `POST /api/tracer/analyze` - Single-file call graph
- `POST /api/tracer/analyze-cross-file` - Cross-file analysis with import resolution
- `POST /api/tracer/trace` - Trace call chain from function
- `POST /api/linters/run` - Execute linter pipeline
- `POST /api/stage/assess` - Assess project stage
- `GET /api/analysis/summary` - Code analysis summary
- Interactive docs: `http://localhost:8010/docs`

**→ Full documentation:** [USAGE.md](./USAGE.md) | [CLAUDE.md](./CLAUDE.md)

---

## 📚 Documentation

**Stage Framework:**
- **[USAGE.md](./USAGE.md)** - Complete usage guide with examples
- **[docs/QUICK_START.md](./docs/QUICK_START.md)** - Quick workflow guide
- **[docs/STAGE_CRITERIA.md](./docs/STAGE_CRITERIA.md)** - Detailed stage criteria
- **[docs/STAGES_COMPARISON.md](./docs/STAGES_COMPARISON.md)** - Side-by-side comparison

**ATLAS Backend:**
- **[CLAUDE.md](./CLAUDE.md)** - Architecture and development guide
- **API Docs** - Interactive Swagger UI at `/docs` when server is running

## ⚙️ Configuration

### Environment Variables

**API Server:**
```bash
CODE_MAP_HOST=0.0.0.0              # Default: 127.0.0.1
CODE_MAP_PORT=8080                 # Default: 8010
```

**Linter Pipeline:**
```bash
CODE_MAP_DISABLE_LINTERS=1                      # Skip linters entirely
CODE_MAP_LINTERS_TOOLS=ruff,pytest              # Limit to specific tools
CODE_MAP_LINTERS_MAX_PROJECT_FILES=2000         # Skip if too many files
CODE_MAP_LINTERS_MAX_PROJECT_SIZE_MB=200        # Skip if project too large
CODE_MAP_LINTERS_MIN_INTERVAL_SECONDS=300       # Minimum seconds between runs
```

**Ollama Integration (Optional):**
```bash
OLLAMA_HOST=http://localhost:11434  # Ollama server address
```

### Linter Configuration

The linter pipeline auto-discovers available tools:
- **ruff** - Fast Python linter
- **mypy** - Static type checker
- **bandit** - Security vulnerability scanner
- **pytest** - Test runner with coverage

Only installed tools are executed. Missing tools are gracefully skipped.

---

## 🎯 Use Cases

### For Individual Developers

Stop over-engineering side projects. Start simple, evolve with evidence.

### For Teams

Consistent development standards. Everyone works at appropriate complexity level.

### For Prototypes

Force simplicity. Prevent "production-ready" code for throwaway experiments.

### For Existing Projects

Assess current state. Get recommendation. Follow appropriate rules going forward.

---

## 🧪 Example: Stage Detection in Action

**Empty project → Stage 1:**
```bash
python init_project.py --existing my-new-idea
# Detected Stage 1 (0 files)
# Rule: One file, no abstractions
```

**After prototyping → Stage 2:**
```bash
python assess_stage.py my-new-idea
# Detected Stage 2 (8 files, 1200 LOC)
# Rule: Multiple files OK, 1-2 patterns
```

**In production → Stage 3:**
```bash
python assess_stage.py my-production-app
# Detected Stage 3 (35 files, 6000 LOC)
# Rule: Patterns appropriate, architect for scale
```

---

## ⚙️ Requirements

### Stage Framework (Core)
**Required:**
- Python 3.10+
- Standard library only (no external dependencies)

**Optional:**
- Claude Code CLI (`claude`) - For CLAUDE.md generation
- `tree` command - For project visualization

### ATLAS Backend
**Required:**
- Python 3.10+
- Dependencies: `pip install -r requirements.txt`
  - fastapi
  - pydantic
  - uvicorn
  - watchdog
  - typer

**Optional (for full features):**
- tree-sitter + tree-sitter-languages (multi-language AST parsing)
- beautifulsoup4 (HTML analysis)
- esprima (JavaScript parsing)
- Linter tools: ruff, mypy, bandit, pytest
- Ollama (AI-powered insights)

**Frontend:**
- Node.js 18+ (for React UI)
- npm/pnpm/yarn

---

## 🛠️ Installation

### Quick Setup

```bash
# Clone repository
git clone https://github.com/jesusramon/atlas
cd atlas

# Stage framework works immediately (no dependencies)
python init_project.py my-project
```

### Full Setup (Backend + Frontend)

```bash
# Install Python dependencies
pip install -r requirements.txt

# Install frontend dependencies
cd frontend
npm install  # or pnpm install / yarn install

# Optional: Install linter tools
pip install ruff mypy bandit pytest pytest-cov

# Optional: Install Ollama for AI insights
# https://ollama.ai/download
```

### Docker Setup (Desktop App Mode)

Docker mode runs ATLAS as a desktop-like application with kiosk mode browser.

> **Note:** Agent features (Claude/Codex/Gemini) do NOT work in Docker mode.
> Use `./start-local.sh` if you need agent functionality.

```bash
# Start in kiosk mode (fullscreen, no browser UI)
./start-app.sh

# Start in windowed mode (app-like window)
./start-app.sh --window

# Stop the container
./start-app.sh --stop

# Check container status
docker ps
```

The script automatically:
1. Starts the Docker container
2. Waits for the API to be ready
3. Opens the browser in kiosk/window mode

**Manual Docker commands (without browser launch):**
```bash
# Start container only
docker compose up -d

# View logs
docker logs -f code-map-app

# Stop container
docker compose down
```

### Local Setup (With Agent Support)

Local mode provides full agent CLI support (Claude, Codex, Gemini).

```bash
# Start backend + frontend + open browser
./start-local.sh

# Start backend only
./start-local.sh --backend

# Stop all servers
./start-local.sh --stop

# Check status
./start-local.sh --status
```

**Requirements for local mode:**
- Python venv: `.venv/` with dependencies installed
- Node.js: `frontend/node_modules/`
- Optional: `claude`, `codex`, or `gemini` CLI in PATH

**Environment variables:**
```bash
# Set project root (default: $HOME)
CODE_MAP_ROOT=/path/to/projects ./start-local.sh
```

**Logs:**
- Backend: `/tmp/atlas-backend.log`
- Frontend: `/tmp/atlas-frontend.log`

---

## 🔍 How Stage Detection Works

### Detection Algorithm

```python
# Stage 1: Prototyping
if files <= 3 and loc < 500:
    stage = 1

# Stage 2: Structuring
elif files <= 20 and loc < 3000 and patterns <= 3:
    stage = 2

# Stage 3: Production
else:
    stage = 3
```

Plus analysis of:
- Design patterns (Factory, Repository, Service, etc.)
- Architecture layers (models, services, controllers, etc.)
- Directory structure complexity

### Confidence Levels

- **High** - Clear indicators, trust the recommendation
- **Medium** - Borderline, manual review recommended
- **Low** - Conflicting signals, definitely review manually

---

## 🤝 Philosophy in Practice

### Real Example: API Development

**Week 1 (Stage 1):**
```python
# main.py - 150 lines
# All in one file, hardcoded, works
```

**Week 3 (Stage 2 - pain felt):**
```
api/
  routes.py      # Routes separated
  handlers.py    # Logic extracted
  models.py      # Data structures
  main.py        # Entry point
```

**Month 3 (Stage 3 - scale needed):**
```
api/
  routes/        # Route modules
  services/      # Business logic
  models/        # Data layer
  middleware/    # Cross-cutting
  tests/         # Comprehensive
```

**The framework prevents jumping to Month 3 structure in Week 1.**

---

## 📖 Background

This framework emerged from experience developing with Claude Code and other AI assistants.

**The pattern:** AI is incredibly helpful but tends toward over-engineering. It's easier to suggest a Repository pattern than to question if it's needed.

**The solution:** Explicit stage rules that AI must follow. Automatic detection of project maturity. Specialized subagents that understand context.

**The result:** Better software, faster. Simple when simple suffices. Complex when complexity is justified.

---

## 🎬 Next Steps

1. **Read [USAGE.md](./USAGE.md)** for complete guide
2. **Initialize a project** with `init_project.py`
3. **Check stage** of existing projects
4. **Use subagents** for stage-appropriate guidance
5. **Re-assess** after major changes

---

## 📊 Project Status

**Current Version:** 3.2 (ATLAS Integration)

**Recent Updates:**
- ✅ **v3.2** - Code quality improvements + ATLAS branding (XSS fix, refactoring, config)
- ✅ **v3.1** - Cross-file call tracing with import resolution
- ✅ **v3.0** - Stage detection + ATLAS backend integration
- ✅ **v2.5** - Integrated subagents
- ✅ **v2.0** - Stage-aware framework focus
- ✅ **v1.0** - Project initialization

**Key Features:**
- ✅ Automatic stage detection
- ✅ Call tracing (single-file + cross-file)
- ✅ Linter pipeline with auto-discovery
- ✅ React UI for visualization
- ✅ Multi-language support (Python, JS/TS, HTML)
- ✅ Ollama integration for AI insights
- ✅ REST API with OpenAPI docs

**Roadmap:**
- [ ] Stage 3 visual call graph (D3.js/ReactFlow)
- [ ] Export functionality (DOT, Mermaid, JSON)
- [x] Docker Compose deployment
- [ ] Stage transition validation
- [ ] Team collaboration features
- [ ] IDE integrations (VS Code extension)
- [ ] GitHub Action for PR analysis

---

## 🙋 FAQ

### Stage Framework

**Q: Do I have to follow the stages strictly?**
A: No. They're guides, not rules. Adapt to your context.

**Q: Can I customize stage rules?**
A: Yes. Edit `.claude/02-stageX-rules.md` files directly.

**Q: What if stage detection is wrong?**
A: Manual override: edit `01-current-phase.md` directly or re-run `assess_stage.py`.

**Q: Does this work without Claude Code?**
A: Yes. The framework works with any AI assistant or manual development.

**Q: What about non-Python projects?**
A: Fully supported. Detection works for Python, JavaScript/TypeScript, Java, Go, Rust, Ruby, PHP, C/C++, and more.

### ATLAS Backend

**Q: Can I use ATLAS without the stage framework?**
A: Yes. They're independent. Use the API server standalone for code analysis.

**Q: What languages does call tracing support?**
A: Currently Python only. JavaScript/TypeScript support is on the roadmap.

**Q: How does cross-file analysis work?**
A: Uses tree-sitter for AST parsing + custom import resolver to follow imports across files.

**Q: Is Ollama required?**
A: No. It's optional for AI-powered insights. All other features work without it.

**Q: Can I run this in CI/CD?**
A: Yes. The linter pipeline and stage detection work great in automated environments.

---

## 📝 License

MIT License - Use freely, commercially or personally.

---

## 🤝 Contributing

This project follows its own stage-aware methodology (currently Stage 3).

**Key areas for contribution:**

**Stage Framework:**
- Detection algorithm refinements
- New subagent types
- Stage rule improvements
- Language-specific criteria

**ATLAS Backend:**
- Additional language support (JS/TS call tracing)
- New analyzers (CSS, SQL, etc.)
- Performance optimizations
- UI/UX improvements
- Integration with more tools

**Process:**
1. Read `.claude/00-project-brief.md` and `.claude/01-current-phase.md`
2. Follow stage-specific rules in `.claude/02-stage3-rules.md`
3. Run tests: `pytest` (backend) and `npm test` (frontend)
4. Update documentation as needed

---

## 🏗️ Architecture Highlights

**Backend:**
- FastAPI for async REST API
- tree-sitter for multi-language AST parsing
- Graceful degradation (missing tools are skipped)
- MD5-based caching for performance
- Configurable via environment variables

**Frontend:**
- React 18 with TypeScript
- TanStack Query for data fetching
- ReactFlow for graph visualization
- Vite for fast development

**Security:**
- SVG sanitization to prevent XSS
- No shell=True in subprocess calls
- Path traversal protection
- Input validation via Pydantic

**Design Decisions:**
- Non-destructive initialization (preserves existing files)
- Stage detection with confidence levels
- Modular architecture (easy to extend)
- Self-documenting (CLAUDE.md, OpenAPI docs)

---

**Built with:** Python, FastAPI, React, YAGNI principles, and lessons from over-engineered prototypes.

**Philosophy:** "The best architecture is the one you add when you need it, not the one you designed when you didn't."

---

## 📞 Support

- **Issues:** [GitHub Issues](https://github.com/jesusramon/atlas/issues)
- **Discussions:** [GitHub Discussions](https://github.com/jesusramon/atlas/discussions)
- **Documentation:** This README + USAGE.md + CLAUDE.md

---

## 🎯 Why ATLAS?

**ATLAS** stands for **Automated Tracing, Linting And Source-mapping** - a fitting name for a tool that helps you navigate and understand your codebase, just like the mythological Atlas held up the celestial spheres.

The framework combines:
- **Tracing** - Follow function calls across your entire codebase
- **Linting** - Automated code quality checks and recommendations
- **Source-mapping** - Visualize dependencies, architectures, and relationships

Together with the Stage-Aware Framework, ATLAS ensures you build software that evolves deliberately, not accidentally.
