/**
 * BranchFlowEdge - React Flow edge for branch connections in call flow.
 *
 * Uses dashed lines for unexpanded branches, solid for expanded.
 */

import { type EdgeProps, getSmoothStepPath } from "reactflow";
import { DESIGN_TOKENS } from "../../theme/designTokens";

interface BranchFlowEdgeData {
  branchId: string;
  branchLabel?: string;
  isExpanded?: boolean;
  callCount?: number;
  callSiteLine?: number;
  callType?: string;  // "statement" | "external" | etc.
}

const { colors } = DESIGN_TOKENS;

const getBranchColor = (label: string, isExpanded: boolean): string => {
  if (isExpanded) return colors.callFlow.branchExpanded;

  const lowerLabel = label.toLowerCase();
  if (lowerLabel === "true") return colors.callFlow.branchTrue;
  if (lowerLabel === "false") return colors.callFlow.branchFalse;
  if (lowerLabel.startsWith("except")) return colors.callFlow.branchExcept;
  if (lowerLabel.startsWith("case")) return colors.callFlow.branchCase;
  return colors.callFlow.branchUnexpanded;
};

export function BranchFlowEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  data,
  markerEnd,
}: EdgeProps<BranchFlowEdgeData>) {
  const isExpanded = data?.isExpanded ?? false;
  const branchLabel = data?.branchLabel ?? "";
  const callSiteLine = data?.callSiteLine;
  const edgeColor = getBranchColor(branchLabel, isExpanded);

  // Determine what label to show:
  // - If we have a callSiteLine (for statement/external edges), show "L{line}"
  // - Otherwise show the branch label (for branch toggle edges)
  const displayLabel = callSiteLine ? `L${callSiteLine}` : branchLabel;
  const hasLabel = displayLabel.length > 0;

  const [edgePath, labelX, labelY] = getSmoothStepPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
    borderRadius: 8,
  });

  return (
    <>
      {/* Main edge path */}
      <path
        id={id}
        className="react-flow__edge-path"
        d={edgePath}
        markerEnd={markerEnd}
        style={{
          stroke: edgeColor,
          strokeWidth: isExpanded ? 2 : 1.5,
          strokeDasharray: isExpanded ? "none" : "5,5",
          fill: "none",
          transition: "all 0.3s ease",
        }}
      />

      {/* Edge label - only show if there's something to display */}
      {hasLabel && (
        <foreignObject
          width={80}
          height={24}
          x={labelX - 40}
          y={labelY - 12}
          className="edgebutton-foreignobject"
          requiredExtensions="http://www.w3.org/1999/xhtml"
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              width: "100%",
              height: "100%",
            }}
          >
            <div
              style={{
                padding: "2px 8px",
                background: `${edgeColor}20`,
                border: `1px solid ${edgeColor}`,
                borderRadius: "4px",
                fontSize: "9px",
                fontWeight: 600,
                color: edgeColor,
                whiteSpace: "nowrap",
                display: "flex",
                alignItems: "center",
                gap: "4px",
              }}
            >
              <span>{displayLabel}</span>
              {!isExpanded && !callSiteLine && (
                <span
                  style={{
                    fontSize: "8px",
                    opacity: 0.7,
                  }}
                >
                  ?
                </span>
              )}
            </div>
          </div>
        </foreignObject>
      )}
    </>
  );
}
