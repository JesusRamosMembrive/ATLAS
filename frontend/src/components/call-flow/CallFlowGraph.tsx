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
import { DecisionFlowNode } from "./DecisionFlowNode";
import { BranchFlowEdge } from "./BranchFlowEdge";
import { DESIGN_TOKENS } from "../../theme/designTokens";

const { colors, borders } = DESIGN_TOKENS;

interface DecisionNodeData {
  id: string;
  decision_type: string;
  condition_text: string;
  file_path?: string | null;
  line: number;
  column: number;
  parent_call_id: string;
  branches: Array<{
    branch_id: string;
    label: string;
    condition_text: string;
    is_expanded: boolean;
    call_count: number;
    start_line: number;
    end_line: number;
  }>;
  depth: number;
}

interface CallFlowGraphProps {
  nodes: Node[];
  edges: Edge[];
  decisionNodes?: DecisionNodeData[];
  onNodeSelect?: (nodeId: string | null) => void;
  onEdgeSelect?: (edgeId: string | null) => void;
  onBranchExpand?: (branchId: string) => void;
}

const nodeTypes: NodeTypes = {
  callFlowNode: CallFlowNode,
  decisionNode: DecisionFlowNode,
};

const edgeTypes: EdgeTypes = {
  callFlow: CallFlowEdge,
  branchFlow: BranchFlowEdge,
};

export function CallFlowGraph({
  nodes,
  edges,
  decisionNodes = [],
  onNodeSelect,
  onEdgeSelect,
  onBranchExpand,
}: CallFlowGraphProps) {
  // Map regular call nodes
  const mappedCallNodes = useMemo(
    () =>
      nodes.map((node) => ({
        ...node,
        type: "callFlowNode",
      })),
    [nodes]
  );

  // Map decision nodes to React Flow format
  const mappedDecisionNodes = useMemo(
    () =>
      decisionNodes.map((dn, index) => ({
        id: dn.id,
        type: "decisionNode",
        position: { x: 0, y: 0 }, // Will be laid out by React Flow
        data: {
          id: dn.id,
          decisionType: dn.decision_type,
          conditionText: dn.condition_text,
          filePath: dn.file_path,
          line: dn.line,
          column: dn.column,
          parentCallId: dn.parent_call_id,
          branches: dn.branches,
          depth: dn.depth,
          onBranchExpand: onBranchExpand,
        },
      })),
    [decisionNodes, onBranchExpand]
  );

  // Combine all nodes
  const allNodes = useMemo(
    () => [...mappedCallNodes, ...mappedDecisionNodes],
    [mappedCallNodes, mappedDecisionNodes]
  );

  // Map edges - detect branch edges by checking if target is a decision node
  const mappedEdges = useMemo(
    () =>
      edges.map((edge) => {
        const isBranchEdge = edge.data?.branchId != null;
        return {
          ...edge,
          type: isBranchEdge ? "branchFlow" : "callFlow",
          animated: !isBranchEdge, // Only animate regular call edges
          markerEnd: {
            type: MarkerType.ArrowClosed,
            color: isBranchEdge
              ? colors.callFlow.decision
              : colors.primary.main,
          },
        };
      }),
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
    // Decision nodes have a distinct color
    if (node.type === "decisionNode") {
      return colors.callFlow.decision;
    }
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
        nodes={allNodes}
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
