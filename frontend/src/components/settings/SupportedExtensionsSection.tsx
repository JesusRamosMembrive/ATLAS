import type { AnalyzerCapability } from "../../api/types";

interface SupportedExtensionsSectionProps {
  capabilities: AnalyzerCapability[];
  isLoading: boolean;
}

export function SupportedExtensionsSection({
  capabilities,
  isLoading,
}: SupportedExtensionsSectionProps): JSX.Element {
  if (isLoading) {
    return (
      <section className="settings-card">
        <h2>Supported Extensions</h2>
        <p>Languages and file types the analyzer can process.</p>
        <div className="settings-status-body">
          <span
            className="settings-status-dot settings-status-dot--loading"
            aria-hidden="true"
          />
          <span className="settings-status-text settings-status-text--muted">
            Loading capabilities...
          </span>
        </div>
      </section>
    );
  }

  const available = capabilities.filter((cap) => cap.available);
  const degraded = capabilities.filter((cap) => !cap.available);

  return (
    <section className="settings-card supported-extensions-card">
      <h2>Supported Extensions</h2>
      <p>Languages and file types the analyzer can process.</p>

      {available.length > 0 && (
        <div className="extensions-group">
          <div className="extensions-group-header">
            <span className="extensions-group-icon extensions-group-icon--active" aria-hidden="true">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <polyline points="20 6 9 17 4 12" />
              </svg>
            </span>
            <strong>Active analyzers</strong>
          </div>
          {available.map((cap) => (
            <div key={cap.key} className="extension-item">
              <div className="extension-item-header">
                <span className="extension-item-name">{cap.description}</span>
                {cap.dependency && (
                  <span className="extension-item-dep" title={`Dependency: ${cap.dependency}`}>
                    via {cap.dependency}
                  </span>
                )}
              </div>
              <div className="settings-tags">
                {cap.extensions.map((ext) => (
                  <span key={ext} className="settings-tag settings-tag--extension">
                    {ext}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {degraded.length > 0 && (
        <div className="extensions-group">
          <div className="extensions-group-header">
            <span className="extensions-group-icon extensions-group-icon--degraded" aria-hidden="true">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
                <line x1="12" y1="9" x2="12" y2="13" />
                <line x1="12" y1="17" x2="12.01" y2="17" />
              </svg>
            </span>
            <strong>Degraded analyzers</strong>
            <span className="extensions-group-hint">(install dependencies to enable)</span>
          </div>
          {degraded.map((cap) => (
            <div key={cap.key} className="extension-item extension-item--degraded">
              <div className="extension-item-header">
                <span className="extension-item-name">{cap.description}</span>
                {cap.dependency && (
                  <code className="extension-item-install">pip install {cap.dependency}</code>
                )}
              </div>
              {cap.error && (
                <p className="extension-item-error">{cap.error}</p>
              )}
              <div className="settings-tags">
                {cap.degraded_extensions.map((ext) => (
                  <span key={ext} className="settings-tag settings-tag--locked">
                    {ext}
                  </span>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      {capabilities.length === 0 && (
        <p className="settings-helper">No analyzer capabilities reported by the backend.</p>
      )}

      <p className="settings-helper">
        The analyzer automatically detects file types and applies the appropriate parser.
        Files with unsupported extensions are tracked but not parsed for symbols.
      </p>
    </section>
  );
}
