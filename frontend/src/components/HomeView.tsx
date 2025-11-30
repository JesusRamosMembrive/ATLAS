import { Link } from "react-router-dom";
import type { UseQueryResult } from "@tanstack/react-query";

import type { StageDetectionStatus, StatusPayload } from "../api/types";
import { useStageStatusQuery } from "../hooks/useStageStatusQuery";
import { TiltCard } from "./TiltCard";

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
          <div className="home-hero__badges">
            <span className="home-version-pill">v1.0.0</span>
            <span className={`home-stage-pill ${detectionTone}`}>
              {stageStatusQuery.isLoading ? "Calculating…" : detectionLabel}
            </span>
          </div>
          <h2>ATLAS: Control Your Code, Guide Your Agents</h2>
          <p className="home-hero__acronym">
            Agent Tooling, Linting And Source-mapping
          </p>
          <p>
            Unified control center for code analysis, linting, and AI agent orchestration. Trace dependencies, monitor quality, execute commands remotely, and leverage local AI for contextual insights—all in one place.
          </p>
          <div className="home-hero__credits">
            <span>Programmed by Jesús Ramos Membrive</span>
            <a
              href="https://github.com/JesusRamosMembrive/ATLAS"
              target="_blank"
              rel="noreferrer"
            >
              github.com/JesusRamosMembrive/ATLAS
            </a>
          </div>
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

            {/* Partículas orbitando - círculo exterior (r=70) */}
            <g className="orbit orbit--slow">
              <circle cx="170" cy="100" r="2.5" fill="#60a5fa" opacity="0.8" />
            </g>
            <g className="orbit orbit--slow-reverse">
              <circle cx="30" cy="100" r="2" fill="#2dd4bf" opacity="0.7" />
            </g>

            {/* Partículas orbitando - círculo medio (r=55) */}
            <g className="orbit orbit--medium">
              <circle cx="155" cy="100" r="2" fill="#34d399" opacity="0.7" />
            </g>
            <g className="orbit orbit--medium-reverse">
              <circle cx="45" cy="100" r="1.5" fill="#5eead4" opacity="0.6" />
            </g>

            {/* Partículas extra para más dinamismo */}
            <g className="orbit orbit--fast">
              <circle cx="140" cy="100" r="1.5" fill="#a5b4fc" opacity="0.5" />
            </g>
          </svg>
        </div>
      </section>

      <section className="home-card-grid">
        <TiltCard to="/stage-toolkit">
          <div className="home-card-body">
            <h3>Project Stage Toolkit</h3>
            <p>
              Run <code>init_project.py</code>, validate the files required by Claude Code and Codex
              CLI, and review the detected project stage.
            </p>
          </div>
          <span className="home-card-cta">Open toolkit →</span>
        </TiltCard>

        <TiltCard to="/overview">
          <div className="home-card-body">
            <h3>Overview</h3>
            <p>
              Review detections, alerts, and recent activity from a single dashboard before diving
              deeper.
            </p>
          </div>
          <span className="home-card-cta">Open overview →</span>
        </TiltCard>

        <TiltCard to="/code-map">
          <div className="home-card-body">
            <h3>Code Analysis</h3>
            <p>
              Browse symbols, semantic search, and recent repository activity—ideal for exploring
              the code with context.
            </p>
          </div>
          <span className="home-card-cta">Open Analysis →</span>
        </TiltCard>

        <TiltCard to="/docs">
          <div className="home-card-body">
            <h3>Docs</h3>
            <p>
              Inspect every markdown file under <code>docs/</code>, keep architecture notes handy,
              and preview content without leaving ATLAS.
            </p>
          </div>
          <span className="home-card-cta">Open Docs →</span>
        </TiltCard>

        <TiltCard to="/class-uml">
          <div className="home-card-body">
            <h3>Class UML</h3>
            <p>
              UML diagrams with class attributes and methods—perfect for understanding internals
              without extra noise.
            </p>
          </div>
          <span className="home-card-cta">View UML →</span>
        </TiltCard>

        <TiltCard to="/timeline">
          <div className="home-card-body">
            <h3>Code Timeline</h3>
            <p>
              DAW-style visualization of git history. See which files changed together over time—perfect for understanding code evolution.
            </p>
          </div>
          <span className="home-card-cta">Open Timeline →</span>
        </TiltCard>

        <TiltCard to="/terminal">
          <div className="home-card-body">
            <h3>Remote Terminal</h3>
            <p>
              Full shell access from your browser. Execute commands, navigate directories, and manage your system remotely with a real bash/zsh terminal.
            </p>
          </div>
          <span className="home-card-cta">Open Terminal →</span>
        </TiltCard>

        <TiltCard to="/agent">
          <div className="home-card-body">
            <h3>Claude Agent</h3>
            <p>
              Interact with Claude Code through a structured UI. Send prompts, see tool calls and results in real-time without TUI rendering issues.
            </p>
          </div>
          <span className="home-card-cta">Open Agent →</span>
        </TiltCard>

        <TiltCard to="/linters">
          <div className="home-card-body">
            <h3>Linters</h3>
            <p>
              Check configured linter status, latest results, and logs to maintain code quality.
            </p>
          </div>
          <span className="home-card-cta">View linters →</span>
        </TiltCard>

        <TiltCard to="/ollama">
          <div className="home-card-body">
            <h3>Ollama Insights</h3>
            <p>
              Configure models, generate insights, and monitor scheduled runs for automated guidance.
            </p>
          </div>
          <span className="home-card-cta">Open Ollama →</span>
        </TiltCard>

        <TiltCard to="/prompts">
          <div className="home-card-body">
            <h3>Prompts</h3>
            <p>
              Explore reusable prompt templates to guide agents and capture team best practices.
            </p>
          </div>
          <span className="home-card-cta">Open Prompts →</span>
        </TiltCard>

        <TiltCard to="/settings">
          <div className="home-card-body">
            <h3>Settings</h3>
            <p>
              Configure project paths, automation toggles, and integrations to match your workflow.
            </p>
          </div>
          <span className="home-card-cta">Open Settings →</span>
        </TiltCard>
      </section>
    </div>
  );
}
