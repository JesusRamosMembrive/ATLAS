import { useMemo } from "react";
import type { AuditEvent } from "../api/types";

interface TimelineViewProps {
  /** Events to build timeline from */
  events: AuditEvent[];
}

interface PhaseBlock {
  phase: string;
  startTime: Date;
  endTime: Date | null;
  duration: number; // milliseconds
  status: "running" | "ok" | "error";
  events: AuditEvent[];
}

/**
 * Timeline visualization component (Gantt-style)
 *
 * Displays workflow phases as horizontal bars showing:
 * - Phase start and end times
 * - Duration of each phase
 * - Current status (running, completed, error)
 * - Events within each phase
 *
 * Phases are extracted from events with type="phase" or from event.phase field.
 */
export function TimelineView({ events }: TimelineViewProps) {
  const { phases, totalDuration, earliestStart } = useMemo(() => {
    return buildPhaseBlocks(events);
  }, [events]);

  if (phases.length === 0) {
    return (
      <div className="timeline-empty">
        <p className="timeline-empty-message">
          No phases detected yet. Phases will appear here as the agent works.
        </p>
      </div>
    );
  }

  return (
    <div className="timeline-view">
      <div className="timeline-header">
        <h3>Workflow Timeline</h3>
        <span className="timeline-total-duration">
          Total: {formatDuration(totalDuration)}
        </span>
      </div>

      <div className="timeline-phases">
        {phases.map((phase, index) => (
          <PhaseBar
            key={`${phase.phase}-${index}`}
            phase={phase}
            totalDuration={totalDuration}
            offset={phase.startTime.getTime() - earliestStart.getTime()}
          />
        ))}
      </div>

      <div className="timeline-legend">
        <div className="timeline-legend-item">
          <span className="timeline-legend-dot phase-plan" />
          Plan
        </div>
        <div className="timeline-legend-item">
          <span className="timeline-legend-dot phase-apply" />
          Apply
        </div>
        <div className="timeline-legend-item">
          <span className="timeline-legend-dot phase-validate" />
          Validate
        </div>
        <div className="timeline-legend-item">
          <span className="timeline-legend-dot phase-explore" />
          Explore
        </div>
      </div>
    </div>
  );
}

interface PhaseBarProps {
  phase: PhaseBlock;
  totalDuration: number;
  offset: number;
}

function PhaseBar({ phase, totalDuration, offset }: PhaseBarProps) {
  const widthPercent = (phase.duration / totalDuration) * 100;
  const offsetPercent = (offset / totalDuration) * 100;

  const phaseClass = `phase-${phase.phase}`;
  const statusClass = `status-${phase.status}`;

  return (
    <div className="timeline-phase-row">
      <div className="timeline-phase-label">
        <span className={`timeline-phase-name ${phaseClass}`}>
          {phase.phase.toUpperCase()}
        </span>
        <span className="timeline-phase-duration">
          {formatDuration(phase.duration)}
        </span>
      </div>

      <div className="timeline-phase-track">
        <div
          className={`timeline-phase-bar ${phaseClass} ${statusClass}`}
          style={{
            width: `${widthPercent}%`,
            marginLeft: `${offsetPercent}%`,
          }}
          title={`${phase.phase}: ${formatDuration(phase.duration)} (${phase.events.length} events)`}
        >
          <div className="timeline-phase-bar-content">
            {phase.status === "running" && (
              <span className="timeline-phase-pulse">●</span>
            )}
            {phase.status === "error" && (
              <span className="timeline-phase-error-icon">✗</span>
            )}
            <span className="timeline-phase-event-count">{phase.events.length}</span>
          </div>
        </div>
      </div>
    </div>
  );
}

/**
 * Build phase blocks from events
 */
function buildPhaseBlocks(events: AuditEvent[]): {
  phases: PhaseBlock[];
  totalDuration: number;
  earliestStart: Date;
} {
  const phaseMap = new Map<string, PhaseBlock>();
  let earliestStart: Date | null = null;
  let latestEnd: Date | null = null;

  // Group events by phase
  events.forEach(event => {
    const eventTime = new Date(event.created_at);

    if (!earliestStart || eventTime < earliestStart) {
      earliestStart = eventTime;
    }

    // Handle explicit phase events (type="phase")
    if (event.type === "phase") {
      const phaseName = (event.payload?.phase_name as string) || event.phase || "unknown";

      if (event.status === "running") {
        // Phase start
        phaseMap.set(phaseName, {
          phase: phaseName,
          startTime: eventTime,
          endTime: null,
          duration: 0,
          status: "running",
          events: [event],
        });
      } else {
        // Phase end
        const existing = phaseMap.get(phaseName);
        if (existing) {
          existing.endTime = eventTime;
          existing.duration =
            (event.payload?.duration_ms as number) || eventTime.getTime() - existing.startTime.getTime();
          existing.status = event.status as "ok" | "error";
          existing.events.push(event);

          if (!latestEnd || eventTime > latestEnd) {
            latestEnd = eventTime;
          }
        }
      }
    } else if (event.phase) {
      // Events with phase field - add to corresponding phase
      const existing = phaseMap.get(event.phase);
      if (existing) {
        existing.events.push(event);
        // Update end time if this event is later
        if (!existing.endTime || eventTime > existing.endTime) {
          existing.endTime = eventTime;
          existing.duration = eventTime.getTime() - existing.startTime.getTime();
        }
      } else {
        // Create implicit phase from event
        phaseMap.set(event.phase, {
          phase: event.phase,
          startTime: eventTime,
          endTime: eventTime,
          duration: 0,
          status: "ok",
          events: [event],
        });
      }

      if (!latestEnd || eventTime > latestEnd) {
        latestEnd = eventTime;
      }
    }
  });

  // Convert to array and sort by start time
  const phases = Array.from(phaseMap.values()).sort(
    (a, b) => a.startTime.getTime() - b.startTime.getTime()
  );

  // Calculate total duration
  const totalDuration =
    earliestStart && latestEnd
      ? (latestEnd as Date).getTime() - (earliestStart as Date).getTime()
      : phases.reduce((sum, p) => sum + p.duration, 0);

  // Update running phases to current time
  const now = new Date();
  phases.forEach(phase => {
    if (phase.status === "running" && !phase.endTime) {
      phase.duration = now.getTime() - phase.startTime.getTime();
    }
  });

  return {
    phases,
    totalDuration: Math.max(totalDuration, 1000), // Minimum 1 second for display
    earliestStart: earliestStart || new Date(),
  };
}

/**
 * Format duration in human-readable form
 */
function formatDuration(ms: number): string {
  if (ms < 1000) {
    return `${Math.round(ms)}ms`;
  }

  const seconds = ms / 1000;

  if (seconds < 60) {
    return `${seconds.toFixed(1)}s`;
  }

  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = Math.floor(seconds % 60);

  if (minutes < 60) {
    return `${minutes}m ${remainingSeconds}s`;
  }

  const hours = Math.floor(minutes / 60);
  const remainingMinutes = minutes % 60;

  return `${hours}h ${remainingMinutes}m`;
}
