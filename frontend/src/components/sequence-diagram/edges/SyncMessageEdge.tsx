/**
 * SyncMessageEdge - Edge for synchronous messages in sequence diagrams.
 *
 * Classic UML style: Solid arrow with filled arrowhead, label above the line.
 */

import { memo } from "react";
import {
  EdgeLabelRenderer,
  type EdgeProps,
} from "reactflow";
import { DESIGN_TOKENS } from "../../../theme/designTokens";

const { colors } = DESIGN_TOKENS;

interface SyncMessageEdgeData {
  label: string;
  messageType: string;
  sequenceNumber: number;
  arguments: string[] | null;
  callSiteLine: number;
  fragmentId: string | null;
  fragmentOperandIndex: number | null;
}

interface CalculatedPositions {
  calculatedSourceX: number;
  calculatedTargetX: number;
  calculatedY: number;
}

export const SyncMessageEdge = memo(
  ({
    id,
    sourceX: _sourceX,
    sourceY: _sourceY,
    targetX: _targetX,
    targetY: _targetY,
    data,
    selected,
  }: EdgeProps<SyncMessageEdgeData & CalculatedPositions>) => {
    // Use calculated positions from layout hook
    const sourceX = data?.calculatedSourceX ?? _sourceX;
    const targetX = data?.calculatedTargetX ?? _targetX;
    const yPos = data?.calculatedY ?? _sourceY;

    // Determine direction
    const isLeftToRight = targetX > sourceX;
    const offset = 60; // Half of lifeline header width

    // Calculate actual start and end points
    const startX = isLeftToRight ? sourceX + offset : sourceX - offset;
    const endX = isLeftToRight ? targetX - offset : targetX + offset;
    const midX = (startX + endX) / 2;

    const edgeColor = selected ? colors.primary.main : "#374151";
    const arrowSize = 10;

    // Format arguments if present (shorter format)
    const argsStr = data?.arguments?.length
      ? `(${data.arguments.slice(0, 2).join(", ")}${data.arguments.length > 2 ? "..." : ""})`
      : "()";

    return (
      <>
        {/* SVG for the arrow line and arrowhead */}
        <svg
          style={{
            position: "absolute",
            left: 0,
            top: 0,
            width: "100%",
            height: "100%",
            pointerEvents: "none",
            overflow: "visible",
          }}
        >
          {/* Main line */}
          <line
            x1={startX}
            y1={yPos}
            x2={endX - (isLeftToRight ? arrowSize : -arrowSize)}
            y2={yPos}
            stroke={edgeColor}
            strokeWidth={selected ? 2 : 1.5}
          />

          {/* Filled arrowhead (classic UML sync message) */}
          <polygon
            points={
              isLeftToRight
                ? `${endX},${yPos} ${endX - arrowSize},${yPos - arrowSize / 2} ${endX - arrowSize},${yPos + arrowSize / 2}`
                : `${endX},${yPos} ${endX + arrowSize},${yPos - arrowSize / 2} ${endX + arrowSize},${yPos + arrowSize / 2}`
            }
            fill={edgeColor}
            stroke={edgeColor}
            strokeWidth="1"
          />
        </svg>

        {/* Label above the line - classic UML style */}
        <EdgeLabelRenderer>
          <div
            style={{
              position: "absolute",
              transform: `translate(-50%, -100%) translate(${midX}px,${yPos - 6}px)`,
              padding: "2px 6px",
              fontSize: "11px",
              fontWeight: 500,
              color: "#1f2937",
              pointerEvents: "all",
              whiteSpace: "nowrap",
              fontFamily: "monospace",
              backgroundColor: "rgba(255, 255, 255, 0.95)",
              borderRadius: "2px",
            }}
            className="nodrag nopan"
            title={`${data?.label}${argsStr} [line ${data?.callSiteLine}]`}
          >
            {/* Sequence number badge */}
            <span
              style={{
                backgroundColor: "#374151",
                color: "#fff",
                borderRadius: "3px",
                padding: "1px 5px",
                marginRight: "6px",
                fontSize: "10px",
                fontWeight: 600,
              }}
            >
              {data?.sequenceNumber}
            </span>
            {data?.label}{argsStr}
          </div>
        </EdgeLabelRenderer>
      </>
    );
  }
);

SyncMessageEdge.displayName = "SyncMessageEdge";
