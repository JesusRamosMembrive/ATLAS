/**
 * Agent Terminal Overlay
 *
 * Main component for agent visualization overlay
 * Shows timeline, status, and command widgets
 */

import { useEffect, useState } from "react";
import { useAgentStore } from "../../stores/agentStore";
import { AgentTimeline } from "./AgentTimeline";
import { AgentStatusBar } from "./AgentStatusBar";
import { CommandWidget } from "./CommandWidget";
import { AgentEventType, formatDuration } from "../../types/agent";
import "./AgentOverlay.css";

interface AgentOverlayProps {
  visible: boolean;
  position?: "left" | "right" | "bottom";
  onClose?: () => void;
}

export function AgentOverlay({ visible, position = "right", onClose }: AgentOverlayProps) {
  const {
    enabled,
    sessionState,
    timeline,
    getCurrentCommand,
    getCurrentTestRun,
    getRecentFiles,
    getErrorCount,
    getTestSummary,
    getSessionDuration,
  } = useAgentStore();

  const [collapsed, setCollapsed] = useState(false);
  const [selectedEvent, setSelectedEvent] = useState<string | null>(null);

  // Auto-scroll timeline to bottom when new events arrive
  const [autoScroll, setAutoScroll] = useState(true);

  if (!visible || !enabled || !sessionState) {
    return null;
  }

  const currentCommand = getCurrentCommand();
  const currentTest = getCurrentTestRun();
  const recentFiles = getRecentFiles(5);
  const errorCount = getErrorCount();
  const testSummary = getTestSummary();
  const sessionDuration = getSessionDuration();

  return (
    <div className={`agent-overlay agent-overlay--${position} ${collapsed ? "agent-overlay--collapsed" : ""}`}>
      {/* Header */}
      <div className="agent-overlay__header">
        <div className="agent-overlay__title">
          <span className="agent-overlay__icon">🤖</span>
          Agent Monitor
        </div>
        <div className="agent-overlay__controls">
          <button
            className="agent-overlay__btn"
            onClick={() => setAutoScroll(!autoScroll)}
            title={autoScroll ? "Disable auto-scroll" : "Enable auto-scroll"}
          >
            {autoScroll ? "📌" : "📍"}
          </button>
          <button
            className="agent-overlay__btn"
            onClick={() => setCollapsed(!collapsed)}
            title={collapsed ? "Expand" : "Collapse"}
          >
            {collapsed ? "◀" : "▶"}
          </button>
          {onClose && (
            <button
              className="agent-overlay__btn agent-overlay__btn--close"
              onClick={onClose}
              title="Close overlay"
            >
              ✕
            </button>
          )}
        </div>
      </div>

      {!collapsed && (
        <>
          {/* Status Bar */}
          <AgentStatusBar
            phase={sessionState.current_phase}
            duration={sessionDuration}
            errorCount={errorCount}
            metrics={sessionState.metrics}
          />

          {/* Current Activity */}
          {(currentCommand || currentTest) && (
            <div className="agent-overlay__section">
              <div className="agent-overlay__section-title">Current Activity</div>
              {currentCommand && (
                <CommandWidget
                  command={currentCommand}
                  type="command"
                  expanded={false}
                />
              )}
              {currentTest && (
                <CommandWidget
                  testRun={currentTest}
                  type="test"
                  expanded={false}
                />
              )}
            </div>
          )}

          {/* Quick Stats */}
          <div className="agent-overlay__stats">
            <div className="agent-stat">
              <span className="agent-stat__label">Commands</span>
              <span className="agent-stat__value">{sessionState.commands.length}</span>
            </div>
            <div className="agent-stat">
              <span className="agent-stat__label">Files</span>
              <span className="agent-stat__value">{sessionState.file_changes.length}</span>
            </div>
            <div className="agent-stat">
              <span className="agent-stat__label">Tests</span>
              <span className="agent-stat__value">
                {testSummary.passed}/{testSummary.total}
              </span>
            </div>
            <div className="agent-stat">
              <span className="agent-stat__label">Errors</span>
              <span className="agent-stat__value agent-stat__value--error">
                {errorCount > 0 ? errorCount : "0"}
              </span>
            </div>
          </div>

          {/* Timeline */}
          <div className="agent-overlay__timeline">
            <div className="agent-overlay__section-title">Timeline</div>
            <AgentTimeline
              events={timeline}
              autoScroll={autoScroll}
              onEventClick={setSelectedEvent}
              selectedEventId={selectedEvent}
            />
          </div>

          {/* Recent Files */}
          {recentFiles.length > 0 && (
            <div className="agent-overlay__section">
              <div className="agent-overlay__section-title">Recent Files</div>
              <div className="agent-overlay__files">
                {recentFiles.map((file: any, idx: number) => (
                  <div key={idx} className="agent-file">
                    <span className="agent-file__icon">
                      {file.operation === "write" ? "✏️" :
                       file.operation === "read" ? "📖" :
                       file.operation === "delete" ? "🗑️" : "📄"}
                    </span>
                    <span className="agent-file__path" title={file.file_path}>
                      {file.file_path.split("/").pop() || file.file_path}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}