/**
 * BaseGraphNode - Flexible container for graph nodes.
 *
 * Provides a consistent structure for both Call Flow and UML Editor nodes:
 * - Header with label and optional icon
 * - Badge area for indicators
 * - Content area for custom children
 * - Configurable handles
 */

import { memo, type ReactNode } from "react";
import { DESIGN_TOKENS } from "../../theme/designTokens";
import { NodeHandles } from "./NodeHandle";
import type { BaseGraphNodeProps, HandleConfig } from "./types";

const { colors, borders } = DESIGN_TOKENS;

/**
 * Default left/right handles for flow-based graphs (Call Flow).
 */
export function createFlowHandles(accentColor: string): HandleConfig[] {
  return [
    {
      id: "target",
      type: "target",
      position: "left" as any,
      color: accentColor,
    },
    {
      id: "source",
      type: "source",
      position: "right" as any,
      color: accentColor,
    },
  ];
}

/**
 * Default handles for UML-style nodes (4-directional).
 */
export function createUmlHandles(primaryColor: string, secondaryColor: string): HandleConfig[] {
  return [
    {
      id: "inheritance-target",
      type: "target",
      position: "top" as any,
      color: primaryColor,
      style: { top: "-5px" },
    },
    {
      id: "inheritance-source",
      type: "source",
      position: "bottom" as any,
      color: primaryColor,
      style: { bottom: "-5px" },
    },
    {
      id: "association-target",
      type: "target",
      position: "left" as any,
      color: secondaryColor,
      size: 8,
    },
    {
      id: "association-source",
      type: "source",
      position: "right" as any,
      color: secondaryColor,
      size: 8,
    },
  ];
}

export const BaseGraphNode = memo(function BaseGraphNode({
  header,
  badges,
  selected = false,
  accentColor,
  handles = [],
  children,
  className,
  style,
  minWidth = 200,
  maxWidth = 300,
}: BaseGraphNodeProps) {
  const headerBgColor = header.backgroundColor;
  const headerTextColor = header.textColor ?? colors.contrast.light;

  return (
    <div
      className={className}
      style={{
        minWidth: `${minWidth}px`,
        maxWidth: `${maxWidth}px`,
        backgroundColor: colors.base.card,
        border: selected
          ? `2px solid ${accentColor}`
          : `1px solid ${borders.default}`,
        borderRadius: "8px",
        overflow: "hidden",
        boxShadow: selected
          ? `0 0 12px ${accentColor}4D`
          : "0 2px 8px rgba(0,0,0,0.15)",
        ...style,
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: "8px 12px",
          backgroundColor: headerBgColor,
          color: headerTextColor,
          display: "flex",
          alignItems: "center",
          gap: "8px",
        }}
      >
        {header.icon && (
          <span style={{ fontSize: "12px", fontWeight: 700 }}>
            {header.icon}
          </span>
        )}
        <span style={{ fontSize: "13px", fontWeight: 600, flex: 1 }}>
          {header.label}
        </span>
        {header.subtitle && (
          <span style={{ fontSize: "10px", opacity: 0.8 }}>
            {header.subtitle}
          </span>
        )}
      </div>

      {/* Badges */}
      {badges && badges.length > 0 && (
        <div
          style={{
            display: "flex",
            flexWrap: "wrap",
            gap: "6px",
            padding: "8px 12px",
            borderBottom: children ? `1px solid ${borders.default}` : undefined,
          }}
        >
          {badges.map((badge, index) => (
            <div
              key={index}
              title={badge.title}
              style={{
                display: "inline-flex",
                alignItems: "center",
                fontSize: "11px",
                fontWeight: 500,
                padding: "2px 8px",
                borderRadius: "4px",
                backgroundColor: badge.bgColor,
                color: badge.color,
                boxShadow: badge.glow ? `0 0 8px ${badge.bgColor}` : undefined,
              }}
            >
              {badge.label}
            </div>
          ))}
        </div>
      )}

      {/* Content area */}
      {children}

      {/* Handles */}
      {handles.length > 0 && <NodeHandles handles={handles} />}
    </div>
  );
});

/**
 * Simple graph node variant without header (content-only).
 */
interface SimpleGraphNodeProps {
  children: ReactNode;
  selected?: boolean;
  accentColor: string;
  handles?: HandleConfig[];
  minWidth?: number;
  maxWidth?: number;
  style?: React.CSSProperties;
}

export const SimpleGraphNode = memo(function SimpleGraphNode({
  children,
  selected = false,
  accentColor,
  handles = [],
  minWidth = 200,
  maxWidth = 280,
  style,
}: SimpleGraphNodeProps) {
  return (
    <div
      style={{
        padding: "12px 16px",
        borderRadius: "8px",
        border: selected
          ? `3px solid ${accentColor}`
          : `2px solid ${accentColor}`,
        backgroundColor: colors.base.card,
        color: colors.text.secondary,
        minWidth: `${minWidth}px`,
        maxWidth: `${maxWidth}px`,
        boxShadow: selected
          ? `0 0 12px ${accentColor}4D`
          : "0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1)",
        ...style,
      }}
    >
      {children}
      {handles.length > 0 && <NodeHandles handles={handles} />}
    </div>
  );
});
