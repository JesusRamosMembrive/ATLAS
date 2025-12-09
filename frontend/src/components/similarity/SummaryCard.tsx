import type { SimilaritySummary } from "../../api/similarityTypes";
import { CompactCard, type CardTone } from "../dashboard/CompactCard";

interface SummaryCardProps {
  summary: SimilaritySummary | null;
  isLoading?: boolean;
}

function getDuplicationTone(duplication: string): CardTone {
  const pct = parseFloat(duplication);
  if (isNaN(pct)) return "neutral";
  if (pct < 10) return "success";
  if (pct < 25) return "warn";
  return "danger";
}

export function SummaryCard({ summary, isLoading }: SummaryCardProps): JSX.Element {
  if (isLoading) {
    return (
      <CompactCard
        title="Analysis Summary"
        status="neutral"
        statusLabel="Loading..."
        className="similarity-summary-card"
      >
        <div className="similarity-loading">Analyzing codebase...</div>
      </CompactCard>
    );
  }

  if (!summary) {
    return (
      <CompactCard
        title="Analysis Summary"
        status="neutral"
        statusLabel="No data"
        className="similarity-summary-card"
      >
        <div className="similarity-empty">
          Run analysis to see similarity metrics
        </div>
      </CompactCard>
    );
  }

  const tone = getDuplicationTone(summary.estimated_duplication);

  return (
    <CompactCard
      title="Analysis Summary"
      status={tone}
      statusLabel={summary.estimated_duplication}
      className="similarity-summary-card"
      metrics={[
        { label: "Files", value: summary.files_analyzed.toLocaleString() },
        { label: "Lines", value: summary.total_lines.toLocaleString() },
        { label: "Clones", value: summary.clone_pairs_found.toLocaleString() },
        { label: "Time", value: `${(summary.analysis_time_ms / 1000).toFixed(2)}s` },
      ]}
    />
  );
}
