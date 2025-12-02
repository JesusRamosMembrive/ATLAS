/**
 * CodeTimelineView - DAW-style visualization of git commit history
 */

import { useState, useRef, useEffect, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import "../styles/timeline.css";
import "../styles/diff.css";

interface CommitInfo {
  hash: string;
  author: string;
  date: string;
  message: string;
  files_changed: string[];
}

interface TimelineMatrixResponse {
  commits: CommitInfo[];
  files: string[];
  matrix: boolean[][];
  total_files: number;
  total_commits: number;
}

interface DiffModalProps {
  commit: { hash: string; file: string };
  onClose: () => void;
}

// Types for split view
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
 * Parse diff text into side-by-side pairs for split view
 */
function parseDiffToSideBySide(diffText: string): SideBySidePair[] {
  const lines = diffText.split(/\r?\n/);
  const pairs: SideBySidePair[] = [];

  let oldLineNum = 1;
  let newLineNum = 1;

  const removedBuffer: DiffLine[] = [];
  const addedBuffer: DiffLine[] = [];

  const flushBuffers = () => {
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
    if (line.startsWith("---") || line.startsWith("+++")) {
      flushBuffers();
      pairs.push({
        left: { type: "meta", content: line },
        right: { type: "meta", content: "" },
      });
      continue;
    }

    if (line.startsWith("@@")) {
      flushBuffers();
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

    if (line.startsWith("-")) {
      removedBuffer.push({
        type: "removed",
        content: line.substring(1),
        oldLineNum: oldLineNum++,
      });
      continue;
    }

    if (line.startsWith("+")) {
      addedBuffer.push({
        type: "added",
        content: line.substring(1),
        newLineNum: newLineNum++,
      });
      continue;
    }

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

function DiffModal({ commit, onClose }: DiffModalProps) {
  const { data: diffData, isLoading, error } = useQuery({
    queryKey: ["file-diff", commit.hash, commit.file],
    queryFn: async () => {
      const params = new URLSearchParams();
      params.append("file_path", commit.file);
      const response = await fetch(`/api/timeline/diff/${commit.hash}?${params}`);
      if (!response.ok) {
        throw new Error(`Failed to fetch diff: ${response.statusText}`);
      }
      return response.json();
    },
  });

  const sideBySidePairs = useMemo(() => {
    if (!diffData?.diff) return [];
    return parseDiffToSideBySide(diffData.diff);
  }, [diffData]);

  return (
    <div className="timeline-modal-overlay" onClick={onClose}>
      <div className="timeline-modal timeline-modal--wide" onClick={(e) => e.stopPropagation()}>
        <div className="timeline-modal-header">
          <h2>File Changes</h2>
          <button className="timeline-modal-close" onClick={onClose}>
            ×
          </button>
        </div>
        <div className="timeline-modal-body">
          <div className="timeline-modal-info">
            <div className="timeline-modal-info-row">
              <strong>File:</strong>
              <code>{commit.file}</code>
            </div>
            <div className="timeline-modal-info-row">
              <strong>Commit:</strong>
              <code>{commit.hash}</code>
            </div>
          </div>

          {isLoading && (
            <div className="timeline-modal-changes">
              <p className="timeline-modal-loading">Loading diff...</p>
            </div>
          )}

          {error && (
            <div className="timeline-modal-changes">
              <p className="timeline-modal-error">
                Error loading diff: {(error as Error).message}
              </p>
            </div>
          )}

          {diffData && sideBySidePairs.length > 0 && (
            <div className="timeline-modal-changes">
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
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function CodeTimelineView() {
  const [limit, setLimit] = useState(30);
  const [filePattern, setFilePattern] = useState("");
  const [selectedCommit, setSelectedCommit] = useState<{
    hash: string;
    file: string;
  } | null>(null);

  // Refs for synchronizing horizontal scroll
  const commitsHeaderRef = useRef<HTMLDivElement>(null);
  const gridBodyRef = useRef<HTMLDivElement>(null);

  const {
    data: matrixData,
    isLoading,
    error,
    refetch,
  } = useQuery<TimelineMatrixResponse>({
    queryKey: ["timeline-matrix", limit, filePattern],
    queryFn: async () => {
      const params = new URLSearchParams();
      params.append("limit", limit.toString());
      if (filePattern) {
        params.append("file_pattern", filePattern);
      }
      const response = await fetch(`/api/timeline/matrix?${params}`);
      if (!response.ok) {
        throw new Error(`Failed to fetch timeline: ${response.statusText}`);
      }
      return response.json();
    },
  });

  const formatDate = (dateStr: string) => {
    try {
      return new Date(dateStr).toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
      });
    } catch {
      return dateStr;
    }
  };

  const formatShortHash = (hash: string) => hash.substring(0, 7);
  const getFileName = (path: string) => path.split("/").pop() || path;

  const formatFilePath = (path: string) => {
    const parts = path.split("/");
    if (parts.length === 1) {
      return <span className="timeline-file-name">{parts[0]}</span>;
    }

    const directory = parts.slice(0, -1).join("/");
    const filename = parts[parts.length - 1];

    return (
      <>
        <span className="timeline-file-directory">{directory}/</span>
        <span className="timeline-file-name">{filename}</span>
      </>
    );
  };

  // Synchronize horizontal scroll between header and body
  useEffect(() => {
    const headerRow = commitsHeaderRef.current;
    const bodyContainer = gridBodyRef.current;

    if (!headerRow || !bodyContainer) return;

    const syncScroll = (source: HTMLElement, target: HTMLElement) => {
      target.scrollLeft = source.scrollLeft;
    };

    const handleHeaderScroll = () => {
      if (headerRow && bodyContainer) {
        syncScroll(headerRow, bodyContainer);
      }
    };

    const handleBodyScroll = () => {
      if (headerRow && bodyContainer) {
        syncScroll(bodyContainer, headerRow);
      }
    };

    headerRow.addEventListener('scroll', handleHeaderScroll);
    bodyContainer.addEventListener('scroll', handleBodyScroll);

    return () => {
      headerRow.removeEventListener('scroll', handleHeaderScroll);
      bodyContainer.removeEventListener('scroll', handleBodyScroll);
    };
  }, [matrixData]); // Re-run when data changes

  // Keep file labels visible during horizontal scroll
  useEffect(() => {
    const bodyContainer = gridBodyRef.current;
    if (!bodyContainer) return;

    const updateStickyPositions = () => {
      const scrollLeft = bodyContainer.scrollLeft;
      const fileLabels = bodyContainer.querySelectorAll('.timeline-file-label');

      fileLabels.forEach((label) => {
        (label as HTMLElement).style.transform = `translateX(${scrollLeft}px)`;
      });
    };

    bodyContainer.addEventListener('scroll', updateStickyPositions);

    return () => {
      bodyContainer.removeEventListener('scroll', updateStickyPositions);
    };
  }, [matrixData]);

  return (
    <div className="timeline-view">
      <div className="timeline-header">
        <h1>Code Timeline</h1>
        <p className="timeline-subtitle">
          DAW-style visualization of git commit history. Each cell represents a file change in a commit.
        </p>
      </div>

      {/* Controls */}
      <div className="timeline-controls">
        <div className="timeline-control-group">
          <label htmlFor="limit">Commits:</label>
          <input
            id="limit"
            type="number"
            min="5"
            max="1000"
            value={limit}
            onChange={(e) => setLimit(parseInt(e.target.value) || 30)}
            className="timeline-input"
          />
        </div>

        <div className="timeline-control-group">
          <label htmlFor="file-pattern">File Filter (regex):</label>
          <input
            id="file-pattern"
            type="text"
            placeholder="e.g., \.py$ for Python files"
            value={filePattern}
            onChange={(e) => setFilePattern(e.target.value)}
            className="timeline-input"
          />
        </div>

        <button onClick={() => refetch()} className="timeline-button">
          Refresh
        </button>
      </div>

      {/* Loading State */}
      {isLoading && (
        <div className="timeline-loading">
          <p>Loading timeline data...</p>
        </div>
      )}

      {/* Error State */}
      {error && (
        <div className="timeline-error">
          <p>Error loading timeline: {(error as Error).message}</p>
          <p>Make sure the backend server is running and this is a git repository.</p>
        </div>
      )}

      {/* Timeline Matrix */}
      {matrixData && !isLoading && (
        <div className="timeline-content">
          {/* Summary Stats */}
          <div className="timeline-stats">
            <div className="timeline-stat">
              <span className="timeline-stat-label">Files:</span>
              <span className="timeline-stat-value">{matrixData.total_files}</span>
            </div>
            <div className="timeline-stat">
              <span className="timeline-stat-label">Commits:</span>
              <span className="timeline-stat-value">{matrixData.total_commits}</span>
            </div>
          </div>

          {matrixData.total_commits === 0 ? (
            <div className="timeline-help">
              <p>No commits found. Make sure you have git history in this repository.</p>
            </div>
          ) : (
            <>
              {/* Main Grid Container */}
              <div className="timeline-grid-container">
                {/* Header Row with Commits */}
                <div className="timeline-commits-header">
                  <div className="timeline-files-spacer">Files</div>
                  <div className="timeline-commits-row" ref={commitsHeaderRef}>
                    {matrixData.commits.map((commit) => (
                      <div
                        key={commit.hash}
                        className="timeline-commit-cell"
                        title={`${commit.message}\n\n${formatShortHash(commit.hash)}\nby ${commit.author}\n${commit.date}`}
                      >
                        <div className="timeline-commit-message">
                          {commit.message}
                        </div>
                        <div className="timeline-commit-date">
                          {formatDate(commit.date)}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Grid Body: Files × Commits */}
                <div className="timeline-grid-body" ref={gridBodyRef}>
                  {matrixData.files.map((file, fileIdx) => (
                    <div key={file} className="timeline-grid-row">
                      {/* File name (left column) */}
                      <div className="timeline-file-label" title={file}>
                        {formatFilePath(file)}
                      </div>

                      {/* Cells for each commit */}
                      <div className="timeline-cells-row">
                        {matrixData.matrix[fileIdx].map((changed, commitIdx) => {
                          const commit = matrixData.commits[commitIdx];
                          return (
                            <div
                              key={`${file}-${commit.hash}`}
                              className={`timeline-cell ${
                                changed ? "timeline-cell--changed" : ""
                              }`}
                              title={
                                changed
                                  ? `${getFileName(file)} changed in ${formatShortHash(
                                      commit.hash
                                    )}\nClick to see changes`
                                  : ""
                              }
                              onClick={() => {
                                if (changed) {
                                  setSelectedCommit({ hash: commit.hash, file });
                                }
                              }}
                            />
                          );
                        })}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Help Text */}
              <div className="timeline-help">
                <h3>How to use:</h3>
                <ul>
                  <li>Each row represents a file in your repository</li>
                  <li>Each column represents a commit (chronological order)</li>
                  <li>
                    Green cells indicate the file was changed in that commit
                  </li>
                  <li>
                    Use the file filter to narrow down to specific file types (e.g.,{" "}
                    <code>\.py$</code> for Python files)
                  </li>
                  <li>Hover over commits and cells to see more details</li>
                </ul>
              </div>
            </>
          )}
        </div>
      )}

      {/* Modal for commit changes */}
      {selectedCommit && <DiffModal commit={selectedCommit} onClose={() => setSelectedCommit(null)} />}
    </div>
  );
}
