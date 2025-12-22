/**
 * ImportExportDialog - Modal for importing/exporting UML projects
 *
 * Features:
 * - Import: Load XML files, paste XML, preview before import
 * - Export: Preview XML, copy to clipboard, download as .xml file
 * - Confirmation before replacing existing project
 */

import { useMemo, useState, useRef, useCallback } from "react";
import { useUmlEditorStore } from "../../../state/useUmlEditorStore";
import { projectToXml, downloadXml, copyXmlToClipboard } from "../../../utils/umlXmlExporter";
import { xmlToProject, readXmlFile } from "../../../utils/umlXmlImporter";
import { validateProject } from "../../../utils/umlValidator";
import { DESIGN_TOKENS } from "../../../theme/designTokens";

const { colors, borders } = DESIGN_TOKENS;

// Helper color for success (using complexity.low which is green)
const successColor = colors.complexity.low;

type TabType = "export" | "import";

interface ImportExportDialogProps {
  isOpen: boolean;
  onClose: () => void;
  initialTab?: TabType;
}

export function ImportExportDialog({ isOpen, onClose, initialTab = "export" }: ImportExportDialogProps): JSX.Element | null {
  const { project, setProject } = useUmlEditorStore();
  const [activeTab, setActiveTab] = useState<TabType>(initialTab);
  const [copyStatus, setCopyStatus] = useState<"idle" | "copied" | "error">("idle");

  // Import state
  const [importXml, setImportXml] = useState("");
  const [importError, setImportError] = useState<string | null>(null);
  const [importPreview, setImportPreview] = useState<{ name: string; modules: number; entities: number } | null>(null);
  const [showConfirmDialog, setShowConfirmDialog] = useState(false);
  const [pendingProject, setPendingProject] = useState<ReturnType<typeof xmlToProject>["project"] | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const xml = useMemo(() => projectToXml(project), [project]);
  const validation = useMemo(() => validateProject(project), [project]);

  // Check if current project has content
  const hasExistingContent = useMemo(() => {
    return project.modules.some(
      (m) => m.classes.length > 0 || m.interfaces.length > 0 || m.enums.length > 0 || m.structs.length > 0
    );
  }, [project]);

  const handleCopy = async () => {
    const success = await copyXmlToClipboard(xml);
    setCopyStatus(success ? "copied" : "error");
    setTimeout(() => setCopyStatus("idle"), 2000);
  };

  const handleDownload = () => {
    const filename = `${project.name.toLowerCase().replace(/\s+/g, "-")}-v${project.version}.xml`;
    downloadXml(xml, filename);
  };

  // Parse and preview XML
  const handleParseXml = useCallback((xmlContent: string) => {
    setImportXml(xmlContent);
    setImportError(null);
    setImportPreview(null);

    if (!xmlContent.trim()) {
      return;
    }

    const result = xmlToProject(xmlContent);
    if (!result.success) {
      setImportError(result.error ?? "Unknown error");
      return;
    }

    if (result.project) {
      const entityCount = result.project.modules.reduce(
        (acc, m) => acc + m.classes.length + m.interfaces.length + m.enums.length + m.structs.length,
        0
      );
      setImportPreview({
        name: result.project.name,
        modules: result.project.modules.length,
        entities: entityCount,
      });
      setPendingProject(result.project);
    }
  }, []);

  // Handle file selection
  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const result = await readXmlFile(file);
    if (!result.success) {
      setImportError(result.error ?? "Failed to read file");
      setImportPreview(null);
      return;
    }

    // Read file content for display
    const reader = new FileReader();
    reader.onload = (ev) => {
      const content = ev.target?.result;
      if (typeof content === "string") {
        handleParseXml(content);
      }
    };
    reader.readAsText(file);

    // Reset file input
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  // Handle import action
  const handleImport = () => {
    if (!pendingProject) return;

    if (hasExistingContent) {
      setShowConfirmDialog(true);
    } else {
      doImport();
    }
  };

  // Actually perform the import
  const doImport = () => {
    if (!pendingProject) return;
    setProject(pendingProject);
    setShowConfirmDialog(false);
    setPendingProject(null);
    setImportXml("");
    setImportPreview(null);
    onClose();
  };

  const handleCancelConfirm = () => {
    setShowConfirmDialog(false);
  };

  if (!isOpen) return null;

  const tabStyle = (tab: TabType) => ({
    padding: "12px 24px",
    border: "none",
    borderBottom: activeTab === tab ? `2px solid ${colors.primary.main}` : "2px solid transparent",
    backgroundColor: "transparent",
    color: activeTab === tab ? colors.primary.main : colors.text.muted,
    fontSize: "14px",
    fontWeight: activeTab === tab ? 600 : 400,
    cursor: "pointer",
    transition: "all 0.2s",
  });

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
        {/* Header with Tabs */}
        <div
          style={{
            borderBottom: `1px solid ${borders.default}`,
          }}
        >
          <div
            style={{
              padding: "16px 24px 0",
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
            }}
          >
            <h2 style={{ margin: 0, fontSize: "18px", color: colors.text.secondary }}>
              Import / Export Project
            </h2>
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
              ×
            </button>
          </div>
          <div style={{ display: "flex", gap: "0", marginTop: "8px" }}>
            <button style={tabStyle("import")} onClick={() => setActiveTab("import")}>
              Import XML
            </button>
            <button style={tabStyle("export")} onClick={() => setActiveTab("export")}>
              Export XML
            </button>
          </div>
        </div>

        {/* Tab Content */}
        {activeTab === "export" ? (
          <>
            {/* Validation Status */}
            <div
              style={{
                padding: "12px 24px",
                backgroundColor: validation.isValid ? successColor + "10" : colors.severity.danger + "10",
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
                  color: validation.isValid ? successColor : colors.severity.danger,
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

            {/* Export Actions */}
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
          </>
        ) : (
          <>
            {/* Import Content */}
            <div style={{ flex: 1, overflow: "auto", padding: "16px 24px" }}>
              {/* File Upload */}
              <div style={{ marginBottom: "16px" }}>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".xml"
                  onChange={handleFileSelect}
                  style={{ display: "none" }}
                  id="xml-file-input"
                />
                <label
                  htmlFor="xml-file-input"
                  style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: "8px",
                    padding: "10px 20px",
                    borderRadius: "6px",
                    border: `1px dashed ${colors.primary.main}`,
                    backgroundColor: colors.primary.main + "10",
                    color: colors.primary.main,
                    fontSize: "13px",
                    fontWeight: 500,
                    cursor: "pointer",
                  }}
                >
                  📁 Choose XML File
                </label>
                <span style={{ marginLeft: "12px", fontSize: "12px", color: colors.text.muted }}>
                  or paste XML below
                </span>
              </div>

              {/* XML Input */}
              <div style={{ marginBottom: "16px" }}>
                <label
                  style={{
                    display: "block",
                    fontSize: "11px",
                    fontWeight: 600,
                    color: colors.text.muted,
                    textTransform: "uppercase",
                    marginBottom: "8px",
                  }}
                >
                  XML Content
                </label>
                <textarea
                  value={importXml}
                  onChange={(e) => handleParseXml(e.target.value)}
                  placeholder="Paste your XML here..."
                  style={{
                    width: "100%",
                    height: "250px",
                    padding: "12px",
                    borderRadius: "8px",
                    border: `1px solid ${importError ? colors.severity.danger : borders.default}`,
                    backgroundColor: colors.base.panel,
                    color: colors.text.secondary,
                    fontSize: "12px",
                    fontFamily: "monospace",
                    resize: "vertical",
                  }}
                />
              </div>

              {/* Error Message */}
              {importError && (
                <div
                  style={{
                    padding: "12px 16px",
                    borderRadius: "8px",
                    backgroundColor: colors.severity.danger + "15",
                    border: `1px solid ${colors.severity.danger}30`,
                    color: colors.severity.danger,
                    fontSize: "13px",
                    marginBottom: "16px",
                  }}
                >
                  ⚠️ {importError}
                </div>
              )}

              {/* Import Preview */}
              {importPreview && (
                <div
                  style={{
                    padding: "16px",
                    borderRadius: "8px",
                    backgroundColor: successColor + "10",
                    border: `1px solid ${successColor}30`,
                  }}
                >
                  <div style={{ fontSize: "13px", fontWeight: 600, color: successColor, marginBottom: "8px" }}>
                    ✓ Valid XML - Ready to Import
                  </div>
                  <div style={{ display: "flex", gap: "24px", fontSize: "12px", color: colors.text.secondary }}>
                    <span>
                      <strong>Project:</strong> {importPreview.name}
                    </span>
                    <span>
                      <strong>Modules:</strong> {importPreview.modules}
                    </span>
                    <span>
                      <strong>Entities:</strong> {importPreview.entities}
                    </span>
                  </div>
                </div>
              )}
            </div>

            {/* Import Actions */}
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
                {hasExistingContent
                  ? "⚠️ Importing will replace the current project"
                  : "Import a previously exported project"}
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
                  onClick={handleImport}
                  disabled={!importPreview}
                  style={{
                    padding: "10px 20px",
                    borderRadius: "6px",
                    border: "none",
                    backgroundColor: importPreview ? colors.primary.main : colors.text.muted,
                    color: colors.contrast.light,
                    fontSize: "13px",
                    fontWeight: 500,
                    cursor: importPreview ? "pointer" : "not-allowed",
                    opacity: importPreview ? 1 : 0.5,
                  }}
                >
                  Import Project
                </button>
              </div>
            </div>
          </>
        )}
      </div>

      {/* Confirmation Dialog */}
      {showConfirmDialog && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: "rgba(0, 0, 0, 0.4)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1001,
          }}
          onClick={handleCancelConfirm}
        >
          <div
            style={{
              backgroundColor: colors.base.card,
              borderRadius: "12px",
              padding: "24px",
              maxWidth: "400px",
              boxShadow: "0 20px 40px rgba(0, 0, 0, 0.3)",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <h3 style={{ margin: "0 0 12px", fontSize: "16px", color: colors.text.secondary }}>
              Replace Current Project?
            </h3>
            <p style={{ margin: "0 0 20px", fontSize: "13px", color: colors.text.muted, lineHeight: 1.5 }}>
              You have an existing project with content. Importing will replace all current data with the imported project.
              <br />
              <br />
              This action cannot be undone.
            </p>
            <div style={{ display: "flex", gap: "12px", justifyContent: "flex-end" }}>
              <button
                onClick={handleCancelConfirm}
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
                onClick={doImport}
                style={{
                  padding: "10px 20px",
                  borderRadius: "6px",
                  border: "none",
                  backgroundColor: colors.severity.danger,
                  color: colors.contrast.light,
                  fontSize: "13px",
                  fontWeight: 500,
                  cursor: "pointer",
                }}
              >
                Replace Project
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// Re-export for backwards compatibility
export { ImportExportDialog as ExportDialog };
