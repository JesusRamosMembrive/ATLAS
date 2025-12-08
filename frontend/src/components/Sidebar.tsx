import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";

import { getTree } from "../api/client";
import { queryKeys } from "../api/queryKeys";
import type { ProjectTreeNode } from "../api/types";
import { useSelectionStore } from "../state/useSelectionStore";

const DIRECTORY_ICONS = ["📂", "📁"];
const FILE_ICON = "📄";

export function Sidebar({
  onShowDiff,
}: {
  onShowDiff?: (path: string) => void;
}): JSX.Element {
  const [filter, setFilter] = useState("");
  const clearSelection = useSelectionStore((state) => state.clearSelection);
  const selectedPath = useSelectionStore((state) => state.selectedPath);

  const { data, isLoading, isError, error } = useQuery({
    queryKey: queryKeys.tree,
    queryFn: getTree,
  });

  const nodes = useMemo(() => {
    const term = filter.trim().toLowerCase();
    const children = data?.children ?? [];
    if (!term) {
      return children;
    }
    return filterTree(children, term);
  }, [data, filter]);

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
      </div>

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

  // Complexity check
  const maxComplexity = useMemo(() => {
    if (isDirectory || !node.symbols) return 0;
    return node.symbols.reduce((max, sym) => {
      const c = sym.metrics?.complexity;
      if (typeof c === "number" && c > max) return c;
      return max;
    }, 0);
  }, [node.symbols, isDirectory]);

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
              <span className="badge">{node.children?.length ?? 0}</span>
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
