/**
 * Tool Permission Modal
 *
 * Modal that appears when Claude Code needs user approval to execute a tool.
 * Shows tool name, input parameters, and approve/deny buttons.
 */

import { useState } from "react";
import { PendingPermission, PendingPTYPermission } from "../stores/claudeSessionStore";
import { getToolIcon } from "../types/claude-events";

// =============================================================================
// Types
// =============================================================================

interface ToolPermissionModalProps {
  permission: PendingPermission;
  onApprove: (always: boolean) => void;
  onDeny: () => void;
}

// =============================================================================
// Component
// =============================================================================

export function ToolPermissionModal({
  permission,
  onApprove,
  onDeny,
}: ToolPermissionModalProps) {
  const [expanded, setExpanded] = useState(false);
  const toolIcon = getToolIcon(permission.tool);

  // Format input for display
  const inputDisplay = JSON.stringify(permission.input, null, 2);
  const inputPreview = inputDisplay.length > 200
    ? inputDisplay.substring(0, 200) + "..."
    : inputDisplay;

  // Determine action description
  const getActionDescription = () => {
    const tool = permission.tool;
    const input = permission.input;

    if (tool === "Write" || tool === "Edit") {
      const filePath = input.file_path as string | undefined;
      return filePath
        ? `Modify file: ${filePath.split("/").pop()}`
        : "Modify a file";
    }
    if (tool === "Read") {
      const filePath = input.file_path as string | undefined;
      return filePath
        ? `Read file: ${filePath.split("/").pop()}`
        : "Read a file";
    }
    if (tool === "Bash") {
      const command = input.command as string | undefined;
      return command
        ? `Run command: ${command.length > 50 ? command.substring(0, 50) + "..." : command}`
        : "Execute a shell command";
    }
    if (tool === "Glob" || tool === "Grep") {
      return `Search files`;
    }
    if (tool.startsWith("mcp__")) {
      const parts = tool.split("__");
      return `Use ${parts[1]} tool: ${parts[2] || "action"}`;
    }
    return `Execute ${tool}`;
  };

  return (
    <>
      <div className="tool-permission-overlay" onClick={onDeny} aria-hidden="true" />
      <div
        className="tool-permission-modal"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="tool-permission-title"
        aria-describedby="tool-permission-desc"
      >
        {/* Header */}
        <div className="tool-permission-header">
          <div className="tool-permission-icon-wrapper">
            <span className="tool-permission-icon">{toolIcon}</span>
          </div>
          <div className="tool-permission-header-text">
            <h2 id="tool-permission-title">Permission Required</h2>
            <p id="tool-permission-desc">Claude wants to perform an action</p>
          </div>
        </div>

        {/* Content */}
        <div className="tool-permission-content">
          {/* Action summary */}
          <div className="tool-permission-action">
            <span className="action-label">Action:</span>
            <span className="action-value">{getActionDescription()}</span>
          </div>

          {/* Tool info */}
          <div className="tool-permission-tool">
            <span className="tool-label">Tool:</span>
            <code className="tool-value">{permission.tool}</code>
          </div>

          {/* Input details - collapsible */}
          <div className="tool-permission-details">
            <button
              className="details-toggle"
              onClick={() => setExpanded(!expanded)}
              aria-expanded={expanded}
            >
              <span className="toggle-icon">{expanded ? "▼" : "▶"}</span>
              <span>Input parameters</span>
            </button>
            {expanded && (
              <pre className="details-content">{inputDisplay}</pre>
            )}
            {!expanded && inputPreview.length < inputDisplay.length && (
              <pre className="details-preview">{inputPreview}</pre>
            )}
          </div>
        </div>

        {/* Actions */}
        <div className="tool-permission-actions">
          <button
            className="permission-btn deny"
            onClick={onDeny}
          >
            Deny
          </button>
          <button
            className="permission-btn approve-always"
            onClick={() => onApprove(true)}
            title="Approve this and similar actions without asking again"
          >
            Always Allow
          </button>
          <button
            className="permission-btn approve"
            onClick={() => onApprove(false)}
          >
            Allow Once
          </button>
        </div>
      </div>

      <style>{modalStyles}</style>
    </>
  );
}

// =============================================================================
// Styles
// =============================================================================

const modalStyles = `
.tool-permission-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.7);
  z-index: 2000;
  backdrop-filter: blur(4px);
}

.tool-permission-modal {
  position: fixed;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 90%;
  max-width: 480px;
  background: var(--agent-bg-primary);
  border: 1px solid var(--agent-accent-yellow);
  border-radius: 12px;
  z-index: 2001;
  box-shadow:
    0 0 0 1px var(--agent-accent-yellow),
    0 20px 60px rgba(0, 0, 0, 0.5),
    0 0 40px rgba(245, 158, 11, 0.1);
  animation: permission-modal-enter 0.2s ease-out;
}

@keyframes permission-modal-enter {
  from {
    opacity: 0;
    transform: translate(-50%, -50%) scale(0.95);
  }
  to {
    opacity: 1;
    transform: translate(-50%, -50%) scale(1);
  }
}

.tool-permission-header {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 20px;
  border-bottom: 1px solid var(--agent-border-primary);
  background: linear-gradient(
    180deg,
    rgba(245, 158, 11, 0.1) 0%,
    transparent 100%
  );
  border-radius: 12px 12px 0 0;
}

.tool-permission-icon-wrapper {
  width: 48px;
  height: 48px;
  background: rgba(245, 158, 11, 0.2);
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
}

.tool-permission-icon {
  font-size: 24px;
}

.tool-permission-header-text h2 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: var(--agent-accent-yellow);
}

.tool-permission-header-text p {
  margin: 4px 0 0;
  font-size: 13px;
  color: var(--agent-text-secondary);
}

.tool-permission-content {
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.tool-permission-action {
  display: flex;
  align-items: flex-start;
  gap: 8px;
}

.action-label {
  font-size: 13px;
  color: var(--agent-text-muted);
  min-width: 50px;
}

.action-value {
  font-size: 14px;
  color: var(--agent-text-primary);
  font-weight: 500;
}

.tool-permission-tool {
  display: flex;
  align-items: center;
  gap: 8px;
}

.tool-label {
  font-size: 13px;
  color: var(--agent-text-muted);
  min-width: 50px;
}

.tool-value {
  padding: 4px 10px;
  background: var(--agent-bg-tertiary);
  border-radius: 4px;
  font-size: 12px;
  color: var(--agent-accent-blue);
}

.tool-permission-details {
  border: 1px solid var(--agent-border-primary);
  border-radius: 8px;
  overflow: hidden;
}

.details-toggle {
  width: 100%;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  background: var(--agent-bg-secondary);
  border: none;
  color: var(--agent-text-secondary);
  font-size: 13px;
  cursor: pointer;
  text-align: left;
  transition: all 0.2s;
}

.details-toggle:hover {
  background: var(--agent-bg-tertiary);
  color: var(--agent-text-primary);
}

.toggle-icon {
  font-size: 10px;
  color: var(--agent-text-muted);
}

.details-content,
.details-preview {
  margin: 0;
  padding: 12px;
  background: var(--agent-bg-primary);
  font-family: monospace;
  font-size: 11px;
  color: var(--agent-text-secondary);
  max-height: 200px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-all;
}

.details-preview {
  color: var(--agent-text-muted);
  font-style: italic;
}

.tool-permission-actions {
  display: flex;
  gap: 10px;
  padding: 16px 20px;
  border-top: 1px solid var(--agent-border-primary);
  background: var(--agent-bg-secondary);
  border-radius: 0 0 12px 12px;
}

.permission-btn {
  flex: 1;
  padding: 10px 16px;
  border: none;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.permission-btn.deny {
  background: transparent;
  border: 1px solid var(--agent-border-secondary);
  color: var(--agent-text-secondary);
}

.permission-btn.deny:hover {
  background: rgba(239, 68, 68, 0.1);
  border-color: var(--agent-accent-red);
  color: var(--agent-accent-red);
}

.permission-btn.approve-always {
  background: var(--agent-bg-tertiary);
  border: 1px solid var(--agent-border-secondary);
  color: var(--agent-text-primary);
}

.permission-btn.approve-always:hover {
  background: var(--agent-border-secondary);
}

.permission-btn.approve {
  background: var(--agent-accent-green);
  color: white;
}

.permission-btn.approve:hover {
  background: var(--agent-accent-green-hover, #059669);
}

/* Responsive */
@media (max-width: 480px) {
  .tool-permission-modal {
    width: 95%;
    max-height: 90vh;
  }

  .tool-permission-actions {
    flex-direction: column;
  }

  .permission-btn {
    width: 100%;
  }
}
`;

// =============================================================================
// PTY Permission Modal
// =============================================================================

interface PTYPermissionModalProps {
  permission: PendingPTYPermission;
  onApprove: () => void;
  onDeny: () => void;
  onAlwaysAllow: () => void;
}

export function PTYPermissionModal({
  permission,
  onApprove,
  onDeny,
  onAlwaysAllow,
}: PTYPermissionModalProps) {
  return (
    <>
      <div className="tool-permission-overlay" onClick={onDeny} aria-hidden="true" />
      <div
        className="tool-permission-modal pty-permission-modal"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="pty-permission-title"
        aria-describedby="pty-permission-desc"
      >
        {/* Header */}
        <div className="tool-permission-header pty-header">
          <div className="tool-permission-icon-wrapper pty-icon-wrapper">
            <span className="tool-permission-icon">🔒</span>
          </div>
          <div className="tool-permission-header-text">
            <h2 id="pty-permission-title">Permission Required</h2>
            <p id="pty-permission-desc">Claude needs your approval to continue</p>
          </div>
        </div>

        {/* Content */}
        <div className="tool-permission-content pty-content">
          {/* Permission type */}
          <div className="pty-permission-type">
            <span className="pty-type-label">Type:</span>
            <span className="pty-type-value">{permission.permissionType}</span>
          </div>

          {/* Target if present */}
          {permission.target && (
            <div className="pty-permission-target">
              <span className="pty-target-label">Target:</span>
              <code className="pty-target-value">{permission.target}</code>
            </div>
          )}

          {/* Full text description */}
          <div className="pty-permission-text">
            <pre className="pty-full-text">{permission.fullText}</pre>
          </div>
        </div>

        {/* Actions */}
        <div className="tool-permission-actions">
          <button
            className="permission-btn deny"
            onClick={onDeny}
          >
            Deny
          </button>
          <button
            className="permission-btn approve-always"
            onClick={onAlwaysAllow}
            title="Approve this and similar actions without asking again"
          >
            Always Allow
          </button>
          <button
            className="permission-btn approve"
            onClick={onApprove}
          >
            Allow Once
          </button>
        </div>
      </div>

      <style>{ptyModalStyles}</style>
    </>
  );
}

const ptyModalStyles = `
.pty-permission-modal {
  border-color: var(--agent-accent-purple, #8b5cf6);
  box-shadow:
    0 0 0 1px var(--agent-accent-purple, #8b5cf6),
    0 20px 60px rgba(0, 0, 0, 0.5),
    0 0 40px rgba(139, 92, 246, 0.1);
}

.pty-header {
  background: linear-gradient(
    180deg,
    rgba(139, 92, 246, 0.1) 0%,
    transparent 100%
  );
}

.pty-icon-wrapper {
  background: rgba(139, 92, 246, 0.2);
}

.pty-header .tool-permission-header-text h2 {
  color: var(--agent-accent-purple, #8b5cf6);
}

.pty-permission-type {
  display: flex;
  align-items: center;
  gap: 8px;
}

.pty-type-label {
  font-size: 13px;
  color: var(--agent-text-muted);
  min-width: 50px;
}

.pty-type-value {
  font-size: 14px;
  font-weight: 500;
  color: var(--agent-accent-purple, #8b5cf6);
  text-transform: capitalize;
}

.pty-permission-target {
  display: flex;
  align-items: center;
  gap: 8px;
}

.pty-target-label {
  font-size: 13px;
  color: var(--agent-text-muted);
  min-width: 50px;
}

.pty-target-value {
  padding: 4px 10px;
  background: var(--agent-bg-tertiary);
  border-radius: 4px;
  font-size: 12px;
  color: var(--agent-accent-blue);
  word-break: break-all;
}

.pty-permission-text {
  border: 1px solid var(--agent-border-primary);
  border-radius: 8px;
  overflow: hidden;
}

.pty-full-text {
  margin: 0;
  padding: 12px;
  background: var(--agent-bg-primary);
  font-family: monospace;
  font-size: 12px;
  color: var(--agent-text-secondary);
  max-height: 200px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-word;
}
`;
