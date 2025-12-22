/**
 * InterfaceInspector - Editor for UML Interface entities
 */

import { useUmlEditorStore } from "../../../state/useUmlEditorStore";
import { DESIGN_TOKENS } from "../../../theme/designTokens";
import { XmlPreview } from "./XmlPreview";
import type { UmlInterfaceDef, UmlInterfaceMethodDef, UmlParameter } from "../../../api/types";

const { colors, borders } = DESIGN_TOKENS;

interface InterfaceInspectorProps {
  interfaceId: string;
  activeTab: string;
}

export function InterfaceInspector({ interfaceId, activeTab }: InterfaceInspectorProps): JSX.Element | null {
  const { getInterfaceById, updateInterface, getAllTypeNames } = useUmlEditorStore();
  const iface = getInterfaceById(interfaceId);

  if (!iface) return null;

  const allTypes = getAllTypeNames();

  const handleChange = (field: keyof UmlInterfaceDef, value: any) => {
    updateInterface(interfaceId, { [field]: value });
  };

  const handleAddMethod = () => {
    const newMethod: UmlInterfaceMethodDef = {
      id: `method-${Date.now()}`,
      name: "newMethod",
      description: "",
      parameters: [],
      returnType: "void",
    };
    updateInterface(interfaceId, {
      methods: [...iface.methods, newMethod],
    });
  };

  const handleUpdateMethod = (methodId: string, updates: Partial<UmlInterfaceMethodDef>) => {
    const updatedMethods = iface.methods.map((m) =>
      m.id === methodId ? { ...m, ...updates } : m
    );
    updateInterface(interfaceId, { methods: updatedMethods });
  };

  const handleDeleteMethod = (methodId: string) => {
    const updatedMethods = iface.methods.filter((m) => m.id !== methodId);
    updateInterface(interfaceId, { methods: updatedMethods });
  };

  const handleAddParameter = (methodId: string) => {
    const method = iface.methods.find((m) => m.id === methodId);
    if (!method) return;

    const newParam: UmlParameter = {
      id: `param-${Date.now()}`,
      name: "param",
      type: "string",
      description: "",
      isOptional: false,
      defaultValue: null,
    };
    handleUpdateMethod(methodId, {
      parameters: [...method.parameters, newParam],
    });
  };

  const handleUpdateParameter = (methodId: string, paramId: string, updates: Partial<UmlParameter>) => {
    const method = iface.methods.find((m) => m.id === methodId);
    if (!method) return;

    const updatedParams = method.parameters.map((p) =>
      p.id === paramId ? { ...p, ...updates } : p
    );
    handleUpdateMethod(methodId, { parameters: updatedParams });
  };

  const handleDeleteParameter = (methodId: string, paramId: string) => {
    const method = iface.methods.find((m) => m.id === methodId);
    if (!method) return;

    const updatedParams = method.parameters.filter((p) => p.id !== paramId);
    handleUpdateMethod(methodId, { parameters: updatedParams });
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
              value={iface.name}
              onChange={(e) => handleChange("name", e.target.value)}
              style={inputStyle}
            />
          </div>

          {/* Description */}
          <div>
            <label style={labelStyle}>Description</label>
            <textarea
              value={iface.description}
              onChange={(e) => handleChange("description", e.target.value)}
              style={{ ...inputStyle, minHeight: "80px", resize: "vertical" }}
              placeholder="Describe what this interface defines..."
            />
          </div>

          {/* Extends */}
          <div>
            <label style={labelStyle}>Extends</label>
            <div style={{ display: "flex", flexWrap: "wrap", gap: "6px", marginTop: "4px" }}>
              {iface.extends.length === 0 ? (
                <span style={{ fontSize: "12px", color: colors.text.muted, fontStyle: "italic" }}>
                  No parent interfaces
                </span>
              ) : (
                iface.extends.map((ext, idx) => (
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
                    {ext}
                    <button
                      onClick={() => {
                        const newExtends = iface.extends.filter((_, i) => i !== idx);
                        handleChange("extends", newExtends);
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
                if (e.target.value && !iface.extends.includes(e.target.value)) {
                  handleChange("extends", [...iface.extends, e.target.value]);
                }
              }}
              style={{ ...inputStyle, marginTop: "8px" }}
            >
              <option value="">+ Add parent interface...</option>
              {allTypes
                .filter((t) => t !== iface.name && !iface.extends.includes(t))
                .map((type) => (
                  <option key={type} value={type}>
                    {type}
                  </option>
                ))}
            </select>
          </div>
        </>
      )}

      {activeTab === "methods" && (
        <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span style={labelStyle}>Methods ({iface.methods.length})</span>
            <button onClick={handleAddMethod} style={addButtonStyle}>
              + Add Method
            </button>
          </div>

          {iface.methods.length === 0 ? (
            <div style={{ padding: "20px", textAlign: "center", color: colors.text.muted }}>
              <div style={{ fontSize: "24px", marginBottom: "8px" }}>+</div>
              <div style={{ fontSize: "12px" }}>No methods defined</div>
              <div style={{ fontSize: "11px", marginTop: "4px" }}>Click "Add Method" to define a method signature</div>
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
              {iface.methods.map((method) => (
                <div
                  key={method.id}
                  style={{
                    padding: "12px",
                    backgroundColor: colors.base.panel,
                    borderRadius: "6px",
                    border: `1px solid ${borders.default}`,
                  }}
                >
                  {/* Method Name and Return Type */}
                  <div style={{ display: "flex", gap: "8px", marginBottom: "8px" }}>
                    <div style={{ flex: 2 }}>
                      <label style={{ ...labelStyle, fontSize: "10px" }}>Name</label>
                      <input
                        type="text"
                        value={method.name}
                        onChange={(e) => handleUpdateMethod(method.id, { name: e.target.value })}
                        style={inputStyle}
                      />
                    </div>
                    <div style={{ flex: 1 }}>
                      <label style={{ ...labelStyle, fontSize: "10px" }}>Return Type</label>
                      <input
                        type="text"
                        value={method.returnType}
                        onChange={(e) => handleUpdateMethod(method.id, { returnType: e.target.value })}
                        style={inputStyle}
                      />
                    </div>
                  </div>

                  {/* Description */}
                  <div style={{ marginBottom: "8px" }}>
                    <label style={{ ...labelStyle, fontSize: "10px" }}>Description</label>
                    <input
                      type="text"
                      value={method.description}
                      onChange={(e) => handleUpdateMethod(method.id, { description: e.target.value })}
                      placeholder="What should this method do?"
                      style={inputStyle}
                    />
                  </div>

                  {/* Parameters */}
                  <div style={{ marginBottom: "8px" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
                      <label style={{ ...labelStyle, fontSize: "10px", marginBottom: 0 }}>Parameters</label>
                      <button
                        onClick={() => handleAddParameter(method.id)}
                        style={{ ...addButtonStyle, padding: "2px 8px", fontSize: "10px" }}
                      >
                        + Add
                      </button>
                    </div>
                    {method.parameters.length === 0 ? (
                      <div style={{ fontSize: "11px", color: colors.text.muted, fontStyle: "italic" }}>
                        No parameters
                      </div>
                    ) : (
                      <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                        {method.parameters.map((param) => (
                          <div
                            key={param.id}
                            style={{
                              display: "flex",
                              gap: "6px",
                              alignItems: "center",
                              padding: "6px",
                              backgroundColor: colors.base.card,
                              borderRadius: "4px",
                            }}
                          >
                            <input
                              type="text"
                              value={param.name}
                              onChange={(e) => handleUpdateParameter(method.id, param.id, { name: e.target.value })}
                              placeholder="name"
                              style={{ ...inputStyle, flex: 1 }}
                            />
                            <input
                              type="text"
                              value={param.type}
                              onChange={(e) => handleUpdateParameter(method.id, param.id, { type: e.target.value })}
                              placeholder="type"
                              style={{ ...inputStyle, flex: 1 }}
                            />
                            <label style={{ display: "flex", alignItems: "center", gap: "4px", cursor: "pointer" }}>
                              <input
                                type="checkbox"
                                checked={param.isOptional}
                                onChange={(e) => handleUpdateParameter(method.id, param.id, { isOptional: e.target.checked })}
                                style={{ width: "12px", height: "12px" }}
                              />
                              <span style={{ fontSize: "10px", color: colors.text.muted }}>?</span>
                            </label>
                            <button
                              onClick={() => handleDeleteParameter(method.id, param.id)}
                              style={{
                                border: "none",
                                background: "transparent",
                                color: colors.severity.danger,
                                cursor: "pointer",
                                fontSize: "14px",
                                padding: "2px 4px",
                              }}
                            >
                              x
                            </button>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Delete Button */}
                  <button
                    onClick={() => handleDeleteMethod(method.id)}
                    style={{
                      ...addButtonStyle,
                      backgroundColor: colors.severity.danger,
                      width: "100%",
                    }}
                  >
                    Delete Method
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {activeTab === "preview" && (
        <XmlPreview entity={iface} entityType="interface" />
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
