import { useState, useMemo } from "react";

import { useCallFlowEntryPointsQuery, useCallFlowQuery } from "../hooks/useCallFlowQuery";
import { CallFlowGraph } from "./call-flow/CallFlowGraph";
import { FileBrowserModal } from "./settings/FileBrowserModal";
import type { CallFlowEntryPoint } from "../api/types";

export function CallFlowView(): JSX.Element {
  const [filePath, setFilePath] = useState("");
  const [inputValue, setInputValue] = useState("");
  const [selectedFunction, setSelectedFunction] = useState<CallFlowEntryPoint | null>(null);
  const [maxDepth, setMaxDepth] = useState(5);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [selectedEdgeId, setSelectedEdgeId] = useState<string | null>(null);
  const [isBrowseModalOpen, setIsBrowseModalOpen] = useState(false);

  // Query entry points when file is selected
  const entryPointsQuery = useCallFlowEntryPointsQuery({
    filePath,
    enabled: !!filePath,
  });

  // Query call flow when function is selected
  const callFlowQuery = useCallFlowQuery({
    filePath,
    functionName: selectedFunction?.name || "",
    maxDepth,
    className: selectedFunction?.class_name,
    enabled: !!filePath && !!selectedFunction,
  });

  const handleFileSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    const trimmed = inputValue.trim();
    if (trimmed) {
      setFilePath(trimmed);
      setSelectedFunction(null);
    }
  };

  const handleBrowseSelect = (path: string) => {
    setInputValue(path);
    setFilePath(path);
    setSelectedFunction(null);
  };

  const handleFunctionSelect = (ep: CallFlowEntryPoint) => {
    setSelectedFunction(ep);
    setSelectedNodeId(null);
    setSelectedEdgeId(null);
  };

  const nodes = useMemo(() => callFlowQuery.data?.nodes || [], [callFlowQuery.data?.nodes]);
  const edges = useMemo(() => callFlowQuery.data?.edges || [], [callFlowQuery.data?.edges]);
  const metadata = callFlowQuery.data?.metadata;

  const entryPoints = entryPointsQuery.data?.entry_points || [];

  // Group entry points by class
  const groupedEntryPoints = useMemo(() => {
    const functions: CallFlowEntryPoint[] = [];
    const methods: Map<string, CallFlowEntryPoint[]> = new Map();

    for (const ep of entryPoints) {
      if (ep.class_name) {
        const existing = methods.get(ep.class_name) || [];
        existing.push(ep);
        methods.set(ep.class_name, existing);
      } else {
        functions.push(ep);
      }
    }

    return { functions, methods };
  }, [entryPoints]);

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "calc(100vh - 200px)",
        minHeight: "500px",
        backgroundColor: "#0f172a",
        color: "#f1f5f9",
      }}
    >
      {/* Header Controls */}
      <div
        style={{
          padding: "16px 24px",
          borderBottom: "1px solid #334155",
          backgroundColor: "#1e293b",
        }}
      >
        <form onSubmit={handleFileSubmit} style={{ display: "flex", gap: "12px", alignItems: "center" }}>
          <label htmlFor="file-path" style={{ fontSize: "14px", fontWeight: 500 }}>
            Python File:
          </label>
          <input
            id="file-path"
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            placeholder="/path/to/file.py"
            style={{
              flex: 1,
              padding: "8px 12px",
              borderRadius: "6px",
              border: "1px solid #334155",
              backgroundColor: "#0f172a",
              color: "#f1f5f9",
              fontSize: "14px",
            }}
          />
          <button
            type="button"
            onClick={() => setIsBrowseModalOpen(true)}
            style={{
              padding: "8px 16px",
              borderRadius: "6px",
              border: "1px solid #334155",
              backgroundColor: "#1e293b",
              color: "#f1f5f9",
              fontSize: "14px",
              fontWeight: 500,
              cursor: "pointer",
            }}
          >
            Browse
          </button>
          <button
            type="submit"
            disabled={entryPointsQuery.isFetching}
            style={{
              padding: "8px 16px",
              borderRadius: "6px",
              border: "none",
              backgroundColor: "#3b82f6",
              color: "#fff",
              fontSize: "14px",
              fontWeight: 500,
              cursor: entryPointsQuery.isFetching ? "not-allowed" : "pointer",
              opacity: entryPointsQuery.isFetching ? 0.6 : 1,
            }}
          >
            {entryPointsQuery.isFetching ? "Loading..." : "Load"}
          </button>
        </form>

        {/* Depth Control */}
        {selectedFunction && (
          <div style={{ marginTop: "12px", display: "flex", gap: "12px", alignItems: "center" }}>
            <label htmlFor="max-depth" style={{ fontSize: "14px", fontWeight: 500 }}>
              Max Depth:
            </label>
            <input
              id="max-depth"
              type="range"
              min={1}
              max={10}
              value={maxDepth}
              onChange={(e) => setMaxDepth(Number(e.target.value))}
              style={{ width: "120px" }}
            />
            <span style={{ fontSize: "14px", color: "#94a3b8", minWidth: "24px" }}>{maxDepth}</span>
          </div>
        )}

        {/* Stats Panel */}
        {metadata && !callFlowQuery.isLoading && !callFlowQuery.isError && (
          <div
            style={{
              display: "flex",
              gap: "24px",
              marginTop: "12px",
              padding: "12px",
              backgroundColor: "#0f172a",
              borderRadius: "6px",
              border: "1px solid #334155",
              flexWrap: "wrap",
            }}
          >
            <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
              <span style={{ fontSize: "11px", color: "#94a3b8", textTransform: "uppercase" }}>
                Entry Point
              </span>
              <strong style={{ fontSize: "14px", color: "#f59e0b" }}>{metadata.entry_point}</strong>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
              <span style={{ fontSize: "11px", color: "#94a3b8", textTransform: "uppercase" }}>
                Max Depth
              </span>
              <strong style={{ fontSize: "14px" }}>
                {metadata.max_depth}
                {metadata.max_depth_reached && (
                  <span style={{ color: "#f59e0b", marginLeft: "4px" }}>(reached)</span>
                )}
              </strong>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
              <span style={{ fontSize: "11px", color: "#94a3b8", textTransform: "uppercase" }}>
                Nodes
              </span>
              <strong style={{ fontSize: "14px", color: "#3b82f6" }}>
                {metadata.node_count}
              </strong>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
              <span style={{ fontSize: "11px", color: "#94a3b8", textTransform: "uppercase" }}>
                Edges
              </span>
              <strong style={{ fontSize: "14px", color: "#a855f7" }}>
                {metadata.edge_count}
              </strong>
            </div>
            {metadata.external_calls_count > 0 && (
              <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
                <span style={{ fontSize: "11px", color: "#94a3b8", textTransform: "uppercase" }}>
                  External Calls
                </span>
                <strong style={{ fontSize: "14px", color: "#6b7280" }}>
                  {metadata.external_calls_count}
                </strong>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Main Content */}
      <div style={{ flex: 1, display: "flex", position: "relative", minHeight: 0 }}>
        {/* Entry Points Sidebar */}
        {filePath && entryPoints.length > 0 && (
          <div
            style={{
              width: "280px",
              borderRight: "1px solid #334155",
              backgroundColor: "#1e293b",
              overflow: "auto",
            }}
          >
            <div style={{ padding: "12px 16px", borderBottom: "1px solid #334155" }}>
              <h3 style={{ margin: 0, fontSize: "14px", fontWeight: 600 }}>Entry Points</h3>
              <p style={{ margin: "4px 0 0", fontSize: "12px", color: "#94a3b8" }}>
                Select a function to visualize
              </p>
            </div>

            {/* Functions */}
            {groupedEntryPoints.functions.length > 0 && (
              <div style={{ padding: "8px 0" }}>
                <div style={{ padding: "4px 16px", fontSize: "11px", color: "#64748b", textTransform: "uppercase" }}>
                  Functions
                </div>
                {groupedEntryPoints.functions.map((ep) => (
                  <button
                    key={ep.qualified_name}
                    onClick={() => handleFunctionSelect(ep)}
                    style={{
                      display: "block",
                      width: "100%",
                      padding: "8px 16px",
                      textAlign: "left",
                      border: "none",
                      backgroundColor: selectedFunction?.qualified_name === ep.qualified_name ? "#334155" : "transparent",
                      color: "#f1f5f9",
                      cursor: "pointer",
                      fontSize: "13px",
                    }}
                  >
                    <div style={{ fontWeight: 500 }}>{ep.name}</div>
                    <div style={{ fontSize: "11px", color: "#64748b" }}>Line {ep.line}</div>
                  </button>
                ))}
              </div>
            )}

            {/* Methods by class */}
            {Array.from(groupedEntryPoints.methods.entries()).map(([className, methods]) => (
              <div key={className} style={{ padding: "8px 0" }}>
                <div style={{ padding: "4px 16px", fontSize: "11px", color: "#a855f7", textTransform: "uppercase" }}>
                  {className}
                </div>
                {methods.map((ep) => (
                  <button
                    key={ep.qualified_name}
                    onClick={() => handleFunctionSelect(ep)}
                    style={{
                      display: "block",
                      width: "100%",
                      padding: "8px 16px",
                      textAlign: "left",
                      border: "none",
                      backgroundColor: selectedFunction?.qualified_name === ep.qualified_name ? "#334155" : "transparent",
                      color: "#f1f5f9",
                      cursor: "pointer",
                      fontSize: "13px",
                    }}
                  >
                    <div style={{ fontWeight: 500 }}>{ep.name}</div>
                    <div style={{ fontSize: "11px", color: "#64748b" }}>Line {ep.line}</div>
                  </button>
                ))}
              </div>
            ))}
          </div>
        )}

        {/* Graph Canvas */}
        <div style={{ flex: 1, position: "relative", height: "100%" }}>
          {entryPointsQuery.isLoading && (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                height: "100%",
                fontSize: "16px",
                color: "#94a3b8",
              }}
            >
              Loading entry points...
            </div>
          )}

          {callFlowQuery.isLoading && (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                height: "100%",
                fontSize: "16px",
                color: "#94a3b8",
              }}
            >
              Analyzing call flow...
            </div>
          )}

          {(entryPointsQuery.isError || callFlowQuery.isError) && (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                height: "100%",
                flexDirection: "column",
                gap: "8px",
              }}
            >
              <div style={{ fontSize: "16px", color: "#ef4444", fontWeight: 500 }}>
                Error loading call flow
              </div>
              <div style={{ fontSize: "14px", color: "#94a3b8" }}>
                {entryPointsQuery.error?.message || callFlowQuery.error?.message || "Unknown error"}
              </div>
            </div>
          )}

          {!entryPointsQuery.isLoading && !entryPointsQuery.isError && !filePath && (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                height: "100%",
                flexDirection: "column",
                gap: "12px",
              }}
            >
              <div style={{ fontSize: "24px" }}>🔄</div>
              <div style={{ fontSize: "16px", color: "#94a3b8" }}>
                Enter a Python file path to analyze call flows
              </div>
              <div style={{ fontSize: "14px", color: "#64748b" }}>
                Select an entry point to see the function call chain
              </div>
            </div>
          )}

          {filePath && !selectedFunction && entryPoints.length > 0 && !entryPointsQuery.isLoading && (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                height: "100%",
                flexDirection: "column",
                gap: "8px",
              }}
            >
              <div style={{ fontSize: "24px" }}>👈</div>
              <div style={{ fontSize: "16px", color: "#94a3b8" }}>
                Select a function from the sidebar
              </div>
            </div>
          )}

          {filePath && entryPoints.length === 0 && !entryPointsQuery.isLoading && !entryPointsQuery.isError && (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                height: "100%",
                flexDirection: "column",
                gap: "8px",
              }}
            >
              <div style={{ fontSize: "16px", color: "#f59e0b" }}>
                No functions found in this file
              </div>
              <div style={{ fontSize: "14px", color: "#94a3b8" }}>
                Make sure the file contains Python function definitions
              </div>
            </div>
          )}

          {!callFlowQuery.isLoading && !callFlowQuery.isError && nodes.length > 0 && (
            <div style={{ position: "absolute", top: 0, left: 0, right: 0, bottom: 0 }}>
              <CallFlowGraph
                nodes={nodes}
                edges={edges}
                onNodeSelect={setSelectedNodeId}
                onEdgeSelect={setSelectedEdgeId}
              />
            </div>
          )}
        </div>

        {/* Selected Node Details */}
        {selectedNodeId && nodes.length > 0 && (
          <div
            style={{
              width: "300px",
              borderLeft: "1px solid #334155",
              backgroundColor: "#1e293b",
              padding: "16px",
              overflow: "auto",
            }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "16px" }}>
              <h3 style={{ margin: 0, fontSize: "14px", fontWeight: 600 }}>Node Details</h3>
              <button
                onClick={() => setSelectedNodeId(null)}
                style={{
                  border: "none",
                  background: "transparent",
                  color: "#94a3b8",
                  cursor: "pointer",
                  fontSize: "18px",
                }}
              >
                ×
              </button>
            </div>
            {(() => {
              const node = nodes.find((n) => n.id === selectedNodeId);
              if (!node) return null;
              return (
                <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                  <div>
                    <div style={{ fontSize: "11px", color: "#64748b", textTransform: "uppercase" }}>Name</div>
                    <div style={{ fontSize: "14px", fontWeight: 500 }}>{node.data.label}</div>
                  </div>
                  <div>
                    <div style={{ fontSize: "11px", color: "#64748b", textTransform: "uppercase" }}>Qualified Name</div>
                    <div style={{ fontSize: "13px", fontFamily: "monospace" }}>{node.data.qualifiedName}</div>
                  </div>
                  <div>
                    <div style={{ fontSize: "11px", color: "#64748b", textTransform: "uppercase" }}>Kind</div>
                    <div style={{ fontSize: "14px" }}>{node.data.kind}</div>
                  </div>
                  {node.data.filePath && (
                    <div>
                      <div style={{ fontSize: "11px", color: "#64748b", textTransform: "uppercase" }}>Location</div>
                      <div style={{ fontSize: "12px", fontFamily: "monospace" }}>
                        {node.data.filePath}:{node.data.line}
                      </div>
                    </div>
                  )}
                  {node.data.docstring && (
                    <div>
                      <div style={{ fontSize: "11px", color: "#64748b", textTransform: "uppercase" }}>Docstring</div>
                      <div style={{ fontSize: "12px", color: "#94a3b8", whiteSpace: "pre-wrap" }}>
                        {node.data.docstring}
                      </div>
                    </div>
                  )}
                </div>
              );
            })()}
          </div>
        )}
      </div>

      {/* File Browser Modal */}
      <FileBrowserModal
        isOpen={isBrowseModalOpen}
        currentPath={inputValue || "/home"}
        extensions=".py"
        onClose={() => setIsBrowseModalOpen(false)}
        onSelect={handleBrowseSelect}
      />
    </div>
  );
}
