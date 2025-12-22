/**
 * EnumNode - React Flow node for UML Enum
 */

import { memo } from "react";
import { Handle, Position, type NodeProps } from "reactflow";
import { DESIGN_TOKENS } from "../../../theme/designTokens";
import type { UmlEnumDef } from "../../../api/types";

const { colors, borders } = DESIGN_TOKENS;

interface EnumNodeData {
  enum: UmlEnumDef;
  selected?: boolean;
}

export const EnumNode = memo(({ data }: NodeProps<EnumNodeData>) => {
  const enm = data.enum;
  const isSelected = data.selected;

  return (
    <div
      style={{
        minWidth: "160px",
        maxWidth: "240px",
        backgroundColor: colors.base.card,
        border: isSelected ? `2px solid ${colors.callFlow.method}` : `1px solid ${borders.default}`,
        borderRadius: "8px",
        overflow: "hidden",
        boxShadow: isSelected
          ? `0 0 12px ${colors.callFlow.method}4D`
          : "0 2px 8px rgba(0,0,0,0.15)",
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: "8px 12px",
          backgroundColor: colors.callFlow.method,
          color: colors.contrast.light,
          display: "flex",
          alignItems: "center",
          gap: "8px",
        }}
      >
        <span style={{ fontSize: "12px", fontWeight: 700 }}>E</span>
        <span style={{ fontSize: "13px", fontWeight: 600, flex: 1 }}>
          <em style={{ fontWeight: 400 }}>{"<<"}</em>
          enum
          <em style={{ fontWeight: 400 }}>{">>"}</em>
        </span>
      </div>

      {/* Enum Name */}
      <div
        style={{
          padding: "6px 12px",
          borderBottom: `1px solid ${borders.default}`,
          fontSize: "14px",
          fontWeight: 600,
          color: colors.text.secondary,
          textAlign: "center",
        }}
      >
        {enm.name}
      </div>

      {/* Values Section */}
      <div
        style={{
          padding: "6px 12px",
          fontSize: "11px",
          fontFamily: "monospace",
          color: colors.text.secondary,
          minHeight: "24px",
        }}
      >
        {enm.values.length === 0 ? (
          <span style={{ color: colors.text.muted, fontStyle: "italic" }}>No values</span>
        ) : (
          enm.values.slice(0, 6).map((val, idx) => (
            <div key={idx} style={{ lineHeight: "1.5" }}>
              {val.name}
              {val.value !== null && (
                <span style={{ color: colors.text.muted }}> = {val.value}</span>
              )}
            </div>
          ))
        )}
        {enm.values.length > 6 && (
          <div style={{ color: colors.text.muted, fontStyle: "italic" }}>
            +{enm.values.length - 6} more...
          </div>
        )}
      </div>

      {/* Handles for connections (enums are typically used as types) */}
      <Handle
        type="target"
        position={Position.Left}
        id="usage-target"
        style={{
          background: colors.callFlow.method,
          width: "8px",
          height: "8px",
        }}
      />
      <Handle
        type="source"
        position={Position.Right}
        id="usage-source"
        style={{
          background: colors.callFlow.method,
          width: "8px",
          height: "8px",
        }}
      />
    </div>
  );
});

EnumNode.displayName = "EnumNode";
