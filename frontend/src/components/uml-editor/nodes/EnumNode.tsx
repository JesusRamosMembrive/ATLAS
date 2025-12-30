/**
 * EnumNode - React Flow node for UML Enum.
 *
 * Uses shared graph-primitives for consistent styling.
 */

import { memo, useState, useCallback } from "react";
import { Position, type NodeProps } from "reactflow";
import { DESIGN_TOKENS } from "../../../theme/designTokens";
import {
  BaseGraphNode,
  type HandleConfig,
  type NodeHeaderConfig,
} from "../../graph-primitives";
import type { UmlEnumDef } from "../../../api/types";

const { colors, borders } = DESIGN_TOKENS;

const COLLAPSED_LIMIT = 6;

interface EnumNodeData {
  enum: UmlEnumDef;
  selected?: boolean;
}

// Enum handles (simpler, typically used as types)
const createEnumHandles = (): HandleConfig[] => [
  {
    id: "usage-target",
    type: "target",
    position: Position.Left,
    color: colors.callFlow.method,
    size: 8,
  },
  {
    id: "usage-source",
    type: "source",
    position: Position.Right,
    color: colors.callFlow.method,
    size: 8,
  },
];

export const EnumNode = memo(({ data }: NodeProps<EnumNodeData>) => {
  const enm = data.enum;
  const isSelected = data.selected;

  // Expand/collapse state for values
  const [valuesExpanded, setValuesExpanded] = useState(false);

  const toggleValues = useCallback((e: React.MouseEvent) => {
    e.stopPropagation();
    setValuesExpanded((prev) => !prev);
  }, []);

  const header: NodeHeaderConfig = {
    icon: "E",
    label: "<<enum>>",
    backgroundColor: colors.callFlow.method,
  };

  const hasMoreValues = enm.values.length > COLLAPSED_LIMIT;
  const displayedValues = valuesExpanded ? enm.values : enm.values.slice(0, COLLAPSED_LIMIT);

  return (
    <BaseGraphNode
      header={header}
      selected={isSelected}
      accentColor={colors.callFlow.method}
      handles={createEnumHandles()}
      minWidth={160}
      maxWidth={240}
    >
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
          displayedValues.map((val, idx) => (
            <div key={idx} style={{ lineHeight: "1.5" }}>
              {val.name}
              {val.value !== null && (
                <span style={{ color: colors.text.muted }}> = {val.value}</span>
              )}
            </div>
          ))
        )}
        {hasMoreValues && (
          <button
            onClick={toggleValues}
            style={{
              background: "none",
              border: "none",
              color: colors.callFlow.method,
              cursor: "pointer",
              fontSize: "11px",
              padding: "2px 0",
              marginTop: "2px",
              textDecoration: "underline",
            }}
          >
            {valuesExpanded
              ? "Show less"
              : `+${enm.values.length - COLLAPSED_LIMIT} more...`}
          </button>
        )}
      </div>
    </BaseGraphNode>
  );
});

EnumNode.displayName = "EnumNode";
