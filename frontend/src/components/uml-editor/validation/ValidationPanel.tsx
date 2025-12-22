/**
 * ValidationPanel - Shows validation errors and warnings
 *
 * Displays errors, warnings, and info messages from the UML validator.
 * Clicking on an error navigates to the related entity.
 */

import { useMemo } from "react";
import { useUmlEditorStore } from "../../../state/useUmlEditorStore";
import { validateModule } from "../../../utils/umlValidator";
import { DESIGN_TOKENS } from "../../../theme/designTokens";
import type { UmlValidationError } from "../../../api/types";

const { colors, borders } = DESIGN_TOKENS;

interface ValidationPanelProps {
  isExpanded: boolean;
  onToggle: () => void;
}

const SEVERITY_CONFIG = {
  error: {
    icon: "!",
    color: colors.severity.danger,
    label: "Errors",
  },
  warning: {
    icon: "⚠",
    color: colors.severity.warning,
    label: "Warnings",
  },
  info: {
    icon: "i",
    color: colors.primary.main,
    label: "Info",
  },
};

export function ValidationPanel({ isExpanded, onToggle }: ValidationPanelProps): JSX.Element {
  const { getCurrentModule, setSelectedNode } = useUmlEditorStore();
  const currentModule = getCurrentModule();

  const validationResult = useMemo(() => {
    if (!currentModule) return null;
    return validateModule(currentModule);
  }, [currentModule]);

  const handleErrorClick = (error: UmlValidationError) => {
    // Navigate to the entity
    setSelectedNode(error.entityId);
  };

  if (!validationResult) {
    return <div />;
  }

  const { isValid, errors, errorCount, warningCount, infoCount } = validationResult;

  // Collapsed view - just the summary bar
  if (!isExpanded) {
    return (
      <div
        onClick={onToggle}
        style={{
          padding: "8px 24px",
          borderTop: `1px solid ${borders.default}`,
          backgroundColor: isValid ? colors.base.card : colors.severity.danger + "10",
          display: "flex",
          alignItems: "center",
          gap: "16px",
          fontSize: "12px",
          cursor: "pointer",
          transition: "background-color 0.2s",
        }}
      >
        <span
          style={{
            display: "flex",
            alignItems: "center",
            gap: "6px",
            color: isValid ? colors.severity.success : colors.severity.danger,
            fontWeight: 600,
          }}
        >
          {isValid ? "✓" : "!"} {isValid ? "Valid" : "Invalid"}
        </span>
        <span style={{ color: colors.text.muted }}>|</span>
        {errorCount > 0 && (
          <span style={{ color: colors.severity.danger }}>
            {errorCount} error{errorCount !== 1 ? "s" : ""}
          </span>
        )}
        {warningCount > 0 && (
          <span style={{ color: colors.severity.warning }}>
            {warningCount} warning{warningCount !== 1 ? "s" : ""}
          </span>
        )}
        {infoCount > 0 && (
          <span style={{ color: colors.primary.main }}>
            {infoCount} info
          </span>
        )}
        {errorCount === 0 && warningCount === 0 && infoCount === 0 && (
          <span style={{ color: colors.text.muted }}>No issues</span>
        )}
        <div style={{ flex: 1 }} />
        <span style={{ color: colors.text.muted, fontSize: "10px" }}>
          Click to {isExpanded ? "collapse" : "expand"}
        </span>
      </div>
    );
  }

  // Expanded view - full error list
  return (
    <div
      style={{
        borderTop: `1px solid ${borders.default}`,
        backgroundColor: colors.base.card,
        maxHeight: "200px",
        display: "flex",
        flexDirection: "column",
      }}
    >
      {/* Header */}
      <div
        onClick={onToggle}
        style={{
          padding: "8px 24px",
          backgroundColor: isValid ? colors.base.panel : colors.severity.danger + "10",
          display: "flex",
          alignItems: "center",
          gap: "16px",
          fontSize: "12px",
          cursor: "pointer",
          borderBottom: `1px solid ${borders.default}`,
          flexShrink: 0,
        }}
      >
        <span
          style={{
            display: "flex",
            alignItems: "center",
            gap: "6px",
            color: isValid ? colors.severity.success : colors.severity.danger,
            fontWeight: 600,
          }}
        >
          {isValid ? "✓" : "!"} Validation
        </span>
        <span style={{ color: colors.text.muted }}>|</span>
        <span style={{ color: colors.severity.danger }}>{errorCount} errors</span>
        <span style={{ color: colors.severity.warning }}>{warningCount} warnings</span>
        <span style={{ color: colors.primary.main }}>{infoCount} info</span>
        <div style={{ flex: 1 }} />
        <span style={{ color: colors.text.muted, fontSize: "10px" }}>
          Click to collapse
        </span>
      </div>

      {/* Error List */}
      <div style={{ flex: 1, overflow: "auto", padding: "8px 0" }}>
        {errors.length === 0 ? (
          <div
            style={{
              padding: "16px 24px",
              textAlign: "center",
              color: colors.text.muted,
            }}
          >
            No validation issues found
          </div>
        ) : (
          errors.map((error, idx) => {
            const config = SEVERITY_CONFIG[error.severity];
            return (
              <div
                key={idx}
                onClick={() => handleErrorClick(error)}
                style={{
                  padding: "6px 24px",
                  display: "flex",
                  alignItems: "flex-start",
                  gap: "12px",
                  cursor: "pointer",
                  transition: "background-color 0.15s",
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.backgroundColor = colors.base.panel;
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.backgroundColor = "transparent";
                }}
              >
                <span
                  style={{
                    width: "18px",
                    height: "18px",
                    borderRadius: "50%",
                    backgroundColor: config.color + "20",
                    color: config.color,
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    fontSize: "10px",
                    fontWeight: 700,
                    flexShrink: 0,
                  }}
                >
                  {config.icon}
                </span>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div
                    style={{
                      fontSize: "12px",
                      color: colors.text.secondary,
                      lineHeight: 1.4,
                    }}
                  >
                    {error.message}
                  </div>
                  <div
                    style={{
                      fontSize: "10px",
                      color: colors.text.muted,
                      marginTop: "2px",
                    }}
                  >
                    {error.code}
                    {error.field && ` • ${error.field}`}
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
