import { Link } from "react-router-dom";
import type { CommitInfo } from "../../hooks/useRecentCommits";

interface RecentCommitsProps {
  commits: CommitInfo[];
  maxItems?: number;
  isLoading?: boolean;
}

function formatRelativeTime(dateStr: string): string {
  const date = new Date(dateStr);
  const now = Date.now();
  const diff = now - date.getTime();

  if (diff < 0) return "upcoming";
  const minutes = Math.floor(diff / 60000);
  if (minutes < 1) return "now";
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d`;
  const weeks = Math.floor(days / 7);
  return `${weeks}w`;
}

function truncateMessage(message: string, maxLen = 40): string {
  const firstLine = message.split("\n")[0];
  if (firstLine.length <= maxLen) return firstLine;
  return `${firstLine.slice(0, maxLen - 3)}...`;
}

function getShortHash(hash: string): string {
  return hash.slice(0, 7);
}

export function RecentCommits({
  commits,
  maxItems = 5,
  isLoading = false,
}: RecentCommitsProps): JSX.Element {
  const visibleCommits = commits.slice(0, maxItems);

  if (isLoading) {
    return (
      <div className="recent-commits recent-commits--loading">
        <div className="recent-commits__header">
          <span className="recent-commits__title">Recent Commits</span>
        </div>
        <span className="recent-commits__loading">Loading...</span>
      </div>
    );
  }

  if (visibleCommits.length === 0) {
    return (
      <div className="recent-commits recent-commits--empty">
        <div className="recent-commits__header">
          <span className="recent-commits__title">Recent Commits</span>
        </div>
        <span className="recent-commits__empty">No commits found</span>
      </div>
    );
  }

  return (
    <div className="recent-commits">
      <div className="recent-commits__header">
        <span className="recent-commits__title">Recent Commits</span>
        <Link to="/timeline" className="recent-commits__link">
          Timeline
        </Link>
      </div>
      <ul className="recent-commits__list">
        {visibleCommits.map((commit) => (
          <li key={commit.hash} className="recent-commits__item">
            <span className="recent-commits__hash">{getShortHash(commit.hash)}</span>
            <span className="recent-commits__message" title={commit.message}>
              {truncateMessage(commit.message)}
            </span>
            <span className="recent-commits__time">{formatRelativeTime(commit.date)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
