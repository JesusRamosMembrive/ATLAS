import { useState, useEffect } from "react";
import { useLocation } from "react-router-dom";
import type { UseQueryResult } from "@tanstack/react-query";

import type { StatusPayload } from "../api/types";
import { Sidebar } from "./Sidebar";
import { DetailPanel } from "./DetailPanel";
import { SearchPanel } from "./SearchPanel";
import { ActivityFeed } from "./ActivityFeed";
import { StatusPanel } from "./StatusPanel";
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
    <div className="main-grid">
      <Sidebar onShowDiff={handleShowDiff} />
      <DetailPanel onShowDiff={handleShowDiff} />
      <aside className="panel inspector-panel">
        <SearchPanel />
        <ChangeListPanel onShowDiff={handleShowDiff} />
        <StatusPanel statusQuery={statusQuery} />
        <div>
          <h2>Actividad reciente</h2>
          <ActivityFeed />
        </div>
        {stageStatusQuery.data?.detection && (
          <div style={{ marginTop: "16px" }}>
            <ComplexityCard detection={stageStatusQuery.data.detection} variant="sidebar" />
          </div>
        )}
      </aside>
      {diffTarget && <FileDiffModal path={diffTarget} onClose={closeDiff} />}
    </div>
  );
}
