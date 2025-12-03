import type { AnalyzerCapability } from "../../api/types";

interface AnalyzerHealthProps {
  capabilities: AnalyzerCapability[];
}

const ANALYZER_LABELS: Record<string, string> = {
  python: "Py",
  typescript: "TS",
  javascript: "JS",
  html: "HTML",
  tsx: "TSX",
  jsx: "JSX",
};

function getAnalyzerLabel(key: string): string {
  return ANALYZER_LABELS[key.toLowerCase()] ?? key.slice(0, 4).toUpperCase();
}

export function AnalyzerHealth({
  capabilities,
}: AnalyzerHealthProps): JSX.Element {
  if (capabilities.length === 0) {
    return <div className="analyzer-health" />;
  }

  return (
    <div className="analyzer-health">
      {capabilities.map((cap) => {
        const hasDegraded = cap.degraded_extensions.length > 0;
        const status = cap.available
          ? hasDegraded
            ? "warn"
            : "success"
          : "danger";

        const tooltip = cap.available
          ? hasDegraded
            ? `${cap.description} (partial: ${cap.degraded_extensions.join(", ")})`
            : cap.description
          : cap.error ?? `${cap.description} unavailable`;

        return (
          <span
            key={cap.key}
            className={`analyzer-health__pill analyzer-health__pill--${status}`}
            title={tooltip}
          >
            {getAnalyzerLabel(cap.key)}
          </span>
        );
      })}
    </div>
  );
}
