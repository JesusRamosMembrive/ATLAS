#!/bin/bash
# =============================================================================
# ATLAS Code Map - Desktop App Launcher
# =============================================================================
# Starts the Docker container and opens the app in kiosk mode (fullscreen)
#
# Usage:
#   ./start-app.sh          # Start app in kiosk mode
#   ./start-app.sh --window # Start app in windowed mode
#   ./start-app.sh --stop   # Stop the container
# =============================================================================

set -e

APP_URL="http://localhost:8080"
CONTAINER_NAME="code-map-app"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Find available browser
find_browser() {
    # Priority: Chromium > Google Chrome > Firefox
    if command -v chromium-browser &> /dev/null; then
        echo "chromium-browser"
    elif command -v chromium &> /dev/null; then
        echo "chromium"
    elif command -v google-chrome &> /dev/null; then
        echo "google-chrome"
    elif command -v google-chrome-stable &> /dev/null; then
        echo "google-chrome-stable"
    elif command -v firefox &> /dev/null; then
        echo "firefox"
    else
        echo ""
    fi
}

# Wait for the API to be ready
wait_for_api() {
    local max_attempts=30
    local attempt=1

    log_info "Waiting for API to be ready..."

    while [ $attempt -le $max_attempts ]; do
        if curl -s -f "$APP_URL/api/settings" > /dev/null 2>&1; then
            log_info "API is ready!"
            return 0
        fi
        echo -n "."
        sleep 1
        ((attempt++))
    done

    echo ""
    log_error "API did not become ready after ${max_attempts} seconds"
    return 1
}

# Start Docker container
start_container() {
    cd "$SCRIPT_DIR"

    # Check if container is already running
    if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        log_info "Container already running"
        return 0
    fi

    # Check if container exists but is stopped
    if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        log_info "Starting existing container..."
        docker start "$CONTAINER_NAME"
    else
        log_info "Starting new container with docker compose..."
        docker compose up -d
    fi
}

# Stop Docker container
stop_container() {
    cd "$SCRIPT_DIR"
    log_info "Stopping container..."
    docker compose down
    log_info "Container stopped"
}

# Launch browser in kiosk mode
launch_browser_kiosk() {
    local browser=$(find_browser)

    if [ -z "$browser" ]; then
        log_error "No compatible browser found (chromium, chrome, or firefox)"
        log_info "Please open $APP_URL manually in your browser"
        return 1
    fi

    log_info "Launching $browser in kiosk mode..."

    case "$browser" in
        chromium-browser|chromium|google-chrome|google-chrome-stable)
            # Chromium/Chrome kiosk mode
            # --app makes it look like a native app (no tabs, minimal UI)
            # --kiosk makes it fullscreen without any UI
            "$browser" \
                --kiosk \
                --no-first-run \
                --disable-infobars \
                --disable-session-crashed-bubble \
                --disable-restore-session-state \
                --noerrdialogs \
                --disable-translate \
                --start-fullscreen \
                "$APP_URL" &
            ;;
        firefox)
            # Firefox kiosk mode
            "$browser" --kiosk "$APP_URL" &
            ;;
    esac

    log_info "App launched! Press F11 to toggle fullscreen, Alt+F4 to close"
}

# Launch browser in windowed app mode
launch_browser_window() {
    local browser=$(find_browser)

    if [ -z "$browser" ]; then
        log_error "No compatible browser found (chromium, chrome, or firefox)"
        log_info "Please open $APP_URL manually in your browser"
        return 1
    fi

    log_info "Launching $browser in app mode..."

    case "$browser" in
        chromium-browser|chromium|google-chrome|google-chrome-stable)
            # App mode - looks like a native app but windowed
            "$browser" \
                --app="$APP_URL" \
                --no-first-run \
                --disable-infobars \
                --window-size=1400,900 \
                &
            ;;
        firefox)
            # Firefox doesn't have a true app mode, open normally
            "$browser" "$APP_URL" &
            ;;
    esac

    log_info "App launched!"
}

# Main script
main() {
    case "${1:-}" in
        --stop)
            stop_container
            exit 0
            ;;
        --window)
            MODE="window"
            ;;
        --kiosk|"")
            MODE="kiosk"
            ;;
        --help|-h)
            echo "Usage: $0 [--window|--kiosk|--stop|--help]"
            echo ""
            echo "Options:"
            echo "  --kiosk   Start in fullscreen kiosk mode (default)"
            echo "  --window  Start in windowed app mode"
            echo "  --stop    Stop the Docker container"
            echo "  --help    Show this help message"
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac

    # Start container
    start_container

    # Wait for API
    if ! wait_for_api; then
        log_error "Failed to start. Check logs with: docker logs $CONTAINER_NAME"
        exit 1
    fi

    # Launch browser
    if [ "$MODE" = "kiosk" ]; then
        launch_browser_kiosk
    else
        launch_browser_window
    fi
}

main "$@"
