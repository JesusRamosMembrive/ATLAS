# Backend SQL Refactoring Plan

## Goal
Replace raw SQL queries and manual schema management in `code_map/settings.py` with `SQLModel` (an ORM built on SQLAlchemy and Pydantic). This aligns with the audit recommendations and the project's existing stack (FastAPI/Pydantic).

## Dependencies
- **Add**: `sqlmodel` (to `requirements.txt`)
- **Reason**: Simplifies database interactions, provides validation, and reduces SQL injection risks. It fits perfectly with the existing `pydantic` usage.

## Proposed Changes

### 1. New Dependency
Add `sqlmodel` to `requirements.txt`.

### 2. Database Module (`code_map/database.py`)
Create a new file to handle:
- Database engine creation (`create_engine`).
- Session management (`Session` dependency).
- Schema initialization (`SQLModel.metadata.create_all`).

### 3. Models
Refactor/Create models to extend `SQLModel`:
- `AppSettings`: Currently a dataclass, will become a SQLModel table.
- `LinterReport`: Currently raw SQL table, will become a SQLModel table.
- `Notification`: Currently raw SQL table, will become a SQLModel table.

### 4. Refactor `settings.py`
- Remove raw `sqlite3` calls.
- Use `Session` for querying and saving `AppSettings`.
- Remove manual "ensure column" logic (migrations); `SQLModel.metadata.create_all` handles table creation.

### 5. Testing
- Create `tests/test_database.py`.
- Add integration tests to verify:
    - Database creation.
    - Schema initialization.
    - CRUD operations for settings.
- Run `pytest`.

## Migration Strategy
Since `SQLModel` doesn't do auto-migrations (ALTER TABLE) without Alembic, and the current code *does* do manual ALTERS (`_ensure_column`), I will:
1.  Define the Table models.
2.  In `database.py`, keep a small utility to adding missing columns if we want to preserve that behavior, OR assume `SQLModel.metadata.create_all` is sufficient for new tables. Existing users might encounter issues if schema mismatches occur, so I will prioritize keeping the tables but simply accessing them via ORM.

## Files to Modify
- `requirements.txt`
- `code_map/database.py` (NEW)
- `code_map/models.py` (Update)
- `code_map/settings.py` (Refactor)
- `tests/test_database.py` (NEW)
