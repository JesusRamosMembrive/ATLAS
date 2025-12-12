import { useEffect, useMemo, useState } from "react";

import type {
  LinterCheckStatus,
  LintersReportListItem,
  LintersReportPayload,
  LinterSeverity,
} from "../api/types";
import { useLintersLatestReport } from "../hooks/useLintersLatestReport";
import { useLintersReports } from "../hooks/useLintersReports";
import { useLintersNotifications } from "../hooks/useLintersNotifications";
import { useMarkNotificationRead } from "../hooks/useMarkNotificationRead";

const STATUS_LABELS: Record<LinterCheckStatus, string> = {
  pass: "OK",
  warn: "Warnings",
  fail: "Fail",
  skipped: "Skipped",
  error: "Error",
};

const STATUS_CLASS: Record<LinterCheckStatus, string> = {
  pass: "linters-status--pass",
  warn: "linters-status--warn",
  fail: "linters-status--fail",
  skipped: "linters-status--skipped",
  error: "linters-status--fail",
};

const SEVERITY_CLASS: Record<LinterSeverity, string> = {
  info: "linters-pill--info",
  low: "linters-pill--info",
  medium: "linters-pill--warn",
  high: "linters-pill--warn",
  critical: "linters-pill--fail",
};

const TOOL_FIX_GUIDE: Array<{ key: string; name: string; command: string; note?: string }> = [
  {
    key: "ruff",
    name: "Ruff",
    command: "ruff check --fix .",
    note: "Applies Ruff's quick fixes for lint violations.",
  },
  {
    key: "black",
    name: "Black",
    command: "black .",
    note: "Formats Python files in place using Black's style.",
  },
];

function formatDate(value?: string | null): string {
  if (!value) {
    return "—";
  }
  try {
    return new Date(value).toLocaleString("en-US");
  } catch {
    return value;
  }
}

function formatDuration(durationMs?: number | null): string {
  if (!durationMs || durationMs <= 0) {
    return "—";
  }
  if (durationMs < 1_000) {
    return `${durationMs} ms`;
  }
  const seconds = durationMs / 1_000;
  return `${seconds.toFixed(seconds >= 10 ? 0 : 1)} s`;
}

function formatLine(line?: number | null): string {
  if (!line || line <= 0) {
    return "";
  }
  return `:${line}`;
}

function formatIssuesSample(sample?: string): string {
  if (!sample) {
    return "—";
  }
  return sample.length > 120 ? `${sample.slice(0, 117)}…` : sample;
}

function filterHistory(
  history: LintersReportListItem[],
  latestId?: number | null
): LintersReportListItem[] {
  if (!latestId) {
    return history;
  }
  return history.filter((item) => item.id !== latestId);
}

function firstIssueSample(report: LintersReportPayload): string | undefined {
  for (const tool of report.tools) {
    if (tool.issues_sample && tool.issues_sample.length > 0) {
      return tool.issues_sample[0]?.message;
    }
  }
  for (const rule of report.custom_rules) {
    if (rule.violations && rule.violations.length > 0) {
      return rule.violations[0]?.message;
    }
  }
  return undefined;
}

export function LintersView(): JSX.Element {
  const latestReportQuery = useLintersLatestReport();
  const historyQuery = useLintersReports(15, 0);
  const notificationsQuery = useLintersNotifications(false, 20);
  const markNotification = useMarkNotificationRead();

  const [selectedToolKey, setSelectedToolKey] = useState<string | null>(null);

  const latestReport = latestReportQuery.data ?? null;
  const historyItems = filterHistory(historyQuery.data ?? [], latestReport?.id);
  const notifications = notificationsQuery.data ?? [];

  const coverage = latestReport?.report.coverage;
  const firstSample = latestReport ? firstIssueSample(latestReport.report) : undefined;

  const statusClass = latestReport
    ? STATUS_CLASS[latestReport.report.summary.overall_status]
    : "linters-status--skipped";

  const statusLabel = latestReport
    ? STATUS_LABELS[latestReport.report.summary.overall_status]
    : "No data";

  const isLoadingAny =
    latestReportQuery.isLoading || historyQuery.isLoading || notificationsQuery.isLoading;

  const hasError = latestReportQuery.isError || historyQuery.isError || notificationsQuery.isError;

  const [isRunning, setIsRunning] = useState(false);

  const refetchAll = async () => {
    setIsRunning(true);
    try {
      const response = await fetch("/api/linters/run", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
      });

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`Failed to run linters: ${errorText}`);
      }

      await Promise.all([
        latestReportQuery.refetch(),
        historyQuery.refetch(),
        notificationsQuery.refetch(),
      ]);
    } catch (error) {
      console.error("Error running linters:", error);
    } finally {
      setIsRunning(false);
    }
  };

  const summaryMetrics = useMemo(() => {
    if (!latestReport) {
      return [];
    }
    const { summary, metrics } = latestReport.report;
    return [
      {
        label: "Total checks",
        value: summary.total_checks,
      },
      {
        label: "Issues",
        value: summary.issues_total,
        highlight: summary.issues_total > 0,
      },
      {
        label: "Critical",
        value: summary.critical_issues,
        highlight: summary.critical_issues > 0,
      },
      {
        label: "Total time",
        value: formatDuration(summary.duration_ms ?? metrics.pipeline_duration_ms),
      },
      {
        label: "Files scanned",
        value: summary.files_scanned ?? metrics.files_scanned ?? "—",
      },
      {
        label: "Lines scanned",
        value: summary.lines_scanned ?? metrics.lines_scanned ?? "—",
      },
    ];
  }, [latestReport]);

  useEffect(() => {
    if (!latestReport) {
      setSelectedToolKey(null);
      return;
    }
    if (selectedToolKey && latestReport.report.tools.some((tool) => tool.key === selectedToolKey)) {
      return;
    }
    const toolWithIssues =
      latestReport.report.tools.find((tool) => tool.issues_found > 0) ??
      latestReport.report.tools[0] ??
      null;
    setSelectedToolKey(toolWithIssues?.key ?? null);
  }, [latestReport, selectedToolKey]);

  const selectedTool =
    latestReport?.report.tools.find((tool) => tool.key === selectedToolKey) ?? null;

  const fixGuideEntries = useMemo(() => {
    const detectedKeys = new Set(
      (latestReport?.report.tools ?? []).map((tool) => tool.key)
    );
    const filtered = TOOL_FIX_GUIDE.filter((entry) => {
      if (detectedKeys.size === 0) {
        return true;
      }
      return detectedKeys.has(entry.key);
    });
    return filtered.length > 0 ? filtered : TOOL_FIX_GUIDE;
  }, [latestReport]);

  return (
    <div className="linters-view">
      <header className="linters-hero">
        <div>
          <h2>Linter status</h2>
          <p>
            Review the latest quality pipeline results, browse the history, and manage tool-generated
            notifications.
          </p>
        </div>
        <div className="linters-hero__actions">
          <button
            type="button"
            className="secondary-btn"
            onClick={refetchAll}
            disabled={isRunning || latestReportQuery.isFetching || historyQuery.isFetching}
            aria-busy={isRunning}
          >
            {isRunning || latestReportQuery.isFetching || historyQuery.isFetching ? (
              <>
                <span className="linters-btn-spinner" aria-hidden="true" />
                {isRunning ? "Running…" : "Refreshing…"}
              </>
            ) : (
              "Run Linters"
            )}
          </button>
        </div>
      </header>

      {hasError ? (
        <section className="linters-error">
          <p>
            Could not retrieve linter reports. Try refreshing the page or checking the backend.
          </p>
        </section>
      ) : null}

      <section className="linters-grid">
        <article className="linters-panel linters-panel--main">
          {latestReport ? (
            <>
              <div className="linters-panel__header">
                <div>
                  <span className={`linters-status-pill ${statusClass}`}>{statusLabel}</span>
                  <h3 className="linters-panel__title">Most recent report</h3>
                </div>
                <span className="linters-panel__timestamp">
                  Generated: {formatDate(latestReport.generated_at)}
                </span>
              </div>

              <div className="linters-metrics">
                {summaryMetrics.map((metric) => (
                  <div
                    key={metric.label}
                    className={`linters-metric${metric.highlight ? " linters-metric--alert" : ""}`}
                  >
                    <span className="linters-metric__label">{metric.label}</span>
                    <span className="linters-metric__value">{metric.value}</span>
                  </div>
                ))}
              </div>

              <div className="linters-subgrid">
                <section>
                  <h4>Tools</h4>
                  <table className="linters-table">
                    <thead>
                      <tr>
                        <th>Tool</th>
                        <th>Status</th>
                        <th>Issues</th>
                        <th>Duration</th>
                        <th>Version</th>
                        <th />
                      </tr>
                    </thead>
                    <tbody>
                      {latestReport.report.tools.map((tool) => (
                        <tr
                          key={tool.key}
                          className={tool.key === selectedToolKey ? "is-selected" : ""}
                        >
                          <td>
                            <span className="linters-table__name">{tool.name}</span>
                            <span className="linters-table__command">{tool.command}</span>
                          </td>
                          <td>
                            <span
                              className={`linters-pill ${STATUS_CLASS[tool.status] ?? ""}`}
                            >
                              {STATUS_LABELS[tool.status]}
                            </span>
                          </td>
                          <td>{tool.issues_found}</td>
                          <td>{formatDuration(tool.duration_ms)}</td>
                          <td>{tool.version ?? "—"}</td>
                          <td>
                            <button
                              type="button"
                              className="linters-link"
                              onClick={() => setSelectedToolKey(tool.key)}
                            >
                              View details
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {selectedTool ? (
                    <section className="linters-tool-details">
                      <div className="linters-tool-details__header">
                        <div>
                          <span className={`linters-pill ${STATUS_CLASS[selectedTool.status]}`}>
                            {STATUS_LABELS[selectedTool.status]}
                          </span>
                          <h4>{selectedTool.name}</h4>
                        </div>
                        <span className="linters-tool-details__meta">
                          {selectedTool.issues_found} issues ·{" "}
                          {formatDuration(selectedTool.duration_ms)}
                        </span>
                      </div>
                      <div className="linters-tool-details__body">
                        {selectedTool.issues_found === 0 ? (
                          <p className="linters-empty">No issues reported.</p>
                        ) : (
                          <ul className="linters-issues">
                            {selectedTool.issues_sample.map((issue, index) => (
                              <li key={`${selectedTool.key}-${index}`}>
                                <div className="linters-issues__header">
                                  <span
                                    className={`linters-pill ${SEVERITY_CLASS[issue.severity]}`}
                                  >
                                    {issue.severity.toUpperCase()}
                                  </span>
                                  <span className="linters-issues__location">
                                    {issue.file ? (
                                      <>
                                        {issue.file}
                                        {formatLine(issue.line)}
                                      </>
                                    ) : null}
                                  </span>
                                </div>
                                <p>{issue.message}</p>
                                {issue.suggestion ? (
                                  <p className="linters-issues__suggestion">
                                    Recommendation: {issue.suggestion}
                                  </p>
                                ) : null}
                              </li>
                            ))}
                          </ul>
                        )}
                        {(selectedTool.stdout_excerpt || selectedTool.stderr_excerpt) && (
                          <div className="linters-logs">
                            {selectedTool.stdout_excerpt ? (
                              <details>
                                <summary>Standard output</summary>
                                <pre>{selectedTool.stdout_excerpt}</pre>
                              </details>
                            ) : null}
                            {selectedTool.stderr_excerpt ? (
                              <details>
                                <summary>Error output</summary>
                                <pre>{selectedTool.stderr_excerpt}</pre>
                              </details>
                            ) : null}
                          </div>
                        )}
                      </div>
                    </section>
                  ) : null}
                </section>

                <section>
                  <h4>Custom rules</h4>
                  {latestReport.report.custom_rules.length === 0 ? (
                    <p className="linters-empty">No custom rules configured.</p>
                  ) : (
                    <ul className="linters-list">
                      {latestReport.report.custom_rules.map((rule) => (
                        <li key={rule.key}>
                          <div className="linters-list__header">
                            <span className="linters-list__name">{rule.name}</span>
                            <span className={`linters-pill ${STATUS_CLASS[rule.status]}`}>
                              {STATUS_LABELS[rule.status]}
                            </span>
                          </div>
                          <p className="linters-list__description">{rule.description}</p>
                          {rule.violations.length > 0 ? (
                            <ul className="linters-violations">
                              {rule.violations.map((violation, index) => (
                                <li key={`${rule.key}-${index}`}>
                                  <span className={`linters-pill ${SEVERITY_CLASS[violation.severity]}`}>
                                    {violation.severity.toUpperCase()}
                                  </span>
                                  <span className="linters-violations__message">
                                    {violation.file ?? "—"}
                                    {formatLine(violation.line)}: {violation.message}
                                  </span>
                                </li>
                              ))}
                            </ul>
                          ) : null}
                        </li>
                      ))}
                    </ul>
                  )}
                </section>
              </div>

              <div className="linters-notes">
                <div>
                  <h4>Notes</h4>
                  {latestReport.report.notes.length > 0 ? (
                    <ul>
                      {latestReport.report.notes.map((note) => (
                        <li key={note}>{note}</li>
                      ))}
                    </ul>
                  ) : (
                    <p className="linters-empty">The pipeline did not produce additional notes.</p>
                  )}
                </div>
                <div>
                  <h4>Coverage</h4>
                  {coverage ? (
                    <dl className="linters-coverage">
                      <div>
                        <dt>Statements</dt>
                        <dd>
                          {coverage.statement_coverage != null
                            ? `${coverage.statement_coverage.toFixed(1)} %`
                            : "—"}
                        </dd>
                      </div>
                      <div>
                        <dt>Branches</dt>
                        <dd>
                          {coverage.branch_coverage != null
                            ? `${coverage.branch_coverage.toFixed(1)} %`
                            : "—"}
                        </dd>
                      </div>
                      <div>
                        <dt>Missing lines</dt>
                        <dd>{coverage.missing_lines ?? "—"}</dd>
                      </div>
                    </dl>
                  ) : (
                    <p className="linters-empty">No coverage data available.</p>
                  )}
                </div>
              </div>

              {firstSample ? (
                <div className="linters-sample">
                  <h4>Highlighted example</h4>
                  <p>{formatIssuesSample(firstSample)}</p>
                </div>
              ) : null}
            </>
          ) : (
            <div className="linters-empty-state">
              {isLoadingAny ? (
                <p>Loading linter report…</p>
              ) : (
                <>
                  <p>No linter reports have been generated yet.</p>
                  <p>
                    Run a full scan or make changes in the project so the pipeline runs automatically.
                  </p>
                </>
              )}
            </div>
          )}
        </article>

        <aside className="linters-aside">
          <section className="linters-panel">
            <div className="linters-panel__header">
              <h3 className="linters-panel__title">Recent history</h3>
              <span className="linters-panel__timestamp">
                {historyQuery.isFetching ? "Refreshing…" : ""}
              </span>
            </div>
            {historyItems.length === 0 ? (
              <p className="linters-empty">No additional history.</p>
            ) : (
              <ul className="linters-history">
                {historyItems.map((item) => (
                  <li key={item.id}>
                    <span className={`linters-pill ${STATUS_CLASS[item.overall_status]}`}>
                      {STATUS_LABELS[item.overall_status]}
                    </span>
                    <div className="linters-history__body">
                      <span className="linters-history__date">
                        {formatDate(item.generated_at)}
                      </span>
                      <span className="linters-history__issues">
                        {item.issues_total} issues · {item.critical_issues} critical
                      </span>
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>

          <section className="linters-panel">
            <div className="linters-panel__header">
              <h3 className="linters-panel__title">Notifications</h3>
              <span className="linters-panel__timestamp">
                {notificationsQuery.isFetching ? "Refreshing…" : ""}
              </span>
            </div>
            {notifications.length === 0 ? (
              <p className="linters-empty">No recent notifications.</p>
            ) : (
              <ul className="linters-notifications">
                {notifications.map((notification) => (
                  <li key={notification.id} className={notification.read ? "is-read" : ""}>
                    <div className="linters-notifications__header">
                      <span
                        className={`linters-pill ${SEVERITY_CLASS[notification.severity]}`}
                      >
                        {notification.severity.toUpperCase()}
                      </span>
                      <span className="linters-notifications__date">
                        {formatDate(notification.created_at)}
                      </span>
                    </div>
                    <h4>{notification.title}</h4>
                    <p>{notification.message}</p>
                    <div className="linters-notifications__actions">
                      {notification.read ? (
                        <button
                          type="button"
                          className="secondary-btn"
                          onClick={() => markNotification.mutate({ id: notification.id, read: false })}
                          disabled={markNotification.isPending}
                        >
                          Mark as unread
                        </button>
                      ) : (
                        <button
                          type="button"
                          className="secondary-btn"
                          onClick={() => markNotification.mutate({ id: notification.id, read: true })}
                          disabled={markNotification.isPending}
                        >
                          Mark as read
                        </button>
                      )}
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </aside>
      </section>

      {fixGuideEntries.length > 0 ? (
        <section className="linters-panel linters-fix-guide">
          <div>
            <h3 className="linters-panel__title">Auto-fix commands</h3>
            <p className="linters-fix-guide__description">
              Use these commands to apply automated fixes for the most common tools. Tools not listed
              here require manual changes.
            </p>
          </div>
          <ul className="linters-fix-guide__list">
            {fixGuideEntries.map((entry) => (
              <li key={entry.key} className="linters-fix-guide__item">
                <span className="linters-fix-guide__name">{entry.name}</span>
                <code>{entry.command}</code>
                {entry.note ? <span className="linters-fix-guide__note">{entry.note}</span> : null}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}
