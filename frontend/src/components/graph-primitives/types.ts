/**
 * Shared types for graph primitives used by Call Flow and UML Editor.
 */

import type { Position } from "reactflow";

/**
 * Configuration for a single badge displayed on a node.
 */
export interface BadgeConfig {
  /** Text to display */
  label: string;
  /** Text color */
  color: string;
  /** Background color */
  bgColor: string;
  /** Optional title for tooltip */
  title?: string;
  /** Optional glow effect (e.g., for entry points) */
  glow?: boolean;
}

/**
 * Configuration for a node handle (connection point).
 */
export interface HandleConfig {
  /** Unique ID for the handle */
  id: string;
  /** Type of handle: target (input) or source (output) */
  type: "target" | "source";
  /** Position on the node */
  position: Position;
  /** Handle color */
  color: string;
  /** Handle size in pixels (default: 10) */
  size?: number;
  /** Optional style overrides */
  style?: React.CSSProperties;
}

/**
 * Configuration for node header section.
 */
export interface NodeHeaderConfig {
  /** Main label text */
  label: string;
  /** Background color for the header */
  backgroundColor: string;
  /** Text color (default: white) */
  textColor?: string;
  /** Optional icon/prefix (e.g., "C" for class, "I" for interface) */
  icon?: string;
  /** Optional subtitle or secondary text */
  subtitle?: string;
}

/**
 * Base props for graph node components.
 */
export interface BaseGraphNodeProps {
  /** Header configuration */
  header: NodeHeaderConfig;
  /** Optional badges to display */
  badges?: BadgeConfig[];
  /** Whether the node is currently selected */
  selected?: boolean;
  /** Accent color for selection border */
  accentColor: string;
  /** Handle configurations */
  handles?: HandleConfig[];
  /** Content to render inside the node body */
  children?: React.ReactNode;
  /** Optional CSS class name */
  className?: string;
  /** Optional inline styles */
  style?: React.CSSProperties;
  /** Min width of the node (default: 200px) */
  minWidth?: number;
  /** Max width of the node (default: 300px) */
  maxWidth?: number;
}

/**
 * Base props for graph edge components.
 */
export interface BaseGraphEdgeProps {
  /** Edge ID from React Flow */
  id: string;
  /** Source X coordinate */
  sourceX: number;
  /** Source Y coordinate */
  sourceY: number;
  /** Target X coordinate */
  targetX: number;
  /** Target Y coordinate */
  targetY: number;
  /** Source position */
  sourcePosition: Position;
  /** Target position */
  targetPosition: Position;
  /** Edge color */
  color: string;
  /** Whether the edge is dashed */
  isDashed?: boolean;
  /** Stroke width (default: 2) */
  strokeWidth?: number;
  /** Label content to render */
  labelContent?: React.ReactNode;
  /** Marker end URL */
  markerEnd?: string;
  /** Whether the edge is selected */
  selected?: boolean;
  /** Optional style overrides */
  style?: React.CSSProperties;
}

/**
 * Common node data interface for consistent typing across graphs.
 */
export interface CommonNodeData {
  /** Display label */
  label: string;
  /** Whether the node is selected */
  selected?: boolean;
}
