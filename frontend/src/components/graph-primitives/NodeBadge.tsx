/**
 * NodeBadge - Reusable badge component for graph nodes.
 *
 * Used by both Call Flow and UML Editor for displaying:
 * - Entry point indicators
 * - Kind/type badges
 * - Complexity indicators
 * - Abstract/static markers
 */

import { memo } from "react";
import { DESIGN_TOKENS } from "../../theme/designTokens";
import type { BadgeConfig } from "./types";

const { colors } = DESIGN_TOKENS;

interface NodeBadgeProps extends BadgeConfig {
  /** Font size in pixels (default: 11) */
  fontSize?: number;
  /** Font weight (default: 500) */
  fontWeight?: number;
  /** Additional CSS classes */
  className?: string;
}

export const NodeBadge = memo(function NodeBadge({
  label,
  color,
  bgColor,
  title,
  glow = false,
  fontSize = 11,
  fontWeight = 500,
  className,
}: NodeBadgeProps) {
  return (
    <div
      className={className}
      title={title}
      style={{
        display: "inline-flex",
        alignItems: "center",
        fontSize: `${fontSize}px`,
        fontWeight,
        padding: "2px 8px",
        borderRadius: "4px",
        backgroundColor: bgColor,
        color,
        boxShadow: glow ? `0 0 8px ${bgColor}` : undefined,
        whiteSpace: "nowrap",
      }}
    >
      {label}
    </div>
  );
});

/**
 * Entry point badge with glow effect.
 */
export const EntryPointBadge = memo(function EntryPointBadge() {
  const entryPointColor = colors.callFlow.entryPoint;

  return (
    <NodeBadge
      label="ENTRY POINT"
      color={colors.contrast.dark}
      bgColor={entryPointColor}
      fontSize={10}
      fontWeight={600}
      glow
    />
  );
});

/**
 * Complexity badge with color-coded severity.
 */
interface ComplexityBadgeProps {
  /** Cyclomatic complexity value */
  complexity: number;
  /** Optional lines of code for tooltip */
  loc?: number | null;
}

export const ComplexityBadge = memo(function ComplexityBadge({
  complexity,
  loc,
}: ComplexityBadgeProps) {
  const getComplexityColor = (value: number): string => {
    if (value <= 5) return colors.complexity.low;
    if (value <= 10) return colors.complexity.medium;
    if (value <= 25) return colors.complexity.high;
    return colors.complexity.extreme;
  };

  const complexityColor = getComplexityColor(complexity);
  const title = `Cyclomatic Complexity: ${complexity}${loc ? ` | ${loc} lines` : ""}`;

  return (
    <div
      title={title}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "4px",
        fontSize: "11px",
        fontWeight: 600,
        padding: "2px 8px",
        borderRadius: "4px",
        backgroundColor: `${complexityColor}20`,
        color: complexityColor,
      }}
    >
      <span style={{ fontWeight: 400 }}>CC</span>
      {complexity}
    </div>
  );
});

/**
 * Kind/type badge (function, method, class, etc.).
 */
interface KindBadgeProps {
  /** The kind label to display */
  kind: string;
  /** Background color for the badge */
  color: string;
  /** Optional custom text color (default: light contrast) */
  textColor?: string;
}

export const KindBadge = memo(function KindBadge({
  kind,
  color,
  textColor = colors.contrast.light,
}: KindBadgeProps) {
  return (
    <NodeBadge
      label={kind}
      color={textColor}
      bgColor={color}
      fontSize={11}
      fontWeight={500}
    />
  );
});
