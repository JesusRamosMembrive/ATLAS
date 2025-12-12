import { useState } from "react";
import type { CloneEntry, CloneType } from "../../api/similarityTypes";

interface ClonesCardProps {
  clones: CloneEntry[];
  isLoading?: boolean;
  maxVisible?: number;
}

interface CloneTypeBadgeInfo {
  label: string;
  className: string;
  tooltip: string;
}

function getCloneTypeBadge(type: CloneType): CloneTypeBadgeInfo {
  switch (type) {
    case "Type-1":
      return {
        label: "Exact",
        className: "similarity-clone-badge--exact",
        tooltip: "Exact duplicate: identical code (ignoring whitespace and comments)",
      };
    case "Type-2":
      return {
        label: "Renamed",
        className: "similarity-clone-badge--renamed",
        tooltip: "Renamed clone: same structure but with different variable/function names",
      };
    case "Type-3":
      return {
        label: "Modified",
        className: "similarity-clone-badge--modified",
        tooltip: "Modified clone: similar code with some statements added, removed, or changed",
      };
    default:
      return { label: type, className: "", tooltip: "" };
  }
}

function getFilename(path: string): string {
  const parts = path.split("/");
  return parts[parts.length - 1] || path;
}

function formatSimilarity(similarity: number): string {
  return `${(similarity * 100).toFixed(0)}%`;
}

interface CloneItemProps {
  clone: CloneEntry;
}

function CloneItem({ clone }: CloneItemProps): JSX.Element {
  const [expanded, setExpanded] = useState(false);
  const badge = getCloneTypeBadge(clone.type);

  const loc1 = clone.locations[0];
  const loc2 = clone.locations[1];

  return (
    <div className="similarity-clone-item">
      <button
        className="similarity-clone-item__header"
        onClick={() => setExpanded(!expanded)}
      >
        <span className="similarity-clone-item__expand">
          {expanded ? "▼" : "▶"}
        </span>
        <span className={`similarity-clone-badge ${badge.className}`} title={badge.tooltip}>
          {badge.label}
        </span>
        <span className="similarity-clone-item__similarity">
          {formatSimilarity(clone.similarity)}
        </span>
        <span className="similarity-clone-item__locations">
          {loc1 && (
            <span className="similarity-clone-item__file" title={loc1.file}>
              {getFilename(loc1.file)}:{loc1.start_line}
            </span>
          )}
          {loc1 && loc2 && <span className="similarity-clone-item__separator">↔</span>}
          {loc2 && (
            <span className="similarity-clone-item__file" title={loc2.file}>
              {getFilename(loc2.file)}:{loc2.start_line}
            </span>
          )}
        </span>
      </button>

      {expanded && (
        <div className="similarity-clone-item__details">
          <div className="similarity-clone-item__recommendation">
            {clone.recommendation}
          </div>
          {clone.locations.map((loc, idx) => (
            <div key={idx} className="similarity-clone-item__location">
              <div className="similarity-clone-item__location-header">
                <span className="similarity-clone-item__location-file">
                  {loc.file}
                </span>
                <span className="similarity-clone-item__location-lines">
                  Lines {loc.start_line}-{loc.end_line}
                </span>
              </div>
              {loc.snippet_preview && (
                <pre className="similarity-clone-item__snippet">
                  {loc.snippet_preview}
                </pre>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export function ClonesCard({
  clones,
  isLoading,
  maxVisible = 20,
}: ClonesCardProps): JSX.Element {
  const [showAll, setShowAll] = useState(false);
  const [filterType, setFilterType] = useState<CloneType | "all">("all");

  const filteredClones =
    filterType === "all"
      ? clones
      : clones.filter((c) => c.type === filterType);

  const displayClones = showAll
    ? filteredClones
    : filteredClones.slice(0, maxVisible);

  const hasMore = filteredClones.length > maxVisible;

  // Count by type
  const typeCounts = clones.reduce(
    (acc, c) => {
      acc[c.type] = (acc[c.type] || 0) + 1;
      return acc;
    },
    {} as Record<string, number>
  );

  if (isLoading) {
    return (
      <section className="similarity-card similarity-clones-card">
        <header className="similarity-card__header">
          <h3 className="similarity-card__title">Clone Pairs</h3>
        </header>
        <div className="similarity-loading">Detecting clones...</div>
      </section>
    );
  }

  return (
    <section className="similarity-card similarity-clones-card">
      <header className="similarity-card__header">
        <h3 className="similarity-card__title">Clone Pairs</h3>
        <div className="similarity-card__filters">
          <button
            className={`similarity-filter-btn ${filterType === "all" ? "active" : ""}`}
            onClick={() => setFilterType("all")}
          >
            All ({clones.length})
          </button>
          {Object.entries(typeCounts).map(([type, count]) => {
            const badge = getCloneTypeBadge(type as CloneType);
            return (
              <button
                key={type}
                className={`similarity-filter-btn ${filterType === type ? "active" : ""}`}
                onClick={() => setFilterType(type as CloneType)}
                title={badge.tooltip}
              >
                {badge.label} ({count})
              </button>
            );
          })}
        </div>
      </header>

      {filteredClones.length === 0 ? (
        <div className="similarity-empty">
          {clones.length === 0
            ? "No code clones detected"
            : "No clones match the current filter"}
        </div>
      ) : (
        <>
          <div className="similarity-clones-list">
            {displayClones.map((clone) => (
              <CloneItem key={clone.id} clone={clone} />
            ))}
          </div>

          {hasMore && (
            <button
              className="similarity-card__toggle"
              onClick={() => setShowAll(!showAll)}
            >
              {showAll
                ? "Show less"
                : `Show ${filteredClones.length - maxVisible} more`}
            </button>
          )}
        </>
      )}
    </section>
  );
}
