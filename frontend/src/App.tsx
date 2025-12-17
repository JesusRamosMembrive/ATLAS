import { useEffect } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { HomeView } from "./components/HomeView";
import { CodeMapDashboard } from "./components/CodeMapDashboard";
import { SettingsView } from "./components/SettingsView";
import { StageToolkitView } from "./components/StageToolkitView";
import { ClassUMLView } from "./components/ClassUMLView";
import { CallFlowView } from "./components/CallFlowView";
import { LintersView } from "./components/LintersView";
import { OverviewDashboard } from "./components/OverviewDashboard";
import { PromptLibraryView } from "./components/PromptLibraryView";
import { AppLayout } from "./components/AppLayout";
import { OllamaInsightsView } from "./components/OllamaInsightsView";
import { RemoteTerminalView } from "./components/RemoteTerminalView";
import { ClaudeAgentView } from "./components/ClaudeAgentView";
import CodeTimelineView from "./components/CodeTimelineView";
import { DocsLibraryView } from "./components/DocsLibraryView";
import { SimilarityDashboard } from "./components/similarity";
import { useEventStream } from "./hooks/useEventStream";
import { useSettingsQuery } from "./hooks/useSettingsQuery";
import { useStatusQuery } from "./hooks/useStatusQuery";
import { useBackendStore } from "./state/useBackendStore";
import "./styles/index.css";

export function App(): JSX.Element {
  const settingsQuery = useSettingsQuery();
  const statusQuery = useStatusQuery();
  useEventStream();

  const setBackendUrl = useBackendStore((state) => state.setBackendUrl);

  // Initialize backend URL from settings on app load
  useEffect(() => {
    if (settingsQuery.data?.backend_url) {
      setBackendUrl(settingsQuery.data.backend_url);
    }
  }, [settingsQuery.data?.backend_url, setBackendUrl]);

  const rootPath = statusQuery.data?.root_path ?? settingsQuery.data?.root_path ?? "";
  const watcherActive = statusQuery.data?.watcher_active ?? false;
  const headerBase = {
    watcherActive,
    rootPath,
    lastFullScan: statusQuery.data?.last_full_scan ?? null,
    filesIndexed: statusQuery.data?.files_indexed,
  };

  const withLayout = (title: string, element: JSX.Element) => (
    <AppLayout headerProps={{ ...headerBase, title }}>{element}</AppLayout>
  );

  return (
    <BrowserRouter>
      <div className="app-root">
        <Routes>
          <Route
            path="/"
            element={withLayout("AEGIS - Home", <HomeView statusQuery={statusQuery} />)}
          />
          <Route
            path="/overview"
            element={withLayout("Workspace Overview", <OverviewDashboard statusQuery={statusQuery} />)}
          />
          <Route
            path="/code-map"
            element={withLayout("Code Map", <CodeMapDashboard statusQuery={statusQuery} />)}
          />
          <Route
            path="/docs"
            element={withLayout("Project Docs", <DocsLibraryView />)}
          />
          <Route
            path="/stage-toolkit"
            element={withLayout("Project Stage Toolkit", <StageToolkitView />)}
          />
          <Route
            path="/ollama"
            element={withLayout("Ollama Insights", <OllamaInsightsView />)}
          />
          <Route
            path="/class-uml"
            element={withLayout("Class UML", <ClassUMLView />)}
          />
          <Route
            path="/call-flow"
            element={withLayout("Call Flow", <CallFlowView />)}
          />
          <Route
            path="/prompts"
            element={withLayout("Prompt Library", <PromptLibraryView />)}
          />
          <Route
            path="/linters"
            element={withLayout("Linters & Quality", <LintersView />)}
          />
          <Route
            path="/similarity"
            element={withLayout("Code Similarity", <SimilarityDashboard />)}
          />
          <Route
            path="/timeline"
            element={withLayout("Code Timeline", <CodeTimelineView />)}
          />
          <Route
            path="/terminal"
            element={withLayout("Remote Terminal", <RemoteTerminalView />)}
          />
          <Route
            path="/agent"
            element={withLayout("Claude Agent", <ClaudeAgentView />)}
          />
          <Route
            path="/settings"
            element={withLayout("Settings", <SettingsView settingsQuery={settingsQuery} />)}
          />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </div>
    </BrowserRouter>
  );
}
