/**
 * Session History Sidebar
 *
 * Displays list of saved Claude Agent sessions with ability to
 * load, delete, and manage conversation history.
 */

import { useCallback } from "react";
import {
  useSessionHistoryStore,
  SessionSnapshot,
} from "../stores/sessionHistoryStore";

interface SessionHistorySidebarProps {
  onLoadSession: (messages: SessionSnapshot["messages"]) => void;
  onNewSession: () => void;
}

export function SessionHistorySidebar({
  onLoadSession,
  onNewSession,
}: SessionHistorySidebarProps) {
  const {
    sessions,
    currentSessionId,
    sidebarOpen,
    loadSession,
    deleteSession,
    clearAllSessions,
    setCurrentSessionId,
    toggleSidebar,
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
    <>
      {/* Toggle button */}
      <button
        className="sidebar-toggle"
        onClick={toggleSidebar}
        title={sidebarOpen ? "Close history" : "Open history"}
        aria-expanded={sidebarOpen}
        aria-controls="session-history-sidebar"
        aria-label={sidebarOpen ? "Close session history" : "Open session history"}
      >
        <span aria-hidden="true">{sidebarOpen ? "«" : "»"}</span>
      </button>

      {/* Sidebar */}
      <aside
        id="session-history-sidebar"
        className={`session-sidebar ${sidebarOpen ? "open" : ""}`}
        aria-label="Session history"
        aria-hidden={!sidebarOpen}
      >
        <div className="sidebar-header">
          <h3 id="sidebar-title">History</h3>
          <div className="sidebar-actions">
            <button
              className="sidebar-btn new"
              onClick={handleNewSession}
              title="New session"
            >
              + New
            </button>
            {sessions.length > 0 && (
              <button
                className="sidebar-btn clear"
                onClick={handleClearAll}
                title="Clear all"
              >
                Clear
              </button>
            )}
          </div>
        </div>

        <nav className="session-list" aria-labelledby="sidebar-title" role="navigation">
          {sessions.length === 0 ? (
            <div className="empty-history" role="status">
              <p>No saved sessions</p>
              <p className="hint">Conversations are auto-saved</p>
            </div>
          ) : (
            <ul role="list" aria-label="Saved sessions">
              {sessions.map((session) => (
                <li key={session.id}>
                  <button
                    className={`session-item ${
                      session.id === currentSessionId ? "active" : ""
                    }`}
                    onClick={() => handleLoadSession(session.id)}
                    aria-current={session.id === currentSessionId ? "true" : undefined}
                    aria-label={`Load session: ${session.title}`}
                  >
                    <div className="session-item-header">
                      <span className="session-title">{session.title}</span>
                      <button
                        className="delete-btn"
                        onClick={(e) => handleDeleteSession(e, session.id)}
                        title="Delete session"
                        aria-label={`Delete session: ${session.title}`}
                      >
                        <span aria-hidden="true">×</span>
                      </button>
                    </div>
                    <div className="session-preview">{session.preview}</div>
                    <div className="session-meta">
                      <span className="session-date">
                        {formatDate(session.updatedAt)}
                      </span>
                      <span className="session-count">
                        {session.messageCount} msg{session.messageCount !== 1 ? "s" : ""}
                      </span>
                      {session.model && (
                        <span className="session-model">
                          {session.model.replace("claude-", "").split("-")[0]}
                        </span>
                      )}
                    </div>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </nav>
      </aside>

      <style>{sidebarStyles}</style>
    </>
  );
}

const sidebarStyles = `
/* Toggle button */
.sidebar-toggle {
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  width: 24px;
  height: 48px;
  background: var(--agent-bg-tertiary);
  border: 1px solid var(--agent-border-secondary);
  border-left: none;
  border-radius: 0 6px 6px 0;
  color: var(--agent-text-secondary);
  font-size: 14px;
  cursor: pointer;
  z-index: 100;
  transition: all 0.2s;
}

.sidebar-toggle:hover {
  background: var(--agent-border-secondary);
  color: var(--agent-text-primary);
}

.sidebar-toggle:focus {
  outline: 2px solid var(--agent-accent-blue);
  outline-offset: 2px;
}

.sidebar-toggle:focus:not(:focus-visible) {
  outline: none;
}

/* Sidebar */
.session-sidebar {
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 280px;
  background: var(--agent-bg-secondary);
  border-right: 1px solid var(--agent-border-primary);
  transform: translateX(-100%);
  transition: transform 0.3s ease;
  z-index: 90;
  display: flex;
  flex-direction: column;
}

.session-sidebar.open {
  transform: translateX(0);
}

.sidebar-header {
  padding: 12px 16px;
  border-bottom: 1px solid var(--agent-border-primary);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.sidebar-header h3 {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--agent-text-primary);
}

.sidebar-actions {
  display: flex;
  gap: 8px;
}

.sidebar-btn {
  padding: 4px 10px;
  font-size: 11px;
  background: transparent;
  border: 1px solid var(--agent-border-secondary);
  border-radius: 4px;
  color: var(--agent-text-secondary);
  cursor: pointer;
  transition: all 0.2s;
}

.sidebar-btn:hover {
  background: var(--agent-bg-tertiary);
  color: var(--agent-text-primary);
}

.sidebar-btn.new {
  background: var(--agent-accent-blue);
  border-color: var(--agent-accent-blue);
  color: white;
}

.sidebar-btn.new:hover {
  background: var(--agent-accent-blue-hover);
}

.sidebar-btn.clear {
  color: var(--agent-accent-red);
  border-color: var(--agent-accent-red);
}

.sidebar-btn.clear:hover {
  background: rgba(239, 68, 68, 0.1);
}

/* Session list */
.session-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.empty-history {
  padding: 24px 16px;
  text-align: center;
  color: var(--agent-text-muted);
}

.empty-history p {
  margin: 0 0 4px;
  font-size: 13px;
}

.empty-history .hint {
  font-size: 11px;
  color: var(--agent-text-disabled);
}

/* Session list container */
.session-list ul {
  list-style: none;
  margin: 0;
  padding: 0;
}

.session-list li {
  margin-bottom: 4px;
}

/* Session item */
.session-item {
  display: block;
  width: 100%;
  padding: 10px 12px;
  border-radius: 6px;
  cursor: pointer;
  transition: background 0.2s;
  background: transparent;
  border: 1px solid transparent;
  text-align: left;
  color: inherit;
  font: inherit;
}

.session-item:hover {
  background: var(--agent-bg-tertiary);
}

.session-item:focus {
  outline: 2px solid var(--agent-accent-blue);
  outline-offset: 2px;
}

.session-item:focus:not(:focus-visible) {
  outline: none;
}

.session-item.active {
  background: var(--agent-info-bg);
  border: 1px solid var(--agent-accent-blue);
}

.session-item-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 8px;
}

.session-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--agent-text-primary);
  line-height: 1.3;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.delete-btn {
  width: 18px;
  height: 18px;
  background: transparent;
  border: none;
  color: var(--agent-text-muted);
  font-size: 16px;
  cursor: pointer;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: all 0.2s;
  flex-shrink: 0;
}

.session-item:hover .delete-btn {
  opacity: 1;
}

.delete-btn:hover {
  background: rgba(239, 68, 68, 0.2);
  color: var(--agent-accent-red);
}

.session-preview {
  font-size: 11px;
  color: var(--agent-text-muted);
  margin-top: 4px;
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.session-meta {
  display: flex;
  gap: 8px;
  margin-top: 6px;
  font-size: 10px;
  color: var(--agent-text-disabled);
}

.session-model {
  padding: 1px 4px;
  background: var(--agent-bg-tertiary);
  border-radius: 3px;
}

/* Scrollbar */
.session-list::-webkit-scrollbar {
  width: 6px;
}

.session-list::-webkit-scrollbar-track {
  background: transparent;
}

.session-list::-webkit-scrollbar-thumb {
  background: var(--agent-border-secondary);
  border-radius: 3px;
}

.session-list::-webkit-scrollbar-thumb:hover {
  background: var(--agent-text-disabled);
}

/* Responsive - Tablet and below */
@media (max-width: 768px) {
  .session-sidebar {
    width: 100%;
    max-width: 320px;
  }

  .sidebar-toggle {
    width: 32px;
    height: 56px;
    font-size: 16px;
  }
}

/* Responsive - Mobile */
@media (max-width: 480px) {
  .session-sidebar {
    max-width: 100%;
  }

  .session-sidebar.open {
    box-shadow: 0 0 20px var(--agent-shadow);
  }

  .sidebar-header {
    padding: 10px 12px;
  }

  .session-list {
    padding: 6px;
  }

  .session-item {
    padding: 8px 10px;
  }

  .delete-btn {
    opacity: 1;
  }
}
`;
