/**
 * Templates Dialog - Design Pattern Template Selection
 *
 * Allows users to select and apply GoF design patterns to the canvas.
 * Organized by category: Creational, Structural, Behavioral.
 */

import { useState, useCallback, useMemo } from "react";
import { useUmlEditorStore } from "../../../state/useUmlEditorStore";
import {
  PATTERN_CATEGORIES,
  DESIGN_PATTERN_TEMPLATES,
  getTemplatesByCategory,
  type PatternCategory,
  type DesignPatternTemplate,
} from "../../../config/designPatternTemplates";
import { DESIGN_TOKENS } from "../../../theme/designTokens";

const { colors, borders } = DESIGN_TOKENS;

interface TemplatesDialogProps {
  isOpen: boolean;
  onClose: () => void;
}

export function TemplatesDialog({ isOpen, onClose }: TemplatesDialogProps): JSX.Element | null {
  const { project, applyTemplate } = useUmlEditorStore();
  const [selectedCategory, setSelectedCategory] = useState<PatternCategory>("creational");
  const [selectedTemplate, setSelectedTemplate] = useState<DesignPatternTemplate | null>(null);

  // Filter templates by category
  const filteredTemplates = useMemo(
    () => getTemplatesByCategory(selectedCategory),
    [selectedCategory]
  );

  // Handle template application
  const handleApply = useCallback(() => {
    if (selectedTemplate) {
      applyTemplate(selectedTemplate);
      onClose();
    }
  }, [selectedTemplate, applyTemplate, onClose]);

  // Handle category change
  const handleCategoryChange = useCallback((category: PatternCategory) => {
    setSelectedCategory(category);
    setSelectedTemplate(null);
  }, []);

  // Count entities by type
  const entityCounts = useMemo(() => {
    if (!selectedTemplate) return { classes: 0, interfaces: 0, relationships: 0 };
    return {
      classes: selectedTemplate.entities.filter((e) => e.type === "class").length,
      interfaces: selectedTemplate.entities.filter((e) => e.type === "interface").length,
      relationships: selectedTemplate.relationships.length,
    };
  }, [selectedTemplate]);

  if (!isOpen) return null;

  return (
    <div
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        right: 0,
        bottom: 0,
        backgroundColor: "rgba(0, 0, 0, 0.6)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 1000,
      }}
      onClick={onClose}
    >
      <div
        style={{
          backgroundColor: colors.base.card,
          borderRadius: "12px",
          width: "900px",
          maxWidth: "95vw",
          maxHeight: "80vh",
          display: "flex",
          flexDirection: "column",
          border: `1px solid ${borders.default}`,
          overflow: "hidden",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div
          style={{
            padding: "16px 24px",
            borderBottom: `1px solid ${borders.default}`,
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <div>
            <h2 style={{ margin: 0, fontSize: "18px", color: colors.text.secondary }}>
              Design Pattern Templates
            </h2>
            <p style={{ margin: "4px 0 0 0", fontSize: "12px", color: colors.text.muted }}>
              Select a pattern to add pre-configured classes and relationships
            </p>
          </div>
          <button
            onClick={onClose}
            style={{
              width: "32px",
              height: "32px",
              borderRadius: "6px",
              border: "none",
              backgroundColor: "transparent",
              color: colors.text.muted,
              fontSize: "20px",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
            }}
          >
            x
          </button>
        </div>

        {/* Body */}
        <div style={{ flex: 1, display: "flex", overflow: "hidden" }}>
          {/* Left Sidebar */}
          <div
            style={{
              width: "280px",
              borderRight: `1px solid ${borders.default}`,
              display: "flex",
              flexDirection: "column",
              overflow: "hidden",
            }}
          >
            {/* Category Tabs */}
            <div
              style={{
                display: "flex",
                padding: "12px",
                gap: "8px",
                borderBottom: `1px solid ${borders.default}`,
              }}
            >
              {PATTERN_CATEGORIES.map((cat) => (
                <button
                  key={cat.id}
                  onClick={() => handleCategoryChange(cat.id)}
                  style={{
                    flex: 1,
                    padding: "8px 12px",
                    borderRadius: "6px",
                    border: "none",
                    backgroundColor:
                      selectedCategory === cat.id ? colors.primary.main : "transparent",
                    color:
                      selectedCategory === cat.id ? colors.contrast.light : colors.text.muted,
                    fontSize: "12px",
                    fontWeight: 500,
                    cursor: "pointer",
                    transition: "all 0.15s ease",
                  }}
                  title={cat.description}
                >
                  {cat.name}
                </button>
              ))}
            </div>

            {/* Template List */}
            <div style={{ flex: 1, overflow: "auto", padding: "8px" }}>
              {filteredTemplates.map((template) => (
                <div
                  key={template.id}
                  onClick={() => setSelectedTemplate(template)}
                  style={{
                    padding: "12px",
                    marginBottom: "4px",
                    borderRadius: "8px",
                    cursor: "pointer",
                    backgroundColor:
                      selectedTemplate?.id === template.id
                        ? colors.primary.main + "20"
                        : "transparent",
                    border:
                      selectedTemplate?.id === template.id
                        ? `1px solid ${colors.primary.main}40`
                        : "1px solid transparent",
                    transition: "all 0.15s ease",
                  }}
                >
                  <div
                    style={{
                      fontSize: "13px",
                      fontWeight: 600,
                      color:
                        selectedTemplate?.id === template.id
                          ? colors.primary.light
                          : colors.text.secondary,
                      marginBottom: "4px",
                    }}
                  >
                    {template.name}
                  </div>
                  <div
                    style={{
                      fontSize: "11px",
                      color: colors.text.muted,
                      lineHeight: 1.4,
                      display: "-webkit-box",
                      WebkitLineClamp: 2,
                      WebkitBoxOrient: "vertical",
                      overflow: "hidden",
                    }}
                  >
                    {template.description}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Right Preview Panel */}
          <div
            style={{
              flex: 1,
              padding: "20px 24px",
              overflow: "auto",
              backgroundColor: colors.base.panel,
            }}
          >
            {selectedTemplate ? (
              <>
                {/* Template Title */}
                <h3
                  style={{
                    margin: "0 0 8px 0",
                    fontSize: "20px",
                    color: colors.text.secondary,
                  }}
                >
                  {selectedTemplate.name}
                </h3>

                {/* Reference */}
                {selectedTemplate.reference && (
                  <div
                    style={{
                      fontSize: "11px",
                      color: colors.text.muted,
                      marginBottom: "12px",
                    }}
                  >
                    {selectedTemplate.reference}
                  </div>
                )}

                {/* Description */}
                <p
                  style={{
                    margin: "0 0 20px 0",
                    fontSize: "13px",
                    color: colors.text.secondary,
                    lineHeight: 1.6,
                  }}
                >
                  {selectedTemplate.description}
                </p>

                {/* Stats */}
                <div
                  style={{
                    display: "flex",
                    gap: "24px",
                    padding: "16px",
                    backgroundColor: colors.base.card,
                    borderRadius: "8px",
                    marginBottom: "20px",
                  }}
                >
                  <div>
                    <div style={{ fontSize: "20px", fontWeight: 600, color: colors.primary.main }}>
                      {entityCounts.classes}
                    </div>
                    <div style={{ fontSize: "11px", color: colors.text.muted }}>Classes</div>
                  </div>
                  <div>
                    <div style={{ fontSize: "20px", fontWeight: 600, color: colors.callFlow.class }}>
                      {entityCounts.interfaces}
                    </div>
                    <div style={{ fontSize: "11px", color: colors.text.muted }}>Interfaces</div>
                  </div>
                  <div>
                    <div style={{ fontSize: "20px", fontWeight: 600, color: colors.text.muted }}>
                      {entityCounts.relationships}
                    </div>
                    <div style={{ fontSize: "11px", color: colors.text.muted }}>Relationships</div>
                  </div>
                </div>

                {/* Entity List */}
                <div style={{ marginBottom: "20px" }}>
                  <h4
                    style={{
                      margin: "0 0 12px 0",
                      fontSize: "12px",
                      fontWeight: 600,
                      color: colors.text.muted,
                      textTransform: "uppercase",
                    }}
                  >
                    Entities
                  </h4>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
                    {selectedTemplate.entities.map((entity) => (
                      <div
                        key={entity.key}
                        style={{
                          padding: "6px 12px",
                          borderRadius: "6px",
                          backgroundColor: colors.base.card,
                          border: `1px solid ${borders.default}`,
                          display: "flex",
                          alignItems: "center",
                          gap: "8px",
                        }}
                      >
                        <span
                          style={{
                            fontSize: "10px",
                            fontWeight: 600,
                            color:
                              entity.type === "class"
                                ? colors.primary.main
                                : colors.callFlow.class,
                            textTransform: "uppercase",
                          }}
                        >
                          {entity.type === "class" ? "C" : "I"}
                        </span>
                        <span style={{ fontSize: "12px", color: colors.text.secondary }}>
                          {entity.name}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Relationship Preview */}
                {selectedTemplate.relationships.length > 0 && (
                  <div>
                    <h4
                      style={{
                        margin: "0 0 12px 0",
                        fontSize: "12px",
                        fontWeight: 600,
                        color: colors.text.muted,
                        textTransform: "uppercase",
                      }}
                    >
                      Relationships
                    </h4>
                    <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
                      {selectedTemplate.relationships.slice(0, 6).map((rel, idx) => {
                        const fromEntity = selectedTemplate.entities.find(
                          (e) => e.key === rel.from
                        );
                        const toEntity = selectedTemplate.entities.find((e) => e.key === rel.to);
                        return (
                          <div
                            key={idx}
                            style={{
                              fontSize: "11px",
                              color: colors.text.muted,
                              display: "flex",
                              alignItems: "center",
                              gap: "6px",
                            }}
                          >
                            <span style={{ color: colors.text.secondary }}>
                              {fromEntity?.name ?? rel.from}
                            </span>
                            <span style={{ color: colors.callFlow.edgeLabel }}>
                              --[{rel.type}]--&gt;
                            </span>
                            <span style={{ color: colors.text.secondary }}>
                              {toEntity?.name ?? rel.to}
                            </span>
                          </div>
                        );
                      })}
                      {selectedTemplate.relationships.length > 6 && (
                        <div style={{ fontSize: "11px", color: colors.text.muted }}>
                          +{selectedTemplate.relationships.length - 6} more relationships
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </>
            ) : (
              <div
                style={{
                  height: "100%",
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  justifyContent: "center",
                  color: colors.text.muted,
                }}
              >
                <div style={{ fontSize: "48px", marginBottom: "16px", opacity: 0.3 }}>
                  {PATTERN_CATEGORIES.find((c) => c.id === selectedCategory)?.icon}
                </div>
                <div style={{ fontSize: "14px" }}>
                  Select a pattern from the list to preview
                </div>
                <div style={{ fontSize: "12px", marginTop: "8px" }}>
                  {filteredTemplates.length} patterns available in{" "}
                  {PATTERN_CATEGORIES.find((c) => c.id === selectedCategory)?.name}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div
          style={{
            padding: "16px 24px",
            borderTop: `1px solid ${borders.default}`,
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
          }}
        >
          <div style={{ fontSize: "12px", color: colors.text.muted }}>
            Target language: <strong>{project.targetLanguage}</strong> | Total patterns:{" "}
            {DESIGN_PATTERN_TEMPLATES.length}
          </div>
          <div style={{ display: "flex", gap: "12px" }}>
            <button
              onClick={onClose}
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
              onClick={handleApply}
              disabled={!selectedTemplate}
              style={{
                padding: "8px 20px",
                borderRadius: "6px",
                border: "none",
                backgroundColor: selectedTemplate ? colors.primary.main : colors.gray[600],
                color: colors.contrast.light,
                fontSize: "13px",
                fontWeight: 500,
                cursor: selectedTemplate ? "pointer" : "not-allowed",
                opacity: selectedTemplate ? 1 : 0.6,
              }}
            >
              Apply Template
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
