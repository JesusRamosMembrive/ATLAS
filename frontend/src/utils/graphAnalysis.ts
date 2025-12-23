/**
 * Graph Analysis Utilities for UML Editor
 *
 * Provides algorithms to analyze relationships between UML entities
 * and find connected components for better visualization organization.
 */

import type { UmlModuleDef, UmlRelationshipDef } from "../api/types";

/**
 * Represents a group of connected entities in the UML diagram.
 */
export interface ConnectedComponent {
  /** Unique identifier for this component */
  id: string;
  /** Display name (derived from the root/most connected entity) */
  name: string;
  /** IDs of all entities (classes, interfaces, enums, structs) in this component */
  entityIds: Set<string>;
  /** IDs of relationships within this component */
  relationshipIds: Set<string>;
  /** Number of entities in this component */
  size: number;
}

/**
 * Result of connected components analysis
 */
export interface ComponentsAnalysis {
  /** All connected components found (excluding isolated nodes) */
  components: ConnectedComponent[];
  /** Isolated component containing nodes with no relationships */
  isolated: ConnectedComponent | null;
  /** Total number of entities analyzed */
  totalEntities: number;
}

/**
 * Entity info for internal processing
 */
interface EntityInfo {
  id: string;
  name: string;
  type: "class" | "interface" | "enum" | "struct";
}

/**
 * Union-Find (Disjoint Set Union) data structure for efficient component detection
 */
class UnionFind {
  private parent: Map<string, string>;
  private rank: Map<string, number>;

  constructor(elements: string[]) {
    this.parent = new Map();
    this.rank = new Map();
    for (const el of elements) {
      this.parent.set(el, el);
      this.rank.set(el, 0);
    }
  }

  find(x: string): string {
    const parent = this.parent.get(x);
    if (parent === undefined) return x;
    if (parent !== x) {
      // Path compression
      const root = this.find(parent);
      this.parent.set(x, root);
      return root;
    }
    return x;
  }

  union(x: string, y: string): void {
    const rootX = this.find(x);
    const rootY = this.find(y);

    if (rootX === rootY) return;

    const rankX = this.rank.get(rootX) ?? 0;
    const rankY = this.rank.get(rootY) ?? 0;

    // Union by rank
    if (rankX < rankY) {
      this.parent.set(rootX, rootY);
    } else if (rankX > rankY) {
      this.parent.set(rootY, rootX);
    } else {
      this.parent.set(rootY, rootX);
      this.rank.set(rootX, rankX + 1);
    }
  }

  getGroups(): Map<string, string[]> {
    const groups = new Map<string, string[]>();
    for (const [element] of this.parent) {
      const root = this.find(element);
      if (!groups.has(root)) {
        groups.set(root, []);
      }
      groups.get(root)!.push(element);
    }
    return groups;
  }
}

/**
 * Find the "root" entity name for a component.
 * Prefers classes over interfaces, and entities with more connections.
 */
function findComponentRootName(
  entityIds: Set<string>,
  entityMap: Map<string, EntityInfo>,
  adjacency: Map<string, Set<string>>
): string {
  let bestEntity: EntityInfo | null = null;
  let bestScore = -1;

  for (const id of entityIds) {
    const entity = entityMap.get(id);
    if (!entity) continue;

    // Score: type priority + connection count
    let score = adjacency.get(id)?.size ?? 0;

    // Prefer classes over interfaces, interfaces over enums/structs
    if (entity.type === "class") score += 1000;
    else if (entity.type === "interface") score += 500;

    if (score > bestScore) {
      bestScore = score;
      bestEntity = entity;
    }
  }

  return bestEntity?.name ?? "Unknown";
}

/**
 * Analyze a UML module and find all connected components.
 *
 * Connected components are groups of entities that are linked through
 * relationships (inheritance, implementation, association, etc.).
 * Entities with no relationships are grouped into an "Isolated" component.
 */
export function findConnectedComponents(module: UmlModuleDef): ComponentsAnalysis {
  // Collect all entities
  const entities: EntityInfo[] = [
    ...module.classes.map((c) => ({ id: c.id, name: c.name, type: "class" as const })),
    ...module.interfaces.map((i) => ({ id: i.id, name: i.name, type: "interface" as const })),
    ...module.enums.map((e) => ({ id: e.id, name: e.name, type: "enum" as const })),
    ...module.structs.map((s) => ({ id: s.id, name: s.name, type: "struct" as const })),
  ];

  if (entities.length === 0) {
    return { components: [], isolated: null, totalEntities: 0 };
  }

  const entityMap = new Map<string, EntityInfo>();
  for (const entity of entities) {
    entityMap.set(entity.id, entity);
  }

  // Build adjacency list from relationships
  const adjacency = new Map<string, Set<string>>();
  const entityIds = new Set(entities.map((e) => e.id));

  for (const rel of module.relationships) {
    // Only consider relationships between entities that exist
    if (!entityIds.has(rel.from) || !entityIds.has(rel.to)) continue;

    if (!adjacency.has(rel.from)) adjacency.set(rel.from, new Set());
    if (!adjacency.has(rel.to)) adjacency.set(rel.to, new Set());

    adjacency.get(rel.from)!.add(rel.to);
    adjacency.get(rel.to)!.add(rel.from);
  }

  // Find connected entities (those with at least one relationship)
  const connectedEntityIds = new Set<string>();
  for (const [id, neighbors] of adjacency) {
    if (neighbors.size > 0) {
      connectedEntityIds.add(id);
      for (const neighbor of neighbors) {
        connectedEntityIds.add(neighbor);
      }
    }
  }

  // Use Union-Find to group connected entities
  const uf = new UnionFind([...connectedEntityIds]);

  for (const rel of module.relationships) {
    if (connectedEntityIds.has(rel.from) && connectedEntityIds.has(rel.to)) {
      uf.union(rel.from, rel.to);
    }
  }

  // Build components from Union-Find groups
  const groups = uf.getGroups();
  const components: ConnectedComponent[] = [];
  let componentIndex = 0;

  for (const [, memberIds] of groups) {
    if (memberIds.length === 0) continue;

    const entityIdsSet = new Set(memberIds);

    // Find relationships within this component
    const relationshipIds = new Set<string>();
    for (const rel of module.relationships) {
      if (entityIdsSet.has(rel.from) && entityIdsSet.has(rel.to)) {
        relationshipIds.add(rel.id);
      }
    }

    const name = findComponentRootName(entityIdsSet, entityMap, adjacency);

    components.push({
      id: `component-${componentIndex++}`,
      name,
      entityIds: entityIdsSet,
      relationshipIds,
      size: entityIdsSet.size,
    });
  }

  // Sort components by size (largest first)
  components.sort((a, b) => b.size - a.size);

  // Find isolated entities (no relationships)
  const isolatedIds = new Set<string>();
  for (const entity of entities) {
    if (!connectedEntityIds.has(entity.id)) {
      isolatedIds.add(entity.id);
    }
  }

  const isolated: ConnectedComponent | null =
    isolatedIds.size > 0
      ? {
          id: "isolated",
          name: "Isolated",
          entityIds: isolatedIds,
          relationshipIds: new Set(),
          size: isolatedIds.size,
        }
      : null;

  return {
    components,
    isolated,
    totalEntities: entities.length,
  };
}

/**
 * Get all entity IDs that belong to a specific component.
 * Returns all entities if componentId is null (show all).
 */
export function getEntitiesForComponent(
  module: UmlModuleDef,
  componentId: string | null,
  analysis: ComponentsAnalysis
): Set<string> {
  if (componentId === null) {
    // Return all entities
    return new Set([
      ...module.classes.map((c) => c.id),
      ...module.interfaces.map((i) => i.id),
      ...module.enums.map((e) => e.id),
      ...module.structs.map((s) => s.id),
    ]);
  }

  if (componentId === "isolated" && analysis.isolated) {
    return analysis.isolated.entityIds;
  }

  const component = analysis.components.find((c) => c.id === componentId);
  return component?.entityIds ?? new Set();
}

/**
 * Get all relationship IDs that belong to a specific component.
 */
export function getRelationshipsForComponent(
  componentId: string | null,
  analysis: ComponentsAnalysis,
  allRelationships: UmlRelationshipDef[]
): Set<string> {
  if (componentId === null) {
    // Return all relationships
    return new Set(allRelationships.map((r) => r.id));
  }

  if (componentId === "isolated") {
    // Isolated nodes have no relationships
    return new Set();
  }

  const component = analysis.components.find((c) => c.id === componentId);
  return component?.relationshipIds ?? new Set();
}
