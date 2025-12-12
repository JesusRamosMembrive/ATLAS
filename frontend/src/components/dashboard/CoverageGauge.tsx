interface CoverageGaugeProps {
  statementCoverage?: number | null;
  branchCoverage?: number | null;
  size?: number;
}

function getColorForCoverage(percent: number): string {
  if (percent >= 80) return "#22c55e";
  if (percent >= 60) return "#eab308";
  if (percent >= 40) return "#f97316";
  return "#ef4444";
}

export function CoverageGauge({
  statementCoverage,
  branchCoverage,
  size = 64,
}: CoverageGaugeProps): JSX.Element {
  const coverage = statementCoverage ?? branchCoverage ?? null;

  if (coverage === null) {
    return (
      <div className="coverage-gauge coverage-gauge--empty">
        <span className="coverage-gauge__label">Coverage</span>
        <span className="coverage-gauge__value">N/A</span>
      </div>
    );
  }

  const percent = Math.min(100, Math.max(0, coverage));
  const color = getColorForCoverage(percent);

  // SVG arc parameters
  const strokeWidth = 6;
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const dashOffset = circumference * (1 - percent / 100);

  return (
    <div className="coverage-gauge">
      <div className="coverage-gauge__circle" style={{ width: size, height: size }}>
        <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
          {/* Background circle */}
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke="rgba(148, 163, 184, 0.2)"
            strokeWidth={strokeWidth}
          />
          {/* Progress arc */}
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke={color}
            strokeWidth={strokeWidth}
            strokeLinecap="round"
            strokeDasharray={circumference}
            strokeDashoffset={dashOffset}
            transform={`rotate(-90 ${size / 2} ${size / 2})`}
            style={{ transition: "stroke-dashoffset 0.3s ease" }}
          />
        </svg>
        <span className="coverage-gauge__percent" style={{ color }}>
          {Math.round(percent)}%
        </span>
      </div>
      <div className="coverage-gauge__labels">
        <span className="coverage-gauge__title">Coverage</span>
        {statementCoverage != null && branchCoverage != null && (
          <span className="coverage-gauge__detail">
            Stmt: {Math.round(statementCoverage)}% | Branch: {Math.round(branchCoverage)}%
          </span>
        )}
      </div>
    </div>
  );
}
