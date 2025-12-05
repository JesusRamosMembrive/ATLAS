/**
 * Socket.IO Terminal Component
 *
 * Based on pyxtermjs pattern for reliable terminal communication.
 * Uses socket.io-client for automatic reconnection and typed events.
 *
 * Key differences from WebSocket approach:
 * 1. Socket.IO handles reconnection automatically
 * 2. Typed events (pty-input, pty-output, resize) instead of text protocol
 * 3. Simpler dimension handling - trusts FitAddon
 * 4. Better handling of TUI agents (Claude, Codex, Gemini)
 */

import { useEffect, useRef, useState, useCallback, memo } from "react";
import { Terminal } from "@xterm/xterm";
import { FitAddon } from "@xterm/addon-fit";
import { WebLinksAddon } from "@xterm/addon-web-links";
import { io, Socket } from "socket.io-client";
import { useBackendStore } from "../state/useBackendStore";
import { resolveBackendBaseUrl } from "../api/client";

import "@xterm/xterm/css/xterm.css";

// Constants
const MIN_COLS = 40;
const MIN_ROWS = 10;
const RESIZE_DEBOUNCE_MS = 50; // Like pyxtermjs

export interface TerminalSocketIOProps {
  autoConnect?: boolean;
  welcomeMessage?: string | null;
  onConnectionChange?: (connected: boolean) => void;
  className?: string;
  height?: string;
}

function TerminalSocketIOInner({
  autoConnect = false,
  welcomeMessage = "AEGIS Terminal (Socket.IO)",
  onConnectionChange,
  className = "",
  height = "500px",
}: TerminalSocketIOProps) {
  const [connected, setConnected] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [terminalDims, setTerminalDims] = useState({ cols: 80, rows: 24 });

  const backendUrl = useBackendStore((state) => state.backendUrl);

  const terminalRef = useRef<HTMLDivElement>(null);
  const xtermRef = useRef<Terminal | null>(null);
  const socketRef = useRef<Socket | null>(null);
  const fitAddonRef = useRef<FitAddon | null>(null);
  const resizeTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mountedRef = useRef(true);
  const dataListenerRef = useRef<{ dispose: () => void } | null>(null);

  // Connection status callback
  useEffect(() => {
    onConnectionChange?.(connected);
  }, [connected, onConnectionChange]);

  // Cleanup on unmount
  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      if (resizeTimeoutRef.current) {
        clearTimeout(resizeTimeoutRef.current);
      }
    };
  }, []);

  // Calculate WebSocket URL from backend URL
  const socketUrl = useCallback(() => {
    const stripApi = (value: string) =>
      value.endsWith("/api") ? value.slice(0, -4) : value;
    const base =
      resolveBackendBaseUrl(backendUrl) ??
      (typeof window !== "undefined"
        ? window.location.origin
        : "http://127.0.0.1:8010");
    return stripApi(base.replace(/\/+$/, ""));
  }, [backendUrl]);

  // Fit terminal and send resize to server
  const fitAndResize = useCallback(() => {
    const terminal = xtermRef.current;
    const fitAddon = fitAddonRef.current;
    const socket = socketRef.current;

    if (!terminal || !fitAddon) return;

    try {
      fitAddon.fit();

      // Validate dimensions
      let { cols, rows } = terminal;
      if (cols < MIN_COLS) cols = MIN_COLS;
      if (rows < MIN_ROWS) rows = MIN_ROWS;

      // Update state
      if (mountedRef.current) {
        setTerminalDims({ cols, rows });
      }

      // Send to server if connected
      if (socket?.connected) {
        console.log(`[TerminalSocketIO] Sending resize: ${cols}x${rows}`);
        socket.emit("resize", { cols, rows });
      }
    } catch (e) {
      console.error("[TerminalSocketIO] Fit error:", e);
    }
  }, []);

  // Debounced resize handler (like pyxtermjs with 50ms)
  const handleResize = useCallback(() => {
    if (resizeTimeoutRef.current) {
      clearTimeout(resizeTimeoutRef.current);
    }
    resizeTimeoutRef.current = setTimeout(fitAndResize, RESIZE_DEBOUNCE_MS);
  }, [fitAndResize]);

  // Initialize terminal
  useEffect(() => {
    if (!terminalRef.current || xtermRef.current) return;

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
      scrollback: 10000,
      disableStdin: false,
    });

    const fitAddon = new FitAddon();
    const webLinksAddon = new WebLinksAddon();

    terminal.loadAddon(fitAddon);
    terminal.loadAddon(webLinksAddon);
    terminal.open(container);

    xtermRef.current = terminal;
    fitAddonRef.current = fitAddon;

    // Initial fit
    requestAnimationFrame(() => {
      fitAddon.fit();
      if (mountedRef.current) {
        setTerminalDims({ cols: terminal.cols, rows: terminal.rows });
      }
    });

    // Welcome message
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
    }

    // Window resize listener
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      // Clean up data listener on unmount
      if (dataListenerRef.current) {
        dataListenerRef.current.dispose();
        dataListenerRef.current = null;
      }
      terminal.dispose();
      xtermRef.current = null;
      fitAddonRef.current = null;
    };
  }, [welcomeMessage, handleResize]);

  // Connect to Socket.IO server
  const connect = useCallback(() => {
    const terminal = xtermRef.current;
    if (!terminal) {
      setError("Terminal not initialized");
      return;
    }

    if (socketRef.current?.connected) {
      return;
    }

    setConnecting(true);
    setError(null);

    const url = socketUrl();
    console.log(`[TerminalSocketIO] Connecting to ${url} namespace /pty`);

    // Connect to /pty namespace
    // The namespace goes in the URL path, socket.io parses it correctly
    const socket = io(`${url}/pty`, {
      transports: ["websocket", "polling"],
      autoConnect: true,
      reconnection: true,
      reconnectionAttempts: 5,
      reconnectionDelay: 1000,
      forceNew: true,  // Force new connection to avoid reusing default namespace
    });

    socketRef.current = socket;

    // Handle connection
    socket.on("connect", () => {
      if (!mountedRef.current) {
        socket.disconnect();
        return;
      }

      console.log("[TerminalSocketIO] Connected to PTY server");
      setConnected(true);
      setConnecting(false);
      setError(null);

      // Clear terminal for PTY takeover
      terminal.reset();

      // Send initial dimensions (like pyxtermjs fitToscreen on connect)
      requestAnimationFrame(() => {
        fitAndResize();
      });
    });

    // Handle PTY output
    socket.on("pty-output", (data: { output: string }) => {
      if (mountedRef.current && data.output) {
        terminal.write(data.output);
      }
    });

    // Handle PTY exit
    socket.on("pty-exit", (data: { reason: string }) => {
      console.log(`[TerminalSocketIO] PTY exited: ${data.reason}`);
      if (mountedRef.current) {
        terminal.writeln(`\r\n\x1b[2m${data.reason}\x1b[0m`);
      }
    });

    // Handle disconnect
    socket.on("disconnect", (reason) => {
      console.log(`[TerminalSocketIO] Disconnected: ${reason}`);
      if (mountedRef.current) {
        setConnected(false);
        setConnecting(false);
        terminal.writeln("\r\n\x1b[2mDisconnected from server\x1b[0m");
      }
    });

    // Handle connection error
    socket.on("connect_error", (err) => {
      console.error("[TerminalSocketIO] Connection error:", err);
      if (mountedRef.current) {
        setConnected(false);
        setConnecting(false);
        setError(`Connection failed: ${err.message}`);
      }
    });

    // Clean up previous data listener if exists
    if (dataListenerRef.current) {
      dataListenerRef.current.dispose();
      dataListenerRef.current = null;
    }

    // Send input to PTY - use ref to ensure we always have current socket
    dataListenerRef.current = terminal.onData((data) => {
      const currentSocket = socketRef.current;
      if (currentSocket?.connected) {
        console.log("[TerminalSocketIO] Sending input:", JSON.stringify(data));
        currentSocket.emit("pty-input", { input: data });
      }
    });
  }, [socketUrl, fitAndResize]);

  // Disconnect from server
  const disconnect = useCallback(() => {
    // Clean up data listener
    if (dataListenerRef.current) {
      dataListenerRef.current.dispose();
      dataListenerRef.current = null;
    }

    if (socketRef.current) {
      socketRef.current.disconnect();
      socketRef.current = null;
    }

    setConnected(false);
    setConnecting(false);

    if (xtermRef.current && mountedRef.current) {
      xtermRef.current.writeln("\r\n\x1b[2mDisconnected.\x1b[0m");
    }
  }, []);

  // Auto-connect if enabled
  useEffect(() => {
    if (autoConnect && xtermRef.current && !connected && !connecting) {
      const timer = setTimeout(connect, 200);
      return () => clearTimeout(timer);
    }
  }, [autoConnect, connect, connected, connecting]);

  // ResizeObserver for container changes
  useEffect(() => {
    const container = terminalRef.current;
    if (!container) return;

    const observer = new ResizeObserver(handleResize);
    observer.observe(container);

    return () => observer.disconnect();
  }, [handleResize]);

  return (
    <div className={`terminal-socketio ${className}`}>
      <div className="terminal-socketio-header">
        <span className="terminal-socketio-title">Terminal (Socket.IO)</span>
        <div className="terminal-socketio-controls">
          <span
            className="terminal-socketio-dims"
            onClick={fitAndResize}
            title="Click to recalculate dimensions"
            style={{ cursor: "pointer" }}
          >
            {terminalDims.cols}×{terminalDims.rows}
          </span>

          {!connected && !connecting && (
            <button onClick={connect} className="terminal-socketio-btn connect">
              Connect
            </button>
          )}
          {connecting && (
            <span className="terminal-socketio-status connecting">
              <span className="terminal-socketio-dot pulse" />
              Connecting...
            </span>
          )}
          {connected && (
            <>
              <span className="terminal-socketio-status connected">
                <span className="terminal-socketio-dot" />
                Active
              </span>
              <button
                onClick={disconnect}
                className="terminal-socketio-btn disconnect"
              >
                Disconnect
              </button>
            </>
          )}
          {error && (
            <span className="terminal-socketio-status error">✗ {error}</span>
          )}
        </div>
      </div>
      <div className="terminal-socketio-xterm-wrapper" style={{ height }}>
        <div ref={terminalRef} className="terminal-socketio-content" />
      </div>
    </div>
  );
}

export const TerminalSocketIO = memo(TerminalSocketIOInner);

export const terminalSocketIOStyles = `
.terminal-socketio {
  display: flex;
  flex-direction: column;
  background: #0a0e18;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid rgba(59, 130, 246, 0.2);
}

.terminal-socketio-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: rgba(15, 23, 42, 0.8);
  border-bottom: 1px solid rgba(59, 130, 246, 0.2);
  flex-shrink: 0;
}

.terminal-socketio-title {
  font-size: 12px;
  font-weight: 600;
  color: #94a3b8;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.terminal-socketio-controls {
  display: flex;
  align-items: center;
  gap: 8px;
}

.terminal-socketio-dims {
  font-size: 11px;
  font-family: 'JetBrains Mono', monospace;
  color: #10b981;
  padding: 2px 8px;
  background: rgba(16, 185, 129, 0.15);
  border: 1px solid rgba(16, 185, 129, 0.3);
  border-radius: 4px;
}

.terminal-socketio-btn {
  padding: 4px 12px;
  font-size: 12px;
  font-weight: 500;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
  border: none;
}

.terminal-socketio-btn.connect {
  background: rgba(59, 130, 246, 0.2);
  color: #60a5fa;
}

.terminal-socketio-btn.connect:hover {
  background: rgba(59, 130, 246, 0.3);
}

.terminal-socketio-btn.disconnect {
  background: rgba(239, 68, 68, 0.2);
  color: #f87171;
}

.terminal-socketio-btn.disconnect:hover {
  background: rgba(239, 68, 68, 0.3);
}

.terminal-socketio-status {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
}

.terminal-socketio-status.connecting { color: #fbbf24; }
.terminal-socketio-status.connected { color: #34d399; }
.terminal-socketio-status.error { color: #f87171; }

.terminal-socketio-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: currentColor;
}

.terminal-socketio-dot.pulse {
  animation: terminal-socketio-pulse 1.5s ease-in-out infinite;
}

@keyframes terminal-socketio-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

.terminal-socketio-xterm-wrapper {
  padding: 8px;
  box-sizing: border-box;
  overflow: hidden;
  min-height: 300px;
  background: #0a0e18;
}

.terminal-socketio-content {
  width: 100%;
  height: 100%;
  overflow: hidden;
  background: #0a0e18;
}

.terminal-socketio-content .xterm,
.terminal-socketio-content .xterm-viewport,
.terminal-socketio-content .xterm-screen {
  width: 100% !important;
  height: 100% !important;
}

.terminal-socketio-content .xterm-viewport {
  overflow-y: auto !important;
}

.terminal-socketio-content .xterm-viewport::-webkit-scrollbar {
  width: 8px;
}

.terminal-socketio-content .xterm-viewport::-webkit-scrollbar-track {
  background: rgba(15, 23, 42, 0.5);
}

.terminal-socketio-content .xterm-viewport::-webkit-scrollbar-thumb {
  background: rgba(148, 163, 184, 0.3);
  border-radius: 4px;
}
`;
