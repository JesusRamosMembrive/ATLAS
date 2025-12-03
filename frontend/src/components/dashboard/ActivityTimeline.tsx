import { Link } from "react-router-dom";

export interface ActivityItem {
  id: string;
  label: string;
  description: string;
  timestamp: number;
  link?: { to: string; label: string };
  tone?: "success" | "warn" | "danger" | "neutral";
}

interface ActivityTimelineProps {
  items: ActivityItem[];
  maxVisible?: number;
}

function formatRelativeTime(timestamp: number): string {
  const now = Date.now();
  const diff = now - timestamp;
  if (diff < 0) return "Upcoming";

  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return "Now";
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h`;
  const days = Math.floor(hours / 24);
  return `${days}d`;
}

export function ActivityTimeline({
  items,
  maxVisible = 6,
}: ActivityTimelineProps): JSX.Element {
  const visibleItems = items.slice(0, maxVisible);
  const hasMore = items.length > maxVisible;

  if (visibleItems.length === 0) {
    return (
      <div className="activity-timeline activity-timeline--empty">
        <span className="activity-timeline__empty">No recent activity</span>
      </div>
    );
  }

  return (
    <div className="activity-timeline">
      <div className="activity-timeline__scroll">
        {visibleItems.map((item) => (
          <div
            key={item.id}
            className={`activity-timeline__item ${item.tone ? `activity-timeline__item--${item.tone}` : ""}`}
          >
            <div className="activity-timeline__header">
              <span className="activity-timeline__label">{item.label}</span>
              <span className="activity-timeline__time">{formatRelativeTime(item.timestamp)}</span>
            </div>
            <p className="activity-timeline__desc">{item.description}</p>
            {item.link ? (
              <Link className="activity-timeline__link" to={item.link.to}>
                {item.link.label}
              </Link>
            ) : null}
          </div>
        ))}
        {hasMore ? (
          <Link to="/code-map" className="activity-timeline__more">
            +{items.length - maxVisible} more
          </Link>
        ) : null}
      </div>
    </div>
  );
}
