import { useEffect, useMemo, useRef, useState, useCallback, memo } from "react";
import { Terminal } from "@xterm/xterm";
import { FitAddon } from "@xterm/addon-fit";
import { WebLinksAddon } from "@xterm/addon-web-links";
import { useBackendStore } from "../state/useBackendStore";
import { resolveBackendBaseUrl } from "../api/client";

import "@xterm/xterm/css/xterm.css";

const MIN_VALID_COLS = 40;
const MIN_VALID_ROWS = 10;
const DEFAULT_COLS = 80;
const DEFAULT_ROWS = 24;

// Character dimensions for JetBrains Mono at 14px
// These are fallback values - we'll measure the actual font
const FALLBACK_CHAR_WIDTH = 8.4;
const FALLBACK_CHAR_HEIGHT = 17;

export interface TerminalEmbedProps {
  autoConnect?: boolean;
  welcomeMessage?: string | null;
  onConnectionChange?: (connected: boolean) => void;
  className?: string;
  height?: string;
  /** Show a separate input box for composing messages (avoids PTY line-wrap issues) */
  showInputBox?: boolean;
}

/**
 * Measure actual character dimensions by rendering a test string
 *
 * For monospace fonts, we measure using a mix of characters to get
 * the true fixed-width value. We also create a hidden DOM element
 * to measure more accurately than Canvas API.
 */
function measureCharacterDimensions(
  fontSize: number = 14,
  fontFamily: string = '"JetBrains Mono", "Fira Code", "Cascadia Code", monospace'
): { width: number; height: number } {
  // Method 1: DOM-based measurement (more accurate for actual rendering)
  const measureElement = document.createElement('span');
  measureElement.style.cssText = `
    position: absolute;
    visibility: hidden;
    white-space: pre;
    font-family: ${fontFamily};
    font-size: ${fontSize}px;
    line-height: normal;
  `;
  // Use a variety of characters to ensure we get the monospace width
  measureElement.textContent = 'XXXXXXXXXXXXXXXXXXXX'; // 20 X's
  document.body.appendChild(measureElement);

  const rect = measureElement.getBoundingClientRect();
  const charWidth = rect.width / 20;
  // xterm uses lineHeight of 1.0 by default, so height = fontSize
  // But we add a small buffer for cell padding
  const charHeight = fontSize * 1.2;

  document.body.removeChild(measureElement);

  // Sanity check - monospace chars at 14px should be ~8-9px wide
  if (charWidth < 6 || charWidth > 12) {
    console.warn(`[TerminalEmbed] Unusual char width ${charWidth.toFixed(2)}px, using fallback`);
    return { width: FALLBACK_CHAR_WIDTH, height: FALLBACK_CHAR_HEIGHT };
  }

  console.log(`[TerminalEmbed] Measured char dimensions: ${charWidth.toFixed(2)}x${charHeight.toFixed(2)}`);

  return { width: charWidth, height: charHeight };
}

/**
 * Calculate terminal dimensions based on container size
 */
function calculateTerminalDimensions(
  containerWidth: number,
  containerHeight: number,
  charWidth: number,
  charHeight: number
): { cols: number; rows: number } {
  // Calculate cols and rows
  const cols = Math.floor(containerWidth / charWidth);
  const rows = Math.floor(containerHeight / charHeight);

  console.log(`[TerminalEmbed] Calculated: ${containerWidth}px/${charWidth}px = ${cols} cols, ${containerHeight}px/${charHeight}px = ${rows} rows`);

  return {
    cols: Math.max(cols, MIN_VALID_COLS),
    rows: Math.max(rows, MIN_VALID_ROWS),
  };
}

function TerminalEmbedInner({
  autoConnect = false,
  welcomeMessage = "AEGIS Terminal",
  onConnectionChange,
  className = "",
  height = "500px",
  showInputBox = false,
}: TerminalEmbedProps) {
  const [connected, setConnected] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [containerReady, setContainerReady] = useState(false);
  const [terminalDims, setTerminalDims] = useState({ cols: DEFAULT_COLS, rows: DEFAULT_ROWS });
  const [charDims, setCharDims] = useState({ width: FALLBACK_CHAR_WIDTH, height: FALLBACK_CHAR_HEIGHT });

  // Input box state for composing messages
  const [inputText, setInputText] = useState("");
  const inputRef = useRef<HTMLTextAreaElement>(null);

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

  useEffect(() => {
    mountedRef.current = true;
    return () => { mountedRef.current = false; };
  }, []);

  useEffect(() => {
    onConnectionChange?.(connected);
  }, [connected, onConnectionChange]);

  const wsBaseUrl = useMemo(() => {
    const stripApi = (value: string) =>
      value.endsWith("/api") ? value.slice(0, -4) : value;
    const base =
      resolveBackendBaseUrl(backendUrl) ??
      (typeof window !== "undefined" ? window.location.origin : "http://127.0.0.1:8010");
    return stripApi(base.replace(/\/+$/, ""));
  }, [backendUrl]);

  // Wait for container and font to be ready
  useEffect(() => {
    const container = terminalRef.current;
    if (!container) return;

    const checkReady = async () => {
      // Wait for font to load
      try {
        await document.fonts.load('14px "JetBrains Mono"');
        console.log('[TerminalEmbed] Font loaded');
      } catch (e) {
        console.warn('[TerminalEmbed] Font load failed, using fallback:', e);
      }

      const rect = container.getBoundingClientRect();
      if (rect.width >= 200 && rect.height >= 150) {
        // Measure character dimensions AFTER font is loaded
        const measured = measureCharacterDimensions(14);
        setCharDims(measured);
        setContainerReady(true);
        return true;
      }
      return false;
    };

    checkReady().then(ready => {
      if (ready) return;

      // If not ready, use ResizeObserver
      const observer = new ResizeObserver(() => {
        checkReady().then(ready => {
          if (ready) observer.disconnect();
        });
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
    });
  }, []);

  // Calculate dimensions manually (don't trust FitAddon)
  const calculateDims = useCallback((): { cols: number; rows: number } => {
    const container = terminalRef.current;
    if (!container) {
      return { cols: DEFAULT_COLS, rows: DEFAULT_ROWS };
    }

    const rect = container.getBoundingClientRect();

    if (rect.width < 200 || rect.height < 150) {
      console.warn(`[TerminalEmbed] Container too small: ${rect.width}x${rect.height}`);
      return { cols: DEFAULT_COLS, rows: DEFAULT_ROWS };
    }

    // CRITICAL: We need to be very conservative with width calculation.
    // The issue is that xterm.js renders characters, and if we calculate
    // even 1 column too many, the PTY will wrap text incorrectly.
    //
    // Subtractions needed:
    // 1. Scrollbar: 17px (standard scrollbar width on most systems)
    // 2. xterm viewport padding: 2px on each side = 4px
    // 3. Safety margin: 2px (account for sub-pixel rendering differences)
    // 4. Additional buffer: 8px (for any box-sizing issues)
    //
    // Total: 31px safety margin
    const SAFETY_MARGIN = 31;

    const effectiveWidth = rect.width - SAFETY_MARGIN;
    const effectiveHeight = rect.height - 4; // Small vertical buffer

    // Use a slightly larger character width for safety
    // This ensures we never calculate more columns than can actually fit
    const safeCharWidth = charDims.width * 1.02; // 2% buffer

    console.log(`[TerminalEmbed] Container: ${rect.width.toFixed(0)}x${rect.height.toFixed(0)}, ` +
                `Effective: ${effectiveWidth.toFixed(0)}x${effectiveHeight.toFixed(0)}, ` +
                `CharDims: ${charDims.width.toFixed(2)}x${charDims.height.toFixed(2)}, ` +
                `SafeCharWidth: ${safeCharWidth.toFixed(2)}`);

    const dims = calculateTerminalDimensions(
      effectiveWidth,
      effectiveHeight,
      safeCharWidth,
      charDims.height
    );

    // Additional safety: subtract 2 columns as final buffer
    // This is aggressive but ensures no wrapping
    dims.cols = Math.max(MIN_VALID_COLS, dims.cols - 2);

    // Final sanity check - ensure cols are reasonable for the width
    const maxReasonableCols = Math.floor(effectiveWidth / 7); // Use 7px as minimum char width
    if (dims.cols > maxReasonableCols) {
      console.warn(`[TerminalEmbed] Clamping cols from ${dims.cols} to ${maxReasonableCols}`);
      dims.cols = maxReasonableCols;
    }

    // Also clamp rows to prevent excessive values
    const maxReasonableRows = Math.floor(effectiveHeight / 12); // Use 12px as minimum line height
    if (dims.rows > maxReasonableRows) {
      console.warn(`[TerminalEmbed] Clamping rows from ${dims.rows} to ${maxReasonableRows}`);
      dims.rows = maxReasonableRows;
    }

    console.log(`[TerminalEmbed] Final dimensions: ${dims.cols}x${dims.rows}`);

    if (mountedRef.current) {
      setTerminalDims(dims);
    }

    return dims;
  }, [charDims]);

  // Initialize terminal
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
    });

    const fitAddon = new FitAddon();
    const webLinksAddon = new WebLinksAddon();

    terminal.loadAddon(fitAddon);
    terminal.loadAddon(webLinksAddon);
    terminal.open(container);

    xtermRef.current = terminal;
    fitAddonRef.current = fitAddon;

    // Initial fit using our manual calculation
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        if (!mountedRef.current) return;

        const dims = calculateDims();

        // Resize terminal to our calculated dimensions
        try {
          terminal.resize(dims.cols, dims.rows);
          console.log(`[TerminalEmbed] Initial resize to ${dims.cols}x${dims.rows}`);
        } catch (err) {
          console.error('[TerminalEmbed] Error resizing:', err);
        }
      });
    });

    // Welcome message - ONLY shown before connecting
    // This is safe because we'll reset() before PTY takes over
    if (welcomeMessage) {
      terminal.writeln(`\x1b[1;36m╔════════════════════════════════════════════════════════╗\x1b[0m`);
      terminal.writeln(`\x1b[1;36m║\x1b[0m    \x1b[1;33m${welcomeMessage.padEnd(50)}\x1b[0m\x1b[1;36m║\x1b[0m`);
      terminal.writeln(`\x1b[1;36m╚════════════════════════════════════════════════════════╝\x1b[0m`);
      terminal.writeln("");
      terminal.writeln("\x1b[2mClick 'Connect' to start shell session...\x1b[0m");
    }

    return () => {
      terminal.dispose();
      xtermRef.current = null;
      fitAddonRef.current = null;
    };
  }, [containerReady, welcomeMessage, calculateDims]);

  // Cleanup
  useEffect(() => {
    return () => {
      if (resizeTimeoutRef.current) clearTimeout(resizeTimeoutRef.current);
      disposablesRef.current.data?.dispose();
      disposablesRef.current.resize?.dispose();
      disposablesRef.current.observer?.disconnect();
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.close(1000, "Component unmounting");
      }
    };
  }, []);

  const connect = useCallback(() => {
    if (!xtermRef.current) {
      setError("Terminal not initialized");
      return;
    }

    if (wsRef.current?.readyState === WebSocket.OPEN || wsRef.current?.readyState === WebSocket.CONNECTING) {
      return;
    }

    const terminal = xtermRef.current;
    const wsUrl = wsBaseUrl.replace("http://", "ws://").replace("https://", "wss://");

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

      // CRITICAL: Reset terminal completely before PTY takes over
      // This ensures:
      // 1. No leftover content from welcome message
      // 2. Cursor at position (0,0)
      // 3. Scrollback cleared
      // 4. PTY has full control of terminal state
      terminal.reset();

      // Calculate and send dimensions
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          if (!mountedRef.current) return;

          const dims = calculateDims();

          // Resize xterm to match
          try {
            terminal.resize(dims.cols, dims.rows);
          } catch (e) {
            console.error('[TerminalEmbed] Resize error:', e);
          }

          console.log(`[TerminalEmbed] Sending to PTY: ${dims.cols}x${dims.rows}`);
          socket.send(`__RESIZE__:${dims.cols}:${dims.rows}`);

          // DO NOT write anything to terminal here!
          // All output must come from PTY to keep cursor position in sync
        });
      });
    };

    socket.onmessage = (event) => {
      if (mountedRef.current) {
        xtermRef.current?.write(event.data);
      }
    };

    socket.onerror = () => {
      if (mountedRef.current) {
        setConnected(false);
        setConnecting(false);
        setError("Connection error");
      }
    };

    socket.onclose = (event) => {
      if (mountedRef.current) {
        setConnected(false);
        setConnecting(false);
        if (event.code !== 1000) {
          xtermRef.current?.writeln("\r\n\x1b[2mConnection closed\x1b[0m");
        }
      }
    };

    wsRef.current = socket;

    disposablesRef.current.data = terminal.onData((data) => {
      if (socket.readyState === WebSocket.OPEN) {
        socket.send(data);
      }
    });

    // Handle resize - use our manual calculation
    const sendResize = () => {
      if (socket?.readyState === WebSocket.OPEN && xtermRef.current && mountedRef.current) {
        const dims = calculateDims();

        try {
          xtermRef.current.resize(dims.cols, dims.rows);
        } catch (e) {
          console.error('[TerminalEmbed] Resize error:', e);
        }

        console.log(`[TerminalEmbed] Sending resize: ${dims.cols}x${dims.rows}`);
        socket.send(`__RESIZE__:${dims.cols}:${dims.rows}`);
      }
    };

    // Don't use terminal.onResize - it uses FitAddon's calculations
    // Instead, only respond to container size changes
    disposablesRef.current.observer = new ResizeObserver(() => {
      if (resizeTimeoutRef.current) clearTimeout(resizeTimeoutRef.current);
      resizeTimeoutRef.current = setTimeout(sendResize, 200);
    });

    if (terminalRef.current) {
      disposablesRef.current.observer.observe(terminalRef.current);
    }
  }, [wsBaseUrl, calculateDims]);

  const disconnect = useCallback(() => {
    disposablesRef.current.data?.dispose();
    disposablesRef.current.resize?.dispose();
    disposablesRef.current.observer?.disconnect();
    disposablesRef.current = {};

    if (wsRef.current) {
      if (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING) {
        wsRef.current.close();
      }
      wsRef.current = null;
    }

    setConnected(false);
    setConnecting(false);

    if (xtermRef.current && mountedRef.current) {
      xtermRef.current.writeln("\r\n\x1b[2mDisconnected.\x1b[0m");
    }
  }, []);

  // Force recalculate (for debugging)
  const handleForceRecalc = useCallback(() => {
    const dims = calculateDims();
    if (xtermRef.current) {
      try {
        xtermRef.current.resize(dims.cols, dims.rows);
      } catch (e) {
        console.error(e);
      }
    }
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(`__RESIZE__:${dims.cols}:${dims.rows}`);
    }
  }, [calculateDims]);

  // Submit input text to terminal (for input box mode)
  const handleInputSubmit = useCallback(() => {
    if (!inputText.trim() || !wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      return;
    }

    // Send the complete text followed by Enter (carriage return)
    // This sends it as a single block rather than character-by-character
    wsRef.current.send(inputText + "\r");
    setInputText("");

    // Focus back to terminal for navigation/confirmations
    xtermRef.current?.focus();
  }, [inputText]);

  // Handle keyboard in input box
  const handleInputKeyDown = useCallback((e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // Shift+Enter or Ctrl+Enter to submit
    if (e.key === "Enter" && (e.shiftKey || e.ctrlKey)) {
      e.preventDefault();
      handleInputSubmit();
    }
    // Regular Enter adds newline (default behavior)
  }, [handleInputSubmit]);

  useEffect(() => {
    if (autoConnect && xtermRef.current && !connected && !connecting) {
      const timer = setTimeout(connect, 200);
      return () => clearTimeout(timer);
    }
  }, [autoConnect, connect, connected, connecting]);

  return (
    <div className={`terminal-embed ${className}`}>
      <div className="terminal-embed-header">
        <span className="terminal-embed-title">Terminal</span>
        <div className="terminal-embed-controls">
          <span
            className="terminal-embed-dims"
            onClick={handleForceRecalc}
            title={`Click to recalculate\nChar: ${charDims.width.toFixed(1)}×${charDims.height.toFixed(1)}px`}
            style={{ cursor: 'pointer' }}
          >
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
              <button onClick={disconnect} className="terminal-embed-btn disconnect">
                Disconnect
              </button>
            </>
          )}
          {error && <span className="terminal-embed-status error">✗ {error}</span>}
        </div>
      </div>
      <div className="terminal-embed-xterm-wrapper" style={{ height }}>
        <div ref={terminalRef} className="terminal-embed-content" />
      </div>

      {/* Input box for composing messages - avoids PTY line-wrap issues */}
      {showInputBox && connected && (
        <div className="terminal-embed-input-container">
          <textarea
            ref={inputRef}
            className="terminal-embed-input"
            value={inputText}
            onChange={(e) => setInputText(e.target.value)}
            onKeyDown={handleInputKeyDown}
            placeholder="Type your message here... (Shift+Enter or Ctrl+Enter to send)"
            rows={3}
          />
          <button
            className="terminal-embed-send-btn"
            onClick={handleInputSubmit}
            disabled={!inputText.trim()}
          >
            Send
          </button>
        </div>
      )}
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
  color: #10b981;
  padding: 2px 8px;
  background: rgba(16, 185, 129, 0.15);
  border: 1px solid rgba(16, 185, 129, 0.3);
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

.terminal-embed-status.connecting { color: #fbbf24; }
.terminal-embed-status.connected { color: #34d399; }
.terminal-embed-status.error { color: #f87171; }

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

/* Input box for composing messages */
.terminal-embed-input-container {
  display: flex;
  gap: 8px;
  padding: 8px 12px;
  background: rgba(15, 23, 42, 0.9);
  border-top: 1px solid rgba(59, 130, 246, 0.2);
}

.terminal-embed-input {
  flex: 1;
  min-height: 60px;
  max-height: 150px;
  padding: 10px 12px;
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  font-size: 13px;
  line-height: 1.5;
  color: #e2e8f0;
  background: rgba(10, 14, 24, 0.8);
  border: 1px solid rgba(59, 130, 246, 0.3);
  border-radius: 6px;
  resize: vertical;
  outline: none;
  transition: border-color 0.2s, box-shadow 0.2s;
}

.terminal-embed-input:focus {
  border-color: rgba(59, 130, 246, 0.6);
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.15);
}

.terminal-embed-input::placeholder {
  color: #64748b;
}

.terminal-embed-send-btn {
  align-self: flex-end;
  padding: 10px 20px;
  font-size: 13px;
  font-weight: 600;
  color: #fff;
  background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
  border: none;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
  min-width: 80px;
}

.terminal-embed-send-btn:hover:not(:disabled) {
  background: linear-gradient(135deg, #60a5fa 0%, #3b82f6 100%);
  transform: translateY(-1px);
}

.terminal-embed-send-btn:active:not(:disabled) {
  transform: translateY(0);
}

.terminal-embed-send-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
`;
