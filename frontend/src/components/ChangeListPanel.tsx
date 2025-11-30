import { useQuery } from "@tanstack/react-query";

import { getWorkingTreeChanges } from "../api/client";
import { queryKeys } from "../api/queryKeys";
import { useSelectionStore } from "../state/useSelectionStore";
import type { WorkingTreeChange } from "../api/types";
import { getChangeLabel, getChangeVariant } from "../utils/changeStatus";
import "../styles/changes.css";

interface ChangeListPanelProps {
  onShowDiff?: (path: string) => void;
}

export function ChangeListPanel({ onShowDiff }: ChangeListPanelProps): JSX.Element {
  const selectPath = useSelectionStore((state) => state.selectPath);

  const { data, isPending, isError, error, refetch } = useQuery({
    queryKey: queryKeys.changes,
    queryFn: getWorkingTreeChanges,
    refetchInterval: 15000,
  });

  const changes = data?.changes ?? [];

  return (
    <section className="change-panel">
      <div className="change-panel__header">
        <h2>Working tree</h2>
        <button type="button" onClick={() => refetch()}>
          Refresh
        </button>
      </div>

      {isPending && <p className="change-panel__hint">Checking git status…</p>}

      {isError && (
        <div className="error-banner">
          Could not load changes: {(error as Error)?.message ?? "unknown error"}
        </div>
      )}

      {!isPending && !isError && changes.length === 0 && (
        <p className="change-panel__hint">Workspace clean — no pending changes.</p>
      )}

      {changes.length > 0 && (
        <ul className="change-list">
          {changes.map((change) => (
            <ChangeListItem
              key={change.path}
              change={change}
              onSelect={selectPath}
              onShowDiff={onShowDiff}
            />
          ))}
        </ul>
      )}
    </section>
  );
}

function ChangeListItem({
  change,
  onSelect,
  onShowDiff,
}: {
  change: WorkingTreeChange;
  onSelect: (path: string) => void;
  onShowDiff?: (path: string) => void;
}): JSX.Element {
  const label = getChangeLabel(change.status);
  const pillClass = `change-pill change-pill--${getChangeVariant(change.status)}`;

  return (
    <li className="change-item">
      <div className="change-item__row">
        <span className={pillClass}>{label}</span>
        <div className="change-item__actions">
          <button
            type="button"
            className="change-item__link"
            onClick={() => onSelect(change.path)}
          >
            Focus file
          </button>
          {onShowDiff && (
            <button
              type="button"
              className="change-item__link"
              onClick={() => onShowDiff(change.path)}
            >
              View diff
            </button>
          )}
        </div>
      </div>
      <div className="change-item__path" onClick={() => onSelect(change.path)}>
        {change.path}
      </div>
      {change.summary && <p className="change-item__summary">{change.summary}</p>}
    </li>
  );
}
