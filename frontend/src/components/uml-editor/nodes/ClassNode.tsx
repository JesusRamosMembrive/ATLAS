/**
 * ClassNode - React Flow node for UML Class.
 *
 * Uses shared graph-primitives for consistent styling.
 */

import { memo } from "react";
import { Position, type NodeProps } from "reactflow";
import { DESIGN_TOKENS } from "../../../theme/designTokens";
import {
  BaseGraphNode,
  type HandleConfig,
  type NodeHeaderConfig,
} from "../../graph-primitives";
import type { UmlClassDef } from "../../../api/types";

const { colors, borders } = DESIGN_TOKENS;

interface ClassNodeData {
  class: UmlClassDef;
  selected?: boolean;
}

// Visibility symbols for UML notation
const visibilitySymbol = (v: string) => {
  switch (v) {
    case "private": return "-";
    case "protected": return "#";
    default: return "+";
  }
};

// Standard UML handles for classes (4-directional)
const createClassHandles = (): HandleConfig[] => [
  {
    id: "inheritance-target",
    type: "target",
    position: Position.Top,
    color: colors.primary.main,
    style: { top: "-5px" },
  },
  {
    id: "inheritance-source",
    type: "source",
    position: Position.Bottom,
    color: colors.primary.main,
    style: { bottom: "-5px" },
  },
  {
    id: "association-target",
    type: "target",
    position: Position.Left,
    color: colors.callFlow.class,
    size: 8,
  },
  {
    id: "association-source",
    type: "source",
    position: Position.Right,
    color: colors.callFlow.class,
    size: 8,
  },
];

export const ClassNode = memo(({ data }: NodeProps<ClassNodeData>) => {
  const cls = data.class;
  const isSelected = data.selected;

  // Build header with abstract indicator
  const header: NodeHeaderConfig = {
    icon: "C",
    label: cls.isAbstract
      ? `<<${cls.name}>>`
      : cls.name,
    backgroundColor: colors.primary.main,
    subtitle: cls.isAbstract ? "abstract" : undefined,
  };

  return (
    <BaseGraphNode
      header={header}
      selected={isSelected}
      accentColor={colors.primary.main}
      handles={createClassHandles()}
    >
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
    </BaseGraphNode>
  );
});

ClassNode.displayName = "ClassNode";
