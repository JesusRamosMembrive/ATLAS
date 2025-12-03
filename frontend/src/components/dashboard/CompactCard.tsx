import { Link } from "react-router-dom";

export type CardTone = "success" | "warn" | "danger" | "neutral";

export interface CardMetric {
  label: string;
  value: string | number;
}

interface CompactCardProps {
  title: string;
  status: CardTone;
  statusLabel: string;
  metrics?: CardMetric[];
  link?: { to: string; label: string };
  children?: React.ReactNode;
  className?: string;
}

export function CompactCard({
  title,
  status,
  statusLabel,
  metrics,
  link,
  children,
  className = "",
}: CompactCardProps): JSX.Element {
  return (
    <article className={`compact-card ${className}`}>
      <header className="compact-card__header">
        <div className="compact-card__title-row">
          <span className={`command-pill command-pill--${status}`}>{statusLabel}</span>
          <h4 className="compact-card__title">{title}</h4>
        </div>
        {link ? (
          <Link className="compact-card__link" to={link.to}>
            {link.label}
          </Link>
        ) : null}
      </header>
      {children ? <div className="compact-card__content">{children}</div> : null}
      {metrics && metrics.length > 0 ? (
        <div className="compact-card__metrics">
          {metrics.map((metric) => (
            <div key={metric.label} className="compact-metric">
              <span className="compact-metric__label">{metric.label}</span>
              <span className="compact-metric__value">{metric.value}</span>
            </div>
          ))}
        </div>
      ) : null}
    </article>
  );
}
