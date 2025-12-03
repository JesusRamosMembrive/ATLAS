import { Link } from "react-router-dom";
import type { WorkingTreeChange } from "../../api/types";

interface PendingChangesListProps {
  changes: WorkingTreeChange[];
  maxItems?: number;
}

function getFileName(path: string): string {
  const parts = path.replace(/\\/g, "/").split("/");
  return parts[parts.length - 1] || path;
}

function getStatusLabel(status: string): string {
  switch (status.toUpperCase()) {
    case "A":
    case "ADDED":
      return "A";
    case "M":
    case "MODIFIED":
      return "M";
    case "D":
    case "DELETED":
      return "D";
    case "R":
    case "RENAMED":
      return "R";
    case "C":
    case "COPIED":
      return "C";
    case "U":
    case "UNTRACKED":
      return "?";
    default:
      return status.charAt(0).toUpperCase();
  }
}

function getStatusClass(status: string): string {
  switch (status.toUpperCase()) {
    case "A":
    case "ADDED":
      return "added";
    case "M":
    case "MODIFIED":
      return "modified";
    case "D":
    case "DELETED":
      return "deleted";
    case "R":
    case "RENAMED":
      return "renamed";
    default:
      return "other";
  }
}

export function PendingChangesList({
  changes,
  maxItems = 5,
}: PendingChangesListProps): JSX.Element {
  const visibleChanges = changes.slice(0, maxItems);
  const remaining = changes.length - maxItems;

  if (changes.length === 0) {
    return (
      <div className="pending-changes pending-changes--empty">
        <span className="pending-changes__empty">No pending changes</span>
      </div>
    );
  }

  return (
    <div className="pending-changes">
      <div className="pending-changes__header">
        <span className="pending-changes__title">Pending Changes</span>
        <Link to="/code-map" className="pending-changes__link">
          View
        </Link>
      </div>
      <ul className="pending-changes__list">
        {visibleChanges.map((change) => (
          <li key={change.path} className="pending-changes__item">
            <span
              className={`pending-changes__status pending-changes__status--${getStatusClass(change.status)}`}
            >
              {getStatusLabel(change.status)}
            </span>
            <span className="pending-changes__name" title={change.path}>
              {getFileName(change.path)}
            </span>
          </li>
        ))}
      </ul>
      {remaining > 0 && (
        <Link to="/code-map" className="pending-changes__more">
          +{remaining} more
        </Link>
      )}
    </div>
  );
}
