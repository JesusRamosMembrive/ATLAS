/**
 * CallFlowEdge - React Flow edge for call graph visualization.
 *
 * Uses shared graph-primitives for consistent styling.
 */

import { type EdgeProps } from "reactflow";
import { DESIGN_TOKENS } from "../../theme/designTokens";
import { BaseGraphEdge, CallSiteLabel } from "../graph-primitives";

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

  return (
    <BaseGraphEdge
      id={id}
      sourceX={sourceX}
      sourceY={sourceY}
      targetX={targetX}
      targetY={targetY}
      sourcePosition={sourcePosition}
      targetPosition={targetPosition}
      color={edgeColor}
      markerEnd={markerEnd}
      labelContent={
        data?.callSiteLine ? (
          <CallSiteLabel line={data.callSiteLine} color={edgeColor} />
        ) : undefined
      }
    />
  );
}
