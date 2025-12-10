import type { SimilarityPerformance, SimilarityTiming } from "../../api/similarityTypes";
import { CompactCard, type CardTone } from "../dashboard/CompactCard";

interface PerformanceCardProps {
  performance: SimilarityPerformance | null;
  timing: SimilarityTiming | null;
  isLoading?: boolean;
}

function getPerformanceTone(locPerSecond: number): CardTone {
  if (locPerSecond >= 10000) return "success";
  if (locPerSecond >= 5000) return "warn";
  return "danger";
}

function formatNumber(n: number): string {
  if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`;
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`;
  return n.toFixed(0);
}

export function PerformanceCard({
  performance,
  timing,
  isLoading,
}: PerformanceCardProps): JSX.Element {
  if (isLoading) {
    return (
      <CompactCard
        title="Performance"
        status="neutral"
        statusLabel="..."
        className="similarity-performance-card"
      >
        <div className="similarity-loading">Measuring...</div>
      </CompactCard>
    );
  }

  if (!performance || !timing) {
    return (
      <CompactCard
        title="Performance"
        status="neutral"
        statusLabel="No data"
        className="similarity-performance-card"
      />
    );
  }

  const tone = getPerformanceTone(performance.loc_per_second);
  const parallelLabel = performance.parallel_enabled
    ? `${performance.thread_count} threads`
    : "Sequential";

  return (
    <CompactCard
      title="Performance"
      status={tone}
      statusLabel={`${formatNumber(performance.loc_per_second)} LOC/s`}
      className="similarity-performance-card"
      metrics={[
        { label: "Tokens/s", value: formatNumber(performance.tokens_per_second) },
        { label: "Processing", value: parallelLabel },
        { label: "Tokenize", value: `${timing.tokenize_ms}ms` },
        { label: "Match", value: `${timing.match_ms}ms` },
      ]}
    />
  );
}
