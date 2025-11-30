import { useState } from "react";
import type { UseQueryResult } from "@tanstack/react-query";

import type { StatusPayload } from "../api/types";
import { Sidebar } from "./Sidebar";
import { DetailPanel } from "./DetailPanel";
import { SearchPanel } from "./SearchPanel";
import { ActivityFeed } from "./ActivityFeed";
import { StatusPanel } from "./StatusPanel";
import { FileDiffModal } from "./FileDiffModal";
import { ChangeListPanel } from "./ChangeListPanel";

export function CodeMapDashboard({
  statusQuery,
}: {
  statusQuery: UseQueryResult<StatusPayload>;
}): JSX.Element {
  const [diffTarget, setDiffTarget] = useState<string | null>(null);

  const handleShowDiff = (path: string) => {
    setDiffTarget(path);
  };

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
      </aside>
      {diffTarget && <FileDiffModal path={diffTarget} onClose={closeDiff} />}
    </div>
  );
}
