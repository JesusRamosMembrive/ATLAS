import { useCallback, useMemo } from "react";
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  MarkerType,
  type Node,
  type Edge,
  type NodeTypes,
  type EdgeTypes,
} from "reactflow";
import "reactflow/dist/style.css";

import { CallFlowNode } from "./CallFlowNode";
import { CallFlowEdge } from "./CallFlowEdge";

interface CallFlowGraphProps {
  nodes: Node[];
  edges: Edge[];
  onNodeSelect?: (nodeId: string | null) => void;
  onEdgeSelect?: (edgeId: string | null) => void;
}

const nodeTypes: NodeTypes = {
  callFlowNode: CallFlowNode,
};

const edgeTypes: EdgeTypes = {
  callFlow: CallFlowEdge,
};

export function CallFlowGraph({
  nodes,
  edges,
  onNodeSelect,
  onEdgeSelect,
}: CallFlowGraphProps) {
  // Map nodes to use our custom type
  const mappedNodes = useMemo(
    () =>
      nodes.map((node) => ({
        ...node,
        type: "callFlowNode",
      })),
    [nodes]
  );

  // Map edges to use our custom type with animation
  const mappedEdges = useMemo(
    () =>
      edges.map((edge) => ({
        ...edge,
        type: "callFlow",
        animated: true,
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: "#3b82f6",
        },
      })),
    [edges]
  );

  const handleNodeClick = useCallback(
    (_event: React.MouseEvent, node: Node) => {
      onNodeSelect?.(node.id);
    },
    [onNodeSelect]
  );

  const handleEdgeClick = useCallback(
    (_event: React.MouseEvent, edge: Edge) => {
      onEdgeSelect?.(edge.id);
    },
    [onEdgeSelect]
  );

  const handlePaneClick = useCallback(() => {
    onNodeSelect?.(null);
    onEdgeSelect?.(null);
  }, [onNodeSelect, onEdgeSelect]);

  const minimapNodeColor = useCallback((node: Node) => {
    if (node.data?.isEntryPoint) {
      return "#f59e0b"; // amber for entry point
    }
    const kind = node.data?.kind || "function";
    const colors: Record<string, string> = {
      function: "#3b82f6",
      method: "#10b981",
      external: "#6b7280",
      builtin: "#f59e0b",
      class: "#a855f7",
    };
    return colors[kind] || "#3b82f6";
  }, []);

  return (
    <div style={{ width: "100%", height: "100%", backgroundColor: "#0f172a" }}>
      <ReactFlow
        nodes={mappedNodes}
        edges={mappedEdges}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        onNodeClick={handleNodeClick}
        onEdgeClick={handleEdgeClick}
        onPaneClick={handlePaneClick}
        fitView
        fitViewOptions={{
          padding: 0.2,
          maxZoom: 1,
        }}
        defaultEdgeOptions={{
          animated: true,
          style: {
            strokeWidth: 2,
            stroke: "#3b82f6",
          },
        }}
        proOptions={{ hideAttribution: true }}
      >
        <Background
          color="#334155"
          gap={16}
          size={1}
          style={{ backgroundColor: "#0f172a" }}
        />
        <Controls
          style={{
            backgroundColor: "#1e293b",
            border: "1px solid #334155",
            borderRadius: "8px",
          }}
        />
        <MiniMap
          nodeColor={minimapNodeColor}
          style={{
            backgroundColor: "#1e293b",
            border: "1px solid #334155",
            borderRadius: "8px",
          }}
          maskColor="rgba(15, 23, 42, 0.7)"
        />
      </ReactFlow>
    </div>
  );
}
