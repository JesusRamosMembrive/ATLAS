/**
 * Open Shell Modal Component
 *
 * Modal that prompts user to open a native system terminal when
 * they try to use slash commands that require shell configuration.
 */

import { useCallback } from "react";
import { type AgentType } from "../stores/claudeSessionStore";

interface OpenShellModalProps {
  /** Whether the modal is visible */
  visible: boolean;
  /** The agent type to launch in the terminal */
  agentType: AgentType;
  /** Working directory for the terminal */
  workingDirectory?: string;
  /** Called when modal is closed */
  onClose: () => void;
  /** Called when user confirms opening shell */
  onConfirm: () => void;
}

export function OpenShellModal({
  visible,
  agentType,
  workingDirectory,
  onClose,
  onConfirm,
}: OpenShellModalProps) {
  const handleConfirm = useCallback(() => {
    onConfirm();
    onClose();
  }, [onConfirm, onClose]);

  const handleBackdropClick = useCallback(
    (e: React.MouseEvent) => {
      if (e.target === e.currentTarget) {
        onClose();
      }
    },
    [onClose]
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      } else if (e.key === "Enter") {
        handleConfirm();
      }
    },
    [onClose, handleConfirm]
  );

  if (!visible) {
    return null;
  }

  const agentName = agentType === "claude" ? "Claude Code" : agentType === "codex" ? "Codex" : "Gemini";

  return (
    <div
      className="open-shell-modal-backdrop"
      onClick={handleBackdropClick}
      onKeyDown={handleKeyDown}
      role="dialog"
      aria-modal="true"
      aria-labelledby="shell-modal-title"
    >
      <div className="open-shell-modal">
        <div className="open-shell-modal-header">
          <span className="open-shell-modal-icon">💻</span>
          <h2 id="shell-modal-title" className="open-shell-modal-title">
            Open Terminal
          </h2>
        </div>

        <div className="open-shell-modal-content">
          <p className="open-shell-modal-message">
            Configuration must be done through a shell.
          </p>
          <p className="open-shell-modal-submessage">
            Do you want to open a terminal with <strong>{agentName}</strong>?
          </p>
          {workingDirectory && (
            <p className="open-shell-modal-directory">
              <span className="open-shell-modal-directory-label">Directory:</span>
              <code className="open-shell-modal-directory-path">{workingDirectory}</code>
            </p>
          )}
        </div>

        <div className="open-shell-modal-actions">
          <button
            className="open-shell-modal-button open-shell-modal-button-cancel"
            onClick={onClose}
          >
            Cancel
          </button>
          <button
            className="open-shell-modal-button open-shell-modal-button-confirm"
            onClick={handleConfirm}
            autoFocus
          >
            Open Terminal
          </button>
        </div>
      </div>
    </div>
  );
}

// CSS styles for the component
export const openShellModalStyles = `
/* Open Shell Modal */
.open-shell-modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
  backdrop-filter: blur(2px);
}

.open-shell-modal {
  background: var(--agent-bg-secondary);
  border: 1px solid var(--agent-border-secondary);
  border-radius: 12px;
  box-shadow: 0 8px 32px var(--agent-shadow);
  max-width: 420px;
  width: 90%;
  padding: 24px;
  animation: modal-appear 0.2s ease-out;
}

@keyframes modal-appear {
  from {
    opacity: 0;
    transform: scale(0.95) translateY(-10px);
  }
  to {
    opacity: 1;
    transform: scale(1) translateY(0);
  }
}

.open-shell-modal-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.open-shell-modal-icon {
  font-size: 28px;
}

.open-shell-modal-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--agent-text-primary);
  margin: 0;
}

.open-shell-modal-content {
  margin-bottom: 24px;
}

.open-shell-modal-message {
  font-size: 14px;
  color: var(--agent-text-primary);
  margin: 0 0 8px 0;
  line-height: 1.5;
}

.open-shell-modal-submessage {
  font-size: 14px;
  color: var(--agent-text-secondary);
  margin: 0;
  line-height: 1.5;
}

.open-shell-modal-submessage strong {
  color: var(--agent-accent-blue);
}

.open-shell-modal-directory {
  margin-top: 12px;
  padding: 8px 12px;
  background: var(--agent-bg-tertiary);
  border-radius: 6px;
  font-size: 12px;
}

.open-shell-modal-directory-label {
  color: var(--agent-text-muted);
  margin-right: 8px;
}

.open-shell-modal-directory-path {
  font-family: 'JetBrains Mono', monospace;
  color: var(--agent-text-secondary);
  word-break: break-all;
}

.open-shell-modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

.open-shell-modal-button {
  padding: 10px 20px;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s ease;
  border: none;
}

.open-shell-modal-button-cancel {
  background: var(--agent-bg-tertiary);
  color: var(--agent-text-secondary);
}

.open-shell-modal-button-cancel:hover {
  background: var(--agent-border-primary);
  color: var(--agent-text-primary);
}

.open-shell-modal-button-confirm {
  background: var(--agent-accent-blue);
  color: white;
}

.open-shell-modal-button-confirm:hover {
  background: var(--agent-accent-blue-hover, #3b82f6);
  transform: translateY(-1px);
}

.open-shell-modal-button-confirm:active {
  transform: translateY(0);
}

/* Mobile adjustments */
@media (max-width: 480px) {
  .open-shell-modal {
    padding: 20px;
    margin: 16px;
  }

  .open-shell-modal-actions {
    flex-direction: column-reverse;
  }

  .open-shell-modal-button {
    width: 100%;
    text-align: center;
  }
}
`;
