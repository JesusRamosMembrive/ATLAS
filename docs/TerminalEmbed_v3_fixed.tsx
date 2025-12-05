import { useEffect, useMemo, useRef, useState, useCallback, memo } from "react";
import { Terminal } from "@xterm/xterm";
import { FitAddon } from "@xterm/addon-fit";
import { WebLinksAddon } from "@xterm/addon-web-links";
import { useBackendStore } from "../state/useBackendStore";
import { resolveBackendBaseUrl } from "../api/client";

import "@xterm/xterm/css/xterm.css";

// Minimum valid dimensions for TUI agents (Claude Code, Gemini CLI, etc.)
const MIN_VALID_COLS = 40;
const MIN_VALID_ROWS = 10;
const DEFAULT_COLS = 80;
const DEFAULT_ROWS = 24;

export interface TerminalEmbedProps {
  /** Auto-connect on mount */
  autoConnect?: boolean;
  /** Custom welcome message (null to disable) - shown BEFORE connecting */
  welcomeMessage?: string | null;
  /** Callback when connection state changes */
  onConnectionChange?: (connected: boolean) => void;
  /** Custom class name for the container */
  className?: string;
  /** Height of the terminal (CSS value) */
  height?: string;
}

/**
 * Reusable Terminal Embed Component
 *
 * IMPORTANT: After WebSocket connects, ALL output must come from PTY.
 * Writing to terminal from frontend after connection causes cursor
 * position desync with bash/readline, leading to duplicated text.
 */
function TerminalEmbedInner({
  autoConnect = false,
  welcomeMessage = "AEGIS Terminal",
  onConnectionChange,
  className = "",
  height = "500px",
}: TerminalEmbedProps) {
  const [connected, setConnected] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [containerReady, setContainerReady] = useState(false);
  const [terminalDims, setTerminalDims] = useState({ cols: DEFAULT_COLS, rows: DEFAULT_ROWS });

  const backendUrl = useBackendStore((state) => state.backendUrl);

  const terminalRef = useRef<HTMLDivElement>(null);
  const xtermRef = useRef<Terminal | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const fitAddonRef = useRef<FitAddon | null>(null);
  const resizeTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mountedRef = useRef(true);
  const disposablesRef = useRef<{
    data?: { dispose: () => void };
    resize?: { dispose: () => void };
    observer?: ResizeObserver;
  }>({});

  // Track mounted state
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  // Notify parent of connection changes
  useEffect(() => {
    onConnectionChange?.(connected);
  }, [connected, onConnectionChange]);

  const wsBaseUrl = useMemo(() => {
    const stripApi = (value: string) =>
      value.endsWith("/api") ? value.slice(0, -4) : value;

    const base =
      resolveBackendBaseUrl(backendUrl) ??
      (typeof window !== "undefined"
        ? window.location.origin
        : "http://127.0.0.1:8010");

    const sanitized = base.replace(/\/+$/, "");
    return stripApi(sanitized);
  }, [backendUrl]);

  // Wait for container to have valid dimensions before initializing terminal
  useEffect(() => {
    const container = terminalRef.current;
    if (!container) return;

    const checkDimensions = () => {
      const rect = container.getBoundingClientRect();
      if (rect.width >= 200 && rect.height >= 150) {
        setContainerReady(true);
        return true;
      }
      return false;
    };

    if (checkDimensions()) return;

    const observer = new ResizeObserver(() => {
      if (checkDimensions()) {
        observer.disconnect();
      }
    });
    observer.observe(container);

    const timeout = setTimeout(() => {
      observer.disconnect();
      setContainerReady(true);
    }, 1000);

    return () => {
      observer.disconnect();
      clearTimeout(timeout);
    };
  }, []);

  // Initialize terminal ONLY when container is ready
  useEffect(() => {
    if (!containerReady || !terminalRef.current || xtermRef.current) return;

    const container = terminalRef.current;

    const terminal = new Terminal({
      cursorBlink: true,
      fontSize: 14,
      fontFamily: '"JetBrains Mono", "Fira Code", "Cascadia Code", monospace',
      theme: {
        background: "#0a0e18",
        foreground: "#e2e8f0",
        cursor: "#3b82f6",
        black: "#1e293b",
        red: "#ef4444",
        green: "#10b981",
        yellow: "#f59e0b",
        blue: "#3b82f6",
        magenta: "#a855f7",
        cyan: "#06b6d4",
        white: "#f1f5f9",
        brightBlack: "#475569",
        brightRed: "#f87171",
        brightGreen: "#34d399",
        brightYellow: "#fbbf24",
        brightBlue: "#60a5fa",
        brightMagenta: "#c084fc",
        brightCyan: "#22d3ee",
        brightWhite: "#ffffff",
      },
      cols: DEFAULT_COLS,
      rows: DEFAULT_ROWS,
      scrollback: 10000,
      disableStdin: false,
      // Enable proper handling of all escape sequences
      allowProposedApi: true,
    });

    const fitAddon = new FitAddon();
    const webLinksAddon = new WebLinksAddon();

    terminal.loadAddon(fitAddon);
    terminal.loadAddon(webLinksAddon);

    terminal.open(container);

    xtermRef.current = terminal;
    fitAddonRef.current = fitAddon;

    // Fit after DOM is stable (multiple frames)
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        if (!mountedRef.current) return;
        
        try {
          const rect = container.getBoundingClientRect();
          if (rect.width >= 200 && rect.height >= 150) {
            fitAddon.fit();
            const { cols, rows } = terminal;
            
            if (cols >= MIN_VALID_COLS && rows >= MIN_VALID_ROWS) {
              setTerminalDims({ cols, rows });
            } else {
              terminal.resize(DEFAULT_COLS, DEFAULT_ROWS);
              setTerminalDims({ cols: DEFAULT_COLS, rows: DEFAULT_ROWS });
            }
          }
        } catch (err) {
          console.error("[TerminalEmbed] Error fitting terminal:", err);
        }
      });
    });

    // Welcome message - ONLY shown before connecting
    // This is safe because we'll reset() before connecting
    if (welcomeMessage) {
      terminal.writeln(
        `\x1b[1;36m╔════════════════════════════════════════════════════════╗\x1b[0m`
      );
      terminal.writeln(
        `\x1b[1;36m║\x1b[0m    \x1b[1;33m${welcomeMessage.padEnd(50)}\x1b[0m\x1b[1;36m║\x1b[0m`
      );
      terminal.writeln(
        `\x1b[1;36m╚════════════════════════════════════════════════════════╝\x1b[0m`
      );
      terminal.writeln("");
      terminal.writeln("\x1b[2mClick 'Connect' to start shell session...\x1b[0m");
      terminal.writeln("");
    }

    return () => {
      terminal.dispose();
      xtermRef.current = null;
      fitAddonRef.current = null;
    };
  }, [containerReady, welcomeMessage]);

  // Cleanup WebSocket and timers on unmount
  useEffect(() => {
    return () => {
      if (resizeTimeoutRef.current) {
        clearTimeout(resizeTimeoutRef.current);
        resizeTimeoutRef.current = null;
      }

      if (disposablesRef.current.data) {
        disposablesRef.current.data.dispose();
        disposablesRef.current.data = undefined;
      }
      if (disposablesRef.current.resize) {
        disposablesRef.current.resize.dispose();
        disposablesRef.current.resize = undefined;
      }
      if (disposablesRef.current.observer) {
        disposablesRef.current.observer.disconnect();
        disposablesRef.current.observer = undefined;
      }

      if (wsRef.current) {
        const socket = wsRef.current;
        if (
          socket.readyState === WebSocket.OPEN ||
          socket.readyState === WebSocket.CONNECTING
        ) {
          socket.close(1000, "Component unmounting");
        }
        wsRef.current = null;
      }
    };
  }, []);

  // Safe fit with dimension validation
  const safeFit = useCallback((): { cols: number; rows: number } => {
    const container = terminalRef.current;
    const terminal = xtermRef.current;
    const fitAddon = fitAddonRef.current;

    if (!container || !terminal || !fitAddon) {
      return { cols: DEFAULT_COLS, rows: DEFAULT_ROWS };
    }

    const rect = container.getBoundingClientRect();

    if (rect.width < 200 || rect.height < 150) {
      return { cols: DEFAULT_COLS, rows: DEFAULT_ROWS };
    }

    try {
      fitAddon.fit();
    } catch (err) {
      console.error("[TerminalEmbed] Error during fit:", err);
      return { cols: DEFAULT_COLS, rows: DEFAULT_ROWS };
    }

    const { cols, rows } = terminal;

    if (cols < MIN_VALID_COLS || rows < MIN_VALID_ROWS) {
      terminal.resize(DEFAULT_COLS, DEFAULT_ROWS);
      return { cols: DEFAULT_COLS, rows: DEFAULT_ROWS };
    }

    if (mountedRef.current) {
      setTerminalDims({ cols, rows });
    }

    return { cols, rows };
  }, []);

  const connect = useCallback(() => {
    if (!xtermRef.current) {
      setError("Terminal not initialized");
      return;
    }

    if (
      wsRef.current &&
      (wsRef.current.readyState === WebSocket.OPEN ||
        wsRef.current.readyState === WebSocket.CONNECTING)
    ) {
      return;
    }

    const terminal = xtermRef.current;
    const wsUrl = wsBaseUrl
      .replace("http://", "ws://")
      .replace("https://", "wss://");

    setConnecting(true);
    setError(null);

    const socket = new WebSocket(`${wsUrl}/api/terminal/ws`);

    socket.onopen = () => {
      if (!mountedRef.current) {
        socket.close();
        return;
      }

      setConnected(true);
      setConnecting(false);
      setError(null);

      // CRITICAL FIX: Reset terminal completely before PTY takes over
      // This ensures:
      // 1. No leftover content from welcome message
      // 2. Cursor at position (0,0)
      // 3. Scrollback cleared
      // 4. PTY has full control of terminal state
      terminal.reset();

      // Send dimensions AFTER reset, in next frame
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          if (!mountedRef.current) return;
          
          const dims = safeFit();
          console.log(`[TerminalEmbed] Sending resize: ${dims.cols}x${dims.rows}`);
          socket.send(`__RESIZE__:${dims.cols}:${dims.rows}`);
          
          // DO NOT write anything to terminal here!
          // All output must come from PTY to keep cursor position in sync
        });
      });
    };

    socket.onmessage = (event) => {
      // Simply write PTY output - no processing needed
      // xterm.js handles all escape sequences correctly
      if (mountedRef.current) {
        xtermRef.current?.write(event.data);
      }
    };

    socket.onerror = () => {
      if (mountedRef.current) {
        setConnected(false);
        setConnecting(false);
        setError("Connection error");
        // It's safe to write here because we're not connected to PTY
        xtermRef.current?.writeln("\r\n\x1b[1;31m✗ Connection error\x1b[0m");
      }
    };

    socket.onclose = (event) => {
      if (mountedRef.current) {
        setConnected(false);
        setConnecting(false);
        // Safe to write after disconnect - PTY is gone
        if (event.code !== 1000) {
          xtermRef.current?.writeln("\r\n\x1b[2mConnection closed\x1b[0m");
        }
      }
    };

    wsRef.current = socket;

    // Handle terminal input - send directly to PTY
    disposablesRef.current.data = terminal.onData((data) => {
      if (socket.readyState === WebSocket.OPEN) {
        socket.send(data);
      }
    });

    // Handle resize events
    const sendResize = () => {
      if (socket?.readyState === WebSocket.OPEN && mountedRef.current) {
        const dims = safeFit();
        socket.send(`__RESIZE__:${dims.cols}:${dims.rows}`);
      }
    };

    disposablesRef.current.resize = terminal.onResize(({ cols, rows }) => {
      if (cols >= MIN_VALID_COLS && rows >= MIN_VALID_ROWS) {
        if (socket?.readyState === WebSocket.OPEN) {
          socket.send(`__RESIZE__:${cols}:${rows}`);
          if (mountedRef.current) {
            setTerminalDims({ cols, rows });
          }
        }
      }
    });

    // Debounced ResizeObserver
    disposablesRef.current.observer = new ResizeObserver(() => {
      if (resizeTimeoutRef.current) {
        clearTimeout(resizeTimeoutRef.current);
      }
      resizeTimeoutRef.current = setTimeout(() => {
        sendResize();
      }, 200);
    });

    if (terminalRef.current) {
      disposablesRef.current.observer.observe(terminalRef.current);
    }
  }, [wsBaseUrl, safeFit]);

  const disconnect = useCallback(() => {
    if (disposablesRef.current.data) {
      disposablesRef.current.data.dispose();
      disposablesRef.current.data = undefined;
    }
    if (disposablesRef.current.resize) {
      disposablesRef.current.resize.dispose();
      disposablesRef.current.resize = undefined;
    }
    if (disposablesRef.current.observer) {
      disposablesRef.current.observer.disconnect();
      disposablesRef.current.observer = undefined;
    }

    if (wsRef.current) {
      const socket = wsRef.current;
      if (
        socket.readyState === WebSocket.OPEN ||
        socket.readyState === WebSocket.CONNECTING
      ) {
        socket.close();
      }
      wsRef.current = null;
    }

    setConnected(false);
    setConnecting(false);
    
    // Show disconnect message and prompt to reconnect
    if (xtermRef.current && mountedRef.current) {
      xtermRef.current.writeln("");
      xtermRef.current.writeln("\x1b[2mDisconnected. Click 'Connect' to start new session.\x1b[0m");
    }
  }, []);

  // Auto-connect on mount if enabled
  useEffect(() => {
    if (autoConnect && xtermRef.current && !connected && !connecting) {
      const timer = setTimeout(() => {
        connect();
      }, 200);
      return () => clearTimeout(timer);
    }
  }, [autoConnect, connect, connected, connecting]);

  return (
    <div className={`terminal-embed ${className}`}>
      <div className="terminal-embed-header">
        <span className="terminal-embed-title">Terminal</span>
        <div className="terminal-embed-controls">
          <span className="terminal-embed-dims">
            {terminalDims.cols}×{terminalDims.rows}
          </span>
          {!connected && !connecting && (
            <button onClick={connect} className="terminal-embed-btn connect">
              Connect
            </button>
          )}
          {connecting && (
            <span className="terminal-embed-status connecting">
              <span className="terminal-embed-dot pulse" />
              Connecting...
            </span>
          )}
          {connected && (
            <>
              <span className="terminal-embed-status connected">
                <span className="terminal-embed-dot" />
                Active
              </span>
              <button
                onClick={disconnect}
                className="terminal-embed-btn disconnect"
              >
                Disconnect
              </button>
            </>
          )}
          {!connected && !connecting && error && (
            <span className="terminal-embed-status error">✗ {error}</span>
          )}
        </div>
      </div>
      <div className="terminal-embed-xterm-wrapper" style={{ height }}>
        <div ref={terminalRef} className="terminal-embed-content" />
      </div>
    </div>
  );
}

export const TerminalEmbed = memo(TerminalEmbedInner);

export const terminalEmbedStyles = `
.terminal-embed {
  display: flex;
  flex-direction: column;
  background: #0a0e18;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid rgba(59, 130, 246, 0.2);
}

.terminal-embed-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: rgba(15, 23, 42, 0.8);
  border-bottom: 1px solid rgba(59, 130, 246, 0.2);
  flex-shrink: 0;
}

.terminal-embed-title {
  font-size: 12px;
  font-weight: 600;
  color: #94a3b8;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.terminal-embed-controls {
  display: flex;
  align-items: center;
  gap: 8px;
}

.terminal-embed-dims {
  font-size: 11px;
  font-family: 'JetBrains Mono', monospace;
  color: #64748b;
  padding: 2px 6px;
  background: rgba(100, 116, 139, 0.15);
  border-radius: 4px;
}

.terminal-embed-btn {
  padding: 4px 12px;
  font-size: 12px;
  font-weight: 500;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
  border: none;
}

.terminal-embed-btn.connect {
  background: rgba(59, 130, 246, 0.2);
  color: #60a5fa;
}

.terminal-embed-btn.connect:hover {
  background: rgba(59, 130, 246, 0.3);
}

.terminal-embed-btn.disconnect {
  background: rgba(239, 68, 68, 0.2);
  color: #f87171;
}

.terminal-embed-btn.disconnect:hover {
  background: rgba(239, 68, 68, 0.3);
}

.terminal-embed-status {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
}

.terminal-embed-status.connecting {
  color: #fbbf24;
}

.terminal-embed-status.connected {
  color: #34d399;
}

.terminal-embed-status.error {
  color: #f87171;
}

.terminal-embed-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: currentColor;
}

.terminal-embed-dot.pulse {
  animation: terminal-pulse 1.5s ease-in-out infinite;
}

@keyframes terminal-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

.terminal-embed-xterm-wrapper {
  padding: 8px;
  box-sizing: border-box;
  overflow: hidden;
  min-height: 300px;
  background: #0a0e18;
}

.terminal-embed-content {
  width: 100%;
  height: 100%;
  overflow: hidden;
  background: #0a0e18;
  /* NO PADDING - xterm needs exact dimensions */
}

.terminal-embed-content .xterm,
.terminal-embed-content .xterm-viewport,
.terminal-embed-content .xterm-screen {
  width: 100% !important;
  height: 100% !important;
}

.terminal-embed-content .xterm-viewport {
  overflow-y: auto !important;
}

.terminal-embed-content .xterm-viewport::-webkit-scrollbar {
  width: 8px;
}

.terminal-embed-content .xterm-viewport::-webkit-scrollbar-track {
  background: rgba(15, 23, 42, 0.5);
}

.terminal-embed-content .xterm-viewport::-webkit-scrollbar-thumb {
  background: rgba(148, 163, 184, 0.3);
  border-radius: 4px;
}
`;
