import {
  BaseEdge,
  EdgeLabelRenderer,
  getBezierPath,
  type EdgeProps,
} from "reactflow";
import { DESIGN_TOKENS } from "../../theme/designTokens";

interface CallFlowEdgeData {
  callSiteLine: number;
  callType: string;  // direct | method | super | static
}

const { colors } = DESIGN_TOKENS;

const CALL_TYPE_COLORS: Record<string, string> = {
  direct: colors.callFlow.direct,
  method: colors.callFlow.methodCall,
  super: colors.callFlow.superCall,
  static: colors.callFlow.staticCall,
};

export function CallFlowEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  data,
  markerEnd,
}: EdgeProps<CallFlowEdgeData>) {
  const callType = (data?.callType || "direct") as keyof typeof CALL_TYPE_COLORS;
  const edgeColor = CALL_TYPE_COLORS[callType] || CALL_TYPE_COLORS.direct;

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
          stroke: edgeColor,
          strokeWidth: 2,
          strokeOpacity: 0.8,
        }}
      />
      {data?.callSiteLine && (
        <EdgeLabelRenderer>
          <div
            style={{
              position: "absolute",
              transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)`,
              fontSize: "10px",
              fontWeight: 500,
              padding: "2px 6px",
              borderRadius: "4px",
              backgroundColor: colors.base.card,
              color: colors.callFlow.edgeLabel,
              border: `1px solid ${edgeColor}`,
              pointerEvents: "all",
            }}
            className="nodrag nopan"
          >
            L{data.callSiteLine}
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  );
}
