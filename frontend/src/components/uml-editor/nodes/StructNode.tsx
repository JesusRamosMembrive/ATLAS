/**
 * StructNode - React Flow node for UML Struct (C++ style).
 *
 * Uses shared graph-primitives for consistent styling.
 * Structs are data containers with public attributes by default.
 */

import { memo, useState, useCallback } from "react";
import { Position, type NodeProps } from "reactflow";
import { DESIGN_TOKENS } from "../../../theme/designTokens";
import {
  BaseGraphNode,
  type HandleConfig,
  type NodeHeaderConfig,
} from "../../graph-primitives";
import type { UmlStructDef } from "../../../api/types";

const { colors, borders } = DESIGN_TOKENS;

const COLLAPSED_LIMIT = 6;

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

  // Expand/collapse state for attributes
  const [attributesExpanded, setAttributesExpanded] = useState(false);

  const toggleAttributes = useCallback((e: React.MouseEvent) => {
    e.stopPropagation();
    setAttributesExpanded((prev) => !prev);
  }, []);

  const header: NodeHeaderConfig = {
    icon: "S",
    label: struct.name,
    backgroundColor: STRUCT_COLOR,
    subtitle: "struct",
  };

  const hasMoreAttributes = struct.attributes.length > COLLAPSED_LIMIT;
  const displayedAttributes = attributesExpanded ? struct.attributes : struct.attributes.slice(0, COLLAPSED_LIMIT);

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
          displayedAttributes.map((attr) => (
            <div key={attr.id} style={{ marginBottom: "2px" }}>
              <span style={{ color: colors.text.muted }}>{visibilitySymbol(attr.visibility)}</span>
              {" "}{attr.name}: <span style={{ color: STRUCT_COLOR }}>{attr.type}</span>
            </div>
          ))
        )}
        {hasMoreAttributes && (
          <button
            onClick={toggleAttributes}
            style={{
              background: "none",
              border: "none",
              color: STRUCT_COLOR,
              cursor: "pointer",
              fontSize: "11px",
              padding: "2px 0",
              marginTop: "4px",
              textDecoration: "underline",
            }}
          >
            {attributesExpanded
              ? "Show less"
              : `+${struct.attributes.length - COLLAPSED_LIMIT} more...`}
          </button>
        )}
      </div>
    </BaseGraphNode>
  );
});

StructNode.displayName = "StructNode";
