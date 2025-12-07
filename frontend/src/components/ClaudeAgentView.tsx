/**
 * Agent View
 *
 * Unified UI for all AI agents (Claude, Codex, Gemini) via Socket.IO terminal.
 * All agents run their respective CLI commands in a shared terminal interface.
 */

import { useState, useCallback } from "react";
import {
  useClaudeSessionStore,
  AGENT_TYPES,
  AGENT_TYPE_LABELS,
  AGENT_CLI_COMMANDS,
  type AgentType,
} from "../stores/claudeSessionStore";
import { TerminalSocketIO, terminalSocketIOStyles } from "./TerminalSocketIO";
import { AgentSidebar } from "./AgentSidebar";
import { useConnectionWarning } from "../hooks/useConnectionWarning";

// ============================================================================
// Main Component
// ============================================================================

export function ClaudeAgentView() {
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [terminalConnected, setTerminalConnected] = useState(false);
  // Key to force terminal remount when agent changes
  const [terminalKey, setTerminalKey] = useState(0);

  // Store state - simplified to just agent configuration
  const { agentType, setAgentType } = useClaudeSessionStore();

  // Warn user if they try to navigate away with active connection
  useConnectionWarning({ isConnected: terminalConnected });

  // Handle agent type change - remount terminal with new command
  const handleAgentTypeChange = useCallback((newType: AgentType) => {
    setAgentType(newType);
    // Force terminal remount to start with new agent command
    setTerminalKey((prev) => prev + 1);
  }, [setAgentType]);

  return (
    <div
      className={`claude-agent-view ${sidebarOpen ? "sidebar-open" : ""}`}
      role="main"
      aria-label="AI Agent Interface"
    >
      {/* Sidebar with git changes */}
      <AgentSidebar
        isOpen={sidebarOpen}
        onToggle={() => setSidebarOpen(!sidebarOpen)}
        onShowDiff={() => {}} // TODO: implement diff view
      />

      {/* Glass Card Container */}
      <div className="claude-agent-card">
        {/* Header */}
        <AgentHeader
          connected={terminalConnected}
          agentType={agentType}
          onAgentTypeChange={handleAgentTypeChange}
        />

        {/* Terminal - always used for all agents */}
        <div className="agent-terminal-wrapper">
          <style>{terminalSocketIOStyles}</style>
          <TerminalSocketIO
            key={terminalKey}
            autoConnect
            welcomeMessage={`${AGENT_TYPE_LABELS[agentType]} Terminal`}
            height="100%"
            className="agent-terminal-embed"
            onConnectionChange={setTerminalConnected}
            initialCommand={AGENT_CLI_COMMANDS[agentType]}
          />
        </div>
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
  agentType: AgentType;
  onAgentTypeChange: (type: AgentType) => void;
}

function AgentHeader({
  connected,
  agentType,
  onAgentTypeChange,
}: AgentHeaderProps) {
  const agentTitle = AGENT_TYPE_LABELS[agentType] || "AI Agent";

  return (
    <div className="claude-header">
      <div className="claude-header-left">
        <h2 className="claude-title">{agentTitle}</h2>
        <div className="claude-status">
          <span className={`status-dot ${connected ? "connected" : "disconnected"}`} />
          <span className="status-text">
            {connected ? "Connected" : "Disconnected"}
          </span>
        </div>
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
      </div>
    </div>
  );
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
  --agent-text-primary: #e2e8f0;
  --agent-text-secondary: #94a3b8;
  --agent-text-muted: #64748b;
  --agent-border-primary: #1e293b;
  --agent-border-secondary: #334155;
  --agent-accent-blue: #3b82f6;
  --agent-accent-green: #10b981;
  --agent-accent-red: #ef4444;
}

.claude-agent-view {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 220px);
  max-height: calc(100vh - 220px);
  padding: 0 20px 0 20px;
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

.status-dot.disconnected {
  background: var(--agent-accent-red);
}

/* Select with glassmorphism */
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

.agent-type-select:hover {
  background: rgba(30, 41, 59, 0.8);
  border-color: rgba(96, 165, 250, 0.35);
  color: var(--agent-text-primary);
}

.agent-type-select:focus {
  border-color: rgba(59, 130, 246, 0.6);
  box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.15);
}

.agent-type-select option {
  background: var(--agent-bg-secondary);
  color: var(--agent-text-primary);
  padding: 8px;
}

/* Agent terminal wrapper - fills available space */
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

/* ============================================================================
   RESPONSIVE DESIGN
   ============================================================================ */

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
}

@media (max-width: 480px) {
  .claude-agent-view {
    padding: 10px;
  }

  .claude-header {
    padding: 10px 12px;
  }

  .claude-title {
    font-size: 14px;
  }

  .claude-header-left {
    gap: 6px;
  }

  .claude-status .status-text {
    display: none;
  }

  .agent-type-select {
    padding: 4px 8px;
    font-size: 11px;
    max-width: 120px;
  }

  .agent-terminal-wrapper {
    padding: 8px;
    min-height: 300px;
  }
}
`;
