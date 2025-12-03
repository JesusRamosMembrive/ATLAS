import { useMemo } from "react";
import { Link } from "react-router-dom";
import { useQuery, type UseQueryResult } from "@tanstack/react-query";

import type { StatusPayload } from "../api/types";
import { getWorkingTreeChanges } from "../api/client";
import { queryKeys } from "../api/queryKeys";
import { useStageStatusQuery } from "../hooks/useStageStatusQuery";
import { useLintersLatestReport } from "../hooks/useLintersLatestReport";
import { useOllamaInsightsQuery } from "../hooks/useOllamaInsightsQuery";
import { useOllamaStatusQuery } from "../hooks/useOllamaStatusQuery";
import { useTimelineSummary } from "../hooks/useTimelineSummary";
import { useRecentCommits } from "../hooks/useRecentCommits";

import {
  CommandStatusBar,
  MetricsStrip,
  QuickActions,
  CompactCard,
  ActivityTimeline,
  IssueSeverityBar,
  CoverageGauge,
  TopOffenders,
  PendingChangesList,
  RecentCommits,
  AnalyzerHealth,
  type ActivityItem,
  type CardTone,
} from "./dashboard";

const LINTER_STATUS_LABEL: Record<string, string> = {
  pass: "OK",
  warn: "Warnings",
  fail: "Failing",
  skipped: "Skipped",
  error: "Error",
  default: "No data",
};

const LINTER_STATUS_TONE: Record<string, CardTone> = {
  pass: "success",
  warn: "warn",
  fail: "danger",
  error: "danger",
  skipped: "neutral",
  default: "neutral",
};

function formatDateTime(value?: string | null): string {
  if (!value) return "—";
  try {
    return new Date(value).toLocaleString("en-US");
  } catch {
    return value;
  }
}

function formatRelativeTime(timestamp: number): string {
  const now = Date.now();
  const diff = now - timestamp;
  if (diff < 0) return "Upcoming";
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return "Just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function formatNumber(value: number): string {
  if (value >= 1000000) return `${(value / 1000000).toFixed(1)}M`;
  if (value >= 1000) return `${(value / 1000).toFixed(1)}k`;
  return value.toLocaleString("en-US");
}

function parseTimestamp(value?: string | null): number | null {
  if (!value) return null;
  const timestamp = new Date(value).getTime();
  return Number.isNaN(timestamp) ? null : timestamp;
}

interface OverviewDashboardProps {
  statusQuery: UseQueryResult<StatusPayload>;
}

export function OverviewDashboard({ statusQuery }: OverviewDashboardProps): JSX.Element {
  // Data queries
  const stageStatusQuery = useStageStatusQuery();
  const lintersQuery = useLintersLatestReport();
  const ollamaInsightsQuery = useOllamaInsightsQuery(5);
  const ollamaStatusQuery = useOllamaStatusQuery();
  const timelineSummaryQuery = useTimelineSummary();
  const recentCommitsQuery = useRecentCommits(5);
  const changesQuery = useQuery({
    queryKey: queryKeys.changes,
    queryFn: getWorkingTreeChanges,
    refetchInterval: 30000,
  });

  // Extract data
  const statusData = statusQuery.data;
  const rootPath = statusData?.absolute_root ?? statusData?.root_path ?? "—";
  const watcherActive = statusData?.watcher_active ?? false;
  const filesIndexed = statusData?.files_indexed ?? 0;
  const symbolsIndexed = statusData?.symbols_indexed ?? 0;
  const pendingEvents = statusData?.pending_events ?? 0;
  const lastFullScan = statusData?.last_full_scan ?? null;

  // Stage detection
  const detection = stageStatusQuery.data?.detection;
  const claudeStatus = stageStatusQuery.data?.claude;
  const codexStatus = stageStatusQuery.data?.codex;
  const geminiStatus = stageStatusQuery.data?.gemini;

  // Linters
  const lintersReport = lintersQuery.data ?? null;
  const lintersStatusKey = lintersReport?.report.summary.overall_status ?? "default";
  const lintersTone = LINTER_STATUS_TONE[lintersStatusKey] ?? "neutral";
  const lintersLabel = LINTER_STATUS_LABEL[lintersStatusKey] ?? "No data";
  const lintersSummary = lintersReport?.report.summary;
  const lintersIssues = lintersSummary?.issues_total ?? 0;
  const lintersCritical = lintersSummary?.critical_issues ?? 0;
  const lintersChartData = lintersReport?.report.chart_data;
  const lintersCoverage = lintersReport?.report.coverage;
  const topOffenders = lintersChartData?.top_offenders ?? [];
  const issuesBySeverity = lintersChartData?.issues_by_severity ?? {};

  // Analyzer capabilities
  const capabilities = statusData?.capabilities ?? [];

  // Recent commits
  const recentCommits = recentCommitsQuery.data ?? [];

  // Ollama
  const ollamaStatus = ollamaStatusQuery.data?.status;
  const ollamaInsights = ollamaInsightsQuery.data ?? [];
  const latestInsight = ollamaInsights[0] ?? null;

  // Timeline
  const timelineSummary = timelineSummaryQuery.data ?? null;
  const timelineLatestCommit = timelineSummary?.latest_commit ?? null;

  // Pending changes
  const pendingChanges = changesQuery.data?.changes ?? [];

  // LOC from detection metrics
  const linesOfCode = detection?.metrics?.lines_of_code as number | undefined;

  // Build activity timeline items
  const activityItems = useMemo<ActivityItem[]>(() => {
    const items: ActivityItem[] = [];

    const stageTimestamp = parseTimestamp(detection?.checked_at);
    if (stageTimestamp) {
      items.push({
        id: "stage",
        label: "Stage detected",
        description: detection?.reasons?.[0] ?? `Stage ${detection?.recommended_stage ?? "?"}`,
        timestamp: stageTimestamp,
        link: { to: "/stage-toolkit", label: "Details" },
        tone: detection?.available ? "success" : "warn",
      });
    }

    const lintersTimestamp = parseTimestamp(lintersReport?.generated_at);
    if (lintersTimestamp) {
      items.push({
        id: "linters",
        label: "Linters",
        description: `${lintersLabel} - ${lintersIssues} issues`,
        timestamp: lintersTimestamp,
        link: { to: "/linters", label: "Report" },
        tone: lintersTone,
      });
    }

    const scanTimestamp = parseTimestamp(lastFullScan);
    if (scanTimestamp) {
      items.push({
        id: "scan",
        label: "Full scan",
        description: `${formatNumber(filesIndexed)} files indexed`,
        timestamp: scanTimestamp,
        link: { to: "/code-map", label: "Map" },
        tone: "success",
      });
    }

    if (latestInsight) {
      const insightTimestamp = parseTimestamp(latestInsight.generated_at);
      if (insightTimestamp) {
        items.push({
          id: `insight-${latestInsight.id}`,
          label: latestInsight.model,
          description: latestInsight.message.slice(0, 100),
          timestamp: insightTimestamp,
          link: { to: "/ollama", label: "Insights" },
          tone: "neutral",
        });
      }
    }

    if (timelineLatestCommit) {
      const commitTimestamp = parseTimestamp(timelineLatestCommit.date);
      if (commitTimestamp) {
        items.push({
          id: `commit-${timelineLatestCommit.hash}`,
          label: "Commit",
          description: timelineLatestCommit.message.slice(0, 60),
          timestamp: commitTimestamp,
          link: { to: "/timeline", label: "Timeline" },
        });
      }
    }

    return items.sort((a, b) => b.timestamp - a.timestamp);
  }, [
    detection,
    lintersReport,
    lintersLabel,
    lintersIssues,
    lintersTone,
    lastFullScan,
    filesIndexed,
    latestInsight,
    timelineLatestCommit,
  ]);

  // Agent status helpers
  const agentStatusText = (installed: boolean | undefined): string =>
    installed ? "OK" : "Missing";
  const agentTone = (installed: boolean | undefined): CardTone =>
    installed ? "success" : "warn";

  return (
    <div className="overview-view overview-view--dense">
      {/* Status Bar */}
      <CommandStatusBar
        backendOnline={statusQuery.isSuccess}
        backendLoading={statusQuery.isLoading}
        ollamaStatus={ollamaStatus}
        watcherActive={watcherActive}
        stageDetection={detection}
        rootPath={rootPath}
        capabilities={capabilities}
      />

      {/* Top Row: Metrics + Quick Actions */}
      <div className="command-grid command-grid--top">
        <MetricsStrip
          filesIndexed={filesIndexed}
          symbolsIndexed={symbolsIndexed}
          pendingEvents={pendingEvents}
          lastScan={lastFullScan}
          linesOfCode={linesOfCode}
        />
        <QuickActions
          ollamaRunning={ollamaStatus?.running}
          ollamaModel={ollamaStatus?.models?.[0]?.name}
          disabled={statusQuery.isLoading}
        />
      </div>

      {/* Main Cards Grid */}
      <div className="command-grid command-grid--cards">
        {/* Linters Card - Enhanced */}
        <CompactCard
          title="Linters"
          status={lintersTone}
          statusLabel={lintersLabel}
          link={{ to: "/linters", label: "View" }}
          metrics={[
            { label: "Issues", value: lintersIssues },
            { label: "Critical", value: lintersCritical },
            { label: "Checks", value: lintersSummary?.total_checks ?? 0 },
          ]}
        >
          {Object.keys(issuesBySeverity).length > 0 && (
            <IssueSeverityBar issuesBySeverity={issuesBySeverity} />
          )}
          {lintersCoverage && (
            <CoverageGauge
              statementCoverage={lintersCoverage.statement_coverage}
              branchCoverage={lintersCoverage.branch_coverage}
              size={48}
            />
          )}
        </CompactCard>

        {/* Code Map Card */}
        <CompactCard
          title="Code Map"
          status={pendingEvents > 0 ? "warn" : "success"}
          statusLabel={pendingEvents > 0 ? `${pendingEvents} pending` : "Synced"}
          link={{ to: "/code-map", label: "Open" }}
          metrics={[
            { label: "Files", value: formatNumber(filesIndexed) },
            { label: "Symbols", value: formatNumber(symbolsIndexed) },
            { label: "Changes", value: pendingChanges.length },
          ]}
        />

        {/* Agents Card */}
        <CompactCard
          title="Agents"
          status={
            claudeStatus?.installed && codexStatus?.installed && geminiStatus?.installed
              ? "success"
              : claudeStatus?.installed || codexStatus?.installed || geminiStatus?.installed
                ? "warn"
                : "danger"
          }
          statusLabel={
            claudeStatus?.installed && codexStatus?.installed && geminiStatus?.installed
              ? "All OK"
              : "Partial"
          }
          link={{ to: "/stage-toolkit", label: "Setup" }}
        >
          <div style={{ display: "flex", gap: "12px", fontSize: "0.75rem" }}>
            <span style={{ color: claudeStatus?.installed ? "#4ade80" : "#94a3b8" }}>
              Claude: {agentStatusText(claudeStatus?.installed)}
            </span>
            <span style={{ color: codexStatus?.installed ? "#4ade80" : "#94a3b8" }}>
              Codex: {agentStatusText(codexStatus?.installed)}
            </span>
            <span style={{ color: geminiStatus?.installed ? "#4ade80" : "#94a3b8" }}>
              Gemini: {agentStatusText(geminiStatus?.installed)}
            </span>
          </div>
        </CompactCard>

        {/* Ollama Card */}
        <CompactCard
          title="Ollama"
          status={ollamaStatus?.running ? "success" : ollamaStatus?.installed ? "warn" : "neutral"}
          statusLabel={ollamaStatus?.running ? "Running" : ollamaStatus?.installed ? "Stopped" : "Not found"}
          link={{ to: "/ollama", label: "Open" }}
          metrics={[
            { label: "Models", value: ollamaStatus?.models?.length ?? 0 },
            { label: "Insights", value: ollamaInsights.length },
          ]}
        >
          {latestInsight ? (
            <p style={{ margin: 0, fontSize: "0.75rem", color: "#94a3b8" }}>
              Last: {latestInsight.message.slice(0, 50)}...
            </p>
          ) : null}
        </CompactCard>
      </div>

      {/* Info Row: Top Offenders, Pending Changes, Recent Commits */}
      <div className="info-row">
        <TopOffenders files={topOffenders} maxItems={5} />
        <PendingChangesList changes={pendingChanges} maxItems={5} />
        <RecentCommits
          commits={recentCommits}
          maxItems={5}
          isLoading={recentCommitsQuery.isLoading}
        />
      </div>

      {/* Activity Timeline */}
      <div style={{ marginTop: "4px" }}>
        <div style={{ marginBottom: "8px", display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <span style={{ fontSize: "0.75rem", textTransform: "uppercase", letterSpacing: "0.08em", color: "#94a3b8" }}>
            Recent Activity
          </span>
          <Link to="/code-map" style={{ fontSize: "0.7rem", color: "#93c5fd", textDecoration: "none" }}>
            See all
          </Link>
        </div>
        <ActivityTimeline items={activityItems} maxVisible={6} />
      </div>

      {/* Stage Info (collapsed) */}
      {detection?.available ? (
        <div className="compact-card" style={{ marginTop: "4px" }}>
          <div className="compact-card__header">
            <div className="compact-card__title-row">
              <span className={`command-pill command-pill--success`}>
                Stage {detection.recommended_stage}
              </span>
              <h4 className="compact-card__title">Detection Summary</h4>
            </div>
            <Link className="compact-card__link" to="/stage-toolkit">Details</Link>
          </div>
          {detection.reasons && detection.reasons.length > 0 ? (
            <ul style={{ margin: 0, paddingLeft: "18px", fontSize: "0.8rem", color: "#cbd5f5" }}>
              {detection.reasons.slice(0, 3).map((reason, i) => (
                <li key={i}>{reason}</li>
              ))}
            </ul>
          ) : null}
          <div className="compact-card__metrics">
            <div className="compact-metric">
              <span className="compact-metric__label">Confidence</span>
              <span className="compact-metric__value">{detection.confidence?.toUpperCase() ?? "—"}</span>
            </div>
            <div className="compact-metric">
              <span className="compact-metric__label">Files</span>
              <span className="compact-metric__value">
                {formatNumber(Number(detection.metrics?.file_count ?? 0))}
              </span>
            </div>
            <div className="compact-metric">
              <span className="compact-metric__label">LOC</span>
              <span className="compact-metric__value">
                {formatNumber(Number(detection.metrics?.lines_of_code ?? 0))}
              </span>
            </div>
            <div className="compact-metric">
              <span className="compact-metric__label">Patterns</span>
              <span className="compact-metric__value">
                {Array.isArray(detection.metrics?.patterns_found)
                  ? detection.metrics.patterns_found.length
                  : 0}
              </span>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
