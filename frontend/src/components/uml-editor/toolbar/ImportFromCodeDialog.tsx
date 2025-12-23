/**
 * Import From Code Dialog - Import existing code as UML entities
 *
 * Allows users to scan their codebase (Python + TypeScript) and import
 * the discovered classes, interfaces, and relationships into the UML Editor.
 */

import { useState, useCallback } from "react";
import { useUmlEditorStore } from "../../../state/useUmlEditorStore";
import { getCodeAsUmlProject } from "../../../api/client";
import { DESIGN_TOKENS } from "../../../theme/designTokens";
import type { UmlProjectDef } from "../../../api/types";

const { colors, borders } = DESIGN_TOKENS;

interface ImportFromCodeDialogProps {
  isOpen: boolean;
  onClose: () => void;
}

type ImportStatus = "idle" | "scanning" | "success" | "error";

interface ScanResult {
  classCount: number;
  interfaceCount: number;
  structCount: number;
  relationshipCount: number;
  project: UmlProjectDef | null;
}

export function ImportFromCodeDialog({
  isOpen,
  onClose,
}: ImportFromCodeDialogProps): JSX.Element | null {
  const { project, mergeProject } = useUmlEditorStore();

  const [modulePrefixes, setModulePrefixes] = useState("");
  const [includeExternal, setIncludeExternal] = useState(false);
  const [status, setStatus] = useState<ImportStatus>("idle");
  const [errorMessage, setErrorMessage] = useState("");
  const [scanResult, setScanResult] = useState<ScanResult | null>(null);

  const handleScan = useCallback(async () => {
    setStatus("scanning");
    setErrorMessage("");
    setScanResult(null);

    try {
      const prefixes = modulePrefixes
        .split(",")
        .map((p) => p.trim())
        .filter(Boolean);

      const result = await getCodeAsUmlProject({
        modulePrefixes: prefixes.length > 0 ? prefixes : undefined,
        includeExternal,
        targetLanguage: project.targetLanguage,
      });

      // Count entities
      let classCount = 0;
      let interfaceCount = 0;
      let structCount = 0;
      let relationshipCount = 0;

      for (const module of result.modules || []) {
        classCount += module.classes?.length || 0;
        interfaceCount += module.interfaces?.length || 0;
        structCount += module.structs?.length || 0;
        relationshipCount += module.relationships?.length || 0;
      }

      setScanResult({
        classCount,
        interfaceCount,
        structCount,
        relationshipCount,
        project: result as unknown as UmlProjectDef,
      });

      setStatus("success");
    } catch (error) {
      setStatus("error");
      setErrorMessage(error instanceof Error ? error.message : "Unknown error");
    }
  }, [modulePrefixes, includeExternal, project.targetLanguage]);

  const handleImport = useCallback(() => {
    if (scanResult?.project) {
      mergeProject(scanResult.project);
      onClose();
      setStatus("idle");
      setScanResult(null);
    }
  }, [scanResult, mergeProject, onClose]);

  const handleClose = useCallback(() => {
    if (status !== "scanning") {
      setStatus("idle");
      setErrorMessage("");
      setScanResult(null);
      onClose();
    }
  }, [status, onClose]);

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
      onClick={handleClose}
    >
      <div
        style={{
          backgroundColor: colors.base.card,
          borderRadius: "12px",
          width: "550px",
          maxWidth: "95vw",
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
              Import from Code
            </h2>
            <p style={{ margin: "4px 0 0 0", fontSize: "12px", color: colors.text.muted }}>
              Scan your codebase and import existing classes and interfaces
            </p>
          </div>
          <button
            onClick={handleClose}
            disabled={status === "scanning"}
            style={{
              width: "32px",
              height: "32px",
              borderRadius: "6px",
              border: "none",
              backgroundColor: "transparent",
              color: colors.text.muted,
              fontSize: "20px",
              cursor: status === "scanning" ? "not-allowed" : "pointer",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              opacity: status === "scanning" ? 0.5 : 1,
            }}
          >
            x
          </button>
        </div>

        {/* Body */}
        <div style={{ padding: "20px 24px" }}>
          {/* Info Box */}
          <div
            style={{
              padding: "12px 16px",
              backgroundColor: colors.primary.main + "15",
              border: `1px solid ${colors.primary.main}30`,
              borderRadius: "8px",
              marginBottom: "16px",
            }}
          >
            <div style={{ fontSize: "13px", color: colors.text.secondary }}>
              This will analyze <strong>Python</strong>, <strong>TypeScript/TSX</strong>, and <strong>C++</strong> files
              in the current workspace and extract classes, interfaces, structs, methods, and relationships.
            </div>
          </div>

          {/* Module Prefixes */}
          <div style={{ marginBottom: "16px" }}>
            <label
              style={{
                display: "block",
                fontSize: "12px",
                fontWeight: 500,
                color: colors.text.muted,
                marginBottom: "8px",
              }}
            >
              Module Prefixes (optional, comma-separated):
            </label>
            <input
              type="text"
              value={modulePrefixes}
              onChange={(e) => setModulePrefixes(e.target.value)}
              disabled={status === "scanning"}
              placeholder="e.g., code_map, frontend.components"
              style={{
                width: "100%",
                padding: "10px 12px",
                borderRadius: "6px",
                border: `1px solid ${borders.default}`,
                backgroundColor: colors.base.panel,
                color: colors.text.secondary,
                fontSize: "13px",
                outline: "none",
                boxSizing: "border-box",
              }}
            />
            <div style={{ fontSize: "11px", color: colors.text.muted, marginTop: "4px" }}>
              Leave empty to scan all modules
            </div>
          </div>

          {/* Include External */}
          <div style={{ marginBottom: "16px" }}>
            <label
              style={{
                display: "flex",
                alignItems: "center",
                gap: "8px",
                fontSize: "13px",
                color: colors.text.secondary,
                cursor: "pointer",
              }}
            >
              <input
                type="checkbox"
                checked={includeExternal}
                onChange={(e) => setIncludeExternal(e.target.checked)}
                disabled={status === "scanning"}
                style={{ cursor: "pointer" }}
              />
              Include external dependencies
            </label>
          </div>

          {/* Status Messages */}
          {status === "scanning" && (
            <div
              style={{
                padding: "12px 16px",
                backgroundColor: colors.primary.main + "20",
                border: `1px solid ${colors.primary.main}40`,
                borderRadius: "8px",
                display: "flex",
                alignItems: "center",
                gap: "12px",
                marginBottom: "16px",
              }}
            >
              <div
                style={{
                  width: "16px",
                  height: "16px",
                  border: `2px solid ${colors.primary.main}`,
                  borderTopColor: "transparent",
                  borderRadius: "50%",
                  animation: "spin 1s linear infinite",
                }}
              />
              <span style={{ fontSize: "13px", color: colors.primary.main }}>
                Scanning codebase... This may take a moment.
              </span>
              <style>{`
                @keyframes spin {
                  to { transform: rotate(360deg); }
                }
              `}</style>
            </div>
          )}

          {status === "error" && (
            <div
              style={{
                padding: "12px 16px",
                backgroundColor: colors.severity.danger + "20",
                border: `1px solid ${colors.severity.danger}40`,
                borderRadius: "8px",
                marginBottom: "16px",
              }}
            >
              <div style={{ fontSize: "13px", color: colors.severity.danger, fontWeight: 500 }}>
                Scan failed
              </div>
              <div style={{ fontSize: "12px", color: colors.text.muted, marginTop: "4px" }}>
                {errorMessage}
              </div>
            </div>
          )}

          {status === "success" && scanResult && (
            <div
              style={{
                padding: "16px",
                backgroundColor: colors.complexity.low + "15",
                border: `1px solid ${colors.complexity.low}40`,
                borderRadius: "8px",
                marginBottom: "16px",
              }}
            >
              <div
                style={{
                  fontSize: "14px",
                  color: colors.complexity.low,
                  fontWeight: 500,
                  marginBottom: "12px",
                }}
              >
                Scan Complete
              </div>
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "repeat(4, 1fr)",
                  gap: "12px",
                }}
              >
                <div style={{ textAlign: "center" }}>
                  <div
                    style={{
                      fontSize: "22px",
                      fontWeight: 600,
                      color: colors.primary.main,
                    }}
                  >
                    {scanResult.classCount}
                  </div>
                  <div style={{ fontSize: "11px", color: colors.text.muted }}>Classes</div>
                </div>
                <div style={{ textAlign: "center" }}>
                  <div
                    style={{
                      fontSize: "22px",
                      fontWeight: 600,
                      color: colors.callFlow.class,
                    }}
                  >
                    {scanResult.interfaceCount}
                  </div>
                  <div style={{ fontSize: "11px", color: colors.text.muted }}>Interfaces</div>
                </div>
                <div style={{ textAlign: "center" }}>
                  <div
                    style={{
                      fontSize: "22px",
                      fontWeight: 600,
                      color: colors.severity.info,
                    }}
                  >
                    {scanResult.structCount}
                  </div>
                  <div style={{ fontSize: "11px", color: colors.text.muted }}>Structs</div>
                </div>
                <div style={{ textAlign: "center" }}>
                  <div
                    style={{
                      fontSize: "22px",
                      fontWeight: 600,
                      color: colors.callFlow.method,
                    }}
                  >
                    {scanResult.relationshipCount}
                  </div>
                  <div style={{ fontSize: "11px", color: colors.text.muted }}>Relations</div>
                </div>
              </div>
            </div>
          )}
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
            Target: <strong>{project.targetLanguage}</strong>
          </div>
          <div style={{ display: "flex", gap: "12px" }}>
            <button
              onClick={handleClose}
              disabled={status === "scanning"}
              style={{
                padding: "8px 16px",
                borderRadius: "6px",
                border: `1px solid ${borders.default}`,
                backgroundColor: "transparent",
                color: colors.text.muted,
                fontSize: "13px",
                cursor: status === "scanning" ? "not-allowed" : "pointer",
                opacity: status === "scanning" ? 0.5 : 1,
              }}
            >
              Cancel
            </button>
            {status === "success" && scanResult ? (
              <button
                onClick={handleImport}
                disabled={
                  scanResult.classCount === 0 && scanResult.interfaceCount === 0 && scanResult.structCount === 0
                }
                style={{
                  padding: "8px 20px",
                  borderRadius: "6px",
                  border: "none",
                  backgroundColor:
                    scanResult.classCount > 0 || scanResult.interfaceCount > 0 || scanResult.structCount > 0
                      ? colors.primary.main
                      : colors.gray[600],
                  color: colors.contrast.light,
                  fontSize: "13px",
                  fontWeight: 500,
                  cursor:
                    scanResult.classCount > 0 || scanResult.interfaceCount > 0 || scanResult.structCount > 0
                      ? "pointer"
                      : "not-allowed",
                  opacity:
                    scanResult.classCount > 0 || scanResult.interfaceCount > 0 || scanResult.structCount > 0
                      ? 1
                      : 0.6,
                }}
              >
                Import to Canvas
              </button>
            ) : (
              <button
                onClick={handleScan}
                disabled={status === "scanning"}
                style={{
                  padding: "8px 20px",
                  borderRadius: "6px",
                  border: "none",
                  backgroundColor:
                    status !== "scanning" ? colors.primary.main : colors.gray[600],
                  color: colors.contrast.light,
                  fontSize: "13px",
                  fontWeight: 500,
                  cursor: status !== "scanning" ? "pointer" : "not-allowed",
                  opacity: status !== "scanning" ? 1 : 0.6,
                }}
              >
                {status === "scanning" ? "Scanning..." : "Scan Codebase"}
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
