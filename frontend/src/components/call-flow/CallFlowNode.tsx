import { memo } from "react";
import { Handle, Position, type NodeProps } from "reactflow";
import { DESIGN_TOKENS } from "../../theme/designTokens";

interface CallFlowNodeData {
  label: string;
  qualifiedName: string;
  filePath?: string | null;
  line: number;
  kind: string;  // function | method | external | builtin
  isEntryPoint: boolean;
  depth: number;
  docstring?: string | null;
  complexity?: number | null;  // Cyclomatic complexity (McCabe)
  loc?: number | null;         // Lines of code
}

const { colors, borders } = DESIGN_TOKENS;

const KIND_COLORS: Record<string, string> = {
  function: colors.callFlow.function,
  method: colors.callFlow.method,
  external: colors.callFlow.external,
  builtin: colors.callFlow.builtin,
  class: colors.callFlow.class,
};

const KIND_LABELS: Record<string, string> = {
  function: "Function",
  method: "Method",
  external: "External",
  builtin: "Built-in",
  class: "Class",
};

/**
 * Get color for cyclomatic complexity value.
 * Uses same thresholds as ComplexityCard for consistency.
 */
function getComplexityColor(value: number): string {
  if (value <= 5) return colors.complexity.low;
  if (value <= 10) return colors.complexity.medium;
  if (value <= 25) return colors.complexity.high;
  return colors.complexity.extreme;
}

export const CallFlowNode = memo(({ data }: NodeProps<CallFlowNodeData>) => {
  const kind = data.kind as keyof typeof KIND_COLORS;
  const kindColor = KIND_COLORS[kind] || KIND_COLORS.function;
  const kindLabel = KIND_LABELS[kind] || data.kind;
  const entryPointColor = colors.callFlow.entryPoint;

  return (
    <div
      className="call-flow-node"
      style={{
        padding: "12px 16px",
        borderRadius: "8px",
        border: data.isEntryPoint ? `3px solid ${entryPointColor}` : `2px solid ${kindColor}`,
        backgroundColor: colors.base.card,
        color: colors.text.secondary,
        minWidth: "200px",
        maxWidth: "280px",
        boxShadow: data.isEntryPoint
          ? `0 0 12px ${entryPointColor}4D` // 4D = 30% opacity in hex
          : "0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)",
      }}
    >
      <Handle
        type="target"
        position={Position.Left}
        style={{
          background: kindColor,
          width: "10px",
          height: "10px",
        }}
      />

      <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
        {/* Entry Point Badge */}
        {data.isEntryPoint && (
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              fontSize: "10px",
              fontWeight: 600,
              padding: "2px 8px",
              borderRadius: "4px",
              backgroundColor: entryPointColor,
              color: colors.contrast.dark,
              width: "fit-content",
              marginBottom: "4px",
            }}
          >
            ENTRY POINT
          </div>
        )}

        {/* Function/Method Name */}
        <div style={{ fontWeight: 600, fontSize: "14px", lineHeight: "1.2" }}>
          {data.label}
        </div>

        {/* Qualified Name (if different) */}
        {data.qualifiedName !== data.label && (
          <div
            style={{
              fontSize: "11px",
              color: colors.text.muted,
              lineHeight: "1.2",
              fontFamily: "monospace",
            }}
          >
            {data.qualifiedName}
          </div>
        )}

        {/* Kind and Complexity Badges */}
        <div style={{ display: "flex", gap: "6px", flexWrap: "wrap" }}>
          {/* Kind Badge */}
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              fontSize: "11px",
              fontWeight: 500,
              padding: "2px 8px",
              borderRadius: "4px",
              backgroundColor: kindColor,
              color: colors.contrast.light,
            }}
          >
            {kindLabel}
          </div>

          {/* Complexity Badge */}
          {data.complexity != null && (
            <div
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "4px",
                fontSize: "11px",
                fontWeight: 600,
                padding: "2px 8px",
                borderRadius: "4px",
                backgroundColor: getComplexityColor(data.complexity) + "20",
                color: getComplexityColor(data.complexity),
              }}
              title={`Cyclomatic Complexity: ${data.complexity}${data.loc ? ` | ${data.loc} lines` : ""}`}
            >
              <span style={{ fontWeight: 400 }}>CC</span>
              {data.complexity}
            </div>
          )}
        </div>

        {/* Location */}
        {data.filePath && (
          <div
            style={{
              fontSize: "10px",
              color: colors.gray[500],
              marginTop: "2px",
              fontFamily: "monospace",
              overflow: "hidden",
              textOverflow: "ellipsis",
              whiteSpace: "nowrap",
            }}
            title={`${data.filePath}:${data.line}`}
          >
            Line {data.line}
          </div>
        )}

        {/* Depth indicator for non-entry points */}
        {!data.isEntryPoint && data.depth > 0 && (
          <div
            style={{
              fontSize: "10px",
              color: colors.gray[600],
            }}
          >
            Depth: {data.depth}
          </div>
        )}
      </div>

      <Handle
        type="source"
        position={Position.Right}
        style={{
          background: kindColor,
          width: "10px",
          height: "10px",
        }}
      />
    </div>
  );
});

CallFlowNode.displayName = "CallFlowNode";
