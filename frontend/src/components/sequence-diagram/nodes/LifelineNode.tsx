/**
 * LifelineNode - React Flow node for sequence diagram lifelines.
 *
 * Classic UML style: Header box at top with vertical dashed line below.
 * Represents a participant (class/module/object) in the sequence diagram.
 */

import { memo } from "react";
import { Position, Handle, type NodeProps } from "reactflow";
import { DESIGN_TOKENS } from "../../../theme/designTokens";
import type { SequenceParticipantType } from "../../../api/types";

const { colors } = DESIGN_TOKENS;

interface LifelineNodeData {
  name: string;
  qualifiedName: string;
  participantType: SequenceParticipantType;
  filePath: string | null;
  line: number;
  isEntryPoint: boolean;
  order: number;
  lifelineHeight?: number;
}

// Colors for different participant types - softer palette
const PARTICIPANT_COLORS: Record<SequenceParticipantType, string> = {
  class: "#7c3aed",      // Purple
  object: "#8b5cf6",     // Violet
  actor: "#f59e0b",      // Amber
  boundary: "#10b981",   // Green
  control: "#6366f1",    // Indigo
  entity: "#ec4899",     // Pink
  module: "#64748b",     // Slate
};

// Icons for participant types
const PARTICIPANT_ICONS: Record<SequenceParticipantType, string> = {
  class: "C",
  object: "O",
  actor: "A",
  boundary: "B",
  control: "K",
  entity: "E",
  module: "M",
};

// Extract filename from path
function getFileName(filePath: string | null): string | null {
  if (!filePath) return null;
  const parts = filePath.split("/");
  return parts[parts.length - 1];
}

export const LifelineNode = memo(({ data, selected }: NodeProps<LifelineNodeData>) => {
  const accentColor = PARTICIPANT_COLORS[data.participantType] || PARTICIPANT_COLORS.class;
  const icon = PARTICIPANT_ICONS[data.participantType] || "?";
  const lifelineHeight = data.lifelineHeight || 400;
  const fileName = getFileName(data.filePath);

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        position: "relative",
      }}
    >
      {/* Classic UML Header Box */}
      <div
        style={{
          backgroundColor: colors.base.card,
          border: `2px solid ${data.isEntryPoint ? colors.callFlow.entryPoint : accentColor}`,
          borderRadius: "4px",
          padding: "8px 12px",
          minWidth: "120px",
          maxWidth: "180px",
          textAlign: "center",
          boxShadow: selected
            ? `0 0 0 3px ${accentColor}30`
            : "0 2px 6px rgba(0, 0, 0, 0.15)",
          position: "relative",
          zIndex: 10,
          cursor: "pointer",
        }}
        title={`${data.qualifiedName}\n${data.filePath || "External"}`}
      >
        {/* Entry Point indicator */}
        {data.isEntryPoint && (
          <div
            style={{
              position: "absolute",
              top: "-10px",
              left: "50%",
              transform: "translateX(-50%)",
              backgroundColor: colors.callFlow.entryPoint,
              color: "white",
              fontSize: "9px",
              fontWeight: 600,
              padding: "2px 8px",
              borderRadius: "10px",
              textTransform: "uppercase",
              letterSpacing: "0.5px",
            }}
          >
            Entry
          </div>
        )}

        {/* Type icon badge */}
        <div
          style={{
            position: "absolute",
            top: "-8px",
            right: "-8px",
            width: "18px",
            height: "18px",
            borderRadius: "50%",
            backgroundColor: accentColor,
            color: "white",
            fontSize: "10px",
            fontWeight: 700,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            border: "2px solid " + colors.base.card,
          }}
          title={data.participantType}
        >
          {icon}
        </div>

        {/* Object name in UML notation: :ClassName */}
        <div
          style={{
            fontWeight: 600,
            fontSize: "12px",
            color: colors.text.main,
            fontFamily: "monospace",
            whiteSpace: "nowrap",
            overflow: "hidden",
            textOverflow: "ellipsis",
          }}
        >
          :{data.name}
        </div>

        {/* File name (if available) */}
        {fileName && (
          <div
            style={{
              fontSize: "9px",
              color: colors.text.muted,
              fontFamily: "monospace",
              marginTop: "2px",
              whiteSpace: "nowrap",
              overflow: "hidden",
              textOverflow: "ellipsis",
            }}
          >
            {fileName}
          </div>
        )}
      </div>

      {/* Vertical Dashed Lifeline */}
      <svg
        width="2"
        height={lifelineHeight}
        style={{
          marginTop: "-1px",
          overflow: "visible",
        }}
      >
        <line
          x1="1"
          y1="0"
          x2="1"
          y2={lifelineHeight}
          stroke={colors.gray[400]}
          strokeWidth="2"
          strokeDasharray="8,6"
        />
      </svg>

      {/* Hidden handles for React Flow edge connections */}
      <Handle
        type="source"
        position={Position.Bottom}
        id="bottom"
        style={{ opacity: 0, pointerEvents: "none" }}
      />
      <Handle
        type="target"
        position={Position.Top}
        id="top"
        style={{ opacity: 0, pointerEvents: "none" }}
      />
    </div>
  );
});

LifelineNode.displayName = "LifelineNode";
