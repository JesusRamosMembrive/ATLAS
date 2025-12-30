import { useCallback, useMemo, useRef, useEffect, useState } from "react";
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  Panel,
  MarkerType,
  useNodesState,
  useEdgesState,
  useReactFlow,
  ReactFlowProvider,
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
import { ReturnFlowNode } from "./ReturnFlowNode";
import { StatementFlowNode } from "./StatementFlowNode";
import { ExternalCallFlowNode } from "./ExternalCallFlowNode";
import { DESIGN_TOKENS } from "../../theme/designTokens";
import { useElkLayout, type LayoutDirection } from "../../hooks/useElkLayout";

const { colors, borders } = DESIGN_TOKENS;

// Decision node from API (already in React Flow format)
interface DecisionNodeFromAPI {
  id: string;
  type: "decisionNode";
  position: { x: number; y: number };
  data: {
    label: string;
    decisionType: string;
    conditionText: string;
    filePath: string;
    line: number;
    column: number;
    parentCallId: string;
    depth: number;
    branches: Array<{
      branch_id: string;
      label: string;
      condition_text: string;
      is_expanded: boolean;
      call_count: number;
      start_line: number;
      end_line: number;
    }>;
  };
}

// Return node from API (already in React Flow format)
interface ReturnNodeFromAPI {
  id: string;
  type: "returnNode";
  position: { x: number; y: number };
  data: {
    label: string;
    returnValue: string;
    filePath: string | null;
    line: number;
    column: number;
    parentCallId: string;
    branchId?: string;
    decisionId?: string;
    depth: number;
  };
}

// Statement node from API (already in React Flow format)
interface StatementNodeFromAPI {
  id: string;
  type: "statementNode";
  position: { x: number; y: number };
  data: {
    label: string;
    statementType: "break" | "continue" | "pass" | "raise" | "assignment";
    content: string;
    filePath: string | null;
    line: number;
    column: number;
    parentCallId: string;
    branchId?: string;
    decisionId?: string;
    depth: number;
  };
}

// External call node from API (already in React Flow format)
interface ExternalCallNodeFromAPI {
  id: string;
  type: "externalCallNode";
  position: { x: number; y: number };
  data: {
    label: string;
    expression: string;
    callType: "builtin" | "stdlib" | "third_party";
    moduleHint: string | null;
    filePath: string | null;
    line: number;
    column: number;
    parentCallId: string;
    branchId?: string;
    decisionId?: string;
    depth: number;
  };
}

interface CallFlowGraphProps {
  nodes: Node[];
  edges: Edge[];
  decisionNodes?: DecisionNodeFromAPI[];
  returnNodes?: ReturnNodeFromAPI[];
  statementNodes?: StatementNodeFromAPI[];
  externalCallNodes?: ExternalCallNodeFromAPI[];
  onNodeSelect?: (nodeId: string | null) => void;
  onEdgeSelect?: (edgeId: string | null) => void;
  onBranchExpand?: (branchId: string) => void;
}

const nodeTypes: NodeTypes = {
  callFlowNode: CallFlowNode,
  decisionNode: DecisionFlowNode,
  returnNode: ReturnFlowNode,
  statementNode: StatementFlowNode,
  externalCallNode: ExternalCallFlowNode,
};

const edgeTypes: EdgeTypes = {
  callFlow: CallFlowEdge,
  branchFlow: BranchFlowEdge,
};

// Inner component that uses useReactFlow (must be inside ReactFlowProvider)
function CallFlowGraphInner({
  nodes,
  edges,
  decisionNodes = [],
  returnNodes = [],
  statementNodes = [],
  externalCallNodes = [],
  onNodeSelect,
  onEdgeSelect,
  onBranchExpand,
}: CallFlowGraphProps) {
  const { fitView } = useReactFlow();
  const { getLayoutedElements, isLayouting } = useElkLayout();
  const [layoutDirection, setLayoutDirection] = useState<LayoutDirection>("DOWN");

  // Use ref to keep a stable reference to onBranchExpand
  // This prevents stale closure issues with React Flow's internal caching
  const onBranchExpandRef = useRef(onBranchExpand);
  useEffect(() => {
    onBranchExpandRef.current = onBranchExpand;
  }, [onBranchExpand]);

  // Stable callback that always uses the latest onBranchExpand
  const stableOnBranchExpand = useCallback((branchId: string) => {
    onBranchExpandRef.current?.(branchId);
  }, []);

  // Map regular call nodes - add draggable property
  const mappedCallNodes = useMemo(
    () =>
      nodes.map((node) => ({
        ...node,
        type: "callFlowNode",
        draggable: true,
      })),
    [nodes]
  );

  // Map decision nodes - they come from API already in React Flow format
  // Just need to add the onBranchExpand callback to their data
  const mappedDecisionNodes = useMemo(
    () =>
      decisionNodes.map((dn) => ({
        ...dn,
        draggable: true,
        data: {
          ...dn.data,
          onBranchExpand: stableOnBranchExpand,
        },
      })),
    [decisionNodes, stableOnBranchExpand]
  );

  // Map return nodes - they come from API already in React Flow format
  const mappedReturnNodes = useMemo(
    () =>
      returnNodes.map((rn) => ({
        ...rn,
        draggable: true,
      })),
    [returnNodes]
  );

  // Map statement nodes - they come from API already in React Flow format
  const mappedStatementNodes = useMemo(
    () =>
      statementNodes.map((sn) => ({
        ...sn,
        draggable: true,
      })),
    [statementNodes]
  );

  // Map external call nodes - they come from API already in React Flow format
  const mappedExternalCallNodes = useMemo(
    () =>
      externalCallNodes.map((en) => ({
        ...en,
        draggable: true,
      })),
    [externalCallNodes]
  );

  // Combine all nodes from props
  const propsNodes = useMemo(
    () => [...mappedCallNodes, ...mappedDecisionNodes, ...mappedReturnNodes, ...mappedStatementNodes, ...mappedExternalCallNodes],
    [mappedCallNodes, mappedDecisionNodes, mappedReturnNodes, mappedStatementNodes, mappedExternalCallNodes]
  );

  // Map edges - detect branch edges by checking if target is a decision node
  const propsEdges = useMemo(
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

  // Use React Flow's state management for draggable nodes
  const [flowNodes, setFlowNodes, onNodesChange] = useNodesState(propsNodes);
  const [flowEdges, setFlowEdges, onEdgesChange] = useEdgesState(propsEdges);

  // Track if we've done initial layout
  const hasInitialLayout = useRef(false);
  // Track the last nodes/edges count to detect significant changes
  const lastLayoutKey = useRef("");

  // Apply ELK layout when nodes/edges change significantly
  const applyLayout = useCallback(
    async (direction: LayoutDirection, nodesToLayout: Node[], edgesToLayout: Edge[]) => {
      if (nodesToLayout.length === 0) return;

      const { nodes: layoutedNodes, edges: layoutedEdges } = await getLayoutedElements(
        nodesToLayout,
        edgesToLayout,
        direction
      );

      setFlowNodes(layoutedNodes);
      setFlowEdges(layoutedEdges);

      // Fit view after layout with a small delay to let React render
      setTimeout(() => fitView({ padding: 0.2, maxZoom: 1 }), 50);
    },
    [getLayoutedElements, setFlowNodes, setFlowEdges, fitView]
  );

  // Auto-layout on initial load and when nodes/edges change significantly
  useEffect(() => {
    // Create a key based on node/edge IDs to detect actual changes
    const currentKey = `${propsNodes.map((n) => n.id).sort().join(",")}|${propsEdges.map((e) => e.id).sort().join(",")}`;

    if (currentKey !== lastLayoutKey.current && propsNodes.length > 0) {
      lastLayoutKey.current = currentKey;
      applyLayout(layoutDirection, propsNodes, propsEdges);
      hasInitialLayout.current = true;
    }
  }, [propsNodes, propsEdges, layoutDirection, applyLayout]);

  // Handler for manual layout button
  const handleLayout = useCallback(
    (direction: LayoutDirection) => {
      setLayoutDirection(direction);
      applyLayout(direction, flowNodes, flowEdges);
    },
    [flowNodes, flowEdges, applyLayout]
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
    // External call nodes get a purple/violet color
    if (node.type === "externalCallNode") {
      return "#8b5cf6"; // violet - matches ExternalCallFlowNode third_party color
    }
    // Statement nodes get their respective colors
    if (node.type === "statementNode") {
      return "#6b7280"; // gray - neutral color for statements
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

  const buttonStyle = {
    padding: "6px 12px",
    fontSize: "12px",
    fontWeight: 500,
    border: `1px solid ${borders.default}`,
    borderRadius: "4px",
    cursor: "pointer",
    transition: "all 0.2s ease",
  };

  const activeButtonStyle = {
    ...buttonStyle,
    backgroundColor: colors.primary.main,
    color: "#fff",
    borderColor: colors.primary.main,
  };

  const inactiveButtonStyle = {
    ...buttonStyle,
    backgroundColor: colors.base.card,
    color: colors.text.main,
  };

  return (
    <div style={{ width: "100%", height: "100%", backgroundColor: colors.base.panel }}>
      <ReactFlow
        nodes={flowNodes}
        edges={flowEdges}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
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
        {/* Layout controls panel */}
        <Panel
          position="top-right"
          style={{
            display: "flex",
            gap: "8px",
            padding: "8px",
            backgroundColor: colors.base.card,
            border: `1px solid ${borders.default}`,
            borderRadius: "8px",
          }}
        >
          <button
            onClick={() => handleLayout("DOWN")}
            disabled={isLayouting}
            style={layoutDirection === "DOWN" ? activeButtonStyle : inactiveButtonStyle}
            title="Vertical layout (top to bottom)"
          >
            Vertical
          </button>
          <button
            onClick={() => handleLayout("RIGHT")}
            disabled={isLayouting}
            style={layoutDirection === "RIGHT" ? activeButtonStyle : inactiveButtonStyle}
            title="Horizontal layout (left to right)"
          >
            Horizontal
          </button>
          {isLayouting && (
            <span style={{ fontSize: "12px", color: colors.text.muted, alignSelf: "center" }}>
              Layouting...
            </span>
          )}
        </Panel>
      </ReactFlow>
    </div>
  );
}

// Main export - wraps inner component with ReactFlowProvider
export function CallFlowGraph(props: CallFlowGraphProps) {
  return (
    <ReactFlowProvider>
      <CallFlowGraphInner {...props} />
    </ReactFlowProvider>
  );
}
