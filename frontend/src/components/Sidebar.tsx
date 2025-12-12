import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";

import { getTree } from "../api/client";
import { queryKeys } from "../api/queryKeys";
import type { ProjectTreeNode } from "../api/types";
import { useSelectionStore } from "../state/useSelectionStore";

const DIRECTORY_ICONS = ["📂", "📁"];
const FILE_ICON = "📄";

// File type filter options
const FILE_TYPE_FILTERS: { label: string; extensions: string[] }[] = [
  { label: "Python", extensions: [".py"] },
  { label: "JavaScript", extensions: [".js", ".jsx"] },
  { label: "TypeScript", extensions: [".ts", ".tsx"] },
  { label: "HTML", extensions: [".html", ".htm"] },
  { label: "CSS", extensions: [".css", ".scss", ".sass"] },
  { label: "JSON", extensions: [".json"] },
  { label: "Markdown", extensions: [".md"] },
  { label: "C/C++", extensions: [".c", ".cpp", ".h", ".hpp"] },
];

export function Sidebar({
  onShowDiff,
}: {
  onShowDiff?: (path: string) => void;
}): JSX.Element {
  const [filter, setFilter] = useState("");
  const [selectedTypes, setSelectedTypes] = useState<Set<string>>(new Set());
  const [showOnlyWarnings, setShowOnlyWarnings] = useState(false);
  const [showFilters, setShowFilters] = useState(false);
  const clearSelection = useSelectionStore((state) => state.clearSelection);
  const selectedPath = useSelectionStore((state) => state.selectedPath);

  const { data, isLoading, isError, error } = useQuery({
    queryKey: queryKeys.tree,
    queryFn: getTree,
  });

  const nodes = useMemo(() => {
    const term = filter.trim().toLowerCase();
    let children = data?.children ?? [];

    // Apply text filter
    if (term) {
      children = filterTree(children, term);
    }

    // Apply file type filter
    if (selectedTypes.size > 0) {
      const allowedExtensions = FILE_TYPE_FILTERS
        .filter(t => selectedTypes.has(t.label))
        .flatMap(t => t.extensions);
      children = filterTreeByExtension(children, allowedExtensions);
    }

    // Apply warnings filter
    if (showOnlyWarnings) {
      children = filterTreeByWarnings(children);
    }

    return children;
  }, [data, filter, selectedTypes, showOnlyWarnings]);

  const toggleFileType = (label: string) => {
    setSelectedTypes(prev => {
      const next = new Set(prev);
      if (next.has(label)) {
        next.delete(label);
      } else {
        next.add(label);
      }
      return next;
    });
  };

  const clearFilters = () => {
    setSelectedTypes(new Set());
    setShowOnlyWarnings(false);
    setFilter("");
  };

  const hasActiveFilters = selectedTypes.size > 0 || showOnlyWarnings;

  return (
    <aside className="panel">
      <div className="panel-header">
        <h2>Project</h2>
        {selectedPath && (
          <button type="button" onClick={clearSelection}>
            Clear selection
          </button>
        )}
      </div>

      <div className="search-box">
        <span role="img" aria-label="Filter">
          🔎
        </span>
        <input
          type="search"
          placeholder="Filter files…"
          value={filter}
          onChange={(event) => setFilter(event.target.value)}
        />
        <button
          type="button"
          onClick={() => setShowFilters(!showFilters)}
          style={{
            background: hasActiveFilters ? "#3b82f6" : "transparent",
            border: "1px solid #334155",
            borderRadius: "4px",
            padding: "4px 8px",
            cursor: "pointer",
            color: hasActiveFilters ? "#fff" : "#94a3b8",
            fontSize: "12px",
            marginLeft: "8px",
          }}
          title="Toggle filters"
        >
          ⚙️ {hasActiveFilters && `(${selectedTypes.size + (showOnlyWarnings ? 1 : 0)})`}
        </button>
      </div>

      {showFilters && (
        <div style={{
          padding: "12px",
          background: "#1e293b",
          borderRadius: "6px",
          margin: "8px 0",
          border: "1px solid #334155",
        }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "10px" }}>
            <span style={{ fontSize: "12px", color: "#94a3b8", fontWeight: 500 }}>Filters</span>
            {hasActiveFilters && (
              <button
                type="button"
                onClick={clearFilters}
                style={{
                  background: "transparent",
                  border: "none",
                  color: "#60a5fa",
                  cursor: "pointer",
                  fontSize: "11px",
                  padding: 0,
                }}
              >
                Clear all
              </button>
            )}
          </div>

          <div style={{ marginBottom: "12px" }}>
            <div style={{ fontSize: "11px", color: "#64748b", marginBottom: "6px" }}>File types</div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: "4px" }}>
              {FILE_TYPE_FILTERS.map((ft) => (
                <button
                  key={ft.label}
                  type="button"
                  onClick={() => toggleFileType(ft.label)}
                  style={{
                    background: selectedTypes.has(ft.label) ? "#3b82f6" : "#334155",
                    border: "none",
                    borderRadius: "4px",
                    padding: "4px 8px",
                    cursor: "pointer",
                    color: selectedTypes.has(ft.label) ? "#fff" : "#94a3b8",
                    fontSize: "11px",
                  }}
                >
                  {ft.label}
                </button>
              ))}
            </div>
          </div>

          <div>
            <label style={{ display: "flex", alignItems: "center", gap: "8px", cursor: "pointer" }}>
              <input
                type="checkbox"
                checked={showOnlyWarnings}
                onChange={(e) => setShowOnlyWarnings(e.target.checked)}
                style={{ accentColor: "#facc15" }}
              />
              <span style={{ fontSize: "12px", color: "#e2e8f0" }}>
                ⚠️ Only files with complexity warnings
              </span>
            </label>
          </div>
        </div>
      )}

      {isLoading && <p style={{ color: "#7f869d" }}>Loading structure…</p>}

      {isError && (
        <div className="error-banner">
          Error loading the tree: {(error as Error)?.message ?? "try reloading the page"}
        </div>
      )}

      {!isLoading && !isError && nodes.length === 0 && (
        <p style={{ color: "#7f869d", fontSize: "13px" }}>
          {filter
            ? `No results for “${filter}”.`
            : "No Python files detected. Add `.py` to the root directory to get started."}
        </p>
      )}

      <ul className="tree-list">
        {nodes.map((node) => (
          <TreeNodeItem
            key={`${node.path}-${node.name}`}
            node={node}
            depth={0}
            onShowDiff={onShowDiff}
          />
        ))}
      </ul>
    </aside>
  );
}

function TreeNodeItem({
  node,
  depth,
  onShowDiff,
}: {
  node: ProjectTreeNode;
  depth: number;
  onShowDiff?: (path: string) => void;
}): JSX.Element {
  const selectedPath = useSelectionStore((state) => state.selectedPath);
  const selectPath = useSelectionStore((state) => state.selectPath);
  const [expanded, setExpanded] = useState(true);

  const isDirectory = node.is_dir;
  const isActive = !isDirectory && selectedPath === node.path;
  const symbolCount = node.symbols?.length ?? 0;
  const hasChange = Boolean(node.change_status);

  // Complexity check - works for both files and directories
  const maxComplexity = useMemo(() => {
    return getMaxComplexityInTree(node);
  }, [node]);

  const complexityLevel = maxComplexity > 25 ? "extreme" : maxComplexity > 10 ? "high" : maxComplexity > 5 ? "medium" : "low";
  const showComplexityWarning = maxComplexity > 5;

  const handleClick = () => {
    if (isDirectory) {
      setExpanded((value) => !value);
    } else {
      selectPath(node.path);
    }
  };

  const icon = isDirectory ? DIRECTORY_ICONS[expanded ? 0 : 1] : FILE_ICON;

  return (
    <li>
      <div
        className={clsx("tree-node", {
          active: isActive,
          "tree-node--changed": hasChange,
        })}
        style={{ paddingLeft: depth * 14 + 12 }}
        role="button"
        tabIndex={0}
        onClick={handleClick}
        onKeyDown={(event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            handleClick();
          }
        }}
      >
        <span className="tree-node__content">
          <span aria-hidden="true">{icon}</span>
          <span
            className={clsx("tree-node__label", {
              "tree-node__label--changed": hasChange,
            })}
          >
            {node.name}
          </span>
        </span>
        {(isDirectory || symbolCount > 0 || hasChange) && (
          <div className="tree-node__meta-indicators">
            {hasChange && (
              <span
                className={clsx("tree-node__change-pill", {
                  "tree-node__change-pill--added": node.change_status === "added" || node.change_status === "untracked",
                  "tree-node__change-pill--deleted": node.change_status === "deleted",
                })}
                title={node.change_summary ?? undefined}
              >
                {formatChangeLabel(node.change_status)}
              </span>
            )}
            {!isDirectory && hasChange && onShowDiff && (
              <button
                type="button"
                className="tree-node__diff-button"
                onClick={(event) => {
                  event.stopPropagation();
                  onShowDiff(node.path);
                }}
              >
                View diff
              </button>
            )}
            {isDirectory ? (
              <>
                {showComplexityWarning && (
                  <span
                    className="badge"
                    style={{
                      background: complexityLevel === "extreme" ? "#f87171" : complexityLevel === "high" ? "#fb923c" : "#facc15",
                      color: "#1e293b",
                      fontWeight: 700,
                      cursor: "help"
                    }}
                    title={`Max Complexity in folder: ${maxComplexity}`}
                  >
                    !
                  </span>
                )}
                <span className="badge">{node.children?.length ?? 0}</span>
              </>
            ) : symbolCount > 0 ? (
              <>
                {showComplexityWarning && (
                  <span
                    className="badge"
                    style={{
                      background: complexityLevel === "extreme" ? "#f87171" : complexityLevel === "high" ? "#fb923c" : "#facc15",
                      color: "#1e293b",
                      fontWeight: 700,
                      cursor: "help"
                    }}
                    title={`Max Complexity: ${maxComplexity}`}
                  >
                    !
                  </span>
                )}
                <span className="badge">{symbolCount} symbols</span>
              </>
            ) : null}
          </div>
        )}
      </div>
      {isDirectory && expanded && node.children?.length ? (
        <ul className="tree-children">
          {node.children.map((child) => (
            <TreeNodeItem
              key={`${child.path}-${child.name}`}
              node={child}
              depth={depth + 1}
              onShowDiff={onShowDiff}
            />
          ))}
        </ul>
      ) : null}
    </li>
  );
}

function formatChangeLabel(status?: string | null): string {
  if (!status) {
    return "";
  }
  switch (status) {
    case "untracked":
      return "New";
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

function filterTree(nodes: ProjectTreeNode[], term: string): ProjectTreeNode[] {
  const matcher = (value: string) => value.toLowerCase().includes(term);

  const walk = (node: ProjectTreeNode): ProjectTreeNode | null => {
    if (!node.children?.length) {
      return matcher(node.name) ? node : null;
    }

    const filteredChildren = node.children
      .map(walk)
      .filter((child): child is ProjectTreeNode => child !== null);

    if (filteredChildren.length > 0 || matcher(node.name)) {
      return { ...node, children: filteredChildren };
    }
    return null;
  };

  return nodes
    .map(walk)
    .filter((node): node is ProjectTreeNode => node !== null);
}

function filterTreeByExtension(nodes: ProjectTreeNode[], extensions: string[]): ProjectTreeNode[] {
  const matchesExtension = (name: string) =>
    extensions.some(ext => name.toLowerCase().endsWith(ext));

  const walk = (node: ProjectTreeNode): ProjectTreeNode | null => {
    if (node.is_dir) {
      const filteredChildren = (node.children ?? [])
        .map(walk)
        .filter((child): child is ProjectTreeNode => child !== null);
      if (filteredChildren.length > 0) {
        return { ...node, children: filteredChildren };
      }
      return null;
    }
    return matchesExtension(node.name) ? node : null;
  };

  return nodes
    .map(walk)
    .filter((node): node is ProjectTreeNode => node !== null);
}

function filterTreeByWarnings(nodes: ProjectTreeNode[]): ProjectTreeNode[] {
  const hasHighComplexity = (node: ProjectTreeNode): boolean => {
    if (!node.symbols) return false;
    return node.symbols.some(sym => {
      const c = sym.metrics?.complexity;
      return typeof c === "number" && c > 5;
    });
  };

  const walk = (node: ProjectTreeNode): ProjectTreeNode | null => {
    if (node.is_dir) {
      const filteredChildren = (node.children ?? [])
        .map(walk)
        .filter((child): child is ProjectTreeNode => child !== null);
      if (filteredChildren.length > 0) {
        return { ...node, children: filteredChildren };
      }
      return null;
    }
    return hasHighComplexity(node) ? node : null;
  };

  return nodes
    .map(walk)
    .filter((node): node is ProjectTreeNode => node !== null);
}

function getMaxComplexityInTree(node: ProjectTreeNode): number {
  if (!node.is_dir) {
    if (!node.symbols) return 0;
    return node.symbols.reduce((max, sym) => {
      const c = sym.metrics?.complexity;
      return typeof c === "number" && c > max ? c : max;
    }, 0);
  }

  return (node.children ?? []).reduce((max, child) => {
    const childMax = getMaxComplexityInTree(child);
    return childMax > max ? childMax : max;
  }, 0);
}
