/**
 * RelationshipEdge - React Flow edge for UML relationships
 *
 * Supports different UML relationship types with appropriate styling:
 * - inheritance: solid line, hollow triangle arrow
 * - implementation: dashed line, hollow triangle arrow
 * - composition: solid line, filled diamond
 * - aggregation: solid line, hollow diamond
 * - association: solid line, open arrow
 * - dependency: dashed line, open arrow
 */

import {
  BaseEdge,
  EdgeLabelRenderer,
  getBezierPath,
  type EdgeProps,
} from "reactflow";
import { DESIGN_TOKENS } from "../../../theme/designTokens";
import type { UmlRelationType } from "../../../api/types";

interface RelationshipEdgeData {
  type: UmlRelationType;
  description?: string;
  cardinality?: string | null;
}

const { colors, borders } = DESIGN_TOKENS;

// Colors for different relationship types
const RELATIONSHIP_COLORS: Record<UmlRelationType, string> = {
  inheritance: colors.primary.main,
  implementation: colors.callFlow.class,
  composition: colors.severity.danger,
  aggregation: colors.callFlow.method,
  association: colors.text.muted,
  dependency: colors.gray[500],
};

// Labels for relationship types
const RELATIONSHIP_LABELS: Record<UmlRelationType, string> = {
  inheritance: "extends",
  implementation: "implements",
  composition: "contains",
  aggregation: "has",
  association: "uses",
  dependency: "depends",
};

export function RelationshipEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  data,
  selected,
}: EdgeProps<RelationshipEdgeData>) {
  const relationType = data?.type || "association";
  const edgeColor = RELATIONSHIP_COLORS[relationType] || colors.text.muted;
  const isDashed = relationType === "implementation" || relationType === "dependency";

  const [edgePath, labelX, labelY] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  });

  // Determine marker based on relationship type
  const getMarkerEnd = () => {
    switch (relationType) {
      case "inheritance":
      case "implementation":
        return `url(#uml-triangle-${relationType})`;
      case "composition":
        return `url(#uml-diamond-filled)`;
      case "aggregation":
        return `url(#uml-diamond-hollow)`;
      default:
        return `url(#uml-arrow)`;
    }
  };

  return (
    <>
      {/* SVG Markers (defined once, reused) */}
      <svg style={{ position: "absolute", width: 0, height: 0 }}>
        <defs>
          {/* Triangle marker for inheritance/implementation */}
          <marker
            id={`uml-triangle-${relationType}`}
            viewBox="0 0 12 12"
            refX="10"
            refY="6"
            markerWidth="10"
            markerHeight="10"
            orient="auto-start-reverse"
          >
            <path
              d="M 0 0 L 12 6 L 0 12 z"
              fill={relationType === "inheritance" ? "none" : "none"}
              stroke={edgeColor}
              strokeWidth="1.5"
            />
          </marker>
          {/* Filled diamond for composition */}
          <marker
            id="uml-diamond-filled"
            viewBox="0 0 12 12"
            refX="10"
            refY="6"
            markerWidth="10"
            markerHeight="10"
            orient="auto-start-reverse"
          >
            <path
              d="M 0 6 L 6 0 L 12 6 L 6 12 z"
              fill={edgeColor}
              stroke={edgeColor}
              strokeWidth="1"
            />
          </marker>
          {/* Hollow diamond for aggregation */}
          <marker
            id="uml-diamond-hollow"
            viewBox="0 0 12 12"
            refX="10"
            refY="6"
            markerWidth="10"
            markerHeight="10"
            orient="auto-start-reverse"
          >
            <path
              d="M 0 6 L 6 0 L 12 6 L 6 12 z"
              fill={colors.base.card}
              stroke={edgeColor}
              strokeWidth="1.5"
            />
          </marker>
          {/* Simple arrow for association/dependency */}
          <marker
            id="uml-arrow"
            viewBox="0 0 12 12"
            refX="10"
            refY="6"
            markerWidth="8"
            markerHeight="8"
            orient="auto-start-reverse"
          >
            <path
              d="M 0 0 L 12 6 L 0 12"
              fill="none"
              stroke={edgeColor}
              strokeWidth="2"
            />
          </marker>
        </defs>
      </svg>

      <BaseEdge
        id={id}
        path={edgePath}
        markerEnd={getMarkerEnd()}
        style={{
          stroke: edgeColor,
          strokeWidth: selected ? 3 : 2,
          strokeDasharray: isDashed ? "5 5" : undefined,
          strokeOpacity: selected ? 1 : 0.7,
        }}
      />

      {/* Label */}
      <EdgeLabelRenderer>
        <div
          style={{
            position: "absolute",
            transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)`,
            fontSize: "10px",
            fontWeight: 500,
            padding: "2px 8px",
            borderRadius: "4px",
            backgroundColor: colors.base.card,
            color: edgeColor,
            border: `1px solid ${selected ? edgeColor : borders.default}`,
            pointerEvents: "all",
            opacity: selected ? 1 : 0.9,
          }}
          className="nodrag nopan"
        >
          {RELATIONSHIP_LABELS[relationType]}
          {data?.cardinality && (
            <span style={{ marginLeft: "4px", color: colors.text.muted }}>
              [{data.cardinality}]
            </span>
          )}
        </div>
      </EdgeLabelRenderer>
    </>
  );
}
