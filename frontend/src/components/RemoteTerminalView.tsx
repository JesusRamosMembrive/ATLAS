import { useEffect, useRef, useState } from "react";
import { Terminal } from "@xterm/xterm";
import { FitAddon } from "@xterm/addon-fit";
import { WebLinksAddon } from "@xterm/addon-web-links";
import { useBackendStore } from "../state/useBackendStore";
import "@xterm/xterm/css/xterm.css";

/**
 * Remote Terminal View
 *
 * Provides a web-based terminal with full shell access
 * Connects to backend via WebSocket for bidirectional communication
 */
export function RemoteTerminalView() {
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const terminalRef = useRef<HTMLDivElement>(null);
  const xtermRef = useRef<Terminal | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const fitAddonRef = useRef<FitAddon | null>(null);

  // Initialize terminal
  useEffect(() => {
    if (!terminalRef.current || xtermRef.current) return;

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
      rows: 30,
      scrollback: 10000,
    });

    const fitAddon = new FitAddon();
    const webLinksAddon = new WebLinksAddon();

    terminal.loadAddon(fitAddon);
    terminal.loadAddon(webLinksAddon);

    terminal.open(terminalRef.current);
    fitAddon.fit();

    xtermRef.current = terminal;
    fitAddonRef.current = fitAddon;

    // Welcome message
    terminal.writeln("\x1b[1;36m╔═══════════════════════════════════════════════════════╗\x1b[0m");
    terminal.writeln("\x1b[1;36m║\x1b[0m    \x1b[1;33mATLAS Remote Terminal\x1b[0m                           \x1b[1;36m║\x1b[0m");
    terminal.writeln("\x1b[1;36m╚═══════════════════════════════════════════════════════╝\x1b[0m");
    terminal.writeln("");
    terminal.writeln("\x1b[2mConnecting to shell...\x1b[0m");
    terminal.writeln("");

    // Cleanup on unmount
    return () => {
      terminal.dispose();
    };
  }, []);

  // Connect to WebSocket
  useEffect(() => {
    if (!xtermRef.current) return;

    const terminal = xtermRef.current;
    const backendUrl = useBackendStore.getState().backendUrl || "http://localhost:8010";
    const wsUrl = backendUrl.replace("http://", "ws://").replace("https://", "wss://");
    const ws = new WebSocket(`${wsUrl}/api/terminal/ws`);

    ws.onopen = () => {
      setConnected(true);
      setError(null);
      terminal.writeln("\x1b[1;32m✓ Connected to shell\x1b[0m");
      terminal.writeln("");

      // Send initial terminal size
      const { cols, rows } = terminal;
      ws.send(JSON.stringify({
        type: "resize",
        cols,
        rows,
      }));
    };

    ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);

        switch (message.type) {
          case "output":
            // Write shell output to terminal
            terminal.write(message.data);
            break;

          case "exit":
            // Shell exited
            terminal.writeln("");
            terminal.writeln("\x1b[1;33m⚠ Shell process exited\x1b[0m");
            setConnected(false);
            ws.close();
            break;

          case "error":
            // Error occurred
            terminal.writeln("");
            terminal.writeln(`\x1b[1;31m✗ Error: ${message.message}\x1b[0m`);
            setError(message.message);
            break;
        }
      } catch (err) {
        console.error("Failed to parse WebSocket message:", err);
      }
    };

    ws.onerror = (err) => {
      console.error("WebSocket error:", err);
      setError("Connection error");
      terminal.writeln("");
      terminal.writeln("\x1b[1;31m✗ Connection error\x1b[0m");
    };

    ws.onclose = () => {
      setConnected(false);
      terminal.writeln("");
      terminal.writeln("\x1b[2mConnection closed\x1b[0m");
    };

    // Handle keyboard input
    const disposable = terminal.onData((data) => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({
          type: "input",
          data,
        }));
      }
    });

    // Handle terminal resize
    const resizeObserver = new ResizeObserver(() => {
      if (fitAddonRef.current) {
        fitAddonRef.current.fit();

        const { cols, rows } = terminal;
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({
            type: "resize",
            cols,
            rows,
          }));
        }
      }
    });

    if (terminalRef.current) {
      resizeObserver.observe(terminalRef.current);
    }

    wsRef.current = ws;

    // Cleanup
    return () => {
      disposable.dispose();
      resizeObserver.disconnect();
      ws.close();
    };
  }, []);

  return (
    <div className="terminal-view">
      {/* Hero Section */}
      <section className="terminal-hero">
        <div>
          <span className="terminal-eyebrow">Remote Shell Access</span>
          <h1>Web Terminal</h1>
          <p className="terminal-subtitle">
            Full shell access from your browser. Execute commands, navigate directories,
            and manage your system remotely.
          </p>
        </div>

        <div className="terminal-hero-meta">
          {connected ? (
            <div className="terminal-badge status-success">
              ✓ Connected
            </div>
          ) : error ? (
            <div className="terminal-badge status-danger">
              ✗ {error}
            </div>
          ) : (
            <div className="terminal-badge status-neutral">
              ⏳ Connecting...
            </div>
          )}
        </div>
      </section>

      {/* Terminal Container */}
      <div className="terminal-container">
        <div className="terminal-header">
          <span className="terminal-title">Shell</span>
          <div className="terminal-controls">
            {connected && (
              <span className="terminal-status">
                <span className="terminal-status-dot" />
                Active
              </span>
            )}
          </div>
        </div>
        <div ref={terminalRef} className="terminal-content" />
      </div>

      {/* Help Section */}
      <section className="terminal-help-section">
        <h2>Terminal Features</h2>
        <div className="terminal-help-grid">
          <div className="terminal-help-card">
            <div className="terminal-help-icon">💻</div>
            <h3>Full Shell Access</h3>
            <p>
              Complete shell environment with all your system commands available.
              Navigate directories, edit files, run scripts.
            </p>
          </div>

          <div className="terminal-help-card">
            <div className="terminal-help-icon">🔗</div>
            <h3>Persistent Session</h3>
            <p>
              Working directory and environment variables persist across commands.
              Just like a local terminal.
            </p>
          </div>

          <div className="terminal-help-card">
            <div className="terminal-help-icon">⚡</div>
            <h3>Real-Time</h3>
            <p>
              See command output as it happens. WebSocket connection provides
              instant feedback for all operations.
            </p>
          </div>

          <div className="terminal-help-card">
            <div className="terminal-help-icon">🎨</div>
            <h3>Rich Text Support</h3>
            <p>
              Full ANSI color support, clickable URLs, and smooth scrollback.
              Professional terminal experience.
            </p>
          </div>
        </div>
      </section>

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
