import type { LinterSeverity } from "../../api/types";

interface IssueSeverityBarProps {
  issuesBySeverity: Record<LinterSeverity | string, number>;
  maxWidth?: number;
}

const SEVERITY_ORDER: LinterSeverity[] = ["critical", "high", "medium", "low", "info"];

const SEVERITY_COLORS: Record<LinterSeverity, string> = {
  critical: "#ef4444",
  high: "#f97316",
  medium: "#eab308",
  low: "#3b82f6",
  info: "#6b7280",
};

const SEVERITY_LABELS: Record<LinterSeverity, string> = {
  critical: "CRIT",
  high: "HIGH",
  medium: "MED",
  low: "LOW",
  info: "INFO",
};

export function IssueSeverityBar({
  issuesBySeverity,
  maxWidth = 100,
}: IssueSeverityBarProps): JSX.Element {
  const total = Object.values(issuesBySeverity).reduce((sum, count) => sum + count, 0);
  const maxCount = Math.max(...Object.values(issuesBySeverity), 1);

  if (total === 0) {
    return (
      <div className="severity-bar severity-bar--empty">
        <span className="severity-bar__empty">No issues</span>
      </div>
    );
  }

  return (
    <div className="severity-bar">
      {SEVERITY_ORDER.map((severity) => {
        const count = issuesBySeverity[severity] ?? 0;
        if (count === 0) return null;

        const widthPercent = (count / maxCount) * maxWidth;

        return (
          <div key={severity} className="severity-bar__row">
            <span
              className="severity-bar__label"
              style={{ color: SEVERITY_COLORS[severity] }}
            >
              {SEVERITY_LABELS[severity]}
            </span>
            <div className="severity-bar__track">
              <div
                className="severity-bar__fill"
                style={{
                  width: `${widthPercent}%`,
                  backgroundColor: SEVERITY_COLORS[severity],
                }}
              />
            </div>
            <span className="severity-bar__count">{count}</span>
          </div>
        );
      })}
    </div>
  );
}
