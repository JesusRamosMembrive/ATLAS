/**
 * ReturnMessageEdge - Edge for return messages in sequence diagrams.
 *
 * Classic UML style: Dashed arrow with open arrowhead, label above the line.
 */

import { memo } from "react";
import {
  EdgeLabelRenderer,
  type EdgeProps,
} from "reactflow";
import { DESIGN_TOKENS } from "../../../theme/designTokens";

const { colors } = DESIGN_TOKENS;

interface ReturnMessageEdgeData {
  label: string;
  messageType: string;
  sequenceNumber: number;
  returnValue: string | null;
  callSiteLine: number;
  fragmentId: string | null;
  fragmentOperandIndex: number | null;
}

interface CalculatedPositions {
  calculatedSourceX: number;
  calculatedTargetX: number;
  calculatedY: number;
}

export const ReturnMessageEdge = memo(
  ({
    id,
    sourceX: _sourceX,
    sourceY: _sourceY,
    targetX: _targetX,
    targetY: _targetY,
    data,
    selected,
  }: EdgeProps<ReturnMessageEdgeData & CalculatedPositions>) => {
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

    const edgeColor = selected ? colors.primary.main : "#9ca3af";
    const arrowSize = 10;

    return (
      <>
        {/* SVG for the dashed arrow line and open arrowhead */}
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
          {/* Dashed line */}
          <line
            x1={startX}
            y1={yPos}
            x2={endX - (isLeftToRight ? arrowSize : -arrowSize)}
            y2={yPos}
            stroke={edgeColor}
            strokeWidth={selected ? 2 : 1.5}
            strokeDasharray="6,4"
          />

          {/* Open arrowhead (classic UML return message) */}
          <polyline
            points={
              isLeftToRight
                ? `${endX - arrowSize},${yPos - arrowSize / 2} ${endX},${yPos} ${endX - arrowSize},${yPos + arrowSize / 2}`
                : `${endX + arrowSize},${yPos - arrowSize / 2} ${endX},${yPos} ${endX + arrowSize},${yPos + arrowSize / 2}`
            }
            fill="none"
            stroke={edgeColor}
            strokeWidth="1.5"
          />
        </svg>

        {/* Label above the line (only if there's a return value) */}
        {data?.returnValue && (
          <EdgeLabelRenderer>
            <div
              style={{
                position: "absolute",
                transform: `translate(-50%, -100%) translate(${midX}px,${yPos - 6}px)`,
                padding: "2px 6px",
                fontSize: "10px",
                fontStyle: "italic",
                color: colors.text.muted,
                pointerEvents: "all",
                whiteSpace: "nowrap",
                fontFamily: "monospace",
                backgroundColor: "rgba(255, 255, 255, 0.9)",
                borderRadius: "2px",
              }}
              className="nodrag nopan"
              title={`return ${data.returnValue} [line ${data.callSiteLine}]`}
            >
              {/* Sequence number badge */}
              <span
                style={{
                  backgroundColor: colors.gray[500],
                  color: "#fff",
                  borderRadius: "3px",
                  padding: "1px 4px",
                  marginRight: "4px",
                  fontSize: "9px",
                  fontWeight: 500,
                }}
              >
                {data.sequenceNumber}
              </span>
              {data.returnValue}
            </div>
          </EdgeLabelRenderer>
        )}
      </>
    );
  }
);

ReturnMessageEdge.displayName = "ReturnMessageEdge";
