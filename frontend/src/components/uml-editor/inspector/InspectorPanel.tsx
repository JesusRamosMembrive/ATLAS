/**
 * InspectorPanel - Right sidebar for editing selected UML entities
 *
 * Tabs:
 * - General: name, description, extends, implements
 * - Attributes: table of attributes (for classes)
 * - Methods: list of methods with full editor
 * - Preview: XML preview of the entity
 */

import { useState, useCallback, useEffect } from "react";
import { useUmlEditorStore } from "../../../state/useUmlEditorStore";
import { ClassInspector } from "./ClassInspector";
import { InterfaceInspector } from "./InterfaceInspector";
import { EnumInspector } from "./EnumInspector";
import { StructInspector } from "./StructInspector";
import { RelationshipInspector } from "./RelationshipInspector";
import { DESIGN_TOKENS } from "../../../theme/designTokens";

const { colors, borders } = DESIGN_TOKENS;

// Relationship color
const RELATIONSHIP_COLOR = "#9333ea";

// Distinct color for structs
const STRUCT_COLOR = "#0891b2";

type TabId = "general" | "attributes" | "methods" | "values" | "preview";

interface Tab {
  id: TabId;
  label: string;
  available: boolean;
}

export function InspectorPanel(): JSX.Element | null {
  const {
    selectedNodeId,
    selectedEdgeId,
    getSelectedEntity,
    getRelationshipById,
    clearSelection,
    deleteClass,
    deleteInterface,
    deleteEnum,
    deleteStruct,
    deleteRelationship,
  } = useUmlEditorStore();

  const [activeTab, setActiveTab] = useState<TabId>("general");
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

  const selectedEntity = getSelectedEntity();
  const selectedRelationship = selectedEdgeId ? getRelationshipById(selectedEdgeId) : null;

  // Determine entity type (always compute, even if null)
  const isClass = selectedEntity ? "attributes" in selectedEntity && "methods" in selectedEntity : false;
  const isInterface = selectedEntity ? "methods" in selectedEntity && !("attributes" in selectedEntity) : false;
  const isEnum = selectedEntity ? "values" in selectedEntity : false;
  const isStruct = selectedEntity ? "attributes" in selectedEntity && !("methods" in selectedEntity) && !("values" in selectedEntity) : false;

  // Handle entity deletion - must be defined before any return
  const handleDelete = useCallback(() => {
    if (!selectedNodeId) return;

    if (isClass) {
      deleteClass(selectedNodeId);
    } else if (isInterface) {
      deleteInterface(selectedNodeId);
    } else if (isEnum) {
      deleteEnum(selectedNodeId);
    } else if (isStruct) {
      deleteStruct(selectedNodeId);
    }
    clearSelection();
    setShowDeleteConfirm(false);
  }, [selectedNodeId, isClass, isInterface, isEnum, isStruct, deleteClass, deleteInterface, deleteEnum, deleteStruct, clearSelection]);

  // Define available tabs based on entity type
  const tabs: Tab[] = [
    { id: "general", label: "General", available: true },
    { id: "attributes", label: isStruct ? "Fields" : "Attributes", available: isClass || isStruct },
    { id: "methods", label: "Methods", available: isClass || isInterface },
    { id: "values", label: "Values", available: isEnum },
    { id: "preview", label: "Preview", available: true },
  ].filter((tab) => tab.available);

  // Reset to general tab if current tab is not available
  useEffect(() => {
    if (selectedEntity && !tabs.some((t) => t.id === activeTab)) {
      setActiveTab("general");
    }
  }, [selectedEntity, tabs, activeTab]);

  // Nothing selected
  if (!selectedNodeId && !selectedEdgeId) {
    return null;
  }

  // Relationship selected
  if (selectedEdgeId && selectedRelationship) {
    return (
      <div
        style={{
          width: "400px",
          borderLeft: `1px solid ${borders.default}`,
          backgroundColor: colors.base.card,
          display: "flex",
          flexDirection: "column",
          overflow: "hidden",
          flexShrink: 0,
        }}
      >
        {/* Header */}
        <div
          style={{
            padding: "12px 16px",
            borderBottom: `1px solid ${borders.default}`,
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            flexShrink: 0,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <span
              style={{
                fontSize: "11px",
                padding: "2px 8px",
                borderRadius: "4px",
                backgroundColor: RELATIONSHIP_COLOR,
                color: colors.contrast.light,
                fontWeight: 600,
              }}
            >
              Relationship
            </span>
            <span style={{ fontSize: "14px", fontWeight: 600, color: colors.text.secondary }}>
              {selectedRelationship.type}
            </span>
          </div>
          <div style={{ display: "flex", gap: "4px" }}>
            <button
              onClick={() => {
                deleteRelationship(selectedEdgeId);
                clearSelection();
              }}
              style={{
                border: "none",
                background: "transparent",
                color: colors.severity.error,
                cursor: "pointer",
                fontSize: "12px",
                padding: "4px 8px",
                borderRadius: "4px",
              }}
              title="Delete relationship"
            >
              Delete
            </button>
            <button
              onClick={clearSelection}
              style={{
                border: "none",
                background: "transparent",
                color: colors.text.muted,
                cursor: "pointer",
                fontSize: "18px",
                padding: "4px 8px",
                borderRadius: "4px",
              }}
              title="Close inspector"
            >
              x
            </button>
          </div>
        </div>

        {/* Content */}
        <div style={{ flex: 1, overflow: "auto", padding: "16px" }}>
          <RelationshipInspector relationshipId={selectedEdgeId} />
        </div>
      </div>
    );
  }

  // Entity selected but not found
  if (!selectedEntity) {
    return null;
  }

  const entityTypeLabel = isClass ? "Class" : isInterface ? "Interface" : isStruct ? "Struct" : "Enum";
  const entityColor = isClass ? colors.primary.main : isInterface ? colors.callFlow.class : isStruct ? STRUCT_COLOR : colors.callFlow.method;

  return (
    <div
      style={{
        width: "400px",
        borderLeft: `1px solid ${borders.default}`,
        backgroundColor: colors.base.card,
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
        flexShrink: 0,
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: "12px 16px",
          borderBottom: `1px solid ${borders.default}`,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          flexShrink: 0,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
          <span
            style={{
              fontSize: "11px",
              padding: "2px 8px",
              borderRadius: "4px",
              backgroundColor: entityColor,
              color: colors.contrast.light,
              fontWeight: 600,
            }}
          >
            {entityTypeLabel}
          </span>
          <span style={{ fontSize: "14px", fontWeight: 600, color: colors.text.secondary }}>
            {selectedEntity.name}
          </span>
        </div>
        <div style={{ display: "flex", gap: "4px" }}>
          <button
            onClick={() => setShowDeleteConfirm(true)}
            style={{
              border: "none",
              background: "transparent",
              color: colors.severity.error,
              cursor: "pointer",
              fontSize: "12px",
              padding: "4px 8px",
              borderRadius: "4px",
            }}
            title={`Delete ${entityTypeLabel.toLowerCase()}`}
          >
            Delete
          </button>
          <button
            onClick={clearSelection}
            style={{
              border: "none",
              background: "transparent",
              color: colors.text.muted,
              cursor: "pointer",
              fontSize: "18px",
              padding: "4px 8px",
              borderRadius: "4px",
            }}
            title="Close inspector"
          >
            x
          </button>
        </div>
      </div>

      {/* Delete Confirmation */}
      {showDeleteConfirm && (
        <div
          style={{
            padding: "12px 16px",
            backgroundColor: colors.severity.error + "20",
            borderBottom: `1px solid ${borders.default}`,
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: "12px",
          }}
        >
          <span style={{ fontSize: "13px", color: colors.text.secondary }}>
            Delete "{selectedEntity.name}"?
          </span>
          <div style={{ display: "flex", gap: "8px" }}>
            <button
              onClick={() => setShowDeleteConfirm(false)}
              style={{
                padding: "4px 12px",
                borderRadius: "4px",
                border: `1px solid ${borders.default}`,
                backgroundColor: "transparent",
                color: colors.text.muted,
                fontSize: "12px",
                cursor: "pointer",
              }}
            >
              Cancel
            </button>
            <button
              onClick={handleDelete}
              style={{
                padding: "4px 12px",
                borderRadius: "4px",
                border: "none",
                backgroundColor: colors.severity.error,
                color: colors.contrast.light,
                fontSize: "12px",
                fontWeight: 500,
                cursor: "pointer",
              }}
            >
              Delete
            </button>
          </div>
        </div>
      )}

      {/* Tabs */}
      <div
        style={{
          display: "flex",
          borderBottom: `1px solid ${borders.default}`,
          flexShrink: 0,
        }}
      >
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            style={{
              flex: 1,
              padding: "10px 12px",
              border: "none",
              borderBottom: activeTab === tab.id ? `2px solid ${entityColor}` : "2px solid transparent",
              backgroundColor: "transparent",
              color: activeTab === tab.id ? colors.text.secondary : colors.text.muted,
              fontSize: "12px",
              fontWeight: activeTab === tab.id ? 600 : 400,
              cursor: "pointer",
              transition: "all 0.15s",
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Content */}
      <div style={{ flex: 1, overflow: "auto", padding: "16px" }}>
        {isClass && selectedNodeId && (
          <ClassInspector
            classId={selectedNodeId}
            activeTab={activeTab}
          />
        )}
        {isInterface && selectedNodeId && (
          <InterfaceInspector
            interfaceId={selectedNodeId}
            activeTab={activeTab}
          />
        )}
        {isEnum && selectedNodeId && (
          <EnumInspector
            enumId={selectedNodeId}
            activeTab={activeTab}
          />
        )}
        {isStruct && selectedNodeId && (
          <StructInspector
            structId={selectedNodeId}
            activeTab={activeTab}
          />
        )}
      </div>
    </div>
  );
}
