/**
 * BaseGraphEdge - Flexible edge component for graph connections.
 *
 * Provides consistent edge rendering for Call Flow and UML Editor:
 * - Bezier path calculation
 * - Customizable stroke styles (solid, dashed)
 * - Optional label rendering
 * - Selection state styling
 */

import { memo, type ReactNode } from "react";
import {
  BaseEdge,
  EdgeLabelRenderer,
  getBezierPath,
  Position,
} from "reactflow";
import { DESIGN_TOKENS } from "../../theme/designTokens";
import type { BaseGraphEdgeProps } from "./types";

const { colors, borders } = DESIGN_TOKENS;

export const BaseGraphEdge = memo(function BaseGraphEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  color,
  isDashed = false,
  strokeWidth = 2,
  labelContent,
  markerEnd,
  selected = false,
  style,
}: BaseGraphEdgeProps) {
  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  });

  return (
    <>
      <BaseEdge
        id={id}
        path={edgePath}
        markerEnd={markerEnd}
        style={{
          stroke: color,
          strokeWidth: selected ? strokeWidth + 1 : strokeWidth,
          strokeDasharray: isDashed ? "5 5" : undefined,
          strokeOpacity: selected ? 1 : 0.8,
          ...style,
        }}
      />
      {labelContent && (
        <EdgeLabelRenderer>
          <div
            style={{
              position: "absolute",
              transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)`,
              pointerEvents: "all",
            }}
            className="nodrag nopan"
          >
            {labelContent}
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  );
});

/**
 * Default edge label styling component.
 */
interface EdgeLabelProps {
  /** Label text content */
  children: ReactNode;
  /** Border/text color */
  color: string;
  /** Whether the edge is selected */
  selected?: boolean;
}

export const EdgeLabel = memo(function EdgeLabel({
  children,
  color,
  selected = false,
}: EdgeLabelProps) {
  return (
    <div
      style={{
        fontSize: "10px",
        fontWeight: 500,
        padding: "2px 6px",
        borderRadius: "4px",
        backgroundColor: colors.base.card,
        color,
        border: `1px solid ${selected ? color : borders.default}`,
        opacity: selected ? 1 : 0.9,
      }}
    >
      {children}
    </div>
  );
});

/**
 * Call site line label for Call Flow edges.
 */
interface CallSiteLabelProps {
  line: number;
  color: string;
}

export const CallSiteLabel = memo(function CallSiteLabel({
  line,
  color,
}: CallSiteLabelProps) {
  return (
    <div
      style={{
        fontSize: "10px",
        fontWeight: 500,
        padding: "2px 6px",
        borderRadius: "4px",
        backgroundColor: colors.base.card,
        color: colors.callFlow.edgeLabel,
        border: `1px solid ${color}`,
      }}
    >
      L{line}
    </div>
  );
});

/**
 * Relationship label for UML Editor edges.
 */
interface RelationshipLabelProps {
  /** Relationship type label (extends, implements, etc.) */
  label: string;
  /** Optional cardinality text */
  cardinality?: string | null;
  /** Border/text color */
  color: string;
  /** Whether the edge is selected */
  selected?: boolean;
}

export const RelationshipLabel = memo(function RelationshipLabel({
  label,
  cardinality,
  color,
  selected = false,
}: RelationshipLabelProps) {
  return (
    <div
      style={{
        fontSize: "10px",
        fontWeight: 500,
        padding: "2px 8px",
        borderRadius: "4px",
        backgroundColor: colors.base.card,
        color,
        border: `1px solid ${selected ? color : borders.default}`,
        opacity: selected ? 1 : 0.9,
      }}
    >
      {label}
      {cardinality && (
        <span style={{ marginLeft: "4px", color: colors.text.muted }}>
          [{cardinality}]
        </span>
      )}
    </div>
  );
});
