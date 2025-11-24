import { Link } from "react-router-dom";
import type { UseQueryResult } from "@tanstack/react-query";

import type { StageDetectionStatus, StatusPayload } from "../api/types";
import { useStageStatusQuery } from "../hooks/useStageStatusQuery";

function detectionBadgeLabel(detection?: StageDetectionStatus): string {
  if (!detection) {
    return "Loading detection…";
  }
  if (!detection.available) {
    return detection.error ?? "Detection unavailable";
  }
  const stage = detection.recommended_stage ?? "?";
  const confidence = detection.confidence ? detection.confidence.toUpperCase() : "NO CONF.";
  return `Stage ${stage} · ${confidence}`;
}

export function HomeView({
  statusQuery,
}: {
  statusQuery: UseQueryResult<StatusPayload>;
}): JSX.Element {
  const stageStatusQuery = useStageStatusQuery();

  const detection = stageStatusQuery.data?.detection;
  const detectionAvailable = detection?.available ?? false;

  const detectionTone = detectionAvailable ? "success" : "warn";
  const detectionLabel = detectionBadgeLabel(detection);
  const backendOffline =
    statusQuery.isError || (!statusQuery.isFetching && !statusQuery.data && !statusQuery.isLoading);
  const executableUrl = "https://github.com/jesusramon/atlas/releases/latest";

  return (
    <div className="home-view">
      {backendOffline && (
        <div className="home-alert home-alert--error" role="alert">
          <div className="home-alert__text">
            <strong>ATLAS Backend offline.</strong>
            <span>
              Start the local server or download the packaged executable for ATLAS.
            </span>
          </div>
          <a
            className="home-alert__cta"
            href={executableUrl}
            target="_blank"
            rel="noreferrer"
          >
            Download executable →
          </a>
        </div>
      )}
      <section className="home-hero">
        <div className="home-hero__glow" aria-hidden />
        <div className="home-hero__content">
          <span className={`home-stage-pill ${detectionTone}`}>
            {stageStatusQuery.isLoading ? "Calculating…" : detectionLabel}
          </span>
          <h2>ATLAS: Navigate Your Codebase with Precision</h2>
          <p>
            Automated Tracing, Linting And Source-mapping. Define shared standards, monitor code quality with integrated linters, trace function calls across files, and rely on local AI for contextual insights.
          </p>
        </div>
        <div className="home-hero__logo">
          <svg viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
            {/* Círculo exterior con gradiente */}
            <defs>
              <linearGradient id="logoGradient1" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" style={{ stopColor: "#3b82f6", stopOpacity: 0.4 }} />
                <stop offset="100%" style={{ stopColor: "#2dd4bf", stopOpacity: 0.9 }} />
              </linearGradient>
              <linearGradient id="logoGradient2" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" style={{ stopColor: "#60a5fa", stopOpacity: 1 }} />
                <stop offset="100%" style={{ stopColor: "#34d399", stopOpacity: 1 }} />
              </linearGradient>
              <filter id="glow">
                <feGaussianBlur stdDeviation="5" result="coloredBlur" />
                <feMerge>
                  <feMergeNode in="coloredBlur" />
                  <feMergeNode in="SourceGraphic" />
                </feMerge>
              </filter>
            </defs>

            {/* Círculo de fondo */}
            <circle cx="100" cy="100" r="85" fill="url(#logoGradient1)" opacity="0.2" />

            {/* Anillos concéntricos */}
            <circle cx="100" cy="100" r="70" fill="none" stroke="url(#logoGradient2)" strokeWidth="2" opacity="0.4" />
            <circle cx="100" cy="100" r="55" fill="none" stroke="url(#logoGradient2)" strokeWidth="2" opacity="0.6" />

            {/* Símbolo central - diseño de código/árbol de decisiones */}
            <g filter="url(#glow)">
              {/* Nodo central */}
              <circle cx="100" cy="100" r="8" fill="#60a5fa" />

              {/* Ramas superiores */}
              <line x1="100" y1="100" x2="70" y2="70" stroke="#60a5fa" strokeWidth="3" strokeLinecap="round" />
              <line x1="100" y1="100" x2="130" y2="70" stroke="#60a5fa" strokeWidth="3" strokeLinecap="round" />
              <circle cx="70" cy="70" r="6" fill="#34d399" />
              <circle cx="130" cy="70" r="6" fill="#34d399" />

              {/* Ramas inferiores */}
              <line x1="100" y1="100" x2="70" y2="130" stroke="#60a5fa" strokeWidth="3" strokeLinecap="round" />
              <line x1="100" y1="100" x2="130" y2="130" stroke="#60a5fa" strokeWidth="3" strokeLinecap="round" />
              <circle cx="70" cy="130" r="6" fill="#2dd4bf" />
              <circle cx="130" cy="130" r="6" fill="#2dd4bf" />

              {/* Subramas */}
              <line x1="70" y1="70" x2="50" y2="50" stroke="#34d399" strokeWidth="2" strokeLinecap="round" opacity="0.8" />
              <line x1="130" y1="70" x2="150" y2="50" stroke="#34d399" strokeWidth="2" strokeLinecap="round" opacity="0.8" />
              <circle cx="50" cy="50" r="4" fill="#5eead4" />
              <circle cx="150" cy="50" r="4" fill="#5eead4" />
            </g>

            {/* Partículas decorativas */}
            <circle cx="40" cy="100" r="2" fill="#60a5fa" opacity="0.6" />
            <circle cx="160" cy="100" r="2" fill="#2dd4bf" opacity="0.6" />
            <circle cx="100" cy="40" r="2" fill="#34d399" opacity="0.5" />
            <circle cx="100" cy="160" r="2" fill="#5eead4" opacity="0.5" />
          </svg>
        </div>
      </section>

      <section className="home-card-grid">
        <Link to="/stage-toolkit" className="home-card">
          <div className="home-card-body">
            <h3>Project Stage Toolkit</h3>
            <p>
              Run <code>init_project.py</code>, validate the files required by Claude Code and Codex
              CLI, and review the detected project stage.
            </p>
          </div>
          <span className="home-card-cta">Open toolkit →</span>
        </Link>

        <Link to="/overview" className="home-card">
          <div className="home-card-body">
            <h3>Overview</h3>
            <p>
              Review detections, alerts, and recent activity from a single dashboard before diving
              deeper.
            </p>
          </div>
          <span className="home-card-cta">Open overview →</span>
        </Link>

        <Link to="/code-map" className="home-card">
          <div className="home-card-body">
            <h3>Code Analysis</h3>
            <p>
              Browse symbols, semantic search, and recent repository activity—ideal for exploring
              the code with context.
            </p>
          </div>
          <span className="home-card-cta">Open Analysis →</span>
        </Link>

        <Link to="/docs" className="home-card">
          <div className="home-card-body">
            <h3>Docs</h3>
            <p>
              Inspect every markdown file under <code>docs/</code>, keep architecture notes handy,
              and preview content without leaving ATLAS.
            </p>
          </div>
          <span className="home-card-cta">Open Docs →</span>
        </Link>

        <Link to="/class-uml" className="home-card">
          <div className="home-card-body">
            <h3>Class UML</h3>
            <p>
              UML diagrams with class attributes and methods—perfect for understanding internals
              without extra noise.
            </p>
          </div>
          <span className="home-card-cta">View UML →</span>
        </Link>

        <Link to="/timeline" className="home-card">
          <div className="home-card-body">
            <h3>Code Timeline</h3>
            <p>
              DAW-style visualization of git history. See which files changed together over time—perfect for understanding code evolution.
            </p>
          </div>
          <span className="home-card-cta">Open Timeline →</span>
        </Link>

        <Link to="/terminal" className="home-card">
          <div className="home-card-body">
            <h3>Remote Terminal</h3>
            <p>
              Full shell access from your browser. Execute commands, navigate directories, and manage your system remotely with a real bash/zsh terminal.
            </p>
          </div>
          <span className="home-card-cta">Open Terminal →</span>
        </Link>

        <Link to="/linters" className="home-card">
          <div className="home-card-body">
            <h3>Linters</h3>
            <p>
              Check configured linter status, latest results, and logs to maintain code quality.
            </p>
          </div>
          <span className="home-card-cta">View linters →</span>
        </Link>

        <Link to="/ollama" className="home-card">
          <div className="home-card-body">
            <h3>Ollama Insights</h3>
            <p>
              Configure models, generate insights, and monitor scheduled runs for automated guidance.
            </p>
          </div>
          <span className="home-card-cta">Open Ollama →</span>
        </Link>

        <Link to="/prompts" className="home-card">
          <div className="home-card-body">
            <h3>Prompts</h3>
            <p>
              Explore reusable prompt templates to guide agents and capture team best practices.
            </p>
          </div>
          <span className="home-card-cta">Open Prompts →</span>
        </Link>

        <Link to="/settings" className="home-card">
          <div className="home-card-body">
            <h3>Settings</h3>
            <p>
              Configure project paths, automation toggles, and integrations to match your workflow.
            </p>
          </div>
          <span className="home-card-cta">Open Settings →</span>
        </Link>
      </section>
    </div>
  );
}
