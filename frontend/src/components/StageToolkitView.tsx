import { useMemo, useState } from "react";
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

const AGENT_OPTIONS: { value: StageAgentSelection; label: string }[] = [
  { value: "both", label: "Claude + Codex" },
  { value: "claude", label: "Claude only" },
  { value: "codex", label: "Codex only" },
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

  const [selection, setSelection] = useState<StageAgentSelection>("both");

  const stageStatus = statusQuery.data;
  const initResult = initMutation.data;
  const superClaudeResult = superClaudeMutation.data;

  const stdout = initResult?.stdout?.trim();
  const stderr = initResult?.stderr?.trim();

  const mutationError = initMutation.error ? String(initMutation.error) : null;
  const superClaudeError = superClaudeMutation.error
    ? String(superClaudeMutation.error.message || superClaudeMutation.error)
    : null;

  const currentAgentLabel = useMemo(
    () => AGENT_OPTIONS.find((option) => option.value === selection)?.label ?? "Claude + Codex",
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
    initMutation.mutate({ agents: selection });
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
          <button
            className="primary-btn"
            type="button"
            onClick={handleStageInit}
            disabled={initMutation.isPending}
          >
            {initMutation.isPending ? "Running…" : `Initialize (${currentAgentLabel})`}
          </button>
        </div>

        {mutationError ? <p className="stage-error">{mutationError}</p> : null}
      </section>

      <section className="stage-section">
        <header className="stage-section-header">
          <div>
            <h2>SuperClaude Framework</h2>
            <p>
              Sincroniza los comandos <code>/sc</code>, 16 agentes especializados, 7 modos y 8 servidores
              MCP recomendados directamente desde la{" "}
              <a
                href="https://github.com/SuperClaude-Org/SuperClaude_Framework"
                target="_blank"
                rel="noreferrer"
              >
                distribución oficial
              </a>
              .
            </p>
          </div>
        </header>

        <article className="stage-card">
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
              {superClaudeMutation.isPending ? "Instalando…" : "Instalar SuperClaude"}
            </button>
            <a
              className="secondary-btn"
              href="https://github.com/SuperClaude-Org/SuperClaude_Framework"
              target="_blank"
              rel="noreferrer"
            >
              Abrir repositorio
            </a>
          </div>

          {superClaudeError ? <p className="stage-error">{superClaudeError}</p> : null}

          {superClaudeResult ? (
            <div>
              {superClaudeResult.installed_at ? (
                <p className="stage-meta">
                  Última ejecución: {new Date(superClaudeResult.installed_at).toLocaleString()}
                </p>
              ) : null}
              {superClaudeResult.source_commit ? (
                <p className="stage-meta">
                  Commit: <code>{superClaudeResult.source_commit.slice(0, 12)}</code>
                </p>
              ) : null}

              {superClaudeResult.copied_paths.length > 0 ? (
                <>
                  <h4>Rutas sincronizadas</h4>
                  <ul className="stage-list">
                    {superClaudeResult.copied_paths.map((path) => (
                      <li key={path}>
                        <code>{path}</code>
                      </li>
                    ))}
                  </ul>
                </>
              ) : (
                <p className="stage-hint">
                  Los activos ya están disponibles en <code>.claude/</code> y <code>docs/superclaude</code>.
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
              Ejecuta el instalador para copiar los agentes, modos y servidores MCP recomendados.
            </p>
          )}
        </article>
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
