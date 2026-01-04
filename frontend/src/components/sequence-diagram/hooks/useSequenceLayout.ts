/**
 * useSequenceLayout - Custom layout hook for sequence diagrams.
 *
 * Classic UML layout:
 * - Lifelines: horizontally spaced columns (left to right by order)
 * - Messages: vertically ordered rows (top to bottom by sequence number)
 *
 * This hook transforms the API response into React Flow nodes and edges
 * with calculated positions.
 */

import { useMemo } from "react";
import type { Node, Edge } from "reactflow";
import type { SequenceDiagramResponse } from "../../../api/types";

// Layout constants - classic UML style
const LIFELINE_SPACING = 180; // Horizontal spacing between lifelines
const MESSAGE_SPACING = 50; // Vertical spacing between messages
const LIFELINE_HEADER_HEIGHT = 60; // Height of lifeline header node
const LIFELINE_START_X = 80; // Left margin for first lifeline
const MESSAGES_START_Y = 120; // Top margin where messages start (below headers)

interface SequenceLayoutResult {
  nodes: Node[];
  edges: Edge[];
  lifelinePositions: Map<string, number>; // lifeline_id -> x position
}

export function useSequenceLayout(
  data: SequenceDiagramResponse | null | undefined
): SequenceLayoutResult {
  return useMemo(() => {
    if (!data) {
      return { nodes: [], edges: [], lifelinePositions: new Map() };
    }

    const nodes: Node[] = [];
    const edges: Edge[] = [];
    const lifelinePositions = new Map<string, number>();

    // Sort lifelines by order
    const sortedLifelines = [...data.lifelines].sort(
      (a, b) => a.data.order - b.data.order
    );

    // Create lifeline header nodes and record positions
    sortedLifelines.forEach((lifeline, index) => {
      const xPos = LIFELINE_START_X + index * LIFELINE_SPACING;
      lifelinePositions.set(lifeline.id, xPos);

      // Lifeline header node
      nodes.push({
        id: lifeline.id,
        type: "lifelineNode",
        position: { x: xPos, y: 50 },
        data: {
          ...lifeline.data,
          // Calculate the lifeline height based on message count
          lifelineHeight: MESSAGES_START_Y + data.messages.length * MESSAGE_SPACING + 50,
        },
        draggable: false, // Lifelines shouldn't be draggable
      });
    });

    // Sort messages by sequence number
    const sortedMessages = [...data.messages].sort(
      (a, b) => a.data.sequenceNumber - b.data.sequenceNumber
    );

    // Create message edges with calculated Y positions
    sortedMessages.forEach((message, index) => {
      const sourceX = lifelinePositions.get(message.source) || 0;
      const targetX = lifelinePositions.get(message.target) || 0;
      const yPos = MESSAGES_START_Y + index * MESSAGE_SPACING;

      // Determine edge type based on message type
      let edgeType = "syncMessageEdge";
      if (message.data.messageType === "return") {
        edgeType = "returnMessageEdge";
      } else if (message.data.messageType === "self") {
        edgeType = "selfMessageEdge";
      }

      edges.push({
        id: message.id,
        source: message.source,
        target: message.target,
        type: edgeType,
        data: {
          ...message.data,
          // Store calculated positions for custom edge rendering
          // These override React Flow's auto-calculated positions
          calculatedSourceX: sourceX,
          calculatedTargetX: targetX,
          calculatedY: yPos,
        },
      });
    });

    return { nodes, edges, lifelinePositions };
  }, [data]);
}

/**
 * Calculate the canvas dimensions based on the diagram data.
 */
export function useSequenceDimensions(
  data: SequenceDiagramResponse | null | undefined
): { width: number; height: number } {
  return useMemo(() => {
    if (!data) {
      return { width: 800, height: 600 };
    }

    const lifelineCount = data.lifelines.length;
    const messageCount = data.messages.length;

    const width = LIFELINE_START_X * 2 + lifelineCount * LIFELINE_SPACING;
    const height = MESSAGES_START_Y + messageCount * MESSAGE_SPACING + 100;

    return { width, height };
  }, [data]);
}

/**
 * Export layout constants for use in components.
 */
export const LAYOUT_CONSTANTS = {
  LIFELINE_SPACING,
  MESSAGE_SPACING,
  LIFELINE_HEADER_HEIGHT,
  LIFELINE_START_X,
  MESSAGES_START_Y,
} as const;
