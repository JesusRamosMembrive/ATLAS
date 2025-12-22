/**
 * StructNode - React Flow node for UML Struct (C++ style)
 *
 * Structs are data containers with public attributes by default.
 * In other languages, they map to:
 * - Python: dataclass
 * - TypeScript: interface or type
 * - C++: struct
 */

import { memo } from "react";
import { Handle, Position, type NodeProps } from "reactflow";
import { DESIGN_TOKENS } from "../../../theme/designTokens";
import type { UmlStructDef } from "../../../api/types";

const { colors, borders } = DESIGN_TOKENS;

// Distinct color for structs (teal/cyan)
const STRUCT_COLOR = "#0891b2";

interface StructNodeData {
  struct: UmlStructDef;
  selected?: boolean;
}

export const StructNode = memo(({ data }: NodeProps<StructNodeData>) => {
  const struct = data.struct;
  const isSelected = data.selected;

  // Visibility symbols
  const visibilitySymbol = (v: string) => {
    switch (v) {
      case "private": return "-";
      case "protected": return "#";
      default: return "+";
    }
  };

  return (
    <div
      style={{
        minWidth: "180px",
        maxWidth: "280px",
        backgroundColor: colors.base.card,
        border: isSelected ? `2px solid ${STRUCT_COLOR}` : `1px solid ${borders.default}`,
        borderRadius: "8px",
        overflow: "hidden",
        boxShadow: isSelected
          ? `0 0 12px ${STRUCT_COLOR}4D`
          : "0 2px 8px rgba(0,0,0,0.15)",
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: "8px 12px",
          backgroundColor: STRUCT_COLOR,
          color: colors.contrast.light,
          display: "flex",
          alignItems: "center",
          gap: "8px",
        }}
      >
        <span style={{ fontSize: "12px", fontWeight: 700 }}>S</span>
        <span style={{ fontSize: "13px", fontWeight: 600, flex: 1 }}>
          {struct.name}
        </span>
        <span style={{ fontSize: "10px", opacity: 0.8 }}>struct</span>
      </div>

      {/* Attributes Section */}
      <div
        style={{
          padding: "8px 12px",
          fontSize: "11px",
          fontFamily: "monospace",
          color: colors.text.secondary,
          minHeight: "32px",
        }}
      >
        {struct.attributes.length === 0 ? (
          <span style={{ color: colors.text.muted, fontStyle: "italic" }}>No fields</span>
        ) : (
          struct.attributes.slice(0, 6).map((attr) => (
            <div key={attr.id} style={{ marginBottom: "2px" }}>
              <span style={{ color: colors.text.muted }}>{visibilitySymbol(attr.visibility)}</span>
              {" "}{attr.name}: <span style={{ color: STRUCT_COLOR }}>{attr.type}</span>
            </div>
          ))
        )}
        {struct.attributes.length > 6 && (
          <div style={{ color: colors.text.muted, marginTop: "4px" }}>
            ... +{struct.attributes.length - 6} more
          </div>
        )}
      </div>

      {/* Handles for connections */}
      <Handle
        type="target"
        position={Position.Top}
        style={{
          width: "10px",
          height: "10px",
          backgroundColor: STRUCT_COLOR,
          border: `2px solid ${colors.base.card}`,
        }}
      />
      <Handle
        type="source"
        position={Position.Bottom}
        style={{
          width: "10px",
          height: "10px",
          backgroundColor: STRUCT_COLOR,
          border: `2px solid ${colors.base.card}`,
        }}
      />
      <Handle
        type="source"
        position={Position.Right}
        id="right"
        style={{
          width: "8px",
          height: "8px",
          backgroundColor: colors.text.muted,
          border: `2px solid ${colors.base.card}`,
        }}
      />
      <Handle
        type="target"
        position={Position.Left}
        id="left"
        style={{
          width: "8px",
          height: "8px",
          backgroundColor: colors.text.muted,
          border: `2px solid ${colors.base.card}`,
        }}
      />
    </div>
  );
});

StructNode.displayName = "StructNode";
