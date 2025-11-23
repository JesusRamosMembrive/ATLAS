import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { getAuditEvents, listAuditRuns } from "../api/client";
import { queryKeys } from "../api/queryKeys";
import type { AuditRun } from "../api/types";
import { useAuditEventStream } from "../hooks/useAuditEventStream";
import { TerminalView } from "./TerminalView";
import { TimelineView } from "./TimelineView";
import { DiffList } from "./DiffViewer";

const DEFAULT_EVENT_LIMIT = 500;

function formatRelative(dateString?: string | null): string {
  if (!dateString) return "just now";
  const date = new Date(dateString);
  const diff = Date.now() - date.getTime();
  const minutes = Math.max(0, Math.floor(diff / 60000));
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function statusBadge(status?: string | null): string {
  if (!status) return "neutral";
  const normalized = status.toLowerCase();
  if (normalized.startsWith("error") || normalized === "fail") return "danger";
  if (normalized === "closed" || normalized === "done") return "muted";
  if (normalized === "pending") return "warning";
  return "success";
}

function RunSelector({
  runs,
  selectedRunId,
  onSelect,
}: {
  runs: AuditRun[];
  selectedRunId: number | null;
  onSelect: (id: number) => void;
}): JSX.Element {
  return (
    <div className="audit-runs-selector">
      <h4>Recent Sessions</h4>
      <div className="audit-runs-list">
        {runs.map((run) => {
          const isSelected = run.id === selectedRunId;
          const badgeClass = `audit-badge status-${statusBadge(run.status)}`;

          return (
            <button
              key={run.id}
              type="button"
              className={`audit-run-card compact${isSelected ? " selected" : ""}`}
              onClick={() => onSelect(run.id)}
            >
              <div className="audit-run-header">
                <span className={badgeClass}>{run.status}</span>
                <span className="audit-run-time">{formatRelative(run.created_at)}</span>
              </div>
              <div className="audit-run-title">{run.name || `Run ${run.id}`}</div>
              <div className="audit-run-meta-inline">
                <span>{run.event_count} events</span>
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}

/**
 * Agent Monitoring Dashboard
 *
 * Full-featured monitoring interface with 3-column layout:
 * - Left: Session selector
 * - Center: Terminal emulator showing command output
 * - Right: Timeline visualization + Event stream
 *
 * Features:
 * - Real-time SSE event streaming
 * - Live terminal updates
 * - Phase timeline visualization
 * - Connection status indicator
 */
export function AgentMonitoringDashboard(): JSX.Element {
  const [selectedRunId, setSelectedRunId] = useState<number | null>(null);

  // Fetch available runs
  const runsQuery = useQuery({
    queryKey: queryKeys.auditRuns(20),
    queryFn: () => listAuditRuns(20),
    refetchInterval: 5000,
  });

  // Auto-select first run if none selected
  useEffect(() => {
    if (selectedRunId || !runsQuery.data?.runs?.length) {
      return;
    }
    setSelectedRunId(runsQuery.data.runs[0]?.id ?? null);
  }, [runsQuery.data?.runs, selectedRunId]);

  const selectedRun = useMemo(
    () => runsQuery.data?.runs.find((run) => run.id === selectedRunId),
    [runsQuery.data?.runs, selectedRunId]
  );

  // Fetch events for selected run
  const eventsQuery = useQuery({
    queryKey: selectedRunId
      ? queryKeys.auditEvents(selectedRunId, DEFAULT_EVENT_LIMIT)
      : ["audit", "events", "none"],
    queryFn: () =>
      selectedRunId
        ? getAuditEvents(selectedRunId, { limit: DEFAULT_EVENT_LIMIT })
        : Promise.resolve({ events: [] }),
    enabled: Boolean(selectedRunId),
  });

  // Real-time event streaming via SSE
  const { isConnected: sseConnected, error: sseError } = useAuditEventStream(
    selectedRunId,
    Boolean(selectedRunId)
  );

  const events = eventsQuery.data?.events ?? [];

  return (
    <div className="audit-page">
      {/* Hero Section */}
      <section className="audit-hero">
        <div>
          <p className="audit-eyebrow">Agent Monitoring</p>
          <h1>Live Dashboard</h1>
          <p className="audit-subtitle">
            Real-time monitoring of agent activities with terminal output,
            phase timeline, and event stream.
          </p>
        </div>
        <div className="audit-hero-meta">
          {sseConnected ? (
            <span className="audit-badge status-success">🟢 Live</span>
          ) : sseError ? (
            <span className="audit-badge status-warning" title={sseError}>
              🟡 Reconnecting
            </span>
          ) : null}
          {selectedRun && (
            <span className="audit-badge subtle">
              Session: {selectedRun.name || `#${selectedRun.id}`}
            </span>
          )}
        </div>
      </section>

      {/* Main Dashboard Grid */}
      <div className="monitoring-dashboard-grid">
        {/* Left Column: Run Selector */}
        <aside className="monitoring-sidebar">
          <RunSelector
            runs={runsQuery.data?.runs ?? []}
            selectedRunId={selectedRunId}
            onSelect={setSelectedRunId}
          />
        </aside>

        {/* Center Column: Terminal */}
        <section className="monitoring-terminal">
          <div className="monitoring-panel">
            <div className="monitoring-panel-header">
              <h3>Terminal Output</h3>
              <span className="monitoring-event-count">
                {events.length} events
              </span>
            </div>
            <div className="monitoring-panel-body">
              {selectedRunId ? (
                <TerminalView events={events} maxHeight={700} />
              ) : (
                <div className="monitoring-empty-state">
                  <p>Select a session to view terminal output</p>
                </div>
              )}
            </div>
          </div>
        </section>

        {/* Right Column: Timeline + Metrics */}
        <aside className="monitoring-sidebar-right">
          {selectedRunId && (
            <>
              <div className="monitoring-panel">
                <div className="monitoring-panel-header">
                  <h3>Phase Timeline</h3>
                </div>
                <div className="monitoring-panel-body">
                  <TimelineView events={events} />
                </div>
              </div>

              <div className="monitoring-panel">
                <div className="monitoring-panel-header">
                  <h3>File Changes</h3>
                </div>
                <div className="monitoring-panel-body">
                  <DiffList events={events} />
                </div>
              </div>

              <div className="monitoring-panel">
                <div className="monitoring-panel-header">
                  <h3>Session Info</h3>
                </div>
                <div className="monitoring-panel-body">
                  {selectedRun && (
                    <div className="monitoring-session-info">
                      <div className="monitoring-info-row">
                        <span className="monitoring-info-label">Name:</span>
                        <span className="monitoring-info-value">
                          {selectedRun.name || `Run #${selectedRun.id}`}
                        </span>
                      </div>
                      <div className="monitoring-info-row">
                        <span className="monitoring-info-label">Status:</span>
                        <span className={`audit-badge status-${statusBadge(selectedRun.status)}`}>
                          {selectedRun.status}
                        </span>
                      </div>
                      <div className="monitoring-info-row">
                        <span className="monitoring-info-label">Events:</span>
                        <span className="monitoring-info-value">
                          {selectedRun.event_count}
                        </span>
                      </div>
                      <div className="monitoring-info-row">
                        <span className="monitoring-info-label">Started:</span>
                        <span className="monitoring-info-value">
                          {formatRelative(selectedRun.created_at)}
                        </span>
                      </div>
                      {selectedRun.closed_at && (
                        <div className="monitoring-info-row">
                          <span className="monitoring-info-label">Closed:</span>
                          <span className="monitoring-info-value">
                            {formatRelative(selectedRun.closed_at)}
                          </span>
                        </div>
                      )}
                      {selectedRun.root_path && (
                        <div className="monitoring-info-row">
                          <span className="monitoring-info-label">Path:</span>
                          <code className="monitoring-info-code">
                            {selectedRun.root_path}
                          </code>
                        </div>
                      )}
                      {selectedRun.notes && (
                        <div className="monitoring-info-row vertical">
                          <span className="monitoring-info-label">Notes:</span>
                          <p className="monitoring-info-notes">
                            {selectedRun.notes}
                          </p>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              </div>
            </>
          )}
        </aside>
      </div>
    </div>
  );
}
