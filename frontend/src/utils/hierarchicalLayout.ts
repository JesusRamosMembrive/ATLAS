/**
 * Hierarchical Layout Algorithm for UML Editor
 *
 * Organizes UML entities in a tree-like structure based on inheritance
 * and implementation relationships. Parent classes/interfaces at top,
 * children below.
 */

import type { UmlModuleDef, UmlRelationshipDef } from "../api/types";

/**
 * Layout direction options
 */
export type LayoutDirection = "TB" | "LR"; // Top-Bottom or Left-Right

/**
 * Layout configuration options
 */
export interface LayoutOptions {
  /** Direction of hierarchy flow */
  direction: LayoutDirection;
  /** Horizontal spacing between nodes on same level */
  nodeSpacing: number;
  /** Vertical spacing between hierarchy levels */
  levelSpacing: number;
  /** Starting X position */
  startX: number;
  /** Starting Y position */
  startY: number;
}

/**
 * Default layout options
 */
export const DEFAULT_LAYOUT_OPTIONS: LayoutOptions = {
  direction: "TB",
  nodeSpacing: 280,
  levelSpacing: 200,
  startX: 50,
  startY: 50,
};

/**
 * Position for a node
 */
export interface Position {
  x: number;
  y: number;
}

/**
 * Internal node representation for layout calculation
 */
interface LayoutNode {
  id: string;
  name: string;
  level: number;
  children: string[];
  parents: string[];
  subtreeWidth: number;
  position: Position;
}

/**
 * Apply hierarchical layout to all entities in a module.
 *
 * The algorithm:
 * 1. Build a directed graph from inheritance/implementation relationships
 * 2. Find root nodes (no parents)
 * 3. Assign levels via BFS from roots
 * 4. Calculate subtree widths bottom-up
 * 5. Position nodes level by level
 *
 * @param module The UML module containing entities and relationships
 * @param options Layout configuration
 * @param entityFilter Optional set of entity IDs to layout (for component filtering)
 * @returns Map of entity ID to position
 */
export function applyHierarchicalLayout(
  module: UmlModuleDef,
  options: Partial<LayoutOptions> = {},
  entityFilter?: Set<string>
): Map<string, Position> {
  const opts = { ...DEFAULT_LAYOUT_OPTIONS, ...options };

  // Collect all entity IDs and names
  const allEntities = [
    ...module.classes.map((c) => ({ id: c.id, name: c.name })),
    ...module.interfaces.map((i) => ({ id: i.id, name: i.name })),
    ...module.enums.map((e) => ({ id: e.id, name: e.name })),
    ...module.structs.map((s) => ({ id: s.id, name: s.name })),
  ];

  // Filter entities if a filter is provided
  const entities = entityFilter
    ? allEntities.filter((e) => entityFilter.has(e.id))
    : allEntities;

  if (entities.length === 0) {
    return new Map();
  }

  const entityIds = new Set(entities.map((e) => e.id));

  // Build parent-child relationships from inheritance/implementation
  const nodes = new Map<string, LayoutNode>();
  for (const entity of entities) {
    nodes.set(entity.id, {
      id: entity.id,
      name: entity.name,
      level: -1,
      children: [],
      parents: [],
      subtreeWidth: 1,
      position: { x: 0, y: 0 },
    });
  }

  // Filter relationships to only include those between filtered entities
  // and only inheritance/implementation types
  const hierarchyRelTypes = new Set(["inheritance", "implementation"]);
  const relevantRels = module.relationships.filter(
    (r) =>
      entityIds.has(r.from) &&
      entityIds.has(r.to) &&
      hierarchyRelTypes.has(r.type)
  );

  // In UML: "from" inherits/implements "to"
  // So "to" is the parent, "from" is the child
  for (const rel of relevantRels) {
    const parent = nodes.get(rel.to);
    const child = nodes.get(rel.from);
    if (parent && child) {
      parent.children.push(rel.from);
      child.parents.push(rel.to);
    }
  }

  // Find root nodes (no parents in the hierarchy)
  const roots: string[] = [];
  for (const [id, node] of nodes) {
    if (node.parents.length === 0) {
      roots.push(id);
    }
  }

  // If no roots found (cyclic or isolated), treat all as roots
  if (roots.length === 0) {
    for (const [id] of nodes) {
      roots.push(id);
    }
  }

  // Assign levels using BFS
  const visited = new Set<string>();
  const queue: Array<{ id: string; level: number }> = [];

  for (const rootId of roots) {
    queue.push({ id: rootId, level: 0 });
  }

  while (queue.length > 0) {
    const { id, level } = queue.shift()!;

    if (visited.has(id)) continue;
    visited.add(id);

    const node = nodes.get(id);
    if (!node) continue;

    node.level = level;

    for (const childId of node.children) {
      if (!visited.has(childId)) {
        queue.push({ id: childId, level: level + 1 });
      }
    }
  }

  // Handle any unvisited nodes (disconnected from hierarchy)
  let maxLevel = 0;
  for (const [, node] of nodes) {
    if (node.level > maxLevel) maxLevel = node.level;
  }

  for (const [, node] of nodes) {
    if (node.level === -1) {
      node.level = maxLevel + 1;
    }
  }

  // Group nodes by level
  const levelGroups = new Map<number, string[]>();
  for (const [id, node] of nodes) {
    if (!levelGroups.has(node.level)) {
      levelGroups.set(node.level, []);
    }
    levelGroups.get(node.level)!.push(id);
  }

  // Calculate subtree widths (bottom-up)
  const sortedLevels = [...levelGroups.keys()].sort((a, b) => b - a);
  for (const level of sortedLevels) {
    const nodeIds = levelGroups.get(level) ?? [];
    for (const id of nodeIds) {
      const node = nodes.get(id);
      if (!node) continue;

      if (node.children.length === 0) {
        node.subtreeWidth = 1;
      } else {
        let totalWidth = 0;
        for (const childId of node.children) {
          const child = nodes.get(childId);
          if (child) {
            totalWidth += child.subtreeWidth;
          }
        }
        node.subtreeWidth = Math.max(1, totalWidth);
      }
    }
  }

  // Position nodes
  const positions = new Map<string, Position>();

  // For TB: x varies by position in level, y varies by level
  // For LR: y varies by position in level, x varies by level
  const isVertical = opts.direction === "TB";

  // Calculate total width at each level for centering
  const levelWidths = new Map<number, number>();
  for (const [level, nodeIds] of levelGroups) {
    let totalWidth = 0;
    for (const id of nodeIds) {
      const node = nodes.get(id);
      if (node) {
        totalWidth += node.subtreeWidth;
      }
    }
    levelWidths.set(level, totalWidth);
  }

  // Position each level
  for (const level of [...levelGroups.keys()].sort((a, b) => a - b)) {
    const nodeIds = levelGroups.get(level) ?? [];
    const levelWidth = levelWidths.get(level) ?? 1;

    // Sort nodes within level by parent position for better alignment
    nodeIds.sort((aId, bId) => {
      const a = nodes.get(aId);
      const b = nodes.get(bId);
      if (!a || !b) return 0;

      // Prefer parent-ordered positioning
      if (a.parents.length > 0 && b.parents.length > 0) {
        const aParent = nodes.get(a.parents[0]);
        const bParent = nodes.get(b.parents[0]);
        if (aParent && bParent) {
          const aParentPos = isVertical ? aParent.position.x : aParent.position.y;
          const bParentPos = isVertical ? bParent.position.x : bParent.position.y;
          return aParentPos - bParentPos;
        }
      }
      return 0;
    });

    let currentOffset = 0;
    for (const id of nodeIds) {
      const node = nodes.get(id);
      if (!node) continue;

      // Calculate position
      const nodeCenter = currentOffset + node.subtreeWidth / 2;
      const primaryPos = opts.startX + nodeCenter * opts.nodeSpacing;
      const secondaryPos = opts.startY + level * opts.levelSpacing;

      if (isVertical) {
        node.position = { x: primaryPos, y: secondaryPos };
      } else {
        node.position = { x: secondaryPos, y: primaryPos };
      }

      positions.set(id, { ...node.position });
      currentOffset += node.subtreeWidth;
    }
  }

  // Second pass: center children under parents
  for (const level of [...levelGroups.keys()].sort((a, b) => a - b)) {
    const nodeIds = levelGroups.get(level) ?? [];
    for (const id of nodeIds) {
      const node = nodes.get(id);
      if (!node || node.children.length === 0) continue;

      // Calculate center of children
      let minChildPos = Infinity;
      let maxChildPos = -Infinity;
      for (const childId of node.children) {
        const child = nodes.get(childId);
        if (child) {
          const pos = isVertical ? child.position.x : child.position.y;
          minChildPos = Math.min(minChildPos, pos);
          maxChildPos = Math.max(maxChildPos, pos);
        }
      }

      if (minChildPos !== Infinity) {
        const childCenter = (minChildPos + maxChildPos) / 2;
        if (isVertical) {
          node.position.x = childCenter;
        } else {
          node.position.y = childCenter;
        }
        positions.set(id, { ...node.position });
      }
    }
  }

  return positions;
}

/**
 * Apply positions from a layout map to the module entities.
 * This doesn't modify the module directly - returns a callback to update the store.
 */
export function createPositionUpdater(
  positions: Map<string, Position>
): (updateEntityPosition: (id: string, position: Position) => void) => void {
  return (updateEntityPosition) => {
    for (const [id, position] of positions) {
      updateEntityPosition(id, position);
    }
  };
}

/**
 * Reset all entity positions to a simple grid layout.
 */
export function resetToGridLayout(
  module: UmlModuleDef,
  entityFilter?: Set<string>
): Map<string, Position> {
  const allEntities = [
    ...module.classes.map((c) => c.id),
    ...module.interfaces.map((i) => i.id),
    ...module.enums.map((e) => e.id),
    ...module.structs.map((s) => s.id),
  ];

  const entities = entityFilter
    ? allEntities.filter((id) => entityFilter.has(id))
    : allEntities;

  const positions = new Map<string, Position>();
  const columns = Math.ceil(Math.sqrt(entities.length));
  const spacing = 280;

  entities.forEach((id, index) => {
    const col = index % columns;
    const row = Math.floor(index / columns);
    positions.set(id, {
      x: 50 + col * spacing,
      y: 50 + row * 200,
    });
  });

  return positions;
}
