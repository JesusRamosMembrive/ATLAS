/**
 * Template Layout Engine - Position calculation for design pattern templates
 *
 * Handles positioning of template entities to avoid overlaps with existing content
 * and arrange entities in a logical layout based on layout hints.
 */

import type { TemplateLayoutHint } from "../config/designPatternTemplates";

export interface LayoutConfig {
  /** Starting X position */
  startX: number;
  /** Starting Y position */
  startY: number;
  /** Horizontal spacing between columns */
  colSpacing: number;
  /** Vertical spacing between rows */
  rowSpacing: number;
}

const DEFAULT_LAYOUT_CONFIG: LayoutConfig = {
  startX: 100,
  startY: 100,
  colSpacing: 280, // Account for typical class node width (~200px) + margin
  rowSpacing: 220, // Account for typical class node height (~150px) + margin
};

/**
 * Calculate absolute positions from layout hints
 */
export function calculatePositions(
  layoutHints: TemplateLayoutHint[],
  config: Partial<LayoutConfig> = {}
): Map<string, { x: number; y: number }> {
  const { startX, startY, colSpacing, rowSpacing } = {
    ...DEFAULT_LAYOUT_CONFIG,
    ...config,
  };

  const positions = new Map<string, { x: number; y: number }>();

  for (const hint of layoutHints) {
    positions.set(hint.key, {
      x: startX + hint.col * colSpacing,
      y: startY + hint.row * rowSpacing,
    });
  }

  return positions;
}

/**
 * Get the bounding box of a template based on layout hints
 */
export function getTemplateBounds(layoutHints: TemplateLayoutHint[]): {
  rows: number;
  cols: number;
} {
  if (layoutHints.length === 0) {
    return { rows: 1, cols: 1 };
  }

  const maxRow = Math.max(...layoutHints.map((h) => h.row));
  const maxCol = Math.max(...layoutHints.map((h) => h.col));

  return {
    rows: maxRow + 1,
    cols: maxCol + 1,
  };
}

/**
 * Find an empty area on the canvas to place a template
 * Avoids overlapping with existing entities
 */
export function findEmptyArea(
  existingPositions: Array<{ x: number; y: number }>,
  templateSize: { rows: number; cols: number },
  config: Partial<LayoutConfig> = {}
): { x: number; y: number } {
  const { startX, startY, colSpacing } = {
    ...DEFAULT_LAYOUT_CONFIG,
    ...config,
  };

  // If no existing entities, start at default position
  if (existingPositions.length === 0) {
    return { x: startX, y: startY };
  }

  // Find the rightmost entity
  const maxX = Math.max(...existingPositions.map((p) => p.x));

  // Calculate average Y position for vertical centering
  const avgY = existingPositions.reduce((sum, p) => sum + p.y, 0) / existingPositions.length;

  // Place template to the right of existing content with extra spacing
  return {
    x: maxX + colSpacing * 1.5,
    y: Math.max(startY, avgY),
  };
}

/**
 * Calculate required canvas dimensions for a template
 */
export function getTemplateCanvasDimensions(
  layoutHints: TemplateLayoutHint[],
  config: Partial<LayoutConfig> = {}
): { width: number; height: number } {
  const { colSpacing, rowSpacing } = {
    ...DEFAULT_LAYOUT_CONFIG,
    ...config,
  };

  const bounds = getTemplateBounds(layoutHints);

  return {
    width: bounds.cols * colSpacing + 200, // Extra padding for node width
    height: bounds.rows * rowSpacing + 150, // Extra padding for node height
  };
}
