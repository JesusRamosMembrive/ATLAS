/**
 * ClassNode - React Flow node for UML Class
 */

import { memo } from "react";
import { Handle, Position, type NodeProps } from "reactflow";
import { DESIGN_TOKENS } from "../../../theme/designTokens";
import type { UmlClassDef } from "../../../api/types";

const { colors, borders } = DESIGN_TOKENS;

interface ClassNodeData {
  class: UmlClassDef;
  selected?: boolean;
}

export const ClassNode = memo(({ data }: NodeProps<ClassNodeData>) => {
  const cls = data.class;
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
        minWidth: "200px",
        maxWidth: "300px",
        backgroundColor: colors.base.card,
        border: isSelected ? `2px solid ${colors.primary.main}` : `1px solid ${borders.default}`,
        borderRadius: "8px",
        overflow: "hidden",
        boxShadow: isSelected
          ? `0 0 12px ${colors.primary.main}4D`
          : "0 2px 8px rgba(0,0,0,0.15)",
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: "8px 12px",
          backgroundColor: colors.primary.main,
          color: colors.contrast.light,
          display: "flex",
          alignItems: "center",
          gap: "8px",
        }}
      >
        <span style={{ fontSize: "12px", fontWeight: 700 }}>C</span>
        <span style={{ fontSize: "13px", fontWeight: 600, flex: 1 }}>
          {cls.isAbstract && <em style={{ fontWeight: 400 }}>{"<<"}</em>}
          {cls.name}
          {cls.isAbstract && <em style={{ fontWeight: 400 }}>{">>"}</em>}
        </span>
        {cls.isAbstract && (
          <span style={{ fontSize: "10px", opacity: 0.8 }}>abstract</span>
        )}
      </div>

      {/* Attributes Section */}
      <div
        style={{
          padding: "6px 12px",
          borderBottom: `1px solid ${borders.default}`,
          fontSize: "11px",
          fontFamily: "monospace",
          color: colors.text.secondary,
          minHeight: "24px",
        }}
      >
        {cls.attributes.length === 0 ? (
          <span style={{ color: colors.text.muted, fontStyle: "italic" }}>No attributes</span>
        ) : (
          cls.attributes.slice(0, 5).map((attr) => (
            <div key={attr.id} style={{ lineHeight: "1.5" }}>
              <span style={{ color: colors.text.muted }}>{visibilitySymbol(attr.visibility)}</span>
              {" "}{attr.name}: <span style={{ color: colors.primary.main }}>{attr.type}</span>
              {attr.isStatic && <span style={{ color: colors.callFlow.method }}> [static]</span>}
            </div>
          ))
        )}
        {cls.attributes.length > 5 && (
          <div style={{ color: colors.text.muted, fontStyle: "italic" }}>
            +{cls.attributes.length - 5} more...
          </div>
        )}
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
        {cls.methods.length === 0 ? (
          <span style={{ color: colors.text.muted, fontStyle: "italic" }}>No methods</span>
        ) : (
          cls.methods.slice(0, 5).map((method) => (
            <div key={method.id} style={{ lineHeight: "1.5" }}>
              <span style={{ color: colors.text.muted }}>{visibilitySymbol(method.visibility)}</span>
              {" "}{method.name}(): <span style={{ color: colors.callFlow.class }}>{method.returnType}</span>
              {method.isAsync && <span style={{ color: colors.callFlow.method }}> [async]</span>}
            </div>
          ))
        )}
        {cls.methods.length > 5 && (
          <div style={{ color: colors.text.muted, fontStyle: "italic" }}>
            +{cls.methods.length - 5} more...
          </div>
        )}
      </div>

      {/* Handles for connections */}
      <Handle
        type="target"
        position={Position.Top}
        id="inheritance-target"
        style={{
          background: colors.primary.main,
          width: "10px",
          height: "10px",
          top: "-5px",
        }}
      />
      <Handle
        type="source"
        position={Position.Bottom}
        id="inheritance-source"
        style={{
          background: colors.primary.main,
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
          background: colors.callFlow.class,
          width: "8px",
          height: "8px",
        }}
      />
      <Handle
        type="source"
        position={Position.Right}
        id="association-source"
        style={{
          background: colors.callFlow.class,
          width: "8px",
          height: "8px",
        }}
      />
    </div>
  );
});

ClassNode.displayName = "ClassNode";
