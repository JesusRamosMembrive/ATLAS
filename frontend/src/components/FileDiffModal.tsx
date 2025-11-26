import { useQuery } from "@tanstack/react-query";

import { getWorkingTreeDiff } from "../api/client";
import { queryKeys } from "../api/queryKeys";
import "../styles/diff.css";

interface FileDiffModalProps {
  path: string;
  onClose: () => void;
}

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
 * Parse unified diff into side-by-side pairs
 */
function parseDiffToSideBySide(diffContent: string): SideBySidePair[] {
  const lines = diffContent.split(/\r?\n/);
  const pairs: SideBySidePair[] = [];

  let oldLineNum = 0;
  let newLineNum = 0;

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

  for (const line of lines) {
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
    if (line.startsWith(" ") || line === "") {
      const content = line.startsWith(" ") ? line.substring(1) : line;
      pairs.push({
        left: { type: "context", content, oldLineNum: oldLineNum++ },
        right: { type: "context", content, newLineNum: newLineNum++ },
      });
    }
  }

  flushBuffers();
  return pairs;
}

export function FileDiffModal({ path, onClose }: FileDiffModalProps): JSX.Element {
  const { data, isPending, isError, error, refetch } = useQuery({
    queryKey: queryKeys.fileDiff(path),
    queryFn: () => getWorkingTreeDiff(path),
    enabled: Boolean(path),
  });

  const diffContent = data?.diff ?? "";
  const hasDiffContent = Boolean(diffContent.trim());
  const changeSummary = data?.change_summary;
  const changeStatus = data?.change_status;
  const changeLabel = formatStatus(changeStatus);

  const sideBySidePairs = hasDiffContent ? parseDiffToSideBySide(diffContent) : [];

  return (
    <div className="diff-overlay" onClick={onClose}>
      <div className="diff-modal diff-modal--wide" onClick={(event) => event.stopPropagation()}>
        <header className="diff-modal__header">
          <div>
            <p className="diff-modal__eyebrow">Working tree diff vs HEAD</p>
            <h2 className="diff-modal__title">{path}</h2>
            {changeLabel && (
              <span className="diff-modal__status" title={changeSummary ?? undefined}>
                {changeLabel}
              </span>
            )}
          </div>
          <div className="diff-modal__actions">
            <button
              type="button"
              className="diff-modal__refresh"
              onClick={() => refetch()}
            >
              Refresh
            </button>
            <button type="button" className="diff-modal__close" onClick={onClose}>
              ×
            </button>
          </div>
        </header>

        {isPending && <p className="diff-modal__hint">Loading diff...</p>}
        {isError && (
          <div className="error-banner" style={{ marginBottom: "16px" }}>
            Error loading diff: {(error as Error)?.message ?? "unknown error"}
          </div>
        )}

        {!isPending && !isError && !hasDiffContent && (
          <p className="diff-modal__hint">No changes detected for this file.</p>
        )}

        {hasDiffContent && (
          <div className="diff-modal__body diff-side-by-side">
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
        )}
      </div>
    </div>
  );
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

function formatStatus(status?: string | null): string {
  if (!status) {
    return "";
  }
  switch (status) {
    case "untracked":
      return "New file";
    case "added":
      return "Added";
    case "deleted":
      return "Deleted";
    case "renamed":
      return "Renamed";
    case "conflict":
      return "Conflict";
    default:
      return "Modified";
  }
}
