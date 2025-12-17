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
import { DESIGN_TOKENS } from "../../theme/designTokens";

const { colors, borders } = DESIGN_TOKENS;

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
          color: colors.primary.main,
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
      return colors.callFlow.entryPoint;
    }
    const kind = node.data?.kind || "function";
    const kindColors: Record<string, string> = {
      function: colors.callFlow.function,
      method: colors.callFlow.method,
      external: colors.callFlow.external,
      builtin: colors.callFlow.builtin,
      class: colors.callFlow.class,
    };
    return kindColors[kind] || colors.callFlow.function;
  }, []);

  return (
    <div style={{ width: "100%", height: "100%", backgroundColor: colors.base.panel }}>
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
            stroke: colors.primary.main,
          },
        }}
        proOptions={{ hideAttribution: true }}
      >
        <Background
          color={borders.default}
          gap={16}
          size={1}
          style={{ backgroundColor: colors.base.panel }}
        />
        <Controls
          style={{
            backgroundColor: colors.base.card,
            border: `1px solid ${borders.default}`,
            borderRadius: "8px",
          }}
        />
        <MiniMap
          nodeColor={minimapNodeColor}
          style={{
            backgroundColor: colors.base.card,
            border: `1px solid ${borders.default}`,
            borderRadius: "8px",
          }}
          maskColor={`${colors.base.panel}B3`} // B3 = 70% opacity
        />
      </ReactFlow>
    </div>
  );
}
