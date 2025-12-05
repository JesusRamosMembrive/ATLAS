/**
 * Claude Agent View
 *
 * UI for interacting with Claude Code via JSON streaming mode.
 * Replaces the TUI-based terminal with a structured, custom-rendered interface.
 */

import { useEffect, useRef, useState, useCallback } from "react";
import { useClaudeSessionStore, PERMISSION_MODES, PERMISSION_MODE_LABELS, PERMISSION_MODE_DESCRIPTIONS, type PermissionMode, AGENT_TYPES, AGENT_TYPE_LABELS, AGENT_WS_ENDPOINTS, AGENT_MODELS, AGENT_SLASH_COMMANDS, type AgentType, type SlashCommand } from "../stores/claudeSessionStore";
import { TerminalSocketIO, terminalSocketIOStyles } from "./TerminalSocketIO";
import { SlashCommandMenu, slashCommandMenuStyles } from "./SlashCommandMenu";
import { OpenShellModal, openShellModalStyles } from "./OpenShellModal";
import { useSessionHistoryStore } from "../stores/sessionHistoryStore";
import { useBackendStore } from "../state/useBackendStore";
import { resolveBackendBaseUrl } from "../api/client";
import {
  ClaudeMessage,
  PermissionDenial,
  formatToolInput,
} from "../types/claude-events";
import { MarkdownRenderer } from "./MarkdownRenderer";
import { AgentSidebar } from "./AgentSidebar";
import { FileDiffModal } from "./FileDiffModal";
import { ToolPermissionModal } from "./ToolPermissionModal";
import { ConnectedToolApprovalModal } from "./ToolApprovalModal";
import "./ToolApprovalModal.css";
import {
  MessageCircleIcon,
  BrainIcon,
  LockIcon,
  ZapIcon,
  ClipboardListIcon,
  AlertTriangleIcon,
  RefreshIcon,
  CircleIcon,
  InfoIcon,
  XCircleIcon,
  CheckCircleIcon,
  ChevronRightIcon,
  ChevronDownIcon,
  getToolIconComponent,
} from "./icons/AgentIcons";

// ============================================================================
// Helpers
// ============================================================================

/**
 * Extract clean content from tool result.
 * Handles JSON responses like {"result":"[ERROR] ..."} and extracts just the value.
 */
function extractResultContent(content: string): string {
  const trimmed = content.trim();

  // Try to parse as JSON and extract "result" field
  if (trimmed.startsWith("{") && trimmed.endsWith("}")) {
    try {
      const parsed = JSON.parse(trimmed);
      if (typeof parsed.result === "string") {
        return parsed.result;
      }
      // If it has other fields, show them more cleanly
      if (typeof parsed === "object" && parsed !== null) {
        const keys = Object.keys(parsed);
        if (keys.length === 1) {
          return String(parsed[keys[0]]);
        }
      }
    } catch {
      // Not valid JSON, return as-is
    }
  }

  return trimmed;
}

// ============================================================================
// Main Component
// ============================================================================

export function ClaudeAgentView() {
  const [promptValue, setPromptValue] = useState("");
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [diffTarget, setDiffTarget] = useState<string | null>(null);
  const [addingPermissions, setAddingPermissions] = useState<Set<string>>(new Set());
  const [slashMenuVisible, setSlashMenuVisible] = useState(false);
  const [slashFilter, setSlashFilter] = useState("");
  const [openShellModalVisible, setOpenShellModalVisible] = useState(false);
  const [terminalConnected, setTerminalConnected] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const inputContainerRef = useRef<HTMLDivElement>(null);

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
    permissionMode,
    totalInputTokens,
    totalOutputTokens,
    isReconnecting,
    reconnectAttempts,
    maxReconnectAttempts,
    pendingPermission,
    permissionDenials,
    // Plan execution state (for toolApproval mode)
    planDescriptionOnly,
    connect,
    disconnect,
    sendPrompt,
    cancel,
    newSession,
    clearMessages,
    clearConnectionError,
    setPermissionMode,
    respondToPermission,
    clearPermissionDenials,
    // Plan execution action
    executePlan,
    // Agent type selection
    agentType,
    setAgentType,
    // Model selection
    selectedModels,
    setSelectedModel,
  } = useClaudeSessionStore();

  // Session history
  const { saveSession } = useSessionHistoryStore();

  const backendUrl = useBackendStore((state) => state.backendUrl);

  // Build WebSocket URL based on selected agent type
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

    // Get the endpoint for the selected agent type
    const endpoint = AGENT_WS_ENDPOINTS[agentType];
    return `${wsBase}${endpoint}`;
  }, [backendUrl, agentType]);

  // Check if this agent uses embedded terminal (not streaming WebSocket)
  const usesTerminalSocketIO = agentType === "codex" || agentType === "gemini";

  // Auto-connect on mount
  useEffect(() => {
    // Only connect if not already connected, connecting, or in the middle of reconnecting
    // The store handles reconnection logic internally via onclose handler
    // IMPORTANT: Don't connect for Codex/Gemini - they use Socket.IO terminal
    if (usesTerminalSocketIO) {
      // Disconnect if previously connected (e.g., switching from Claude)
      if (connected) {
        console.log("[ClaudeAgent] Terminal Socket.IO mode - disconnecting stream WebSocket");
        disconnect();
      }
      return;
    }

    if (!connected && !connecting && !isReconnecting) {
      const wsUrl = getWsUrl();
      console.log("[ClaudeAgent] Connecting to:", wsUrl);
      connect(wsUrl);
    }
  }, [connected, connecting, isReconnecting, connect, getWsUrl, usesTerminalSocketIO, disconnect]);

  // Reconnect when agent type changes
  useEffect(() => {
    // Don't reconnect if switching to Codex/Gemini - they use Socket.IO terminal
    if (usesTerminalSocketIO) {
      if (connected) {
        console.log("[ClaudeAgent] Switching to terminal Socket.IO mode - disconnecting stream WebSocket");
        disconnect();
      }
      // Clear messages when switching agents
      clearMessages();
      return;
    }

    // Only reconnect if we were previously connected (switching back to Claude)
    if (connected) {
      console.log("[ClaudeAgent] Agent type changed to:", agentType, "- reconnecting...");
      disconnect();
      // Clear messages for new agent
      clearMessages();
      // Small delay to ensure clean disconnect
      const timer = setTimeout(() => {
        const wsUrl = getWsUrl();
        console.log("[ClaudeAgent] Reconnecting to:", wsUrl);
        connect(wsUrl);
      }, 100);
      return () => clearTimeout(timer);
    }
  }, [agentType, usesTerminalSocketIO]); // eslint-disable-line react-hooks/exhaustive-deps

  // Auto-scroll to bottom when messages change
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Auto-save session when messages change (debounced)
  useEffect(() => {
    if (messages.length > 0 && !running) {
      const timer = setTimeout(() => {
        saveSession(sessionInfo.sessionId, sessionInfo.model, agentType, messages);
      }, 1000);
      return () => clearTimeout(timer);
    }
  }, [messages, running, sessionInfo.sessionId, sessionInfo.model, agentType, saveSession]);

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

  // Handle input change - detect slash commands
  const handleInputChange = useCallback(
    (e: React.ChangeEvent<HTMLTextAreaElement>) => {
      const value = e.target.value;
      setPromptValue(value);

      // Check if input starts with "/" for slash command menu
      if (value.startsWith("/")) {
        // Extract filter text (everything after the /)
        const filter = value.slice(1).split(" ")[0]; // Only filter on first word
        setSlashFilter(filter);
        setSlashMenuVisible(true);
      } else {
        setSlashMenuVisible(false);
        setSlashFilter("");
      }
    },
    []
  );

  // Handle slash command selection - show modal to open native terminal
  const handleSlashCommandSelect = useCallback(
    (_command: SlashCommand) => {
      // All slash commands require a native terminal - show the modal
      setSlashMenuVisible(false);
      setSlashFilter("");
      setPromptValue("");
      setOpenShellModalVisible(true);
    },
    []
  );

  // Handle opening native terminal with agent
  const handleOpenNativeTerminal = useCallback(async () => {
    try {
      const baseUrl = resolveBackendBaseUrl(backendUrl) ?? "http://127.0.0.1:8010";
      const response = await fetch(`${baseUrl}/api/terminal/open-native`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          agent_type: agentType,
          working_directory: cwd,
        }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || `Failed to open terminal: ${response.statusText}`);
      }

      const result = await response.json();
      console.log("[ClaudeAgent] Native terminal opened:", result);
    } catch (error) {
      console.error("[ClaudeAgent] Failed to open native terminal:", error);
      alert(`Failed to open terminal: ${error instanceof Error ? error.message : String(error)}`);
    }
  }, [backendUrl, agentType, cwd]);

  // Close slash menu
  const handleSlashMenuClose = useCallback(() => {
    setSlashMenuVisible(false);
    setSlashFilter("");
  }, []);

  // Handle key press in textarea
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      // Don't handle Enter/Tab if slash menu is visible (menu handles it)
      if (slashMenuVisible && (e.key === "Enter" || e.key === "Tab" || e.key === "ArrowDown" || e.key === "ArrowUp")) {
        return; // Let the menu handle these keys
      }

      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        handleSubmit();
      }
    },
    [handleSubmit, slashMenuVisible]
  );

  // Handle cancel
  const handleCancel = useCallback(() => {
    cancel();
  }, [cancel]);

  // Global keyboard shortcuts
  useEffect(() => {
    const handleGlobalKeyDown = (e: KeyboardEvent) => {
      // Escape to cancel running operation
      if (e.key === "Escape" && running) {
        e.preventDefault();
        handleCancel();
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
  }, [running, handleCancel, clearMessages, newSession]);

  // Reconnect
  const handleReconnect = useCallback(() => {
    disconnect();
    setTimeout(() => {
      const wsUrl = getWsUrl();
      connect(wsUrl);
    }, 100);
  }, [disconnect, connect, getWsUrl]);

  // Add permission to settings.local.json
  const handleAddPermission = useCallback(
    async (toolName: string) => {
      setAddingPermissions((prev) => new Set(prev).add(toolName));
      try {
        const baseUrl = resolveBackendBaseUrl(backendUrl) ?? "http://127.0.0.1:8010";
        const response = await fetch(`${baseUrl}/api/claude-permissions/add`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ permissions: [toolName] }),
        });
        if (!response.ok) {
          throw new Error(`Failed to add permission: ${response.statusText}`);
        }
        const result = await response.json();
        console.log("[ClaudeAgent] Permission added:", result);
        // Remove this denial from the list
        useClaudeSessionStore.setState((state) => ({
          permissionDenials: state.permissionDenials.filter(
            (d) => d.tool_name !== toolName
          ),
        }));
      } catch (error) {
        console.error("[ClaudeAgent] Failed to add permission:", error);
        alert(`Failed to add permission: ${error}`);
      } finally {
        setAddingPermissions((prev) => {
          const next = new Set(prev);
          next.delete(toolName);
          return next;
        });
      }
    },
    [backendUrl]
  );

  return (
    <div
      className={`claude-agent-view ${sidebarOpen ? "sidebar-open" : ""}`}
      role="main"
      aria-label="Claude Agent Interface"
    >
      {/* Unified Sidebar with tabs */}
      <AgentSidebar
        isOpen={sidebarOpen}
        onToggle={() => setSidebarOpen(!sidebarOpen)}
        onLoadSession={handleLoadSession}
        onNewSession={handleNewSessionFromSidebar}
        onShowDiff={setDiffTarget}
        totalInputTokens={totalInputTokens}
        totalOutputTokens={totalOutputTokens}
        agentType={agentType}
      />

      {/* Glass Card Container */}
      <div className="claude-agent-card">
        {/* Header */}
        <AgentHeader
        connected={usesTerminalSocketIO ? terminalConnected : connected}
        connecting={usesTerminalSocketIO ? false : connecting}
        running={running}
        sessionInfo={sessionInfo}
        cwd={cwd}
        continueSession={continueSession}
        agentType={agentType}
        onAgentTypeChange={setAgentType}
        selectedModel={selectedModels[agentType]}
        onModelChange={(model) => setSelectedModel(agentType, model)}
        permissionMode={permissionMode}
        onPermissionModeChange={setPermissionMode}
        totalInputTokens={totalInputTokens}
        totalOutputTokens={totalOutputTokens}
        isReconnecting={isReconnecting}
        reconnectAttempts={reconnectAttempts}
        maxReconnectAttempts={maxReconnectAttempts}
        onReconnect={handleReconnect}
        onNewSession={newSession}
        onClearMessages={clearMessages}
        usesTerminal={usesTerminalSocketIO}
      />

      {/* Connection Error Banner */}
      {connectionError && (
        <div className="connection-error-banner" role="alert">
          <span className="error-icon"><AlertTriangleIcon size={16} /></span>
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

      {/* Conditional: Terminal Socket.IO (Codex/Gemini) OR Claude Stream Mode */}
      {usesTerminalSocketIO ? (
        /* Terminal Socket.IO Mode - for Codex and Gemini */
        <div className="agent-terminal-wrapper">
          <style>{terminalSocketIOStyles}</style>
          <TerminalSocketIO
            autoConnect
            welcomeMessage={`${AGENT_TYPE_LABELS[agentType]} Terminal`}
            height="100%"
            className="agent-terminal-embed"
            onConnectionChange={setTerminalConnected}
            initialCommand={agentType === "gemini" ? "gemini" : agentType === "codex" ? "codex" : undefined}
          />
        </div>
      ) : (
        /* Stream Mode - JSON streaming with messages and input */
        <>
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
                      <span className="thinking-icon" aria-hidden="true">
                        <BrainIcon size={20} />
                      </span>
                      <span className="thinking-text">The agent is thinking...</span>
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

                {/* Execute Plan button - shown when Claude only described actions */}
                {planDescriptionOnly && !running && (
                  <div className="execute-plan-banner" role="status">
                    <div className="plan-banner-content">
                      <span className="plan-banner-icon" aria-hidden="true"><ClipboardListIcon size={20} /></span>
                      <span className="plan-banner-text">
                        Claude described changes above. Click "Execute Plan" to apply them automatically.
                      </span>
                    </div>
                    <button
                      className="execute-plan-btn"
                      onClick={executePlan}
                      aria-label="Execute the described plan automatically"
                    >
                      <ZapIcon size={16} /> Execute Plan
                    </button>
                  </div>
                )}

                {/* Error display */}
                {lastError && (
                  <div className="claude-error" role="alert" aria-live="assertive">
                    <span className="error-icon" aria-hidden="true">!</span>
                    <span className="error-text">{lastError}</span>
                  </div>
                )}

                {/* Permission denials - tools that were blocked */}
                {permissionDenials.length > 0 && (
                  <PermissionDenialsBanner
                    denials={permissionDenials}
                    onAddPermission={handleAddPermission}
                    onClear={clearPermissionDenials}
                    addingPermissions={addingPermissions}
                  />
                )}

                <div ref={messagesEndRef} />
              </div>
            )}
          </div>

          {/* Input Area */}
          <div className="claude-input-container" ref={inputContainerRef}>
            <form onSubmit={handleSubmit} className="claude-input-form" role="form" aria-label="Send message to Claude">
              <div className="claude-input-wrapper">
                <label htmlFor="claude-prompt-input" className="visually-hidden">
                  Enter your message for Claude
                </label>
                <textarea
                  id="claude-prompt-input"
                  ref={inputRef}
                  value={promptValue}
                  onChange={handleInputChange}
                  onKeyDown={handleKeyDown}
                  placeholder={
                    connected
                      ? `Ask ${AGENT_TYPE_LABELS[agentType]} anything... (Type / for commands)`
                      : "Connecting..."
                  }
                  disabled={!connected || running}
                  className="claude-input"
                  rows={3}
                  aria-describedby="input-hint"
                  aria-haspopup="listbox"
                  aria-expanded={slashMenuVisible}
                />
                <span id="input-hint" className="visually-hidden">
                  Press Enter to send, Shift+Enter for new line. Type / to see available commands.
                </span>
                {/* Slash Command Menu */}
                <SlashCommandMenu
                  commands={AGENT_SLASH_COMMANDS[agentType]}
                  filter={slashFilter}
                  onSelect={handleSlashCommandSelect}
                  onClose={handleSlashMenuClose}
                  visible={slashMenuVisible}
                />
              </div>
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
                    onClick={handleCancel}
                    className="claude-cancel-btn"
                    aria-label="Cancel current operation"
                  >
                    Cancel
                  </button>
                )}
              </div>
            </form>
          </div>
        </>
      )}
      </div>{/* End of claude-agent-card */}

      <style>{styles}</style>
      <style>{slashCommandMenuStyles}</style>
      <style>{openShellModalStyles}</style>

      {/* Open Shell Modal - shown when user selects a slash command */}
      <OpenShellModal
        visible={openShellModalVisible}
        agentType={agentType}
        workingDirectory={cwd ?? undefined}
        onClose={() => setOpenShellModalVisible(false)}
        onConfirm={handleOpenNativeTerminal}
      />

      {/* File Diff Modal */}
      {diffTarget && <FileDiffModal path={diffTarget} onClose={() => setDiffTarget(null)} />}

      {/* Tool Permission Modal */}
      {pendingPermission && (
        <ToolPermissionModal
          permission={pendingPermission}
          onApprove={(always) => respondToPermission(true, always)}
          onDeny={() => respondToPermission(false)}
        />
      )}

      {/* Tool Approval Modal (for toolApproval mode) */}
      <ConnectedToolApprovalModal />
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
  agentType: AgentType;
  onAgentTypeChange: (type: AgentType) => void;
  selectedModel: string;
  onModelChange: (model: string) => void;
  permissionMode: PermissionMode;
  onPermissionModeChange: (mode: PermissionMode) => void;
  totalInputTokens: number;
  totalOutputTokens: number;
  isReconnecting: boolean;
  reconnectAttempts: number;
  maxReconnectAttempts: number;
  onReconnect: () => void;
  onNewSession: () => void;
  onClearMessages: () => void;
  usesTerminal: boolean;
}

function AgentHeader({
  connected,
  connecting,
  sessionInfo,
  cwd,
  continueSession,
  agentType,
  onAgentTypeChange,
  selectedModel,
  onModelChange,
  permissionMode,
  onPermissionModeChange,
  totalInputTokens,
  totalOutputTokens,
  isReconnecting,
  reconnectAttempts,
  maxReconnectAttempts,
  onReconnect,
  onNewSession,
  onClearMessages,
  usesTerminal,
}: AgentHeaderProps) {
  const toggleContinueSession = useCallback(() => {
    useClaudeSessionStore.setState((state) => ({
      continueSession: !state.continueSession,
    }));
  }, []);

  const totalTokens = totalInputTokens + totalOutputTokens;
  const estimatedCost = ((totalInputTokens * 3 + totalOutputTokens * 15) / 1_000_000).toFixed(4);

  // Get dynamic title based on agent type
  const agentTitle = AGENT_TYPE_LABELS[agentType] || "AI Agent";

  return (
    <div className="claude-header">
      <div className="claude-header-left">
        <h2 className="claude-title">{agentTitle}</h2>
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
              ? "Continue mode: ON - Will resume previous session"
              : "Continue mode: OFF - Will start fresh session"
          }
        >
          <span className="toggle-icon">{continueSession ? <RefreshIcon size={12} /> : <CircleIcon size={12} />}</span>
          <span className="toggle-label">
            {continueSession ? "Continue" : "Fresh"}
          </span>
        </button>
        <select
          className="agent-type-select"
          value={agentType}
          onChange={(e) => onAgentTypeChange(e.target.value as AgentType)}
          title="Select AI agent CLI to use"
        >
          {AGENT_TYPES.map((type) => (
            <option key={type} value={type}>
              {AGENT_TYPE_LABELS[type]}
            </option>
          ))}
        </select>
        {!usesTerminal && (
          <>
            <select
              className="model-select"
              value={selectedModel}
              onChange={(e) => onModelChange(e.target.value)}
              title={`Select model for ${AGENT_TYPE_LABELS[agentType]}`}
            >
              {AGENT_MODELS[agentType].map((model) => (
                <option key={model} value={model}>
                  {model}
                </option>
              ))}
            </select>
            <select
              className="permission-mode-select"
              value={permissionMode}
              onChange={(e) => onPermissionModeChange(e.target.value as PermissionMode)}
              title={`Permission mode: ${PERMISSION_MODE_DESCRIPTIONS[permissionMode]}\n\nNote: Stream mode doesn't support interactive prompts. Use 'Bypass All' for full autonomy or configure allowed tools in .claude/settings.local.json`}
            >
              {PERMISSION_MODES.map((mode) => (
                <option key={mode} value={mode} title={PERMISSION_MODE_DESCRIPTIONS[mode]}>
                  {PERMISSION_MODE_LABELS[mode]}
                </option>
              ))}
            </select>
          </>
        )}
        {totalTokens > 0 && (
          <span
            className="token-usage"
            title={`Input: ${totalInputTokens.toLocaleString()} | Output: ${totalOutputTokens.toLocaleString()} | Est. cost: $${estimatedCost}`}
          >
            <span className="token-icon"><ZapIcon size={12} /></span>
            <span className="token-count">{totalTokens.toLocaleString()}</span>
            <span className="token-cost">${estimatedCost}</span>
          </span>
        )}
      </div>
      <div className="claude-header-right">
        {cwd && <span className="claude-cwd" title={cwd}>{truncatePath(cwd, 40)}</span>}
        {!usesTerminal && (
          <div className="claude-header-actions">
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
        )}
      </div>
    </div>
  );
}

function EmptyState() {
  return (
    <div className="claude-empty">
      <div className="empty-icon">
        <MessageCircleIcon size={48} />
      </div>
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
  const isUser = message.role === "user";

  // User messages: right-aligned with card
  if (isUser && message.type === "text") {
    const textContent = message.content != null ? String(message.content) : "";
    return (
      <div className="message-row user" role="listitem" aria-label="Your message">
        <div className="user-message-card">
          <div className="user-message-content">{textContent}</div>
          <div className="message-meta">
            {message.timestamp.toLocaleTimeString()}
          </div>
        </div>
      </div>
    );
  }

  // Assistant messages: left-aligned without card
  switch (message.type) {
    case "text":
      const textContent = message.content != null ? String(message.content) : "";
      const isShortText = textContent.length < 100 && !textContent.includes('\n');
      return (
        <div className="message-row assistant" role="listitem" aria-label="Claude response">
          {isShortText ? (
            <div className="assistant-message assistant-text-inline">
              <span className="text-icon" aria-hidden="true">
                <MessageCircleIcon size={14} />
              </span>
              <span className="text-content">{textContent}</span>
            </div>
          ) : (
            <div className="assistant-message">
              <MarkdownRenderer content={textContent} />
              <div className="message-meta">
                {message.timestamp.toLocaleTimeString()}
              </div>
            </div>
          )}
        </div>
      );

    case "tool_use":
      const toolContent = message.content as {
        id: string;
        name: string;
        input: Record<string, unknown>;
      };
      const ToolIcon = getToolIconComponent(toolContent.name);
      return (
        <div className="message-row assistant" role="listitem" aria-label={`Tool call: ${toolContent.name}`}>
          <div className="assistant-message message-tool-use">
            <button
              className="tool-header"
              onClick={() => setExpanded(!expanded)}
              aria-expanded={expanded}
              aria-controls={`tool-details-${toolContent.id}`}
            >
              <span className="tool-icon" aria-hidden="true">
                <ToolIcon size={16} />
              </span>
              <span className="tool-name">{toolContent.name}</span>
              <span className="tool-expand" aria-hidden="true">
                {expanded ? <ChevronDownIcon size={12} /> : <ChevronRightIcon size={12} />}
              </span>
            </button>
            {expanded && (
              <div id={`tool-details-${toolContent.id}`} className="tool-details">
                <pre className="tool-input" aria-label="Tool input parameters">
                  {formatToolInput(toolContent.input, 500)}
                </pre>
              </div>
            )}
            <div className="message-meta">
              {message.timestamp.toLocaleTimeString()}
            </div>
          </div>
        </div>
      );

    case "tool_result":
      const rawResultContent = message.content != null ? String(message.content) : "";
      const resultContent = extractResultContent(rawResultContent);
      const isLong = resultContent.length > 300;
      const isMultiline = resultContent.includes('\n');
      const isInline = !isLong && !isMultiline;
      return (
        <div className="message-row assistant" role="listitem" aria-label={message.isError ? "Tool error result" : "Tool result"}>
          <div className={`assistant-message message-tool-result ${message.isError ? "error" : ""} ${isInline ? "inline" : ""}`}>
            <div className="result-header">
              <span className="result-icon" aria-hidden="true">
                {message.isError ? <XCircleIcon size={14} /> : <CheckCircleIcon size={14} />}
              </span>
              <span className="result-label">{message.isError ? "Error" : "Result"}</span>
              {isInline ? (
                <span className="result-inline-content">{resultContent}</span>
              ) : (
                isLong && (
                  <button
                    className="result-toggle"
                    onClick={() => setExpanded(!expanded)}
                    aria-expanded={expanded}
                    aria-label={expanded ? "Collapse result" : "Expand result"}
                  >
                    {expanded ? "Collapse" : "Expand"}
                  </button>
                )
              )}
            </div>
            {!isInline && (
              <pre
                className={`result-content ${!expanded && isLong ? "truncated" : ""}`}
                aria-label="Tool output"
              >
                {expanded || !isLong ? resultContent : resultContent.substring(0, 300) + "..."}
              </pre>
            )}
          </div>
        </div>
      );

    case "error":
      const errorMsgContent = message.content != null ? String(message.content) : "Unknown error";
      return (
        <div className="message-row assistant" role="listitem" aria-label="Error message">
          <div className="assistant-message message-error">
            <span className="error-icon" aria-hidden="true">
              <XCircleIcon size={18} />
            </span>
            <span className="error-content">{errorMsgContent}</span>
          </div>
        </div>
      );

    case "system":
      const systemMsgContent = message.content != null ? String(message.content) : "";
      return (
        <div className="message-row assistant" role="listitem" aria-label="System message">
          <div className="assistant-message message-system">
            <span className="system-icon" aria-hidden="true">
              <InfoIcon size={16} />
            </span>
            <span className="system-content">{systemMsgContent}</span>
          </div>
        </div>
      );

    default:
      return null;
  }
}

// ============================================================================
// Permission Denials Banner
// ============================================================================

interface PermissionDenialsBannerProps {
  denials: PermissionDenial[];
  onAddPermission: (toolName: string) => void;
  onClear: () => void;
  addingPermissions: Set<string>;
}

function PermissionDenialsBanner({
  denials,
  onAddPermission,
  onClear,
  addingPermissions,
}: PermissionDenialsBannerProps) {
  // Group denials by tool name to avoid duplicates
  const uniqueTools = Array.from(new Set(denials.map((d) => d.tool_name)));

  return (
    <div className="permission-denials-banner" role="alert">
      <div className="denials-header">
        <span className="denials-icon" aria-hidden="true"><LockIcon size={18} /></span>
        <span className="denials-title">
          {uniqueTools.length} tool{uniqueTools.length > 1 ? "s" : ""} blocked due to missing permissions
        </span>
        <button
          className="denials-clear"
          onClick={onClear}
          title="Dismiss"
          aria-label="Dismiss blocked tools notification"
        >
          ×
        </button>
      </div>
      <div className="denials-list">
        {uniqueTools.map((toolName) => {
          const denial = denials.find((d) => d.tool_name === toolName);
          const isAdding = addingPermissions.has(toolName);
          const ToolIconComponent = getToolIconComponent(toolName);
          return (
            <div key={toolName} className="denial-item">
              <span className="denial-tool-icon" aria-hidden="true">
                <ToolIconComponent size={16} />
              </span>
              <span className="denial-tool-name">{toolName}</span>
              {denial?.tool_input && (
                <span className="denial-tool-hint" title={JSON.stringify(denial.tool_input, null, 2)}>
                  {truncateInput(denial.tool_input)}
                </span>
              )}
              <button
                className="denial-add-btn"
                onClick={() => onAddPermission(toolName)}
                disabled={isAdding}
                title={`Add "${toolName}" to .claude/settings.local.json`}
              >
                {isAdding ? "Adding..." : "Add Permission"}
              </button>
            </div>
          );
        })}
      </div>
      <div className="denials-help">
        Click "Add Permission" to allow this tool in future requests.
        Changes are saved to <code>.claude/settings.local.json</code>
      </div>
    </div>
  );
}

function truncateInput(input: Record<string, unknown>): string {
  const str = JSON.stringify(input);
  if (str.length <= 50) return str;
  return str.substring(0, 47) + "...";
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
  height: calc(100vh - 120px);
  max-height: calc(100vh - 120px);
  padding: 12px 20px 20px 20px;
  background: transparent;
  color: var(--agent-text-primary);
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  position: relative;
  overflow: hidden;
}

.claude-agent-view.sidebar-open {
  padding-left: 300px;
}

/* Glass Card Container */
.claude-agent-card {
  display: flex;
  flex-direction: column;
  flex: 1;
  background: rgba(15, 23, 42, 0.6);
  backdrop-filter: blur(10.5px);
  -webkit-backdrop-filter: blur(10.5px);
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 18px;
  box-shadow: 0 20px 50px rgba(0, 0, 0, 0.25);
  overflow: hidden;
  min-height: 0;
}

/* Adjust padding when file sidebar is open. 
   If both are open, we might need more space or they overlap. 
   For now, let's assume they overlap or user toggles one. 
   But if we want them side-by-side, we'd need dynamic padding.
   Let's try to make the file sidebar sit ON TOP of the history sidebar if both are open,
   so we don't need double padding. 
   OR, we can make the file sidebar push content too.
*/
.claude-agent-view:has(.file-status-sidebar.open) {
  /* If we want it to push content, we need to know if history is also open.
     This is tricky with pure CSS unless we add a class to the parent.
     Let's rely on the JS state to add classes if we want complex layout.
     For now, let's just let it overlap or use the same padding-left if it's on top.
  */
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
  gap: 6px;
  padding: 6px 12px;
  font-size: 12px;
  background: rgba(30, 41, 59, 0.6);
  backdrop-filter: blur(8px);
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 8px;
  color: var(--agent-text-muted);
  cursor: pointer;
  transition: all 0.2s ease;
}

.continue-toggle:hover {
  background: rgba(30, 41, 59, 0.8);
  border-color: rgba(96, 165, 250, 0.35);
  color: var(--agent-text-secondary);
}

.continue-toggle.active {
  background: rgba(16, 185, 129, 0.2);
  border-color: rgba(16, 185, 129, 0.4);
  color: var(--agent-accent-green);
}

.toggle-icon {
  display: flex;
  align-items: center;
}

.toggle-label {
  font-weight: 500;
}

/* Selects with glassmorphism */
.model-select,
.permission-mode-select,
.agent-type-select {
  padding: 6px 12px;
  font-size: 12px;
  background: rgba(30, 41, 59, 0.6);
  backdrop-filter: blur(8px);
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 8px;
  color: var(--agent-text-secondary);
  cursor: pointer;
  transition: all 0.2s ease;
  outline: none;
  max-width: 200px;
}

.model-select:hover,
.permission-mode-select:hover,
.agent-type-select:hover {
  background: rgba(30, 41, 59, 0.8);
  border-color: rgba(96, 165, 250, 0.35);
  color: var(--agent-text-primary);
}

.model-select:focus,
.permission-mode-select:focus,
.agent-type-select:focus {
  border-color: rgba(59, 130, 246, 0.6);
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.15);
}

.model-select option,
.permission-mode-select option,
.agent-type-select option {
  background: var(--agent-bg-secondary);
  color: var(--agent-text-primary);
  padding: 8px;
}

/* Token usage display */
.token-usage {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  font-size: 12px;
  background: rgba(30, 41, 59, 0.6);
  backdrop-filter: blur(8px);
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 8px;
  color: var(--agent-text-secondary);
}

.token-icon {
  display: flex;
  align-items: center;
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
  padding: 14px 18px;
  background: rgba(30, 41, 59, 0.7);
  backdrop-filter: blur(10.5px);
  -webkit-backdrop-filter: blur(10.5px);
  border-bottom: 1px solid rgba(148, 163, 184, 0.15);
  border-radius: 18px 18px 0 0;
  flex-shrink: 0;
  gap: 12px;
}

.claude-header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.claude-title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: var(--agent-text-primary);
}

.claude-status {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  padding: 4px 10px;
  background: rgba(15, 23, 42, 0.5);
  border: 1px solid rgba(148, 163, 184, 0.15);
  border-radius: 8px;
}

.status-dot {
  width: 6px;
  height: 6px;
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
  padding: 4px 10px;
  background: rgba(15, 23, 42, 0.5);
  border: 1px solid rgba(148, 163, 184, 0.15);
  border-radius: 8px;
  color: var(--agent-text-secondary);
}

.claude-header-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.claude-cwd {
  font-size: 12px;
  padding: 6px 12px;
  background: rgba(15, 23, 42, 0.5);
  border: 1px solid rgba(148, 163, 184, 0.15);
  border-radius: 8px;
  color: var(--agent-text-secondary);
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  max-width: 350px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.claude-header-actions {
  display: flex;
  gap: 6px;
}

.header-btn {
  padding: 6px 14px;
  font-size: 12px;
  font-weight: 500;
  background: rgba(30, 41, 59, 0.6);
  backdrop-filter: blur(8px);
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 8px;
  color: var(--agent-text-secondary);
  cursor: pointer;
  transition: all 0.2s ease;
}

.header-btn:hover {
  background: rgba(30, 41, 59, 0.8);
  border-color: rgba(96, 165, 250, 0.35);
  color: var(--agent-text-primary);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
}

.header-btn.primary {
  background: rgba(59, 130, 246, 0.3);
  border-color: rgba(59, 130, 246, 0.5);
  color: #60a5fa;
}

.header-btn.primary:hover {
  background: rgba(59, 130, 246, 0.5);
  border-color: rgba(59, 130, 246, 0.7);
  box-shadow: 0 4px 20px rgba(59, 130, 246, 0.3);
}

.header-btn.active {
  background: rgba(59, 130, 246, 0.3);
  border-color: rgba(59, 130, 246, 0.5);
  color: #60a5fa;
}

/* Messages Container - Fixed height scroll */
.claude-messages-container {
  flex: 1;
  overflow-y: auto;
  padding: 8px 16px;
  min-height: 0; /* Important for flex scroll */
  scroll-behavior: smooth;
}

/* Custom scrollbar for messages */
.claude-messages-container::-webkit-scrollbar {
  width: 8px;
}

.claude-messages-container::-webkit-scrollbar-track {
  background: var(--agent-bg-primary);
}

.claude-messages-container::-webkit-scrollbar-thumb {
  background: var(--agent-border-secondary);
  border-radius: 4px;
}

.claude-messages-container::-webkit-scrollbar-thumb:hover {
  background: var(--agent-text-muted);
}

.claude-messages {
  display: flex;
  flex-direction: column;
  gap: 6px;
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

/* Messages - Chat Layout */
.message-row {
  display: flex;
  width: 100%;
}

.message-row.user {
  justify-content: flex-end;
}

.message-row.assistant {
  justify-content: flex-start;
}

/* User Messages - Right aligned with card */
.user-message-card {
  max-width: 75%;
  background: var(--agent-accent-blue);
  color: white;
  padding: 6px 10px;
  border-radius: 12px 12px 2px 12px;
  font-size: 15px;
  line-height: 1.4;
  box-shadow: 0 1px 4px rgba(59, 130, 246, 0.15);
}

.user-message-card .message-meta {
  color: rgba(255, 255, 255, 0.7);
  text-align: right;
  margin-top: 2px;
  font-size: 11px;
}

.user-message-content {
  white-space: pre-wrap;
  word-break: break-word;
}

/* Assistant Messages - Left aligned without card */
.assistant-message {
  max-width: 90%;
  padding: 4px 0;
  font-size: 15px;
  line-height: 1.5;
}

.assistant-message.assistant-text-inline {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 4px 0;
}

.assistant-text-inline .text-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  color: var(--agent-text-muted);
  margin-top: 2px;
}

.assistant-text-inline .text-content {
  font-size: 15px;
  color: var(--agent-text-primary);
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.5;
}

.assistant-message .message-meta {
  color: var(--agent-text-disabled);
  margin-top: 2px;
  font-size: 9px;
}

/* Legacy message class for compatibility */
.message {
  padding: 6px 8px;
  border-radius: 6px;
  background: var(--agent-bg-secondary);
  border: 1px solid var(--agent-border-primary);
  font-size: 14px;
}

.message-meta {
  font-size: 12px;
  color: var(--agent-text-disabled);
  margin-top: 2px;
  text-align: right;
}

.message-text-content {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: inherit;
  font-size: 12px;
  line-height: 1.4;
}

/* Tool Use - inside assistant-message */
.assistant-message.message-tool-use {
  background: var(--agent-bg-accent);
  border: 1px solid var(--agent-accent-blue);
  border-radius: 6px;
  padding: 6px 8px;
}

.tool-header {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  padding: 2px;
  border-radius: 3px;
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
  outline-offset: 1px;
}

.tool-header:focus:not(:focus-visible) {
  outline: none;
}

.tool-icon {
  font-size: 13px;
}

.tool-name {
  font-weight: 500;
  font-size: 15px;
  color: var(--agent-accent-blue);
  font-family: monospace;
}

.tool-expand {
  margin-left: auto;
  font-size: 9px;
  color: var(--agent-text-muted);
}

.tool-details {
  margin-top: 4px;
  padding: 4px 6px;
  background: var(--agent-bg-primary);
  border-radius: 3px;
}

.tool-input {
  margin: 0;
  font-size: 10px;
  font-family: 'JetBrains Mono', monospace;
  color: var(--agent-text-secondary);
  white-space: pre-wrap;
  word-break: break-word;
}

/* Tool Result - inside assistant-message */
.assistant-message.message-tool-result {
  background: var(--agent-bg-accent);
  border: 1px solid var(--agent-accent-green);
  border-radius: 6px;
  padding: 6px 8px;
}

.assistant-message.message-tool-result.inline {
  padding: 4px 8px;
}

.assistant-message.message-tool-result.error {
  border-color: var(--agent-accent-red);
}

.result-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 4px;
}

.assistant-message.message-tool-result.inline .result-header {
  margin-bottom: 0;
}

.result-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  color: var(--agent-accent-green);
}

.assistant-message.message-tool-result.error .result-icon {
  color: var(--agent-accent-red);
}

.result-label {
  font-size: 15px;
  font-weight: 500;
  color: var(--agent-text-muted);
}

.result-inline-content {
  font-size: 13px;
  font-family: 'JetBrains Mono', monospace;
  color: var(--agent-text-secondary);
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.result-toggle {
  margin-left: auto;
  padding: 1px 6px;
  font-size: 9px;
  background: transparent;
  border: 1px solid var(--agent-border-secondary);
  border-radius: 3px;
  color: var(--agent-text-muted);
  cursor: pointer;
}

.result-toggle:hover {
  background: var(--agent-bg-tertiary);
}

.result-content {
  margin: 0;
  font-size: 15px;
  font-family: 'JetBrains Mono', monospace;
  color: var(--agent-text-secondary);
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 300px;
  overflow-y: auto;
}

.result-content.truncated {
  max-height: 80px;
  overflow: hidden;
}

/* Error Message - inside assistant-message */
.assistant-message.message-error {
  background: var(--agent-error-bg);
  border: 1px solid var(--agent-accent-red);
  border-radius: 6px;
  padding: 6px 8px;
  display: flex;
  align-items: flex-start;
  gap: 6px;
}

.message-error .error-icon {
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: var(--agent-accent-red);
  color: white;
  font-size: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.message-error .error-content {
  color: var(--agent-error-text);
  font-size: 11px;
}

/* System Message - inside assistant-message */
.assistant-message.message-system {
  background: var(--agent-info-bg);
  border: 1px solid var(--agent-accent-blue);
  border-radius: 6px;
  padding: 6px 8px;
  display: flex;
  align-items: flex-start;
  gap: 6px;
  font-size: 10px;
  color: var(--agent-accent-blue);
}

.system-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  color: var(--agent-accent-blue);
}

/* Thinking */
.claude-thinking {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 8px;
  background: var(--agent-bg-tertiary);
  border-radius: 6px;
  color: var(--agent-text-secondary);
}

.thinking-content {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
}

.thinking-icon {
  display: flex;
  align-items: center;
  color: var(--agent-accent-purple);
  animation: bounce 1s infinite;
}

@keyframes bounce {
  0%, 100% { transform: translateY(0); }
  50% { transform: translateY(-4px); }
}

.thinking-text {
  font-size: 13px;
}

.active-tools {
  font-size: 12px;
  padding: 2px 8px;
  background: var(--agent-accent-blue);
  color: white;
  border-radius: 4px;
}

.pty-indicator {
  font-size: 11px;
  padding: 2px 8px;
  background: var(--agent-accent-purple);
  color: white;
  border-radius: 4px;
  font-weight: 500;
}

.claude-thinking.pty-mode {
  border-left: 3px solid var(--agent-accent-purple);
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

/* Execute Plan Banner */
.execute-plan-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 12px 16px;
  background: linear-gradient(135deg, var(--agent-info-bg), var(--agent-bg-tertiary));
  border: 1px solid var(--agent-accent-blue);
  border-radius: 8px;
  margin: 8px 0;
  animation: slideDown 0.3s ease-out;
}

.plan-banner-content {
  display: flex;
  align-items: center;
  gap: 10px;
}

.plan-banner-icon {
  display: flex;
  align-items: center;
  color: var(--agent-accent-blue);
}

.plan-banner-text {
  font-size: 13px;
  color: var(--agent-text-secondary);
}

.execute-plan-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 20px;
  font-size: 14px;
  font-weight: 600;
  background: var(--agent-accent-green);
  border: none;
  border-radius: 6px;
  color: white;
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;
}

.execute-plan-btn:hover {
  background: #059669;
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(16, 185, 129, 0.3);
}

.execute-plan-btn:active {
  transform: translateY(0);
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
  padding: 14px 18px;
  background: rgba(30, 41, 59, 0.5);
  backdrop-filter: blur(10.5px);
  -webkit-backdrop-filter: blur(10.5px);
  border-top: 1px solid rgba(148, 163, 184, 0.15);
  border-radius: 0 0 18px 18px;
  flex-shrink: 0;
}

.claude-input-form {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.claude-input-wrapper {
  position: relative;
  width: 100%;
}

.claude-input {
  width: 100%;
  padding: 12px 14px;
  background: rgba(15, 23, 42, 0.6);
  backdrop-filter: blur(8px);
  border: 1px solid rgba(148, 163, 184, 0.2);
  border-radius: 12px;
  color: var(--agent-text-primary);
  font-size: 14px;
  font-family: inherit;
  resize: none;
  outline: none;
  transition: all 0.2s ease;
}

.claude-input:focus {
  border-color: rgba(59, 130, 246, 0.5);
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
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
  gap: 6px;
}

.claude-send-btn {
  padding: 8px 20px;
  background: rgba(59, 130, 246, 0.4);
  backdrop-filter: blur(8px);
  border: 1px solid rgba(59, 130, 246, 0.5);
  border-radius: 10px;
  color: #60a5fa;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.claude-send-btn:hover:not(:disabled) {
  background: rgba(59, 130, 246, 0.6);
  border-color: rgba(59, 130, 246, 0.8);
  box-shadow: 0 4px 20px rgba(59, 130, 246, 0.3);
  color: white;
}

.claude-send-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.claude-cancel-btn {
  padding: 8px 20px;
  background: rgba(239, 68, 68, 0.3);
  backdrop-filter: blur(8px);
  border: 1px solid rgba(239, 68, 68, 0.5);
  border-radius: 10px;
  color: #f87171;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
}

.claude-cancel-btn:hover {
  background: rgba(239, 68, 68, 0.5);
  border-color: rgba(239, 68, 68, 0.8);
  box-shadow: 0 4px 20px rgba(239, 68, 68, 0.3);
  color: white;
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

  .user-message-card {
    max-width: 85%;
  }

  .assistant-message {
    max-width: 95%;
  }

  .message {
    padding: 8px;
  }

  .claude-input-container {
    padding: 6px 10px;
  }

  .tool-input,
  .result-content {
    font-size: 10px;
  }
}

/* Mobile (480px and below) */
@media (max-width: 480px) {
  .claude-agent-view {
    padding: 10px;
  }

  .claude-header {
    padding: 10px 12px;
    flex-wrap: wrap;
  }

  .claude-title {
    font-size: 14px;
  }

  .claude-header-left {
    gap: 6px;
    flex-wrap: wrap;
  }

  .claude-status .status-text {
    display: none;
  }

  .claude-model {
    display: none;
  }

  .continue-toggle .toggle-label {
    display: none;
  }

  .model-select,
  .permission-mode-select,
  .agent-type-select {
    padding: 4px 8px;
    font-size: 11px;
    max-width: 120px;
  }

  .token-usage .token-cost {
    display: none;
  }

  .header-btn {
    padding: 5px 10px;
    font-size: 11px;
  }

  .claude-header-actions {
    gap: 4px;
  }

  .claude-cwd {
    display: none;
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
    padding: 6px 8px;
  }

  .claude-input {
    padding: 6px 8px;
    font-size: 12px;
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

/* ============================================================================
   PERMISSION DENIALS BANNER
   ============================================================================ */

.permission-denials-banner {
  background: var(--agent-bg-tertiary);
  border: 1px solid var(--agent-accent-yellow);
  border-radius: 8px;
  padding: 12px;
  margin: 8px 0;
  animation: slideDown 0.3s ease-out;
}

.denials-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.denials-icon {
  display: flex;
  align-items: center;
  color: var(--agent-accent-yellow);
}

.denials-title {
  flex: 1;
  font-size: 14px;
  font-weight: 500;
  color: var(--agent-accent-yellow);
}

.denials-clear {
  background: transparent;
  border: none;
  color: var(--agent-text-muted);
  font-size: 18px;
  cursor: pointer;
  padding: 4px 8px;
  border-radius: 4px;
  transition: all 0.2s;
}

.denials-clear:hover {
  background: var(--agent-bg-accent);
  color: var(--agent-text-primary);
}

.denials-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.denial-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  background: var(--agent-bg-accent);
  border-radius: 6px;
  border: 1px solid var(--agent-border-secondary);
}

.denial-tool-icon {
  display: flex;
  align-items: center;
  color: var(--agent-text-secondary);
}

.denial-tool-name {
  font-family: 'JetBrains Mono', monospace;
  font-size: 13px;
  font-weight: 500;
  color: var(--agent-text-primary);
}

.denial-tool-hint {
  flex: 1;
  font-size: 11px;
  color: var(--agent-text-muted);
  font-family: 'JetBrains Mono', monospace;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.denial-add-btn {
  padding: 6px 12px;
  font-size: 12px;
  font-weight: 500;
  background: var(--agent-accent-green);
  border: none;
  border-radius: 4px;
  color: white;
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;
}

.denial-add-btn:hover:not(:disabled) {
  background: #059669;
}

.denial-add-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.denials-help {
  margin-top: 12px;
  padding-top: 10px;
  border-top: 1px solid var(--agent-border-secondary);
  font-size: 11px;
  color: var(--agent-text-muted);
}

.denials-help code {
  background: var(--agent-bg-primary);
  padding: 2px 6px;
  border-radius: 3px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px;
}

/* Mobile adjustments for permission banner */
@media (max-width: 480px) {
  .denial-item {
    flex-wrap: wrap;
  }

  .denial-tool-hint {
    flex-basis: 100%;
    order: 3;
    margin-top: 4px;
  }

  .denial-add-btn {
    margin-left: auto;
  }
}

/* ============================================================================
   AGENT TERMINAL MODE STYLES (Codex/Gemini)
   ============================================================================ */

/* Agent terminal wrapper - fills available space (Codex/Gemini) */
.agent-terminal-wrapper {
  flex: 1;
  min-height: 400px;
  display: flex;
  flex-direction: column;
  padding: 12px;
  overflow: hidden;
  height: 100%;
}

.agent-terminal-wrapper .agent-terminal-embed {
  flex: 1;
  min-height: 400px;
  height: 100%;
}

.agent-terminal-wrapper .terminal-embed {
  height: 100%;
}

.agent-terminal-wrapper .terminal-embed-content {
  flex: 1;
  min-height: 350px;
}

/* Mobile adjustments for terminal mode */
@media (max-width: 480px) {
  .agent-terminal-wrapper {
    padding: 8px;
    min-height: 300px;
  }
}
`;
