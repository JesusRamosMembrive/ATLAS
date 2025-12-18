import type { UseQueryResult } from "@tanstack/react-query";

import type { AnalyzerCapability, StatusPayload } from "../api/types";

function formatRelative(timestamp: string | null | undefined): string {
  if (!timestamp) {
    return "—";
  }
  const date = new Date(timestamp);
  if (Number.isNaN(date.getTime())) {
    return "—";
  }
  return date.toLocaleString();
}

export function StatusPanel({
  statusQuery,
  showAnalyzers = false,
}: {
  statusQuery: UseQueryResult<StatusPayload>;
  showAnalyzers?: boolean;
}): JSX.Element {
  const status = statusQuery.data;

  if (statusQuery.isLoading) {
    return (
      <div>
        <h2>Status</h2>
        <p style={{ color: "#7f869d", fontSize: "13px" }}>Loading status…</p>
      </div>
    );
  }

  if (statusQuery.isError || !status) {
    return (
      <div>
        <h2>Status</h2>
        <div className="error-banner">
          Could not retrieve the current backend status.
        </div>
      </div>
    );
  }

  return (
    <div className="status-panel">
      <h2>Status</h2>
      <dl className="status-grid">
        <div>
          <dt>Watcher</dt>
          <dd>{status.watcher_active ? "Active" : "Inactive"}</dd>
        </div>
        <div>
          <dt>Docstrings</dt>
          <dd>{status.include_docstrings ? "Included" : "Hidden"}</dd>
        </div>
        <div>
          <dt>Files</dt>
          <dd>{status.files_indexed}</dd>
        </div>
        <div>
          <dt>Symbols</dt>
          <dd>{status.symbols_indexed}</dd>
        </div>
        <div>
          <dt>Last scan</dt>
          <dd>{formatRelative(status.last_full_scan)}</dd>
        </div>
        <div>
          <dt>Last event</dt>
          <dd>{formatRelative(status.last_event_batch)}</dd>
        </div>
        <div>
          <dt>Pending</dt>
          <dd>{status.pending_events}</dd>
        </div>
      </dl>

      {showAnalyzers && <CapabilitySummary capabilities={status.capabilities} />}
    </div>
  );
}

export function AnalyzersPanel({
  statusQuery,
}: {
  statusQuery: UseQueryResult<StatusPayload>;
}): JSX.Element {
  const status = statusQuery.data;

  if (statusQuery.isLoading) {
    return (
      <div className="capability-summary">
        <h2>Analyzers</h2>
        <p style={{ color: "#7f869d", fontSize: "13px" }}>Loading…</p>
      </div>
    );
  }

  if (statusQuery.isError || !status) {
    return (
      <div className="capability-summary">
        <h2>Analyzers</h2>
        <p style={{ color: "#7f869d", fontSize: "13px" }}>Unable to load</p>
      </div>
    );
  }

  return <CapabilitySummary capabilities={status.capabilities} />;
}

function CapabilitySummary({ capabilities }: { capabilities: AnalyzerCapability[] }): JSX.Element {
  if (!capabilities || capabilities.length === 0) {
    return (
      <div className="capability-summary">
        <p className="capability-helper">No information about optional dependencies.</p>
      </div>
    );
  }

  return (
    <div className="capability-summary">
      <h3>Analyzers</h3>
      <ul>
        {capabilities.map((cap) => {
          const downgraded = !cap.available;
          const badge = downgraded ? "Degraded" : "Active";
          return (
            <li key={cap.key}>
              <div>
                <strong>{cap.description}</strong>
                <span>{cap.extensions.join(", ")}</span>
              </div>
              <span className={`capability-badge ${downgraded ? "capability-badge--warn" : ""}`}>
                {badge}
              </span>
              {downgraded && (
                <p className="capability-warning">
                  {cap.dependency ? `Install ${cap.dependency}` : "Missing dependency"}
                  {cap.error ? ` · ${cap.error}` : ""}
                </p>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
