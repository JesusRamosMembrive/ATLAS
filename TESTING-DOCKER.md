# Docker Implementation - Testing Guide

This document describes how to test the Docker kiosk mode implementation.

## Implementation Status ✅

All Docker files have been successfully created:

- ✅ `Dockerfile` - Multi-stage build (2.2KB)
- ✅ `docker-compose.yml` - Service orchestration (1.9KB)
- ✅ `.dockerignore` - Build optimization (3.2KB)
- ✅ `launch-kiosk.sh` - Linux/macOS launcher (6.7KB, executable)
- ✅ `launch-kiosk.bat` - Windows launcher (4.6KB)
- ✅ `README-DOCKER.md` - Complete documentation (12KB)
- ✅ `code_map/server.py` - Modified to serve static files

## Code Validation ✅

- Python syntax validated: `code_map/server.py` compiles successfully
- StaticFiles import and mount code verified
- All scripts have proper permissions

## Testing Steps (When Docker is Available)

### Prerequisites

1. Install Docker:
   - **Linux**: `sudo apt install docker.io docker-compose`
   - **macOS**: Install Docker Desktop
   - **Windows**: Install Docker Desktop

2. Install Chrome:
   - **Linux**: `sudo apt install google-chrome-stable`
   - **macOS/Windows**: Download from https://www.google.com/chrome/

### Test 1: Build Validation

```bash
# Validate docker-compose.yml syntax
docker compose config

# Build the image (without running)
docker compose build

# Expected: Build completes successfully
# Time: ~5-10 minutes on first build
```

**Success criteria:**
- No build errors
- Frontend builds successfully (Stage 1)
- Backend image created (Stage 2)
- Image size: ~1-2GB

### Test 2: Container Startup

```bash
# Start container manually
export PROJECT_PATH=.
docker compose up -d

# Check container status
docker compose ps

# Expected: Container status shows "healthy"
```

**Success criteria:**
- Container starts without errors
- Healthcheck passes (status: healthy)
- Logs show: "Uvicorn running on http://0.0.0.0:8010"

### Test 3: API Accessibility

```bash
# Test API endpoint
curl http://localhost:8080/api/settings

# Expected: JSON response with settings

# Test frontend serving
curl -I http://localhost:8080/

# Expected: HTTP 200, Content-Type: text/html
```

**Success criteria:**
- API endpoints respond on port 8080
- Frontend index.html is served
- No 404 or 500 errors

### Test 4: Kiosk Mode Launcher (Linux/macOS)

```bash
# Run launcher script
./launch-kiosk.sh

# Enter project path when prompted
# (or press Enter for current directory)
```

**Success criteria:**
- Script detects Docker is running
- Container builds and starts
- Healthcheck waits for app to be ready
- Chrome launches in kiosk mode
- Application loads at http://localhost:8080

**Visual verification:**
- Chrome is fullscreen (no address bar)
- Code Map UI loads correctly
- Can navigate between pages
- Call Tracer works
- Settings page accessible

**Exit:**
- Press Alt+F4 to close Chrome
- Run `docker compose down` to stop container

### Test 5: Kiosk Mode Launcher (Windows)

```cmd
REM Run launcher script
launch-kiosk.bat

REM Enter project path when prompted
```

**Success criteria:**
- Same as Test 4 but on Windows
- Script detects Chrome installation
- Chrome launches with correct flags

### Test 6: Volume Persistence

```bash
# Start container
export PROJECT_PATH=.
docker compose up -d

# Make changes in UI (e.g., change settings)
# Open http://localhost:8080 and modify settings

# Restart container
docker compose restart

# Check settings persist
# Expected: Settings are preserved
```

**Success criteria:**
- Database persists in named volume `code-map-data`
- Settings survive container restart
- No data loss

### Test 7: Project Mounting

```bash
# Test with different project path
export PROJECT_PATH=/path/to/different/project
docker compose up -d

# Access UI and verify project is analyzed
# Expected: UI shows files from mounted project
```

**Success criteria:**
- Project files visible in analysis
- Can analyze mounted project code
- Read-only mount prevents modifications

### Test 8: Multi-platform Testing

Test on all target platforms:

1. **Linux (Ubuntu/Debian)**
   ```bash
   ./launch-kiosk.sh
   ```

2. **macOS**
   ```bash
   ./launch-kiosk.sh
   ```

3. **Windows**
   ```cmd
   launch-kiosk.bat
   ```

**Success criteria:**
- All platforms successfully build and run
- Chrome detection works on all platforms
- Kiosk mode launches correctly

## Known Limitations

1. **Docker not installed**: Scripts will fail gracefully with helpful error
2. **Chrome not found**: Scripts provide manual URL fallback
3. **Port 8080 in use**: User must manually change port in docker-compose.yml
4. **Large projects**: Build may take longer for projects with many dependencies

## Troubleshooting During Testing

### Build Fails

```bash
# Clean build
docker compose down -v
docker system prune -a
docker compose build --no-cache
```

### Container Won't Start

```bash
# Check logs
docker compose logs -f

# Common issues:
# - Port already in use (change in docker-compose.yml)
# - Permission errors (run with sudo on Linux)
```

### Frontend Not Loading

```bash
# Check if dist/ was created during build
docker compose exec code-map ls -la /app/frontend/dist/

# Expected: HTML, CSS, JS files present

# If empty, rebuild:
docker compose build --no-cache
```

### Database Permissions

```bash
# Check volume
docker volume inspect code-map-data

# If needed, reset:
docker compose down -v
docker compose up -d
```

## Performance Benchmarks

Expected build times (first build):
- **Frontend build**: ~2-3 minutes
- **Backend build**: ~1-2 minutes
- **Total build**: ~5-7 minutes

Expected runtime metrics:
- **Container startup**: ~10-15 seconds
- **Healthcheck ready**: ~5-10 seconds
- **Memory usage**: ~500MB-1GB
- **CPU usage**: <10% idle, 20-40% during analysis

## Integration Testing Checklist

- [ ] Build completes without errors
- [ ] Container starts and becomes healthy
- [ ] API endpoints accessible on port 8080
- [ ] Frontend loads correctly
- [ ] Kiosk launcher works (Linux/macOS)
- [ ] Kiosk launcher works (Windows)
- [ ] Database persists across restarts
- [ ] Project mounting works correctly
- [ ] Chrome opens in kiosk mode
- [ ] UI navigation works
- [ ] Call Tracer functionality works
- [ ] Settings persist
- [ ] Logs are accessible
- [ ] Clean shutdown works

## Next Steps After Testing

1. **Document results**: Note any platform-specific issues
2. **Update README-DOCKER.md**: Add any discovered gotchas
3. **Create demo video** (optional): Screen recording of kiosk mode
4. **User testing**: Get feedback from real users
5. **CI/CD integration** (optional): Automated Docker builds

## Validation Summary

**Current Status:**
- ✅ All files created correctly
- ✅ Python syntax validated
- ✅ Scripts are executable
- ⏳ Docker build pending (requires Docker installation)
- ⏳ Integration testing pending

**Ready for Testing:**
The implementation is complete and ready for testing when Docker is available.
