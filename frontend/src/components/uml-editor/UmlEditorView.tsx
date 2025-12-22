/**
 * UML Editor View - Main page for AEGIS v2 Model-Driven Development
 *
 * This is the entry point for the UML Editor feature.
 * Layout: Toolbar | Canvas | Inspector Panel
 */

import { useCallback, useState, useMemo } from "react";
import { ReactFlowProvider } from "reactflow";
import { useUmlEditorStore } from "../../state/useUmlEditorStore";
import { UmlEditorCanvas } from "./UmlEditorCanvas";
import { InspectorPanel } from "./inspector";
import { ValidationPanel } from "./validation";
import { ExportDialog } from "./toolbar";
import { DESIGN_TOKENS } from "../../theme/designTokens";
import {
  LANGUAGE_CONFIG,
  getEntityDisplayName,
  getIncompatibleEntities,
  type EntityType,
} from "../../config/languageConfig";
import type { UmlTargetLanguage } from "../../api/types";

const { colors, borders } = DESIGN_TOKENS;

// Struct color
const STRUCT_COLOR = "#0891b2";

export function UmlEditorView(): JSX.Element {
  const {
    project,
    isDirty,
    addClass,
    addInterface,
    addEnum,
    addStruct,
    getCurrentModule,
    resetProject,
    updateProjectMeta,
  } = useUmlEditorStore();

  const currentModule = getCurrentModule();
  const currentLanguage = project.targetLanguage;

  const [isExportDialogOpen, setExportDialogOpen] = useState(false);
  const [isValidationExpanded, setValidationExpanded] = useState(false);
  const [pendingLanguageChange, setPendingLanguageChange] = useState<UmlTargetLanguage | null>(null);

  // Count entities by type for language change warnings
  const entityCounts = useMemo((): Record<EntityType, number> => {
    if (!currentModule) {
      return { class: 0, interface: 0, enum: 0, struct: 0 };
    }
    return {
      class: currentModule.classes.length,
      interface: currentModule.interfaces.length,
      enum: currentModule.enums.length,
      struct: currentModule.structs.length,
    };
  }, [currentModule]);

  // Get entity names for current language
  const entityNames = useMemo(() => ({
    class: getEntityDisplayName(currentLanguage, "class"),
    interface: getEntityDisplayName(currentLanguage, "interface"),
    enum: getEntityDisplayName(currentLanguage, "enum"),
    struct: getEntityDisplayName(currentLanguage, "struct"),
  }), [currentLanguage]);

  // Calculate center position for new nodes
  const getNewNodePosition = useCallback(() => {
    const baseX = 100 + Math.random() * 200;
    const baseY = 100 + Math.random() * 200;
    return { x: baseX, y: baseY };
  }, []);

  const handleAddClass = useCallback(() => {
    addClass(getNewNodePosition());
  }, [addClass, getNewNodePosition]);

  const handleAddInterface = useCallback(() => {
    addInterface(getNewNodePosition());
  }, [addInterface, getNewNodePosition]);

  const handleAddEnum = useCallback(() => {
    addEnum(getNewNodePosition());
  }, [addEnum, getNewNodePosition]);

  const handleAddStruct = useCallback(() => {
    addStruct(getNewNodePosition());
  }, [addStruct, getNewNodePosition]);

  const handleExport = useCallback(() => {
    setExportDialogOpen(true);
  }, []);

  // Handle language change with warning
  const handleLanguageChange = useCallback((newLanguage: UmlTargetLanguage) => {
    if (newLanguage === currentLanguage) return;

    const incompatible = getIncompatibleEntities(currentLanguage, newLanguage, entityCounts);

    if (incompatible.length > 0) {
      // Show confirmation dialog
      setPendingLanguageChange(newLanguage);
    } else {
      // No incompatibilities, change directly
      updateProjectMeta({ targetLanguage: newLanguage });
    }
  }, [currentLanguage, entityCounts, updateProjectMeta]);

  const confirmLanguageChange = useCallback(() => {
    if (pendingLanguageChange) {
      updateProjectMeta({ targetLanguage: pendingLanguageChange });
      setPendingLanguageChange(null);
    }
  }, [pendingLanguageChange, updateProjectMeta]);

  const cancelLanguageChange = useCallback(() => {
    setPendingLanguageChange(null);
  }, []);

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "calc(100vh - 200px)",
        minHeight: "500px",
        backgroundColor: colors.base.panel,
        color: colors.text.secondary,
      }}
    >
      {/* Toolbar */}
      <div
        style={{
          padding: "12px 24px",
          borderBottom: `1px solid ${borders.default}`,
          backgroundColor: colors.base.card,
          display: "flex",
          alignItems: "center",
          gap: "16px",
        }}
      >
        {/* Project Name (editable) */}
        <input
          type="text"
          value={project.name}
          onChange={(e) => updateProjectMeta({ name: e.target.value })}
          style={{
            fontSize: "14px",
            fontWeight: 600,
            padding: "4px 8px",
            borderRadius: "4px",
            border: `1px solid transparent`,
            backgroundColor: "transparent",
            color: colors.text.secondary,
            outline: "none",
            minWidth: "120px",
            maxWidth: "200px",
          }}
          onFocus={(e) => {
            e.target.style.border = `1px solid ${colors.primary.main}`;
            e.target.style.backgroundColor = colors.base.panel;
          }}
          onBlur={(e) => {
            e.target.style.border = `1px solid transparent`;
            e.target.style.backgroundColor = "transparent";
          }}
          title="Click to edit project name"
        />

        {/* Language Selector */}
        <select
          value={project.targetLanguage}
          onChange={(e) => handleLanguageChange(e.target.value as UmlTargetLanguage)}
          style={{
            padding: "4px 8px",
            borderRadius: "4px",
            border: `1px solid ${borders.default}`,
            backgroundColor: colors.base.panel,
            color: colors.text.secondary,
            fontSize: "12px",
            cursor: "pointer",
            outline: "none",
          }}
          title="Target language"
        >
          <option value="python">{LANGUAGE_CONFIG.python.name}</option>
          <option value="typescript">{LANGUAGE_CONFIG.typescript.name}</option>
          <option value="cpp">{LANGUAGE_CONFIG.cpp.name}</option>
        </select>

        {isDirty && (
          <span
            style={{
              fontSize: "10px",
              padding: "2px 6px",
              borderRadius: "4px",
              backgroundColor: colors.severity.warning,
              color: colors.contrast.light,
            }}
          >
            Unsaved
          </span>
        )}

        {/* Separator */}
        <div style={{ width: "1px", height: "24px", backgroundColor: borders.default }} />

        {/* Add Buttons */}
        <div style={{ display: "flex", gap: "8px" }}>
          <button
            onClick={handleAddClass}
            style={{
              padding: "6px 12px",
              borderRadius: "6px",
              border: `1px solid ${colors.primary.main}`,
              backgroundColor: "transparent",
              color: colors.primary.main,
              fontSize: "13px",
              fontWeight: 500,
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: "6px",
            }}
            title={`Add ${entityNames.class}`}
          >
            <span style={{ fontSize: "14px" }}>+</span>
            {entityNames.class}
          </button>
          <button
            onClick={handleAddInterface}
            style={{
              padding: "6px 12px",
              borderRadius: "6px",
              border: `1px solid ${colors.callFlow.class}`,
              backgroundColor: "transparent",
              color: colors.callFlow.class,
              fontSize: "13px",
              fontWeight: 500,
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: "6px",
            }}
            title={`Add ${entityNames.interface}`}
          >
            <span style={{ fontSize: "14px" }}>+</span>
            {entityNames.interface}
          </button>
          <button
            onClick={handleAddEnum}
            style={{
              padding: "6px 12px",
              borderRadius: "6px",
              border: `1px solid ${colors.callFlow.method}`,
              backgroundColor: "transparent",
              color: colors.callFlow.method,
              fontSize: "13px",
              fontWeight: 500,
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: "6px",
            }}
            title={`Add ${entityNames.enum}`}
          >
            <span style={{ fontSize: "14px" }}>+</span>
            {entityNames.enum}
          </button>
          <button
            onClick={handleAddStruct}
            style={{
              padding: "6px 12px",
              borderRadius: "6px",
              border: `1px solid ${STRUCT_COLOR}`,
              backgroundColor: "transparent",
              color: STRUCT_COLOR,
              fontSize: "13px",
              fontWeight: 500,
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: "6px",
            }}
            title={`Add ${entityNames.struct}`}
          >
            <span style={{ fontSize: "14px" }}>+</span>
            {entityNames.struct}
          </button>
        </div>

        {/* Spacer */}
        <div style={{ flex: 1 }} />

        {/* Right Actions */}
        <div style={{ display: "flex", gap: "8px" }}>
          <button
            onClick={resetProject}
            style={{
              padding: "6px 12px",
              borderRadius: "6px",
              border: `1px solid ${borders.default}`,
              backgroundColor: "transparent",
              color: colors.text.muted,
              fontSize: "13px",
              cursor: "pointer",
            }}
          >
            New Project
          </button>
          <button
            onClick={handleExport}
            style={{
              padding: "6px 12px",
              borderRadius: "6px",
              border: "none",
              backgroundColor: colors.primary.main,
              color: colors.contrast.light,
              fontSize: "13px",
              fontWeight: 500,
              cursor: "pointer",
            }}
          >
            Export XML
          </button>
        </div>
      </div>

      {/* Main Content Area */}
      <div style={{ flex: 1, display: "flex", position: "relative", minHeight: 0 }}>
        {/* Canvas Area */}
        <div
          style={{
            flex: 1,
            position: "relative",
            backgroundColor: colors.base.panel,
          }}
        >
          {/* Empty State */}
          {currentModule &&
            currentModule.classes.length === 0 &&
            currentModule.interfaces.length === 0 &&
            currentModule.enums.length === 0 &&
            currentModule.structs.length === 0 && (
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                height: "100%",
                gap: "16px",
              }}
            >
              <div style={{ fontSize: "48px" }}>+</div>
              <div style={{ fontSize: "18px", color: colors.text.secondary }}>
                Start building your model
              </div>
              <div style={{ fontSize: "14px", color: colors.text.muted, textAlign: "center" }}>
                Add classes, interfaces, enums, or structs using the toolbar above.<br />
                Connect them to define relationships.
              </div>
            </div>
          )}

          {/* React Flow Canvas */}
          {currentModule && (currentModule.classes.length > 0 || currentModule.interfaces.length > 0 || currentModule.enums.length > 0 || currentModule.structs.length > 0) && (
            <ReactFlowProvider>
              <UmlEditorCanvas />
            </ReactFlowProvider>
          )}
        </div>

        {/* Inspector Panel (Right Sidebar) */}
        <InspectorPanel />
      </div>

      {/* Validation Panel (replaces status bar) */}
      <ValidationPanel
        isExpanded={isValidationExpanded}
        onToggle={() => setValidationExpanded(!isValidationExpanded)}
      />

      {/* Export Dialog */}
      <ExportDialog
        isOpen={isExportDialogOpen}
        onClose={() => setExportDialogOpen(false)}
      />

      {/* Language Change Confirmation Dialog */}
      {pendingLanguageChange && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: "rgba(0, 0, 0, 0.5)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000,
          }}
          onClick={cancelLanguageChange}
        >
          <div
            style={{
              backgroundColor: colors.base.card,
              borderRadius: "12px",
              padding: "24px",
              maxWidth: "450px",
              width: "90%",
              border: `1px solid ${borders.default}`,
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <h3 style={{ margin: "0 0 16px 0", color: colors.text.secondary }}>
              Change Target Language?
            </h3>
            <p style={{ margin: "0 0 16px 0", color: colors.text.muted, fontSize: "14px" }}>
              Changing from <strong>{LANGUAGE_CONFIG[currentLanguage].name}</strong> to{" "}
              <strong>{LANGUAGE_CONFIG[pendingLanguageChange].name}</strong> will affect how entities are generated:
            </p>
            <ul style={{ margin: "0 0 20px 0", paddingLeft: "20px", color: colors.text.muted, fontSize: "13px" }}>
              {getIncompatibleEntities(currentLanguage, pendingLanguageChange, entityCounts).map((item) => (
                <li key={item.type} style={{ marginBottom: "4px" }}>
                  {item.count} {item.currentName}{item.count > 1 ? "s" : ""} → {item.newName}
                </li>
              ))}
            </ul>
            <div style={{ display: "flex", gap: "12px", justifyContent: "flex-end" }}>
              <button
                onClick={cancelLanguageChange}
                style={{
                  padding: "8px 16px",
                  borderRadius: "6px",
                  border: `1px solid ${borders.default}`,
                  backgroundColor: "transparent",
                  color: colors.text.muted,
                  fontSize: "13px",
                  cursor: "pointer",
                }}
              >
                Cancel
              </button>
              <button
                onClick={confirmLanguageChange}
                style={{
                  padding: "8px 16px",
                  borderRadius: "6px",
                  border: "none",
                  backgroundColor: colors.primary.main,
                  color: colors.contrast.light,
                  fontSize: "13px",
                  fontWeight: 500,
                  cursor: "pointer",
                }}
              >
                Change Language
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
