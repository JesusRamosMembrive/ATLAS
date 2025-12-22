/**
 * ClassInspector - Editor for UML Class entities
 */

import { useState } from "react";
import { useUmlEditorStore } from "../../../state/useUmlEditorStore";
import { AttributeEditor } from "./AttributeEditor";
import { MethodEditor } from "./MethodEditor";
import { XmlPreview } from "./XmlPreview";
import { DESIGN_TOKENS } from "../../../theme/designTokens";
import type { UmlClassDef } from "../../../api/types";

const { colors, borders } = DESIGN_TOKENS;

interface ClassInspectorProps {
  classId: string;
  activeTab: string;
}

export function ClassInspector({ classId, activeTab }: ClassInspectorProps): JSX.Element | null {
  const { getClassById, updateClass, getAllTypeNames } = useUmlEditorStore();
  const cls = getClassById(classId);

  if (!cls) return null;

  const allTypes = getAllTypeNames();

  const handleChange = (field: keyof UmlClassDef, value: any) => {
    updateClass(classId, { [field]: value });
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
      {activeTab === "general" && (
        <>
          {/* Name */}
          <div>
            <label style={labelStyle}>Name</label>
            <input
              type="text"
              value={cls.name}
              onChange={(e) => handleChange("name", e.target.value)}
              style={inputStyle}
            />
          </div>

          {/* Description */}
          <div>
            <label style={labelStyle}>Description</label>
            <textarea
              value={cls.description}
              onChange={(e) => handleChange("description", e.target.value)}
              style={{ ...inputStyle, minHeight: "80px", resize: "vertical" }}
              placeholder="Describe what this class does..."
            />
          </div>

          {/* Is Abstract */}
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <input
              type="checkbox"
              id="isAbstract"
              checked={cls.isAbstract}
              onChange={(e) => handleChange("isAbstract", e.target.checked)}
              style={{ width: "16px", height: "16px", accentColor: colors.primary.main }}
            />
            <label htmlFor="isAbstract" style={{ fontSize: "13px", color: colors.text.secondary, cursor: "pointer" }}>
              Abstract class
            </label>
          </div>

          {/* Extends */}
          <div>
            <label style={labelStyle}>Extends</label>
            <select
              value={cls.extends || ""}
              onChange={(e) => handleChange("extends", e.target.value || null)}
              style={inputStyle}
            >
              <option value="">None</option>
              {allTypes
                .filter((t) => t !== cls.name)
                .map((type) => (
                  <option key={type} value={type}>
                    {type}
                  </option>
                ))}
            </select>
          </div>

          {/* Implements */}
          <div>
            <label style={labelStyle}>Implements</label>
            <div style={{ display: "flex", flexWrap: "wrap", gap: "6px", marginTop: "4px" }}>
              {cls.implements.length === 0 ? (
                <span style={{ fontSize: "12px", color: colors.text.muted, fontStyle: "italic" }}>
                  No interfaces implemented
                </span>
              ) : (
                cls.implements.map((iface, idx) => (
                  <span
                    key={idx}
                    style={{
                      fontSize: "11px",
                      padding: "2px 8px",
                      borderRadius: "4px",
                      backgroundColor: colors.callFlow.class,
                      color: colors.contrast.light,
                      display: "flex",
                      alignItems: "center",
                      gap: "4px",
                    }}
                  >
                    {iface}
                    <button
                      onClick={() => {
                        const newImplements = cls.implements.filter((_, i) => i !== idx);
                        handleChange("implements", newImplements);
                      }}
                      style={{
                        border: "none",
                        background: "transparent",
                        color: colors.contrast.light,
                        cursor: "pointer",
                        fontSize: "12px",
                        padding: "0 2px",
                      }}
                    >
                      x
                    </button>
                  </span>
                ))
              )}
            </div>
            <select
              value=""
              onChange={(e) => {
                if (e.target.value && !cls.implements.includes(e.target.value)) {
                  handleChange("implements", [...cls.implements, e.target.value]);
                }
              }}
              style={{ ...inputStyle, marginTop: "8px" }}
            >
              <option value="">+ Add interface...</option>
              {allTypes
                .filter((t) => t !== cls.name && !cls.implements.includes(t))
                .map((type) => (
                  <option key={type} value={type}>
                    {type}
                  </option>
                ))}
            </select>
          </div>
        </>
      )}

      {activeTab === "attributes" && (
        <AttributeEditor classId={classId} />
      )}

      {activeTab === "methods" && (
        <MethodEditor classId={classId} />
      )}

      {activeTab === "preview" && (
        <XmlPreview entity={cls} entityType="class" />
      )}
    </div>
  );
}

// Shared styles
const labelStyle: React.CSSProperties = {
  display: "block",
  fontSize: "11px",
  fontWeight: 600,
  color: DESIGN_TOKENS.colors.text.muted,
  textTransform: "uppercase",
  marginBottom: "6px",
};

const inputStyle: React.CSSProperties = {
  width: "100%",
  padding: "8px 12px",
  borderRadius: "6px",
  border: `1px solid ${DESIGN_TOKENS.borders.default}`,
  backgroundColor: DESIGN_TOKENS.colors.base.panel,
  color: DESIGN_TOKENS.colors.text.secondary,
  fontSize: "13px",
  outline: "none",
};
