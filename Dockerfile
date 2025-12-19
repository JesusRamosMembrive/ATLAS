# Multi-stage Dockerfile for Code Map in Production Mode
# Stage 1: Build frontend with Node.js
# Stage 2: Production runtime with Python + built frontend

# ============================================================================
# Stage 1: Frontend Builder
# ============================================================================
FROM node:18-alpine AS frontend-builder

WORKDIR /app/frontend

# Copy package files for dependency installation
COPY frontend/package*.json ./

# Install dependencies (using ci for reproducible builds)
RUN npm ci

# Copy frontend source code
COPY frontend/ ./

# Build production frontend (output to dist/)
# VITE_DEPLOY_BACKEND_URL="" forces the frontend to use window.location.origin
# This is correct for Docker where frontend and backend are served from same port
ENV VITE_DEPLOY_BACKEND_URL=""
RUN npm run build

# ============================================================================
# Stage 2: Production Runtime
# ============================================================================
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for tree-sitter and other tools
RUN apt-get update && apt-get install -y \
    curl \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Install uv for faster dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Copy dependency files
COPY pyproject.toml uv.lock ./

# Install Python dependencies using uv (faster than pip)
# --frozen: Use exact versions from uv.lock
# --no-dev: Skip dev dependencies in production
RUN uv sync --frozen --no-dev

# Copy backend source code
COPY code_map/ ./code_map/
COPY init_project.py assess_stage.py stage_config.py claude_assess.py ./
COPY stage_init/ ./stage_init/
COPY templates/ ./templates/

# Copy frontend build artifacts from Stage 1
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Create directories for volumes
RUN mkdir -p /work /app/.code-map

# Expose FastAPI port
EXPOSE 8010

# Environment variables for production
ENV CODE_MAP_ROOT=/work
ENV CODE_MAP_DB_PATH=/app/.code-map/state.db
ENV PYTHONUNBUFFERED=1
ENV CODE_MAP_INCLUDE_DOCSTRINGS=1

# Health check endpoint
HEALTHCHECK --interval=10s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8010/api/settings || exit 1

# Start Uvicorn server using uv run
# --host 0.0.0.0: Listen on all interfaces (required for Docker)
# --port 8010: Internal container port
# --log-level info: Production logging level
CMD ["uv", "run", "uvicorn", "code_map.server:app", "--host", "0.0.0.0", "--port", "8010", "--log-level", "info"]
