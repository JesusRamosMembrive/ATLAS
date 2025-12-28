/**
 * NodeHandle - Styled handle component for graph nodes.
 *
 * Provides consistent handle styling across Call Flow and UML Editor.
 */

import { memo } from "react";
import { Handle, type HandleProps } from "reactflow";
import type { HandleConfig } from "./types";

interface NodeHandleProps extends Omit<HandleProps, "id" | "type" | "position"> {
  config: HandleConfig;
}

/**
 * Single styled handle based on configuration.
 */
export const NodeHandle = memo(function NodeHandle({
  config,
  ...rest
}: NodeHandleProps) {
  const size = config.size ?? 10;

  return (
    <Handle
      id={config.id}
      type={config.type}
      position={config.position}
      style={{
        background: config.color,
        width: `${size}px`,
        height: `${size}px`,
        borderRadius: "50%",
        ...config.style,
      }}
      {...rest}
    />
  );
});

interface NodeHandlesProps {
  /** Array of handle configurations */
  handles: HandleConfig[];
}

/**
 * Renders multiple handles from configuration array.
 */
export const NodeHandles = memo(function NodeHandles({
  handles,
}: NodeHandlesProps) {
  return (
    <>
      {handles.map((config) => (
        <NodeHandle key={config.id} config={config} />
      ))}
    </>
  );
});
