/**
 * Permissions Modal
 *
 * Modal to view and manage Claude Code permissions for the Agent UI.
 * Allows users to add recommended permissions or individual ones.
 */

import { useState, useCallback, useEffect } from "react";
import { useBackendStore } from "../state/useBackendStore";
import { resolveBackendBaseUrl } from "../api/client";

// =============================================================================
// Types
// =============================================================================

interface ClaudePermissions {
  allow: string[];
  deny: string[];
  ask: string[];
}

interface PermissionsResponse {
  settings_path: string;
  exists: boolean;
  permissions: ClaudePermissions;
  recommended_permissions: string[];
}

interface AddPermissionsResponse {
  success: boolean;
  added: string[];
  already_present: string[];
  current_permissions: ClaudePermissions;
}

interface PermissionsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

// =============================================================================
// Component
// =============================================================================

export function PermissionsModal({ isOpen, onClose }: PermissionsModalProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [permissions, setPermissions] = useState<PermissionsResponse | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const backendUrl = useBackendStore((state) => state.backendUrl);

  const getApiUrl = useCallback(() => {
    const base = resolveBackendBaseUrl(backendUrl) ?? "http://127.0.0.1:8010";
    return base.replace(/\/+$/, "");
  }, [backendUrl]);

  // Fetch permissions on open
  const fetchPermissions = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${getApiUrl()}/api/claude-permissions`);
      if (!response.ok) {
        throw new Error(`Failed to fetch permissions: ${response.statusText}`);
      }
      const data: PermissionsResponse = await response.json();
      setPermissions(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load permissions");
    } finally {
      setLoading(false);
    }
  }, [getApiUrl]);

  useEffect(() => {
    if (isOpen) {
      fetchPermissions();
      setSuccessMessage(null);
    }
  }, [isOpen, fetchPermissions]);

  // Add recommended permissions
  const handleAddRecommended = useCallback(async () => {
    setLoading(true);
    setError(null);
    setSuccessMessage(null);
    try {
      const response = await fetch(`${getApiUrl()}/api/claude-permissions/add-recommended`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });
      if (!response.ok) {
        throw new Error(`Failed to add permissions: ${response.statusText}`);
      }
      const data: AddPermissionsResponse = await response.json();
      if (data.added.length > 0) {
        setSuccessMessage(`Added ${data.added.length} permissions: ${data.added.join(", ")}`);
      } else {
        setSuccessMessage("All recommended permissions are already present");
      }
      // Refresh permissions
      await fetchPermissions();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to add permissions");
    } finally {
      setLoading(false);
    }
  }, [getApiUrl, fetchPermissions]);

  // Add specific permission
  const handleAddPermission = useCallback(async (permission: string) => {
    setLoading(true);
    setError(null);
    setSuccessMessage(null);
    try {
      const response = await fetch(`${getApiUrl()}/api/claude-permissions/add`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ permissions: [permission] }),
      });
      if (!response.ok) {
        throw new Error(`Failed to add permission: ${response.statusText}`);
      }
      setSuccessMessage(`Added permission: ${permission}`);
      await fetchPermissions();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to add permission");
    } finally {
      setLoading(false);
    }
  }, [getApiUrl, fetchPermissions]);

  // Remove permission
  const handleRemovePermission = useCallback(async (permission: string) => {
    setLoading(true);
    setError(null);
    setSuccessMessage(null);
    try {
      const response = await fetch(`${getApiUrl()}/api/claude-permissions/${encodeURIComponent(permission)}`, {
        method: "DELETE",
      });
      if (!response.ok) {
        throw new Error(`Failed to remove permission: ${response.statusText}`);
      }
      setSuccessMessage(`Removed permission: ${permission}`);
      await fetchPermissions();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to remove permission");
    } finally {
      setLoading(false);
    }
  }, [getApiUrl, fetchPermissions]);

  if (!isOpen) return null;

  const hasMissingRecommended = permissions?.recommended_permissions && permissions.recommended_permissions.length > 0;

  return (
    <>
      <div className="permissions-overlay" onClick={onClose} aria-hidden="true" />
      <div
        className="permissions-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="permissions-title"
      >
        <div className="permissions-header">
          <h2 id="permissions-title">Claude Code Permissions</h2>
          <button className="close-btn" onClick={onClose} aria-label="Close">
            ×
          </button>
        </div>

        <div className="permissions-content">
          {loading && <div className="permissions-loading">Loading...</div>}

          {error && (
            <div className="permissions-error" role="alert">
              <span className="error-icon">⚠️</span>
              {error}
            </div>
          )}

          {successMessage && (
            <div className="permissions-success" role="status">
              <span className="success-icon">✓</span>
              {successMessage}
            </div>
          )}

          {permissions && !loading && (
            <>
              {/* Warning if missing permissions */}
              {hasMissingRecommended && (
                <div className="permissions-warning">
                  <h3>⚠️ Missing Recommended Permissions</h3>
                  <p>
                    The Agent UI needs certain permissions to work properly.
                    Without these, Claude Code will fail when trying to write files.
                  </p>
                  <div className="missing-list">
                    {permissions.recommended_permissions.map((perm) => (
                      <span key={perm} className="permission-badge missing">
                        {perm}
                      </span>
                    ))}
                  </div>
                  <button
                    className="add-recommended-btn"
                    onClick={handleAddRecommended}
                    disabled={loading}
                  >
                    Add All Recommended Permissions
                  </button>
                </div>
              )}

              {!hasMissingRecommended && (
                <div className="permissions-ok">
                  <span className="ok-icon">✓</span>
                  All recommended permissions are configured
                </div>
              )}

              {/* Current permissions */}
              <div className="permissions-section">
                <h3>Current Allowed Permissions ({permissions.permissions.allow.length})</h3>
                {permissions.permissions.allow.length === 0 ? (
                  <p className="no-permissions">No permissions configured</p>
                ) : (
                  <div className="permissions-list">
                    {permissions.permissions.allow.map((perm) => (
                      <div key={perm} className="permission-item">
                        <span className="permission-name">{perm}</span>
                        <button
                          className="remove-btn"
                          onClick={() => handleRemovePermission(perm)}
                          title="Remove permission"
                          disabled={loading}
                        >
                          ×
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>

              {/* Settings file path */}
              <div className="permissions-info">
                <span className="info-label">Settings file:</span>
                <code>{permissions.settings_path}</code>
              </div>
            </>
          )}
        </div>

        <div className="permissions-footer">
          <button className="close-modal-btn" onClick={onClose}>
            Close
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
.permissions-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.6);
  z-index: 1000;
}

.permissions-modal {
  position: fixed;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 90%;
  max-width: 600px;
  max-height: 80vh;
  background: var(--agent-bg-secondary);
  border: 1px solid var(--agent-border-primary);
  border-radius: 12px;
  z-index: 1001;
  display: flex;
  flex-direction: column;
  box-shadow: 0 20px 60px var(--agent-shadow);
}

.permissions-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid var(--agent-border-primary);
}

.permissions-header h2 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: var(--agent-text-primary);
}

.close-btn {
  width: 32px;
  height: 32px;
  background: transparent;
  border: none;
  color: var(--agent-text-secondary);
  font-size: 24px;
  cursor: pointer;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.close-btn:hover {
  background: var(--agent-bg-tertiary);
  color: var(--agent-text-primary);
}

.permissions-content {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
}

.permissions-loading {
  text-align: center;
  color: var(--agent-text-muted);
  padding: 40px;
}

.permissions-error {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: var(--agent-error-bg);
  border: 1px solid var(--agent-accent-red);
  border-radius: 8px;
  color: var(--agent-error-text);
  margin-bottom: 16px;
}

.permissions-success {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: var(--agent-success-bg);
  border: 1px solid var(--agent-accent-green);
  border-radius: 8px;
  color: var(--agent-accent-green);
  margin-bottom: 16px;
}

.permissions-warning {
  background: rgba(245, 158, 11, 0.1);
  border: 1px solid var(--agent-accent-yellow);
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 20px;
}

.permissions-warning h3 {
  margin: 0 0 8px;
  font-size: 14px;
  color: var(--agent-accent-yellow);
}

.permissions-warning p {
  margin: 0 0 12px;
  font-size: 13px;
  color: var(--agent-text-secondary);
}

.missing-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 16px;
}

.permission-badge {
  padding: 4px 10px;
  font-size: 12px;
  font-family: monospace;
  border-radius: 4px;
  background: var(--agent-bg-tertiary);
  color: var(--agent-text-secondary);
}

.permission-badge.missing {
  background: rgba(245, 158, 11, 0.2);
  color: var(--agent-accent-yellow);
}

.add-recommended-btn {
  width: 100%;
  padding: 10px 16px;
  background: var(--agent-accent-blue);
  border: none;
  border-radius: 6px;
  color: white;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: background 0.2s;
}

.add-recommended-btn:hover:not(:disabled) {
  background: var(--agent-accent-blue-hover);
}

.add-recommended-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.permissions-ok {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  background: var(--agent-success-bg);
  border: 1px solid var(--agent-accent-green);
  border-radius: 8px;
  color: var(--agent-accent-green);
  margin-bottom: 20px;
}

.ok-icon {
  font-size: 16px;
}

.permissions-section {
  margin-bottom: 20px;
}

.permissions-section h3 {
  margin: 0 0 12px;
  font-size: 14px;
  font-weight: 600;
  color: var(--agent-text-primary);
}

.no-permissions {
  color: var(--agent-text-muted);
  font-style: italic;
  font-size: 13px;
}

.permissions-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-height: 200px;
  overflow-y: auto;
}

.permission-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 12px;
  background: var(--agent-bg-tertiary);
  border-radius: 6px;
}

.permission-name {
  font-family: monospace;
  font-size: 12px;
  color: var(--agent-text-secondary);
}

.remove-btn {
  width: 20px;
  height: 20px;
  background: transparent;
  border: none;
  color: var(--agent-text-muted);
  font-size: 16px;
  cursor: pointer;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: all 0.2s;
}

.permission-item:hover .remove-btn {
  opacity: 1;
}

.remove-btn:hover {
  background: rgba(239, 68, 68, 0.2);
  color: var(--agent-accent-red);
}

.permissions-info {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--agent-text-muted);
}

.permissions-info code {
  padding: 4px 8px;
  background: var(--agent-bg-tertiary);
  border-radius: 4px;
  font-size: 11px;
}

.permissions-footer {
  padding: 16px 20px;
  border-top: 1px solid var(--agent-border-primary);
  display: flex;
  justify-content: flex-end;
}

.close-modal-btn {
  padding: 8px 20px;
  background: var(--agent-bg-tertiary);
  border: 1px solid var(--agent-border-secondary);
  border-radius: 6px;
  color: var(--agent-text-primary);
  font-size: 14px;
  cursor: pointer;
  transition: all 0.2s;
}

.close-modal-btn:hover {
  background: var(--agent-border-secondary);
}

/* Responsive */
@media (max-width: 640px) {
  .permissions-modal {
    width: 95%;
    max-height: 90vh;
  }

  .permissions-content {
    padding: 16px;
  }
}
`;
