# Code Map - Docker Kiosk Mode

Run Code Map in a Docker container with Chrome kiosk mode for a dedicated analysis environment.

---

## 📋 Table of Contents

- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Usage](#usage)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)
- [Advanced Usage](#advanced-usage)

---

## 🎯 Overview

This Docker setup provides a **production-ready** environment for Code Map with the following features:

- **Multi-stage build**: Optimized frontend build + Python backend
- **Kiosk mode launcher**: Opens Chrome in fullscreen automatically
- **Persistent database**: SQLite database persists across restarts
- **Project mounting**: Analyze any project on your host machine
- **Cross-platform**: Works on Linux, macOS, and Windows

### Architecture

```
┌─────────────────────────────────────┐
│      Docker Container               │
│  ┌───────────────────────────────┐  │
│  │  FastAPI Backend (port 8010)  │  │
│  │  - API endpoints: /api/*      │  │
│  │  - Call tracer: /tracer/*     │  │
│  │  - Serves frontend at /       │  │
│  └───────────────────────────────┘  │
│                                      │
│  Volumes:                            │
│  - /work → Your project (read-only) │
│  - .code-map → Database (persistent)│
└──────────────────┬───────────────────┘
                   │ Port 8080:8010
                   ↓
       ┌───────────────────────┐
       │   Host Machine        │
       │  ┌─────────────────┐  │
       │  │ Chrome Kiosk    │  │
       │  │ localhost:8080  │  │
       │  └─────────────────┘  │
       └───────────────────────┘
```

---

## 📦 Prerequisites

### Required

- **Docker**: Docker Engine 20.10+ or Docker Desktop
  - Linux: [Install Docker Engine](https://docs.docker.com/engine/install/)
  - macOS: [Install Docker Desktop](https://docs.docker.com/desktop/install/mac-install/)
  - Windows: [Install Docker Desktop](https://docs.docker.com/desktop/install/windows-install/)

- **Docker Compose**: Version 2.0+ (usually included with Docker Desktop)

- **Google Chrome**: For kiosk mode
  - Linux: `sudo apt install google-chrome-stable` or `chromium-browser`
  - macOS: [Download Chrome](https://www.google.com/chrome/)
  - Windows: [Download Chrome](https://www.google.com/chrome/)

### System Requirements

- **RAM**: 4GB minimum, 8GB recommended
- **Disk**: ~2GB for Docker image + build cache
- **CPU**: 2+ cores recommended for faster builds

---

## 🚀 Quick Start

### Linux / macOS

```bash
# 1. Navigate to project directory
cd /path/to/Claude-Prompt-Library

# 2. Run the kiosk launcher
./launch-kiosk.sh

# 3. Enter project path when prompted (or press Enter for current directory)
# Example: /home/user/my-project

# 4. Chrome will open in kiosk mode automatically
```

### Windows

```cmd
REM 1. Navigate to project directory
cd C:\path\to\Claude-Prompt-Library

REM 2. Run the kiosk launcher
launch-kiosk.bat

REM 3. Enter project path when prompted (or press Enter for current directory)
REM Example: C:\Users\username\my-project

REM 4. Chrome will open in kiosk mode automatically
```

### Exit Kiosk Mode

- **Linux/macOS**: Press `Alt+F4` or `Ctrl+W`
- **Windows**: Press `Alt+F4`

---

## 📖 Usage

### Basic Workflow

1. **Launch**: Run `./launch-kiosk.sh` (Linux/macOS) or `launch-kiosk.bat` (Windows)
2. **Select Project**: Enter path to project you want to analyze
3. **Wait**: Container builds and starts (first run takes ~5 minutes)
4. **Analyze**: Chrome opens in kiosk mode with Code Map UI
5. **Exit**: Close Chrome to exit kiosk mode
6. **Stop**: Run `docker-compose down` to stop container

### Manual Docker Commands

If you prefer manual control:

```bash
# Build and start container
export PROJECT_PATH=/path/to/your/project
docker-compose up -d --build

# View logs
docker-compose logs -f

# Stop container
docker-compose down

# Restart container
docker-compose restart

# Open browser manually (not kiosk mode)
open http://localhost:8080  # macOS
xdg-open http://localhost:8080  # Linux
start http://localhost:8080  # Windows
```

### Accessing the Application

Once running, the application is available at:

- **Main UI**: http://localhost:8080
- **API Docs**: http://localhost:8080/docs (FastAPI Swagger UI)
- **API Redoc**: http://localhost:8080/redoc

---

## ⚙️ Configuration

### Environment Variables

You can customize the container behavior via environment variables in `docker-compose.yml`:

```yaml
environment:
  # Project root (mounted at /work in container)
  - CODE_MAP_ROOT=/work

  # Include docstrings in analysis
  - CODE_MAP_INCLUDE_DOCSTRINGS=1

  # Database path
  - CODE_MAP_DB_PATH=/app/.code-map/state.db

  # Linter configuration
  - CODE_MAP_DISABLE_LINTERS=0
  - CODE_MAP_LINTERS_TOOLS=ruff,mypy,bandit,pytest
  - CODE_MAP_LINTERS_MAX_PROJECT_FILES=2000
  - CODE_MAP_LINTERS_MAX_PROJECT_SIZE_MB=200
  - CODE_MAP_LINTERS_MIN_INTERVAL_SECONDS=300

  # Ollama integration (if using)
  - CODE_MAP_OLLAMA_BASE_URL=http://host.docker.internal:11434
  - CODE_MAP_OLLAMA_MODEL=codellama
```

### Port Configuration

To change the exposed port, edit `docker-compose.yml`:

```yaml
ports:
  - "9000:8010"  # Change 9000 to your preferred port
```

Then update launcher scripts to use the new port.

### Resource Limits

Uncomment the `deploy` section in `docker-compose.yml` to limit resources:

```yaml
deploy:
  resources:
    limits:
      cpus: '2'
      memory: 4G
    reservations:
      cpus: '1'
      memory: 2G
```

---

## 🐛 Troubleshooting

### Container Won't Start

**Problem**: `docker-compose up` fails

**Solutions**:
```bash
# Check Docker daemon is running
docker info

# Check logs for errors
docker-compose logs

# Rebuild from scratch
docker-compose down -v
docker-compose build --no-cache
docker-compose up -d
```

### Chrome Not Found

**Problem**: Script can't find Chrome

**Solutions**:
- **Linux**: Install Chrome: `sudo apt install google-chrome-stable`
- **macOS**: Install from https://www.google.com/chrome/
- **Windows**: Install from https://www.google.com/chrome/

Alternatively, open manually: http://localhost:8080

### Port Already in Use

**Problem**: `Error: port 8080 already in use`

**Solutions**:
```bash
# Option 1: Stop the conflicting service
sudo lsof -i :8080  # Find process using port
sudo kill <PID>     # Kill the process

# Option 2: Change port in docker-compose.yml
# Edit: "9000:8010" instead of "8080:8010"
```

### Build Takes Too Long

**Problem**: Docker build is very slow

**Solutions**:
```bash
# Ensure .dockerignore is present (excludes node_modules, etc.)
# Check available disk space
df -h

# Clean Docker cache
docker system prune -a

# Increase Docker memory (Docker Desktop Settings → Resources)
```

### Application Not Responding

**Problem**: Container runs but app doesn't load

**Solutions**:
```bash
# Check container health
docker inspect code-map-app | grep -A 10 Health

# Check logs
docker-compose logs -f

# Restart container
docker-compose restart

# Check if port is accessible
curl http://localhost:8080/api/settings
```

### Permission Errors (Linux)

**Problem**: `Permission denied` when mounting project

**Solutions**:
```bash
# Ensure project directory is readable
chmod -R 755 /path/to/project

# Run Docker commands with sudo if needed
sudo docker-compose up -d
```

### Database Persistence Issues

**Problem**: Settings don't persist after restart

**Solutions**:
```bash
# Check volume exists
docker volume ls | grep code-map-data

# Inspect volume
docker volume inspect code-map-data

# If needed, recreate volume
docker-compose down -v
docker-compose up -d
```

---

## 🔧 Advanced Usage

### Using with Ollama (AI Insights)

If you have Ollama running on your host:

1. Edit `docker-compose.yml`:
   ```yaml
   environment:
     - CODE_MAP_OLLAMA_BASE_URL=http://host.docker.internal:11434
     - CODE_MAP_OLLAMA_MODEL=codellama
   ```

2. Restart container:
   ```bash
   docker-compose restart
   ```

### Analyzing Multiple Projects

The database persists project settings. To switch projects:

```bash
# Option 1: Restart with new PROJECT_PATH
export PROJECT_PATH=/path/to/different/project
docker-compose restart

# Option 2: Use the UI directory selector
# (Settings icon → Change project root)
```

### Building for Different Architectures

For ARM-based systems (e.g., Apple M1/M2):

```bash
# Build for ARM64
docker buildx build --platform linux/arm64 -t code-map:latest .

# Or let Docker auto-detect
docker-compose build
```

### Production Deployment

For deploying to a server:

```yaml
# docker-compose.prod.yml
services:
  code-map:
    image: code-map:latest
    restart: always
    ports:
      - "80:8010"
    volumes:
      - ./projects:/work:ro
      - code-map-data:/app/.code-map
    environment:
      - CODE_MAP_ROOT=/work
    deploy:
      resources:
        limits:
          cpus: '4'
          memory: 8G
```

```bash
# Deploy
docker-compose -f docker-compose.prod.yml up -d
```

### Accessing from Network

To access from other devices on your network:

1. Change host binding in Dockerfile (already set to `0.0.0.0`)
2. Expose port in firewall:
   ```bash
   # Linux (ufw)
   sudo ufw allow 8080/tcp

   # macOS (allow in System Preferences → Security)

   # Windows (allow in Windows Defender Firewall)
   ```
3. Access via: http://YOUR_IP:8080

### Debugging Build Issues

Enable verbose output:

```bash
# Build with full output
docker-compose build --progress=plain

# Run container with debug logs
docker-compose up
```

---

## 📝 Files Reference

### Created Files

- **Dockerfile**: Multi-stage build (frontend + backend)
- **docker-compose.yml**: Container orchestration
- **.dockerignore**: Build optimization (excludes unnecessary files)
- **launch-kiosk.sh**: Linux/macOS launcher script
- **launch-kiosk.bat**: Windows launcher script
- **README-DOCKER.md**: This documentation

### Modified Files

- **code_map/server.py**: Added static file serving for frontend

---

## 🎓 How It Works

### Build Process

1. **Stage 1 (Frontend)**:
   - Uses Node.js 18 Alpine image
   - Runs `npm ci` to install dependencies
   - Runs `npm run build` to create production build
   - Output: `frontend/dist/` (static files)

2. **Stage 2 (Backend)**:
   - Uses Python 3.11 Slim image
   - Installs Python dependencies from `requirements.txt`
   - Copies backend code
   - Copies frontend build from Stage 1
   - Sets up volumes and environment

### Runtime

- FastAPI serves API at `/api/*` and `/tracer/*`
- FastAPI serves frontend static files at `/`
- SPA routing enabled (`html=True` in StaticFiles mount)
- Database stored in Docker volume for persistence
- Project mounted read-only at `/work`

### Launcher Scripts

1. Check Docker is running
2. Prompt for project path
3. Set `PROJECT_PATH` environment variable
4. Run `docker-compose up -d --build`
5. Wait for healthcheck (container ready)
6. Detect Chrome binary
7. Launch Chrome in kiosk mode: `--kiosk --app=http://localhost:8080`

---

## 🤝 Contributing

If you improve the Docker setup:

1. Test on all platforms (Linux, macOS, Windows)
2. Update this README
3. Update launcher scripts if needed
4. Document breaking changes

---

## 📄 License

Same as the main project (see root LICENSE file).

---

## 🆘 Support

If you encounter issues:

1. Check this README's [Troubleshooting](#troubleshooting) section
2. Check Docker logs: `docker-compose logs -f`
3. Open an issue with:
   - OS and version
   - Docker version (`docker --version`)
   - Error messages
   - Steps to reproduce

---

**Happy analyzing!** 🚀
