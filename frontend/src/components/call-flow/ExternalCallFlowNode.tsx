/**
 * ExternalCallFlowNode - React Flow node for external library calls in call flow.
 *
 * Renders external calls (builtin, stdlib, third-party) that were previously
 * "ignored" but still need to be shown to indicate what a branch does.
 * Ensures decision nodes are never "dead ends" visually.
 */

import { memo } from "react";
import { Handle, Position, type NodeProps } from "reactflow";
import { DESIGN_TOKENS } from "../../theme/designTokens";

interface ExternalCallFlowNodeData {
  label: string;
  expression: string;
  callType: "builtin" | "stdlib" | "third_party";
  moduleHint?: string | null;
  filePath?: string | null;
  line: number;
  column: number;
  parentCallId: string;
  branchId?: string;
  decisionId?: string;
  depth: number;
}

const { colors } = DESIGN_TOKENS;

// Colors for different external call types
const CALL_TYPE_COLORS: Record<string, { main: string; light: string; icon: string }> = {
  builtin: { main: "#3b82f6", light: "#60a5fa", icon: "fn" },       // blue - Python builtins
  stdlib: { main: "#6366f1", light: "#818cf8", icon: "lib" },       // indigo - standard library
  third_party: { main: "#8b5cf6", light: "#a78bfa", icon: "pkg" },  // purple - external packages
};

export const ExternalCallFlowNode = memo(
  ({ data }: NodeProps<ExternalCallFlowNodeData>) => {
    const colorScheme = CALL_TYPE_COLORS[data.callType] || CALL_TYPE_COLORS.third_party;

    // Extract just the function name from the expression for display
    // e.g., "session.get(url)" -> "session.get"
    const extractName = (expr: string): string => {
      // Remove everything from the first parenthesis
      const withoutArgs = expr.split("(")[0];
      return withoutArgs;
    };

    const displayName = extractName(data.expression);
    const truncatedName = displayName.length > 25
      ? `${displayName.substring(0, 22)}...`
      : displayName;

    // Get label based on call type
    const getTypeLabel = () => {
      switch (data.callType) {
        case "builtin":
          return "BUILTIN";
        case "stdlib":
          return "STDLIB";
        case "third_party":
          return "EXTERNAL";
        default:
          return "EXTERNAL";
      }
    };

    return (
      <>
        {/* Handles for connections - both positions for layout flexibility */}
        <Handle
          type="target"
          position={Position.Left}
          id="target-left"
          style={{
            background: colorScheme.main,
            border: `2px solid ${colorScheme.light}`,
            width: 10,
            height: 10,
          }}
        />
        <Handle
          type="target"
          position={Position.Top}
          id="target-top"
          style={{
            background: colorScheme.main,
            border: `2px solid ${colorScheme.light}`,
            width: 10,
            height: 10,
          }}
        />

        {/* External call node container */}
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            padding: "10px 14px",
            background: `linear-gradient(135deg, ${colors.base.card}, ${colors.base.panel})`,
            border: `2px dashed ${colorScheme.main}`,  // Dashed border to distinguish from regular nodes
            borderRadius: "12px",
            minWidth: "100px",
            maxWidth: "220px",
            boxShadow: `0 2px 8px ${colorScheme.main}20`,
            opacity: 0.9,  // Slightly transparent to show it's "external"
          }}
        >
          {/* Type badge with icon */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "6px",
              padding: "2px 10px",
              background: `${colorScheme.main}25`,
              borderRadius: "10px",
              marginBottom: "6px",
            }}
          >
            <span
              style={{
                fontSize: "9px",
                fontWeight: 700,
                fontFamily: "monospace",
                color: colorScheme.light,
              }}
            >
              {colorScheme.icon}
            </span>
            <span
              style={{
                fontSize: "9px",
                fontWeight: 700,
                color: colorScheme.light,
                textTransform: "uppercase",
                letterSpacing: "0.5px",
              }}
            >
              {getTypeLabel()}
            </span>
          </div>

          {/* Function name */}
          <div
            style={{
              fontSize: "11px",
              fontFamily: "monospace",
              fontWeight: 600,
              color: colors.text.main,
              textAlign: "center",
              wordBreak: "break-word",
              padding: "4px 0",
              maxWidth: "200px",
            }}
            title={data.expression}
          >
            {truncatedName}
          </div>

          {/* Module hint if available */}
          {data.moduleHint && (
            <div
              style={{
                fontSize: "9px",
                color: colorScheme.light,
                fontFamily: "monospace",
                marginTop: "2px",
              }}
            >
              {data.moduleHint}
            </div>
          )}

          {/* Line number */}
          <div
            style={{
              fontSize: "9px",
              color: colors.gray[500],
              fontFamily: "monospace",
              marginTop: "4px",
            }}
          >
            Line {data.line}
          </div>
        </div>
      </>
    );
  }
);

ExternalCallFlowNode.displayName = "ExternalCallFlowNode";
