/**
 * MethodEditor - Full editor for class methods
 *
 * Includes:
 * - Basic info: name, visibility, returnType, isStatic, isAsync
 * - Parameters table
 * - Preconditions / Postconditions
 * - Throws definitions
 * - Hints (edgeCases, performance, style, custom)
 * - Test cases
 */

import { useState } from "react";
import { useUmlEditorStore } from "../../../state/useUmlEditorStore";
import { DESIGN_TOKENS } from "../../../theme/designTokens";
import type { UmlMethodDef, UmlParameter, UmlThrows, UmlTestCase, UmlHints } from "../../../api/types";

const { colors, borders } = DESIGN_TOKENS;

interface MethodEditorProps {
  classId: string;
}

export function MethodEditor({ classId }: MethodEditorProps): JSX.Element {
  const { getClassById, addMethod, updateMethod, deleteMethod } = useUmlEditorStore();
  const cls = getClassById(classId);
  const [selectedMethodId, setSelectedMethodId] = useState<string | null>(null);
  const [activeSection, setActiveSection] = useState<"basic" | "params" | "contracts" | "hints" | "tests">("basic");

  if (!cls) return <div>Class not found</div>;

  const selectedMethod = cls.methods.find((m) => m.id === selectedMethodId);

  const handleAddMethod = () => {
    const newId = addMethod(classId);
    setSelectedMethodId(newId);
  };

  const handleUpdateMethod = (updates: Partial<UmlMethodDef>) => {
    if (selectedMethodId) {
      updateMethod(classId, selectedMethodId, updates);
    }
  };

  const handleDeleteMethod = (methodId: string) => {
    deleteMethod(classId, methodId);
    if (selectedMethodId === methodId) {
      setSelectedMethodId(null);
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
      {/* Method List */}
      <div>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "8px" }}>
          <span style={labelStyle}>Methods ({cls.methods.length})</span>
          <button onClick={handleAddMethod} style={addButtonStyle}>
            + Add Method
          </button>
        </div>

        <div style={{ display: "flex", flexDirection: "column", gap: "4px", maxHeight: "150px", overflow: "auto" }}>
          {cls.methods.length === 0 ? (
            <span style={{ fontSize: "12px", color: colors.text.muted, fontStyle: "italic" }}>
              No methods defined
            </span>
          ) : (
            cls.methods.map((method) => (
              <div
                key={method.id}
                onClick={() => setSelectedMethodId(method.id)}
                style={{
                  padding: "8px 12px",
                  borderRadius: "6px",
                  border: selectedMethodId === method.id ? `1px solid ${colors.primary.main}` : `1px solid ${borders.default}`,
                  backgroundColor: selectedMethodId === method.id ? `${colors.primary.main}15` : colors.base.panel,
                  cursor: "pointer",
                  display: "flex",
                  justifyContent: "space-between",
                  alignItems: "center",
                }}
              >
                <div style={{ fontSize: "12px", fontFamily: "monospace" }}>
                  <span style={{ color: colors.text.muted }}>
                    {method.visibility === "private" ? "-" : method.visibility === "protected" ? "#" : "+"}
                  </span>
                  {" "}{method.name}(): <span style={{ color: colors.callFlow.class }}>{method.returnType}</span>
                  {method.isAsync && <span style={{ color: colors.callFlow.method }}> async</span>}
                </div>
                <button
                  onClick={(e) => { e.stopPropagation(); handleDeleteMethod(method.id); }}
                  style={{
                    border: "none",
                    background: "transparent",
                    color: colors.severity.danger,
                    cursor: "pointer",
                    fontSize: "14px",
                    padding: "2px 6px",
                  }}
                  title="Delete method"
                >
                  x
                </button>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Method Detail Editor */}
      {selectedMethod && (
        <div style={{ borderTop: `1px solid ${borders.default}`, paddingTop: "12px" }}>
          {/* Section Tabs */}
          <div style={{ display: "flex", gap: "4px", marginBottom: "12px", flexWrap: "wrap" }}>
            {(["basic", "params", "contracts", "hints", "tests"] as const).map((section) => (
              <button
                key={section}
                onClick={() => setActiveSection(section)}
                style={{
                  padding: "4px 10px",
                  borderRadius: "4px",
                  border: activeSection === section ? `1px solid ${colors.primary.main}` : `1px solid ${borders.default}`,
                  backgroundColor: activeSection === section ? `${colors.primary.main}20` : "transparent",
                  color: activeSection === section ? colors.primary.main : colors.text.muted,
                  fontSize: "11px",
                  fontWeight: 500,
                  cursor: "pointer",
                  textTransform: "capitalize",
                }}
              >
                {section}
              </button>
            ))}
          </div>

          {/* Basic Info */}
          {activeSection === "basic" && (
            <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
              <div>
                <label style={labelStyle}>Name</label>
                <input
                  type="text"
                  value={selectedMethod.name}
                  onChange={(e) => handleUpdateMethod({ name: e.target.value })}
                  style={inputStyle}
                />
              </div>

              <div>
                <label style={labelStyle}>Description</label>
                <textarea
                  value={selectedMethod.description}
                  onChange={(e) => handleUpdateMethod({ description: e.target.value })}
                  style={{ ...inputStyle, minHeight: "60px", resize: "vertical" }}
                  placeholder="What does this method do?"
                />
              </div>

              <div style={{ display: "flex", gap: "12px" }}>
                <div style={{ flex: 1 }}>
                  <label style={labelStyle}>Visibility</label>
                  <select
                    value={selectedMethod.visibility}
                    onChange={(e) => handleUpdateMethod({ visibility: e.target.value as any })}
                    style={inputStyle}
                  >
                    <option value="public">Public (+)</option>
                    <option value="protected">Protected (#)</option>
                    <option value="private">Private (-)</option>
                  </select>
                </div>
                <div style={{ flex: 1 }}>
                  <label style={labelStyle}>Return Type</label>
                  <input
                    type="text"
                    value={selectedMethod.returnType}
                    onChange={(e) => handleUpdateMethod({ returnType: e.target.value })}
                    style={inputStyle}
                    placeholder="void"
                  />
                </div>
              </div>

              <div style={{ display: "flex", gap: "16px" }}>
                <label style={{ display: "flex", alignItems: "center", gap: "6px", cursor: "pointer" }}>
                  <input
                    type="checkbox"
                    checked={selectedMethod.isStatic}
                    onChange={(e) => handleUpdateMethod({ isStatic: e.target.checked })}
                    style={{ width: "14px", height: "14px", accentColor: colors.primary.main }}
                  />
                  <span style={{ fontSize: "12px", color: colors.text.secondary }}>Static</span>
                </label>
                <label style={{ display: "flex", alignItems: "center", gap: "6px", cursor: "pointer" }}>
                  <input
                    type="checkbox"
                    checked={selectedMethod.isAsync}
                    onChange={(e) => handleUpdateMethod({ isAsync: e.target.checked })}
                    style={{ width: "14px", height: "14px", accentColor: colors.primary.main }}
                  />
                  <span style={{ fontSize: "12px", color: colors.text.secondary }}>Async</span>
                </label>
              </div>
            </div>
          )}

          {/* Parameters */}
          {activeSection === "params" && (
            <ParametersSection method={selectedMethod} onUpdate={handleUpdateMethod} />
          )}

          {/* Contracts (Pre/Post conditions, Throws) */}
          {activeSection === "contracts" && (
            <ContractsSection method={selectedMethod} onUpdate={handleUpdateMethod} />
          )}

          {/* Hints */}
          {activeSection === "hints" && (
            <HintsSection method={selectedMethod} onUpdate={handleUpdateMethod} />
          )}

          {/* Test Cases */}
          {activeSection === "tests" && (
            <TestCasesSection method={selectedMethod} onUpdate={handleUpdateMethod} />
          )}
        </div>
      )}
    </div>
  );
}

// Parameters Section Component
function ParametersSection({ method, onUpdate }: { method: UmlMethodDef; onUpdate: (u: Partial<UmlMethodDef>) => void }) {
  const addParameter = () => {
    const newParam: UmlParameter = {
      name: "param" + (method.parameters.length + 1),
      type: "string",
      description: "",
      isOptional: false,
      defaultValue: null,
    };
    onUpdate({ parameters: [...method.parameters, newParam] });
  };

  const updateParameter = (index: number, updates: Partial<UmlParameter>) => {
    const newParams = [...method.parameters];
    newParams[index] = { ...newParams[index], ...updates };
    onUpdate({ parameters: newParams });
  };

  const deleteParameter = (index: number) => {
    onUpdate({ parameters: method.parameters.filter((_, i) => i !== index) });
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span style={labelStyle}>Parameters ({method.parameters.length})</span>
        <button onClick={addParameter} style={addButtonStyle}>+ Add</button>
      </div>

      {method.parameters.length === 0 ? (
        <span style={{ fontSize: "12px", color: colors.text.muted, fontStyle: "italic" }}>No parameters</span>
      ) : (
        method.parameters.map((param, idx) => (
          <div key={idx} style={{ padding: "8px", backgroundColor: colors.base.panel, borderRadius: "6px", border: `1px solid ${borders.default}` }}>
            <div style={{ display: "flex", gap: "8px", marginBottom: "6px" }}>
              <input
                type="text"
                value={param.name}
                onChange={(e) => updateParameter(idx, { name: e.target.value })}
                placeholder="name"
                style={{ ...inputStyle, flex: 1 }}
              />
              <input
                type="text"
                value={param.type}
                onChange={(e) => updateParameter(idx, { type: e.target.value })}
                placeholder="type"
                style={{ ...inputStyle, flex: 1 }}
              />
              <button onClick={() => deleteParameter(idx)} style={{ ...addButtonStyle, backgroundColor: colors.severity.danger }}>x</button>
            </div>
            <input
              type="text"
              value={param.description}
              onChange={(e) => updateParameter(idx, { description: e.target.value })}
              placeholder="Description..."
              style={{ ...inputStyle, fontSize: "11px" }}
            />
            <div style={{ display: "flex", gap: "12px", marginTop: "6px" }}>
              <label style={{ display: "flex", alignItems: "center", gap: "4px", fontSize: "11px", color: colors.text.muted }}>
                <input
                  type="checkbox"
                  checked={param.isOptional}
                  onChange={(e) => updateParameter(idx, { isOptional: e.target.checked })}
                  style={{ width: "12px", height: "12px" }}
                />
                Optional
              </label>
              {param.isOptional && (
                <input
                  type="text"
                  value={param.defaultValue || ""}
                  onChange={(e) => updateParameter(idx, { defaultValue: e.target.value || null })}
                  placeholder="default"
                  style={{ ...inputStyle, flex: 1, fontSize: "11px", padding: "4px 8px" }}
                />
              )}
            </div>
          </div>
        ))
      )}
    </div>
  );
}

// Contracts Section Component
function ContractsSection({ method, onUpdate }: { method: UmlMethodDef; onUpdate: (u: Partial<UmlMethodDef>) => void }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
      {/* Preconditions */}
      <StringListEditor
        label="Preconditions"
        items={method.preconditions}
        onChange={(items) => onUpdate({ preconditions: items })}
        placeholder="e.g., 'input must not be null'"
      />

      {/* Postconditions */}
      <StringListEditor
        label="Postconditions"
        items={method.postconditions}
        onChange={(items) => onUpdate({ postconditions: items })}
        placeholder="e.g., 'returns valid user object'"
      />

      {/* Throws */}
      <div>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "6px" }}>
          <span style={labelStyle}>Throws ({method.throws.length})</span>
          <button
            onClick={() => onUpdate({ throws: [...method.throws, { exception: "Error", when: "" }] })}
            style={addButtonStyle}
          >
            + Add
          </button>
        </div>
        {method.throws.map((t, idx) => (
          <div key={idx} style={{ display: "flex", gap: "6px", marginBottom: "6px" }}>
            <input
              type="text"
              value={t.exception}
              onChange={(e) => {
                const newThrows = [...method.throws];
                newThrows[idx] = { ...newThrows[idx], exception: e.target.value };
                onUpdate({ throws: newThrows });
              }}
              placeholder="Exception"
              style={{ ...inputStyle, flex: 1 }}
            />
            <input
              type="text"
              value={t.when}
              onChange={(e) => {
                const newThrows = [...method.throws];
                newThrows[idx] = { ...newThrows[idx], when: e.target.value };
                onUpdate({ throws: newThrows });
              }}
              placeholder="When..."
              style={{ ...inputStyle, flex: 2 }}
            />
            <button
              onClick={() => onUpdate({ throws: method.throws.filter((_, i) => i !== idx) })}
              style={{ ...addButtonStyle, backgroundColor: colors.severity.danger }}
            >
              x
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}

// Hints Section Component
function HintsSection({ method, onUpdate }: { method: UmlMethodDef; onUpdate: (u: Partial<UmlMethodDef>) => void }) {
  const updateHints = (key: keyof UmlHints, items: string[]) => {
    onUpdate({ hints: { ...method.hints, [key]: items } });
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
      <StringListEditor
        label="Edge Cases"
        items={method.hints.edgeCases}
        onChange={(items) => updateHints("edgeCases", items)}
        placeholder="e.g., 'handle empty list'"
      />
      <StringListEditor
        label="Performance"
        items={method.hints.performance}
        onChange={(items) => updateHints("performance", items)}
        placeholder="e.g., 'use caching for large inputs'"
      />
      <StringListEditor
        label="Style"
        items={method.hints.style}
        onChange={(items) => updateHints("style", items)}
        placeholder="e.g., 'use early return pattern'"
      />
      <StringListEditor
        label="Custom"
        items={method.hints.custom}
        onChange={(items) => updateHints("custom", items)}
        placeholder="Any other instructions for the agent"
      />
    </div>
  );
}

// Test Cases Section Component
function TestCasesSection({ method, onUpdate }: { method: UmlMethodDef; onUpdate: (u: Partial<UmlMethodDef>) => void }) {
  const addTestCase = () => {
    const newTest: UmlTestCase = {
      name: "test_" + (method.testCases.length + 1),
      type: "success",
      description: "",
    };
    onUpdate({ testCases: [...method.testCases, newTest] });
  };

  const updateTestCase = (index: number, updates: Partial<UmlTestCase>) => {
    const newTests = [...method.testCases];
    newTests[index] = { ...newTests[index], ...updates };
    onUpdate({ testCases: newTests });
  };

  const deleteTestCase = (index: number) => {
    onUpdate({ testCases: method.testCases.filter((_, i) => i !== index) });
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <span style={labelStyle}>Test Cases ({method.testCases.length})</span>
        <button onClick={addTestCase} style={addButtonStyle}>+ Add</button>
      </div>

      {method.testCases.length === 0 ? (
        <span style={{ fontSize: "12px", color: colors.text.muted, fontStyle: "italic" }}>
          No test cases defined
        </span>
      ) : (
        method.testCases.map((test, idx) => (
          <div key={idx} style={{ padding: "8px", backgroundColor: colors.base.panel, borderRadius: "6px", border: `1px solid ${borders.default}` }}>
            <div style={{ display: "flex", gap: "6px", marginBottom: "6px" }}>
              <input
                type="text"
                value={test.name}
                onChange={(e) => updateTestCase(idx, { name: e.target.value })}
                placeholder="test name"
                style={{ ...inputStyle, flex: 2 }}
              />
              <select
                value={test.type}
                onChange={(e) => updateTestCase(idx, { type: e.target.value as any })}
                style={{ ...inputStyle, flex: 1 }}
              >
                <option value="success">Success</option>
                <option value="error">Error</option>
                <option value="edge">Edge</option>
              </select>
              <button onClick={() => deleteTestCase(idx)} style={{ ...addButtonStyle, backgroundColor: colors.severity.danger }}>x</button>
            </div>
            <input
              type="text"
              value={test.description}
              onChange={(e) => updateTestCase(idx, { description: e.target.value })}
              placeholder="Description of what this test verifies..."
              style={{ ...inputStyle, fontSize: "11px" }}
            />
          </div>
        ))
      )}
    </div>
  );
}

// Reusable String List Editor
function StringListEditor({
  label,
  items,
  onChange,
  placeholder,
}: {
  label: string;
  items: string[];
  onChange: (items: string[]) => void;
  placeholder?: string;
}) {
  const [newItem, setNewItem] = useState("");

  const handleAdd = () => {
    if (newItem.trim()) {
      onChange([...items, newItem.trim()]);
      setNewItem("");
    }
  };

  return (
    <div>
      <span style={labelStyle}>{label} ({items.length})</span>
      <div style={{ display: "flex", flexDirection: "column", gap: "4px", marginTop: "6px" }}>
        {items.map((item, idx) => (
          <div key={idx} style={{ display: "flex", gap: "6px" }}>
            <input
              type="text"
              value={item}
              onChange={(e) => {
                const newItems = [...items];
                newItems[idx] = e.target.value;
                onChange(newItems);
              }}
              style={{ ...inputStyle, flex: 1, fontSize: "12px" }}
            />
            <button
              onClick={() => onChange(items.filter((_, i) => i !== idx))}
              style={{ ...addButtonStyle, backgroundColor: colors.severity.danger, padding: "4px 8px" }}
            >
              x
            </button>
          </div>
        ))}
        <div style={{ display: "flex", gap: "6px" }}>
          <input
            type="text"
            value={newItem}
            onChange={(e) => setNewItem(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleAdd()}
            placeholder={placeholder}
            style={{ ...inputStyle, flex: 1, fontSize: "12px" }}
          />
          <button onClick={handleAdd} style={addButtonStyle}>+</button>
        </div>
      </div>
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
  padding: "4px 10px",
  borderRadius: "4px",
  border: "none",
  backgroundColor: DESIGN_TOKENS.colors.primary.main,
  color: DESIGN_TOKENS.colors.contrast.light,
  fontSize: "11px",
  fontWeight: 500,
  cursor: "pointer",
};
