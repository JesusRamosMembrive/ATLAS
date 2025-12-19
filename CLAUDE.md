# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Project Overview

This repository contains **two integrated systems**:

### 1. Stage-Aware Development Framework
CLI tools for evolutionary software development that prevent over-engineering:
- `init_project.py` - Initialize projects with `.claude/` tracking structure
- `assess_stage.py` - Analyze codebases and recommend Stage 1/2/3
- `stage_config.py` - Core stage detection algorithms and thresholds
- `stage_init/` - Modular initialization logic (CLI, templates, updaters)

### 2. Code Map Backend
FastAPI service for code analysis and quality tooling:
- `code_map/server.py` - FastAPI application factory
- `code_map/analyzer.py` - Multi-language code parsing (Python, JS/TS, HTML)
- `code_map/linters/pipeline.py` - Automated linter execution (ruff, mypy, bandit, pytest)
- `code_map/integrations/ollama_service.py` - AI-powered code insights via Ollama
- `code_map/api/` - REST endpoints for analysis, graphs, linters, settings

---

## Commands Reference

### Stage-Aware Framework

```bash
# Initialize new project
python init_project.py my-new-project

# Add framework to existing project (with auto-detection)
python init_project.py --existing /path/to/project

# Detect project stage only
python assess_stage.py /path/to/project
# OR
python init_project.py --detect-only /path/to/project

# Preview changes without writing
python init_project.py my-project --dry-run

# Configure for specific agent (claude, codex, or both)
python init_project.py my-project --agent=claude
```

### Code Map Backend

```bash
# Run development server (with uv - recommended)
uv run python -m code_map.cli run --root /path/to/project

# Or without uv prefix (if activated venv)
python -m code_map.cli run --root /path/to/project

# Access API docs at: http://localhost:8010/docs
```

### Testing

```bash
# Run all tests (with uv)
uv run pytest

# Specific test suites
uv run pytest tests/test_linters_pipeline.py
uv run pytest tests/test_analysis_engine.py
uv run pytest tests/test_stage_config.py

# With coverage
uv run pytest --cov=code_map --cov=stage_init

# Full flow test (stage framework)
bash tests/test_full_flow.sh
```

### Package Management (uv)

```bash
# Add a new dependency
uv add package-name

# Add a dev dependency
uv add --dev package-name

# Update lockfile after pyproject.toml changes
uv lock

# Sync environment with lockfile
uv sync --all-extras

# Run any command in the project environment
uv run <command>
```

---

## Architecture

### High-Level Structure

**Stage Framework (Standalone CLI)**
- Pure Python 3.10+ using only stdlib (no external dependencies)
- `init_project.py` → delegates to `stage_init/` modules
- `assess_stage.py` → uses `stage_config.py` for detection logic
- Templates in `templates/basic/.claude/` and `templates/docs/`

**Code Map (Web Service)**
- FastAPI async application
- Multi-language analyzers using tree-sitter, esprima, BeautifulSoup
- Automated linter pipeline with configurable tools
- Optional Ollama integration for AI insights
- File watching and change scheduling

### Key Integrations

**Stage Detection in Code Map:**
- `code_map/stage_toolkit.py` provides stage assessment via `assess_stage.py`
- `code_map/api/stage.py` exposes REST endpoint: `POST /api/stage/assess`
- Uses symbol index from code analysis for deeper insights when available

**Linter Pipeline Configuration:**
Set environment variables before starting the API:
```bash
CODE_MAP_DISABLE_LINTERS=1                      # Skip linters entirely
CODE_MAP_LINTERS_TOOLS=ruff,pytest              # Limit to specific tools
CODE_MAP_LINTERS_MAX_PROJECT_FILES=2000         # Skip if too many files
CODE_MAP_LINTERS_MAX_PROJECT_SIZE_MB=200        # Skip if project too large
CODE_MAP_LINTERS_MIN_INTERVAL_SECONDS=300       # Minimum seconds between runs
```

**Ollama Integration:**
- `code_map/integrations/ollama_service.py` - Core service
- `code_map/insights/ollama_service.py` - Insights-specific wrapper
- Configurable via settings: model, base URL, focus areas
- Provides AI-powered code analysis and suggestions

### Directory Structure

```
/
├── init_project.py              # Stage framework CLI entry point
├── assess_stage.py              # Stage detection CLI
├── claude_assess.py             # Deep analysis helper
├── stage_config.py              # Stage detection algorithms & thresholds
├── stage_init/                  # Modular initialization logic
│   ├── cli.py                   # Argument parsing
│   ├── initializer.py           # Core initialization
│   ├── templates.py             # Template management
│   └── stage_update.py          # Stage tracking updates
├── templates/                   # Project initialization templates
│   ├── basic/.claude/           # Tracking files, stage rules, subagents
│   └── docs/                    # Reference documentation
├── code_map/                    # FastAPI backend
│   ├── server.py                # Application factory
│   ├── cli.py                   # CLI commands (run, config)
│   ├── analyzer.py              # Python code parsing
│   ├── ts_analyzer.py           # TypeScript/JavaScript parsing
│   ├── js_analyzer.py           # Additional JS analysis
│   ├── html_analyzer.py         # HTML parsing
│   ├── index.py                 # Symbol indexing
│   ├── dependencies.py          # Dependency graph
│   ├── class_graph.py           # Class hierarchy
│   ├── uml_graph.py             # UML diagram generation
│   ├── linters/                 # Linter pipeline
│   │   ├── pipeline.py          # Orchestration
│   │   ├── discovery.py         # Tool detection
│   │   ├── storage.py           # Results persistence
│   │   └── report_schema.py     # Report formats
│   ├── integrations/            # External services
│   │   └── ollama_service.py    # Ollama AI integration
│   ├── insights/                # AI insights
│   │   ├── ollama_service.py    # Insights-specific wrapper
│   │   └── storage.py           # Insights persistence
│   ├── api/                     # REST endpoints
│   │   ├── routes.py            # Main router
│   │   ├── analysis.py          # Code analysis
│   │   ├── linters.py           # Linter reports
│   │   ├── integrations.py      # Ollama integration
│   │   ├── stage.py             # Stage assessment
│   │   ├── graph.py             # Dependency graphs
│   │   └── preview.py           # Code previews
│   ├── settings.py              # Configuration
│   ├── state.py                 # Application state
│   └── watcher.py               # File watching
├── tests/                       # Test suite
│   ├── test_full_flow.sh        # Integration test
│   ├── test_linters_pipeline.py
│   ├── test_analysis_engine.py
│   ├── test_stage_*.py
│   └── test_api.py
└── tools/                       # Development utilities
    ├── debug_ollama.py
    └── test_backend_ollama.py
```

---

## Development Workflows

### Working on Stage Framework

**Adding detection logic:**
1. Update `stage_config.py` with new metrics/thresholds
2. Test with: `python assess_stage.py <project-path>`
3. Update tests in `tests/test_stage_config.py`
4. Run: `bash tests/test_full_flow.sh`

**Modifying templates:**
1. Edit files in `templates/basic/.claude/` or `templates/docs/`
2. Test: `python init_project.py test-temp --dry-run`
3. Verify with actual init: `python init_project.py test-temp`
4. Update `tests/test_full_flow.sh` if structure changed

### Working on Code Map

**Adding analyzer features:**
1. Update relevant analyzer in `code_map/` (e.g., `analyzer.py`, `ts_analyzer.py`)
2. Add tests in `tests/test_analysis_engine.py`
3. Update API endpoints in `code_map/api/` if exposing new functionality
4. Test: `pytest tests/test_analysis_engine.py -v`

**Modifying linter pipeline:**
1. Edit `code_map/linters/pipeline.py` for orchestration
2. Edit `code_map/linters/discovery.py` to add new tools
3. Test: `pytest tests/test_linters_pipeline.py -v`
4. Verify environment variable controls work
5. Test API integration: `POST /api/linters/run`

**Adding Ollama features:**
1. Update `code_map/integrations/ollama_service.py`
2. Test locally with Ollama running
3. Use debug tool: `python tools/debug_ollama.py`
4. Test backend: `python tools/test_backend_ollama.py`
5. Add API endpoints in `code_map/api/integrations.py`

---

## Critical Design Decisions

### Stage Framework: Non-Destructive Initialization

**Philosophy:** Allow adding framework to existing projects safely.

Implementation in `stage_init/initializer.py`:
- Only copies files if they don't exist
- Never overwrites existing `.claude/` files
- Reports skipped vs. copied files separately
- Preserves user customizations

### Stage Framework: Placeholder System

Simple `str.replace()` approach in copied template files:
- `{{PROJECT_NAME}}` - Project directory name
- `{{DATE}}` - Current date (YYYY-MM-DD)
- `{{YEAR}}` - Current year
- Applied only to newly copied files (not existing ones)

### Code Map: Linter Pipeline Design

**Graceful Degradation:**
- Auto-discovers available tools (ruff, mypy, bandit, pytest)
- Runs only installed tools, skips missing ones
- Respects size/file thresholds to avoid performance issues
- Minimum interval prevents excessive runs
- Environment variables provide runtime control

Implementation: `code_map/linters/pipeline.py`

### Code Map: Symbol Index Integration

**Enhanced Stage Detection:**
- Code Map's `SymbolIndex` provides deep code analysis
- Detects design patterns, class hierarchies, dependencies
- Used by `assess_stage.py` when available (via API or direct import)
- Falls back to basic file/LOC metrics if unavailable

Integration: `code_map/stage_toolkit.py`

---

## Dependencies

### Stage Framework (Core)
- **Python 3.10+** only
- **No external dependencies** (stdlib only: `pathlib`, `shutil`, `sys`, `datetime`, `subprocess`)
- Optional: `claude` CLI for CLAUDE.md generation

### Code Map Backend

**Package Manager: uv** (recommended) or pip

```bash
# Install uv (if not installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies with uv (recommended)
uv sync --all-extras

# Or with pip (legacy)
pip install -r requirements.txt
```

**Core (required):**
- fastapi>=0.110,<0.120
- pydantic>=2.7,<3
- uvicorn[standard]>=0.29,<0.32
- watchdog>=3.0,<5
- typer>=0.12,<1

**Testing:**
- pytest>=8.2,<9
- pytest-asyncio>=0.23,<0.24
- pytest-cov>=5.0,<6
- httpx>=0.27,<0.28

**Linters (used by pipeline):**
- ruff>=0.5,<0.6
- black>=24.4,<25
- mypy>=1.10,<1.11
- bandit>=1.7.10,<1.8

**Analyzers (optional):**
- beautifulsoup4>=4.12,<5 (HTML analysis)
- esprima>=4.0,<5 (JavaScript parsing)
- tree_sitter>=0.20,<0.22 (Multi-language AST)
- tree_sitter_languages>=1.10,<2

---

## Common Development Tasks

### Add New Stage Rule

1. Create `templates/basic/.claude/02-stageN-rules.md`
2. Update `stage_config.py` with new `StageDefinition`
3. Test: `python init_project.py test-project --dry-run`
4. Update documentation in `docs/STAGE_CRITERIA.md`

### Add New Linter Tool

1. Add detection logic in `code_map/linters/discovery.py`
2. Add execution logic in `code_map/linters/pipeline.py`
3. Add tests in `tests/test_linters_pipeline.py`
4. Document in README.md (environment variables section)

### Add New API Endpoint

1. Create/edit module in `code_map/api/`
2. Define Pydantic schemas if needed (see `code_map/api/schemas.py`)
3. Register router in `code_map/api/routes.py`
4. Add tests in `tests/test_api.py`
5. Test manually via FastAPI docs: `http://localhost:8010/docs`

### Integrate New AI Service

1. Create service module in `code_map/integrations/`
2. Follow pattern from `ollama_service.py`
3. Add configuration to `code_map/settings.py`
4. Create API endpoints in `code_map/api/integrations.py`
5. Create debug/test tools in `tools/`

---

## Testing Strategy

### Stage Framework Tests
- **Integration:** `bash tests/test_full_flow.sh` (covers full initialization flow)
- **Unit:** `pytest tests/test_stage_*.py`
- **Manual:** Use `--dry-run` flag for safe testing
- **Validation:** Test on real projects with known stages

### Code Map Tests
- **Unit:** `pytest tests/test_*.py`
- **Focused:** `pytest tests/test_linters_pipeline.py -v`
- **Integration:** Start server and test via `http://localhost:8010/docs`
- **Coverage:** `pytest --cov=code_map --cov=stage_init`

### Philosophy
- Test real behavior, avoid mocking when possible
- Add tests when bugs appear (not preemptively - YAGNI)
- Document expected behavior through tests
- Integration tests verify end-to-end flows

---

## Session Continuity

This project follows its own stage-aware methodology:

**Key context files:**
- [.claude/00-project-brief.md](.claude/00-project-brief.md) - Project scope and constraints
- [.claude/01-current-phase.md](.claude/01-current-phase.md) - Current development state, decisions, next steps
- [.claude/02-stage3-rules.md](.claude/02-stage3-rules.md) - Production-level development rules (current stage)

**Workflow:**
- **Session start:** Read the above files to understand current state
- **During work:** Follow stage-specific rules, propose before implementing
- **Session end:** Update `01-current-phase.md` with progress and decisions

---

## Core Philosophy

**YAGNI (You Aren't Gonna Need It):**
- Add features only when pain is felt 3+ times
- Start minimal, evolve with evidence
- Stage framework enforces this discipline

**Evolutionary Architecture:**
- **Stage 1:** Prove the concept (single file, hardcoded values)
- **Stage 2:** Add structure when refactoring hurts (multiple files, simple patterns)
- **Stage 3:** Scale when usage demands it (full architecture, optimization)

**Maintain Control:**
- AI executes, humans decide, framework enforces
- Stage rules prevent over-engineering
- Explicit constraints guide development

---

## Git Workflow

**Current branch:** `integrate-ollama`
**Main branch:** `first-steps` (target for PRs)

Recent work focuses on:
- Ollama insights integration
- Linter pipeline enhancements
- Stage detection algorithm refinements
- Code Map API expansion

When creating PRs, target the `first-steps` branch.

---

# Custom Workflow Instructions

<!-- Added by stage-aware initializer -->

## 🎯 PROJECT CONTEXT

Before ANY work, read in this order:
1. .claude/00-project-brief.md - Project scope and constraints
2. .claude/01-current-phase.md - Current state and progress
3. .claude/02-stage[X]-rules.md - Rules for current stage

## 📝 SESSION WORKFLOW

⚠️ MANDATORY: At the START of EVERY session, BEFORE responding to user:

1. **ALWAYS read these files first** (use Read tool in parallel):
   - .claude/00-project-brief.md - Project scope and constraints
   - .claude/01-current-phase.md - Current state and next steps (COMPACT)
   - .claude/02-stage[X]-rules.md - Rules for current stage

2. **ALWAYS confirm to user** you've read the context:
   - State current phase/stage
   - Summarize what was last done
   - Ask for clarification if anything is unclear

3. **ONLY THEN** respond to the user's request

**This applies EVEN IF the user's first message is a simple question.**
Do NOT skip this protocol to "be helpful faster" - reading context IS being helpful.

**Need deep context?** Read `.claude/01-session-history.md` for full session details.

At END of session:
- Update .claude/01-current-phase.md with progress
- **CRITICAL**: Keep 01-current-phase.md under 150 lines

## 🔄 FEATURE DEVELOPMENT WORKFLOW

For ANY new feature, follow this workflow with explicit gates:

```
1. CHECK/CREATE → 2. PLAN → 3. APPROVE → 4. IMPLEMENT → 5. TEST → 6. VALIDATE → 7. APPROVE
```

### Phase 1: PLANNING (Research & Design)
**Agents**: @architect, @stage-keeper
**Output**: `docs/{feature}/architecture.md`

**Steps**:
1. Check if `docs/{feature}/` exists
   - If exists: **READ existing documentation first**
   - If not: Create the directory
2. @architect analyzes requirements and constraints
3. @architect designs stage-appropriate architecture
4. @architect defines testing strategy (unit + integration)
5. @stage-keeper validates stage-appropriateness
6. Document in `docs/{feature}/architecture.md`

**Architecture must include**:
- Context & Requirements
- Stage Assessment
- Component Structure
- Technology Stack with trade-offs
- Build Order with dependencies
- **Testing Strategy** (what to test, how)
- Evolution Triggers

**🚦 GATE**: Present plan to user. **WAIT FOR APPROVAL** before Phase 2.

### Phase 2: IMPLEMENTATION (Building & Testing)
**Agent**: @implementer
**Output**: Code files + `docs/{feature}/implementation.md`

**Steps**:
1. **READ `architecture.md` FIRST** (mandatory)
2. Implement components in specified build order
3. Write unit tests for each component
4. **Run unit tests - MUST PASS**
5. Write integration tests (if Stage 2+)
6. **Run integration tests - MUST PASS**
7. Track progress in `docs/{feature}/implementation.md`
8. Document any deviations or blockers

**Testing Requirements by Stage**:
| Stage | Unit Tests | Integration Tests |
|-------|------------|-------------------|
| 1 (PoC) | Optional | Not required |
| 2 (Prototype) | Basic coverage | Optional |
| 3 (Production) | Full coverage | Required |
| 4 (Scale) | Full + edge cases | Full + performance |

**Blockers trigger**:
- Plan is unclear or incomplete
- Technical constraints make plan infeasible
- Need to deviate significantly from plan
→ **STOP**, document in `blockers.md`, request architect clarification

**🚦 GATE**: All tests must **PASS** before Phase 3.

### Phase 3: VALIDATION (Quality Assurance)
**Agents**: @code-reviewer, @stage-keeper
**Output**: `docs/{feature}/qa-report.md`

**Steps**:
1. @code-reviewer reads `architecture.md` and `implementation.md`
2. Validate implementation matches plan
3. Verify all tests pass (unit + integration)
4. Check security, correctness, performance
5. @stage-keeper verifies stage-appropriate complexity
6. Document findings in `docs/{feature}/qa-report.md`

**Recommendation options**:
- ✅ **APPROVED**: Feature complete
- ⚠️ **MINOR FIXES**: Small changes needed
- ❌ **REQUEST CHANGES**: Return to Phase 2

**🚦 GATE**: Present QA report to user. **WAIT FOR FINAL APPROVAL**.

## 📁 DOCUMENTATION STRUCTURE

For each feature, maintain:
```
docs/{feature-name}/
├── architecture.md      # Phase 1: Plan
├── implementation.md    # Phase 2: Progress
├── qa-report.md        # Phase 3: Validation
└── blockers.md         # Issues (optional)
```

## 👥 AGENT ROLES

| Agent | Phase | Role | Can Write Code? |
|-------|-------|------|-----------------|
| @architect | 1 | Design architecture, create plan | ❌ No |
| @stage-keeper | 1, 2, 3 | Validate stage-appropriateness | ❌ No |
| @implementer | 2 | Execute plan, write code & tests | ✅ Yes |
| @code-reviewer | 3 | Validate quality, plan adherence | ❌ No |
| @orchestrator | All | Coordinate phases, manage transitions | ✅ Limited |

## ⚠️ CRITICAL RULES

### Workflow Compliance
- **NEVER skip phases** (must go 1 → 2 → 3)
- **NEVER implement without approved plan**
- **NEVER skip tests** (except Stage 1 PoC)
- **NEVER proceed without user approval at gates**
- **ALWAYS read existing docs before changes**

### Agent-Specific Rules
- **@architect, @stage-keeper**: NEVER write implementation code
- **@implementer**: ALWAYS read architecture.md FIRST
- **@code-reviewer**: NEVER redesign architecture
- **All agents**: Output to correct `docs/{feature}/` locations

### Session Management
- Never implement without reading current context
- Never skip updating progress at end of session
- Never assume you remember from previous sessions
- Always check current stage rules before proposing solutions

### Stage Awareness
- **Stage 1 (PoC)**: Speed and simplicity, minimal tests
- **Stage 2 (Prototype)**: Basic structure, basic tests
- **Stage 3 (Production)**: Full tests, error handling
- **Stage 4 (Scale)**: Performance tests, edge cases

## 🚫 NEVER

### Phase 1 (Planning)
- Write implementation code
- Skip stage-keeper validation
- Create incomplete architecture plans
- Proceed to Phase 2 without user approval

### Phase 2 (Implementation)
- Start coding without reading architecture.md
- Make architectural decisions not in the plan
- Skip writing tests (Stage 2+)
- Proceed to Phase 3 with failing tests
- Ignore blockers (document and escalate)

### Phase 3 (Validation)
- Redesign the architecture
- Approve code that deviates from plan without documented reason
- Skip reading architecture.md before review
- Ignore stage compliance violations

## 📚 PROJECT RESOURCES

Available in `docs/` folder:
- **README.md** - Workflow documentation and templates
- **PROMPT_LIBRARY.md** - Templates for common situations
- **QUICK_START.md** - Workflow guide
- **STAGES_COMPARISON.md** - Quick reference table
- **CLAUDE_CODE_REFERENCE.md** - Claude Code tips, slash commands, MCP, subagents

## 💡 REMEMBER

- **Check → Plan → Approve → Implement → Test → Validate → Approve**
- Tests are mandatory (Stage 2+)
- User approval required at gates
- Simplicity > Completeness
- When in doubt, check the stage rules

---

*To update these instructions, modify templates/basic/.claude/CUSTOM_INSTRUCTIONS.md*

