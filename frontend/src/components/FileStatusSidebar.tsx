import { useQuery } from "@tanstack/react-query";
import { getWorkingTreeChanges } from "../api/client";
import { queryKeys } from "../api/queryKeys";
import { useSelectionStore } from "../state/useSelectionStore";
import type { WorkingTreeChange } from "../api/types";
import { getChangeLabel, getChangeVariant } from "../utils/changeStatus";
import "../styles/changes.css";

interface FileStatusSidebarProps {
    isOpen: boolean;
    onShowDiff: (path: string) => void;
    onClose: () => void;
}

export function FileStatusSidebar({ isOpen, onShowDiff, onClose }: FileStatusSidebarProps): JSX.Element {
    const selectPath = useSelectionStore((state) => state.selectPath);

    const { data, isPending, isError, error, refetch } = useQuery({
        queryKey: queryKeys.changes,
        queryFn: getWorkingTreeChanges,
        refetchInterval: 15000,
    });

    const changes = data?.changes ?? [];

    return (
        <aside
            className={`file-status-sidebar ${isOpen ? "open" : ""}`}
            aria-label="File status sidebar"
            aria-hidden={!isOpen}
        >
            <div className="sidebar-header">
                <h3>Modified Files</h3>
                <div className="sidebar-actions">
                    <button className="sidebar-btn" onClick={() => refetch()} title="Refresh">
                        ↻
                    </button>
                    <button className="sidebar-btn" onClick={onClose} title="Close sidebar">
                        ×
                    </button>
                </div>
            </div>

            <div className="file-list-container">
                {isPending && <p className="sidebar-hint">Checking git status…</p>}

                {isError && (
                    <div className="sidebar-error">
                        Could not load changes: {(error as Error)?.message ?? "unknown error"}
                    </div>
                )}

                {!isPending && !isError && changes.length === 0 && (
                    <p className="sidebar-hint">No pending changes.</p>
                )}

                {changes.length > 0 && (
                    <ul className="file-list">
                        {changes.map((change) => (
                            <FileListItem
                                key={change.path}
                                change={change}
                                onSelect={selectPath}
                                onShowDiff={onShowDiff}
                            />
                        ))}
                    </ul>
                )}
            </div>
            <style>{sidebarStyles}</style>
        </aside>
    );
}

function FileListItem({
    change,
    onSelect,
    onShowDiff,
}: {
    change: WorkingTreeChange;
    onSelect: (path: string) => void;
    onShowDiff: (path: string) => void;
}): JSX.Element {
    const label = getChangeLabel(change.status);
    const variant = getChangeVariant(change.status);

    return (
        <li className="file-item">
            <button
                className="file-item-btn"
                onClick={() => onShowDiff(change.path)}
                title={change.path}
            >
                <div className="file-item-header">
                    <span className={`status-indicator status-${variant}`} />
                    <span className="file-path">{change.path}</span>
                </div>
                <div className="file-item-meta">
                    <span className={`status-text text-${variant}`}>{label}</span>
                </div>
            </button>
        </li>
    );
}

const sidebarStyles = `
.file-status-sidebar {
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  width: 280px;
  background: var(--agent-bg-secondary);
  border-right: 1px solid var(--agent-border-primary);
  transform: translateX(-100%);
  transition: transform 0.3s ease;
  z-index: 95; /* Higher than history sidebar if needed, or manage z-index */
  display: flex;
  flex-direction: column;
}

.file-status-sidebar.open {
  transform: translateX(0);
}

.file-list-container {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.sidebar-hint {
  padding: 16px;
  text-align: center;
  color: var(--agent-text-muted);
  font-size: 13px;
}

.sidebar-error {
  padding: 12px;
  color: var(--agent-error-text);
  background: var(--agent-error-bg);
  font-size: 12px;
  border-radius: 4px;
  margin: 8px;
}

.file-list {
  list-style: none;
  margin: 0;
  padding: 0;
}

.file-item {
  margin-bottom: 4px;
}

.file-item-btn {
  display: block;
  width: 100%;
  padding: 8px 10px;
  background: transparent;
  border: 1px solid transparent;
  border-radius: 6px;
  cursor: pointer;
  text-align: left;
  transition: background 0.2s;
}

.file-item-btn:hover {
  background: var(--agent-bg-tertiary);
}

.file-item-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.file-path {
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  color: var(--agent-text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  direction: rtl;
  text-align: left;
}

.status-indicator {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.status-added { background-color: var(--agent-accent-green); }
.status-deleted { background-color: var(--agent-accent-red); }
.status-modified { background-color: var(--agent-accent-blue); }
.status-renamed { background-color: var(--agent-accent-purple); }
.status-conflict { background-color: var(--agent-accent-yellow); }

.file-item-meta {
  font-size: 10px;
  margin-left: 16px;
}

.status-text {
  font-weight: 500;
}

.text-added { color: var(--agent-accent-green); }
.text-deleted { color: var(--agent-accent-red); }
.text-modified { color: var(--agent-accent-blue); }
.text-renamed { color: var(--agent-accent-purple); }
.text-conflict { color: var(--agent-accent-yellow); }
`;
