/**
 * RelationshipInspector - Editor for UML Relationships
 */

import { useUmlEditorStore } from "../../../state/useUmlEditorStore";
import { DESIGN_TOKENS } from "../../../theme/designTokens";
import type { UmlRelationshipDef, UmlRelationshipType } from "../../../api/types";

const { colors, borders } = DESIGN_TOKENS;

const RELATIONSHIP_TYPES: { value: UmlRelationshipType; label: string; description: string }[] = [
  { value: "inheritance", label: "Inheritance", description: "extends (is-a relationship)" },
  { value: "implementation", label: "Implementation", description: "implements interface" },
  { value: "composition", label: "Composition", description: "owns (lifecycle bound)" },
  { value: "aggregation", label: "Aggregation", description: "has (independent lifecycle)" },
  { value: "association", label: "Association", description: "uses/knows about" },
  { value: "dependency", label: "Dependency", description: "depends on" },
];

interface RelationshipInspectorProps {
  relationshipId: string;
}

export function RelationshipInspector({ relationshipId }: RelationshipInspectorProps): JSX.Element | null {
  const { getRelationshipById, updateRelationship, getAllTypeNames, getClassById, getInterfaceById, getEnumById, getStructById } = useUmlEditorStore();
  const relationship = getRelationshipById(relationshipId);

  if (!relationship) return null;

  // Get names for from/to entities
  const getEntityName = (id: string): string => {
    const cls = getClassById(id);
    if (cls) return cls.name;
    const iface = getInterfaceById(id);
    if (iface) return iface.name;
    const enm = getEnumById(id);
    if (enm) return enm.name;
    const struct = getStructById(id);
    if (struct) return struct.name;
    return id;
  };

  const fromName = getEntityName(relationship.from);
  const toName = getEntityName(relationship.to);

  const handleChange = (field: keyof UmlRelationshipDef, value: any) => {
    updateRelationship(relationshipId, { [field]: value });
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
      {/* Relationship Summary */}
      <div
        style={{
          padding: "12px",
          backgroundColor: colors.base.panel,
          borderRadius: "6px",
          border: `1px solid ${borders.default}`,
        }}
      >
        <div style={{ fontSize: "13px", color: colors.text.muted, marginBottom: "8px" }}>
          Connection
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "8px", flexWrap: "wrap" }}>
          <span
            style={{
              padding: "4px 8px",
              backgroundColor: colors.primary.main,
              color: colors.contrast.light,
              borderRadius: "4px",
              fontSize: "12px",
              fontWeight: 500,
            }}
          >
            {fromName}
          </span>
          <span style={{ color: colors.text.muted, fontSize: "18px" }}>→</span>
          <span
            style={{
              padding: "4px 8px",
              backgroundColor: colors.callFlow.class,
              color: colors.contrast.light,
              borderRadius: "4px",
              fontSize: "12px",
              fontWeight: 500,
            }}
          >
            {toName}
          </span>
        </div>
      </div>

      {/* Relationship Type */}
      <div>
        <label style={labelStyle}>Type</label>
        <select
          value={relationship.type}
          onChange={(e) => handleChange("type", e.target.value as UmlRelationshipType)}
          style={inputStyle}
        >
          {RELATIONSHIP_TYPES.map((rt) => (
            <option key={rt.value} value={rt.value}>
              {rt.label}
            </option>
          ))}
        </select>
        <div style={{ fontSize: "11px", color: colors.text.muted, marginTop: "4px" }}>
          {RELATIONSHIP_TYPES.find((rt) => rt.value === relationship.type)?.description}
        </div>
      </div>

      {/* Label */}
      <div>
        <label style={labelStyle}>Label (optional)</label>
        <input
          type="text"
          value={relationship.label || ""}
          onChange={(e) => handleChange("label", e.target.value || undefined)}
          style={inputStyle}
          placeholder="e.g., 'uses', '1..*', 'parent'"
        />
      </div>

      {/* Cardinality */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
        <div>
          <label style={labelStyle}>From Cardinality</label>
          <input
            type="text"
            value={relationship.fromCardinality || ""}
            onChange={(e) => handleChange("fromCardinality", e.target.value || undefined)}
            style={inputStyle}
            placeholder="e.g., '1', '0..1', '*'"
          />
        </div>
        <div>
          <label style={labelStyle}>To Cardinality</label>
          <input
            type="text"
            value={relationship.toCardinality || ""}
            onChange={(e) => handleChange("toCardinality", e.target.value || undefined)}
            style={inputStyle}
            placeholder="e.g., '1', '0..*', '1..n'"
          />
        </div>
      </div>

      {/* Hints */}
      <div
        style={{
          padding: "12px",
          backgroundColor: colors.base.panel,
          borderRadius: "6px",
          fontSize: "12px",
          color: colors.text.muted,
        }}
      >
        <div style={{ fontWeight: 500, marginBottom: "6px", color: colors.text.secondary }}>
          Relationship Guide
        </div>
        <ul style={{ margin: 0, paddingLeft: "16px", lineHeight: 1.6 }}>
          <li><strong>Inheritance:</strong> Class A extends Class B</li>
          <li><strong>Implementation:</strong> Class implements Interface</li>
          <li><strong>Composition:</strong> Part cannot exist without Whole</li>
          <li><strong>Aggregation:</strong> Part can exist independently</li>
          <li><strong>Association:</strong> Objects know about each other</li>
          <li><strong>Dependency:</strong> Uses but doesn't hold reference</li>
        </ul>
      </div>
    </div>
  );
}

// Styles
const labelStyle: React.CSSProperties = {
  display: "block",
  fontSize: "12px",
  fontWeight: 500,
  color: colors.text.muted,
  marginBottom: "6px",
};

const inputStyle: React.CSSProperties = {
  width: "100%",
  padding: "8px 10px",
  borderRadius: "6px",
  border: `1px solid ${borders.default}`,
  backgroundColor: colors.base.panel,
  color: colors.text.secondary,
  fontSize: "13px",
  outline: "none",
  boxSizing: "border-box",
};
