/**
 * Agent Sidebar
 *
 * Sidebar for Agent view with Files (git changes) and Project Stats tabs.
 * Fixed position on the left side with toggle visibility.
 */

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  getWorkingTreeChanges,
  getStatus,
  getLintersLatestReport,
  getStageStatus,
} from "../api/client";
import { queryKeys } from "../api/queryKeys";
import type { WorkingTreeChange } from "../api/types";
import { getChangeLabel, getChangeVariant } from "../utils/changeStatus";

// =============================================================================
// Types
// =============================================================================

type TabType = "files" | "stats";

interface AgentSidebarProps {
  isOpen: boolean;
  onToggle: () => void;
  onShowDiff: (path: string) => void;
}

// =============================================================================
// Main Component
// =============================================================================

export function AgentSidebar({
  isOpen,
  onToggle,
  onShowDiff,
}: AgentSidebarProps) {
  const [activeTab, setActiveTab] = useState<TabType>("files");

  return (
    <>
      {/* Toggle button - always visible */}
      <button
        className="agent-sidebar-toggle"
        onClick={onToggle}
        title={isOpen ? "Hide sidebar" : "Show sidebar"}
        aria-expanded={isOpen}
        aria-label={isOpen ? "Hide sidebar" : "Show sidebar"}
      >
        <span aria-hidden="true">{isOpen ? "◀" : "▶"}</span>
      </button>

      {/* Sidebar */}
      <aside
        className={`agent-sidebar ${isOpen ? "open" : ""}`}
        aria-label="Agent sidebar"
        aria-hidden={!isOpen}
      >
        {/* Tab buttons */}
        <div className="sidebar-tabs" role="tablist">
          <button
            role="tab"
            aria-selected={activeTab === "files"}
            className={`tab-btn ${activeTab === "files" ? "active" : ""}`}
            onClick={() => setActiveTab("files")}
          >
            Files
          </button>
          <button
            role="tab"
            aria-selected={activeTab === "stats"}
            className={`tab-btn ${activeTab === "stats" ? "active" : ""}`}
            onClick={() => setActiveTab("stats")}
          >
            Stats
          </button>
        </div>

        {/* Tab content */}
        <div className="sidebar-content">
          {activeTab === "files" && <FilesTab onShowDiff={onShowDiff} />}
          {activeTab === "stats" && <StatsTab />}
        </div>
      </aside>

      <style>{sidebarStyles}</style>
    </>
  );
}

// =============================================================================
// Files Tab
// =============================================================================

interface FilesTabProps {
  onShowDiff: (path: string) => void;
}

function FilesTab({ onShowDiff }: FilesTabProps) {
  const { data, isPending, isError, error, refetch } = useQuery({
    queryKey: queryKeys.changes,
    queryFn: getWorkingTreeChanges,
    refetchInterval: 15000,
  });

  const changes = data?.changes ?? [];

  return (
    <div className="tab-panel">
      <div className="tab-header">
        <span className="tab-title">Modified Files</span>
        <button className="action-btn" onClick={() => refetch()} title="Refresh">
          ↻
        </button>
      </div>

      <div className="tab-list">
        {isPending && <p className="loading">Checking git status…</p>}

        {isError && (
          <div className="error-msg">
            {(error as Error)?.message ?? "Could not load changes"}
          </div>
        )}

        {!isPending && !isError && changes.length === 0 && (
          <div className="empty-state">
            <p>No pending changes</p>
            <p className="hint">Modified files will appear here</p>
          </div>
        )}

        {changes.length > 0 && (
          <ul>
            {changes.map((change) => (
              <FileItem
                key={change.path}
                change={change}
                onShowDiff={onShowDiff}
              />
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function FileItem({
  change,
  onShowDiff,
}: {
  change: WorkingTreeChange;
  onShowDiff: (path: string) => void;
}) {
  const label = getChangeLabel(change.status);
  const variant = getChangeVariant(change.status);

  return (
    <li>
      <button
        className="list-item file-item"
        onClick={() => onShowDiff(change.path)}
        title={change.path}
      >
        <div className="item-header">
          <span className={`status-dot status-${variant}`} />
          <span className="file-path">{change.path}</span>
        </div>
        <div className="item-meta">
          <span className={`status-label text-${variant}`}>{label}</span>
        </div>
      </button>
    </li>
  );
}

// =============================================================================
// Stats Tab - Project Overview
// =============================================================================

const LINTER_STATUS_LABEL: Record<string, string> = {
  pass: "Passing",
  warn: "Warnings",
  fail: "Failing",
  skipped: "Skipped",
  error: "Error",
  default: "No data",
};

const LINTER_STATUS_VARIANT: Record<string, string> = {
  pass: "success",
  warn: "warning",
  fail: "danger",
  error: "danger",
  skipped: "neutral",
  default: "neutral",
};

function formatNumber(value: number): string {
  if (value >= 1000000) return `${(value / 1000000).toFixed(1)}M`;
  if (value >= 1000) return `${(value / 1000).toFixed(1)}k`;
  return value.toLocaleString("en-US");
}

function StatsTab() {
  // Fetch project status
  const statusQuery = useQuery({
    queryKey: queryKeys.status,
    queryFn: getStatus,
    refetchInterval: 30000,
  });

  // Fetch linters report
  const lintersQuery = useQuery({
    queryKey: queryKeys.lintersLatest,
    queryFn: getLintersLatestReport,
    refetchInterval: 60000,
  });

  // Fetch stage detection
  const stageQuery = useQuery({
    queryKey: queryKeys.stageStatus,
    queryFn: getStageStatus,
    refetchInterval: 60000,
  });

  // Fetch pending changes count
  const changesQuery = useQuery({
    queryKey: queryKeys.changes,
    queryFn: getWorkingTreeChanges,
    refetchInterval: 30000,
  });

  // Extract data
  const status = statusQuery.data;
  const filesIndexed = status?.files_indexed ?? 0;
  const symbolsIndexed = status?.symbols_indexed ?? 0;
  const pendingEvents = status?.pending_events ?? 0;

  const lintersReport = lintersQuery.data;
  const lintersStatusKey = lintersReport?.report?.summary?.overall_status ?? "default";
  const lintersLabel = LINTER_STATUS_LABEL[lintersStatusKey] ?? "No data";
  const lintersVariant = LINTER_STATUS_VARIANT[lintersStatusKey] ?? "neutral";
  const lintersIssues = lintersReport?.report?.summary?.issues_total ?? 0;

  const detection = stageQuery.data?.detection;
  const stageNumber = detection?.recommended_stage;
  const stageConfidence = detection?.confidence;
  const linesOfCode = detection?.metrics?.lines_of_code as number | undefined;

  const pendingChanges = changesQuery.data?.changes?.length ?? 0;

  const isLoading = statusQuery.isPending || lintersQuery.isPending;

  return (
    <div className="tab-panel">
      <div className="tab-header">
        <span className="tab-title">Project Overview</span>
        <button
          className="action-btn"
          onClick={() => {
            statusQuery.refetch();
            lintersQuery.refetch();
            stageQuery.refetch();
          }}
          title="Refresh"
        >
          ↻
        </button>
      </div>

      <div className="stats-content">
        {isLoading ? (
          <p className="loading">Loading project stats…</p>
        ) : (
          <>
            {/* Code Metrics */}
            <div className="stat-card">
              <div className="stat-card-title">Code Index</div>
              <div className="stat-grid">
                <div className="stat-item">
                  <span className="stat-value">{formatNumber(filesIndexed)}</span>
                  <span className="stat-label">Files</span>
                </div>
                <div className="stat-item">
                  <span className="stat-value">{formatNumber(symbolsIndexed)}</span>
                  <span className="stat-label">Symbols</span>
                </div>
                {linesOfCode !== undefined && (
                  <div className="stat-item">
                    <span className="stat-value">{formatNumber(linesOfCode)}</span>
                    <span className="stat-label">LOC</span>
                  </div>
                )}
              </div>
            </div>

            {/* Linters Status */}
            <div className="stat-card">
              <div className="stat-card-title">Linters</div>
              <div className="stat-row">
                <span className={`status-badge status-${lintersVariant}`}>
                  {lintersLabel}
                </span>
                {lintersIssues > 0 && (
                  <span className="stat-detail">{lintersIssues} issues</span>
                )}
              </div>
            </div>

            {/* Changes & Events */}
            <div className="stat-card">
              <div className="stat-card-title">Activity</div>
              <div className="stat-grid">
                <div className="stat-item">
                  <span className={`stat-value ${pendingChanges > 0 ? "text-modified" : ""}`}>
                    {pendingChanges}
                  </span>
                  <span className="stat-label">Changes</span>
                </div>
                <div className="stat-item">
                  <span className={`stat-value ${pendingEvents > 0 ? "text-warning" : ""}`}>
                    {pendingEvents}
                  </span>
                  <span className="stat-label">Pending</span>
                </div>
              </div>
            </div>

            {/* Stage Detection */}
            {detection?.available && stageNumber && (
              <div className="stat-card">
                <div className="stat-card-title">Stage Detection</div>
                <div className="stat-row">
                  <span className="stage-badge">Stage {stageNumber}</span>
                  {stageConfidence && (
                    <span className="stat-detail">{stageConfidence} confidence</span>
                  )}
                </div>
                {detection.reasons && detection.reasons.length > 0 && (
                  <p className="stage-reason">{detection.reasons[0]}</p>
                )}
              </div>
            )}

            {/* CLI Tip */}
            <div className="stat-info">
              <p className="hint">
                💡 Use <code>/cost</code> in terminal to see token usage
              </p>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

// =============================================================================
// Styles
// =============================================================================

const sidebarStyles = `
/* Toggle button */
.agent-sidebar-toggle {
  position: fixed;
  left: 0;
  top: calc(50% + 25px);
  transform: translateY(-50%);
  width: 20px;
  height: 60px;
  background: var(--agent-bg-tertiary);
  border: 1px solid var(--agent-border-secondary);
  border-left: none;
  border-radius: 0 8px 8px 0;
  color: var(--agent-text-secondary);
  font-size: 12px;
  cursor: pointer;
  z-index: 200;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
}

.agent-sidebar-toggle:hover {
  background: var(--agent-border-secondary);
  color: var(--agent-text-primary);
  width: 24px;
}

/* Sidebar */
.agent-sidebar {
  position: fixed;
  left: 0;
  top: 180px;
  bottom: 36px;
  width: 280px;
  background: var(--agent-bg-secondary);
  border-right: 1px solid var(--agent-border-primary);
  border-radius: 0 0 12px 0;
  transform: translateX(-100%);
  transition: transform 0.25s ease;
  z-index: 150;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.agent-sidebar.open {
  transform: translateX(0);
}

/* Tabs */
.sidebar-tabs {
  display: flex;
  border-bottom: 1px solid var(--agent-border-primary);
  background: var(--agent-bg-tertiary);
}

.tab-btn {
  flex: 1;
  padding: 10px 8px;
  background: transparent;
  border: none;
  border-bottom: 2px solid transparent;
  color: var(--agent-text-muted);
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.tab-btn:hover {
  color: var(--agent-text-secondary);
  background: rgba(255, 255, 255, 0.03);
}

.tab-btn.active {
  color: var(--agent-accent-blue);
  border-bottom-color: var(--agent-accent-blue);
}

/* Content */
.sidebar-content {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.tab-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.tab-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  padding: 10px 12px;
  border-bottom: 1px solid var(--agent-border-primary);
}

.tab-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--agent-text-primary);
}

.action-btn {
  padding: 4px 10px;
  font-size: 11px;
  background: var(--agent-bg-tertiary);
  border: 1px solid var(--agent-border-secondary);
  border-radius: 4px;
  color: var(--agent-text-secondary);
  cursor: pointer;
  transition: all 0.2s;
}

.action-btn:hover {
  background: var(--agent-border-secondary);
  color: var(--agent-text-primary);
}

/* List */
.tab-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.tab-list ul {
  list-style: none;
  margin: 0;
  padding: 0;
}

.tab-list li {
  margin-bottom: 4px;
}

.list-item {
  display: block;
  width: 100%;
  padding: 8px 10px;
  background: transparent;
  border: 1px solid transparent;
  border-radius: 6px;
  cursor: pointer;
  text-align: left;
  color: inherit;
  font: inherit;
  transition: background 0.2s;
}

.list-item:hover {
  background: var(--agent-bg-tertiary);
}

.item-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.item-meta {
  display: flex;
  gap: 8px;
  margin-top: 4px;
  font-size: 10px;
  color: var(--agent-text-disabled);
}

/* File item specifics */
.file-item .file-path {
  font-family: 'JetBrains Mono', monospace;
  font-size: 11px;
  color: var(--agent-text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  direction: rtl;
  text-align: left;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.status-added { background: var(--agent-accent-green); }
.status-deleted { background: var(--agent-accent-red); }
.status-modified { background: var(--agent-accent-blue); }
.status-renamed { background: var(--agent-accent-purple); }
.status-conflict { background: var(--agent-accent-yellow); }

.status-label {
  font-weight: 500;
}

.text-added { color: var(--agent-accent-green); }
.text-deleted { color: var(--agent-accent-red); }
.text-modified { color: var(--agent-accent-blue); }
.text-renamed { color: var(--agent-accent-purple); }
.text-conflict { color: var(--agent-accent-yellow); }

/* Stats */
.stats-content {
  flex: 1;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  overflow-y: auto;
  min-height: 0;
}

.stat-card {
  background: var(--agent-bg-tertiary);
  border: 1px solid var(--agent-border-primary);
  border-radius: 8px;
  padding: 10px 12px;
}

.stat-card-title {
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--agent-text-muted);
  margin-bottom: 8px;
}

.stat-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(60px, 1fr));
  gap: 8px;
}

.stat-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
}

.stat-value {
  font-size: 18px;
  font-weight: 600;
  color: var(--agent-text-primary);
  line-height: 1.2;
}

.stat-label {
  font-size: 10px;
  color: var(--agent-text-muted);
  margin-top: 2px;
}

.stat-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.stat-detail {
  font-size: 11px;
  color: var(--agent-text-secondary);
}

.status-badge {
  display: inline-block;
  padding: 3px 8px;
  font-size: 11px;
  font-weight: 500;
  border-radius: 4px;
}

.status-success {
  background: rgba(16, 185, 129, 0.15);
  color: var(--agent-accent-green);
}

.status-warning {
  background: rgba(245, 158, 11, 0.15);
  color: #f59e0b;
}

.status-danger {
  background: rgba(239, 68, 68, 0.15);
  color: var(--agent-accent-red);
}

.status-neutral {
  background: rgba(148, 163, 184, 0.15);
  color: var(--agent-text-muted);
}

.stage-badge {
  display: inline-block;
  padding: 3px 8px;
  font-size: 11px;
  font-weight: 600;
  border-radius: 4px;
  background: rgba(59, 130, 246, 0.15);
  color: var(--agent-accent-blue);
}

.stage-reason {
  margin: 6px 0 0;
  font-size: 11px;
  color: var(--agent-text-secondary);
  line-height: 1.4;
}

.text-warning {
  color: #f59e0b;
}

.stat-info {
  padding: 10px 12px;
  background: var(--agent-bg-tertiary);
  border-radius: 8px;
  font-size: 12px;
  color: var(--agent-text-secondary);
}

.stat-info p {
  margin: 0;
}

.stat-info .hint {
  font-size: 11px;
  color: var(--agent-text-muted);
  margin: 0;
}

.stat-info code {
  background: rgba(0, 0, 0, 0.3);
  padding: 1px 4px;
  border-radius: 3px;
  font-family: 'JetBrains Mono', monospace;
  font-size: 10px;
}

/* Empty state */
.empty-state {
  padding: 24px 16px;
  text-align: center;
  color: var(--agent-text-muted);
}

.empty-state p {
  margin: 0 0 4px;
  font-size: 13px;
}

.empty-state .hint {
  font-size: 11px;
  color: var(--agent-text-disabled);
}

.loading {
  padding: 16px;
  text-align: center;
  color: var(--agent-text-muted);
  font-size: 12px;
}

.error-msg {
  margin: 8px;
  padding: 10px;
  background: var(--agent-error-bg);
  border: 1px solid var(--agent-accent-red);
  border-radius: 6px;
  color: var(--agent-error-text);
  font-size: 12px;
}

/* Scrollbar */
.tab-list::-webkit-scrollbar {
  width: 6px;
}

.tab-list::-webkit-scrollbar-track {
  background: transparent;
}

.tab-list::-webkit-scrollbar-thumb {
  background: var(--agent-border-secondary);
  border-radius: 3px;
}

.tab-list::-webkit-scrollbar-thumb:hover {
  background: var(--agent-text-disabled);
}

/* Responsive */
@media (max-width: 768px) {
  .agent-sidebar {
    width: 100%;
    max-width: 320px;
  }
}

@media (max-width: 480px) {
  .agent-sidebar {
    max-width: 100%;
  }

  .agent-sidebar.open {
    box-shadow: 0 0 30px var(--agent-shadow);
  }
}
`;
