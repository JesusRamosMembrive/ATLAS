import { useCallback, useState } from "react";
import type { Node, Edge } from "reactflow";
import ELK from "elkjs/lib/elk.bundled.js";

const elk = new ELK();

export type LayoutDirection = "DOWN" | "RIGHT";

// ELK layout options for UML diagrams
// Reference: https://www.eclipse.org/elk/reference/options.html
const getElkOptions = (direction: LayoutDirection) => ({
  "elk.algorithm": "layered",
  "elk.direction": direction,
  // Spacing between nodes in the same layer
  "elk.spacing.nodeNode": "60",
  // Spacing between layers (rows/columns)
  "elk.layered.spacing.nodeNodeBetweenLayers": "100",
  // Spacing for edges
  "elk.spacing.edgeNode": "40",
  "elk.spacing.edgeEdge": "25",
  // Edge routing strategy - ORTHOGONAL creates right-angle edges
  "elk.layered.edgeRouting": "ORTHOGONAL",
  // Minimize edge crossings
  "elk.layered.crossingMinimization.strategy": "LAYER_SWEEP",
  // Node placement strategy for compact layout
  "elk.layered.nodePlacement.strategy": "NETWORK_SIMPLEX",
  // Consider node size for better spacing
  "elk.layered.considerModelOrder.strategy": "NODES_AND_EDGES",
});

// Default UML node dimensions
const DEFAULT_CLASS_WIDTH = 220;
const DEFAULT_CLASS_HEIGHT = 150;
const DEFAULT_INTERFACE_WIDTH = 200;
const DEFAULT_INTERFACE_HEIGHT = 120;
const DEFAULT_ENUM_WIDTH = 180;
const DEFAULT_ENUM_HEIGHT = 100;
const DEFAULT_STRUCT_WIDTH = 200;
const DEFAULT_STRUCT_HEIGHT = 120;

interface LayoutResult {
  nodes: Node[];
  edges: Edge[];
}

/**
 * Hook for automatic UML diagram layout using ELK (Eclipse Layout Kernel).
 *
 * ELK provides sophisticated graph layout algorithms that:
 * - Prevent node overlaps
 * - Minimize edge crossings
 * - Create hierarchical/layered layouts perfect for UML diagrams
 *
 * @returns Layout function and loading state
 */
export function useUmlElkLayout() {
  const [isLayouting, setIsLayouting] = useState(false);

  const getLayoutedElements = useCallback(
    async (
      nodes: Node[],
      edges: Edge[],
      direction: LayoutDirection = "DOWN"
    ): Promise<LayoutResult> => {
      if (nodes.length === 0) {
        return { nodes, edges };
      }

      setIsLayouting(true);

      try {
        const isHorizontal = direction === "RIGHT";

        // Build ELK graph structure
        const graph = {
          id: "root",
          layoutOptions: getElkOptions(direction),
          children: nodes.map((node) => {
            // Determine node dimensions based on type
            let width: number;
            let height: number;

            switch (node.type) {
              case "classNode":
                width = DEFAULT_CLASS_WIDTH;
                height = DEFAULT_CLASS_HEIGHT;
                break;
              case "interfaceNode":
                width = DEFAULT_INTERFACE_WIDTH;
                height = DEFAULT_INTERFACE_HEIGHT;
                break;
              case "enumNode":
                width = DEFAULT_ENUM_WIDTH;
                height = DEFAULT_ENUM_HEIGHT;
                break;
              case "structNode":
                width = DEFAULT_STRUCT_WIDTH;
                height = DEFAULT_STRUCT_HEIGHT;
                break;
              default:
                width = DEFAULT_CLASS_WIDTH;
                height = DEFAULT_CLASS_HEIGHT;
            }

            // Allow explicit node dimensions to override defaults
            width = node.width || width;
            height = node.height || height;

            return {
              id: node.id,
              width,
              height,
            };
          }),
          edges: edges.map((edge) => ({
            id: edge.id,
            sources: [edge.source],
            targets: [edge.target],
          })),
        };

        const layoutedGraph = await elk.layout(graph);

        // Map ELK results back to React Flow format
        const layoutedNodes = nodes.map((node) => {
          const elkNode = layoutedGraph.children?.find((n) => n.id === node.id);

          if (elkNode) {
            return {
              ...node,
              position: {
                x: elkNode.x ?? node.position.x,
                y: elkNode.y ?? node.position.y,
              },
              // Update handle positions based on layout direction
              targetPosition: isHorizontal ? "left" : "top",
              sourcePosition: isHorizontal ? "right" : "bottom",
            };
          }
          return node;
        });

        return {
          nodes: layoutedNodes as Node[],
          edges,
        };
      } catch (error) {
        console.error("ELK layout failed:", error);
        return { nodes, edges };
      } finally {
        setIsLayouting(false);
      }
    },
    []
  );

  return {
    getLayoutedElements,
    isLayouting,
  };
}
