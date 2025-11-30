import { useMemo } from "react";
import { Link } from "react-router-dom";
import { useQuery, type UseQueryResult } from "@tanstack/react-query";

import type { StatusPayload } from "../api/types";
import { getWorkingTreeChanges } from "../api/client";
import { queryKeys } from "../api/queryKeys";
import { useStageStatusQuery } from "../hooks/useStageStatusQuery";
import { useLintersLatestReport } from "../hooks/useLintersLatestReport";
import { useOllamaInsightsQuery } from "../hooks/useOllamaInsightsQuery";
import { useTimelineSummary } from "../hooks/useTimelineSummary";
import { getChangeLabel, getChangeVariant, isNewFileStatus } from "../utils/changeStatus";

const LINTER_STATUS_LABEL: Record<string, string> = {
  pass: "OK",
  warn: "Warnings",
  fail: "Failing",
  skipped: "Skipped",
  error: "Error",
  default: "No data",
};

const LINTER_STATUS_TONE: Record<string, "success" | "warn" | "danger" | "neutral"> = {
  pass: "success",
  warn: "warn",
  fail: "danger",
  error: "danger",
  skipped: "neutral",
  default: "neutral",
};

function formatDateTime(value?: string | null): string {
  if (!value) {
    return "—";
  }
  try {
    return new Date(value).toLocaleString("en-US");
  } catch {
    return value;
  }
}

function formatDuration(ms?: number | null): string {
  if (!ms || ms <= 0) {
    return "—";
  }
  if (ms < 1000) {
    return `${ms.toLocaleString("en-US")} ms`;
  }
  const seconds = ms / 1000;
  if (seconds < 60) {
    return `${seconds.toFixed(seconds >= 10 ? 0 : 1)} s`;
  }
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = Math.round(seconds % 60);
  return `${minutes} min ${remainingSeconds > 0 ? `${remainingSeconds} s` : ""}`.trim();
}

function truncatePath(path: string): string {
  return path;
}

function parseTimestamp(value?: string | null): number | null {
  if (!value) {
    return null;
  }
  const timestamp = new Date(value).getTime();
  return Number.isNaN(timestamp) ? null : timestamp;
}

function formatRelativeTime(timestamp: number): string {
  const now = Date.now();
  const diff = now - timestamp;
  if (diff < 0) {
    return "Upcoming";
  }
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) {
    return "Just now";
  }
  if (minutes < 60) {
    return `${minutes} min ago`;
  }
  const hours = Math.floor(minutes / 60);
  if (hours < 24) {
    return `${hours} hr${hours === 1 ? "" : "s"} ago`;
  }
  const days = Math.floor(hours / 24);
  if (days < 7) {
    return `${days} day${days === 1 ? "" : "s"} ago`;
  }
  return new Date(timestamp).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
  });
}

interface ActivityItem {
  id: string;
  label: string;
  description: string;
  timestamp: number;
  formattedDate: string;
  link?: { label: string; to: string };
}

interface OverviewDashboardProps {
  statusQuery: UseQueryResult<StatusPayload>;
}

export function OverviewDashboard({ statusQuery }: OverviewDashboardProps): JSX.Element {
  const stageStatusQuery = useStageStatusQuery();
  const lintersQuery = useLintersLatestReport();
  const ollamaInsightsQuery = useOllamaInsightsQuery(5);
  const timelineSummaryQuery = useTimelineSummary();
  const changesQuery = useQuery({
    queryKey: queryKeys.changes,
    queryFn: getWorkingTreeChanges,
    refetchInterval: 30000,
  });

  const statusData = statusQuery.data;
  const rootPath = statusData?.absolute_root ?? statusData?.root_path ?? "—";
  const formattedRoot = truncatePath(rootPath);
  const watcherActive = statusData?.watcher_active ?? false;
  const filesIndexed = statusData?.files_indexed ?? 0;
  const lastFullScanLabel = statusData?.last_full_scan
    ? formatDateTime(statusData.last_full_scan)
    : "No scans yet";

  const detection = stageStatusQuery.data?.detection;
  const detectionAvailable = detection?.available ?? false;
  const detectionReasons = detection?.reasons ?? [];
  const stageTone: "success" | "warn" | "neutral" =
    stageStatusQuery.isLoading ? "neutral" : detectionAvailable ? "success" : "warn";
  const stageHeadline = stageStatusQuery.isLoading
    ? "Calculating status…"
    : detectionAvailable
      ? `Stage ${detection?.recommended_stage ?? "?"}`
      : "Unavailable";
  const stageConfidence = detection?.confidence
    ? detection.confidence.toUpperCase()
    : detectionAvailable
      ? "NO CONF."
      : "—";
  const stageSummary = stageStatusQuery.isLoading
    ? "Fetching the current Stage Toolkit status."
    : detectionAvailable
      ? detection?.reasons?.[0] ?? "Toolkit operating without reported issues."
      : detection?.error ?? "Not enough information about the Stage yet.";
  const degradedAnalyzers = statusData?.degraded_capabilities ?? [];
  const analyzersDegraded = statusData?.analyzers_degraded ?? false;

  const highlightCards = [
    {
      key: "root",
      title: "Configured root",
      value: formattedRoot,
      tooltip: rootPath,
    },
    {
      key: "files",
      title: "Indexed files",
      value: filesIndexed.toLocaleString("en-US"),
    },
    {
      key: "scan",
      title: "Last scan",
      value: lastFullScanLabel,
    },
  ];

  const degradedBanner =
    analyzersDegraded && degradedAnalyzers.length > 0
      ? {
          title: "Analyzer support degraded",
          message: `Some languages are partially unsupported: ${degradedAnalyzers.join(", ")}. Install optional dependencies (esprima, tree_sitter_languages, beautifulsoup4) to restore full analysis.`,
        }
      : null;

  const lintersReport = lintersQuery.data ?? null;
  const lintersStatusKey = lintersReport?.report.summary.overall_status ?? "default";
  const lintersTone = LINTER_STATUS_TONE[lintersStatusKey] ?? "neutral";
  const lintersLabel = LINTER_STATUS_LABEL[lintersStatusKey] ?? LINTER_STATUS_LABEL.default;
  const lintersSummary = lintersReport
    ? lintersReport.report.summary
    : null;
  const lintersIssues = lintersSummary?.issues_total ?? 0;
  const lintersCritical = lintersSummary?.critical_issues ?? 0;
  const lintersDuration = lintersSummary?.duration_ms;
  const lintersGeneratedAt = lintersReport?.report.generated_at ?? lintersReport?.generated_at;

  const ollamaInsights = ollamaInsightsQuery.data ?? [];
  const ollamaInsightsEnabled = statusData?.ollama_insights_enabled ?? false;
  const ollamaInsightsError =
    statusData?.ollama_insights_last_error ||
    (ollamaInsightsQuery.error instanceof Error ? ollamaInsightsQuery.error.message : null);
  const latestOllamaInsight = ollamaInsights[0] ?? null;
  const latestInsightModel = statusData?.ollama_insights_last_model ?? latestOllamaInsight?.model;
  const latestInsightMessage =
    statusData?.ollama_insights_last_message ?? latestOllamaInsight?.message ?? null;

  let ollamaInsightsTone: "success" | "warn" | "danger" | "neutral" = "neutral";
  let ollamaInsightsLabel = "No data";
  if (ollamaInsightsQuery.isLoading) {
    ollamaInsightsLabel = "Loading…";
  } else if (ollamaInsightsError) {
    ollamaInsightsTone = "danger";
    ollamaInsightsLabel = "Error";
  } else if (ollamaInsightsEnabled && ollamaInsights.length > 0) {
    ollamaInsightsTone = "success";
    ollamaInsightsLabel = "Insights active";
  } else if (ollamaInsightsEnabled) {
    ollamaInsightsTone = "warn";
    ollamaInsightsLabel = "No messages";
  } else {
    ollamaInsightsTone = "neutral";
    ollamaInsightsLabel = "Disabled";
  }

  let ollamaInsightsSummary =
    "Ollama Insights is disabled. Enable recommendations from Settings.";
  if (ollamaInsightsQuery.isLoading) {
    ollamaInsightsSummary = "Retrieving the latest messages generated by Ollama…";
  } else if (ollamaInsightsError) {
    ollamaInsightsSummary =
      typeof ollamaInsightsError === "string"
        ? `Could not retrieve insights: ${ollamaInsightsError}`
        : `Could not retrieve insights.`;
  } else if (ollamaInsightsEnabled && latestOllamaInsight) {
    const modelLabel = latestInsightModel ? ` by model ${latestInsightModel}` : "";
    ollamaInsightsSummary = `Latest insight on ${formatDateTime(latestOllamaInsight.generated_at)}${modelLabel}.`;
  } else if (ollamaInsightsEnabled && statusData?.ollama_insights_last_message) {
    const modelLabel = latestInsightModel ? ` - ${latestInsightModel}` : "";
    ollamaInsightsSummary = `${statusData.ollama_insights_last_message}${modelLabel}`;
  } else if (ollamaInsightsEnabled) {
    ollamaInsightsSummary =
      "No insights have been generated yet. Run an analysis from the Ollama tab.";
  }

  const ollamaInsightsLastRun = statusData?.ollama_insights_last_run ?? null;
  const ollamaInsightsNextRun = statusData?.ollama_insights_next_run ?? null;

  const pendingChanges = changesQuery.data?.changes ?? [];
  const newFilesCount = pendingChanges.filter((change) => isNewFileStatus(change.status)).length;
  const modifiedCount = Math.max(pendingChanges.length - newFilesCount, 0);
  const changePreview = pendingChanges.slice(0, 3);
  const additionalChanges = Math.max(pendingChanges.length - changePreview.length, 0);
  const changeError =
    changesQuery.error && changesQuery.error instanceof Error
      ? changesQuery.error
      : null;

  const timelineSummary = timelineSummaryQuery.data ?? null;
  const timelineTotalCommits = timelineSummary?.total_commits ?? 0;
  const timelineTotalFiles = timelineSummary?.total_files ?? 0;
  const timelineLatestCommit = timelineSummary?.latest_commit ?? null;
  const timelineActiveFiles = timelineSummary?.active_files_count ?? 0;

  let timelineTone: "success" | "warn" | "neutral" = "neutral";
  let timelineLabel = "No data";
  if (timelineSummaryQuery.isLoading) {
    timelineLabel = "Loading…";
  } else if (timelineSummaryQuery.error) {
    timelineTone = "warn";
    timelineLabel = "Unavailable";
  } else if (timelineTotalCommits > 0) {
    timelineTone = "success";
    timelineLabel = `${timelineTotalCommits.toLocaleString("en-US")} commits`;
  } else {
    timelineTone = "warn";
    timelineLabel = "No commits";
  }

  const timelineSummaryText = timelineSummaryQuery.isLoading
    ? "Loading commit history..."
    : timelineSummaryQuery.error
      ? "Could not load timeline data. Make sure this is a git repository."
      : timelineLatestCommit
        ? `Latest commit by ${timelineLatestCommit.author} on ${formatDateTime(timelineLatestCommit.date)}.`
        : timelineLatestCommit?.message
          ? `${timelineLatestCommit.message.slice(0, 77)}...`
          : "No commit history available yet.";

  const pendingEvents = statusData?.pending_events ?? 0;
  const capabilityIssues =
    statusData?.capabilities?.filter((capability) => !capability.available) ?? [];
  const degradedCapabilitiesText =
    analyzersDegraded && degradedAnalyzers.length > 0
      ? `Degraded: ${degradedAnalyzers.join(", ")}`
      : null;

  const activityTimeline = useMemo<ActivityItem[]>(() => {
    const items: ActivityItem[] = [];
    const stageTimestamp = parseTimestamp(detection?.checked_at);
    if (stageTimestamp) {
      items.push({
        id: "stage-detection",
        label: "Stage detection run",
        description: stageSummary,
        timestamp: stageTimestamp,
        formattedDate: new Date(stageTimestamp).toLocaleString("en-US"),
        link: { label: "Stage Toolkit", to: "/stage-toolkit" },
      });
    }

    const scanTimestamp = parseTimestamp(statusData?.last_full_scan);
    if (scanTimestamp) {
      items.push({
        id: "full-scan",
        label: "Full repository scan",
        description: `Indexed ${filesIndexed.toLocaleString("en-US")} files.`,
        timestamp: scanTimestamp,
        formattedDate: new Date(scanTimestamp).toLocaleString("en-US"),
        link: { label: "Open Code Map", to: "/code-map" },
      });
    }

    const eventsTimestamp = parseTimestamp(statusData?.last_event_batch);
    if (eventsTimestamp) {
      items.push({
        id: "event-batch",
        label: "Event batch processed",
        description:
          pendingEvents > 0
            ? `${pendingEvents.toLocaleString("en-US")} events pending review.`
            : "All events processed.",
        timestamp: eventsTimestamp,
        formattedDate: new Date(eventsTimestamp).toLocaleString("en-US"),
        link: { label: "Review activity", to: "/code-map" },
      });
    }

    const lintersTimestamp = parseTimestamp(lintersGeneratedAt);
    if (lintersTimestamp) {
      items.push({
        id: `linters-${lintersTimestamp}`,
        label: "Linter pipeline run",
        description: `${lintersLabel} - ${lintersIssues.toLocaleString("en-US")} issue${lintersIssues === 1 ? "" : "s"}.`,
        timestamp: lintersTimestamp,
        formattedDate: new Date(lintersTimestamp).toLocaleString("en-US"),
        link: { label: "View linters", to: "/linters" },
      });
    }

    if (latestOllamaInsight) {
      const insightTimestamp = parseTimestamp(latestOllamaInsight.generated_at);
      if (insightTimestamp) {
        const truncatedMessage =
          latestOllamaInsight.message.length > 160
            ? `${latestOllamaInsight.message.slice(0, 157)}...`
            : latestOllamaInsight.message;
        items.push({
          id: `ollama-insight-${latestOllamaInsight.id}`,
          label: `Ollama insight (${latestOllamaInsight.model})`,
          description: truncatedMessage,
          timestamp: insightTimestamp,
          formattedDate: new Date(insightTimestamp).toLocaleString("en-US"),
          link: { label: "Open Ollama", to: "/ollama" },
        });
      }
    } else {
      const lastRunTimestamp = parseTimestamp(ollamaInsightsLastRun);
      if (lastRunTimestamp) {
        items.push({
          id: "ollama-last-run",
          label: "Ollama scheduled run",
          description: "Last schedule completed successfully.",
          timestamp: lastRunTimestamp,
          formattedDate: new Date(lastRunTimestamp).toLocaleString("en-US"),
          link: { label: "Open Ollama", to: "/ollama" },
        });
      }
    }

    const nextRunTimestamp = parseTimestamp(ollamaInsightsNextRun);
    if (nextRunTimestamp && nextRunTimestamp > Date.now()) {
      items.push({
        id: "ollama-next-run",
        label: "Next Ollama run",
        description: `Scheduled for ${new Date(nextRunTimestamp).toLocaleString("en-US")}.`,
        timestamp: nextRunTimestamp,
        formattedDate: new Date(nextRunTimestamp).toLocaleString("en-US"),
        link: { label: "Adjust schedule", to: "/ollama" },
      });
    }

    if (timelineLatestCommit) {
      const commitTimestamp = parseTimestamp(timelineLatestCommit.date);
      if (commitTimestamp) {
        const truncatedMessage =
          timelineLatestCommit.message.length > 80
            ? `${timelineLatestCommit.message.slice(0, 77)}...`
            : timelineLatestCommit.message;
        items.push({
          id: `timeline-commit-${timelineLatestCommit.hash}`,
          label: "Git commit",
          description: `${truncatedMessage} by ${timelineLatestCommit.author}`,
          timestamp: commitTimestamp,
          formattedDate: new Date(commitTimestamp).toLocaleString("en-US"),
          link: { label: "View Timeline", to: "/timeline" },
        });
      }
    }

    return items
      .sort((a, b) => b.timestamp - a.timestamp)
      .slice(0, 6);
  }, [
    detection?.checked_at,
    stageSummary,
    statusData?.last_full_scan,
    filesIndexed,
    statusData?.last_event_batch,
    pendingEvents,
    lintersGeneratedAt,
    lintersLabel,
    lintersIssues,
    latestOllamaInsight,
    ollamaInsightsLastRun,
    ollamaInsightsNextRun,
    timelineLatestCommit,
  ]);

  return (
    <div className="overview-view">
      <section className="overview-intro">
        <div className="overview-intro__text">
          <h2>Workspace overview</h2>
          <p>Review Stage Toolkit, Code Map, and linters at a glance. Dive deeper from here.</p>
          <div className="overview-meta">
            <span className={`overview-meta-pill ${watcherActive ? "success" : "warn"}`}>
              {watcherActive ? "Watcher active" : "Watcher inactive"}
            </span>
          </div>
        </div>

        {degradedBanner ? (
          <div className="overview-alert overview-alert--warn">
            <div>
              <strong>{degradedBanner.title}</strong>
              <p>{degradedBanner.message}</p>
            </div>
            <a
              className="overview-alert__cta"
              href="https://github.com/jesusramos/ATLAS/blob/main/docs/backend_quickstart.md#dependencias-opcionales"
              target="_blank"
              rel="noreferrer"
            >
              Install deps
            </a>
          </div>
        ) : null}

        <div className="overview-detection-card">
          <span className="overview-highlight__title">Detection highlights</span>
          {stageStatusQuery.isLoading ? (
            <p className="overview-highlight__note">Analyzing repository...</p>
          ) : detectionAvailable && detectionReasons.length > 0 ? (
            <ul className="overview-highlight__list">
              {detectionReasons.slice(0, 4).map((reason) => (
                <li key={reason}>{reason}</li>
              ))}
            </ul>
          ) : (
            <p className="overview-highlight__note">
              {detection?.error ?? "Not enough information to report yet."}
            </p>
          )}

          {detection?.metrics ? (
            <div className="overview-highlight__metrics">
              <div>
                <span className="metric-label">Files</span>
                <span className="metric-value">
                  {Number(detection.metrics.file_count ?? 0).toLocaleString("en-US")}
                </span>
              </div>
              <div>
                <span className="metric-label">Approx. LOC</span>
                <span className="metric-value">
                  {Number(detection.metrics.lines_of_code ?? 0).toLocaleString("en-US")}
                </span>
              </div>
              <div>
                <span className="metric-label">Patterns</span>
                <span className="metric-value">
                  {Array.isArray(detection.metrics.patterns_found) &&
                  detection.metrics.patterns_found.length > 0
                    ? detection.metrics.patterns_found.slice(0, 3).join(", ")
                    : "—"}
                </span>
              </div>
            </div>
          ) : null}
        </div>

        <section className="overview-highlight">
          {highlightCards.map((card) => (
            <div key={card.key} className="overview-highlight__card">
              <span className="overview-highlight__title">{card.title}</span>
              <span
                className="overview-highlight__value"
                title={card.tooltip ?? undefined}
              >
                {card.value}
              </span>
            </div>
          ))}
        </section>
      </section>

      <section className="overview-grid">
        {/* placeholder for Stage Toolkit, Code Map, Linters, Timeline grid */}
        <article className="overview-card overview-card--stage">
          <header className="overview-card__header">
            <div>
              <span className={`overview-pill ${stageTone}`}>{stageHeadline}</span>
              <h3>Stage Toolkit</h3>
            </div>
            <Link className="overview-card__cta" to="/stage-toolkit">
              <span>View details -&gt;</span>
            </Link>
          </header>
          <p className="overview-card__summary">{stageSummary}</p>
          <dl className="overview-metrics">
            <div>
              <dt>Confidence</dt>
              <dd>{stageConfidence}</dd>
            </div>
            <div>
              <dt>Last detection</dt>
              <dd>{formatDateTime(detection?.checked_at)}</dd>
            </div>
            <div>
              <dt>Recorded reasons</dt>
              <dd>{detection?.reasons?.length ? detection.reasons.length : 0}</dd>
            </div>
          </dl>
        </article>

        <article className="overview-card overview-card--code">
          <header className="overview-card__header">
            <div>
              <span className="overview-pill neutral">
                {statusQuery.isLoading ? "Loading…" : "Indexing active"}
              </span>
              <h3>Code Map</h3>
            </div>
            <Link className="overview-card__cta" to="/code-map">
              <span>Open Code Map -&gt;</span>
            </Link>
          </header>
          <p className="overview-card__summary">
            {statusQuery.isLoading
              ? "Retrieving analyzer metrics…"
              : `The analyzer has ${statusData?.symbols_indexed?.toLocaleString("en-US") ?? "0"} indexed symbols.`}
          </p>
          <dl className="overview-metrics">
            <div>
              <dt>Indexed files</dt>
              <dd>{statusData?.files_indexed?.toLocaleString("en-US") ?? "—"}</dd>
            </div>
            <div>
              <dt>Last full scan</dt>
              <dd>{formatDateTime(statusData?.last_full_scan)}</dd>
            </div>
            <div>
              <dt>Pending events</dt>
              <dd>{pendingEvents.toLocaleString("en-US")}</dd>
            </div>
          </dl>
          <div className="overview-code-changes">
            <div className="overview-code-changes__header">
              <span
                className={`overview-pill ${changesQuery.isLoading ? "neutral" : pendingChanges.length > 0 ? "warn" : "success"}`}
              >
                {changesQuery.isLoading
                  ? "Checking changes…"
                  : pendingChanges.length > 0
                    ? `${pendingChanges.length} pending ${pendingChanges.length === 1 ? "file" : "files"}`
                    : "Workspace clean"}
              </span>
              {!changesQuery.isLoading && !changeError && pendingChanges.length > 0 && (
                <span className="overview-code-changes__meta">
              {newFilesCount} new - {modifiedCount} modified
                </span>
              )}
            </div>
            {changeError ? (
              <p className="overview-code-changes__hint">
                Could not read git status: {changeError.message}
              </p>
            ) : changesQuery.isLoading ? (
            <p className="overview-code-changes__hint">Gathering recent file changes...</p>
            ) : pendingChanges.length === 0 ? (
              <p className="overview-code-changes__hint">All tracked files match HEAD.</p>
            ) : (
              <>
                <ul className="overview-code-changes__list">
                  {changePreview.map((change) => (
                    <li key={change.path}>
                      <span className={`change-pill change-pill--${getChangeVariant(change.status)}`}>
                        {getChangeLabel(change.status)}
                      </span>
                      <span className="overview-code-changes__path">{change.path}</span>
                    </li>
                  ))}
                </ul>
                {additionalChanges > 0 && (
                  <p className="overview-code-changes__hint">
                    +{additionalChanges} more files pending review in Code Map.
                  </p>
                )}
              </>
            )}
          </div>
        </article>

        <article className="overview-card overview-card--linters">
          <header className="overview-card__header">
            <div>
              <span className={`overview-pill ${lintersTone}`}>{lintersLabel}</span>
              <h3>Linters</h3>
            </div>
            <Link className="overview-card__cta" to="/linters">
              <span>View linters -&gt;</span>
            </Link>
          </header>
          <p className="overview-card__summary">
            {lintersQuery.isLoading
              ? "Fetching the latest linter pipeline…"
              : lintersReport
                ? `Latest pipeline generated on ${formatDateTime(lintersGeneratedAt)}.`
                : "No linter reports available yet."}
          </p>
          <dl className="overview-metrics">
            <div>
              <dt>Total checks</dt>
              <dd>{lintersSummary?.total_checks?.toLocaleString("en-US") ?? "—"}</dd>
            </div>
            <div>
              <dt>Issues</dt>
              <dd>{lintersIssues.toLocaleString("en-US")}</dd>
            </div>
            <div>
              <dt>Critical</dt>
              <dd>{lintersCritical.toLocaleString("en-US")}</dd>
            </div>
            <div>
              <dt>Duration</dt>
              <dd>{formatDuration(lintersDuration)}</dd>
            </div>
          </dl>
        </article>

        <article className="overview-card overview-card--timeline">
          <header className="overview-card__header">
            <div>
              <span className={`overview-pill ${timelineTone}`}>{timelineLabel}</span>
              <h3>Code Timeline</h3>
            </div>
            <Link className="overview-card__cta" to="/timeline">
              <span>Open Timeline -&gt;</span>
            </Link>
          </header>
          <p className="overview-card__summary">{timelineSummaryText}</p>
          {timelineLatestCommit ? (
            <div style={{
              padding: "0.75rem",
              background: "rgba(12, 14, 21, 0.6)",
              borderRadius: "4px",
              marginBottom: "1rem",
              border: "1px solid rgba(59, 130, 246, 0.1)"
            }}>
              <p style={{
                fontSize: "0.85rem",
                color: "#f6f7fb",
                marginBottom: "0.25rem",
                lineHeight: "1.4"
              }}>
                {timelineLatestCommit.message}
              </p>
              <span style={{ fontSize: "0.75rem", color: "#7c849a" }}>
              {timelineLatestCommit.hash.substring(0, 7)} - {timelineLatestCommit.author}
              </span>
            </div>
          ) : null}
          <dl className="overview-metrics">
            <div>
              <dt>Total commits</dt>
              <dd>{timelineTotalCommits.toLocaleString("en-US")}</dd>
            </div>
            <div>
              <dt>Files tracked</dt>
              <dd>{timelineTotalFiles.toLocaleString("en-US")}</dd>
            </div>
            <div>
              <dt>Active files</dt>
              <dd>{timelineActiveFiles.toLocaleString("en-US")}</dd>
            </div>
            <div>
              <dt>Latest commit</dt>
              <dd>{formatDateTime(timelineLatestCommit?.date)}</dd>
            </div>
          </dl>
        </article>
      </section>

      {/* Ollama Insights - Full Width Section */}
      <section className="overview-grid-full">
        <article className="overview-card overview-card--ollama">
          <header className="overview-card__header">
            <div>
              <span className={`overview-pill ${ollamaInsightsTone}`}>{ollamaInsightsLabel}</span>
              <h3>Ollama Insights</h3>
            </div>
            <Link className="overview-card__cta" to="/ollama">
              <span>Open Ollama -&gt;</span>
            </Link>
          </header>
          <p className="overview-card__summary">{ollamaInsightsSummary}</p>
          {ollamaInsights.length > 0 ? (
            <ul className="ollama-insights-list">
              {ollamaInsights.slice(0, 4).map((insight) => (
                <li key={insight.id} className="ollama-insights-item">
                  <p className="ollama-insights-message">{insight.message}</p>
                  <span className="ollama-insights-meta">
                    {formatDateTime(insight.generated_at)} - {insight.model}
                  </span>
                </li>
              ))}
            </ul>
          ) : null}
          <dl className="overview-metrics">
            <div>
              <dt>Service</dt>
              <dd>{ollamaInsightsEnabled ? "Enabled" : "Disabled"}</dd>
            </div>
            <div>
              <dt>Last run</dt>
              <dd>{formatDateTime(ollamaInsightsLastRun)}</dd>
            </div>
            <div>
              <dt>Next run</dt>
              <dd>{formatDateTime(ollamaInsightsNextRun)}</dd>
            </div>
          </dl>
        </article>
      </section>

      {activityTimeline.length > 0 ? (
        <section className="overview-timeline">
          <div className="overview-section-header">
            <h3>Recent activity</h3>
            <span className="overview-section-subtitle">
              Track the latest runs and updates across the workspace.
            </span>
          </div>
          <ul className="overview-timeline__list">
            {activityTimeline.map((item) => (
              <li key={item.id} className="overview-timeline__item">
                <div className="overview-timeline__meta">
                  <span className="overview-timeline__label">{item.label}</span>
                  <span className="overview-timeline__time">
                    {formatRelativeTime(item.timestamp)}
                  </span>
                </div>
                <p className="overview-timeline__description">{item.description}</p>
                <div className="overview-timeline__footer">
                  <span className="overview-timeline__date">{item.formattedDate}</span>
                  {item.link ? (
                      <Link className="overview-timeline__cta" to={item.link.to}>
                        <span>{item.link.label} -&gt;</span>
                      </Link>
                  ) : null}
                </div>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}
