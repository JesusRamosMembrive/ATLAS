/**
 * SequenceDiagramView - Main container for sequence diagram visualization.
 *
 * Fetches sequence diagram data from the API and renders it using React Flow.
 * Triggered from CallFlowView with a specific function as entry point.
 */

import { useState, useCallback, useEffect } from "react";
import { ReactFlowProvider, useNodesState, useEdgesState } from "reactflow";
import type { Node, Edge } from "reactflow";

import { SequenceDiagramCanvas } from "./SequenceDiagramCanvas";
import { useSequenceLayout, useSequenceDimensions } from "./hooks/useSequenceLayout";
import { getSequenceDiagram } from "../../api/client";
import type { SequenceDiagramResponse } from "../../api/types";
import { DESIGN_TOKENS } from "../../theme/designTokens";

const { colors, borders } = DESIGN_TOKENS;

interface SequenceDiagramViewProps {
  filePath: string;
  functionName: string;
  maxDepth?: number;
  onClose?: () => void;
  onNodeClick?: (nodeData: unknown) => void;
  onEdgeClick?: (edgeData: unknown) => void;
}

// Type for lifeline node data shown in detail panel
interface LifelineNodeData {
  name: string;
  qualifiedName: string;
  participantType: string;
  filePath: string | null;
  line: number;
  isEntryPoint: boolean;
  order: number;
}

function SequenceDiagramViewInner({
  filePath,
  functionName,
  maxDepth = 5,
  onClose,
  onNodeClick,
  onEdgeClick,
}: SequenceDiagramViewProps) {
  const [data, setData] = useState<SequenceDiagramResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedNode, setSelectedNode] = useState<LifelineNodeData | null>(null);

  // Layout hook transforms API response to React Flow nodes/edges
  const { nodes: layoutNodes, edges: layoutEdges } = useSequenceLayout(data);

  // React Flow state
  const [nodes, setNodes, onNodesChange] = useNodesState(layoutNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(layoutEdges);

  // Update nodes/edges when layout changes
  useEffect(() => {
    setNodes(layoutNodes);
    setEdges(layoutEdges);
  }, [layoutNodes, layoutEdges, setNodes, setEdges]);

  // Fetch data on mount
  useEffect(() => {
    let cancelled = false;

    async function fetchData() {
      setLoading(true);
      setError(null);

      try {
        const response = await getSequenceDiagram(filePath, functionName, maxDepth);
        if (!cancelled) {
          setData(response);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Failed to load sequence diagram");
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    fetchData();

    return () => {
      cancelled = true;
    };
  }, [filePath, functionName, maxDepth]);

  // Handle node click - show detail panel
  const handleNodeClick = useCallback(
    (node: Node) => {
      setSelectedNode(node.data as LifelineNodeData);
      onNodeClick?.(node.data);
    },
    [onNodeClick]
  );

  // Handle edge click
  const handleEdgeClick = useCallback(
    (edge: Edge) => {
      onEdgeClick?.(edge.data);
    },
    [onEdgeClick]
  );

  // Loading state
  if (loading) {
    return (
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          height: "100%",
          gap: "16px",
          color: colors.text.muted,
        }}
      >
        <div
          style={{
            width: "40px",
            height: "40px",
            border: `3px solid ${colors.gray[700]}`,
            borderTopColor: colors.primary.main,
            borderRadius: "50%",
            animation: "spin 1s linear infinite",
          }}
        />
        <span>Loading sequence diagram...</span>
        <style>
          {`
            @keyframes spin {
              to { transform: rotate(360deg); }
            }
          `}
        </style>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          height: "100%",
          gap: "16px",
          padding: "24px",
        }}
      >
        <div
          style={{
            padding: "16px 24px",
            backgroundColor: colors.severity.danger + "20",
            border: `1px solid ${colors.severity.danger}`,
            borderRadius: "8px",
            color: colors.severity.danger,
            textAlign: "center",
          }}
        >
          <strong>Error loading sequence diagram</strong>
          <p style={{ margin: "8px 0 0 0", fontSize: "14px" }}>{error}</p>
        </div>
        {onClose && (
          <button
            onClick={onClose}
            style={{
              padding: "8px 16px",
              backgroundColor: colors.gray[700],
              border: `1px solid ${borders.default}`,
              borderRadius: "6px",
              cursor: "pointer",
              fontSize: "14px",
              color: colors.text.main,
            }}
          >
            Close
          </button>
        )}
      </div>
    );
  }

  // Empty state
  if (!data || data.lifelines.length === 0) {
    return (
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          height: "100%",
          gap: "16px",
          color: colors.text.muted,
        }}
      >
        <span style={{ fontSize: "48px" }}>📭</span>
        <span>No sequence data found for this function</span>
        <span style={{ fontSize: "12px", color: colors.gray[500] }}>
          The function may not have any outgoing calls
        </span>
      </div>
    );
  }

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100%",
        backgroundColor: colors.base.panel,
      }}
    >
      {/* Header */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "12px 16px",
          borderBottom: `1px solid ${borders.default}`,
          backgroundColor: colors.base.card,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <span style={{ fontSize: "18px" }}>📊</span>
          <div>
            <h3
              style={{
                margin: 0,
                fontSize: "16px",
                fontWeight: 600,
                color: colors.text.main,
              }}
            >
              Sequence Diagram
            </h3>
            <span
              style={{
                fontSize: "12px",
                color: colors.text.muted,
                fontFamily: "monospace",
              }}
            >
              {functionName}
            </span>
          </div>
        </div>

        <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
          {/* Stats */}
          <div
            style={{
              display: "flex",
              gap: "12px",
              fontSize: "12px",
              color: colors.text.muted,
            }}
          >
            <span>
              <strong>{data.metadata.lifelineCount}</strong> lifelines
            </span>
            <span>•</span>
            <span>
              <strong>{data.metadata.messageCount}</strong> messages
            </span>
            <span>•</span>
            <span>
              depth <strong>{data.metadata.maxDepth}</strong>
            </span>
          </div>

          {/* Close button */}
          {onClose && (
            <button
              onClick={onClose}
              style={{
                padding: "6px 12px",
                backgroundColor: colors.gray[700],
                border: `1px solid ${borders.default}`,
                borderRadius: "6px",
                cursor: "pointer",
                fontSize: "13px",
                display: "flex",
                alignItems: "center",
                gap: "4px",
                color: colors.text.main,
              }}
            >
              ✕ Close
            </button>
          )}
        </div>
      </div>

      {/* Canvas and Detail Panel Container */}
      <div style={{ flex: 1, minHeight: 0, display: "flex" }}>
        {/* Canvas */}
        <div style={{ flex: 1, minHeight: 0 }}>
          <SequenceDiagramCanvas
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onNodeClick={handleNodeClick}
            onEdgeClick={handleEdgeClick}
          />
        </div>

        {/* Detail Panel */}
        {selectedNode && (
          <div
            style={{
              width: "320px",
              borderLeft: `1px solid ${borders.default}`,
              backgroundColor: colors.base.card,
              overflow: "auto",
              padding: "16px",
            }}
          >
            {/* Panel Header */}
            <div
              style={{
                display: "flex",
                justifyContent: "space-between",
                alignItems: "center",
                marginBottom: "16px",
              }}
            >
              <h4
                style={{
                  margin: 0,
                  fontSize: "14px",
                  fontWeight: 600,
                  color: colors.text.main,
                }}
              >
                Lifeline Details
              </h4>
              <button
                onClick={() => setSelectedNode(null)}
                style={{
                  background: "none",
                  border: "none",
                  cursor: "pointer",
                  fontSize: "18px",
                  color: colors.text.muted,
                  padding: "4px",
                }}
              >
                ×
              </button>
            </div>

            {/* Details Content */}
            <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
              {/* Name */}
              <div>
                <label
                  style={{
                    fontSize: "10px",
                    color: colors.text.muted,
                    textTransform: "uppercase",
                    letterSpacing: "0.5px",
                  }}
                >
                  Name
                </label>
                <div
                  style={{
                    fontSize: "14px",
                    fontWeight: 600,
                    color: colors.text.main,
                    fontFamily: "monospace",
                    marginTop: "2px",
                  }}
                >
                  {selectedNode.name}
                </div>
              </div>

              {/* Qualified Name */}
              <div>
                <label
                  style={{
                    fontSize: "10px",
                    color: colors.text.muted,
                    textTransform: "uppercase",
                    letterSpacing: "0.5px",
                  }}
                >
                  Qualified Name
                </label>
                <div
                  style={{
                    fontSize: "12px",
                    color: colors.text.main,
                    fontFamily: "monospace",
                    marginTop: "2px",
                    wordBreak: "break-all",
                  }}
                >
                  {selectedNode.qualifiedName}
                </div>
              </div>

              {/* Type */}
              <div>
                <label
                  style={{
                    fontSize: "10px",
                    color: colors.text.muted,
                    textTransform: "uppercase",
                    letterSpacing: "0.5px",
                  }}
                >
                  Type
                </label>
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                    marginTop: "4px",
                  }}
                >
                  <span
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      justifyContent: "center",
                      width: "24px",
                      height: "24px",
                      borderRadius: "50%",
                      backgroundColor:
                        selectedNode.participantType === "class"
                          ? "#7c3aed"
                          : selectedNode.participantType === "module"
                          ? "#64748b"
                          : selectedNode.participantType === "object"
                          ? "#8b5cf6"
                          : "#6366f1",
                      color: "white",
                      fontSize: "12px",
                      fontWeight: 700,
                    }}
                  >
                    {selectedNode.participantType.charAt(0).toUpperCase()}
                  </span>
                  <span style={{ fontSize: "13px", color: colors.text.main }}>
                    {selectedNode.participantType}
                  </span>
                </div>
              </div>

              {/* File Path */}
              <div>
                <label
                  style={{
                    fontSize: "10px",
                    color: colors.text.muted,
                    textTransform: "uppercase",
                    letterSpacing: "0.5px",
                  }}
                >
                  File Path
                </label>
                <div
                  style={{
                    fontSize: "11px",
                    color: selectedNode.filePath ? colors.text.main : colors.text.muted,
                    fontFamily: "monospace",
                    marginTop: "2px",
                    wordBreak: "break-all",
                    padding: "8px",
                    backgroundColor: colors.base.panel,
                    borderRadius: "4px",
                    border: `1px solid ${borders.default}`,
                  }}
                >
                  {selectedNode.filePath || "External / Built-in"}
                </div>
              </div>

              {/* Line Number */}
              {selectedNode.line > 0 && (
                <div>
                  <label
                    style={{
                      fontSize: "10px",
                      color: colors.text.muted,
                      textTransform: "uppercase",
                      letterSpacing: "0.5px",
                    }}
                  >
                    Line Number
                  </label>
                  <div
                    style={{
                      fontSize: "13px",
                      color: colors.text.main,
                      marginTop: "2px",
                    }}
                  >
                    Line {selectedNode.line}
                  </div>
                </div>
              )}

              {/* Entry Point Badge */}
              {selectedNode.isEntryPoint && (
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "8px",
                    padding: "8px 12px",
                    backgroundColor: colors.callFlow.entryPoint + "20",
                    borderRadius: "6px",
                    border: `1px solid ${colors.callFlow.entryPoint}`,
                  }}
                >
                  <span style={{ fontSize: "16px" }}>🎯</span>
                  <span
                    style={{
                      fontSize: "12px",
                      color: colors.callFlow.entryPoint,
                      fontWeight: 600,
                    }}
                  >
                    Entry Point
                  </span>
                </div>
              )}

              {/* Order */}
              <div>
                <label
                  style={{
                    fontSize: "10px",
                    color: colors.text.muted,
                    textTransform: "uppercase",
                    letterSpacing: "0.5px",
                  }}
                >
                  Order in Diagram
                </label>
                <div
                  style={{
                    fontSize: "13px",
                    color: colors.text.main,
                    marginTop: "2px",
                  }}
                >
                  #{selectedNode.order + 1}
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * SequenceDiagramView wrapped with ReactFlowProvider.
 */
export function SequenceDiagramView(props: SequenceDiagramViewProps) {
  return (
    <ReactFlowProvider>
      <SequenceDiagramViewInner {...props} />
    </ReactFlowProvider>
  );
}
