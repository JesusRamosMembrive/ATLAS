/**
 * UmlEditorCanvas - React Flow canvas for the UML Editor
 *
 * Renders classes, interfaces, enums as nodes and relationships as edges.
 * Handles drag, drop, selection, and connection creation.
 */

import { useCallback, useMemo } from "react";
import ReactFlow, {
  Background,
  Controls,
  MiniMap,
  type Node,
  type Edge,
  type NodeTypes,
  type EdgeTypes,
  type OnNodesChange,
  type OnEdgesChange,
  type OnConnect,
  type Connection,
  applyNodeChanges,
  applyEdgeChanges,
  MarkerType,
} from "reactflow";
import "reactflow/dist/style.css";

import { ClassNode } from "./nodes/ClassNode";
import { InterfaceNode } from "./nodes/InterfaceNode";
import { EnumNode } from "./nodes/EnumNode";
import { StructNode } from "./nodes/StructNode";
import { RelationshipEdge } from "./edges/RelationshipEdge";
import { useUmlEditorStore } from "../../state/useUmlEditorStore";
import { DESIGN_TOKENS } from "../../theme/designTokens";
import type { UmlRelationType } from "../../api/types";

const { colors } = DESIGN_TOKENS;

// Struct color
const STRUCT_COLOR = "#0891b2";

// Define custom node types
const nodeTypes: NodeTypes = {
  classNode: ClassNode,
  interfaceNode: InterfaceNode,
  enumNode: EnumNode,
  structNode: StructNode,
};

// Define custom edge types
const edgeTypes: EdgeTypes = {
  relationship: RelationshipEdge,
};

export function UmlEditorCanvas(): JSX.Element {
  const {
    selectedNodeId,
    selectedEdgeId,
    getCurrentModule,
    selectNode,
    selectEdge,
    clearSelection,
    updateClassPosition,
    updateInterfacePosition,
    updateEnumPosition,
    updateStructPosition,
    addRelationship,
    deleteRelationship,
  } = useUmlEditorStore();

  const currentModule = getCurrentModule();

  // Convert module data to React Flow nodes
  const nodes: Node[] = useMemo(() => {
    if (!currentModule) return [];

    const result: Node[] = [];

    // Add class nodes
    for (const cls of currentModule.classes) {
      result.push({
        id: cls.id,
        type: "classNode",
        position: cls.position,
        data: {
          class: cls,
          selected: selectedNodeId === cls.id,
        },
        selected: selectedNodeId === cls.id,
      });
    }

    // Add interface nodes
    for (const iface of currentModule.interfaces) {
      result.push({
        id: iface.id,
        type: "interfaceNode",
        position: iface.position,
        data: {
          interface: iface,
          selected: selectedNodeId === iface.id,
        },
        selected: selectedNodeId === iface.id,
      });
    }

    // Add enum nodes
    for (const enm of currentModule.enums) {
      result.push({
        id: enm.id,
        type: "enumNode",
        position: enm.position,
        data: {
          enum: enm,
          selected: selectedNodeId === enm.id,
        },
        selected: selectedNodeId === enm.id,
      });
    }

    // Add struct nodes
    for (const struct of currentModule.structs) {
      result.push({
        id: struct.id,
        type: "structNode",
        position: struct.position,
        data: {
          struct: struct,
          selected: selectedNodeId === struct.id,
        },
        selected: selectedNodeId === struct.id,
      });
    }

    return result;
  }, [currentModule, selectedNodeId]);

  // Convert relationships to React Flow edges
  const edges: Edge[] = useMemo(() => {
    if (!currentModule) return [];

    return currentModule.relationships.map((rel) => ({
      id: rel.id,
      source: rel.from,
      target: rel.to,
      type: "relationship",
      data: {
        type: rel.type,
        description: rel.description,
        cardinality: rel.cardinality,
      },
      selected: selectedEdgeId === rel.id,
    }));
  }, [currentModule, selectedEdgeId]);

  // Handle node position changes
  const onNodesChange: OnNodesChange = useCallback(
    (changes) => {
      // Apply position changes to store
      for (const change of changes) {
        if (change.type === "position" && change.position) {
          const node = nodes.find((n) => n.id === change.id);
          if (!node) continue;

          if (node.type === "classNode") {
            updateClassPosition(change.id, change.position);
          } else if (node.type === "interfaceNode") {
            updateInterfacePosition(change.id, change.position);
          } else if (node.type === "enumNode") {
            updateEnumPosition(change.id, change.position);
          } else if (node.type === "structNode") {
            updateStructPosition(change.id, change.position);
          }
        }
      }
    },
    [nodes, updateClassPosition, updateInterfacePosition, updateEnumPosition, updateStructPosition]
  );

  // Handle edge changes (deletion)
  const onEdgesChange: OnEdgesChange = useCallback(
    (changes) => {
      for (const change of changes) {
        if (change.type === "remove") {
          deleteRelationship(change.id);
        }
      }
    },
    [deleteRelationship]
  );

  // Handle new connections
  const onConnect: OnConnect = useCallback(
    (connection: Connection) => {
      if (!connection.source || !connection.target) return;

      // Determine relationship type based on source/target handles
      let relationType: UmlRelationType = "association";

      if (connection.sourceHandle?.includes("inheritance")) {
        relationType = "inheritance";
      } else if (connection.sourceHandle?.includes("implementation")) {
        relationType = "implementation";
      }

      addRelationship({
        type: relationType,
        from: connection.source,
        to: connection.target,
        description: "",
        cardinality: null,
      });
    },
    [addRelationship]
  );

  // Handle node click
  const onNodeClick = useCallback(
    (_event: React.MouseEvent, node: Node) => {
      selectNode(node.id);
    },
    [selectNode]
  );

  // Handle edge click
  const onEdgeClick = useCallback(
    (_event: React.MouseEvent, edge: Edge) => {
      selectEdge(edge.id);
    },
    [selectEdge]
  );

  // Handle pane click (deselect)
  const onPaneClick = useCallback(() => {
    clearSelection();
  }, [clearSelection]);

  // MiniMap node color
  const minimapNodeColor = useCallback((node: Node) => {
    switch (node.type) {
      case "classNode":
        return colors.primary.main;
      case "interfaceNode":
        return colors.callFlow.class;
      case "enumNode":
        return colors.callFlow.method;
      case "structNode":
        return STRUCT_COLOR;
      default:
        return colors.text.muted;
    }
  }, []);

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      nodeTypes={nodeTypes}
      edgeTypes={edgeTypes}
      onNodesChange={onNodesChange}
      onEdgesChange={onEdgesChange}
      onConnect={onConnect}
      onNodeClick={onNodeClick}
      onEdgeClick={onEdgeClick}
      onPaneClick={onPaneClick}
      fitView
      fitViewOptions={{ padding: 0.2 }}
      defaultEdgeOptions={{
        type: "relationship",
        animated: false,
      }}
      connectionLineStyle={{
        stroke: colors.primary.main,
        strokeWidth: 2,
      }}
      style={{
        backgroundColor: colors.base.panel,
      }}
    >
      <Background color={colors.gray[700]} gap={20} size={1} />
      <Controls
        style={{
          backgroundColor: colors.base.card,
          borderRadius: "8px",
          border: `1px solid ${colors.gray[700]}`,
        }}
      />
      <MiniMap
        nodeColor={minimapNodeColor}
        maskColor={`${colors.base.panel}CC`}
        style={{
          backgroundColor: colors.base.card,
          borderRadius: "8px",
          border: `1px solid ${colors.gray[700]}`,
        }}
      />
    </ReactFlow>
  );
}
