/**
 * UmlEditorCanvas - React Flow canvas for the UML Editor
 *
 * Renders classes, interfaces, enums as nodes and relationships as edges.
 * Handles drag, drop, selection, and connection creation.
 */

import { useCallback, useMemo, useEffect } from "react";
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
import {
  findConnectedComponents,
  getEntitiesForComponent,
  getRelationshipsForComponent,
} from "../../utils/graphAnalysis";
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
    activeComponentId,
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
    deleteClass,
    deleteInterface,
    deleteEnum,
    deleteStruct,
  } = useUmlEditorStore();

  const currentModule = getCurrentModule();

  // Analyze connected components for filtering
  const componentAnalysis = useMemo(() => {
    if (!currentModule) return null;
    return findConnectedComponents(currentModule);
  }, [currentModule]);

  // Get filtered entity IDs based on active component
  const visibleEntityIds = useMemo(() => {
    if (!currentModule || !componentAnalysis) return null;
    return getEntitiesForComponent(currentModule, activeComponentId, componentAnalysis);
  }, [currentModule, activeComponentId, componentAnalysis]);

  // Get filtered relationship IDs based on active component
  const visibleRelationshipIds = useMemo(() => {
    if (!currentModule || !componentAnalysis) return null;
    return getRelationshipsForComponent(
      activeComponentId,
      componentAnalysis,
      currentModule.relationships
    );
  }, [currentModule, activeComponentId, componentAnalysis]);

  // Handle Delete key to remove selected element
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      // Check if Delete or Backspace is pressed
      if (event.key === "Delete" || event.key === "Backspace") {
        // Don't delete if user is typing in an input field
        const target = event.target as HTMLElement;
        if (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable) {
          return;
        }

        // Delete selected relationship
        if (selectedEdgeId) {
          event.preventDefault();
          deleteRelationship(selectedEdgeId);
          return;
        }

        // Delete selected node
        if (selectedNodeId && currentModule) {
          event.preventDefault();

          // Determine node type and delete
          if (currentModule.classes.some((c) => c.id === selectedNodeId)) {
            deleteClass(selectedNodeId);
          } else if (currentModule.interfaces.some((i) => i.id === selectedNodeId)) {
            deleteInterface(selectedNodeId);
          } else if (currentModule.enums.some((e) => e.id === selectedNodeId)) {
            deleteEnum(selectedNodeId);
          } else if (currentModule.structs.some((s) => s.id === selectedNodeId)) {
            deleteStruct(selectedNodeId);
          }
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [
    selectedNodeId,
    selectedEdgeId,
    currentModule,
    deleteClass,
    deleteInterface,
    deleteEnum,
    deleteStruct,
    deleteRelationship,
  ]);

  // Convert module data to React Flow nodes (filtered by active component)
  const nodes: Node[] = useMemo(() => {
    if (!currentModule) return [];

    const result: Node[] = [];

    // Add class nodes (filtered)
    for (const cls of currentModule.classes) {
      // Skip if not in visible set
      if (visibleEntityIds && !visibleEntityIds.has(cls.id)) continue;

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

    // Add interface nodes (filtered)
    for (const iface of currentModule.interfaces) {
      if (visibleEntityIds && !visibleEntityIds.has(iface.id)) continue;

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

    // Add enum nodes (filtered)
    for (const enm of currentModule.enums) {
      if (visibleEntityIds && !visibleEntityIds.has(enm.id)) continue;

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

    // Add struct nodes (filtered)
    for (const struct of currentModule.structs) {
      if (visibleEntityIds && !visibleEntityIds.has(struct.id)) continue;

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
  }, [currentModule, selectedNodeId, visibleEntityIds]);

  // Convert relationships to React Flow edges (filtered by active component)
  const edges: Edge[] = useMemo(() => {
    if (!currentModule) return [];

    return currentModule.relationships
      .filter((rel) => !visibleRelationshipIds || visibleRelationshipIds.has(rel.id))
      .map((rel) => ({
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
  }, [currentModule, selectedEdgeId, visibleRelationshipIds]);

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
