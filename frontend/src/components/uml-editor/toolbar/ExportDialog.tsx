/**
 * ExportDialog - Modal for exporting UML project to XML
 *
 * Features:
 * - Preview XML
 * - Copy to clipboard
 * - Download as .xml file
 * - Validation status
 */

import { useMemo, useState } from "react";
import { useUmlEditorStore } from "../../../state/useUmlEditorStore";
import { projectToXml, downloadXml, copyXmlToClipboard } from "../../../utils/umlXmlExporter";
import { validateProject } from "../../../utils/umlValidator";
import { DESIGN_TOKENS } from "../../../theme/designTokens";

const { colors, borders } = DESIGN_TOKENS;

interface ExportDialogProps {
  isOpen: boolean;
  onClose: () => void;
}

export function ExportDialog({ isOpen, onClose }: ExportDialogProps): JSX.Element | null {
  const { project } = useUmlEditorStore();
  const [copyStatus, setCopyStatus] = useState<"idle" | "copied" | "error">("idle");

  const xml = useMemo(() => projectToXml(project), [project]);
  const validation = useMemo(() => validateProject(project), [project]);

  const handleCopy = async () => {
    const success = await copyXmlToClipboard(xml);
    setCopyStatus(success ? "copied" : "error");
    setTimeout(() => setCopyStatus("idle"), 2000);
  };

  const handleDownload = () => {
    const filename = `${project.name.toLowerCase().replace(/\s+/g, "-")}-v${project.version}.xml`;
    downloadXml(xml, filename);
  };

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
          width: "90%",
          maxWidth: "800px",
          maxHeight: "90vh",
          display: "flex",
          flexDirection: "column",
          boxShadow: "0 20px 40px rgba(0, 0, 0, 0.3)",
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div
          style={{
            padding: "16px 24px",
            borderBottom: `1px solid ${borders.default}`,
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <div>
            <h2 style={{ margin: 0, fontSize: "18px", color: colors.text.secondary }}>
              Export XML
            </h2>
            <div style={{ fontSize: "12px", color: colors.text.muted, marginTop: "4px" }}>
              {project.name} v{project.version}
            </div>
          </div>
          <button
            onClick={onClose}
            style={{
              border: "none",
              background: "transparent",
              color: colors.text.muted,
              cursor: "pointer",
              fontSize: "24px",
              padding: "4px 8px",
            }}
          >
            x
          </button>
        </div>

        {/* Validation Status */}
        <div
          style={{
            padding: "12px 24px",
            backgroundColor: validation.isValid ? colors.severity.success + "10" : colors.severity.danger + "10",
            borderBottom: `1px solid ${borders.default}`,
            display: "flex",
            alignItems: "center",
            gap: "16px",
          }}
        >
          <span
            style={{
              display: "flex",
              alignItems: "center",
              gap: "8px",
              color: validation.isValid ? colors.severity.success : colors.severity.danger,
              fontWeight: 600,
              fontSize: "13px",
            }}
          >
            {validation.isValid ? "✓" : "!"} {validation.isValid ? "Valid" : "Has Errors"}
          </span>
          <span style={{ color: colors.text.muted, fontSize: "12px" }}>|</span>
          <span style={{ fontSize: "12px", color: colors.severity.danger }}>
            {validation.errorCount} error{validation.errorCount !== 1 ? "s" : ""}
          </span>
          <span style={{ fontSize: "12px", color: colors.severity.warning }}>
            {validation.warningCount} warning{validation.warningCount !== 1 ? "s" : ""}
          </span>
          <span style={{ fontSize: "12px", color: colors.primary.main }}>
            {validation.infoCount} info
          </span>
        </div>

        {/* XML Preview */}
        <div style={{ flex: 1, overflow: "auto", padding: "16px 24px" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
            <span style={{ fontSize: "11px", fontWeight: 600, color: colors.text.muted, textTransform: "uppercase" }}>
              XML Preview
            </span>
            <span style={{ fontSize: "11px", color: colors.text.muted }}>
              {xml.split("\n").length} lines
            </span>
          </div>
          <pre
            style={{
              margin: 0,
              padding: "16px",
              backgroundColor: colors.base.panel,
              borderRadius: "8px",
              border: `1px solid ${borders.default}`,
              fontSize: "12px",
              fontFamily: "monospace",
              color: colors.text.secondary,
              overflow: "auto",
              whiteSpace: "pre",
              maxHeight: "400px",
            }}
          >
            {xml}
          </pre>
        </div>

        {/* Actions */}
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
            Use this XML with Claude to generate code
          </div>
          <div style={{ display: "flex", gap: "12px" }}>
            <button
              onClick={onClose}
              style={{
                padding: "10px 20px",
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
              onClick={handleCopy}
              style={{
                padding: "10px 20px",
                borderRadius: "6px",
                border: `1px solid ${colors.primary.main}`,
                backgroundColor: "transparent",
                color: colors.primary.main,
                fontSize: "13px",
                fontWeight: 500,
                cursor: "pointer",
                minWidth: "140px",
              }}
            >
              {copyStatus === "copied" ? "✓ Copied!" : copyStatus === "error" ? "Failed" : "Copy to Clipboard"}
            </button>
            <button
              onClick={handleDownload}
              style={{
                padding: "10px 20px",
                borderRadius: "6px",
                border: "none",
                backgroundColor: colors.primary.main,
                color: colors.contrast.light,
                fontSize: "13px",
                fontWeight: 500,
                cursor: "pointer",
              }}
            >
              Download .xml
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
