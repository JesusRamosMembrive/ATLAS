/**
 * InterfaceNode - React Flow node for UML Interface
 */

import { memo } from "react";
import { Handle, Position, type NodeProps } from "reactflow";
import { DESIGN_TOKENS } from "../../../theme/designTokens";
import type { UmlInterfaceDef } from "../../../api/types";

const { colors, borders } = DESIGN_TOKENS;

interface InterfaceNodeData {
  interface: UmlInterfaceDef;
  selected?: boolean;
}

export const InterfaceNode = memo(({ data }: NodeProps<InterfaceNodeData>) => {
  const iface = data.interface;
  const isSelected = data.selected;

  return (
    <div
      style={{
        minWidth: "200px",
        maxWidth: "300px",
        backgroundColor: colors.base.card,
        border: isSelected ? `2px solid ${colors.callFlow.class}` : `1px solid ${borders.default}`,
        borderRadius: "8px",
        overflow: "hidden",
        boxShadow: isSelected
          ? `0 0 12px ${colors.callFlow.class}4D`
          : "0 2px 8px rgba(0,0,0,0.15)",
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: "8px 12px",
          backgroundColor: colors.callFlow.class,
          color: colors.contrast.light,
          display: "flex",
          alignItems: "center",
          gap: "8px",
        }}
      >
        <span style={{ fontSize: "12px", fontWeight: 700 }}>I</span>
        <span style={{ fontSize: "13px", fontWeight: 600, flex: 1 }}>
          <em style={{ fontWeight: 400 }}>{"<<"}</em>
          interface
          <em style={{ fontWeight: 400 }}>{">>"}</em>
        </span>
      </div>

      {/* Interface Name */}
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
        {iface.name}
      </div>

      {/* Methods Section */}
      <div
        style={{
          padding: "6px 12px",
          fontSize: "11px",
          fontFamily: "monospace",
          color: colors.text.secondary,
          minHeight: "24px",
        }}
      >
        {iface.methods.length === 0 ? (
          <span style={{ color: colors.text.muted, fontStyle: "italic" }}>No methods</span>
        ) : (
          iface.methods.slice(0, 5).map((method) => (
            <div key={method.id} style={{ lineHeight: "1.5" }}>
              <span style={{ color: colors.text.muted }}>+</span>
              {" "}{method.name}(): <span style={{ color: colors.callFlow.class }}>{method.returnType}</span>
            </div>
          ))
        )}
        {iface.methods.length > 5 && (
          <div style={{ color: colors.text.muted, fontStyle: "italic" }}>
            +{iface.methods.length - 5} more...
          </div>
        )}
      </div>

      {/* Handles for connections */}
      <Handle
        type="target"
        position={Position.Top}
        id="inheritance-target"
        style={{
          background: colors.callFlow.class,
          width: "10px",
          height: "10px",
          top: "-5px",
        }}
      />
      <Handle
        type="source"
        position={Position.Bottom}
        id="implementation-source"
        style={{
          background: colors.callFlow.class,
          width: "10px",
          height: "10px",
          bottom: "-5px",
        }}
      />
      <Handle
        type="target"
        position={Position.Left}
        id="association-target"
        style={{
          background: colors.callFlow.method,
          width: "8px",
          height: "8px",
        }}
      />
      <Handle
        type="source"
        position={Position.Right}
        id="association-source"
        style={{
          background: colors.callFlow.method,
          width: "8px",
          height: "8px",
        }}
      />
    </div>
  );
});

InterfaceNode.displayName = "InterfaceNode";
