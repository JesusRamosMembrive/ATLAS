import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { getFileSummary } from "../api/client";
import { queryKeys } from "../api/queryKeys";
import type { SymbolInfo } from "../api/types";
import { useSelectionStore } from "../state/useSelectionStore";
import { PreviewPane } from "./PreviewPane";
import { TraceModal } from "./TraceModal";

interface ClassWithMethods {
  symbol: SymbolInfo;
  methods: SymbolInfo[];
}

interface GroupedSymbols {
  classes: ClassWithMethods[];
  functions: SymbolInfo[];
}

export function DetailPanel({
  onShowDiff,
}: {
  onShowDiff?: (path: string) => void;
}): JSX.Element {
  const selectedPath = useSelectionStore((state) => state.selectedPath);
  const [traceTarget, setTraceTarget] = useState<string | null>(null);

  const { data, isPending, isError, error } = useQuery({
    queryKey: queryKeys.file(selectedPath ?? ""),
    queryFn: () => getFileSummary(selectedPath!),
    enabled: Boolean(selectedPath),
  });

  const grouped = useMemo<GroupedSymbols>(() => {
    if (!data) {
      return { classes: [], functions: [] };
    }

    const classSymbols = data.symbols.filter((symbol) => symbol.kind === "class");
    const methodSymbols = data.symbols.filter((symbol) => symbol.kind === "method");
    const functionSymbols = data.symbols.filter(
      (symbol) => symbol.kind === "function"
    );

    const methodsMap = new Map<string, SymbolInfo[]>();
    for (const method of methodSymbols) {
      if (!method.parent) {
        continue;
      }
      const list = methodsMap.get(method.parent) ?? [];
      list.push(method);
      methodsMap.set(method.parent, list);
    }

    return {
      classes: classSymbols.map((cls) => ({
        symbol: cls,
        methods: (methodsMap.get(cls.name) ?? []).sort(
          (a, b) => a.lineno - b.lineno
        ),
      })),
      functions: functionSymbols.sort((a, b) => a.lineno - b.lineno),
    };
  }, [data]);

  if (!selectedPath) {
    return (
      <section className="panel">
        <div className="placeholder">
          <h3>Select a file</h3>
          <p>
            Click a file in the tree to see its classes, methods, and functions. Any docstrings you
            add will appear as descriptions.
          </p>
        </div>
      </section>
    );
  }

  if (isPending) {
    return (
      <section className="panel">
        <p style={{ color: "#7f869d" }}>
          Loading symbols for <strong>{selectedPath}</strong>…
        </p>
      </section>
    );
  }

  if (isError) {
    return (
      <section className="panel">
        <div className="error-banner">
          Error loading <strong>{selectedPath}</strong>:{" "}
          {(error as Error)?.message ?? "try again"}
        </div>
      </section>
    );
  }

  if (!data) {
    return (
      <section className="panel">
        <p style={{ color: "#7f869d" }}>
          No information available for <strong>{selectedPath}</strong>.
        </p>
      </section>
    );
  }

  const hasSymbols =
    grouped.classes.length > 0 || grouped.functions.length > 0;
  const showPreviewFirst = !hasSymbols;
  const showSymbolPlaceholder =
    !hasSymbols &&
    shouldShowSymbolPlaceholder(selectedPath, data.symbols.length);

  const modified =
    data.modified_at != null ? new Date(data.modified_at).toLocaleString() : "—";
  const hasWorkingChanges = Boolean(data.change_status);
  const changeLabel = formatChangeStatus(data.change_status);

  return (
    <section className="panel">
      <div className="detail-header">
        <div>
          <h2>{selectedPath}</h2>
          <div className="detail-meta">
            Last modified: {modified} · {data.symbols.length} symbols
          </div>
          {hasWorkingChanges && (
            <div className="detail-change-banner">
              <div className="detail-change-info">
                {changeLabel && <span className="detail-change-pill">{changeLabel}</span>}
                {data.change_summary && (
                  <span className="detail-change-summary">{data.change_summary}</span>
                )}
              </div>
              {onShowDiff && (
                <button
                  type="button"
                  className="detail-change-button"
                  onClick={() => onShowDiff(selectedPath)}
                >
                  View latest changes
                </button>
              )}
            </div>
          )}
        </div>
        {data.errors.length > 0 && (
          <span className="badge" style={{ background: "rgba(249, 115, 22, 0.18)", color: "#f9a84b" }}>
            {data.errors.length} errors
          </span>
        )}
      </div>

      {data.errors.length > 0 && (
        <div className="error-banner">
          {data.errors.map((issue, index) => (
            <div key={`${issue.message}-${index}`}>
              {issue.message}
              {issue.lineno != null ? ` · line ${issue.lineno}` : ""}
            </div>
          ))}
        </div>
      )}

      {grouped.classes.map(({ symbol, methods }) => (
        <article key={symbol.name} className="symbol-card" style={{
          borderLeft: "4px solid #9b59d5",
          background: "#1a1e2a"
        }}>
          <div className="symbol-title" style={{
            fontSize: "18px",
            fontWeight: 600,
            marginBottom: "12px",
            color: "#e4e6eb"
          }}>
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <span style={{ color: "#9b59d5" }}>class</span>
              {symbol.name}
            </div>
            <span className="symbol-meta" style={{ fontSize: "12px", fontWeight: 400 }}>
              <span>line {symbol.lineno}</span>
              <span>{methods.length} methods</span>
            </span>
          </div>
          {symbol.docstring && (
            <p className="symbol-doc" style={{
              fontSize: "14px",
              lineHeight: "1.6",
              marginBottom: "16px",
              color: "#b4b9c9",
              padding: "8px 12px",
              background: "#252b3a",
              borderRadius: "4px"
            }}>
              {formatDocstring(symbol.docstring)}
            </p>
          )}
          <div style={{
            marginTop: "16px",
            paddingTop: "12px",
            borderTop: "1px solid #2a2f3e"
          }}>
            <h4 style={{
              fontSize: "13px",
              color: "#7f869d",
              marginBottom: "12px",
              fontWeight: 500,
              textTransform: "uppercase",
              letterSpacing: "0.5px"
            }}>
              Methods
            </h4>
            <ul className="symbol-methods" style={{ listStyle: "none", padding: 0, margin: 0 }}>
              {methods.map((method) => (
                <li key={method.name} style={{
                  marginBottom: "12px",
                  padding: "12px",
                  background: "#252b3a",
                  borderRadius: "4px",
                  borderLeft: "3px solid #5b9bd5"
                }}>
                  <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: "12px" }}>
                    <div style={{ flex: 1 }}>
                      <div style={{
                        fontSize: "15px",
                        fontWeight: 500,
                        color: "#e4e6eb",
                        marginBottom: "6px",
                        fontFamily: "monospace"
                      }}>
                        {method.name}
                        <span style={{
                          fontSize: "12px",
                          color: "#7f869d",
                          fontWeight: 400,
                          marginLeft: "8px"
                        }}>
                          (line {method.lineno})
                        </span>
                      </div>
                      {method.docstring && (
                        <p style={{
                          fontSize: "13px",
                          color: "#9aa5b9",
                          margin: 0,
                          lineHeight: "1.5",
                          paddingLeft: "8px",
                          borderLeft: "2px solid #3a3f4e"
                        }}>
                          {formatDocstring(method.docstring)}
                        </p>
                      )}
                    </div>
                    <button
                      onClick={() => setTraceTarget(`${selectedPath}::${method.parent}.${method.name}`)}
                      style={{
                        padding: "4px 10px",
                        fontSize: "12px",
                        background: "#5b9bd5",
                        color: "#fff",
                        border: "none",
                        borderRadius: "4px",
                        cursor: "pointer",
                        flexShrink: 0,
                        fontWeight: 500
                      }}
                      title="Trace method calls"
                    >
                      Trace
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          </div>
        </article>
      ))}

      {grouped.functions.map((fn) => (
        <article key={fn.name} className="symbol-card">
          <div className="symbol-title">
            <div style={{ display: "flex", alignItems: "center", gap: "8px", flex: 1 }}>
              {fn.name}
              <button
                onClick={() => setTraceTarget(`${selectedPath}::${fn.name}`)}
                style={{
                  padding: "2px 8px",
                  fontSize: "11px",
                  background: "#5b9bd5",
                  color: "#fff",
                  border: "none",
                  borderRadius: "3px",
                  cursor: "pointer",
                }}
                title="Trace function calls"
              >
                Trace
              </button>
            </div>
            <span className="symbol-meta">
              <span>line {fn.lineno}</span>
              <span>function</span>
            </span>
          </div>
          {fn.docstring ? (
            <p className="symbol-doc">{formatDocstring(fn.docstring)}</p>
          ) : (
            <p className="symbol-doc" style={{ opacity: 0.65 }}>
              No docstring
            </p>
          )}
        </article>
      ))}

      {showPreviewFirst && (
        <div className="preview-container">
          <h3 className="preview-title">Preview</h3>
          <PreviewPane path={selectedPath} />
        </div>
      )}

      {showSymbolPlaceholder && (
        <div className="placeholder">
          <h3>File without exportable symbols</h3>
          <p>
            Add top-level functions or classes to visualize them here. Methods are automatically
            grouped under their class.
          </p>
        </div>
      )}

      {selectedPath && !showPreviewFirst && (
        <div className="preview-container">
          <h3 className="preview-title">Preview</h3>
          <PreviewPane path={selectedPath} />
        </div>
      )}

      {traceTarget && (
        <TraceModal
          qualifiedName={traceTarget}
          onClose={() => setTraceTarget(null)}
        />
      )}
    </section>
  );
}

function formatDocstring(docstring: string): string {
  return docstring.trim().split("\n\n")[0].replace(/\s+/g, " ");
}

function formatChangeStatus(status?: string | null): string {
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

const SYMBOL_FRIENDLY_EXTENSIONS = [
  "py",
  "ts",
  "tsx",
  "js",
  "jsx",
  "java",
  "go",
  "rb",
  "rs",
  "php",
  "cs",
  "cpp",
  "c",
  "m",
  "swift",
];

function shouldShowSymbolPlaceholder(path: string, symbolCount: number): boolean {
  if (symbolCount > 0) {
    return false;
  }
  const normalized = path.toLowerCase();
  return SYMBOL_FRIENDLY_EXTENSIONS.some((ext) =>
    normalized.endsWith(`.${ext}`)
  );
}
