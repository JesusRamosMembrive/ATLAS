/**
 * EnumInspector - Editor for UML Enum entities
 */

import { useUmlEditorStore } from "../../../state/useUmlEditorStore";
import { DESIGN_TOKENS } from "../../../theme/designTokens";
import { XmlPreview } from "./XmlPreview";
import type { UmlEnumDef, UmlEnumValue } from "../../../api/types";

const { colors, borders } = DESIGN_TOKENS;

interface EnumInspectorProps {
  enumId: string;
  activeTab: string;
}

export function EnumInspector({ enumId, activeTab }: EnumInspectorProps): JSX.Element | null {
  const { getEnumById, updateEnum } = useUmlEditorStore();
  const enumDef = getEnumById(enumId);

  if (!enumDef) return null;

  const handleChange = (field: keyof UmlEnumDef, value: any) => {
    updateEnum(enumId, { [field]: value });
  };

  const handleAddValue = () => {
    const newValue: UmlEnumValue = {
      id: `value-${Date.now()}`,
      name: "NEW_VALUE",
      description: "",
      value: null,
    };
    updateEnum(enumId, {
      values: [...enumDef.values, newValue],
    });
  };

  const handleUpdateValue = (valueId: string, updates: Partial<UmlEnumValue>) => {
    const updatedValues = enumDef.values.map((v) =>
      v.id === valueId ? { ...v, ...updates } : v
    );
    updateEnum(enumId, { values: updatedValues });
  };

  const handleDeleteValue = (valueId: string) => {
    const updatedValues = enumDef.values.filter((v) => v.id !== valueId);
    updateEnum(enumId, { values: updatedValues });
  };

  const handleMoveValue = (valueId: string, direction: "up" | "down") => {
    const index = enumDef.values.findIndex((v) => v.id === valueId);
    if (index === -1) return;

    const newIndex = direction === "up" ? index - 1 : index + 1;
    if (newIndex < 0 || newIndex >= enumDef.values.length) return;

    const newValues = [...enumDef.values];
    [newValues[index], newValues[newIndex]] = [newValues[newIndex], newValues[index]];
    updateEnum(enumId, { values: newValues });
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
              value={enumDef.name}
              onChange={(e) => handleChange("name", e.target.value)}
              style={inputStyle}
            />
          </div>

          {/* Description */}
          <div>
            <label style={labelStyle}>Description</label>
            <textarea
              value={enumDef.description}
              onChange={(e) => handleChange("description", e.target.value)}
              style={{ ...inputStyle, minHeight: "80px", resize: "vertical" }}
              placeholder="Describe what values this enum represents..."
            />
          </div>
        </>
      )}

      {activeTab === "values" && (
        <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={labelStyle}>Values ({enumDef.values.length})</span>
            <button onClick={handleAddValue} style={addButtonStyle}>
              + Add Value
            </button>
          </div>

          {enumDef.values.length === 0 ? (
            <div style={{ padding: "20px", textAlign: "center", color: colors.text.muted }}>
              <div style={{ fontSize: "24px", marginBottom: "8px" }}>+</div>
              <div style={{ fontSize: "12px" }}>No values defined</div>
              <div style={{ fontSize: "11px", marginTop: "4px" }}>Click "Add Value" to add enum values</div>
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
              {enumDef.values.map((enumValue, index) => (
                <div
                  key={enumValue.id}
                  style={{
                    padding: "12px",
                    backgroundColor: colors.base.panel,
                    borderRadius: "6px",
                    border: `1px solid ${borders.default}`,
                  }}
                >
                  {/* Row 1: Name and Value */}
                  <div style={{ display: "flex", gap: "8px", marginBottom: "8px" }}>
                    <div style={{ flex: 2 }}>
                      <label style={{ ...labelStyle, fontSize: "10px" }}>Name</label>
                      <input
                        type="text"
                        value={enumValue.name}
                        onChange={(e) => handleUpdateValue(enumValue.id, { name: e.target.value.toUpperCase() })}
                        style={{ ...inputStyle, fontFamily: "monospace" }}
                      />
                    </div>
                    <div style={{ flex: 1 }}>
                      <label style={{ ...labelStyle, fontSize: "10px" }}>Value (optional)</label>
                      <input
                        type="text"
                        value={enumValue.value ?? ""}
                        onChange={(e) => {
                          const val = e.target.value;
                          // Try to parse as number, otherwise keep as string
                          const parsedValue = val === "" ? null : !isNaN(Number(val)) ? Number(val) : val;
                          handleUpdateValue(enumValue.id, { value: parsedValue });
                        }}
                        placeholder="auto"
                        style={inputStyle}
                      />
                    </div>
                  </div>

                  {/* Row 2: Description */}
                  <div style={{ marginBottom: "8px" }}>
                    <label style={{ ...labelStyle, fontSize: "10px" }}>Description</label>
                    <input
                      type="text"
                      value={enumValue.description}
                      onChange={(e) => handleUpdateValue(enumValue.id, { description: e.target.value })}
                      placeholder="What does this value represent?"
                      style={inputStyle}
                    />
                  </div>

                  {/* Row 3: Actions */}
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                    <div style={{ display: "flex", gap: "4px" }}>
                      <button
                        onClick={() => handleMoveValue(enumValue.id, "up")}
                        disabled={index === 0}
                        style={{
                          ...moveButtonStyle,
                          opacity: index === 0 ? 0.4 : 1,
                          cursor: index === 0 ? "not-allowed" : "pointer",
                        }}
                        title="Move up"
                      >
                        ^
                      </button>
                      <button
                        onClick={() => handleMoveValue(enumValue.id, "down")}
                        disabled={index === enumDef.values.length - 1}
                        style={{
                          ...moveButtonStyle,
                          opacity: index === enumDef.values.length - 1 ? 0.4 : 1,
                          cursor: index === enumDef.values.length - 1 ? "not-allowed" : "pointer",
                        }}
                        title="Move down"
                      >
                        v
                      </button>
                    </div>
                    <button
                      onClick={() => handleDeleteValue(enumValue.id)}
                      style={{
                        ...addButtonStyle,
                        backgroundColor: colors.severity.danger,
                      }}
                    >
                      Delete
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {activeTab === "preview" && (
        <XmlPreview entity={enumDef} entityType="enum" />
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

const addButtonStyle: React.CSSProperties = {
  padding: "6px 12px",
  borderRadius: "4px",
  border: "none",
  backgroundColor: DESIGN_TOKENS.colors.primary.main,
  color: DESIGN_TOKENS.colors.contrast.light,
  fontSize: "11px",
  fontWeight: 500,
  cursor: "pointer",
};

const moveButtonStyle: React.CSSProperties = {
  padding: "4px 8px",
  borderRadius: "4px",
  border: `1px solid ${DESIGN_TOKENS.borders.default}`,
  backgroundColor: DESIGN_TOKENS.colors.base.card,
  color: DESIGN_TOKENS.colors.text.muted,
  fontSize: "12px",
  cursor: "pointer",
};
