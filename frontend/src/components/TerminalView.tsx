import { useEffect, useRef } from "react";
import { Terminal } from "@xterm/xterm";
import { FitAddon } from "@xterm/addon-fit";
import { WebLinksAddon } from "@xterm/addon-web-links";
import "@xterm/xterm/css/xterm.css";

import type { AuditEvent } from "../api/types";

interface TerminalViewProps {
  /** Events to display in terminal */
  events: AuditEvent[];
  /** Optional max height in pixels */
  maxHeight?: number;
}

/**
 * Terminal emulator component using xterm.js
 *
 * Displays audit events as a terminal session, showing:
 * - Command executions with their output
 * - Phase transitions
 * - File changes
 * - Git operations
 *
 * Features:
 * - Auto-scroll to latest event
 * - Color coding by event type and status
 * - Clickable file paths
 * - Automatic terminal resizing
 */
export function TerminalView({ events, maxHeight = 600 }: TerminalViewProps) {
  const terminalRef = useRef<HTMLDivElement>(null);
  const xtermRef = useRef<Terminal | null>(null);
  const fitAddonRef = useRef<FitAddon | null>(null);
  const processedEventsRef = useRef<Set<number>>(new Set());

  // Initialize terminal
  useEffect(() => {
    if (!terminalRef.current) return;

    const terminal = new Terminal({
      cursorBlink: false,
      disableStdin: true,
      fontSize: 13,
      fontFamily: '"JetBrains Mono", "Fira Code", "Courier New", monospace',
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
        brightWhite: "#f8fafc",
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
    terminal.writeln("\x1b[1;36m╔════════════════════════════════════════════════════════╗\x1b[0m");
    terminal.writeln("\x1b[1;36m║\x1b[0m  \x1b[1;37mATLAS Agent Monitoring Terminal\x1b[0m                    \x1b[1;36m║\x1b[0m");
    terminal.writeln("\x1b[1;36m╚════════════════════════════════════════════════════════╝\x1b[0m");
    terminal.writeln("");

    // Resize on window resize
    const handleResize = () => {
      if (fitAddonRef.current) {
        fitAddonRef.current.fit();
      }
    };
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      terminal.dispose();
    };
  }, []);

  // Process new events
  useEffect(() => {
    if (!xtermRef.current) return;

    const terminal = xtermRef.current;
    const newEvents = events.filter(e => !processedEventsRef.current.has(e.id));

    newEvents.forEach(event => {
      processedEventsRef.current.add(event.id);
      writeEventToTerminal(terminal, event);
    });

    // Auto-scroll to bottom
    if (newEvents.length > 0) {
      terminal.scrollToBottom();
    }
  }, [events]);

  return (
    <div
      className="terminal-container"
      style={{
        height: "100%",
        maxHeight: `${maxHeight}px`,
        overflow: "hidden",
        borderRadius: "12px",
        background: "#0a0e18",
        padding: "12px",
      }}
    >
      <div ref={terminalRef} style={{ height: "100%" }} />
    </div>
  );
}

/**
 * Write an audit event to the terminal with appropriate formatting
 */
function writeEventToTerminal(terminal: Terminal, event: AuditEvent): void {
  const timestamp = formatTimestamp(event.created_at);

  switch (event.type) {
    case "command":
      writeCommand(terminal, timestamp, event);
      break;

    case "command_result":
      writeCommandResult(terminal, timestamp, event);
      break;

    case "phase":
      writePhase(terminal, timestamp, event);
      break;

    case "file_change":
      writeFileChange(terminal, timestamp, event);
      break;

    case "git":
      writeGitOperation(terminal, timestamp, event);
      break;

    case "thought":
      writeThought(terminal, timestamp, event);
      break;

    case "error":
      writeError(terminal, timestamp, event);
      break;

    case "session":
      writeSession(terminal, timestamp, event);
      break;

    default:
      writeGeneric(terminal, timestamp, event);
  }
}

function writeCommand(terminal: Terminal, timestamp: string, event: AuditEvent): void {
  const phaseColor = getPhaseColor(event.phase);
  const phase = event.phase ? `[${event.phase}]` : "";

  terminal.writeln(
    `\x1b[2m${timestamp}\x1b[0m ${phaseColor}${phase}\x1b[0m \x1b[1;33m$\x1b[0m \x1b[37m${event.title.replace("$ ", "")}\x1b[0m`
  );
}

function writeCommandResult(terminal: Terminal, timestamp: string, event: AuditEvent): void {
  const isSuccess = event.status === "ok";
  const statusColor = isSuccess ? "\x1b[32m" : "\x1b[31m";
  const statusIcon = isSuccess ? "✓" : "✗";
  const exitCode = event.payload?.exit_code as number | undefined ?? "?";

  terminal.writeln(
    `\x1b[2m${timestamp}\x1b[0m ${statusColor}${statusIcon}\x1b[0m Exit code: ${exitCode}`
  );

  // Show output if available (truncated)
  if (event.detail) {
    const lines = event.detail.split("\n").slice(0, 10); // First 10 lines
    lines.forEach(line => {
      terminal.writeln(`  \x1b[2m${line}\x1b[0m`);
    });
    if (event.detail.split("\n").length > 10) {
      terminal.writeln(`  \x1b[2m... (output truncated)\x1b[0m`);
    }
  }

  terminal.writeln(""); // Blank line after command output
}

function writePhase(terminal: Terminal, timestamp: string, event: AuditEvent): void {
  const isStart = event.status === "running";
  const isSuccess = event.status === "ok";
  const phaseColor = getPhaseColor(event.phase);

  if (isStart) {
    terminal.writeln("");
    terminal.writeln(`\x1b[1;36m┌─────────────────────────────────────────────────────────\x1b[0m`);
    terminal.writeln(
      `\x1b[1;36m│\x1b[0m ${phaseColor}▶\x1b[0m \x1b[1m${event.title}\x1b[0m`
    );
    terminal.writeln(`\x1b[1;36m└─────────────────────────────────────────────────────────\x1b[0m`);
  } else {
    const statusColor = isSuccess ? "\x1b[32m" : "\x1b[31m";
    const statusIcon = isSuccess ? "✓" : "✗";
    const durationMs = event.payload?.duration_ms as number | undefined;
    const duration = durationMs
      ? ` (${(durationMs / 1000).toFixed(2)}s)`
      : "";

    terminal.writeln("");
    terminal.writeln(
      `\x1b[2m${timestamp}\x1b[0m ${statusColor}${statusIcon}\x1b[0m \x1b[1m${event.title}\x1b[0m${duration}`
    );
    terminal.writeln("");
  }
}

function writeFileChange(terminal: Terminal, timestamp: string, event: AuditEvent): void {
  const changeType = (event.payload?.change_type as string) || "modify";
  const changeIcon = {
    create: "\x1b[32m+",
    modify: "\x1b[33m~",
    delete: "\x1b[31m-",
  }[changeType] || "\x1b[37m•";

  const filePath = event.ref || event.payload?.file_path || "unknown";

  terminal.writeln(
    `\x1b[2m${timestamp}\x1b[0m ${changeIcon}\x1b[0m \x1b[36m${filePath}\x1b[0m`
  );
  if (event.detail) {
    terminal.writeln(`  \x1b[2m${event.detail}\x1b[0m`);
  }
}

function writeGitOperation(terminal: Terminal, timestamp: string, event: AuditEvent): void {
  terminal.writeln(
    `\x1b[2m${timestamp}\x1b[0m \x1b[35mgit\x1b[0m ${event.title.replace("Git ", "")}`
  );
  if (event.detail) {
    terminal.writeln(`  \x1b[2m${event.detail}\x1b[0m`);
  }
}

function writeThought(terminal: Terminal, timestamp: string, event: AuditEvent): void {
  const phaseColor = getPhaseColor(event.phase);
  const phase = event.phase ? `[${event.phase}]` : "";

  terminal.writeln(
    `\x1b[2m${timestamp}\x1b[0m ${phaseColor}${phase}\x1b[0m \x1b[36m💭\x1b[0m ${event.detail || event.title}`
  );
}

function writeError(terminal: Terminal, timestamp: string, event: AuditEvent): void {
  terminal.writeln("");
  terminal.writeln(`\x1b[2m${timestamp}\x1b[0m \x1b[1;31m❌ ${event.title}\x1b[0m`);
  if (event.detail) {
    const lines = event.detail.split("\n").slice(0, 15);
    lines.forEach(line => {
      terminal.writeln(`  \x1b[31m${line}\x1b[0m`);
    });
  }
  terminal.writeln("");
}

function writeSession(terminal: Terminal, timestamp: string, event: AuditEvent): void {
  const isStart = event.title.toLowerCase().includes("started");
  const color = isStart ? "\x1b[1;32m" : "\x1b[1;34m";
  const icon = isStart ? "🚀" : "🏁";

  terminal.writeln("");
  terminal.writeln(`${color}${icon} ${event.title}\x1b[0m`);
  if (event.detail) {
    terminal.writeln(`  \x1b[2m${event.detail}\x1b[0m`);
  }
  terminal.writeln("");
}

function writeGeneric(terminal: Terminal, timestamp: string, event: AuditEvent): void {
  const phaseColor = getPhaseColor(event.phase);
  const phase = event.phase ? `[${event.phase}]` : "";

  terminal.writeln(
    `\x1b[2m${timestamp}\x1b[0m ${phaseColor}${phase}\x1b[0m \x1b[37m${event.title}\x1b[0m`
  );
  if (event.detail) {
    terminal.writeln(`  \x1b[2m${event.detail}\x1b[0m`);
  }
}

function formatTimestamp(timestamp: string): string {
  const date = new Date(timestamp);
  return date.toLocaleTimeString("en-US", {
    hour12: false,
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function getPhaseColor(phase: string | null | undefined): string {
  switch (phase) {
    case "plan":
      return "\x1b[34m"; // Blue
    case "apply":
      return "\x1b[33m"; // Yellow
    case "validate":
      return "\x1b[32m"; // Green
    case "explore":
      return "\x1b[35m"; // Magenta
    default:
      return "\x1b[37m"; // White
  }
}
