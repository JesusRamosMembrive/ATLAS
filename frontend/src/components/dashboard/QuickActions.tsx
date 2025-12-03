import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { queryKeys } from "../../api/queryKeys";
import { useOllamaStartMutation } from "../../hooks/useOllamaStartMutation";
import { useOllamaTestMutation } from "../../hooks/useOllamaTestMutation";
import { useStageInitMutation } from "../../hooks/useStageInitMutation";

interface QuickActionsProps {
  ollamaRunning?: boolean;
  ollamaModel?: string;
  disabled?: boolean;
}

export function QuickActions({
  ollamaRunning = false,
  ollamaModel,
  disabled = false,
}: QuickActionsProps): JSX.Element {
  const queryClient = useQueryClient();
  const [isRunningLinters, setIsRunningLinters] = useState(false);
  const [lastResult, setLastResult] = useState<string | null>(null);

  const ollamaStartMutation = useOllamaStartMutation();
  const ollamaTestMutation = useOllamaTestMutation();
  const stageInitMutation = useStageInitMutation();

  const handleRunLinters = async () => {
    setIsRunningLinters(true);
    setLastResult(null);
    try {
      const response = await fetch("/api/linters/run", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      });

      if (!response.ok) {
        setLastResult("Linters failed");
      } else {
        setLastResult("Linters OK");
        await queryClient.invalidateQueries({ queryKey: queryKeys.lintersLatest });
      }
    } catch {
      setLastResult("Linters error");
    } finally {
      setIsRunningLinters(false);
    }
  };

  const handleOllamaAction = () => {
    setLastResult(null);
    if (ollamaRunning && ollamaModel) {
      ollamaTestMutation.mutate(
        { model: ollamaModel, prompt: "ping" },
        {
          onSuccess: (data) => setLastResult(`Ollama: ${data.latency_ms}ms`),
          onError: () => setLastResult("Ollama test failed"),
        }
      );
    } else {
      ollamaStartMutation.mutate(
        {},
        {
          onSuccess: () => {
            setLastResult("Ollama started");
            queryClient.invalidateQueries({ queryKey: queryKeys.ollamaStatus });
          },
          onError: () => setLastResult("Ollama start failed"),
        }
      );
    }
  };

  const handleDetectStage = () => {
    setLastResult(null);
    stageInitMutation.mutate(
      { agents: "all", force: false },
      {
        onSuccess: () => {
          setLastResult("Stage detected");
          queryClient.invalidateQueries({ queryKey: queryKeys.stageStatus });
        },
        onError: () => setLastResult("Stage detection failed"),
      }
    );
  };

  const isOllamaLoading = ollamaStartMutation.isPending || ollamaTestMutation.isPending;
  const isStageLoading = stageInitMutation.isPending;

  return (
    <div className="quick-actions">
      <button
        type="button"
        className={`quick-action-btn ${isRunningLinters ? "quick-action-btn--loading" : ""}`}
        onClick={handleRunLinters}
        disabled={disabled || isRunningLinters}
      >
        {isRunningLinters ? "Running..." : "Run Linters"}
      </button>

      <button
        type="button"
        className={`quick-action-btn ${isOllamaLoading ? "quick-action-btn--loading" : ""}`}
        onClick={handleOllamaAction}
        disabled={disabled || isOllamaLoading}
      >
        {isOllamaLoading ? "..." : ollamaRunning ? "Test Ollama" : "Start Ollama"}
      </button>

      <button
        type="button"
        className={`quick-action-btn ${isStageLoading ? "quick-action-btn--loading" : ""}`}
        onClick={handleDetectStage}
        disabled={disabled || isStageLoading}
      >
        {isStageLoading ? "Detecting..." : "Detect Stage"}
      </button>

      <button
        type="button"
        className="quick-action-btn"
        onClick={() => queryClient.invalidateQueries()}
        disabled={disabled}
      >
        Refresh All
      </button>

      {lastResult ? (
        <span className="quick-actions__result">{lastResult}</span>
      ) : null}
    </div>
  );
}
