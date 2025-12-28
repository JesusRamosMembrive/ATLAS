/**
 * RelationshipEdge - React Flow edge for UML relationships.
 *
 * Supports different UML relationship types with appropriate styling:
 * - inheritance: solid line, hollow triangle arrow
 * - implementation: dashed line, hollow triangle arrow
 * - composition: solid line, filled diamond
 * - aggregation: solid line, hollow diamond
 * - association: solid line, open arrow
 * - dependency: dashed line, open arrow
 *
 * Uses shared graph-primitives for base edge functionality.
 */

import { type EdgeProps } from "reactflow";
import { DESIGN_TOKENS } from "../../../theme/designTokens";
import { BaseGraphEdge, RelationshipLabel } from "../../graph-primitives";
import type { UmlRelationType } from "../../../api/types";

interface RelationshipEdgeData {
  type: UmlRelationType;
  description?: string;
  cardinality?: string | null;
}

const { colors } = DESIGN_TOKENS;

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

/**
 * SVG Markers for UML relationships.
 * Rendered once per edge and referenced via URL.
 */
function UmlMarkers({ color, relationType }: { color: string; relationType: UmlRelationType }) {
  return (
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
            fill="none"
            stroke={color}
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
            fill={color}
            stroke={color}
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
            stroke={color}
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
            stroke={color}
            strokeWidth="2"
          />
        </marker>
      </defs>
    </svg>
  );
}

// Determine marker based on relationship type
function getMarkerEnd(relationType: UmlRelationType): string {
  switch (relationType) {
    case "inheritance":
    case "implementation":
      return `url(#uml-triangle-${relationType})`;
    case "composition":
      return "url(#uml-diamond-filled)";
    case "aggregation":
      return "url(#uml-diamond-hollow)";
    default:
      return "url(#uml-arrow)";
  }
}

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

  return (
    <>
      <UmlMarkers color={edgeColor} relationType={relationType} />
      <BaseGraphEdge
        id={id}
        sourceX={sourceX}
        sourceY={sourceY}
        targetX={targetX}
        targetY={targetY}
        sourcePosition={sourcePosition}
        targetPosition={targetPosition}
        color={edgeColor}
        isDashed={isDashed}
        markerEnd={getMarkerEnd(relationType)}
        selected={selected}
        labelContent={
          <RelationshipLabel
            label={RELATIONSHIP_LABELS[relationType]}
            cardinality={data?.cardinality}
            color={edgeColor}
            selected={selected}
          />
        }
      />
    </>
  );
}
