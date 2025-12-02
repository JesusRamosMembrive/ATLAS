import { useEffect, useMemo, useRef, useState } from "react";
import { Terminal } from "@xterm/xterm";
import { FitAddon } from "@xterm/addon-fit";
import { WebLinksAddon } from "@xterm/addon-web-links";
import { useBackendStore } from "../state/useBackendStore";
import { resolveBackendBaseUrl } from "../api/client";

import "@xterm/xterm/css/xterm.css";

/**
 * Remote Terminal View
 *
 * Provides a web-based terminal with full shell access
 * Connects to backend via WebSocket for bidirectional communication
 */
export function RemoteTerminalView() {
  console.log("[COMPONENT] RemoteTerminalView rendering");

  const [connected, setConnected] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);


  const backendUrl = useBackendStore((state) => state.backendUrl);



  const terminalRef = useRef<HTMLDivElement>(null);
  const xtermRef = useRef<Terminal | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const fitAddonRef = useRef<FitAddon | null>(null);
  const disposablesRef = useRef<{ data?: any; resize?: any; observer?: ResizeObserver }>({});

  // Claude Code redraw detection
  const lastFrameRef = useRef<string>("");
  const redrawPatternRef = useRef(new RegExp('\\x1b\\[2K.*\\x1b\\[1A', 'g'));

  const wsBaseUrl = useMemo(() => {
    console.log(`[WS] useMemo recomputing wsBaseUrl, backendUrl=${backendUrl}`);
    const stripApi = (value: string) =>
      value.endsWith("/api") ? value.slice(0, -4) : value;

    const base =
      resolveBackendBaseUrl(backendUrl) ??
      (typeof window !== "undefined" ? window.location.origin : "http://127.0.0.1:8010");

    const sanitized = base.replace(/\/+$/, "");
    const result = stripApi(sanitized);
    console.log(`[WS] useMemo result: ${result}`);
    return result;
  }, [backendUrl]);

  // Initialize terminal
  useEffect(() => {
    if (!terminalRef.current || xtermRef.current) return;

    // Ensure container has dimensions before initializing terminal
    const container = terminalRef.current;
    const rect = container.getBoundingClientRect();

    if (rect.width === 0 || rect.height === 0) {
      // Container not yet laid out, wait for next frame
      console.log("Terminal container not ready, waiting...");
      const timer = setTimeout(() => {
        // Trigger re-render by forcing dependency update
        container.style.minHeight = "600px";
      }, 0);
      return () => clearTimeout(timer);
    }

    console.log(`Initializing terminal with container dimensions: ${rect.width}x${rect.height}`);

    const terminal = new Terminal({
      cursorBlink: false, // Disable cursor since terminal is read-only
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
      rows: 30,
      scrollback: 10000,
      disableStdin: false, // Enable terminal input
    });

    const fitAddon = new FitAddon();
    const webLinksAddon = new WebLinksAddon();

    terminal.loadAddon(fitAddon);
    terminal.loadAddon(webLinksAddon);

    terminal.open(container);

    // Wait a frame for terminal to be fully attached before fitting
    requestAnimationFrame(() => {
      try {
        fitAddon.fit();
        console.log("Terminal fitted successfully");
      } catch (err) {
        console.error("Error fitting terminal:", err);
      }
    });

    xtermRef.current = terminal;
    fitAddonRef.current = fitAddon;

    // Welcome message
    terminal.writeln("\x1b[1;36m╔═══════════════════════════════════════════════════════╗\x1b[0m");
    terminal.writeln("\x1b[1;36m║\x1b[0m    \x1b[1;33mAEGIS Remote Terminal\x1b[0m                           \x1b[1;36m║\x1b[0m");
    terminal.writeln("\x1b[1;36m╚═══════════════════════════════════════════════════════╝\x1b[0m");
    terminal.writeln("");
    terminal.writeln("\x1b[2mClick 'Connect' button to start shell session...\x1b[0m");
    terminal.writeln("");

    // Cleanup on unmount
    return () => {
      terminal.dispose();
      xtermRef.current = null;
      fitAddonRef.current = null;
    };
  }, []);

  // Cleanup WebSocket on component unmount (e.g., page reload)
  useEffect(() => {
    console.log("[WS] Component mounted, setting up unmount cleanup");

    return () => {
      console.log("[WS] Component unmounting - cleaning up WebSocket connection");

      // Clean up disposables
      if (disposablesRef.current.data) {
        console.log("[WS] Disposing data listener");
        disposablesRef.current.data.dispose();
        disposablesRef.current.data = undefined;
      }
      if (disposablesRef.current.resize) {
        console.log("[WS] Disposing resize listener");
        disposablesRef.current.resize.dispose();
        disposablesRef.current.resize = undefined;
      }
      if (disposablesRef.current.observer) {
        console.log("[WS] Disconnecting resize observer");
        disposablesRef.current.observer.disconnect();
        disposablesRef.current.observer = undefined;
      }

      // Close WebSocket
      if (wsRef.current) {
        const socket = wsRef.current;
        const state = socket.readyState;
        console.log(`[WS] Closing WebSocket on unmount (state=${state}: ${state === 0 ? 'CONNECTING' : state === 1 ? 'OPEN' : state === 2 ? 'CLOSING' : 'CLOSED'})`);

        if (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING) {
          socket.close(1000, "Component unmounting");
        }
        wsRef.current = null;
      } else {
        console.log("[WS] No WebSocket to close on unmount");
      }
    };
  }, []);

  // Manual connection function - called by user clicking "Connect" button
  const connectToShell = () => {
    console.log(`[WS] Manual connect triggered - wsBaseUrl=${wsBaseUrl}`);

    if (!xtermRef.current) {
      console.error("[WS] Cannot connect: terminal not ready");
      setError("Terminal not initialized");
      return;
    }

    // Check if already connected
    if (wsRef.current && (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING)) {
      console.log(`[WS] Already connected or connecting (state=${wsRef.current.readyState})`);
      return;
    }

    const terminal = xtermRef.current;
    const wsUrl = wsBaseUrl.replace("http://", "ws://").replace("https://", "wss://");
    console.log(`[WS] Creating WebSocket to ${wsUrl}/api/terminal/ws`);

    setConnecting(true);
    setError(null);

    // Create WebSocket connection
    const socket = new WebSocket(`${wsUrl}/api/terminal/ws`);
    console.log(`[WS] WebSocket created, initial state: ${socket.readyState} (0=CONNECTING, 1=OPEN, 2=CLOSING, 3=CLOSED)`);

    // IMPORTANT: Set all event handlers BEFORE assigning to ref
    // This prevents race conditions where events fire before handlers are set
    socket.onopen = () => {
      console.log("[WS] ✅ WebSocket ONOPEN fired - connected successfully");
      setConnected(true);
      setConnecting(false);
      setError(null);

      const { cols, rows } = xtermRef.current ?? terminal;
      socket.send(`__RESIZE__:${cols}:${rows}`);

      // Clear terminal and show connected message
      terminal.clear();
      terminal.writeln("\x1b[1;32m✓ Connected to shell\x1b[0m");
      terminal.writeln("");
    };

    socket.onmessage = (event) => {
      const message = event.data;



      // Detect Claude Code redraw pattern (multiple line clears + cursor ups)
      // When detected, clear terminal and write fresh content
      const isRedraw = redrawPatternRef.current.test(message);
      if (isRedraw) {
        // This is a redraw frame from Claude Code
        // Clear terminal to prevent duplicate/stacking content
        xtermRef.current?.clear();

        // Strip the redraw control sequences and write clean content
        const cleanMessage = message
          .replace(/\x1b\[2K/g, '')      // Remove "erase line"
          .replace(/\x1b\[\d*A/g, '')    // Remove "cursor up"
          .replace(/\x1b\[\d*G/g, '')    // Remove "cursor to column"
          .replace(/\x1b\[\?2026[hl]/g, '') // Remove synchronized output
          .replace(/\x1b\[\?25[hl]/g, '');  // Remove cursor visibility

        lastFrameRef.current = cleanMessage;
        xtermRef.current?.write(cleanMessage);
      } else {
        // Regular output - just write it
        xtermRef.current?.write(message);
      }
    };

    socket.onerror = (err) => {
      console.error("[WS] ❌ WebSocket ONERROR fired:", err);
      setConnected(false);
      setConnecting(false);
      setError("Connection error");
      xtermRef.current?.writeln("");
      xtermRef.current?.writeln("\x1b[1;31m✗ Connection error\x1b[0m");
    };

    socket.onclose = (event) => {
      console.log(`[WS] 🔴 WebSocket ONCLOSE fired: code=${event.code}, reason=${event.reason || "none"}, wasClean=${event.wasClean}`);
      setConnected(false);
      setConnecting(false);
      if (!error) {
        xtermRef.current?.writeln("");
        xtermRef.current?.writeln("\x1b[2mConnection closed\x1b[0m");
      }
    };

    // Now save to ref after all handlers are configured
    wsRef.current = socket;

    // Handle terminal input
    disposablesRef.current.data = xtermRef.current.onData((data) => {
      if (socket.readyState === WebSocket.OPEN) {
        socket.send(data);
      }
    });

    const sendResize = () => {
      if (socket?.readyState === WebSocket.OPEN && xtermRef.current) {
        const { cols, rows } = xtermRef.current;
        socket.send(`__RESIZE__:${cols}:${rows}`);
      }
    };

    disposablesRef.current.resize = xtermRef.current.onResize(() => {
      sendResize();
    });

    disposablesRef.current.observer = new ResizeObserver(() => {
      if (fitAddonRef.current) {
        fitAddonRef.current.fit();
        sendResize();
      }
    });

    if (terminalRef.current) {
      disposablesRef.current.observer.observe(terminalRef.current);
    }
  };





  // Disconnect function
  const disconnectFromShell = () => {
    console.log("[WS] Manual disconnect triggered");



    // Clean up disposables
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

    // Close WebSocket
    if (wsRef.current) {
      const socket = wsRef.current;
      if (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING) {
        console.log("[WS] Closing socket");
        socket.close();
      }
      wsRef.current = null;
    }

    setConnected(false);
    setConnecting(false);
  };

  return (
    <div className="terminal-view">


      {/* Terminal Container */}
      <div className="terminal-container">
        <div className="terminal-header">
          <span className="terminal-title">Shell</span>
          <div className="terminal-controls">
            {!connected && !connecting && (
              <button
                onClick={connectToShell}
                className="secondary-btn"
                style={{ marginRight: "0.5rem" }}
              >
                Connect
              </button>
            )}
            {connecting && (
              <span className="terminal-status">
                <span className="terminal-status-dot" style={{ animation: "pulse 1.5s ease-in-out infinite" }} />
                Connecting...
              </span>
            )}
            {connected && (
              <>
                <span className="terminal-status">
                  <span className="terminal-status-dot" />
                  Active
                </span>
                <button
                  onClick={disconnectFromShell}
                  className="secondary-btn"
                  style={{ marginLeft: "0.5rem" }}
                >
                  Disconnect
                </button>
              </>
            )}
            {!connected && !connecting && error && (
              <span className="terminal-status terminal-status--error">
                ✗ {error}
              </span>
            )}
          </div>
        </div>
        <div ref={terminalRef} className="terminal-content" />


      </div>



      {/* Security Warning */}
      <section className="terminal-warning-section">
        <div className="terminal-warning">
          <div className="terminal-warning-icon">⚠️</div>
          <div className="terminal-warning-content">
            <h3>Security Notice</h3>
            <p>
              This terminal has full access to your system with the same permissions
              as the backend process. Only use on trusted networks and be careful
              with sensitive operations.
            </p>
          </div>
        </div>
      </section>
    </div>
  );
}
