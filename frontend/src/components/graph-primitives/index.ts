/**
 * Graph Primitives - Shared components for Call Flow and UML Editor.
 *
 * This module provides reusable building blocks for graph-based visualizations.
 */

// Types
export type {
  BadgeConfig,
  HandleConfig,
  NodeHeaderConfig,
  BaseGraphNodeProps,
  BaseGraphEdgeProps,
  CommonNodeData,
} from "./types";

// Badge components
export {
  NodeBadge,
  EntryPointBadge,
  ComplexityBadge,
  KindBadge,
} from "./NodeBadge";

// Handle components
export { NodeHandle, NodeHandles } from "./NodeHandle";

// Node components
export {
  BaseGraphNode,
  SimpleGraphNode,
  createFlowHandles,
  createUmlHandles,
} from "./BaseGraphNode";

// Edge components
export {
  BaseGraphEdge,
  EdgeLabel,
  CallSiteLabel,
  RelationshipLabel,
} from "./BaseGraphEdge";
