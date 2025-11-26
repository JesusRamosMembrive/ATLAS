/**
 * Agent Sidebar
 *
 * Unified tabbed sidebar for Claude Agent with History, Files, and Statistics tabs.
 * Fixed position on the left side with toggle visibility.
 */

import { useState, useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  useSessionHistoryStore,
  SessionSnapshot,
} from "../stores/sessionHistoryStore";
import { getWorkingTreeChanges } from "../api/client";
import { queryKeys } from "../api/queryKeys";
import { useSelectionStore } from "../state/useSelectionStore";
import type { WorkingTreeChange } from "../api/types";
import { getChangeLabel, getChangeVariant } from "../utils/changeStatus";

// =============================================================================
// Types
// =============================================================================

type TabType = "history" | "files" | "stats";

interface AgentSidebarProps {
  isOpen: boolean;
  onToggle: () => void;
  onLoadSession: (messages: SessionSnapshot["messages"]) => void;
  onNewSession: () => void;
  onShowDiff: (path: string) => void;
  totalInputTokens: number;
  totalOutputTokens: number;
}

// =============================================================================
// Main Component
// =============================================================================

export function AgentSidebar({
  isOpen,
  onToggle,
  onLoadSession,
  onNewSession,
  onShowDiff,
  totalInputTokens,
  totalOutputTokens,
}: AgentSidebarProps) {
  const [activeTab, setActiveTab] = useState<TabType>("history");

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
            aria-selected={activeTab === "history"}
            className={`tab-btn ${activeTab === "history" ? "active" : ""}`}
            onClick={() => setActiveTab("history")}
          >
            History
          </button>
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
          {activeTab === "history" && (
            <HistoryTab
              onLoadSession={onLoadSession}
              onNewSession={onNewSession}
            />
          )}
          {activeTab === "files" && (
            <FilesTab onShowDiff={onShowDiff} />
          )}
          {activeTab === "stats" && (
            <StatsTab
              totalInputTokens={totalInputTokens}
              totalOutputTokens={totalOutputTokens}
            />
          )}
        </div>
      </aside>

      <style>{sidebarStyles}</style>
    </>
  );
}

// =============================================================================
// History Tab
// =============================================================================

interface HistoryTabProps {
  onLoadSession: (messages: SessionSnapshot["messages"]) => void;
  onNewSession: () => void;
}

function HistoryTab({ onLoadSession, onNewSession }: HistoryTabProps) {
  const {
    sessions,
    currentSessionId,
    loadSession,
    deleteSession,
    clearAllSessions,
    setCurrentSessionId,
  } = useSessionHistoryStore();

  const handleLoadSession = useCallback(
    (id: string) => {
      const session = loadSession(id);
      if (session) {
        setCurrentSessionId(id);
        onLoadSession(session.messages);
      }
    },
    [loadSession, setCurrentSessionId, onLoadSession]
  );

  const handleNewSession = useCallback(() => {
    setCurrentSessionId(null);
    onNewSession();
  }, [setCurrentSessionId, onNewSession]);

  const handleDeleteSession = useCallback(
    (e: React.MouseEvent, id: string) => {
      e.stopPropagation();
      if (confirm("Delete this session?")) {
        deleteSession(id);
      }
    },
    [deleteSession]
  );

  const handleClearAll = useCallback(() => {
    if (confirm("Delete all sessions? This cannot be undone.")) {
      clearAllSessions();
      onNewSession();
    }
  }, [clearAllSessions, onNewSession]);

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    const now = new Date();
    const diff = now.getTime() - date.getTime();
    const days = Math.floor(diff / (1000 * 60 * 60 * 24));

    if (days === 0) {
      return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
    } else if (days === 1) {
      return "Yesterday";
    } else if (days < 7) {
      return date.toLocaleDateString([], { weekday: "short" });
    } else {
      return date.toLocaleDateString([], { month: "short", day: "numeric" });
    }
  };

  return (
    <div className="tab-panel">
      <div className="tab-header">
        <button className="action-btn primary" onClick={handleNewSession}>
          + New Session
        </button>
        {sessions.length > 0 && (
          <button className="action-btn danger" onClick={handleClearAll}>
            Clear All
          </button>
        )}
      </div>

      <div className="tab-list">
        {sessions.length === 0 ? (
          <div className="empty-state">
            <p>No saved sessions</p>
            <p className="hint">Conversations are auto-saved</p>
          </div>
        ) : (
          <ul>
            {sessions.map((session) => (
              <li key={session.id}>
                <button
                  className={`list-item ${session.id === currentSessionId ? "active" : ""}`}
                  onClick={() => handleLoadSession(session.id)}
                >
                  <div className="item-header">
                    <span className="item-title">{session.title}</span>
                    <button
                      className="delete-btn"
                      onClick={(e) => handleDeleteSession(e, session.id)}
                      title="Delete"
                    >
                      ×
                    </button>
                  </div>
                  <div className="item-preview">{session.preview}</div>
                  <div className="item-meta">
                    <span>{formatDate(session.updatedAt)}</span>
                    <span>{session.messageCount} msgs</span>
                  </div>
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

// =============================================================================
// Files Tab
// =============================================================================

interface FilesTabProps {
  onShowDiff: (path: string) => void;
}

function FilesTab({ onShowDiff }: FilesTabProps) {
  const selectPath = useSelectionStore((state) => state.selectPath);

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
// Stats Tab
// =============================================================================

interface StatsTabProps {
  totalInputTokens: number;
  totalOutputTokens: number;
}

function StatsTab({ totalInputTokens, totalOutputTokens }: StatsTabProps) {
  const totalTokens = totalInputTokens + totalOutputTokens;
  const estimatedCost = ((totalInputTokens * 3 + totalOutputTokens * 15) / 1_000_000).toFixed(4);

  return (
    <div className="tab-panel">
      <div className="tab-header">
        <span className="tab-title">Session Statistics</span>
      </div>

      <div className="stats-content">
        <div className="stat-card">
          <div className="stat-label">Total Tokens</div>
          <div className="stat-value">{totalTokens.toLocaleString()}</div>
        </div>

        <div className="stat-card">
          <div className="stat-label">Input Tokens</div>
          <div className="stat-value">{totalInputTokens.toLocaleString()}</div>
        </div>

        <div className="stat-card">
          <div className="stat-label">Output Tokens</div>
          <div className="stat-value">{totalOutputTokens.toLocaleString()}</div>
        </div>

        <div className="stat-card highlight">
          <div className="stat-label">Estimated Cost</div>
          <div className="stat-value">${estimatedCost}</div>
        </div>

        <div className="stat-info">
          <p>Pricing based on Claude API rates:</p>
          <ul>
            <li>Input: $3/M tokens</li>
            <li>Output: $15/M tokens</li>
          </ul>
        </div>
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
  top: calc(50% + 25px); /* Offset to account for header */
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
  top: 180px; /* Start below the header */
  bottom: 0;
  width: 280px;
  background: var(--agent-bg-secondary);
  border-right: 1px solid var(--agent-border-primary);
  transform: translateX(-100%);
  transition: transform 0.25s ease;
  z-index: 150;
  display: flex;
  flex-direction: column;
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

.action-btn.primary {
  background: var(--agent-accent-blue);
  border-color: var(--agent-accent-blue);
  color: white;
}

.action-btn.primary:hover {
  background: var(--agent-accent-blue-hover);
}

.action-btn.danger {
  color: var(--agent-accent-red);
  border-color: var(--agent-accent-red);
}

.action-btn.danger:hover {
  background: rgba(239, 68, 68, 0.1);
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

.list-item.active {
  background: var(--agent-info-bg);
  border-color: var(--agent-accent-blue);
}

.item-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.item-title {
  flex: 1;
  font-size: 12px;
  font-weight: 500;
  color: var(--agent-text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.item-preview {
  font-size: 11px;
  color: var(--agent-text-muted);
  margin-top: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.item-meta {
  display: flex;
  gap: 8px;
  margin-top: 4px;
  font-size: 10px;
  color: var(--agent-text-disabled);
}

.delete-btn {
  width: 18px;
  height: 18px;
  background: transparent;
  border: none;
  color: var(--agent-text-muted);
  font-size: 14px;
  cursor: pointer;
  border-radius: 4px;
  opacity: 0;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
}

.list-item:hover .delete-btn {
  opacity: 1;
}

.delete-btn:hover {
  background: rgba(239, 68, 68, 0.2);
  color: var(--agent-accent-red);
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
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.stat-card {
  padding: 12px;
  background: var(--agent-bg-tertiary);
  border-radius: 8px;
  border: 1px solid var(--agent-border-primary);
}

.stat-card.highlight {
  background: var(--agent-info-bg);
  border-color: var(--agent-accent-blue);
}

.stat-label {
  font-size: 11px;
  color: var(--agent-text-muted);
  margin-bottom: 4px;
}

.stat-value {
  font-size: 18px;
  font-weight: 600;
  color: var(--agent-text-primary);
}

.stat-card.highlight .stat-value {
  color: var(--agent-accent-green);
}

.stat-info {
  margin-top: 8px;
  padding: 10px;
  background: var(--agent-bg-tertiary);
  border-radius: 6px;
  font-size: 11px;
  color: var(--agent-text-muted);
}

.stat-info p {
  margin: 0 0 6px;
}

.stat-info ul {
  margin: 0;
  padding-left: 16px;
}

.stat-info li {
  margin-bottom: 2px;
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
