import { Link } from "react-router-dom";
import type { OllamaStatus, StageDetectionStatus, AnalyzerCapability } from "../../api/types";
import { AnalyzerHealth } from "./AnalyzerHealth";

interface CommandStatusBarProps {
  backendOnline: boolean;
  backendLoading?: boolean;
  ollamaStatus?: OllamaStatus;
  watcherActive: boolean;
  stageDetection?: StageDetectionStatus;
  rootPath: string;
  capabilities?: AnalyzerCapability[];
}

export function CommandStatusBar({
  backendOnline,
  backendLoading,
  ollamaStatus,
  watcherActive,
  stageDetection,
  rootPath,
  capabilities = [],
}: CommandStatusBarProps): JSX.Element {
  const backendTone = backendLoading ? "neutral" : backendOnline ? "success" : "danger";
  const backendLabel = backendLoading ? "..." : backendOnline ? "Backend" : "Offline";

  const ollamaTone = ollamaStatus?.running
    ? "success"
    : ollamaStatus?.installed
      ? "warn"
      : "neutral";
  const ollamaLabel = ollamaStatus?.running
    ? "Ollama"
    : ollamaStatus?.installed
      ? "Ollama stopped"
      : "No Ollama";

  const watcherTone = watcherActive ? "success" : "warn";
  const watcherLabel = watcherActive ? "Watcher" : "Watcher off";

  const stageTone = stageDetection?.available ? "success" : "neutral";
  const stageLabel = stageDetection?.available
    ? `Stage ${stageDetection.recommended_stage ?? "?"}`
    : "No stage";

  const truncatedRoot =
    rootPath.length > 40 ? `...${rootPath.slice(-37)}` : rootPath;

  return (
    <header className="command-status-bar">
      <div className="command-status-pills">
        <Link to="/" className={`command-pill command-pill--${backendTone}`} title="Backend status">
          {backendLabel}
        </Link>
        <Link to="/ollama" className={`command-pill command-pill--${ollamaTone}`} title="Ollama status">
          {ollamaLabel}
        </Link>
        <Link to="/code-map" className={`command-pill command-pill--${watcherTone}`} title="File watcher">
          {watcherLabel}
        </Link>
        <Link to="/stage-toolkit" className={`command-pill command-pill--${stageTone}`} title="Stage detection">
          {stageLabel}
        </Link>
        {capabilities.length > 0 && (
          <span className="command-status-bar__separator">|</span>
        )}
        <AnalyzerHealth capabilities={capabilities} />
      </div>
      <div className="command-status-bar__path" title={rootPath}>
        <code>{truncatedRoot}</code>
      </div>
    </header>
  );
}
