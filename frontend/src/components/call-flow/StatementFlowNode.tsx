/**
 * StatementFlowNode - React Flow node for control flow statements in call flow.
 *
 * Renders statements like break, continue, pass, and raise that don't call
 * functions but still need to be shown to indicate what a branch does.
 * Ensures decision nodes are never "dead ends" visually.
 */

import { memo } from "react";
import { Handle, Position, type NodeProps } from "reactflow";
import { DESIGN_TOKENS } from "../../theme/designTokens";

interface StatementFlowNodeData {
  label: string;
  statementType: "break" | "continue" | "pass" | "raise" | "assignment";
  content: string;
  filePath?: string | null;
  line: number;
  column: number;
  parentCallId: string;
  branchId?: string;
  decisionId?: string;
  depth: number;
}

const { colors } = DESIGN_TOKENS;

// Colors for different statement types
const STATEMENT_COLORS: Record<string, { main: string; light: string; icon: string }> = {
  break: { main: "#f97316", light: "#fb923c", icon: "⏹" },      // orange - stop/exit
  continue: { main: "#8b5cf6", light: "#a78bfa", icon: "↩" },   // purple - loop back
  pass: { main: "#6b7280", light: "#9ca3af", icon: "⋯" },       // gray - do nothing
  raise: { main: "#ef4444", light: "#f87171", icon: "⚠" },      // red - error/exception
  assignment: { main: "#10b981", light: "#34d399", icon: "=" }, // green - set value
};

export const StatementFlowNode = memo(
  ({ data }: NodeProps<StatementFlowNodeData>) => {
    const colorScheme = STATEMENT_COLORS[data.statementType] || STATEMENT_COLORS.pass;

    // Truncate content if too long
    const displayContent =
      data.content.length > 40
        ? `${data.content.substring(0, 37)}...`
        : data.content;

    // Get label based on statement type
    const getLabel = () => {
      switch (data.statementType) {
        case "break":
          return "break";
        case "continue":
          return "continue";
        case "pass":
          return "pass";
        case "raise":
          return "raise";
        case "assignment":
          return "assign";
        default:
          return data.statementType;
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

        {/* Statement node container */}
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            padding: "10px 14px",
            background: `linear-gradient(135deg, ${colors.base.card}, ${colors.base.panel})`,
            border: `2px solid ${colorScheme.main}`,
            borderRadius: "12px",
            minWidth: "100px",
            maxWidth: "200px",
            boxShadow: `0 2px 8px ${colorScheme.main}30`,
          }}
        >
          {/* Statement type badge */}
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
            <span style={{ fontSize: "12px" }}>{colorScheme.icon}</span>
            <span
              style={{
                fontSize: "10px",
                fontWeight: 700,
                color: colorScheme.light,
                textTransform: "uppercase",
                letterSpacing: "0.5px",
              }}
            >
              {getLabel()}
            </span>
          </div>

          {/* Statement content (only show if different from type) */}
          {data.content !== data.statementType && (
            <div
              style={{
                fontSize: "11px",
                fontFamily: "monospace",
                fontWeight: 500,
                color: colors.text.main,
                textAlign: "center",
                wordBreak: "break-word",
                padding: "4px 0",
                maxWidth: "180px",
              }}
              title={data.content}
            >
              {displayContent}
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

StatementFlowNode.displayName = "StatementFlowNode";
