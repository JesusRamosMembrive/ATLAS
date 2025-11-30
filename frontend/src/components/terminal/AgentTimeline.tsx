/**
 * Agent Timeline Component
 *
 * Displays a vertical timeline of agent events with states and timestamps
 */

import { useEffect, useRef } from "react";
import { TimelineEntry, AgentEventType, EVENT_ICONS, PHASE_COLORS } from "../../types/agent";

interface AgentTimelineProps {
  events: TimelineEntry[];
  autoScroll?: boolean;
  onEventClick?: (eventId: string) => void;
  selectedEventId?: string | null;
  maxHeight?: string;
}

export function AgentTimeline({
  events,
  autoScroll = true,
  onEventClick,
  selectedEventId,
  maxHeight = "400px",
}: AgentTimelineProps) {
  const timelineRef = useRef<HTMLDivElement>(null);
  const endRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom when new events arrive
  useEffect(() => {
    if (autoScroll && endRef.current) {
      endRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [events.length, autoScroll]);

  // Group events by phase for visual separation
  const groupedEvents = groupEventsByPhase(events);

  return (
    <div className="agent-timeline" ref={timelineRef} style={{ maxHeight, overflowY: "auto" }}>
      {groupedEvents.map((group, groupIdx) => (
        <div key={groupIdx} className="agent-timeline__group">
          {/* Phase header */}
          <div
            className="agent-timeline__phase"
            style={{ borderLeftColor: PHASE_COLORS[group.phase] || "#gray" }}
          >
            <div className="agent-timeline__phase-dot"
                 style={{ backgroundColor: PHASE_COLORS[group.phase] || "#gray" }} />
            <div className="agent-timeline__phase-name">
              {getPhaseName(group.phase)}
            </div>
            <div className="agent-timeline__phase-duration">
              {formatPhaseDuration(group.startTime, group.endTime)}
            </div>
          </div>

          {/* Events in this phase */}
          {group.events.map((event, idx) => {
            const eventId = `${event.timestamp}-${idx}`;
            const isSelected = selectedEventId === eventId;
            const icon = EVENT_ICONS[event.type as AgentEventType] || "•";

            return (
              <div
                key={idx}
                className={`agent-timeline__event ${isSelected ? "agent-timeline__event--selected" : ""}`}
                onClick={() => onEventClick?.(eventId)}
              >
                <div className="agent-timeline__event-time">
                  {formatTime(event.timestamp)}
                </div>
                <div className="agent-timeline__event-icon" title={event.type}>
                  {icon}
                </div>
                <div className="agent-timeline__event-content">
                  <div className="agent-timeline__event-description">
                    {event.description}
                  </div>
                  {isSelected && event.data && (
                    <div className="agent-timeline__event-details">
                      <pre>{JSON.stringify(event.data, null, 2)}</pre>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      ))}
      <div ref={endRef} />
    </div>
  );
}

// Helper functions

interface EventGroup {
  phase: string;
  events: TimelineEntry[];
  startTime: string;
  endTime?: string;
}

function groupEventsByPhase(events: TimelineEntry[]): EventGroup[] {
  const groups: EventGroup[] = [];
  let currentGroup: EventGroup | null = null;

  events.forEach((event) => {
    if (!currentGroup || currentGroup.phase !== event.phase) {
      // Start new group
      if (currentGroup) {
        currentGroup.endTime = event.timestamp;
      }
      currentGroup = {
        phase: event.phase,
        events: [event],
        startTime: event.timestamp,
      };
      groups.push(currentGroup);
    } else {
      // Add to current group
      currentGroup.events.push(event);
    }
  });

  return groups;
}

function getPhaseName(phase: string): string {
  const names: Record<string, string> = {
    idle: "Idle",
    thinking: "Thinking",
    planning: "Planning",
    executing: "Executing",
    verifying: "Verifying",
    testing: "Testing",
    building: "Building",
    installing: "Installing",
  };
  return names[phase] || phase;
}

function formatTime(timestamp: string): string {
  const date = new Date(timestamp);
  return date.toLocaleTimeString("en-US", {
    hour12: false,
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

function formatPhaseDuration(start: string, end?: string): string {
  const startTime = new Date(start).getTime();
  const endTime = end ? new Date(end).getTime() : Date.now();
  const duration = (endTime - startTime) / 1000; // seconds

  if (duration < 1) {
    return `${Math.round(duration * 1000)}ms`;
  } else if (duration < 60) {
    return `${duration.toFixed(1)}s`;
  } else {
    const mins = Math.floor(duration / 60);
    const secs = Math.floor(duration % 60);
    return `${mins}m ${secs}s`;
  }
}