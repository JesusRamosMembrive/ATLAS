import { useEffect, useMemo, useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  appendAuditEvent,
  closeAuditRun,
  createAuditRun,
  getAuditEvents,
  listAuditRuns,
} from "../api/client";
import { queryKeys } from "../api/queryKeys";
import type { AuditEvent, AuditRun } from "../api/types";
import { useAuditEventStream } from "../hooks/useAuditEventStream";

const EVENT_TYPE_LABELS: Record<string, string> = {
  intent: "Intent",
  plan: "Plan",
  command: "Command",
  command_result: "Result",
  diff: "Diff",
  test: "Test",
  note: "Note",
};

const DEFAULT_EVENT_LIMIT = 200;

function formatRelative(dateString?: string | null): string {
  if (!dateString) return "just now";
  const date = new Date(dateString);
  const diff = Date.now() - date.getTime();
  const minutes = Math.max(0, Math.floor(diff / 60000));
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function formatDate(dateString?: string | null): string {
  if (!dateString) return "";
  return new Date(dateString).toLocaleString();
}

function statusBadge(status?: string | null): string {
  if (!status) return "neutral";
  const normalized = status.toLowerCase();
  if (normalized.startsWith("error") || normalized === "fail") return "danger";
  if (normalized === "closed" || normalized === "done") return "muted";
  if (normalized === "pending") return "warning";
  return "success";
}

function summarizePayload(payload?: Record<string, unknown> | null): string | null {
  if (!payload) return null;
  const serialized = JSON.stringify(payload, null, 2);
  if (serialized.length <= 800) {
    return serialized;
  }
  return `${serialized.slice(0, 800)}…`;
}

function RunCard({
  run,
  isSelected,
  onSelect,
}: {
  run: AuditRun;
  isSelected: boolean;
  onSelect: (id: number) => void;
}): JSX.Element {
  const badgeClass = `audit-badge status-${statusBadge(run.status)}`;
  const closedInfo = run.closed_at ? ` · closed ${formatRelative(run.closed_at)}` : "";
  return (
    <button
      type="button"
      className={`audit-run-card${isSelected ? " selected" : ""}`}
      onClick={() => onSelect(run.id)}
    >
      <div className="audit-run-header">
        <span className={badgeClass}>{run.status}</span>
        <span className="audit-run-time">{formatRelative(run.created_at)}</span>
      </div>
      <div className="audit-run-title">{run.name || `Run ${run.id}`}</div>
      <div className="audit-run-meta">
        <span>{run.event_count} events</span>
        {run.root_path ? <code className="audit-run-path">{run.root_path}</code> : null}
      </div>
      {closedInfo ? <div className="audit-run-closed">{closedInfo}</div> : null}
    </button>
  );
}

function EventCard({ event }: { event: AuditEvent }): JSX.Element {
  const typeLabel = EVENT_TYPE_LABELS[event.type] ?? event.type;
  const payload = summarizePayload(event.payload);
  const badgeClass = `audit-badge status-${statusBadge(event.status)}`;

  return (
    <article className="audit-event-card">
      <header className="audit-event-header">
        <div className="audit-event-tags">
          <span className="audit-badge subtle">{typeLabel}</span>
          {event.status ? <span className={badgeClass}>{event.status}</span> : null}
          {event.phase ? <span className="audit-chip">{event.phase}</span> : null}
          {event.actor ? <span className="audit-chip muted">{event.actor}</span> : null}
          {event.ref ? <code className="audit-ref">{event.ref}</code> : null}
        </div>
        <span className="audit-event-time">{formatRelative(event.created_at)}</span>
      </header>
      <div className="audit-event-title">{event.title}</div>
      {event.detail ? <pre className="audit-event-detail">{event.detail}</pre> : null}
      {payload ? <pre className="audit-event-payload">{payload}</pre> : null}
    </article>
  );
}

export function AuditSessionsView(): JSX.Element {
  const queryClient = useQueryClient();
  const [selectedRunId, setSelectedRunId] = useState<number | null>(null);
  const [runName, setRunName] = useState("");
  const [runNotes, setRunNotes] = useState("");
  const [eventType, setEventType] = useState("note");
  const [eventTitle, setEventTitle] = useState("");
  const [eventDetail, setEventDetail] = useState("");
  const [eventActor, setEventActor] = useState("human");
  const [eventPhase, setEventPhase] = useState("");
  const [eventStatus, setEventStatus] = useState("");
  const [eventRef, setEventRef] = useState("");
  const [typeFilter, setTypeFilter] = useState<string>("all");

  const runsQuery = useQuery({
    queryKey: queryKeys.auditRuns(30),
    queryFn: () => listAuditRuns(30),
    refetchInterval: 5000,
  });

  useEffect(() => {
    if (selectedRunId || !runsQuery.data?.runs?.length) {
      return;
    }
    setSelectedRunId(runsQuery.data.runs[0]?.id ?? null);
  }, [runsQuery.data?.runs, selectedRunId]);

  const selectedRun = useMemo(
    () => runsQuery.data?.runs.find((run) => run.id === selectedRunId),
    [runsQuery.data?.runs, selectedRunId]
  );

  const eventsQuery = useQuery({
    queryKey: selectedRunId
      ? queryKeys.auditEvents(selectedRunId, DEFAULT_EVENT_LIMIT)
      : ["audit", "events", "none"],
    queryFn: () =>
      selectedRunId
        ? getAuditEvents(selectedRunId, { limit: DEFAULT_EVENT_LIMIT })
        : Promise.resolve({ events: [] }),
    enabled: Boolean(selectedRunId),
    // No polling - using SSE instead
  });

  // Real-time event streaming via SSE
  const { isConnected: sseConnected, error: sseError } = useAuditEventStream(
    selectedRunId,
    Boolean(selectedRunId)
  );

  const createRunMutation = useMutation({
    mutationFn: createAuditRun,
    onSuccess: (run) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.auditRuns(30) });
      setSelectedRunId(run.id);
      setRunName("");
      setRunNotes("");
    },
  });

  const appendEventMutation = useMutation({
    mutationFn: (payload: Parameters<typeof appendAuditEvent>[1]) => {
      if (!selectedRunId) {
        return Promise.reject(new Error("No run selected"));
      }
      return appendAuditEvent(selectedRunId, payload);
    },
    onSuccess: () => {
      if (selectedRunId) {
        queryClient.invalidateQueries({
          queryKey: queryKeys.auditEvents(selectedRunId, DEFAULT_EVENT_LIMIT),
        });
      }
      queryClient.invalidateQueries({ queryKey: queryKeys.auditRuns(30) });
      setEventTitle("");
      setEventDetail("");
      setEventRef("");
    },
  });

  const closeRunMutation = useMutation({
    mutationFn: (runId: number) => closeAuditRun(runId, { status: "closed" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.auditRuns(30) });
      if (selectedRunId) {
        queryClient.invalidateQueries({ queryKey: queryKeys.auditRun(selectedRunId) });
      }
    },
  });

  const filteredEvents = useMemo(() => {
    const events = eventsQuery.data?.events ?? [];
    if (typeFilter === "all") return events;
    return events.filter((event) => event.type === typeFilter);
  }, [eventsQuery.data?.events, typeFilter]);

  const handleCreateRun = (event: FormEvent) => {
    event.preventDefault();
    createRunMutation.mutate({
      name: runName.trim() || undefined,
      notes: runNotes.trim() || undefined,
    });
  };

  const handleAppendEvent = (event: FormEvent) => {
    event.preventDefault();
    if (!selectedRunId || !eventTitle.trim()) {
      return;
    }
    appendEventMutation.mutate({
      type: eventType,
      title: eventTitle.trim(),
      detail: eventDetail.trim() || undefined,
      actor: eventActor.trim() || undefined,
      phase: eventPhase.trim() || undefined,
      status: eventStatus.trim() || undefined,
      ref: eventRef.trim() || undefined,
    });
  };

  return (
    <div className="audit-page">
      <section className="audit-hero">
        <div>
          <p className="audit-eyebrow">Pair programming auditable</p>
          <h1>Track every agent move in one place</h1>
          <p className="audit-subtitle">
            Spin up a run, stream commands/diffs/tests, and export a timeline your boss can audit.
            Keeps intent → actions → results together so you always know what the agent changed.
          </p>
        </div>
        <div className="audit-hero-meta">
          <span className="audit-badge subtle">Live timeline</span>
          <span className="audit-badge subtle">Commands &amp; diffs</span>
          <span className="audit-badge subtle">Human approvals</span>
        </div>
      </section>

      <div className="audit-grid">
        <section className="audit-column audit-runs">
          <header className="audit-section-header">
            <div>
              <p className="audit-eyebrow">Sessions</p>
              <h2>Runs</h2>
            </div>
            <span className="audit-muted">
              {runsQuery.data?.runs.length ?? 0} stored
            </span>
          </header>

          <form className="audit-card audit-form" onSubmit={handleCreateRun}>
            <div className="audit-field">
              <label htmlFor="run-name">Run name</label>
              <input
                id="run-name"
                className="audit-input"
                placeholder="Implement checkout flow"
                value={runName}
                onChange={(e) => setRunName(e.target.value)}
              />
            </div>
            <div className="audit-field">
              <label htmlFor="run-notes">Goal / notes</label>
              <textarea
                id="run-notes"
                className="audit-textarea"
                placeholder="What should this session accomplish?"
                value={runNotes}
                onChange={(e) => setRunNotes(e.target.value)}
                rows={3}
              />
            </div>
            <div className="audit-actions">
              <button className="primary-btn" type="submit" disabled={createRunMutation.isPending}>
                {createRunMutation.isPending ? "Starting…" : "Start run"}
              </button>
            </div>
          </form>

          <div className="audit-runs-list">
            {runsQuery.isLoading ? (
              <p className="audit-muted">Loading runs…</p>
            ) : runsQuery.data?.runs.length ? (
              runsQuery.data.runs.map((run) => (
                <RunCard
                  key={run.id}
                  run={run}
                  isSelected={selectedRunId === run.id}
                  onSelect={setSelectedRunId}
                />
              ))
            ) : (
              <p className="audit-muted">No runs yet. Create one to start tracking.</p>
            )}
          </div>
        </section>

        <section className="audit-column audit-timeline">
          <header className="audit-section-header">
            <div>
              <p className="audit-eyebrow">Timeline</p>
              <h2>{selectedRun?.name || "Select a run"}</h2>
            </div>
            {selectedRun ? (
              <div className="audit-run-meta-inline">
                <span className={`audit-badge status-${statusBadge(selectedRun.status)}`}>
                  {selectedRun.status}
                </span>
                <span className="audit-muted">Started {formatDate(selectedRun.created_at)}</span>
                {selectedRun.closed_at ? (
                  <span className="audit-muted">Closed {formatDate(selectedRun.closed_at)}</span>
                ) : null}
              </div>
            ) : null}
          </header>

          {selectedRun ? (
            <>
              <div className="audit-card audit-run-overview">
                <div className="audit-overview-row">
                  <div>
                    <p className="audit-muted">Root</p>
                    <code className="audit-run-path">
                      {selectedRun.root_path ?? "not set"}
                    </code>
                  </div>
                  <div>
                    <p className="audit-muted">Events</p>
                    <strong>{selectedRun.event_count}</strong>
                  </div>
                  <div>
                    <p className="audit-muted">Status</p>
                    <span className={`audit-badge status-${statusBadge(selectedRun.status)}`}>
                      {selectedRun.status}
                    </span>
                  </div>
                  <div className="audit-actions">
                    <button
                      className="secondary-btn"
                      type="button"
                      onClick={() => selectedRun && closeRunMutation.mutate(selectedRun.id)}
                      disabled={closeRunMutation.isPending || selectedRun.status === "closed"}
                    >
                      {closeRunMutation.isPending ? "Closing…" : "Close run"}
                    </button>
                  </div>
                </div>
                {selectedRun.notes ? (
                  <p className="audit-notes">{selectedRun.notes}</p>
                ) : null}
              </div>

              <form className="audit-card audit-form" onSubmit={handleAppendEvent}>
                <div className="audit-form-grid">
                  <div className="audit-field">
                    <label htmlFor="event-type">Type</label>
                    <select
                      id="event-type"
                      className="audit-input"
                      value={eventType}
                      onChange={(e) => setEventType(e.target.value)}
                    >
                      {Object.keys(EVENT_TYPE_LABELS).map((type) => (
                        <option key={type} value={type}>
                          {EVENT_TYPE_LABELS[type]}
                        </option>
                      ))}
                    </select>
                  </div>
                  <div className="audit-field">
                    <label htmlFor="event-actor">Actor</label>
                    <input
                      id="event-actor"
                      className="audit-input"
                      placeholder="agent or human"
                      value={eventActor}
                      onChange={(e) => setEventActor(e.target.value)}
                    />
                  </div>
                  <div className="audit-field">
                    <label htmlFor="event-phase">Phase</label>
                    <input
                      id="event-phase"
                      className="audit-input"
                      placeholder="plan / apply / validate"
                      value={eventPhase}
                      onChange={(e) => setEventPhase(e.target.value)}
                    />
                  </div>
                  <div className="audit-field">
                    <label htmlFor="event-status">Status</label>
                    <input
                      id="event-status"
                      className="audit-input"
                      placeholder="ok / error / pending"
                      value={eventStatus}
                      onChange={(e) => setEventStatus(e.target.value)}
                    />
                  </div>
                  <div className="audit-field">
                    <label htmlFor="event-ref">Ref</label>
                    <input
                      id="event-ref"
                      className="audit-input"
                      placeholder="file or resource (optional)"
                      value={eventRef}
                      onChange={(e) => setEventRef(e.target.value)}
                    />
                  </div>
                </div>

                <div className="audit-field">
                  <label htmlFor="event-title">Title</label>
                  <input
                    id="event-title"
                    className="audit-input"
                    placeholder="e.g. Run tests or Apply patch"
                    value={eventTitle}
                    onChange={(e) => setEventTitle(e.target.value)}
                    required
                  />
                </div>
                <div className="audit-field">
                  <label htmlFor="event-detail">Detail</label>
                  <textarea
                    id="event-detail"
                    className="audit-textarea"
                    placeholder="stdout, summary of diff, or reasoning"
                    value={eventDetail}
                    onChange={(e) => setEventDetail(e.target.value)}
                    rows={3}
                  />
                </div>
                <div className="audit-actions">
                  <button
                    className="primary-btn"
                    type="submit"
                    disabled={appendEventMutation.isPending || !eventTitle.trim()}
                  >
                    {appendEventMutation.isPending ? "Recording…" : "Record event"}
                  </button>
                </div>
              </form>

              <div className="audit-filter-row">
                <div className="audit-filter-chips">
                  {["all", ...Object.keys(EVENT_TYPE_LABELS)].map((type) => (
                    <button
                      key={type}
                      type="button"
                      className={`audit-chip${typeFilter === type ? " active" : ""}`}
                      onClick={() => setTypeFilter(type)}
                    >
                      {type === "all" ? "All" : EVENT_TYPE_LABELS[type] ?? type}
                    </button>
                  ))}
                </div>
                <div className="audit-connection-status">
                  {sseConnected ? (
                    <span className="audit-badge status-success">
                      🟢 Live
                    </span>
                  ) : sseError ? (
                    <span className="audit-badge status-warning" title={sseError}>
                      🟡 Reconnecting
                    </span>
                  ) : null}
                  <span className="audit-muted">
                    {filteredEvents.length} events
                  </span>
                </div>
              </div>

              <div className="audit-events">
                {eventsQuery.isLoading ? (
                  <p className="audit-muted">Loading timeline…</p>
                ) : filteredEvents.length ? (
                  filteredEvents.map((event) => <EventCard key={event.id} event={event} />)
                ) : (
                  <p className="audit-muted">No events yet for this run.</p>
                )}
              </div>
            </>
          ) : (
            <div className="audit-card">
              <p className="audit-muted">Select or start a run to see its timeline.</p>
            </div>
          )}
        </section>
      </div>
    </div>
  );
}
