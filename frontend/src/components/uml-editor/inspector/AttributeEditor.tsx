/**
 * AttributeEditor - Editor for class attributes
 */

import { useUmlEditorStore } from "../../../state/useUmlEditorStore";
import { DESIGN_TOKENS } from "../../../theme/designTokens";
import type { UmlAttributeDef } from "../../../api/types";

const { colors, borders } = DESIGN_TOKENS;

interface AttributeEditorProps {
  classId: string;
}

export function AttributeEditor({ classId }: AttributeEditorProps): JSX.Element {
  const { getClassById, addAttribute, updateAttribute, deleteAttribute } = useUmlEditorStore();
  const cls = getClassById(classId);

  if (!cls) return <div>Class not found</div>;

  const handleAddAttribute = () => {
    addAttribute(classId);
  };

  const handleUpdateAttribute = (attrId: string, updates: Partial<UmlAttributeDef>) => {
    updateAttribute(classId, attrId, updates);
  };

  const handleDeleteAttribute = (attrId: string) => {
    deleteAttribute(classId, attrId);
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span style={labelStyle}>Attributes ({cls.attributes.length})</span>
        <button onClick={handleAddAttribute} style={addButtonStyle}>
          + Add Attribute
        </button>
      </div>

      {cls.attributes.length === 0 ? (
        <div style={{ padding: "20px", textAlign: "center", color: colors.text.muted }}>
          <div style={{ fontSize: "24px", marginBottom: "8px" }}>+</div>
          <div style={{ fontSize: "12px" }}>No attributes yet</div>
          <div style={{ fontSize: "11px", marginTop: "4px" }}>Click "Add Attribute" to create one</div>
        </div>
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
          {cls.attributes.map((attr) => (
            <div
              key={attr.id}
              style={{
                padding: "12px",
                backgroundColor: colors.base.panel,
                borderRadius: "6px",
                border: `1px solid ${borders.default}`,
              }}
            >
              {/* Row 1: Name and Type */}
              <div style={{ display: "flex", gap: "8px", marginBottom: "8px" }}>
                <div style={{ flex: 1 }}>
                  <label style={{ ...labelStyle, fontSize: "10px" }}>Name</label>
                  <input
                    type="text"
                    value={attr.name}
                    onChange={(e) => handleUpdateAttribute(attr.id, { name: e.target.value })}
                    style={inputStyle}
                  />
                </div>
                <div style={{ flex: 1 }}>
                  <label style={{ ...labelStyle, fontSize: "10px" }}>Type</label>
                  <input
                    type="text"
                    value={attr.type}
                    onChange={(e) => handleUpdateAttribute(attr.id, { type: e.target.value })}
                    style={inputStyle}
                  />
                </div>
                <div style={{ width: "80px" }}>
                  <label style={{ ...labelStyle, fontSize: "10px" }}>Visibility</label>
                  <select
                    value={attr.visibility}
                    onChange={(e) => handleUpdateAttribute(attr.id, { visibility: e.target.value as any })}
                    style={inputStyle}
                  >
                    <option value="public">+ public</option>
                    <option value="protected"># protected</option>
                    <option value="private">- private</option>
                  </select>
                </div>
              </div>

              {/* Row 2: Description */}
              <div style={{ marginBottom: "8px" }}>
                <label style={{ ...labelStyle, fontSize: "10px" }}>Description</label>
                <input
                  type="text"
                  value={attr.description}
                  onChange={(e) => handleUpdateAttribute(attr.id, { description: e.target.value })}
                  placeholder="What is this attribute for?"
                  style={inputStyle}
                />
              </div>

              {/* Row 3: Default Value and Modifiers */}
              <div style={{ display: "flex", gap: "12px", alignItems: "center" }}>
                <div style={{ flex: 1 }}>
                  <label style={{ ...labelStyle, fontSize: "10px" }}>Default Value</label>
                  <input
                    type="text"
                    value={attr.defaultValue || ""}
                    onChange={(e) => handleUpdateAttribute(attr.id, { defaultValue: e.target.value || null })}
                    placeholder="null"
                    style={inputStyle}
                  />
                </div>
                <div style={{ display: "flex", gap: "12px", paddingTop: "16px" }}>
                  <label style={{ display: "flex", alignItems: "center", gap: "4px", cursor: "pointer" }}>
                    <input
                      type="checkbox"
                      checked={attr.isStatic}
                      onChange={(e) => handleUpdateAttribute(attr.id, { isStatic: e.target.checked })}
                      style={{ width: "14px", height: "14px", accentColor: colors.primary.main }}
                    />
                    <span style={{ fontSize: "11px", color: colors.text.secondary }}>Static</span>
                  </label>
                  <label style={{ display: "flex", alignItems: "center", gap: "4px", cursor: "pointer" }}>
                    <input
                      type="checkbox"
                      checked={attr.isReadonly}
                      onChange={(e) => handleUpdateAttribute(attr.id, { isReadonly: e.target.checked })}
                      style={{ width: "14px", height: "14px", accentColor: colors.primary.main }}
                    />
                    <span style={{ fontSize: "11px", color: colors.text.secondary }}>Readonly</span>
                  </label>
                </div>
                <button
                  onClick={() => handleDeleteAttribute(attr.id)}
                  style={{
                    ...addButtonStyle,
                    backgroundColor: colors.severity.danger,
                    marginTop: "16px",
                  }}
                  title="Delete attribute"
                >
                  Delete
                </button>
              </div>
            </div>
          ))}
        </div>
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
  marginBottom: "4px",
};

const inputStyle: React.CSSProperties = {
  width: "100%",
  padding: "6px 10px",
  borderRadius: "4px",
  border: `1px solid ${DESIGN_TOKENS.borders.default}`,
  backgroundColor: DESIGN_TOKENS.colors.base.card,
  color: DESIGN_TOKENS.colors.text.secondary,
  fontSize: "12px",
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
