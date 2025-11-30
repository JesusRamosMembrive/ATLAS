import { useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import type { OllamaModelInfo, OllamaStatus } from "../api/types";
import { clearOllamaInsights, triggerOllamaInsights, updateSettings } from "../api/client";
import { queryKeys } from "../api/queryKeys";
import { useOllamaInsightsQuery } from "../hooks/useOllamaInsightsQuery";
import { useOllamaStartMutation } from "../hooks/useOllamaStartMutation";
import { useOllamaStatusQuery } from "../hooks/useOllamaStatusQuery";
import { useOllamaTestMutation } from "../hooks/useOllamaTestMutation";
import { useSettingsQuery } from "../hooks/useSettingsQuery";
import { useStatusQuery } from "../hooks/useStatusQuery";

const HISTORY_LIMIT = 50;
const DEFAULT_PROMPT = "Briefly summarize the purpose of the current repository.";
const QUICK_TEST_PROMPT = "responde solo pong";

const INSIGHT_FOCUS_OPTIONS = [
  {
    value: "general",
    label: "General overview",
    description: "Combine refactors, quality recommendations, and high-level next steps.",
    prompt:
      "Analyze the current state of the repository at {root}. Suggest refactors, solutions for linter issues, and relevant design patterns. If you lack context, propose general next steps.",
  },
  {
    value: "refactors",
    label: "Refactors and cleanup",
    description: "Prioritize simplifications, modularization, and readability improvements.",
    prompt:
      "Analyze the repository at {root} and prioritize spotting refactor opportunities. Recommend simplifications, module extraction, and readability improvements. Include concrete suggestions about files or components to adjust.",
  },
  {
    value: "issues",
    label: "Potential issues",
    description: "Surface bug risks, fragile dependencies, or weak error handling.",
    prompt:
      "Review the repository at {root} for potential failures, poor error handling, fragile dependencies, or inconsistent behavior. Suggest additional checks and mitigations.",
  },
  {
    value: "duplication",
    label: "Duplication & responsibilities",
    description: "Detect duplicated logic and overlapping responsibilities.",
    prompt:
      "Inspect {root} for duplicated logic, overlapping responsibilities, or modules that should be consolidated. Propose strategies to redistribute responsibilities and reduce redundancies.",
  },
  {
    value: "testing",
    label: "Coverage & testing",
    description: "Focus on detecting test gaps and unvalidated critical scenarios.",
    prompt:
      "Assess {root} with a focus on coverage and testing strategy. Identify areas without tests, critical scenarios left unvalidated, and opportunities to strengthen automated suites.",
  },
] as const;

function normalizeFocus(value?: string | null): string {
  const normalized = (value ?? "").trim().toLowerCase();
  return INSIGHT_FOCUS_OPTIONS.some((option) => option.value === normalized)
    ? normalized
    : "general";
}

type ManualInsightsPayload = {
  model?: string;
  timeout_seconds?: number;
  focus?: string;
};

function formatLatency(latencyMs: number): string {
  if (latencyMs < 1000) {
    return `${latencyMs.toFixed(0)} ms`;
  }
  return `${(latencyMs / 1000).toFixed(2)} s`;
}

function formatModelDetails(model: OllamaModelInfo): string | null {
  const details: string[] = [];
  if (model.size_human) {
    details.push(model.size_human);
  }
  if (model.modified_at) {
    details.push(`updated ${new Date(model.modified_at).toLocaleDateString()}`);
  }
  return details.length > 0 ? details.join(" · ") : null;
}

function OllamaStatusCard({
  status,
  lastChecked,
  onStart,
  isStarting,
  startError,
  onTestConnection,
  isTestingConnection = false,
  canTestConnection = true,
}: {
  status: OllamaStatus | undefined;
  lastChecked: string | undefined;
  onStart: () => void;
  isStarting: boolean;
  startError: string | null;
  onTestConnection?: () => void;
  isTestingConnection?: boolean;
  canTestConnection?: boolean;
}): JSX.Element {
  if (!status) {
    return (
      <article className="stage-card">
        <header>
          <h3>Ollama</h3>
        </header>
        <p>Could not fetch the Ollama status.</p>
      </article>
    );
  }

  const runningBadgeClass = status.running ? "stage-badge success" : "stage-badge warn";
  const runningLabel = status.running ? "Running" : "Stopped";
  const canStart = status.installed && !status.running;
  const canRunQuickTest = Boolean(status.running && onTestConnection && canTestConnection);

  return (
    <article className="stage-card">
      <header>
        <h3>Ollama</h3>
        <span className={runningBadgeClass}>{runningLabel}</span>
      </header>
      <section>
        <p className="stage-meta">
          Installation: <strong>{status.installed ? "Detected" : "Not found"}</strong>
        </p>
        {status.version ? <p className="stage-meta">Version: {status.version}</p> : null}
        {status.binary_path ? (
          <p className="stage-meta">
            Binary: <code>{status.binary_path}</code>
          </p>
        ) : null}
        {status.endpoint ? (
          <p className="stage-meta">
            Endpoint: <code>{status.endpoint}</code>
          </p>
        ) : null}
        {lastChecked ? (
          <p className="stage-meta">Last check: {new Date(lastChecked).toLocaleString()}</p>
        ) : null}
      </section>
      <section>
        <h4>Detected models</h4>
        {status.models.length > 0 ? (
          <ul className="stage-list">
            {status.models.map((model) => {
              const details = formatModelDetails(model);
              return (
                <li key={model.name}>
                  <span>{model.name}</span>
                  {details ? <span> - {details}</span> : null}
                </li>
              );
            })}
          </ul>
        ) : status.running ? (
          <p className="stage-info">No registered models found.</p>
        ) : (
          <p className="stage-info">Start Ollama to list the available models.</p>
        )}
      </section>
      {status.warning ? <p className="stage-info">Warning: {status.warning}</p> : null}
      {status.error ? <p className="stage-error">Error: {status.error}</p> : null}
      {(canStart || onTestConnection) ? (
        <div className="stage-form-actions">
          {canStart ? (
            <button className="secondary-btn" type="button" onClick={onStart} disabled={isStarting}>
              {isStarting ? "Starting…" : "Start Ollama"}
            </button>
          ) : null}
          {onTestConnection ? (
            <button
              className="secondary-btn"
              type="button"
              onClick={onTestConnection}
              disabled={!canRunQuickTest || isTestingConnection}
            >
              {isTestingConnection ? "Testing…" : "Test connection"}
            </button>
          ) : null}
        </div>
      ) : null}
      {onTestConnection ? (
        <p className="stage-hint">
          Sends "{QUICK_TEST_PROMPT}" to confirm the local endpoint responds correctly.
        </p>
      ) : null}
      {startError ? <p className="stage-error">{startError}</p> : null}
    </article>
  );
}

export function OllamaInsightsView(): JSX.Element {
  const statusQuery = useStatusQuery();
  const settingsQuery = useSettingsQuery();
  const ollamaStatusQuery = useOllamaStatusQuery();
  const ollamaStartMutation = useOllamaStartMutation();
  const ollamaTestMutation = useOllamaTestMutation();
  const insightsQuery = useOllamaInsightsQuery(HISTORY_LIMIT);
  const queryClient = useQueryClient();

  const [selectedOllamaModel, setSelectedOllamaModel] = useState<string>("");
  const [ollamaPrompt, setOllamaPrompt] = useState<string>(DEFAULT_PROMPT);
  const [ollamaSystemPrompt, setOllamaSystemPrompt] = useState<string>("");
  const [ollamaEndpoint, setOllamaEndpoint] = useState<string>("");
  const [ollamaTimeout, setOllamaTimeout] = useState<string>("180");
  const [ollamaEndpointTouched, setOllamaEndpointTouched] = useState<boolean>(false);
  const [insightsEnabled, setInsightsEnabled] = useState<boolean>(false);
  const [insightsModel, setInsightsModel] = useState<string>("");
  const [insightsFocus, setInsightsFocus] = useState<string>("general");
  const [insightsFrequency, setInsightsFrequency] = useState<string>("60");
  const [insightsStatus, setInsightsStatus] = useState<string | null>(null);

  const settings = settingsQuery.data;
  const settingsLoading = settingsQuery.isLoading;

  useEffect(() => {
    if (!settings) {
      return;
    }
    setInsightsEnabled(settings.ollama_insights_enabled);
    setInsightsModel(settings.ollama_insights_model ?? "");
    setInsightsFocus(normalizeFocus(settings.ollama_insights_focus));
    setInsightsFrequency(
      settings.ollama_insights_frequency_minutes !== null
        ? String(settings.ollama_insights_frequency_minutes)
        : "60",
    );
  }, [settings]);

  const ollamaStatus = ollamaStatusQuery.data?.status;
  const ollamaLastChecked = ollamaStatusQuery.data?.checked_at;

  const availableOllamaModels = useMemo(
    () => (ollamaStatus?.models ?? []).map((model) => model.name),
    [ollamaStatus],
  );

  useEffect(() => {
    if (availableOllamaModels.length === 0) {
      return;
    }
    setSelectedOllamaModel((current) =>
      current && availableOllamaModels.includes(current)
        ? current
        : availableOllamaModels[0],
    );
  }, [availableOllamaModels]);

  const ollamaEndpointHint = ollamaStatus?.endpoint ?? "http://127.0.0.1:11434";
  const isOllamaRunning = ollamaStatus?.running ?? false;
  const isOllamaDetected = ollamaStatus?.installed ?? false;

  const parsedTimeout = useMemo(() => {
    const raw = ollamaTimeout.trim();
    if (!raw) {
      return undefined;
    }
    const value = Number.parseFloat(raw);
    return Number.isFinite(value) ? value : undefined;
  }, [ollamaTimeout]);

  const isTimeoutValid =
    !ollamaTimeout.trim() ||
    (parsedTimeout !== undefined && parsedTimeout > 0 && parsedTimeout <= 1200);

  const isTestingOllama = ollamaTestMutation.isPending;
  const ollamaTestResult = ollamaTestMutation.data;
  const ollamaTestError = ollamaTestMutation.error;

  const canSubmitOllamaTest =
    selectedOllamaModel.trim().length > 0 && ollamaPrompt.trim().length > 0 && isTimeoutValid;

  const hasOllamaFeedback = Boolean(ollamaTestResult || ollamaTestError);
  const ollamaErrorMessage =
    (ollamaTestError?.detail?.message ?? ollamaTestError?.message) ?? null;
  const ollamaErrorEndpoint = ollamaTestError?.detail?.endpoint;
  const ollamaErrorOriginal = ollamaTestError?.detail?.original_error;
  const ollamaErrorReason = ollamaTestError?.detail?.reason_code ?? null;
  const ollamaErrorRetryAfterSeconds = ollamaTestError?.detail?.retry_after_seconds;
  const isOllamaLoadingModel = Boolean(ollamaTestError?.detail?.loading);
  const ollamaLoadingSinceRaw = ollamaTestError?.detail?.loading_since ?? null;
  const ollamaLoadingSince = useMemo(() => {
    if (!ollamaLoadingSinceRaw) {
      return null;
    }
    const parsed = new Date(ollamaLoadingSinceRaw);
    return Number.isNaN(parsed.getTime()) ? null : parsed;
  }, [ollamaLoadingSinceRaw]);

  const formattedRetrySeconds =
    typeof ollamaErrorRetryAfterSeconds === "number" && Number.isFinite(ollamaErrorRetryAfterSeconds)
      ? Math.max(1, Math.round(ollamaErrorRetryAfterSeconds))
      : null;
  const showOllamaRetryHint =
    ollamaErrorReason === "timeout" || ollamaErrorReason === "service_unavailable";
  const showTimeoutError = Boolean(ollamaTimeout.trim() && !isTimeoutValid);
  const isStartingOllama = ollamaStartMutation.isPending;
  const ollamaStartError = ollamaStartMutation.error ? String(ollamaStartMutation.error) : null;
  const ollamaStartResult = ollamaStartMutation.data;
  const showOllamaDetectionWarning = !ollamaStatusQuery.isLoading && !isOllamaDetected;
  const showOllamaOfflineWarning =
    !ollamaStatusQuery.isLoading && isOllamaDetected && !isOllamaRunning;

  const insightsHistory = insightsQuery.data ?? [];
  const insightsHistoryError =
    insightsQuery.error && insightsQuery.error instanceof Error
      ? insightsQuery.error.message
      : statusQuery.data?.ollama_insights_last_error ?? null;

  const showInsightsErrorBanner = Boolean(statusQuery.data?.ollama_insights_last_error);

  const insightsLastRunRaw = statusQuery.data?.ollama_insights_last_run ?? null;
  const insightsNextRunRaw = statusQuery.data?.ollama_insights_next_run ?? null;
  const insightsLastRun = insightsLastRunRaw ? new Date(insightsLastRunRaw) : null;
  const insightsNextRun = insightsNextRunRaw ? new Date(insightsNextRunRaw) : null;

  const trimmedInsightsModel = insightsModel.trim();

  const parsedInsightsFrequency = useMemo(() => {
    const raw = insightsFrequency.trim();
    if (!raw) {
      return null;
    }
    const value = Number.parseInt(raw, 10);
    return Number.isFinite(value) ? value : null;
  }, [insightsFrequency]);

  const isFrequencyValid =
    !insightsEnabled ||
    insightsFrequency.trim().length === 0 ||
    (parsedInsightsFrequency !== null &&
      parsedInsightsFrequency >= 1 &&
      parsedInsightsFrequency <= 1440);

  const originalInsightsEnabled = settings?.ollama_insights_enabled ?? false;
  const originalInsightsModel = settings?.ollama_insights_model ?? "";
  const originalInsightsFrequency =
    settings?.ollama_insights_frequency_minutes !== null &&
    settings?.ollama_insights_frequency_minutes !== undefined
      ? String(settings.ollama_insights_frequency_minutes)
      : null;
  const originalInsightsFocus = normalizeFocus(settings?.ollama_insights_focus);
  const selectedFocusOption = useMemo(
    () =>
      INSIGHT_FOCUS_OPTIONS.find((option) => option.value === insightsFocus) ??
      INSIGHT_FOCUS_OPTIONS[0],
    [insightsFocus],
  );
  const focusPromptPreview = useMemo(() => {
    const template = selectedFocusOption.prompt;
    const rootPath = settings?.root_path ?? "{root}";
    return template.replace("{root}", rootPath);
  }, [selectedFocusOption, settings?.root_path]);

  const insightsChanges: Record<string, unknown> = {};
  if (insightsEnabled !== originalInsightsEnabled) {
    insightsChanges.ollama_insights_enabled = insightsEnabled;
  }
  if (trimmedInsightsModel !== originalInsightsModel) {
    insightsChanges.ollama_insights_model = trimmedInsightsModel || null;
  }
  if (
    (parsedInsightsFrequency === null && originalInsightsFrequency !== null) ||
    (parsedInsightsFrequency !== null &&
      String(parsedInsightsFrequency) !== originalInsightsFrequency)
  ) {
    insightsChanges.ollama_insights_frequency_minutes =
      parsedInsightsFrequency !== null ? parsedInsightsFrequency : null;
  }
  if (insightsFocus !== originalInsightsFocus) {
    insightsChanges.ollama_insights_focus = insightsFocus;
  }

  const hasInsightsChanges = Object.keys(insightsChanges).length > 0;

  const insightsMutation = useMutation({
    mutationFn: updateSettings,
    onSuccess: (result) => {
      queryClient.setQueryData(queryKeys.settings, result.settings);
      queryClient.invalidateQueries({ queryKey: queryKeys.settings });
      queryClient.invalidateQueries({ queryKey: queryKeys.status });
      queryClient.invalidateQueries({ queryKey: queryKeys.stageStatus });
      queryClient.invalidateQueries({ queryKey: queryKeys.ollamaInsights(HISTORY_LIMIT) });
      setInsightsStatus(
        result.updated.length > 0
          ? `Preferences updated (${result.updated.join(", ")}).`
          : "No changes needed saving.",
      );
    },
    onError: (error: unknown) => {
      const message = error instanceof Error ? error.message : "Unknown error.";
      setInsightsStatus(`Error while saving: ${message}`);
    },
  });

  const manualInsightsMutation = useMutation({
    mutationFn: (input: ManualInsightsPayload | undefined) => triggerOllamaInsights(input),
    onSuccess: (result) => {
      const timestamp = new Date(result.generated_at).toLocaleString();
      setInsightsStatus(`Insight generated (${timestamp}).`);
      queryClient.invalidateQueries({ queryKey: queryKeys.ollamaInsights(HISTORY_LIMIT) });
      queryClient.invalidateQueries({ queryKey: queryKeys.status });
    },
    onError: (error: unknown) => {
      const message = error instanceof Error ? error.message : "Could not generate the insight.";
      setInsightsStatus(`Error generating insight: ${message}`);
    },
  });

  const clearInsightsMutation = useMutation({
    mutationFn: clearOllamaInsights,
    onSuccess: (result) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.ollamaInsights(HISTORY_LIMIT) });
      setInsightsStatus(
        result.deleted > 0
          ? `Deleted ${result.deleted} stored insights.`
          : "No insights to remove.",
      );
    },
    onError: (error: unknown) => {
      const message = error instanceof Error ? error.message : "Could not clear the history.";
      setInsightsStatus(`Error clearing history: ${message}`);
    },
  });

  const handleInsightsSave = () => {
    if (!isFrequencyValid || insightsMutation.isPending || !hasInsightsChanges) {
      return;
    }
    setInsightsStatus(null);
    insightsMutation.mutate(insightsChanges);
  };

  const handleOllamaStart = () => {
    ollamaStartMutation.mutate(
      {},
      {
        onSuccess: (data) => {
          if (!ollamaEndpointTouched && data.status.endpoint) {
            setOllamaEndpoint(data.status.endpoint);
          }
          ollamaStatusQuery.refetch();
        },
      },
    );
  };

  const quickTestModel = (selectedOllamaModel.trim() || availableOllamaModels[0] || "").trim();
  const canQuickTest = Boolean(quickTestModel) && isOllamaRunning;

  const handleQuickOllamaTest = () => {
    if (!canQuickTest || isTestingOllama || !quickTestModel) {
      return;
    }
    const endpointValue = ollamaEndpoint.trim() || undefined;
    const payload = {
      model: quickTestModel,
      prompt: QUICK_TEST_PROMPT,
      endpoint: endpointValue,
      timeout_seconds: parsedTimeout,
    };
    ollamaTestMutation.mutate(payload);
  };

  const handleOllamaTestSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!canSubmitOllamaTest) {
      return;
    }
    const payload = {
      model: selectedOllamaModel.trim(),
      prompt: ollamaPrompt.trim(),
      system_prompt: ollamaSystemPrompt.trim() || undefined,
      endpoint: ollamaEndpoint.trim() || undefined,
      timeout_seconds: parsedTimeout,
    };
    ollamaTestMutation.mutate(payload);
  };

  return (
    <div className="stage-toolkit">
      <section className="stage-section">
        <header className="stage-section-header">
          <div>
            <h2>Local Ollama</h2>
            <p>
              Manage the local Ollama service, review installed models, and start it when needed.
            </p>
          </div>
          <button
            className="secondary-btn"
            type="button"
            onClick={() => ollamaStatusQuery.refetch()}
            disabled={ollamaStatusQuery.isFetching}
          >
            {ollamaStatusQuery.isFetching ? "Checking…" : "Check again"}
          </button>
        </header>

        {ollamaStatusQuery.isLoading ? (
          <p className="stage-info">Checking Ollama status...</p>
        ) : ollamaStatusQuery.isError ? (
          <p className="stage-error">
            Could not query the Ollama status. {String(ollamaStatusQuery.error)}
          </p>
        ) : (
          <>
            <OllamaStatusCard
              status={ollamaStatus}
              lastChecked={ollamaLastChecked}
              onStart={handleOllamaStart}
              isStarting={isStartingOllama}
              startError={ollamaStartError}
              onTestConnection={handleQuickOllamaTest}
              isTestingConnection={isTestingOllama}
              canTestConnection={canQuickTest}
            />
            {ollamaStartResult ? (
              <p className="stage-meta">
                {ollamaStartResult.already_running
                  ? "Ollama was already running."
                  : `Ollama started successfully (PID ${ollamaStartResult.process_id ?? "?"}).`}
              </p>
            ) : null}
          </>
        )}
      </section>

      <section className="stage-section">
        <header className="stage-section-header">
          <div>
            <h2>Automated insights</h2>
            <p>
              Choose the model and cadence for Ollama to generate recommendations about your repository.
            </p>
          </div>
        </header>

        <article className="stage-card">
          {settingsLoading ? (
        <p className="stage-info">Loading preferences...</p>
          ) : (
            <>
              <div className="stage-form-field stage-toggle-field">
                <span>Enable insights</span>
                <label className="stage-switch">
                  <input
                    type="checkbox"
                    checked={insightsEnabled}
                    onChange={(event) => setInsightsEnabled(event.target.checked)}
                    disabled={insightsMutation.isPending}
                  />
                  <span className="stage-switch-slider" aria-hidden="true" />
                </label>
              </div>

              <div className="stage-form-field">
                <span>Analysis focus</span>
                <select
                  className="stage-select"
                  value={insightsFocus}
                  onChange={(event) => setInsightsFocus(event.target.value)}
                  disabled={insightsMutation.isPending}
                >
                  {INSIGHT_FOCUS_OPTIONS.map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
                </select>
                <p className="stage-hint">{selectedFocusOption.description}</p>
                <pre
                  className="stage-output"
                  style={{ maxHeight: 160, overflow: "auto", fontSize: "0.85rem", marginTop: 8 }}
                >
                  {focusPromptPreview}
                </pre>
              </div>

              <div className="stage-form-field">
                <span>Preferred model</span>
                <input
                  className="stage-input"
                  type="text"
                  list="ollama-insights-models"
                  value={insightsModel}
                  onChange={(event) => setInsightsModel(event.target.value)}
                  placeholder="e.g. gpt-oss:latest"
                  disabled={!insightsEnabled || insightsMutation.isPending}
                />
                <datalist id="ollama-insights-models">
                  {availableOllamaModels.map((model) => (
                    <option value={model} key={`insights-model-${model}`} />
                  ))}
                </datalist>
                <p className="stage-hint">
                  You can enter any model available in your Ollama installation.
                </p>
              </div>

              <div className="stage-form-field">
                <span>Frequency (minutes)</span>
                <input
                  className="stage-input"
                  type="number"
                  min={1}
                  max={1440}
                  value={insightsFrequency}
                  onChange={(event) => setInsightsFrequency(event.target.value)}
                  disabled={!insightsEnabled || insightsMutation.isPending}
                />
                {!isFrequencyValid ? (
                  <p className="stage-error">
                    Enter a number between 1 and 1,440 minutes or leave the field empty.
                  </p>
                ) : (
                  <p className="stage-hint">
                    Choose how often analyses run. Leave it blank to use 60 minutes by default.
                  </p>
                )}
              </div>

              <div className="stage-form-actions">
                <button
                  className="primary-btn"
                  type="button"
                  onClick={handleInsightsSave}
                  disabled={
                    insightsMutation.isPending ||
                    !hasInsightsChanges ||
                    !isFrequencyValid
                  }
                >
                  {insightsMutation.isPending ? "Saving…" : "Save preferences"}
                </button>
                <button
                  className="secondary-btn"
                  type="button"
                  onClick={() => {
                    if (!settings) {
                      return;
                    }
                    setInsightsEnabled(settings.ollama_insights_enabled);
                    setInsightsModel(settings.ollama_insights_model ?? "");
                    setInsightsFocus(normalizeFocus(settings.ollama_insights_focus));
                    setInsightsFrequency(
                      settings.ollama_insights_frequency_minutes !== null
                        ? String(settings.ollama_insights_frequency_minutes)
                        : "60",
                    );
                    setInsightsStatus("Reverted to the current values.");
                  }}
                  disabled={insightsMutation.isPending}
                >
                  Revert changes
                </button>
              </div>
              {insightsStatus ? <p className="stage-info">{insightsStatus}</p> : null}

              <div className="stage-form-field">
                <span>Recent history</span>
                {insightsQuery.isLoading ? (
                  <p className="stage-info">Retrieving generated insights...</p>
              ) : insightsQuery.isError ? (
                <p className="stage-error">
                  Error loading history: {String(insightsHistoryError)}
                </p>
              ) : showInsightsErrorBanner ? (
                <div className="stage-alert stage-alert--warn">
                  <strong>Automatic insights failed</strong>
                  <p>{statusQuery.data?.ollama_insights_last_error}</p>
                  <p className="stage-hint">
                    Ensure Ollama is running and the configured model exists, then retry.
                  </p>
                  <button
                    className="secondary-btn"
                    type="button"
                    onClick={() =>
                      manualInsightsMutation.mutate({
                        model:
                          statusQuery.data?.ollama_insights_last_model || insightsModel || "",
                        focus: insightsFocus,
                      })
                    }
                    disabled={manualInsightsMutation.isPending}
                  >
                      {manualInsightsMutation.isPending ? "Retrying..." : "Retry now"}
                  </button>
                </div>
              ) : insightsHistory.length === 0 ? (
                <p className="stage-hint">
                  No insights recorded yet. Generate one manually or wait for the next automatic run.
                  </p>
              ) : (
                  <ul className="stage-list stage-insights-list">
                    {insightsHistory.map((entry) => (
                      <li key={entry.id}>
                        <strong>{entry.model}</strong>
                        <span> · {new Date(entry.generated_at).toLocaleString()}</span>
                        <p className="stage-insight-message">{entry.message}</p>
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              <div className="stage-form-actions">
                <button
                  className="secondary-btn"
                  type="button"
                  onClick={() => {
                    manualInsightsMutation.mutate({
                      model: trimmedInsightsModel || undefined,
                      focus: insightsFocus,
                    });
                  }}
                  disabled={manualInsightsMutation.isPending}
                >
                  {manualInsightsMutation.isPending ? "Generating…" : "Generate now"}
                </button>
                <button
                  className="secondary-btn"
                  type="button"
                  onClick={() => clearInsightsMutation.mutate()}
                  disabled={clearInsightsMutation.isPending}
                >
                  {clearInsightsMutation.isPending ? "Clearing…" : "Clear history"}
                </button>
                {insightsLastRun ? (
                  <p className="stage-hint">
                    Last run: {insightsLastRun.toLocaleString()}
                    {insightsNextRun ? ` · Next estimated: ${insightsNextRun.toLocaleString()}` : ""}
                  </p>
                ) : (
                  <p className="stage-hint">No automated insights have run yet.</p>
                )}
              </div>
            </>
          )}
        </article>
      </section>

      <section className="stage-section">
        <header className="stage-section-header">
          <div>
            <h2>Manual message</h2>
            <p>
              Send any ad-hoc prompt to the local model, review the response, and inspect latency or errors.
            </p>
          </div>
        </header>

        {showOllamaDetectionWarning ? (
          <p className="stage-info">
            We have not detected an Ollama installation yet. If it lives in another path, adjust the endpoint field and test anyway.
          </p>
        ) : null}
        {showOllamaOfflineWarning ? (
          <p className="stage-error">
            Ollama is installed but the endpoint <code>{ollamaEndpointHint}</code> did not respond.
            Try starting it with the button above or launch it manually.
          </p>
        ) : null}

        <form className="stage-form" onSubmit={handleOllamaTestSubmit}>
          <label className="stage-form-field">
            <span>Model</span>
            {availableOllamaModels.length > 0 ? (
              <select
                className="stage-select"
                value={selectedOllamaModel}
                onChange={(event) => setSelectedOllamaModel(event.target.value)}
                disabled={isTestingOllama}
              >
                {availableOllamaModels.map((model) => (
                  <option key={model} value={model}>
                    {model}
                  </option>
                ))}
              </select>
            ) : (
              <input
                className="stage-input"
                type="text"
                value={selectedOllamaModel}
                placeholder="Type the model name (e.g. llama3)"
                onChange={(event) => setSelectedOllamaModel(event.target.value)}
                disabled={isTestingOllama}
              />
            )}
          </label>

          <label className="stage-form-field">
            <span>Endpoint (optional)</span>
            <input
              className="stage-input"
              type="text"
              value={ollamaEndpoint}
              placeholder={ollamaEndpointHint}
              onChange={(event) => {
                setOllamaEndpoint(event.target.value);
                setOllamaEndpointTouched(true);
              }}
              disabled={isTestingOllama}
              aria-label="Ollama endpoint"
            />
            <p className="stage-hint">
              Leave the field blank to reuse the automatically detected endpoint.
            </p>
          </label>

          <label className="stage-form-field">
            <span>Maximum response time (seconds)</span>
            <input
              className="stage-input"
              type="number"
              min={1}
              max={1200}
              step={0.5}
              value={ollamaTimeout}
              onChange={(event) => setOllamaTimeout(event.target.value)}
              disabled={isTestingOllama}
              aria-label="Maximum wait time for the response"
            />
            {showTimeoutError ? (
              <p className="stage-error">
                Enter a value between 1 and 1,200 seconds or leave the field empty.
              </p>
            ) : (
              <p className="stage-hint">
                Leaving it blank uses the default ({parsedTimeout ?? 180} s). Use this limit to avoid long waits.
              </p>
            )}
          </label>

          <label className="stage-form-field">
            <span>System prompt (optional)</span>
            <textarea
              className="stage-textarea"
              value={ollamaSystemPrompt}
              onChange={(event) => setOllamaSystemPrompt(event.target.value)}
              placeholder="Additional context to guide the response."
              disabled={isTestingOllama}
            />
          </label>

          <label className="stage-form-field">
            <span>Message</span>
            <textarea
              className="stage-textarea"
              value={ollamaPrompt}
              onChange={(event) => setOllamaPrompt(event.target.value)}
              minLength={4}
              disabled={isTestingOllama}
              required
            />
            <p className="stage-hint">
              Great for manual debugging or quick follow-up prompts. Automated insights remain available above.
            </p>
          </label>

          <div className="stage-form-actions">
            <button className="primary-btn" type="submit" disabled={!canSubmitOllamaTest || isTestingOllama}>
              {isTestingOllama ? "Sending…" : "Send message"}
            </button>
            <button
              className="secondary-btn"
              type="button"
              onClick={() => {
                setOllamaPrompt(DEFAULT_PROMPT);
                setOllamaSystemPrompt("");
                setOllamaEndpoint("");
                setOllamaEndpointTouched(false);
                setOllamaTimeout("180");
              }}
              disabled={isTestingOllama}
            >
              Reset form
            </button>
          </div>
        </form>

        {hasOllamaFeedback ? (
          <article className="stage-card">
            <header>
              <h3>Result</h3>
              {ollamaTestResult ? (
                <span className="stage-badge success">{formatLatency(ollamaTestResult.latency_ms)}</span>
              ) : null}
            </header>
            {ollamaTestError ? (
              <>
                <p className="stage-error">{ollamaErrorMessage ?? "The test failed."}</p>
                {ollamaErrorEndpoint ? (
                  <p className="stage-meta">
                    Endpoint: <code>{ollamaErrorEndpoint}</code>
                  </p>
                ) : null}
                {ollamaErrorOriginal ? (
                  <p className="stage-meta">Detalle: {ollamaErrorOriginal}</p>
                ) : null}
                {isOllamaLoadingModel ? (
                  <p className="stage-info">
                    The model appears to still be loading
                    {ollamaLoadingSince ? <> since {ollamaLoadingSince.toLocaleTimeString()}</> : null}.
                    Try again
                    {formattedRetrySeconds ? <> in ~{formattedRetrySeconds} s</> : " in a few seconds"} or inspect the logs with{" "}
                    <code>ollama serve</code>.
                </p>
                ) : null}
                {!isOllamaLoadingModel && showOllamaRetryHint ? (
                  <p className="stage-info">
                    Ollama suggested retrying soon
                    {formattedRetrySeconds ? <> (≈{formattedRetrySeconds} s)</> : ""}. If it takes too long, open a terminal and watch{" "}
                    <code>ollama serve</code>.
                </p>
                ) : null}
              </>
            ) : null}

            {ollamaTestResult ? (
              <>
                <p className="stage-meta">
                  Endpoint: <code>{ollamaTestResult.endpoint}</code>
                </p>
                <section>
                  <h4>Mensaje</h4>
                  <pre className="stage-output">{ollamaTestResult.message}</pre>
                </section>
                <details className="stage-details">
                  <summary>View full JSON</summary>
                  <pre className="stage-output">
                    {JSON.stringify(ollamaTestResult.raw, null, 2)}
                  </pre>
                </details>
              </>
            ) : null}
          </article>
        ) : null}
      </section>
    </div>
  );
}
