import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import type {
  AgentInstallStatus,
  DocsStatus,
  StageAgentSelection,
  StageDetectionStatus,
} from "../api/types";
import { useStageInitMutation } from "../hooks/useStageInitMutation";
import { useStageStatusQuery } from "../hooks/useStageStatusQuery";
import { useSuperClaudeInstallMutation } from "../hooks/useSuperClaudeInstallMutation";

type LoadingStep = "preparing" | "running" | "verifying";

const LOADING_STEPS: { key: LoadingStep; label: string }[] = [
  { key: "preparing", label: "Preparing" },
  { key: "running", label: "Running" },
  { key: "verifying", label: "Verifying" },
];

function LoadingOverlay({
  title,
  subtitle,
  currentStep,
}: {
  title: string;
  subtitle?: string;
  currentStep?: LoadingStep;
}): JSX.Element {
  return (
    <div className="stage-loading-overlay">
      <div className="stage-spinner" />
      <div className="stage-loading-text">
        {title}
        {subtitle && <div className="stage-loading-subtext">{subtitle}</div>}
      </div>
      {currentStep && (
        <div className="stage-loading-steps">
          {LOADING_STEPS.map((step) => {
            const stepIndex = LOADING_STEPS.findIndex((s) => s.key === step.key);
            const currentIndex = LOADING_STEPS.findIndex((s) => s.key === currentStep);
            const isCompleted = stepIndex < currentIndex;
            const isActive = step.key === currentStep;

            return (
              <div
                key={step.key}
                className={`stage-loading-step ${isActive ? "active" : ""} ${isCompleted ? "completed" : ""}`}
              >
                {isCompleted && (
                  <svg className="stage-loading-step-icon" viewBox="0 0 20 20" fill="currentColor">
                    <path
                      fillRule="evenodd"
                      d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z"
                      clipRule="evenodd"
                    />
                  </svg>
                )}
                {step.label}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

const AGENT_OPTIONS: { value: StageAgentSelection; label: string }[] = [
  { value: "all", label: "All (Claude + Codex + Gemini)" },
  { value: "both", label: "Claude + Codex" },
  { value: "claude", label: "Claude only" },
  { value: "codex", label: "Codex only" },
  { value: "gemini", label: "Gemini only" },
];

const SUPERCLAUDE_REFERENCE_COUNTS = {
  plugin_commands: 3,
  specialist_agents: 16,
  behavior_modes: 7,
  mcp_servers: 8,
} as const;

type SuperClaudeStatKey = keyof typeof SUPERCLAUDE_REFERENCE_COUNTS;

const SUPERCLAUDE_LABELS: Record<SuperClaudeStatKey, string> = {
  plugin_commands: "Comandos del plugin",
  specialist_agents: "Agentes especializados",
  behavior_modes: "Modos conductuales",
  mcp_servers: "Servidores MCP",
};

function formatList(values: string[]): JSX.Element {
  if (values.length === 0) {
    return <em>—</em>;
  }

  return (
    <ul className="stage-list">
      {values.map((item) => (
        <li key={item}>{item}</li>
      ))}
    </ul>
  );
}

function AgentStatusCard({
  title,
  status,
}: {
  title: string;
  status: AgentInstallStatus | undefined;
}): JSX.Element {
  if (!status) {
    return (
      <article className="stage-card">
        <header>
          <h3>{title}</h3>
        </header>
        <p>Unable to retrieve status.</p>
      </article>
    );
  }

  const badgeClass = status.installed ? "stage-badge success" : "stage-badge warn";
  const badgeLabel = status.installed ? "Installed" : "Missing items";

  return (
    <article className="stage-card">
      <header>
        <h3>{title}</h3>
        <span className={badgeClass}>{badgeLabel}</span>
      </header>
      <section>
        <h4>Present files</h4>
        {formatList(status.present)}
      </section>
      <section>
        <h4>Missing files</h4>
        {formatList(status.missing)}
      </section>
      {status.optional && status.optional.expected.length > 0 ? (
        <section>
          <h4>Optional files</h4>
          {status.optional.missing.length === 0 ? (
            <p className="stage-optional">All optional files are present.</p>
          ) : (
            <>
              <p className="stage-optional">
                Recommended optional files that are not strictly required:
              </p>
              {formatList(status.optional.missing)}
            </>
          )}
        </section>
      ) : null}
    </article>
  );
}

function DocsStatusCard({ status }: { status: DocsStatus | undefined }): JSX.Element {
  if (!status) {
    return (
      <article className="stage-card">
        <header>
          <h3>Documentation</h3>
        </header>
        <p>Could not inspect the docs/ folder.</p>
      </article>
    );
  }
  const badgeClass = status.complete ? "stage-badge success" : "stage-badge warn";
  const badgeLabel = status.complete ? "Complete" : "Missing files";

  return (
    <article className="stage-card">
      <header>
        <h3>Documentation</h3>
        <span className={badgeClass}>{badgeLabel}</span>
      </header>
      <section>
        <h4>Present</h4>
        {formatList(status.present)}
      </section>
      <section>
        <h4>Missing</h4>
        {formatList(status.missing)}
      </section>
    </article>
  );
}

function StageDetectionCard({ detection }: { detection: StageDetectionStatus | undefined }) {
  if (!detection) {
    return null;
  }
  const { available, recommended_stage, confidence, reasons, metrics, error, checked_at } = detection;

  if (!available) {
    return (
      <article className="stage-card">
        <header>
          <h3>Stage detection</h3>
          <span className="stage-badge warn">Unavailable</span>
        </header>
        <p>{error ?? "The project stage could not be evaluated."}</p>
      </article>
    );
  }

  return (
    <article className="stage-card stage-detection">
      <header>
        <h3>Stage detection</h3>
        <span className="stage-badge success">
          Stage {recommended_stage} · {confidence?.toUpperCase() ?? "N/A"}
        </span>
      </header>
      {checked_at ? (
        <p className="stage-meta">Last check: {new Date(checked_at).toLocaleString()}</p>
      ) : null}
      <section>
        <h4>Key reasons</h4>
        {formatList(reasons)}
      </section>
      {metrics ? (
        <section>
          <h4>Metrics</h4>
          <dl className="stage-metrics">
            {Object.entries(metrics).map(([key, value]) => (
              <div key={key}>
                <dt>{key}</dt>
                <dd>{Array.isArray(value) ? value.join(", ") : String(value)}</dd>
              </div>
            ))}
          </dl>
        </section>
      ) : null}
    </article>
  );
}

export function StageToolkitView(): JSX.Element {
  const statusQuery = useStageStatusQuery();
  const initMutation = useStageInitMutation();
  const superClaudeMutation = useSuperClaudeInstallMutation();

  const [selection, setSelection] = useState<StageAgentSelection>("all");
  const [forceReset, setForceReset] = useState(false);
  const [initStep, setInitStep] = useState<LoadingStep>("preparing");
  const [superClaudeStep, setSuperClaudeStep] = useState<LoadingStep>("preparing");

  const stageStatus = statusQuery.data;
  const initResult = initMutation.data;
  const superClaudeResult = superClaudeMutation.data;

  const stdout = initResult?.stdout?.trim();
  const stderr = initResult?.stderr?.trim();

  const mutationError = initMutation.error ? String(initMutation.error) : null;
  const superClaudeError = superClaudeMutation.error
    ? String(superClaudeMutation.error.message || superClaudeMutation.error)
    : null;

  // Simulate step progression for init mutation
  useEffect(() => {
    if (initMutation.isPending) {
      setInitStep("preparing");
      const runningTimer = setTimeout(() => setInitStep("running"), 500);
      const verifyingTimer = setTimeout(() => setInitStep("verifying"), 3000);
      return () => {
        clearTimeout(runningTimer);
        clearTimeout(verifyingTimer);
      };
    }
  }, [initMutation.isPending]);

  // Simulate step progression for SuperClaude mutation
  useEffect(() => {
    if (superClaudeMutation.isPending) {
      setSuperClaudeStep("preparing");
      const runningTimer = setTimeout(() => setSuperClaudeStep("running"), 500);
      const verifyingTimer = setTimeout(() => setSuperClaudeStep("verifying"), 4000);
      return () => {
        clearTimeout(runningTimer);
        clearTimeout(verifyingTimer);
      };
    }
  }, [superClaudeMutation.isPending]);

  const currentAgentLabel = useMemo(
    () => AGENT_OPTIONS.find((option) => option.value === selection)?.label ?? "All agents",
    [selection],
  );

  const superClaudeCounts = useMemo(() => {
    const keys = Object.keys(SUPERCLAUDE_REFERENCE_COUNTS) as SuperClaudeStatKey[];
    return keys.reduce<Record<SuperClaudeStatKey, number>>((acc, key) => {
      const currentValue = superClaudeResult?.component_counts?.[key];
      acc[key] = typeof currentValue === "number" ? currentValue : SUPERCLAUDE_REFERENCE_COUNTS[key];
      return acc;
    }, {} as Record<SuperClaudeStatKey, number>);
  }, [superClaudeResult?.component_counts]);

  const handleStageInit = () => {
    initMutation.mutate({ agents: selection, force: forceReset });
  };

  const handleSuperClaudeInstall = () => {
    superClaudeMutation.mutate();
  };

  return (
    <div className="stage-toolkit">
      <section className="stage-section">
        <header className="stage-section-header">
          <div>
            <h2>Stage-Aware project status</h2>
            <p>
              Check whether the key files for Claude Code and Codex CLI are present in the current
              workspace.
            </p>
          </div>
          <button
            className="secondary-btn"
            type="button"
            onClick={() => statusQuery.refetch()}
            disabled={statusQuery.isFetching}
          >
            {statusQuery.isFetching ? "Checking…" : "Check again"}
          </button>
        </header>

        {statusQuery.isLoading ? (
          <p className="stage-info">Loading status…</p>
        ) : statusQuery.isError ? (
          <p className="stage-error">
            Could not fetch status. {String(statusQuery.error)}
          </p>
        ) : (
          <div className="stage-status-grid">
            <AgentStatusCard title="Claude Code" status={stageStatus?.claude} />
            <AgentStatusCard title="Codex CLI" status={stageStatus?.codex} />
            <AgentStatusCard title="Gemini CLI" status={stageStatus?.gemini} />
            <DocsStatusCard status={stageStatus?.docs} />
          </div>
        )}
      </section>

      <section className="stage-section">
        <header className="stage-section-header">
          <div>
            <h2>Ollama and recommendations</h2>
            <p>
              Ollama service configuration and the insight history now live on a dedicated page.
            </p>
          </div>
        </header>

        <article className="stage-card">
          <p>
            Visit the <Link to="/ollama">Ollama</Link> tab to start the server, test models, and
            manage automatically generated recommendations.
          </p>
          <p className="stage-hint">
            From there you can adjust the model and cadence, launch manual analyses, and review the
            latest insights.
          </p>
        </article>
      </section>

      <section className="stage-section">
        {initMutation.isPending && (
          <LoadingOverlay
            title="Initializing Stage-Aware Framework"
            subtitle={`Installing ${currentAgentLabel} configuration...`}
            currentStep={initStep}
          />
        )}
        <header className="stage-section-header">
          <div>
            <h2>Initialize or reinstall instructions</h2>
            <p>
              Run <code>init_project.py --existing</code> (optionally add <code>--dry-run</code> to
              simulate) against the current workspace with the selected agents.
            </p>
          </div>
        </header>

        <div className="stage-actions">
          <label className="stage-radio-group-title" htmlFor="agent-selection">
            Agents
          </label>
          <div className="stage-radio-group" id="agent-selection">
            {AGENT_OPTIONS.map((option) => (
              <label key={option.value} className="stage-radio">
                <input
                  type="radio"
                  name="agent"
                  value={option.value}
                  checked={selection === option.value}
                  onChange={() => setSelection(option.value)}
                  disabled={initMutation.isPending}
                />
                <span>{option.label}</span>
              </label>
            ))}
          </div>

          <label className="stage-checkbox">
            <input
              type="checkbox"
              checked={forceReset}
              onChange={(e) => setForceReset(e.target.checked)}
              disabled={initMutation.isPending}
            />
            <span>Force reset (clean install, overwrite existing files)</span>
          </label>

          <div className="stage-button-group">
            <button
              className="primary-btn"
              type="button"
              onClick={handleStageInit}
              disabled={initMutation.isPending}
            >
              {initMutation.isPending ? "Running…" : `Initialize (${currentAgentLabel})`}
            </button>
            {forceReset && (
              <span className="stage-warning-text">
                ⚠️ This will overwrite existing configuration files
              </span>
            )}
          </div>
        </div>

        {mutationError ? <p className="stage-error">{mutationError}</p> : null}
      </section>

      <section className="stage-section">
        {superClaudeMutation.isPending && (
          <LoadingOverlay
            title="Installing SuperClaude Framework"
            subtitle="Cloning repository and syncing assets..."
            currentStep={superClaudeStep}
          />
        )}
        <header className="stage-section-header">
          <div>
            <h2>Frameworks y extensiones</h2>
            <p>
              Instala frameworks y skills para potenciar tus agentes de Claude Code.
            </p>
          </div>
        </header>

        <div className="stage-frameworks-grid">
          <article className="stage-card">
            <header>
              <h3>SuperClaude Framework</h3>
            </header>
            <p>
              Comandos <code>/sc</code>, 16 agentes especializados, 7 modos y 8 servidores MCP.
            </p>
            <dl className="stage-metrics">
              {(Object.keys(SUPERCLAUDE_REFERENCE_COUNTS) as SuperClaudeStatKey[]).map((key) => (
                <div key={key}>
                  <dt>{SUPERCLAUDE_LABELS[key]}</dt>
                  <dd>{superClaudeCounts[key]}</dd>
                </div>
              ))}
            </dl>

            <div className="stage-actions">
              <button
                className="primary-btn"
                type="button"
                onClick={handleSuperClaudeInstall}
                disabled={superClaudeMutation.isPending}
              >
                {superClaudeMutation.isPending ? "Instalando…" : "Instalar"}
              </button>
              <a
                className="secondary-btn"
                href="https://github.com/SuperClaude-Org/SuperClaude_Framework"
                target="_blank"
                rel="noreferrer"
              >
                Repositorio
              </a>
            </div>

            {superClaudeError ? <p className="stage-error">{superClaudeError}</p> : null}

            {superClaudeResult ? (
              <div>
                {superClaudeResult.installed_at ? (
                  <p className="stage-meta">
                    Instalado: {new Date(superClaudeResult.installed_at).toLocaleString()}
                  </p>
                ) : null}
                {superClaudeResult.source_commit ? (
                  <p className="stage-meta">
                    Commit: <code>{superClaudeResult.source_commit.slice(0, 12)}</code>
                  </p>
                ) : null}

                {superClaudeResult.copied_paths.length > 0 ? (
                  <details className="stage-log-details">
                    <summary>Rutas sincronizadas ({superClaudeResult.copied_paths.length})</summary>
                    <ul className="stage-list">
                      {superClaudeResult.copied_paths.map((path) => (
                        <li key={path}>
                          <code>{path}</code>
                        </li>
                      ))}
                    </ul>
                  </details>
                ) : (
                  <p className="stage-hint">
                    Activos en <code>.claude/</code> y <code>docs/superclaude</code>.
                  </p>
                )}

                {superClaudeResult.logs.length > 0 ? (
                  <details className="stage-log-details">
                    <summary>Ver registro ({superClaudeResult.logs.length})</summary>
                    <div className="stage-log-entries">
                      {superClaudeResult.logs.map((log, index) => {
                        const stdout = log.stdout.trim();
                        const stderr = log.stderr.trim();
                        return (
                          <div key={`${log.command.join(" ")}-${index}`} className="stage-log-entry">
                            <p>
                              <code>{log.command.join(" ")}</code>{" "}
                              <span className={`stage-badge ${log.exit_code === 0 ? "success" : "warn"}`}>
                                {log.exit_code === 0 ? "OK" : `Exit ${log.exit_code}`}
                              </span>
                            </p>
                            {stdout ? <pre className="stage-output">{stdout}</pre> : null}
                            {stderr ? <pre className="stage-output error">{stderr}</pre> : null}
                          </div>
                        );
                      })}
                    </div>
                  </details>
                ) : null}
              </div>
            ) : (
              <p className="stage-hint">
                Instala agentes, modos y servidores MCP recomendados.
              </p>
            )}
          </article>

          <article className="stage-card">
            <header>
              <h3>Awesome Claude Skills</h3>
            </header>
            <p>
              Coleccion de skills de la comunidad para Claude Code por{" "}
              <a href="https://composio.dev" target="_blank" rel="noreferrer">Composio</a>.
            </p>
            <dl className="stage-metrics">
              <div>
                <dt>Skills disponibles</dt>
                <dd>50+</dd>
              </div>
              <div>
                <dt>Categorias</dt>
                <dd>PDF, Excel, APIs...</dd>
              </div>
            </dl>

            <div className="stage-actions">
              <a
                className="primary-btn"
                href="https://github.com/ComposioHQ/awesome-claude-skills"
                target="_blank"
                rel="noreferrer"
              >
                Ver Skills
              </a>
            </div>

            <p className="stage-hint">
              <strong>Instalacion:</strong><br />
              Linux/macOS: <code>~/.config/claude-code/skills/</code><br />
              Windows: <code>%APPDATA%\claude-code\skills\</code>
            </p>
          </article>
        </div>
      </section>

      <section className="stage-section">
        {statusQuery.isLoading ? (
          <p className="stage-info">Calculating stage detection…</p>
        ) : stageStatus ? (
          <StageDetectionCard detection={stageStatus.detection} />
        ) : (
          <p className="stage-info">Unable to retrieve project status.</p>
        )}
      </section>

      {initResult ? (
        <section className="stage-section">
          <header className="stage-section-header">
            <div>
              <h2>init_project.py output</h2>
              <p>
                Command: <code>{initResult.command.join(" ")}</code>
              </p>
            </div>
          </header>
          {stdout ? (
            <pre className="stage-output">{stdout}</pre>
          ) : (
            <p className="stage-info">No stdout output.</p>
          )}
          {stderr ? <pre className="stage-output error">{stderr}</pre> : null}
        </section>
      ) : null}
    </div>
  );
}
