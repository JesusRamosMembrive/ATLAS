import { useState, useMemo, useEffect, useCallback } from "react";

import { useCallFlowEntryPointsQuery, useCallFlowQuery, useExpandBranchMutation } from "../hooks/useCallFlowQuery";
import { useSettingsQuery } from "../hooks/useSettingsQuery";
import { CallFlowGraph } from "./call-flow/CallFlowGraph";
import { FileBrowserModal } from "./settings/FileBrowserModal";
import { getCallFlowSource } from "../api/client";
import type { CallFlowEntryPoint, CallFlowNode, CallFlowEdge, CallFlowDecisionNode, CallFlowReturnNode } from "../api/types";
import { DESIGN_TOKENS } from "../theme/designTokens";

const { colors, borders } = DESIGN_TOKENS;

export function CallFlowView(): JSX.Element {
  // Get project root from settings
  const settingsQuery = useSettingsQuery();
  const projectRoot = settingsQuery.data?.absolute_root || "";

  const [filePath, setFilePath] = useState("");
  const [inputValue, setInputValue] = useState("");

  // Initialize inputValue with project root when settings load
  useEffect(() => {
    if (projectRoot && !inputValue) {
      setInputValue(projectRoot);
    }
  }, [projectRoot, inputValue]);
  const [selectedFunction, setSelectedFunction] = useState<CallFlowEntryPoint | null>(null);
  const [maxDepth, setMaxDepth] = useState(5);
  const [minCalls, setMinCalls] = useState(0);
  const [includeExternal, setIncludeExternal] = useState(true); // Show external calls by default
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [selectedEdgeId, setSelectedEdgeId] = useState<string | null>(null);
  const [isBrowseModalOpen, setIsBrowseModalOpen] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [nodeSourceCode, setNodeSourceCode] = useState<string | null>(null);
  const [sourceCodeLoading, setSourceCodeLoading] = useState(false);

  // State for incrementally expanded branches (merged with initial query data)
  const [expandedNodes, setExpandedNodes] = useState<CallFlowNode[]>([]);
  const [expandedEdges, setExpandedEdges] = useState<CallFlowEdge[]>([]);
  const [expandedDecisionNodes, setExpandedDecisionNodes] = useState<CallFlowDecisionNode[]>([]);
  const [expandedReturnNodes, setExpandedReturnNodes] = useState<CallFlowReturnNode[]>([]);
  // Track which branches have been loaded (fetched from API)
  const [loadedBranchIds, setLoadedBranchIds] = useState<Set<string>>(new Set());
  // Track which branches are currently visible (can toggle on/off)
  const [visibleBranchIds, setVisibleBranchIds] = useState<Set<string>>(new Set());
  // Cache: maps branchId -> { nodes, edges, decisionNodes, returnNodes } for toggle functionality
  const [branchDataCache, setBranchDataCache] = useState<Map<string, {
    nodes: CallFlowNode[];
    edges: CallFlowEdge[];
    decisionNodes: CallFlowDecisionNode[];
    returnNodes: CallFlowReturnNode[];
  }>>(new Map());

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
    includeExternal,
    enabled: !!filePath && !!selectedFunction,
  });

  // Mutation for expanding branches
  const expandBranchMutation = useExpandBranchMutation({
    filePath,
    functionName: selectedFunction?.name || "",
    maxDepth,
    includeExternal,
    onSuccess: (data) => {
      const branchId = data.expanded_branch_id;

      // Cache the data for this branch (for toggle functionality)
      setBranchDataCache((prev) => {
        const newCache = new Map(prev);
        newCache.set(branchId, {
          nodes: data.new_nodes,
          edges: data.new_edges,
          decisionNodes: data.new_decision_nodes,
          returnNodes: data.new_return_nodes || [],
        });
        return newCache;
      });

      // Merge new nodes (avoiding duplicates by id)
      setExpandedNodes((prev) => {
        const existingIds = new Set(prev.map((n) => n.id));
        const newNodes = data.new_nodes.filter((n) => !existingIds.has(n.id));
        return [...prev, ...newNodes];
      });

      // Merge new edges (avoiding duplicates by id)
      setExpandedEdges((prev) => {
        const existingIds = new Set(prev.map((e) => e.id));
        const newEdges = data.new_edges.filter((e) => !existingIds.has(e.id));
        return [...prev, ...newEdges];
      });

      // Merge new decision nodes (avoiding duplicates by id)
      setExpandedDecisionNodes((prev) => {
        const existingIds = new Set(prev.map((d) => d.id));
        const newDecisions = data.new_decision_nodes.filter((d) => !existingIds.has(d.id));
        return [...prev, ...newDecisions];
      });

      // Merge new return nodes (avoiding duplicates by id)
      setExpandedReturnNodes((prev) => {
        const existingIds = new Set(prev.map((r) => r.id));
        const newReturns = (data.new_return_nodes || []).filter((r) => !existingIds.has(r.id));
        return [...prev, ...newReturns];
      });

      // Mark branch as loaded and visible
      setLoadedBranchIds((prev) => new Set([...prev, branchId]));
      setVisibleBranchIds((prev) => new Set([...prev, branchId]));
    },
    onError: (error) => {
      console.error("Failed to expand branch:", error);
    },
  });

  // Handler for branch toggle (expand/collapse) from decision nodes
  const handleBranchToggle = useCallback(
    (branchId: string) => {
      // If already visible, collapse it (hide nodes)
      if (visibleBranchIds.has(branchId)) {
        setVisibleBranchIds((prev) => {
          const newSet = new Set(prev);
          newSet.delete(branchId);
          return newSet;
        });
        return;
      }

      // If already loaded but not visible, just show it
      if (loadedBranchIds.has(branchId)) {
        setVisibleBranchIds((prev) => new Set([...prev, branchId]));
        return;
      }

      // Not loaded yet, fetch from API
      if (!expandBranchMutation.isPending) {
        expandBranchMutation.mutate(branchId);
      }
    },
    [visibleBranchIds, loadedBranchIds, expandBranchMutation]
  );

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
    // Reset expansion state when selecting a new function
    setExpandedNodes([]);
    setExpandedEdges([]);
    setExpandedDecisionNodes([]);
    setExpandedReturnNodes([]);
    setLoadedBranchIds(new Set());
    setVisibleBranchIds(new Set());
    setBranchDataCache(new Map());
  };

  // Compute visible nodes from branches that are currently expanded
  const visibleBranchNodes = useMemo(() => {
    const nodeIds = new Set<string>();
    for (const branchId of visibleBranchIds) {
      const cached = branchDataCache.get(branchId);
      if (cached) {
        cached.nodes.forEach((n) => nodeIds.add(n.id));
      }
    }
    return nodeIds;
  }, [visibleBranchIds, branchDataCache]);

  const visibleBranchEdges = useMemo(() => {
    const edgeIds = new Set<string>();
    for (const branchId of visibleBranchIds) {
      const cached = branchDataCache.get(branchId);
      if (cached) {
        cached.edges.forEach((e) => edgeIds.add(e.id));
      }
    }
    return edgeIds;
  }, [visibleBranchIds, branchDataCache]);

  const visibleBranchDecisionNodes = useMemo(() => {
    const decisionIds = new Set<string>();
    for (const branchId of visibleBranchIds) {
      const cached = branchDataCache.get(branchId);
      if (cached) {
        cached.decisionNodes.forEach((d) => decisionIds.add(d.id));
      }
    }
    return decisionIds;
  }, [visibleBranchIds, branchDataCache]);

  const visibleBranchReturnNodes = useMemo(() => {
    const returnIds = new Set<string>();
    for (const branchId of visibleBranchIds) {
      const cached = branchDataCache.get(branchId);
      if (cached) {
        cached.returnNodes.forEach((r) => returnIds.add(r.id));
      }
    }
    return returnIds;
  }, [visibleBranchIds, branchDataCache]);

  // Combine initial query data with visible expanded data
  const nodes = useMemo(() => {
    const initial = callFlowQuery.data?.nodes || [];
    const initialIds = new Set(initial.map((n) => n.id));
    // Only include expanded nodes that are in a visible branch
    const uniqueExpanded = expandedNodes.filter(
      (n) => !initialIds.has(n.id) && visibleBranchNodes.has(n.id)
    );
    return [...initial, ...uniqueExpanded];
  }, [callFlowQuery.data?.nodes, expandedNodes, visibleBranchNodes]);

  const edges = useMemo(() => {
    const initial = callFlowQuery.data?.edges || [];
    const initialIds = new Set(initial.map((e) => e.id));
    // Only include expanded edges that are in a visible branch
    const uniqueExpanded = expandedEdges.filter(
      (e) => !initialIds.has(e.id) && visibleBranchEdges.has(e.id)
    );
    return [...initial, ...uniqueExpanded];
  }, [callFlowQuery.data?.edges, expandedEdges, visibleBranchEdges]);

  const decisionNodes = useMemo(() => {
    const initial = callFlowQuery.data?.decision_nodes || [];
    const initialIds = new Set(initial.map((d) => d.id));
    // Only include expanded decision nodes that are in a visible branch
    const uniqueExpanded = expandedDecisionNodes.filter(
      (d) => !initialIds.has(d.id) && visibleBranchDecisionNodes.has(d.id)
    );
    // Mark branches based on visibility state (not just loaded state)
    const allDecisions = [...initial, ...uniqueExpanded];
    return allDecisions.map((dn) => ({
      ...dn,
      data: {
        ...dn.data,
        branches: dn.data.branches.map((branch) => ({
          ...branch,
          // is_expanded now means "currently visible"
          is_expanded: visibleBranchIds.has(branch.branch_id),
          // is_loaded indicates if data has been fetched (for UI feedback)
          is_loaded: loadedBranchIds.has(branch.branch_id),
        })),
      },
    }));
  }, [callFlowQuery.data?.decision_nodes, expandedDecisionNodes, visibleBranchDecisionNodes, visibleBranchIds, loadedBranchIds]);

  const returnNodes = useMemo(() => {
    const initial = callFlowQuery.data?.return_nodes || [];
    const initialIds = new Set(initial.map((r) => r.id));
    // Only include expanded return nodes that are in a visible branch
    const uniqueExpanded = expandedReturnNodes.filter(
      (r) => !initialIds.has(r.id) && visibleBranchReturnNodes.has(r.id)
    );
    return [...initial, ...uniqueExpanded];
  }, [callFlowQuery.data?.return_nodes, expandedReturnNodes, visibleBranchReturnNodes]);

  const metadata = callFlowQuery.data?.metadata;

  const entryPoints = entryPointsQuery.data?.entry_points || [];

  // Calculate max node_count for slider range
  const maxNodeCount = useMemo(() => {
    return Math.max(0, ...entryPoints.map((ep) => ep.node_count ?? 0));
  }, [entryPoints]);

  // Filter entry points by minimum calls
  const filteredEntryPoints = useMemo(() => {
    if (minCalls === 0) return entryPoints;
    return entryPoints.filter((ep) => (ep.node_count ?? 0) >= minCalls);
  }, [entryPoints, minCalls]);

  // Group entry points by class
  const groupedEntryPoints = useMemo(() => {
    const functions: CallFlowEntryPoint[] = [];
    const methods: Map<string, CallFlowEntryPoint[]> = new Map();

    for (const ep of filteredEntryPoints) {
      if (ep.class_name) {
        const existing = methods.get(ep.class_name) || [];
        existing.push(ep);
        methods.set(ep.class_name, existing);
      } else {
        functions.push(ep);
      }
    }

    return { functions, methods };
  }, [filteredEntryPoints]);

  // Load source code when a node is selected
  useEffect(() => {
    const selectedNode = nodes.find((n) => n.id === selectedNodeId);
    const nodeFilePath = selectedNode?.data.filePath;
    const nodeLine = selectedNode?.data.line;

    if (!nodeFilePath || !nodeLine) {
      setNodeSourceCode(null);
      return;
    }

    const loadSourceCode = async () => {
      setSourceCodeLoading(true);
      try {
        // First, get a chunk of code starting from the function line
        const startLine = nodeLine;
        const maxLinesToFetch = 60; // Fetch extra to determine function boundaries

        const content = await getCallFlowSource(
          nodeFilePath,
          startLine,
          startLine + maxLinesToFetch
        );

        const lines = content.split("\n");

        // Find the function end by looking for the next function/class definition
        // or end of file
        let endIdx = lines.length;
        const indent = lines[0]?.match(/^(\s*)/)?.[1]?.length ?? 0;

        for (let i = 1; i < lines.length; i++) {
          const line = lines[i];
          if (!line) continue;

          // Check if we hit a new definition at same or lower indent level
          const lineIndent = line.match(/^(\s*)/)?.[1]?.length ?? 0;
          const isDefinition = /^\s*(def |class |async def )/.test(line);

          if (isDefinition && lineIndent <= indent) {
            endIdx = i;
            break;
          }
        }

        // Limit to 40 lines max for display
        const maxDisplayLines = 40;
        const actualEndIdx = Math.min(endIdx, maxDisplayLines);
        const codeLines = lines.slice(0, actualEndIdx);

        setNodeSourceCode(codeLines.join("\n"));
      } catch (err) {
        console.error("Failed to load source code:", err);
        setNodeSourceCode(null);
      } finally {
        setSourceCodeLoading(false);
      }
    };

    loadSourceCode();
  }, [selectedNodeId, nodes]);

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "calc(100vh - 200px)",
        minHeight: "500px",
        backgroundColor: colors.base.panel,
        color: colors.text.secondary,
      }}
    >
      {/* Header Controls */}
      <div
        style={{
          padding: "16px 24px",
          borderBottom: `1px solid ${borders.default}`,
          backgroundColor: colors.base.card,
        }}
      >
        <form onSubmit={handleFileSubmit} style={{ display: "flex", gap: "12px", alignItems: "center" }}>
          <label htmlFor="file-path" style={{ fontSize: "14px", fontWeight: 500 }}>
            Source File:
          </label>
          <input
            id="file-path"
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            placeholder="/path/to/file.py, .ts, .cpp, etc."
            style={{
              flex: 1,
              padding: "8px 12px",
              borderRadius: "6px",
              border: `1px solid ${borders.default}`,
              backgroundColor: colors.base.panel,
              color: colors.text.secondary,
              fontSize: "14px",
            }}
          />
          <button
            type="button"
            onClick={() => setIsBrowseModalOpen(true)}
            style={{
              padding: "8px 16px",
              borderRadius: "6px",
              border: `1px solid ${borders.default}`,
              backgroundColor: colors.base.card,
              color: colors.text.secondary,
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
              backgroundColor: colors.primary.main,
              color: colors.contrast.light,
              fontSize: "14px",
              fontWeight: 500,
              cursor: entryPointsQuery.isFetching ? "not-allowed" : "pointer",
              opacity: entryPointsQuery.isFetching ? 0.6 : 1,
            }}
          >
            {entryPointsQuery.isFetching ? "Loading..." : "Load"}
          </button>
        </form>

        {/* Controls Row */}
        {filePath && entryPoints.length > 0 && (
          <div style={{ marginTop: "12px", display: "flex", gap: "24px", alignItems: "center", flexWrap: "wrap" }}>
            {/* Max Depth Slider */}
            {selectedFunction && (
              <div style={{ display: "flex", gap: "12px", alignItems: "center" }}>
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
                <span style={{ fontSize: "14px", color: colors.text.muted, minWidth: "24px" }}>{maxDepth}</span>
              </div>
            )}

            {/* Min Calls Slider */}
            <div style={{ display: "flex", gap: "12px", alignItems: "center" }}>
              <label htmlFor="min-calls" style={{ fontSize: "14px", fontWeight: 500 }}>
                Min Calls:
              </label>
              <input
                id="min-calls"
                type="range"
                min={0}
                max={Math.max(maxNodeCount, 10)}
                value={minCalls}
                onChange={(e) => setMinCalls(Number(e.target.value))}
                style={{ width: "120px" }}
              />
              <span style={{ fontSize: "14px", color: colors.text.muted, minWidth: "24px" }}>{minCalls}</span>
              <span style={{ fontSize: "12px", color: colors.gray[500] }}>
                ({filteredEntryPoints.length}/{entryPoints.length} shown)
              </span>
            </div>

            {/* Include External Toggle */}
            {selectedFunction && (
              <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                <label
                  htmlFor="include-external"
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                    fontSize: "14px",
                    fontWeight: 500,
                    cursor: "pointer",
                  }}
                >
                  <input
                    id="include-external"
                    type="checkbox"
                    checked={includeExternal}
                    onChange={(e) => setIncludeExternal(e.target.checked)}
                    style={{
                      width: "16px",
                      height: "16px",
                      accentColor: colors.primary.main,
                      cursor: "pointer",
                    }}
                  />
                  Show External Calls
                </label>
                <span
                  style={{
                    fontSize: "11px",
                    color: colors.gray[500],
                    padding: "2px 6px",
                    backgroundColor: borders.default,
                    borderRadius: "4px",
                  }}
                  title="Include stdlib, builtins, and third-party calls as gray/amber leaf nodes"
                >
                  ?
                </span>
              </div>
            )}
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
              backgroundColor: colors.base.panel,
              borderRadius: "6px",
              border: `1px solid ${borders.default}`,
              flexWrap: "wrap",
            }}
          >
            <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
              <span style={{ fontSize: "11px", color: colors.text.muted, textTransform: "uppercase" }}>
                Entry Point
              </span>
              <strong style={{ fontSize: "14px", color: colors.callFlow.entryPoint }}>{metadata.entry_point}</strong>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
              <span style={{ fontSize: "11px", color: colors.text.muted, textTransform: "uppercase" }}>
                Max Depth
              </span>
              <strong style={{ fontSize: "14px" }}>
                {metadata.max_depth}
                {metadata.max_depth_reached && (
                  <span style={{ color: colors.callFlow.entryPoint, marginLeft: "4px" }}>(reached)</span>
                )}
              </strong>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
              <span style={{ fontSize: "11px", color: colors.text.muted, textTransform: "uppercase" }}>
                Nodes
              </span>
              <strong style={{ fontSize: "14px", color: colors.primary.main }}>
                {metadata.node_count}
              </strong>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
              <span style={{ fontSize: "11px", color: colors.text.muted, textTransform: "uppercase" }}>
                Edges
              </span>
              <strong style={{ fontSize: "14px", color: colors.callFlow.class }}>
                {metadata.edge_count}
              </strong>
            </div>
            {metadata.external_calls_count > 0 && (
              <div style={{ display: "flex", flexDirection: "column", gap: "2px" }}>
                <span style={{ fontSize: "11px", color: colors.text.muted, textTransform: "uppercase" }}>
                  External Calls
                </span>
                <strong style={{ fontSize: "14px", color: colors.callFlow.external }}>
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
              width: sidebarCollapsed ? "48px" : "280px",
              borderRight: `1px solid ${borders.default}`,
              backgroundColor: colors.base.card,
              overflow: "auto",
              transition: "width 0.2s ease-in-out",
              flexShrink: 0,
            }}
          >
            <div style={{
              padding: sidebarCollapsed ? "12px 8px" : "12px 16px",
              borderBottom: `1px solid ${borders.default}`,
              display: "flex",
              alignItems: "center",
              justifyContent: sidebarCollapsed ? "center" : "space-between",
              gap: "8px",
            }}>
              {!sidebarCollapsed && (
                <div>
                  <h3 style={{ margin: 0, fontSize: "14px", fontWeight: 600 }}>Entry Points</h3>
                  <p style={{ margin: "4px 0 0", fontSize: "12px", color: colors.text.muted }}>
                    Select a function to visualize
                  </p>
                </div>
              )}
              <button
                onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
                title={sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"}
                style={{
                  border: "none",
                  background: "transparent",
                  color: colors.text.muted,
                  cursor: "pointer",
                  fontSize: "16px",
                  padding: "4px",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  borderRadius: "4px",
                  transition: "background-color 0.15s",
                }}
                onMouseEnter={(e) => (e.currentTarget.style.backgroundColor = borders.default)}
                onMouseLeave={(e) => (e.currentTarget.style.backgroundColor = "transparent")}
              >
                {sidebarCollapsed ? "»" : "«"}
              </button>
            </div>

            {/* Functions - hidden when collapsed */}
            {!sidebarCollapsed && groupedEntryPoints.functions.length > 0 && (
              <div style={{ padding: "8px 0" }}>
                <div style={{ padding: "4px 16px", fontSize: "11px", color: colors.gray[500], textTransform: "uppercase" }}>
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
                      backgroundColor: selectedFunction?.qualified_name === ep.qualified_name ? borders.default : "transparent",
                      color: colors.text.secondary,
                      cursor: "pointer",
                      fontSize: "13px",
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                      <span style={{ fontWeight: 500 }}>{ep.name}</span>
                      {ep.node_count != null && ep.node_count > 0 && (
                        <span
                          style={{
                            fontSize: "10px",
                            padding: "2px 6px",
                            borderRadius: "10px",
                            backgroundColor: ep.node_count > 10 ? colors.severity.danger : ep.node_count > 5 ? colors.severity.warning : colors.severity.info,
                            color: colors.contrast.light,
                            fontWeight: 600,
                          }}
                          title={`${ep.node_count} calls in this function`}
                        >
                          {ep.node_count}
                        </span>
                      )}
                    </div>
                    <div style={{ fontSize: "11px", color: colors.gray[500] }}>Line {ep.line}</div>
                  </button>
                ))}
              </div>
            )}

            {/* Methods by class - hidden when collapsed */}
            {!sidebarCollapsed && Array.from(groupedEntryPoints.methods.entries()).map(([className, methods]) => (
              <div key={className} style={{ padding: "8px 0" }}>
                <div style={{ padding: "4px 16px", fontSize: "11px", color: colors.callFlow.class, textTransform: "uppercase" }}>
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
                      backgroundColor: selectedFunction?.qualified_name === ep.qualified_name ? borders.default : "transparent",
                      color: colors.text.secondary,
                      cursor: "pointer",
                      fontSize: "13px",
                    }}
                  >
                    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                      <span style={{ fontWeight: 500 }}>{ep.name}</span>
                      {ep.node_count != null && ep.node_count > 0 && (
                        <span
                          style={{
                            fontSize: "10px",
                            padding: "2px 6px",
                            borderRadius: "10px",
                            backgroundColor: ep.node_count > 10 ? colors.severity.danger : ep.node_count > 5 ? colors.severity.warning : colors.severity.info,
                            color: colors.contrast.light,
                            fontWeight: 600,
                          }}
                          title={`${ep.node_count} calls in this method`}
                        >
                          {ep.node_count}
                        </span>
                      )}
                    </div>
                    <div style={{ fontSize: "11px", color: colors.gray[500] }}>Line {ep.line}</div>
                  </button>
                ))}
              </div>
            ))}

            {/* Collapsed indicator - shows entry point count */}
            {sidebarCollapsed && (
              <div
                style={{
                  padding: "12px 8px",
                  textAlign: "center",
                  color: colors.gray[500],
                  fontSize: "11px",
                }}
                title={`${filteredEntryPoints.length}/${entryPoints.length} entry points`}
              >
                <div style={{ fontSize: "16px", marginBottom: "4px" }}>📋</div>
                <div>{filteredEntryPoints.length}</div>
              </div>
            )}
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
                color: colors.text.muted,
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
                color: colors.text.muted,
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
              <div style={{ fontSize: "16px", color: colors.complexity.extreme, fontWeight: 500 }}>
                Error loading call flow
              </div>
              <div style={{ fontSize: "14px", color: colors.text.muted }}>
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
              <div style={{ fontSize: "16px", color: colors.text.muted }}>
                Enter a source file path to analyze call flows
              </div>
              <div style={{ fontSize: "14px", color: colors.gray[500] }}>
                Supports Python (.py) and C++ (.cpp, .hpp, .c, .h) files
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
              <div style={{ fontSize: "16px", color: colors.text.muted }}>
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
              <div style={{ fontSize: "16px", color: colors.severity.warning }}>
                No functions found in this file
              </div>
              <div style={{ fontSize: "14px", color: colors.text.muted }}>
                Make sure the file contains function definitions (Python or C++)
              </div>
            </div>
          )}

          {!callFlowQuery.isLoading && !callFlowQuery.isError && nodes.length > 0 && (
            <div style={{ position: "absolute", top: 0, left: 0, right: 0, bottom: 0 }}>
              <CallFlowGraph
                nodes={nodes}
                edges={edges}
                decisionNodes={decisionNodes}
                returnNodes={returnNodes}
                onNodeSelect={setSelectedNodeId}
                onEdgeSelect={setSelectedEdgeId}
                onBranchExpand={handleBranchToggle}
              />
            </div>
          )}
        </div>

        {/* Selected Node Details */}
        {selectedNodeId && nodes.length > 0 && (
          <div
            style={{
              width: "400px",
              borderLeft: `1px solid ${borders.default}`,
              backgroundColor: colors.base.card,
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
                  color: colors.text.muted,
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
                    <div style={{ fontSize: "11px", color: colors.gray[500], textTransform: "uppercase" }}>Name</div>
                    <div style={{ fontSize: "14px", fontWeight: 500 }}>{node.data.label}</div>
                  </div>
                  <div>
                    <div style={{ fontSize: "11px", color: colors.gray[500], textTransform: "uppercase" }}>Qualified Name</div>
                    <div style={{ fontSize: "13px", fontFamily: "monospace" }}>{node.data.qualifiedName}</div>
                  </div>
                  <div>
                    <div style={{ fontSize: "11px", color: colors.gray[500], textTransform: "uppercase" }}>Kind</div>
                    <div style={{ fontSize: "14px" }}>{node.data.kind}</div>
                  </div>
                  {node.data.filePath && (
                    <div>
                      <div style={{ fontSize: "11px", color: colors.gray[500], textTransform: "uppercase" }}>Location</div>
                      <div style={{ fontSize: "12px", fontFamily: "monospace" }}>
                        {node.data.filePath}:{node.data.line}
                      </div>
                    </div>
                  )}
                  {node.data.docstring && (
                    <div>
                      <div style={{ fontSize: "11px", color: colors.gray[500], textTransform: "uppercase" }}>Docstring</div>
                      <div style={{ fontSize: "12px", color: colors.text.muted, whiteSpace: "pre-wrap" }}>
                        {node.data.docstring}
                      </div>
                    </div>
                  )}

                  {/* Source Code Section */}
                  {node.data.filePath && (
                    <div style={{ marginTop: "8px" }}>
                      <div style={{
                        fontSize: "11px",
                        color: colors.gray[500],
                        textTransform: "uppercase",
                        marginBottom: "8px",
                        display: "flex",
                        alignItems: "center",
                        gap: "8px",
                      }}>
                        Source Code
                        {sourceCodeLoading && (
                          <span style={{ color: colors.text.muted, fontWeight: "normal", textTransform: "none" }}>
                            Loading...
                          </span>
                        )}
                      </div>
                      {nodeSourceCode && !sourceCodeLoading && (
                        <pre
                          style={{
                            margin: 0,
                            padding: "12px",
                            backgroundColor: colors.base.panel,
                            borderRadius: "6px",
                            border: `1px solid ${borders.default}`,
                            fontSize: "11px",
                            fontFamily: "'Fira Code', 'Consolas', monospace",
                            lineHeight: "1.5",
                            overflow: "auto",
                            maxHeight: "300px",
                            whiteSpace: "pre",
                            color: colors.gray[300],
                          }}
                        >
                          <code>{nodeSourceCode}</code>
                        </pre>
                      )}
                      {!nodeSourceCode && !sourceCodeLoading && (
                        <div style={{ fontSize: "12px", color: colors.gray[500], fontStyle: "italic" }}>
                          Could not load source code
                        </div>
                      )}
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
        extensions=".py,.cpp,.hpp,.c,.h,.ts,.tsx,.js,.jsx"
        onClose={() => setIsBrowseModalOpen(false)}
        onSelect={handleBrowseSelect}
      />
    </div>
  );
}
