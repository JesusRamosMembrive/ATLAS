import { useState, useEffect } from "react";
import { useLocation } from "react-router-dom";
import type { UseQueryResult } from "@tanstack/react-query";

import type { StatusPayload } from "../api/types";
import { Sidebar } from "./Sidebar";
import { DetailPanel } from "./DetailPanel";
import { SearchPanel } from "./SearchPanel";
import { ActivityFeed } from "./ActivityFeed";
import { StatusPanel, AnalyzersPanel } from "./StatusPanel";
import { FileDiffModal } from "./FileDiffModal";
import { useStageStatusQuery } from "../hooks/useStageStatusQuery";
import { ComplexityCard } from "./dashboard/ComplexityCard";
import { ChangeListPanel } from "./ChangeListPanel";
import { useSelectionStore } from "../state/useSelectionStore";

export function CodeMapDashboard({
  statusQuery,
}: {
  statusQuery: UseQueryResult<StatusPayload>;
}): JSX.Element {
  const [diffTarget, setDiffTarget] = useState<string | null>(null);
  const location = useLocation();
  const selectPath = useSelectionStore((state) => state.selectPath);

  // Handle navigation from complexity modal with file path in state
  useEffect(() => {
    const state = location.state as { selectPath?: string } | null;
    if (state?.selectPath) {
      selectPath(state.selectPath);
      // Clear the state to prevent re-selection on re-render
      window.history.replaceState({}, document.title);
    }
  }, [location.state, selectPath]);

  const handleShowDiff = (path: string) => {
    setDiffTarget(path);
  };

  const stageStatusQuery = useStageStatusQuery();

  const closeDiff = () => setDiffTarget(null);

  return (
    <div className="codemap-layout">
      {/* Main 3-column grid */}
      <div className="main-grid">
        <Sidebar onShowDiff={handleShowDiff} />
        <DetailPanel onShowDiff={handleShowDiff} />
        <aside className="panel inspector-panel">
          <SearchPanel />
          <ChangeListPanel onShowDiff={handleShowDiff} />
          <div>
            <h2>Actividad reciente</h2>
            <ActivityFeed />
          </div>
        </aside>
      </div>

      {/* Secondary row with info cards */}
      <div className="secondary-row">
        <article className="panel secondary-card">
          <StatusPanel statusQuery={statusQuery} />
        </article>
        <article className="panel secondary-card">
          <AnalyzersPanel statusQuery={statusQuery} />
        </article>
        {stageStatusQuery.data?.detection && (
          <article className="panel secondary-card">
            <ComplexityCard detection={stageStatusQuery.data.detection} variant="sidebar" />
          </article>
        )}
      </div>

      {diffTarget && <FileDiffModal path={diffTarget} onClose={closeDiff} />}
    </div>
  );
}
