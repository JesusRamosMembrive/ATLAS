/**
 * Agent Status Bar Component
 *
 * Shows current agent phase, session duration, and key metrics
 */

import { useEffect, useState } from "react";
import { PHASE_COLORS, formatDuration, AgentMetrics } from "../../types/agent";

interface AgentStatusBarProps {
  phase: string;
  duration: number; // seconds
  errorCount: number;
  metrics: AgentMetrics;
}

export function AgentStatusBar({ phase, duration, errorCount, metrics }: AgentStatusBarProps) {
  const [currentTime, setCurrentTime] = useState(Date.now());

  // Update time every second for live duration
  useEffect(() => {
    const interval = setInterval(() => {
      setCurrentTime(Date.now());
    }, 1000);
    return () => clearInterval(interval);
  }, []);

  const phaseColor = PHASE_COLORS[phase] || "#gray";
  const phaseIcon = getPhaseIcon(phase);
  const phaseName = getPhaseName(phase);

  return (
    <div className="agent-status-bar">
      {/* Current Phase */}
      <div className="agent-status-bar__phase">
        <div
          className="agent-status-bar__phase-indicator"
          style={{ backgroundColor: phaseColor }}
        >
          <span className="agent-status-bar__phase-icon">{phaseIcon}</span>
        </div>
        <div className="agent-status-bar__phase-info">
          <div className="agent-status-bar__phase-name">{phaseName}</div>
          <div className="agent-status-bar__phase-duration">
            {formatDuration(duration)}
          </div>
        </div>
      </div>

      {/* Live Metrics */}
      <div className="agent-status-bar__metrics">
        {/* Commands */}
        <div className="agent-status-bar__metric">
          <span className="agent-status-bar__metric-icon">🚀</span>
          <span className="agent-status-bar__metric-value">{metrics.total_commands}</span>
          <span className="agent-status-bar__metric-label">cmds</span>
        </div>

        {/* Files */}
        <div className="agent-status-bar__metric">
          <span className="agent-status-bar__metric-icon">📄</span>
          <span className="agent-status-bar__metric-value">{metrics.total_files_changed}</span>
          <span className="agent-status-bar__metric-label">files</span>
        </div>

        {/* Tests */}
        {metrics.total_tests !== undefined && metrics.total_tests > 0 && (
          <div className="agent-status-bar__metric">
            <span className="agent-status-bar__metric-icon">🧪</span>
            <span className="agent-status-bar__metric-value">
              {metrics.tests_passed || 0}/{metrics.total_tests}
            </span>
            <span className="agent-status-bar__metric-label">tests</span>
          </div>
        )}

        {/* Errors */}
        {errorCount > 0 && (
          <div className="agent-status-bar__metric agent-status-bar__metric--error">
            <span className="agent-status-bar__metric-icon">⚠️</span>
            <span className="agent-status-bar__metric-value">{errorCount}</span>
            <span className="agent-status-bar__metric-label">errors</span>
          </div>
        )}
      </div>

      {/* Progress Indicator */}
      {phase !== "idle" && (
        <div className="agent-status-bar__progress">
          <div className="agent-status-bar__progress-spinner" />
        </div>
      )}
    </div>
  );
}

// Helper functions

function getPhaseIcon(phase: string): string {
  const icons: Record<string, string> = {
    idle: "⏸️",
    thinking: "🤔",
    planning: "📝",
    executing: "⚡",
    verifying: "✅",
    testing: "🧪",
    building: "🔨",
    installing: "📦",
  };
  return icons[phase] || "●";
}

function getPhaseName(phase: string): string {
  const names: Record<string, string> = {
    idle: "Idle",
    thinking: "Thinking...",
    planning: "Planning...",
    executing: "Executing",
    verifying: "Verifying",
    testing: "Running Tests",
    building: "Building",
    installing: "Installing",
  };
  return names[phase] || phase;
}