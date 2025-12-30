/**
 * InterfaceNode - React Flow node for UML Interface.
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
import type { UmlInterfaceDef } from "../../../api/types";

const { colors, borders } = DESIGN_TOKENS;

const COLLAPSED_LIMIT = 5;

interface InterfaceNodeData {
  interface: UmlInterfaceDef;
  selected?: boolean;
}

// Standard UML handles for interfaces (4-directional)
const createInterfaceHandles = (): HandleConfig[] => [
  {
    id: "inheritance-target",
    type: "target",
    position: Position.Top,
    color: colors.callFlow.class,
    style: { top: "-5px" },
  },
  {
    id: "implementation-source",
    type: "source",
    position: Position.Bottom,
    color: colors.callFlow.class,
    style: { bottom: "-5px" },
  },
  {
    id: "association-target",
    type: "target",
    position: Position.Left,
    color: colors.callFlow.method,
    size: 8,
  },
  {
    id: "association-source",
    type: "source",
    position: Position.Right,
    color: colors.callFlow.method,
    size: 8,
  },
];

export const InterfaceNode = memo(({ data }: NodeProps<InterfaceNodeData>) => {
  const iface = data.interface;
  const isSelected = data.selected;

  // Expand/collapse state for methods
  const [methodsExpanded, setMethodsExpanded] = useState(false);

  const toggleMethods = useCallback((e: React.MouseEvent) => {
    e.stopPropagation();
    setMethodsExpanded((prev) => !prev);
  }, []);

  const header: NodeHeaderConfig = {
    icon: "I",
    label: "<<interface>>",
    backgroundColor: colors.callFlow.class,
  };

  const hasMoreMethods = iface.methods.length > COLLAPSED_LIMIT;
  const displayedMethods = methodsExpanded ? iface.methods : iface.methods.slice(0, COLLAPSED_LIMIT);

  return (
    <BaseGraphNode
      header={header}
      selected={isSelected}
      accentColor={colors.callFlow.class}
      handles={createInterfaceHandles()}
    >
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
          displayedMethods.map((method) => (
            <div key={method.id} style={{ lineHeight: "1.5" }}>
              <span style={{ color: colors.text.muted }}>+</span>
              {" "}{method.name}(): <span style={{ color: colors.callFlow.class }}>{method.returnType}</span>
            </div>
          ))
        )}
        {hasMoreMethods && (
          <button
            onClick={toggleMethods}
            style={{
              background: "none",
              border: "none",
              color: colors.callFlow.class,
              cursor: "pointer",
              fontSize: "11px",
              padding: "2px 0",
              marginTop: "2px",
              textDecoration: "underline",
            }}
          >
            {methodsExpanded
              ? "Show less"
              : `+${iface.methods.length - COLLAPSED_LIMIT} more...`}
          </button>
        )}
      </div>
    </BaseGraphNode>
  );
});

InterfaceNode.displayName = "InterfaceNode";
