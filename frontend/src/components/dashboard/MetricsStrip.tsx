interface MetricsStripProps {
  filesIndexed: number;
  symbolsIndexed: number;
  pendingEvents: number;
  lastScan: string | null;
  linesOfCode?: number | null;
}

function formatNumber(value: number): string {
  if (value >= 1000000) {
    return `${(value / 1000000).toFixed(1)}M`;
  }
  if (value >= 1000) {
    return `${(value / 1000).toFixed(1)}k`;
  }
  return value.toLocaleString("en-US");
}

function formatRelativeTime(dateString: string | null): string {
  if (!dateString) return "Never";
  const timestamp = new Date(dateString).getTime();
  if (Number.isNaN(timestamp)) return "—";

  const now = Date.now();
  const diff = now - timestamp;
  const minutes = Math.floor(diff / 60000);

  if (minutes < 1) return "Just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

export function MetricsStrip({
  filesIndexed,
  symbolsIndexed,
  pendingEvents,
  lastScan,
  linesOfCode,
}: MetricsStripProps): JSX.Element {
  return (
    <div className="metrics-strip">
      <div className="metrics-strip__item">
        <span className="metrics-strip__label">Files</span>
        <span className="metrics-strip__value">{formatNumber(filesIndexed)}</span>
      </div>
      <div className="metrics-strip__item">
        <span className="metrics-strip__label">Symbols</span>
        <span className="metrics-strip__value">{formatNumber(symbolsIndexed)}</span>
      </div>
      {linesOfCode != null && linesOfCode > 0 ? (
        <div className="metrics-strip__item">
          <span className="metrics-strip__label">LOC</span>
          <span className="metrics-strip__value">{formatNumber(linesOfCode)}</span>
        </div>
      ) : null}
      <div className="metrics-strip__item">
        <span className="metrics-strip__label">Pending</span>
        <span className={`metrics-strip__value ${pendingEvents > 0 ? "metrics-strip__value--warn" : ""}`}>
          {pendingEvents}
        </span>
      </div>
      <div className="metrics-strip__item">
        <span className="metrics-strip__label">Last scan</span>
        <span className="metrics-strip__value">{formatRelativeTime(lastScan)}</span>
      </div>
    </div>
  );
}
