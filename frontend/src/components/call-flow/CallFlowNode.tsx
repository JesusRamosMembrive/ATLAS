import { memo } from "react";
import { Handle, Position, type NodeProps } from "reactflow";

interface CallFlowNodeData {
  label: string;
  qualifiedName: string;
  filePath?: string | null;
  line: number;
  kind: string;  // function | method | external | builtin
  isEntryPoint: boolean;
  depth: number;
  docstring?: string | null;
}

const KIND_COLORS = {
  function: "#3b82f6",   // blue
  method: "#10b981",     // green
  external: "#6b7280",   // gray
  builtin: "#f59e0b",    // amber
  class: "#a855f7",      // purple
} as const;

const KIND_LABELS = {
  function: "Function",
  method: "Method",
  external: "External",
  builtin: "Built-in",
  class: "Class",
} as const;

export const CallFlowNode = memo(({ data }: NodeProps<CallFlowNodeData>) => {
  const kind = data.kind as keyof typeof KIND_COLORS;
  const kindColor = KIND_COLORS[kind] || KIND_COLORS.function;
  const kindLabel = KIND_LABELS[kind] || data.kind;

  return (
    <div
      className="call-flow-node"
      style={{
        padding: "12px 16px",
        borderRadius: "8px",
        border: data.isEntryPoint ? `3px solid #f59e0b` : `2px solid ${kindColor}`,
        backgroundColor: "#1e293b",
        color: "#f1f5f9",
        minWidth: "200px",
        maxWidth: "280px",
        boxShadow: data.isEntryPoint
          ? "0 0 12px rgba(245, 158, 11, 0.3)"
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
              backgroundColor: "#f59e0b",
              color: "#000",
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
              color: "#94a3b8",
              lineHeight: "1.2",
              fontFamily: "monospace",
            }}
          >
            {data.qualifiedName}
          </div>
        )}

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
            color: "#fff",
            width: "fit-content",
          }}
        >
          {kindLabel}
        </div>

        {/* Location */}
        {data.filePath && (
          <div
            style={{
              fontSize: "10px",
              color: "#64748b",
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
              color: "#475569",
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
