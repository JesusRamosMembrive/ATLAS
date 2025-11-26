/**
 * Claude Agent View
 *
 * UI for interacting with Claude Code via JSON streaming mode.
 * Replaces the TUI-based terminal with a structured, custom-rendered interface.
 */

import { useEffect, useRef, useState, useCallback } from "react";
import { useClaudeSessionStore } from "../stores/claudeSessionStore";
import { useSessionHistoryStore } from "../stores/sessionHistoryStore";
import { useThemeStore } from "../stores/themeStore";
import { useBackendStore } from "../state/useBackendStore";
import { resolveBackendBaseUrl } from "../api/client";
import {
  ClaudeMessage,
  getToolIcon,
  formatToolInput,
} from "../types/claude-events";
import { MarkdownRenderer } from "./MarkdownRenderer";
import { SessionHistorySidebar } from "./SessionHistorySidebar";

// ============================================================================
// Main Component
// ============================================================================

export function ClaudeAgentView() {
  const [promptValue, setPromptValue] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Store state
  const {
    connected,
    connecting,
    running,
    messages,
    sessionInfo,
    lastError,
    connectionError,
    cwd,
    activeToolCalls,
    continueSession,
    totalInputTokens,
    totalOutputTokens,
    isReconnecting,
    reconnectAttempts,
    maxReconnectAttempts,
    connect,
    disconnect,
    sendPrompt,
    cancel,
    newSession,
    clearMessages,
    clearConnectionError,
  } = useClaudeSessionStore();

  // Session history
  const { saveSession, sidebarOpen } = useSessionHistoryStore();

  // Theme
  const { resolvedTheme, toggleTheme } = useThemeStore();

  const backendUrl = useBackendStore((state) => state.backendUrl);

  // Build WebSocket URL
  const getWsUrl = useCallback(() => {
    const stripApi = (value: string) =>
      value.endsWith("/api") ? value.slice(0, -4) : value;

    const base =
      resolveBackendBaseUrl(backendUrl) ??
      (typeof window !== "undefined"
        ? window.location.origin
        : "http://127.0.0.1:8010");

    const sanitized = base.replace(/\/+$/, "");
    const httpBase = stripApi(sanitized);
    const wsBase = httpBase.replace(/^http/, "ws");
    return `${wsBase}/api/terminal/ws/agent`;
  }, [backendUrl]);

  // Auto-connect on mount
  useEffect(() => {
    if (!connected && !connecting) {
      const wsUrl = getWsUrl();
      console.log("[ClaudeAgent] Connecting to:", wsUrl);
      connect(wsUrl);
    }
  }, [connected, connecting, connect, getWsUrl]);

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Auto-save session when messages change (debounced)
  useEffect(() => {
    if (messages.length > 0 && !running) {
      const timer = setTimeout(() => {
        saveSession(sessionInfo.sessionId, sessionInfo.model, messages);
      }, 1000);
      return () => clearTimeout(timer);
    }
  }, [messages, running, sessionInfo.sessionId, sessionInfo.model, saveSession]);

  // Handle loading a session from history
  const handleLoadSession = useCallback(
    (loadedMessages: ClaudeMessage[]) => {
      // Clear current messages and load new ones
      clearMessages();
      // We need to set messages directly - this requires updating the store
      useClaudeSessionStore.setState({ messages: loadedMessages });
    },
    [clearMessages]
  );

  // Handle new session from sidebar
  const handleNewSessionFromSidebar = useCallback(() => {
    newSession();
  }, [newSession]);

  // Handle submit
  const handleSubmit = useCallback(
    (e?: React.FormEvent) => {
      e?.preventDefault();
      if (!promptValue.trim() || running) return;

      sendPrompt(promptValue.trim());
      setPromptValue("");
    },
    [promptValue, running, sendPrompt]
  );

  // Handle key press in textarea
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSubmit();
      }
    },
    [handleSubmit]
  );

  // Global keyboard shortcuts
  useEffect(() => {
    const handleGlobalKeyDown = (e: KeyboardEvent) => {
      // Escape to cancel running operation
      if (e.key === "Escape" && running) {
        e.preventDefault();
        cancel();
      }
      // Ctrl+L to clear messages
      if (e.key === "l" && (e.ctrlKey || e.metaKey)) {
        e.preventDefault();
        clearMessages();
      }
      // Ctrl+N for new session
      if (e.key === "n" && (e.ctrlKey || e.metaKey) && e.shiftKey) {
        e.preventDefault();
        newSession();
      }
      // Focus input with /
      if (e.key === "/" && !e.ctrlKey && !e.metaKey && document.activeElement?.tagName !== "TEXTAREA") {
        e.preventDefault();
        inputRef.current?.focus();
      }
    };

    window.addEventListener("keydown", handleGlobalKeyDown);
    return () => window.removeEventListener("keydown", handleGlobalKeyDown);
  }, [running, cancel, clearMessages, newSession]);

  // Reconnect
  const handleReconnect = useCallback(() => {
    disconnect();
    setTimeout(() => {
      const wsUrl = getWsUrl();
      connect(wsUrl);
    }, 100);
  }, [disconnect, connect, getWsUrl]);

  return (
    <div
      className={`claude-agent-view ${sidebarOpen ? "sidebar-open" : ""}`}
      role="main"
      aria-label="Claude Agent Interface"
    >
      {/* Session History Sidebar */}
      <SessionHistorySidebar
        onLoadSession={handleLoadSession}
        onNewSession={handleNewSessionFromSidebar}
      />

      {/* Header */}
      <AgentHeader
        connected={connected}
        connecting={connecting}
        running={running}
        sessionInfo={sessionInfo}
        cwd={cwd}
        continueSession={continueSession}
        totalInputTokens={totalInputTokens}
        totalOutputTokens={totalOutputTokens}
        isReconnecting={isReconnecting}
        reconnectAttempts={reconnectAttempts}
        maxReconnectAttempts={maxReconnectAttempts}
        onReconnect={handleReconnect}
        onNewSession={newSession}
        onClearMessages={clearMessages}
        resolvedTheme={resolvedTheme}
        onToggleTheme={toggleTheme}
      />

      {/* Connection Error Banner */}
      {connectionError && (
        <div className="connection-error-banner" role="alert">
          <span className="error-icon">⚠</span>
          <span className="error-message">{connectionError}</span>
          {!isReconnecting && (
            <button onClick={handleReconnect} className="retry-btn">
              Reconnect
            </button>
          )}
          <button
            onClick={clearConnectionError}
            className="dismiss-btn"
            aria-label="Dismiss error"
          >
            ×
          </button>
        </div>
      )}

      {/* Messages Area */}
      <div
        className="claude-messages-container"
        role="log"
        aria-label="Conversation messages"
        aria-live="polite"
        aria-relevant="additions"
      >
        {messages.length === 0 && !running ? (
          <EmptyState />
        ) : (
          <div className="claude-messages" role="list">
            {messages.map((msg, idx) => (
              <MessageItem key={msg.id || idx} message={msg} />
            ))}

            {/* Running indicator */}
            {running && (
              <div
                className="claude-thinking"
                role="status"
                aria-live="polite"
                aria-label="Claude is processing your request"
              >
                <div className="thinking-content">
                  <span className="thinking-icon" aria-hidden="true">🤔</span>
                  <span className="thinking-text">Claude is thinking...</span>
                  {activeToolCalls.size > 0 && (
                    <span className="active-tools" aria-label={`Running ${activeToolCalls.size} tools`}>
                      Running {activeToolCalls.size} tool
                      {activeToolCalls.size > 1 ? "s" : ""}
                    </span>
                  )}
                  <span className="escape-hint">Press Esc to cancel</span>
                </div>
                <div className="thinking-progress" role="progressbar" aria-label="Processing">
                  <div className="progress-bar" />
                </div>
              </div>
            )}

            {/* Error display */}
            {lastError && (
              <div className="claude-error" role="alert" aria-live="assertive">
                <span className="error-icon" aria-hidden="true">!</span>
                <span className="error-text">{lastError}</span>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Input Area */}
      <div className="claude-input-container">
        <form onSubmit={handleSubmit} className="claude-input-form" role="form" aria-label="Send message to Claude">
          <label htmlFor="claude-prompt-input" className="visually-hidden">
            Enter your message for Claude
          </label>
          <textarea
            id="claude-prompt-input"
            ref={inputRef}
            value={promptValue}
            onChange={(e) => setPromptValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={
              connected
                ? "Ask Claude anything... (Enter to send, Shift+Enter for newline)"
                : "Connecting..."
            }
            disabled={!connected || running}
            className="claude-input"
            rows={3}
            aria-describedby="input-hint"
          />
          <span id="input-hint" className="visually-hidden">
            Press Enter to send, Shift+Enter for new line. Press Escape to cancel running operations.
          </span>
          <div className="claude-input-actions">
            <button
              type="submit"
              disabled={!connected || running || !promptValue.trim()}
              className="claude-send-btn"
              aria-label="Send message"
            >
              Send
            </button>
            {running && (
              <button
                type="button"
                onClick={cancel}
                className="claude-cancel-btn"
                aria-label="Cancel current operation"
              >
                Cancel
              </button>
            )}
          </div>
        </form>
      </div>

      <style>{styles}</style>
    </div>
  );
}

// ============================================================================
// Sub-Components
// ============================================================================

interface AgentHeaderProps {
  connected: boolean;
  connecting: boolean;
  running: boolean;
  sessionInfo: {
    sessionId: string | null;
    model: string | null;
    tools: string[];
    mcpServers: Array<{ name: string; status: string }>;
  };
  cwd: string | null;
  continueSession: boolean;
  totalInputTokens: number;
  totalOutputTokens: number;
  isReconnecting: boolean;
  reconnectAttempts: number;
  maxReconnectAttempts: number;
  onReconnect: () => void;
  onNewSession: () => void;
  onClearMessages: () => void;
  resolvedTheme: "dark" | "light";
  onToggleTheme: () => void;
}

function AgentHeader({
  connected,
  connecting,
  sessionInfo,
  cwd,
  continueSession,
  totalInputTokens,
  totalOutputTokens,
  isReconnecting,
  reconnectAttempts,
  maxReconnectAttempts,
  onReconnect,
  onNewSession,
  onClearMessages,
  resolvedTheme,
  onToggleTheme,
}: AgentHeaderProps) {
  const toggleContinueSession = useCallback(() => {
    useClaudeSessionStore.setState((state) => ({
      continueSession: !state.continueSession,
    }));
  }, []);

  const totalTokens = totalInputTokens + totalOutputTokens;
  const estimatedCost = ((totalInputTokens * 3 + totalOutputTokens * 15) / 1_000_000).toFixed(4);

  return (
    <div className="claude-header">
      <div className="claude-header-left">
        <h2 className="claude-title">Claude Agent</h2>
        <div className="claude-status">
          <span
            className={`status-dot ${connected ? "connected" : connecting || isReconnecting ? "connecting" : "disconnected"}`}
          />
          <span className="status-text">
            {connected
              ? "Connected"
              : isReconnecting
                ? `Reconnecting (${reconnectAttempts}/${maxReconnectAttempts})...`
                : connecting
                  ? "Connecting..."
                  : "Disconnected"}
          </span>
        </div>
        {sessionInfo.model && (
          <span className="claude-model">{sessionInfo.model}</span>
        )}
        <button
          className={`continue-toggle ${continueSession ? "active" : ""}`}
          onClick={toggleContinueSession}
          title={
            continueSession
              ? "Continue mode: ON - Will resume previous Claude session"
              : "Continue mode: OFF - Will start fresh session"
          }
        >
          <span className="toggle-icon">{continueSession ? "⟳" : "○"}</span>
          <span className="toggle-label">
            {continueSession ? "Continue" : "Fresh"}
          </span>
        </button>
        {totalTokens > 0 && (
          <span
            className="token-usage"
            title={`Input: ${totalInputTokens.toLocaleString()} | Output: ${totalOutputTokens.toLocaleString()} | Est. cost: $${estimatedCost}`}
          >
            <span className="token-icon">⚡</span>
            <span className="token-count">{totalTokens.toLocaleString()}</span>
            <span className="token-cost">${estimatedCost}</span>
          </span>
        )}
      </div>
      <div className="claude-header-right">
        {cwd && <span className="claude-cwd" title={cwd}>{truncatePath(cwd, 40)}</span>}
        <div className="claude-header-actions">
          <button
            onClick={onToggleTheme}
            className="header-btn theme-toggle"
            title={`Switch to ${resolvedTheme === "dark" ? "light" : "dark"} mode`}
            aria-label={`Current theme: ${resolvedTheme}. Click to switch to ${resolvedTheme === "dark" ? "light" : "dark"} mode`}
          >
            {resolvedTheme === "dark" ? "☀️" : "🌙"}
          </button>
          <button onClick={onClearMessages} className="header-btn" title="Clear messages (Ctrl+L)">
            Clear
          </button>
          <button onClick={onNewSession} className="header-btn" title="Start new session (Ctrl+Shift+N)">
            New Session
          </button>
          {!connected && !connecting && (
            <button onClick={onReconnect} className="header-btn primary" title="Reconnect">
              Reconnect
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="claude-empty">
      <div className="empty-icon">💬</div>
      <h3>Start a conversation</h3>
      <p>Type a message below to start interacting with Claude Code.</p>
      <p className="empty-hint">
        Claude can read files, run commands, write code, and more.
      </p>
    </div>
  );
}

interface MessageItemProps {
  message: ClaudeMessage;
}

function MessageItem({ message }: MessageItemProps) {
  const [expanded, setExpanded] = useState(false);

  switch (message.type) {
    case "text":
      return (
        <div className="message message-text" role="listitem" aria-label="Claude response">
          <div className="message-content">
            <MarkdownRenderer content={String(message.content)} />
          </div>
          <div className="message-meta" aria-label={`Sent at ${message.timestamp.toLocaleTimeString()}`}>
            {message.timestamp.toLocaleTimeString()}
          </div>
        </div>
      );

    case "tool_use":
      const toolContent = message.content as {
        id: string;
        name: string;
        input: Record<string, unknown>;
      };
      return (
        <div className="message message-tool-use" role="listitem" aria-label={`Tool call: ${toolContent.name}`}>
          <button
            className="tool-header"
            onClick={() => setExpanded(!expanded)}
            aria-expanded={expanded}
            aria-controls={`tool-details-${toolContent.id}`}
          >
            <span className="tool-icon" aria-hidden="true">{getToolIcon(toolContent.name)}</span>
            <span className="tool-name">{toolContent.name}</span>
            <span className="tool-expand" aria-hidden="true">{expanded ? "▼" : "▶"}</span>
          </button>
          {expanded && (
            <div id={`tool-details-${toolContent.id}`} className="tool-details">
              <pre className="tool-input" aria-label="Tool input parameters">
                {formatToolInput(toolContent.input, 500)}
              </pre>
            </div>
          )}
          <div className="message-meta" aria-label={`Sent at ${message.timestamp.toLocaleTimeString()}`}>
            {message.timestamp.toLocaleTimeString()}
          </div>
        </div>
      );

    case "tool_result":
      const resultContent = String(message.content);
      const isLong = resultContent.length > 300;
      return (
        <div
          className={`message message-tool-result ${message.isError ? "error" : ""}`}
          role="listitem"
          aria-label={message.isError ? "Tool error result" : "Tool result"}
        >
          <div className="result-header">
            <span className="result-icon" aria-hidden="true">{message.isError ? "!" : ">"}</span>
            <span className="result-label">{message.isError ? "Error" : "Result"}</span>
            {isLong && (
              <button
                className="result-toggle"
                onClick={() => setExpanded(!expanded)}
                aria-expanded={expanded}
                aria-label={expanded ? "Collapse result" : "Expand result"}
              >
                {expanded ? "Collapse" : "Expand"}
              </button>
            )}
          </div>
          <pre
            className={`result-content ${!expanded && isLong ? "truncated" : ""}`}
            aria-label="Tool output"
          >
            {expanded || !isLong ? resultContent : resultContent.substring(0, 300) + "..."}
          </pre>
          <div className="message-meta" aria-label={`Sent at ${message.timestamp.toLocaleTimeString()}`}>
            {message.timestamp.toLocaleTimeString()}
          </div>
        </div>
      );

    case "error":
      return (
        <div className="message message-error" role="listitem" aria-label="Error message">
          <span className="error-icon" aria-hidden="true">!</span>
          <span className="error-content">{String(message.content)}</span>
        </div>
      );

    case "system":
      return (
        <div className="message message-system" role="listitem" aria-label="System message">
          <span className="system-icon" aria-hidden="true">i</span>
          <span className="system-content">{String(message.content)}</span>
        </div>
      );

    default:
      return null;
  }
}

// ============================================================================
// Helpers
// ============================================================================

function truncatePath(path: string, maxLength: number): string {
  if (path.length <= maxLength) return path;
  const parts = path.split("/");
  let result = parts[parts.length - 1];
  for (let i = parts.length - 2; i >= 0 && result.length < maxLength - 4; i--) {
    result = parts[i] + "/" + result;
  }
  return ".../" + result;
}

// ============================================================================
// Styles
// ============================================================================

const styles = `
/* ============================================================================
   CSS VARIABLES - Theme Support
   ============================================================================ */

:root, .theme-dark {
  --agent-bg-primary: #0a0e18;
  --agent-bg-secondary: #111827;
  --agent-bg-tertiary: #1e293b;
  --agent-bg-accent: #0f172a;
  --agent-text-primary: #e2e8f0;
  --agent-text-secondary: #94a3b8;
  --agent-text-muted: #64748b;
  --agent-text-disabled: #475569;
  --agent-border-primary: #1e293b;
  --agent-border-secondary: #334155;
  --agent-accent-blue: #3b82f6;
  --agent-accent-blue-hover: #2563eb;
  --agent-accent-green: #10b981;
  --agent-accent-red: #ef4444;
  --agent-accent-red-hover: #dc2626;
  --agent-accent-yellow: #f59e0b;
  --agent-accent-purple: #8b5cf6;
  --agent-error-bg: #450a0a;
  --agent-error-border: #ef4444;
  --agent-error-text: #fca5a5;
  --agent-success-bg: rgba(16, 185, 129, 0.15);
  --agent-info-bg: #172554;
  --agent-shadow: rgba(0, 0, 0, 0.3);
}

.theme-light {
  --agent-bg-primary: #f8fafc;
  --agent-bg-secondary: #ffffff;
  --agent-bg-tertiary: #f1f5f9;
  --agent-bg-accent: #e2e8f0;
  --agent-text-primary: #1e293b;
  --agent-text-secondary: #475569;
  --agent-text-muted: #64748b;
  --agent-text-disabled: #94a3b8;
  --agent-border-primary: #e2e8f0;
  --agent-border-secondary: #cbd5e1;
  --agent-accent-blue: #2563eb;
  --agent-accent-blue-hover: #1d4ed8;
  --agent-accent-green: #059669;
  --agent-accent-red: #dc2626;
  --agent-accent-red-hover: #b91c1c;
  --agent-accent-yellow: #d97706;
  --agent-accent-purple: #7c3aed;
  --agent-error-bg: #fef2f2;
  --agent-error-border: #fca5a5;
  --agent-error-text: #991b1b;
  --agent-success-bg: rgba(5, 150, 105, 0.1);
  --agent-info-bg: #eff6ff;
  --agent-shadow: rgba(0, 0, 0, 0.1);
}

/* Visually hidden but accessible to screen readers */
.visually-hidden {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

.claude-agent-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--agent-bg-primary);
  color: var(--agent-text-primary);
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  position: relative;
  overflow: hidden;
}

.claude-agent-view.sidebar-open {
  padding-left: 280px;
}

/* Connection Error Banner */
.connection-error-banner {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 16px;
  background: var(--agent-error-bg);
  border-bottom: 1px solid var(--agent-error-border);
  color: var(--agent-error-text);
  font-size: 13px;
  animation: slideDown 0.3s ease-out;
}

@keyframes slideDown {
  from {
    transform: translateY(-100%);
    opacity: 0;
  }
  to {
    transform: translateY(0);
    opacity: 1;
  }
}

.connection-error-banner .error-icon {
  font-size: 16px;
  color: var(--agent-error-text);
}

.connection-error-banner .error-message {
  flex: 1;
}

.connection-error-banner .retry-btn {
  padding: 4px 12px;
  font-size: 12px;
  font-weight: 500;
  background: var(--agent-accent-red);
  border: none;
  border-radius: 4px;
  color: white;
  cursor: pointer;
  transition: background 0.2s;
}

.connection-error-banner .retry-btn:hover {
  background: var(--agent-accent-red-hover);
}

.connection-error-banner .dismiss-btn {
  padding: 4px 8px;
  font-size: 18px;
  background: transparent;
  border: none;
  color: var(--agent-error-text);
  cursor: pointer;
  opacity: 0.7;
  transition: opacity 0.2s;
}

.connection-error-banner .dismiss-btn:hover {
  opacity: 1;
}

/* Continue toggle */
.continue-toggle {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  font-size: 11px;
  background: var(--agent-bg-tertiary);
  border: 1px solid var(--agent-border-secondary);
  border-radius: 4px;
  color: var(--agent-text-muted);
  cursor: pointer;
  transition: all 0.2s;
}

.continue-toggle:hover {
  background: var(--agent-border-secondary);
  color: var(--agent-text-secondary);
}

.continue-toggle.active {
  background: var(--agent-success-bg);
  border-color: var(--agent-accent-green);
  color: var(--agent-accent-green);
}

.toggle-icon {
  font-size: 12px;
}

.toggle-label {
  font-weight: 500;
}

/* Token usage display */
.token-usage {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  font-size: 11px;
  background: var(--agent-bg-tertiary);
  border: 1px solid var(--agent-border-secondary);
  border-radius: 4px;
  color: var(--agent-text-secondary);
}

.token-icon {
  color: var(--agent-accent-yellow);
}

.token-count {
  font-weight: 500;
  color: var(--agent-text-primary);
}

.token-cost {
  color: var(--agent-accent-green);
  font-weight: 500;
}

/* Header */
.claude-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: var(--agent-bg-secondary);
  border-bottom: 1px solid var(--agent-border-primary);
}

.claude-header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.claude-title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--agent-text-primary);
}

.claude-status {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.status-dot.connected {
  background: var(--agent-accent-green);
}

.status-dot.connecting {
  background: var(--agent-accent-yellow);
  animation: pulse 1s infinite;
}

.status-dot.disconnected {
  background: var(--agent-accent-red);
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.claude-model {
  font-size: 11px;
  padding: 2px 8px;
  background: var(--agent-bg-tertiary);
  border-radius: 4px;
  color: var(--agent-text-secondary);
}

.claude-header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.claude-cwd {
  font-size: 11px;
  color: var(--agent-text-muted);
  font-family: monospace;
}

.claude-header-actions {
  display: flex;
  gap: 8px;
}

.header-btn {
  padding: 4px 12px;
  font-size: 12px;
  background: var(--agent-bg-tertiary);
  border: 1px solid var(--agent-border-secondary);
  border-radius: 4px;
  color: var(--agent-text-secondary);
  cursor: pointer;
  transition: all 0.2s;
}

.header-btn:hover {
  background: var(--agent-border-secondary);
  color: var(--agent-text-primary);
}

.header-btn.primary {
  background: var(--agent-accent-blue);
  border-color: var(--agent-accent-blue);
  color: white;
}

.header-btn.primary:hover {
  background: var(--agent-accent-blue-hover);
}

.header-btn.theme-toggle {
  font-size: 14px;
  padding: 4px 8px;
}

.header-btn.theme-toggle:hover {
  background: var(--agent-border-secondary);
}

/* Messages Container */
.claude-messages-container {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

.claude-messages {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* Empty State */
.claude-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  text-align: center;
  color: var(--agent-text-muted);
}

.empty-icon {
  font-size: 48px;
  margin-bottom: 16px;
}

.claude-empty h3 {
  margin: 0 0 8px;
  color: var(--agent-text-secondary);
}

.claude-empty p {
  margin: 0 0 4px;
  font-size: 14px;
}

.empty-hint {
  font-size: 12px;
  color: var(--agent-text-disabled);
}

/* Messages */
.message {
  padding: 12px;
  border-radius: 8px;
  background: var(--agent-bg-secondary);
  border: 1px solid var(--agent-border-primary);
}

.message-meta {
  font-size: 10px;
  color: var(--agent-text-disabled);
  margin-top: 8px;
  text-align: right;
}

.message-text-content {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: inherit;
  font-size: 14px;
  line-height: 1.5;
}

/* Tool Use */
.message-tool-use {
  background: var(--agent-bg-accent);
  border-color: var(--agent-accent-blue);
}

.tool-header {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
  background: transparent;
  border: none;
  width: 100%;
  text-align: left;
  color: inherit;
  font: inherit;
}

.tool-header:hover {
  background: var(--agent-bg-tertiary);
}

.tool-header:focus {
  outline: 2px solid var(--agent-accent-blue);
  outline-offset: 2px;
}

.tool-header:focus:not(:focus-visible) {
  outline: none;
}

.tool-icon {
  font-size: 16px;
}

.tool-name {
  font-weight: 500;
  color: var(--agent-accent-blue);
  font-family: monospace;
}

.tool-expand {
  margin-left: auto;
  font-size: 10px;
  color: var(--agent-text-muted);
}

.tool-details {
  margin-top: 8px;
  padding: 8px;
  background: var(--agent-bg-primary);
  border-radius: 4px;
}

.tool-input {
  margin: 0;
  font-size: 12px;
  font-family: 'JetBrains Mono', monospace;
  color: var(--agent-text-secondary);
  white-space: pre-wrap;
  word-break: break-word;
}

/* Tool Result */
.message-tool-result {
  background: var(--agent-bg-accent);
  border-color: var(--agent-accent-green);
}

.message-tool-result.error {
  border-color: var(--agent-accent-red);
}

.result-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.result-icon {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: var(--agent-accent-green);
  color: white;
  font-size: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.message-tool-result.error .result-icon {
  background: var(--agent-accent-red);
}

.result-label {
  font-size: 12px;
  font-weight: 500;
  color: var(--agent-text-muted);
}

.result-toggle {
  margin-left: auto;
  padding: 2px 8px;
  font-size: 10px;
  background: transparent;
  border: 1px solid var(--agent-border-secondary);
  border-radius: 4px;
  color: var(--agent-text-muted);
  cursor: pointer;
}

.result-toggle:hover {
  background: var(--agent-bg-tertiary);
}

.result-content {
  margin: 0;
  font-size: 12px;
  font-family: 'JetBrains Mono', monospace;
  color: var(--agent-text-secondary);
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 400px;
  overflow-y: auto;
}

.result-content.truncated {
  max-height: 100px;
  overflow: hidden;
}

/* Error Message */
.message-error {
  background: var(--agent-error-bg);
  border-color: var(--agent-accent-red);
  display: flex;
  align-items: flex-start;
  gap: 8px;
}

.message-error .error-icon {
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: var(--agent-accent-red);
  color: white;
  font-size: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.message-error .error-content {
  color: var(--agent-error-text);
  font-size: 13px;
}

/* System Message */
.message-system {
  background: var(--agent-info-bg);
  border-color: var(--agent-accent-blue);
  display: flex;
  align-items: flex-start;
  gap: 8px;
  font-size: 12px;
  color: var(--agent-accent-blue);
}

.system-icon {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  background: var(--agent-accent-blue);
  color: white;
  font-size: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

/* Thinking */
.claude-thinking {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px;
  background: var(--agent-bg-tertiary);
  border-radius: 8px;
  color: var(--agent-text-secondary);
}

.thinking-content {
  display: flex;
  align-items: center;
  gap: 8px;
}

.thinking-icon {
  font-size: 20px;
  animation: bounce 1s infinite;
}

@keyframes bounce {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-4px); }
}

.thinking-text {
  font-size: 14px;
}

.active-tools {
  font-size: 12px;
  padding: 2px 8px;
  background: var(--agent-accent-blue);
  color: white;
  border-radius: 4px;
}

.escape-hint {
  margin-left: auto;
  font-size: 11px;
  color: var(--agent-text-disabled);
}

.thinking-progress {
  height: 3px;
  background: var(--agent-bg-accent);
  border-radius: 2px;
  overflow: hidden;
}

.progress-bar {
  height: 100%;
  width: 30%;
  background: linear-gradient(90deg, var(--agent-accent-blue), var(--agent-accent-purple), var(--agent-accent-blue));
  background-size: 200% 100%;
  animation: progress-move 1.5s ease-in-out infinite;
  border-radius: 2px;
}

@keyframes progress-move {
  0% { transform: translateX(-100%); background-position: 0% 0%; }
  50% { background-position: 100% 0%; }
  100% { transform: translateX(400%); background-position: 0% 0%; }
}

/* Error Display */
.claude-error {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px;
  background: var(--agent-error-bg);
  border: 1px solid var(--agent-accent-red);
  border-radius: 8px;
  color: var(--agent-error-text);
}

.claude-error .error-icon {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  background: var(--agent-accent-red);
  color: white;
  font-size: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* Input Area */
.claude-input-container {
  padding: 16px;
  background: var(--agent-bg-secondary);
  border-top: 1px solid var(--agent-border-primary);
}

.claude-input-form {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.claude-input {
  width: 100%;
  padding: 12px;
  background: var(--agent-bg-primary);
  border: 1px solid var(--agent-border-secondary);
  border-radius: 8px;
  color: var(--agent-text-primary);
  font-size: 14px;
  font-family: inherit;
  resize: none;
  outline: none;
  transition: border-color 0.2s;
}

.claude-input:focus {
  border-color: var(--agent-accent-blue);
}

.claude-input:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.claude-input::placeholder {
  color: var(--agent-text-muted);
}

.claude-input-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.claude-send-btn {
  padding: 8px 24px;
  background: var(--agent-accent-blue);
  border: none;
  border-radius: 6px;
  color: white;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.2s;
}

.claude-send-btn:hover:not(:disabled) {
  background: var(--agent-accent-blue-hover);
}

.claude-send-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.claude-cancel-btn {
  padding: 8px 24px;
  background: var(--agent-accent-red);
  border: none;
  border-radius: 6px;
  color: white;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.2s;
}

.claude-cancel-btn:hover {
  background: var(--agent-accent-red-hover);
}

/* ============================================================================
   RESPONSIVE DESIGN
   ============================================================================ */

/* Tablet (768px and below) */
@media (max-width: 768px) {
  .claude-agent-view.sidebar-open {
    padding-left: 0;
  }

  .claude-header {
    flex-direction: column;
    gap: 12px;
    padding: 12px;
  }

  .claude-header-left {
    width: 100%;
    flex-wrap: wrap;
    justify-content: flex-start;
  }

  .claude-header-right {
    width: 100%;
    justify-content: space-between;
  }

  .claude-cwd {
    display: none;
  }

  .token-usage {
    order: -1;
  }

  .claude-messages-container {
    padding: 12px;
  }

  .message {
    padding: 10px;
  }

  .claude-input-container {
    padding: 12px;
  }

  .tool-input,
  .result-content {
    font-size: 11px;
  }
}

/* Mobile (480px and below) */
@media (max-width: 480px) {
  .claude-header {
    padding: 10px;
  }

  .claude-title {
    font-size: 14px;
  }

  .claude-header-left {
    gap: 8px;
  }

  .claude-status .status-text {
    display: none;
  }

  .claude-model {
    max-width: 100px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .continue-toggle .toggle-label {
    display: none;
  }

  .token-usage .token-cost {
    display: none;
  }

  .header-btn {
    padding: 4px 8px;
    font-size: 11px;
  }

  .claude-header-actions {
    gap: 4px;
  }

  .connection-error-banner {
    flex-wrap: wrap;
    padding: 8px 12px;
    font-size: 12px;
  }

  .connection-error-banner .error-message {
    flex-basis: 100%;
    order: 2;
    margin-top: 4px;
  }

  .connection-error-banner .retry-btn {
    order: 3;
  }

  .claude-messages-container {
    padding: 8px;
  }

  .message {
    padding: 8px;
    border-radius: 6px;
  }

  .message-content {
    font-size: 13px;
  }

  .tool-header {
    font-size: 13px;
  }

  .tool-details {
    padding: 6px;
  }

  .tool-input,
  .result-content {
    font-size: 10px;
    max-height: 200px;
  }

  .claude-input-container {
    padding: 8px;
  }

  .claude-input {
    padding: 10px;
    font-size: 14px;
    rows: 2;
  }

  .claude-input-actions {
    flex-direction: row;
  }

  .claude-send-btn,
  .claude-cancel-btn {
    padding: 10px 16px;
    font-size: 13px;
    flex: 1;
  }

  .claude-thinking {
    padding: 10px;
  }

  .thinking-content {
    flex-wrap: wrap;
    gap: 6px;
  }

  .escape-hint {
    flex-basis: 100%;
    margin-left: 0;
    margin-top: 4px;
    text-align: center;
  }

  .claude-empty {
    padding: 20px;
  }

  .empty-icon {
    font-size: 36px;
  }

  .claude-empty h3 {
    font-size: 16px;
  }

  .claude-empty p {
    font-size: 13px;
  }
}

/* Small mobile (360px and below) */
@media (max-width: 360px) {
  .claude-header-left {
    gap: 6px;
  }

  .continue-toggle {
    padding: 3px 6px;
  }

  .token-usage {
    padding: 3px 6px;
  }

  .claude-title {
    font-size: 13px;
  }

  .message-meta {
    font-size: 9px;
  }
}
`;
