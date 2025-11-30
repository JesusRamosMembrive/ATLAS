# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a full-stack ecommerce application with a FastAPI backend implementing hexagonal architecture and a React TypeScript frontend. The project manages products, users, and orders with OAuth2 authentication.

### Tech Stack
- **Backend**: FastAPI, Motor (MongoDB), OAuth2, Pydantic
- **Frontend**: React 19, TypeScript, Vite, TailwindCSS, Radix UI, React Query, React Router
- **Database**: MongoDB (with Docker setup available)
- **Architecture**: Hexagonal Architecture (Ports & Adapters) for backend, Feature-based architecture for frontend

## Common Commands

### Backend (from `/backend` directory)
```bash
# Install Poetry (if not already installed)
curl -sSL https://install.python-poetry.org | python3 -

# Install dependencies
poetry install

# Activate virtual environment
poetry shell

# Run development server
poetry run uvicorn src.main:app --reload

# Run tests with coverage
poetry run pytest --cov=src --cov-report=term-missing --cov-report=html

# Run specific test types
poetry run pytest -m unit          # Unit tests only
poetry run pytest -m integration   # Integration tests only
poetry run pytest -m "not slow"  # Skip slow tests

# Run specific test file
poetry run pytest tests/test_domain_entities.py

# Run tests matching pattern
poetry run pytest -k "test_user"

# Add a new dependency
poetry add package-name

# Add a development dependency
poetry add --group dev package-name

# Update dependencies
poetry update

# Show installed packages
poetry show

# Export to requirements.txt (if needed for compatibility)
poetry export -f requirements.txt --output requirements.txt
```

### Frontend (from `/frontend` directory)
```bash
# Install dependencies
npm install

# Run development server
npm run dev

# Build for production
npm run build

# Lint code
npm run lint

# Preview production build
npm run preview
```

### Database
```bash
# Start MongoDB with Docker
docker compose up -d
```

## Architecture

### Backend - Hexagonal Architecture

The backend follows hexagonal architecture with clear separation of concerns:

#### Domain Layer (`src/domain/`)
- **Entities** (`entities/`): Core business objects using `@dataclass` with validation in `__post_init__`
- **Exceptions** (`exceptions/`): Domain-specific exceptions for business rule violations

#### Application Layer (`src/application/`)
- **Ports** (`ports/`): Repository interfaces (abstract contracts)
- **Use Cases** (`use_cases/`): Business logic orchestration, one public `execute` method per use case

#### Infrastructure Layer (`src/infrastructure/`)
- **Adapters** (`adapters/repositories/`): MongoDB repository implementations
- **Web** (`web/`): FastAPI routers, DTOs, mappers, dependencies
  - **Routers**: Thin controllers delegating to use cases
  - **DTOs**: Pydantic models for request/response validation
  - **Mappers**: Clean conversion between DTOs and domain entities
  - **Dependencies**: Dependency injection with `@lru_cache()` for repositories

### Frontend - Feature-based Architecture

The frontend is organized by features with each feature containing:

#### Feature Structure (`src/features/{feature}/`)
- **Components** (`components/`): React components using feature context
- **Data** (`data/`): Schemas (Zod), services (API calls)
- **Hooks** (`hooks/`):
  - **Context Hook** (`use{Feature}Context.tsx`): Feature state management and operations using context
  - **Business Hook** (`use{Feature}.tsx`): Feature state management and operations 
  - **Mutations** (`mutations/`): React Query mutations for data modification
  - **Queries** (`queries/`): React Query queries for data fetching

#### Core Infrastructure (`src/core/`)
- **Data** (`data/`): API client, app storage, query client setup
- **Hooks** (`hooks/`): Shared hooks across features

#### UI Components (`src/components/ui/`)
- Radix UI-based reusable components with TailwindCSS styling

## Development Guidelines

### Backend Conventions
- Use dependency injection throughout the web layer
- All use cases follow the pattern: constructor injection → single `execute` method
- Domain entities validate in `__post_init__` and business methods
- Repository implementations use MongoDB with Motor async driver
- DTOs use Pydantic with comprehensive validation
- Map domain exceptions to appropriate HTTP status codes

### Frontend Conventions
- Each feature exports a context provider and custom hook
- Components import UI components from `@/components/ui/`
- Use `use{Feature}Context` for accessing feature state and operations for context states
- Use `use{Feature}` for accessing feature state and operations
- Mutations return: `{action, isLoading, error, isSuccess}`
- Services use axios for API communication
- Type safety with TypeScript and Zod schemas

### Testing
- Backend uses pytest with comprehensive test configuration
- Tests organized by layers: domain, service, repository, API, integration
- Coverage requirement: 80%
- Use markers for test categorization: `unit`, `integration`, `slow`, `auth`, `api`

### Security
- OAuth2 authentication with JWT tokens
- Password hashing with bcrypt
- Protected routes on both backend and frontend
- Environment-based configuration for sensitive data

## Environment Setup


## Important Files
- `backend/src/app.py`: FastAPI application factory
- `backend/src/main.py`: Application entry point
- `frontend/src/main.tsx`: React application entry point
- `backend/pytest.ini`: Test configuration
- `backend/run_tests.py`: Comprehensive test runner with multiple options


## WORKFLOW RULES
### Phase 1
- At the starting point of a feature on plan mode phase you MUST ALWAYS init a `.claude/sessions/context_session_{feature_name}.md` with yor first analisis
- You MUST ask to the subagents that you considered that have to be involved about the implementation and check their opinions, try always to run them on parallel if is posible
- After a plan mode phase you ALWAYS update the `.claude/sessions/context_session_{feature_name}.md` with the definition of the plan and the recomentations of the subagents
### Phase 2
- Before you do any work, MUST view files in `.claude/sessions/context_session_{feature_name}.md` file to get the full context (x being the id of the session we are operate)
- `.claude/sessions/context_session_{feature_name}.md` should contain most of context of what we did, overall plan, and sub agents will continusly add context to the file
- After you finish the each phase, MUST update the `.claude/sessions/context_session_{feature_name}.md` file to make sure others can get full context of what you did
- After you finish the work, MUST update the `.claude/sessions/context_session_{feature_name}.md` file to make sure others can get full context of what you did
### Phase 3
- After finish the final implementation MUST use qa-criteria-validator subagent to provide a report feedback an iterate over this feedback until acceptance criterias are passed
- After qa-criteria-validator finish, you MUST review their report and implement the feedback related with the feature

### SUBAGENTS MANAGEMENT
You have access to 8 subagents:
- shadcn-ui-architect: all task related to UI building & tweaking HAVE TO consult this agent
- qa-criteria-validator: all final client UI/UX implementations has to be validated by this subagent to provide feedback an iterate.
- ui-ux-analyzer: all the task related with UI review, improvements & tweaking HAVE TO consult this agent
- pydantic-ai-architect: all task related to ai agents using pydantic-ai framework & tweaking HAVE TO consult this agent
- frontend-developer: all task related to business logic in the client side before create the UI building & tweaking HAVE TO consult this agent
- frontend-test-engineer: all task related to business logic in the client side after implementation has to consult this agent to get the necesary test cases definitions
- backend-developer: all task related to business logic in the backend side HAVE TO consult this agent
- backend-test-engineer: all task related to business logic in the backned side after implementation has to consult this agent to get the necesary test cases definitions

Subagents will do research about the implementation and report feedback, but you will do the actual implementation;

When passing task to sub agent, make sure you pass the context file, e.g. `.claude/sessions/context_session_{feature_name}.md`.

After each sub agent finish the work, make sure you read the related documentation they created to get full context of the plan before you start executing
