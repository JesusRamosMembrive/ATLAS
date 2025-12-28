/**
 * StructNode - React Flow node for UML Struct (C++ style).
 *
 * Uses shared graph-primitives for consistent styling.
 * Structs are data containers with public attributes by default.
 */

import { memo } from "react";
import { Position, type NodeProps } from "reactflow";
import { DESIGN_TOKENS } from "../../../theme/designTokens";
import {
  BaseGraphNode,
  type HandleConfig,
  type NodeHeaderConfig,
} from "../../graph-primitives";
import type { UmlStructDef } from "../../../api/types";

const { colors, borders } = DESIGN_TOKENS;

// Distinct color for structs (teal/cyan)
const STRUCT_COLOR = "#0891b2";

interface StructNodeData {
  struct: UmlStructDef;
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

// Standard UML handles for structs
const createStructHandles = (): HandleConfig[] => [
  {
    id: "inheritance-target",
    type: "target",
    position: Position.Top,
    color: STRUCT_COLOR,
    style: { border: `2px solid ${colors.base.card}` },
  },
  {
    id: "inheritance-source",
    type: "source",
    position: Position.Bottom,
    color: STRUCT_COLOR,
    style: { border: `2px solid ${colors.base.card}` },
  },
  {
    id: "left",
    type: "target",
    position: Position.Left,
    color: colors.text.muted,
    size: 8,
    style: { border: `2px solid ${colors.base.card}` },
  },
  {
    id: "right",
    type: "source",
    position: Position.Right,
    color: colors.text.muted,
    size: 8,
    style: { border: `2px solid ${colors.base.card}` },
  },
];

export const StructNode = memo(({ data }: NodeProps<StructNodeData>) => {
  const struct = data.struct;
  const isSelected = data.selected;

  const header: NodeHeaderConfig = {
    icon: "S",
    label: struct.name,
    backgroundColor: STRUCT_COLOR,
    subtitle: "struct",
  };

  return (
    <BaseGraphNode
      header={header}
      selected={isSelected}
      accentColor={STRUCT_COLOR}
      handles={createStructHandles()}
      minWidth={180}
      maxWidth={280}
    >
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
    </BaseGraphNode>
  );
});

StructNode.displayName = "StructNode";
