/**
 * StructInspector - Editor for UML Struct entities
 *
 * Structs are data containers (similar to C++ structs, Python dataclasses, TS interfaces).
 * They only have attributes, no methods.
 */

import { useUmlEditorStore } from "../../../state/useUmlEditorStore";
import { DESIGN_TOKENS } from "../../../theme/designTokens";
import { XmlPreview } from "./XmlPreview";
import type { UmlStructDef, UmlAttributeDef } from "../../../api/types";

const { colors, borders } = DESIGN_TOKENS;

// Distinct color for structs
const STRUCT_COLOR = "#0891b2";

interface StructInspectorProps {
  structId: string;
  activeTab: string;
}

export function StructInspector({ structId, activeTab }: StructInspectorProps): JSX.Element | null {
  const { getStructById, updateStruct, addStructAttribute, updateStructAttribute, deleteStructAttribute } = useUmlEditorStore();
  const struct = getStructById(structId);

  if (!struct) return null;

  const handleChange = (field: keyof UmlStructDef, value: any) => {
    updateStruct(structId, { [field]: value });
  };

  const handleAddAttribute = () => {
    addStructAttribute(structId);
  };

  const handleUpdateAttribute = (attrId: string, updates: Partial<UmlAttributeDef>) => {
    updateStructAttribute(structId, attrId, updates);
  };

  const handleDeleteAttribute = (attrId: string) => {
    deleteStructAttribute(structId, attrId);
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
              value={struct.name}
              onChange={(e) => handleChange("name", e.target.value)}
              style={inputStyle}
            />
          </div>

          {/* Description */}
          <div>
            <label style={labelStyle}>Description</label>
            <textarea
              value={struct.description}
              onChange={(e) => handleChange("description", e.target.value)}
              style={{ ...inputStyle, minHeight: "80px", resize: "vertical" }}
              placeholder="Describe what data this struct holds..."
            />
          </div>

          {/* Language hint */}
          <div
            style={{
              padding: "12px",
              backgroundColor: colors.base.panel,
              borderRadius: "6px",
              fontSize: "12px",
              color: colors.text.muted,
            }}
          >
            <strong style={{ color: STRUCT_COLOR }}>Struct</strong> maps to:
            <ul style={{ margin: "8px 0 0 16px", padding: 0 }}>
              <li><strong>C++:</strong> struct</li>
              <li><strong>Python:</strong> @dataclass</li>
              <li><strong>TypeScript:</strong> interface / type</li>
            </ul>
          </div>
        </>
      )}

      {activeTab === "attributes" && (
        <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={labelStyle}>Fields ({struct.attributes.length})</span>
            <button onClick={handleAddAttribute} style={addButtonStyle}>
              + Add Field
            </button>
          </div>

          {struct.attributes.length === 0 ? (
            <div style={{ padding: "20px", textAlign: "center", color: colors.text.muted }}>
              <div style={{ fontSize: "24px", marginBottom: "8px" }}>+</div>
              <div style={{ fontSize: "12px" }}>No fields yet</div>
              <div style={{ fontSize: "11px", marginTop: "4px" }}>Click "Add Field" to define struct members</div>
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
              {struct.attributes.map((attr) => (
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
                      placeholder="What is this field for?"
                      style={inputStyle}
                    />
                  </div>

                  {/* Row 3: Default Value and Actions */}
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
                    <button
                      onClick={() => handleDeleteAttribute(attr.id)}
                      style={{
                        ...addButtonStyle,
                        backgroundColor: colors.severity.danger,
                        marginTop: "16px",
                      }}
                      title="Delete field"
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
        <XmlPreview entity={struct} entityType="struct" />
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
