# Repository Guidelines

ATLAS mixes a stage-aware framework, a FastAPI analysis backend, and a React UI. Use this guide to keep code, prompts, and docs predictable.

## Project Structure & Module Organization
- `code_map/`: Python backend (analyzers, tracers, linter pipeline, FastAPI server, `code_map.cli`). Shared models in `models.py`; settings in `settings.py`.
- `frontend/`: Vite + React + TypeScript UI in `frontend/src`; keep hooks/components near their feature.
- `templates/` and `docs/`: Prompt library and design notes; update when adding agent flows or stage rules.
- `tests/`: Pytest for analyzers, API, stage toolkit; `test_full_flow.sh` for smoke. Frontend Vitest lives in `frontend/src`.
- `build/`, `dist/`, `docker-compose.yml`: Release artifacts and container setup. Avoid editing generated assets.

## Build, Test, and Development Commands
- Backend setup: `python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`
- Run API locally: `python -m code_map --root . --reload` (default port 8010).
- Lint/format backend: `ruff .`, `black .`, `mypy code_map`.
- Backend tests: `pytest -q` or `pytest --cov=code_map`.
- Frontend: `cd frontend && npm install`, then `npm run dev` (UI), `npm run build` (bundle), `npm run test` (unit).

## Coding Style & Naming Conventions
- Python: Black-formatted, 4-space indent, type-annotate public functions, snake_case for modules/functions, PascalCase for classes. Keep utilities side-effect free.
- JS/TS: Prettier + ESLint in `frontend`; 2-space indent, PascalCase components, `use*` hooks, kebab-case files unless exporting a component.
- Config: Prefer `.env` for `CODE_MAP_HOST`, `CODE_MAP_PORT`, `OLLAMA_HOST`; never commit secrets or local data.

## Testing Guidelines
- Favor small, deterministic tests; mirror backend modules under `tests/` with `test_<module>.py`.
- Mark async tests with `pytest.mark.asyncio` when needed.
- For frontend, colocate Vitest files as `*.test.tsx` near the component; use Testing Library for DOM behavior.
- Run smoke before PRs: `pytest` + `npm run test` (frontend) and spot-check `python -m code_map --root .`.

## Commit & Pull Request Guidelines
- Commits: short, imperative summaries (e.g., “Add stage-aware tracer”), no trailing punctuation; group related changes.
- PRs: include purpose, key changes, tests executed, and UI screenshots when relevant. Link issues and note docs updated (`docs/`, `templates/`, or `.claude/`/`stage_*`).
- Keep diffs focused; add follow-up tasks if work is staged. Update roadmap/usage docs when behavior or interfaces change.
