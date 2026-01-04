/**
 * SequenceDiagramCanvas - React Flow canvas for sequence diagram visualization.
 *
 * Renders lifelines as columns and messages as horizontal arrows between them.
 */

import { useCallback, useMemo } from "react";
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  type NodeTypes,
  type EdgeTypes,
  type OnNodesChange,
  type OnEdgesChange,
  type Node,
  type Edge,
} from "reactflow";
import "reactflow/dist/style.css";

import { LifelineNode } from "./nodes/LifelineNode";
import { SyncMessageEdge } from "./edges/SyncMessageEdge";
import { ReturnMessageEdge } from "./edges/ReturnMessageEdge";
import { DESIGN_TOKENS } from "../../theme/designTokens";

const { colors, borders } = DESIGN_TOKENS;

// Register custom node types
const nodeTypes: NodeTypes = {
  lifelineNode: LifelineNode,
};

// Register custom edge types
const edgeTypes: EdgeTypes = {
  syncMessageEdge: SyncMessageEdge,
  returnMessageEdge: ReturnMessageEdge,
  selfMessageEdge: SyncMessageEdge, // Reuse sync for self-calls for now
};

interface SequenceDiagramCanvasProps {
  nodes: Node[];
  edges: Edge[];
  onNodesChange?: OnNodesChange;
  onEdgesChange?: OnEdgesChange;
  onNodeClick?: (node: Node) => void;
  onEdgeClick?: (edge: Edge) => void;
}

export function SequenceDiagramCanvas({
  nodes,
  edges,
  onNodesChange,
  onEdgesChange,
  onNodeClick,
  onEdgeClick,
}: SequenceDiagramCanvasProps) {
  // Handle node click
  const handleNodeClick = useCallback(
    (_event: React.MouseEvent, node: Node) => {
      onNodeClick?.(node);
    },
    [onNodeClick]
  );

  // Handle edge click
  const handleEdgeClick = useCallback(
    (_event: React.MouseEvent, edge: Edge) => {
      onEdgeClick?.(edge);
    },
    [onEdgeClick]
  );

  // Default viewport
  const defaultViewport = useMemo(
    () => ({
      x: 0,
      y: 0,
      zoom: 0.8,
    }),
    []
  );

  return (
    <div style={{ width: "100%", height: "100%" }}>
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        edgeTypes={edgeTypes}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onNodeClick={handleNodeClick}
        onEdgeClick={handleEdgeClick}
        defaultViewport={defaultViewport}
        fitView
        fitViewOptions={{
          padding: 0.2,
          includeHiddenNodes: false,
        }}
        minZoom={0.2}
        maxZoom={2}
        nodesDraggable={false}
        nodesConnectable={false}
        elementsSelectable={true}
        panOnDrag={true}
        zoomOnScroll={true}
        proOptions={{ hideAttribution: true }}
      >
        <Background
          color={borders.default}
          gap={20}
          size={1}
        />
        <Controls
          showZoom={true}
          showFitView={true}
          showInteractive={false}
          position="bottom-right"
        />
        <MiniMap
          nodeColor={(node) => {
            if (node.data?.isEntryPoint) {
              return colors.callFlow.entryPoint;
            }
            return colors.gray[400];
          }}
          maskColor={`${colors.base.panel}80`}
          position="bottom-left"
          pannable
          zoomable
        />
      </ReactFlow>
    </div>
  );
}
