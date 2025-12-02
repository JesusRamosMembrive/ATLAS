/**
 * Tool Approval Modal
 *
 * Displays a modal for approving/rejecting tool executions with preview.
 * Shows diff for file modifications, command preview for Bash, etc.
 */

import React, { useState, useMemo } from "react";
import {
  useClaudeSessionStore,
  PendingToolApproval,
} from "../stores/claudeSessionStore";
import { getToolIcon } from "../types/claude-events";
import { createLogger } from "../utils/logger";
import {
  extractCommandPreview,
  extractMultiDiffEdits,
  getPreviewBoolean,
  getPreviewString,
} from "../types/approval";
import "../styles/diff.css";
import "./ToolApprovalModal.css";

// Create namespaced logger
const log = createLogger("ToolApprovalModal");

// ============================================================================
// Diff Viewer Component - Split View (Side by Side)
// ============================================================================

interface DiffLine {
  type: "context" | "added" | "removed" | "hunk" | "meta";
  content: string;
  oldLineNum?: number;
  newLineNum?: number;
}

interface SideBySidePair {
  left: DiffLine | null;
  right: DiffLine | null;
}

/**
 * Parse diff lines array into side-by-side pairs for split view
 */
function parseDiffLinesToSideBySide(diffLines: string[]): SideBySidePair[] {
  const pairs: SideBySidePair[] = [];

  let oldLineNum = 1;
  let newLineNum = 1;

  // Buffers for collecting removed/added lines to pair them
  const removedBuffer: DiffLine[] = [];
  const addedBuffer: DiffLine[] = [];

  const flushBuffers = () => {
    // Pair up removed and added lines
    const maxLen = Math.max(removedBuffer.length, addedBuffer.length);
    for (let i = 0; i < maxLen; i++) {
      pairs.push({
        left: removedBuffer[i] || null,
        right: addedBuffer[i] || null,
      });
    }
    removedBuffer.length = 0;
    addedBuffer.length = 0;
  };

  for (const line of diffLines) {
    // Meta lines (--- and +++)
    if (line.startsWith("---") || line.startsWith("+++")) {
      flushBuffers();
      pairs.push({
        left: { type: "meta", content: line },
        right: { type: "meta", content: "" },
      });
      continue;
    }

    // Hunk header (@@ -x,y +a,b @@)
    if (line.startsWith("@@")) {
      flushBuffers();
      // Parse line numbers from hunk header
      const match = line.match(/@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@/);
      if (match) {
        oldLineNum = parseInt(match[1], 10);
        newLineNum = parseInt(match[2], 10);
      }
      pairs.push({
        left: { type: "hunk", content: line },
        right: { type: "hunk", content: "" },
      });
      continue;
    }

    // Removed line
    if (line.startsWith("-")) {
      removedBuffer.push({
        type: "removed",
        content: line.substring(1),
        oldLineNum: oldLineNum++,
      });
      continue;
    }

    // Added line
    if (line.startsWith("+")) {
      addedBuffer.push({
        type: "added",
        content: line.substring(1),
        newLineNum: newLineNum++,
      });
      continue;
    }

    // Context line (unchanged)
    flushBuffers();
    const content = line.startsWith(" ") ? line.substring(1) : line;
    pairs.push({
      left: { type: "context", content, oldLineNum: oldLineNum++ },
      right: { type: "context", content, newLineNum: newLineNum++ },
    });
  }

  flushBuffers();
  return pairs;
}

function getCellClass(line: DiffLine | null): string {
  if (!line) return "diff-cell--empty";
  switch (line.type) {
    case "added": return "diff-cell--added";
    case "removed": return "diff-cell--removed";
    case "hunk": return "diff-cell--hunk";
    case "meta": return "diff-cell--meta";
    default: return "";
  }
}

interface DiffViewerProps {
  diffLines: string[];
  filePath?: string;
  isNewFile?: boolean;
}

const DiffViewer: React.FC<DiffViewerProps> = ({
  diffLines,
  filePath,
  isNewFile,
}) => {
  const stats = useMemo(() => {
    let added = 0;
    let removed = 0;
    for (const line of diffLines) {
      if (line.startsWith("+") && !line.startsWith("+++")) {
        added++;
      } else if (line.startsWith("-") && !line.startsWith("---")) {
        removed++;
      }
    }
    return { added, removed };
  }, [diffLines]);

  const sideBySidePairs = useMemo(
    () => parseDiffLinesToSideBySide(diffLines),
    [diffLines]
  );

  return (
    <div className="tool-approval-diff-viewer">
      <div className="tool-approval-diff-header-bar">
        <span className="tool-approval-diff-file">
          {isNewFile ? "📄 " : "📝 "}
          {filePath || "Unknown file"}
          {isNewFile && <span className="tool-approval-diff-new-badge">NEW</span>}
        </span>
        <span className="tool-approval-diff-stats">
          <span className="tool-approval-diff-added-count">+{stats.added}</span>
          <span className="tool-approval-diff-removed-count">-{stats.removed}</span>
        </span>
      </div>

      {diffLines.length > 0 ? (
        <div className="diff-side-by-side">
          {/* Column headers */}
          <div className="diff-columns-header">
            <div className="diff-column-header diff-column-header--old">Original</div>
            <div className="diff-column-header diff-column-header--new">Modified</div>
          </div>

          {/* Diff content */}
          <div className="diff-columns">
            {sideBySidePairs.map((pair, index) => (
              <div key={index} className="diff-row">
                {/* Left side (old/removed) */}
                <div className={`diff-cell diff-cell--left ${getCellClass(pair.left)}`}>
                  {pair.left && (
                    <>
                      <span className="diff-line-num">
                        {pair.left.oldLineNum ?? ""}
                      </span>
                      <span className="diff-line-content">
                        {pair.left.content || "\u00A0"}
                      </span>
                    </>
                  )}
                  {!pair.left && <span className="diff-line-content diff-empty">&nbsp;</span>}
                </div>

                {/* Right side (new/added) */}
                <div className={`diff-cell diff-cell--right ${getCellClass(pair.right)}`}>
                  {pair.right && (
                    <>
                      <span className="diff-line-num">
                        {pair.right.newLineNum ?? ""}
                      </span>
                      <span className="diff-line-content">
                        {pair.right.content || "\u00A0"}
                      </span>
                    </>
                  )}
                  {!pair.right && <span className="diff-line-content diff-empty">&nbsp;</span>}
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div className="tool-approval-diff-empty">No changes to preview</div>
      )}
    </div>
  );
};

// ============================================================================
// Command Preview Component
// ============================================================================

interface CommandPreviewProps {
  command: string;
  description?: string;
  previewData: Record<string, unknown>;
}

const CommandPreview: React.FC<CommandPreviewProps> = ({
  command,
  description,
  previewData,
}) => {
  // Use type-safe extraction instead of unsafe `as boolean` casts
  const cmdPreview = extractCommandPreview(previewData);
  const hasSudo = cmdPreview.has_sudo ?? false;
  const hasRm = cmdPreview.has_rm ?? false;
  const hasPipe = cmdPreview.has_pipe ?? false;
  const hasRedirect = cmdPreview.has_redirect ?? false;

  return (
    <div className="tool-approval-command-preview">
      {description && (
        <div className="tool-approval-command-description">{description}</div>
      )}
      <div className="tool-approval-command-box">
        <pre>{command}</pre>
      </div>
      {(hasSudo || hasRm || hasPipe || hasRedirect) && (
        <div className="tool-approval-command-warnings">
          {hasSudo && (
            <span className="tool-approval-warning tool-approval-warning-sudo">
              ⚠️ Uses sudo
            </span>
          )}
          {hasRm && (
            <span className="tool-approval-warning tool-approval-warning-rm">
              ⚠️ Uses rm (delete)
            </span>
          )}
          {hasPipe && (
            <span className="tool-approval-warning tool-approval-warning-pipe">
              ℹ️ Uses pipe
            </span>
          )}
          {hasRedirect && (
            <span className="tool-approval-warning tool-approval-warning-redirect">
              ℹ️ Uses redirect
            </span>
          )}
        </div>
      )}
    </div>
  );
};

// ============================================================================
// Generic Preview Component
// ============================================================================

interface GenericPreviewProps {
  toolInput: Record<string, unknown>;
}

const GenericPreview: React.FC<GenericPreviewProps> = ({ toolInput }) => {
  return (
    <div className="tool-approval-generic-preview">
      <pre>{JSON.stringify(toolInput, null, 2)}</pre>
    </div>
  );
};

// ============================================================================
// Main Modal Component
// ============================================================================

interface ToolApprovalModalProps {
  approval: PendingToolApproval;
  onApprove: () => void;
  onReject: (feedback?: string) => void;
}

export const ToolApprovalModal: React.FC<ToolApprovalModalProps> = ({
  approval,
  onApprove,
  onReject,
}) => {
  const [feedback, setFeedback] = useState("");
  const [showFeedback, setShowFeedback] = useState(false);

  const handleReject = () => {
    if (showFeedback && feedback.trim()) {
      onReject(feedback.trim());
    } else if (showFeedback) {
      // User clicked reject with empty feedback - just reject
      onReject();
    } else {
      // Show feedback input
      setShowFeedback(true);
    }
  };

  const handleRejectWithoutFeedback = () => {
    onReject();
  };

  const icon = getToolIcon(approval.toolName);

  return (
    <div className="tool-approval-modal-overlay">
      <div className="tool-approval-modal">
        <div className="tool-approval-modal-header">
          <span className="tool-approval-modal-icon">{icon}</span>
          <h3>Tool Approval Required</h3>
          <span className="tool-approval-modal-tool-name">{approval.toolName}</span>
        </div>

        <div className="tool-approval-modal-body">
          {/* Preview based on type */}
          {approval.previewType === "diff" && (
            <DiffViewer
              diffLines={approval.diffLines}
              filePath={approval.filePath}
              isNewFile={getPreviewBoolean(approval.previewData, "is_new_file")}
            />
          )}

          {approval.previewType === "multi_diff" && (
            <div className="tool-approval-multi-diff">
              {extractMultiDiffEdits(approval.previewData).map((edit, idx) => (
                <DiffViewer
                  key={idx}
                  diffLines={edit.diff}
                  filePath={edit.file_path}
                />
              ))}
            </div>
          )}

          {approval.previewType === "command" && (
            <CommandPreview
              command={getPreviewString(approval.toolInput, "command")}
              description={getPreviewString(approval.toolInput, "description")}
              previewData={approval.previewData}
            />
          )}

          {approval.previewType === "generic" && (
            <GenericPreview toolInput={approval.toolInput} />
          )}

          {/* Feedback section */}
          {showFeedback && (
            <div className="tool-approval-feedback-section">
              <label htmlFor="feedback-input">
                Why are you rejecting this? (optional - helps Claude understand)
              </label>
              <textarea
                id="feedback-input"
                value={feedback}
                onChange={(e) => setFeedback(e.target.value)}
                placeholder="e.g., Don't modify that file, use a different approach..."
                rows={3}
              />
            </div>
          )}
        </div>

        <div className="tool-approval-modal-footer">
          {showFeedback ? (
            <>
              <button
                className="tool-approval-btn tool-approval-btn-cancel"
                onClick={() => setShowFeedback(false)}
              >
                Back
              </button>
              <button
                className="tool-approval-btn tool-approval-btn-reject-confirm"
                onClick={handleReject}
              >
                {feedback.trim() ? "Reject with Feedback" : "Reject"}
              </button>
            </>
          ) : (
            <>
              <button
                className="tool-approval-btn tool-approval-btn-reject"
                onClick={handleReject}
                title="Reject and provide feedback"
              >
                ✕ Reject
              </button>
              <button
                className="tool-approval-btn tool-approval-btn-reject-silent"
                onClick={handleRejectWithoutFeedback}
                title="Reject without feedback"
              >
                Skip
              </button>
              <button
                className="tool-approval-btn tool-approval-btn-approve"
                onClick={onApprove}
                title="Approve and execute"
              >
                ✓ Approve
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
};

// ============================================================================
// Connected Modal Component (uses store directly)
// ============================================================================

export const ConnectedToolApprovalModal: React.FC = () => {
  const pendingToolApproval = useClaudeSessionStore(
    (state) => state.pendingToolApproval
  );
  const respondToToolApproval = useClaudeSessionStore(
    (state) => state.respondToToolApproval
  );

  // Debug log for modal visibility
  log.debug("pendingToolApproval:", pendingToolApproval);

  if (!pendingToolApproval) {
    return null;
  }

  log.debug("SHOWING MODAL for:", pendingToolApproval.toolName);

  const handleApprove = () => {
    respondToToolApproval(true);
  };

  const handleReject = (feedback?: string) => {
    respondToToolApproval(false, feedback);
  };

  return (
    <ToolApprovalModal
      approval={pendingToolApproval}
      onApprove={handleApprove}
      onReject={handleReject}
    />
  );
};

export default ConnectedToolApprovalModal;
