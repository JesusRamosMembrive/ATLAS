import { useState } from "react";
import { Diff, Hunk, parseDiff } from "react-diff-view";
import "react-diff-view/style/index.css";
import type { AuditEvent } from "../api/types";

interface DiffViewerProps {
  /** Event containing the diff to display */
  event: AuditEvent;
}

/**
 * Diff viewer component using react-diff-view
 *
 * Displays unified diffs from file_change events with:
 * - Syntax highlighting (TODO: integrate Prism)
 * - Side-by-side or unified view toggle
 * - Line-by-line change visualization
 * - Collapsible unchanged sections
 *
 * Features:
 * - Handles create/modify/delete change types
 * - Color coding (green=added, red=removed, yellow=modified)
 * - File path display with change type badge
 * - Statistics (lines added/removed)
 */
export function DiffViewer({ event }: DiffViewerProps) {
  const [viewType, setViewType] = useState<"split" | "unified">("unified");

  // Extract diff from event detail
  const diffText = event.detail || "";

  // Parse diff text
  const files = parseDiff(diffText);

  // Extract metadata from event
  const changeType = (event.payload?.change_type as string) || "modify";
  const filePath = event.ref || (event.payload?.file_path as string) || "unknown";
  const linesAdded = (event.payload?.lines_added as number) || 0;
  const linesRemoved = (event.payload?.lines_removed as number) || 0;

  if (!diffText || files.length === 0) {
    return (
      <div className="diff-viewer-empty">
        <p className="diff-empty-message">No diff available</p>
      </div>
    );
  }

  const changeTypeClass = `change-type-${changeType}`;
  const changeTypeLabel = {
    create: "Created",
    modify: "Modified",
    delete: "Deleted",
  }[changeType] || "Changed";

  return (
    <div className="diff-viewer">
      {/* Header with file info and controls */}
      <div className="diff-header">
        <div className="diff-file-info">
          <span className={`diff-change-badge ${changeTypeClass}`}>
            {changeTypeLabel}
          </span>
          <span className="diff-file-path">{filePath}</span>
        </div>

        <div className="diff-stats">
          {linesAdded > 0 && (
            <span className="diff-stat-added">+{linesAdded}</span>
          )}
          {linesRemoved > 0 && (
            <span className="diff-stat-removed">-{linesRemoved}</span>
          )}
        </div>

        <div className="diff-controls">
          <button
            className={`diff-view-toggle ${viewType === "unified" ? "active" : ""}`}
            onClick={() => setViewType("unified")}
            title="Unified view"
          >
            Unified
          </button>
          <button
            className={`diff-view-toggle ${viewType === "split" ? "active" : ""}`}
            onClick={() => setViewType("split")}
            title="Split view"
          >
            Split
          </button>
        </div>
      </div>

      {/* Diff content */}
      <div className="diff-content">
        {files.map((file, index) => (
          <Diff
            key={`${file.oldPath}-${file.newPath}-${index}`}
            viewType={viewType}
            diffType={file.type}
            hunks={file.hunks}
          >
            {(hunks) =>
              hunks.map((hunk) => (
                <Hunk key={hunk.content} hunk={hunk} />
              ))
            }
          </Diff>
        ))}
      </div>
    </div>
  );
}

/**
 * DiffList component for displaying multiple diffs
 *
 * Shows a chronological list of file changes with expandable diffs.
 */
interface DiffListProps {
  /** File change events to display */
  events: AuditEvent[];
}

export function DiffList({ events }: DiffListProps) {
  const [expandedIds, setExpandedIds] = useState<Set<number>>(new Set());

  const fileChangeEvents = events.filter((e) => e.type === "file_change");

  const toggleExpanded = (id: number) => {
    const newExpanded = new Set(expandedIds);
    if (expandedIds.has(id)) {
      newExpanded.delete(id);
    } else {
      newExpanded.add(id);
    }
    setExpandedIds(newExpanded);
  };

  if (fileChangeEvents.length === 0) {
    return (
      <div className="diff-list-empty">
        <p className="diff-list-empty-message">
          No file changes detected yet. File changes will appear here as the agent works.
        </p>
      </div>
    );
  }

  return (
    <div className="diff-list">
      {fileChangeEvents.map((event) => {
        const isExpanded = expandedIds.has(event.id);
        const changeType = (event.payload?.change_type as string) || "modify";
        const filePath = event.ref || (event.payload?.file_path as string) || "unknown";

        return (
          <div key={event.id} className="diff-list-item">
            <div
              className="diff-list-item-header"
              onClick={() => toggleExpanded(event.id)}
            >
              <div className="diff-list-item-info">
                <span className={`diff-change-icon change-type-${changeType}`}>
                  {changeType === "create" && "+"}
                  {changeType === "modify" && "~"}
                  {changeType === "delete" && "-"}
                </span>
                <span className="diff-list-item-path">{filePath}</span>
                <span className="diff-list-item-time">
                  {new Date(event.created_at).toLocaleTimeString()}
                </span>
              </div>

              <button className="diff-list-item-toggle">
                {isExpanded ? "▼" : "▶"}
              </button>
            </div>

            {isExpanded && (
              <div className="diff-list-item-content">
                <DiffViewer event={event} />
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
