/**
 * ClassNode - React Flow node for UML Class.
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
import type { UmlClassDef } from "../../../api/types";

const { colors, borders } = DESIGN_TOKENS;

const COLLAPSED_LIMIT = 5;

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

  // Expand/collapse state for attributes and methods
  const [attributesExpanded, setAttributesExpanded] = useState(false);
  const [methodsExpanded, setMethodsExpanded] = useState(false);

  const toggleAttributes = useCallback((e: React.MouseEvent) => {
    e.stopPropagation();
    setAttributesExpanded((prev) => !prev);
  }, []);

  const toggleMethods = useCallback((e: React.MouseEvent) => {
    e.stopPropagation();
    setMethodsExpanded((prev) => !prev);
  }, []);

  // Build header with abstract indicator
  const header: NodeHeaderConfig = {
    icon: "C",
    label: cls.isAbstract
      ? `<<${cls.name}>>`
      : cls.name,
    backgroundColor: colors.primary.main,
    subtitle: cls.isAbstract ? "abstract" : undefined,
  };

  const hasMoreAttributes = cls.attributes.length > COLLAPSED_LIMIT;
  const hasMoreMethods = cls.methods.length > COLLAPSED_LIMIT;
  const displayedAttributes = attributesExpanded ? cls.attributes : cls.attributes.slice(0, COLLAPSED_LIMIT);
  const displayedMethods = methodsExpanded ? cls.methods : cls.methods.slice(0, COLLAPSED_LIMIT);

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
          displayedAttributes.map((attr) => (
            <div key={attr.id} style={{ lineHeight: "1.5" }}>
              <span style={{ color: colors.text.muted }}>{visibilitySymbol(attr.visibility)}</span>
              {" "}{attr.name}: <span style={{ color: colors.primary.main }}>{attr.type}</span>
              {attr.isStatic && <span style={{ color: colors.callFlow.method }}> [static]</span>}
            </div>
          ))
        )}
        {hasMoreAttributes && (
          <button
            onClick={toggleAttributes}
            style={{
              background: "none",
              border: "none",
              color: colors.primary.main,
              cursor: "pointer",
              fontSize: "11px",
              padding: "2px 0",
              marginTop: "2px",
              textDecoration: "underline",
            }}
          >
            {attributesExpanded
              ? "Show less"
              : `+${cls.attributes.length - COLLAPSED_LIMIT} more...`}
          </button>
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
          displayedMethods.map((method) => (
            <div key={method.id} style={{ lineHeight: "1.5" }}>
              <span style={{ color: colors.text.muted }}>{visibilitySymbol(method.visibility)}</span>
              {" "}{method.name}(): <span style={{ color: colors.callFlow.class }}>{method.returnType}</span>
              {method.isAsync && <span style={{ color: colors.callFlow.method }}> [async]</span>}
            </div>
          ))
        )}
        {hasMoreMethods && (
          <button
            onClick={toggleMethods}
            style={{
              background: "none",
              border: "none",
              color: colors.primary.main,
              cursor: "pointer",
              fontSize: "11px",
              padding: "2px 0",
              marginTop: "2px",
              textDecoration: "underline",
            }}
          >
            {methodsExpanded
              ? "Show less"
              : `+${cls.methods.length - COLLAPSED_LIMIT} more...`}
          </button>
        )}
      </div>
    </BaseGraphNode>
  );
});

ClassNode.displayName = "ClassNode";
