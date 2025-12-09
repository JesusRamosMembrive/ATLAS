import { useState } from "react";
import type { DuplicationHotspot } from "../../api/similarityTypes";

interface HotspotsCardProps {
  hotspots: DuplicationHotspot[];
  isLoading?: boolean;
  maxVisible?: number;
}

function getScoreColor(score: number): string {
  if (score >= 0.5) return "var(--tone-danger)";
  if (score >= 0.25) return "var(--tone-warn)";
  return "var(--tone-success)";
}

function getFilename(path: string): string {
  const parts = path.split("/");
  return parts[parts.length - 1] || path;
}

export function HotspotsCard({
  hotspots,
  isLoading,
  maxVisible = 10,
}: HotspotsCardProps): JSX.Element {
  const [expanded, setExpanded] = useState(false);
  const displayHotspots = expanded ? hotspots : hotspots.slice(0, maxVisible);
  const hasMore = hotspots.length > maxVisible;

  if (isLoading) {
    return (
      <section className="similarity-card similarity-hotspots-card">
        <header className="similarity-card__header">
          <h3 className="similarity-card__title">Duplication Hotspots</h3>
        </header>
        <div className="similarity-loading">Finding hotspots...</div>
      </section>
    );
  }

  if (hotspots.length === 0) {
    return (
      <section className="similarity-card similarity-hotspots-card">
        <header className="similarity-card__header">
          <h3 className="similarity-card__title">Duplication Hotspots</h3>
          <span className="similarity-card__badge similarity-card__badge--success">
            No hotspots
          </span>
        </header>
        <div className="similarity-empty">
          No files with significant duplication detected
        </div>
      </section>
    );
  }

  const maxScore = Math.max(...hotspots.map((h) => h.duplication_score), 1);

  return (
    <section className="similarity-card similarity-hotspots-card">
      <header className="similarity-card__header">
        <h3 className="similarity-card__title">Duplication Hotspots</h3>
        <span className="similarity-card__badge">
          {hotspots.length} files
        </span>
      </header>

      <div className="similarity-hotspots-list">
        {displayHotspots.map((hotspot, index) => {
          const barWidth = (hotspot.duplication_score / maxScore) * 100;
          const scoreColor = getScoreColor(hotspot.duplication_score);

          return (
            <div key={hotspot.file || index} className="similarity-hotspot-item">
              <div className="similarity-hotspot-item__info">
                <span className="similarity-hotspot-item__name" title={hotspot.file}>
                  {getFilename(hotspot.file)}
                </span>
                <span className="similarity-hotspot-item__stats">
                  {hotspot.clone_count} clones
                  <span className="similarity-hotspot-item__score" style={{ color: scoreColor }}>
                    {(hotspot.duplication_score * 100).toFixed(1)}%
                  </span>
                </span>
              </div>
              <div className="similarity-hotspot-item__bar-container">
                <div
                  className="similarity-hotspot-item__bar"
                  style={{
                    width: `${barWidth}%`,
                    backgroundColor: scoreColor,
                  }}
                />
              </div>
            </div>
          );
        })}
      </div>

      {hasMore && (
        <button
          className="similarity-card__toggle"
          onClick={() => setExpanded(!expanded)}
        >
          {expanded ? "Show less" : `Show ${hotspots.length - maxVisible} more`}
        </button>
      )}
    </section>
  );
}
