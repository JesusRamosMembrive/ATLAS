/**
 * CallFlowNode - React Flow node for call graph visualization.
 *
 * Uses shared graph-primitives for consistent styling.
 */

import { memo } from "react";
import { Position, type NodeProps } from "reactflow";
import { DESIGN_TOKENS } from "../../theme/designTokens";
import {
  SimpleGraphNode,
  EntryPointBadge,
  KindBadge,
  ComplexityBadge,
  type HandleConfig,
} from "../graph-primitives";

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

const { colors } = DESIGN_TOKENS;

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

export const CallFlowNode = memo(({ data }: NodeProps<CallFlowNodeData>) => {
  const kind = data.kind as keyof typeof KIND_COLORS;
  const kindColor = KIND_COLORS[kind] || KIND_COLORS.function;
  const kindLabel = KIND_LABELS[kind] || data.kind;
  const entryPointColor = colors.callFlow.entryPoint;

  // Configure handles with accent color
  const handles: HandleConfig[] = [
    {
      id: "target",
      type: "target",
      position: Position.Left,
      color: kindColor,
    },
    {
      id: "source",
      type: "source",
      position: Position.Right,
      color: kindColor,
    },
  ];

  return (
    <SimpleGraphNode
      selected={data.isEntryPoint}
      accentColor={data.isEntryPoint ? entryPointColor : kindColor}
      handles={handles}
      style={{
        boxShadow: data.isEntryPoint
          ? `0 0 12px ${entryPointColor}4D`
          : "0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)",
      }}
    >
      <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
        {/* Entry Point Badge */}
        {data.isEntryPoint && (
          <div style={{ marginBottom: "4px" }}>
            <EntryPointBadge />
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
          <KindBadge kind={kindLabel} color={kindColor} />

          {data.complexity != null && (
            <ComplexityBadge complexity={data.complexity} loc={data.loc} />
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
    </SimpleGraphNode>
  );
});

CallFlowNode.displayName = "CallFlowNode";
