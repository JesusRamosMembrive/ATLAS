/**
 * Agent Store for Terminal Overlay
 *
 * Manages agent session state, events, and metrics
 * using Zustand for state management.
 */

import { create } from "zustand";
import { devtools, subscribeWithSelector } from "zustand/middleware";
import {
  AgentEvent,
  AgentEventType,
  AgentSessionState,
  CommandExecution,
  FileChange,
  TestRun,
  TimelineEntry,
  SessionSummary,
  AgentMetrics,
} from "../types/agent";

interface AgentStore {
  // State
  enabled: boolean;
  sessionState: AgentSessionState | null;
  timeline: TimelineEntry[];
  eventHistory: AgentEvent[];
  maxEvents: number;

  // Actions
  enableAgentParsing: () => void;
  disableAgentParsing: () => void;
  processAgentEvent: (event: AgentEvent) => void;
  updateSessionSummary: (summary: SessionSummary) => void;
  clearSession: () => void;
  setMaxEvents: (max: number) => void;

  // Getters
  getCurrentCommand: () => CommandExecution | undefined;
  getCurrentTestRun: () => TestRun | undefined;
  getRecentFiles: (count?: number) => FileChange[];
  getErrorCount: () => number;
  getTestSummary: () => { total: number; passed: number; failed: number; success_rate: number };
  getSessionDuration: () => number;
  getPhaseHistory: () => Array<{ phase: string; timestamp: string }>;
}

export const useAgentStore = create<AgentStore>()(
  devtools(
    subscribeWithSelector((set, get) => ({
      // Initial state
      enabled: false,
      sessionState: null,
      timeline: [],
      eventHistory: [],
      maxEvents: 1000, // Limit event history to prevent memory issues

      // Enable agent parsing
      enableAgentParsing: () =>
        set((state) => {
          // Initialize session state if not exists
          const sessionState: AgentSessionState = state.sessionState || {
            session_id: `session_${Date.now()}`,
            start_time: new Date().toISOString(),
            current_phase: "idle",
            commands: [],
            file_changes: [],
            test_runs: [],
            events: [],
            metrics: {
              total_commands: 0,
              total_events: 0,
              total_files_changed: 0,
              total_test_runs: 0,
              session_duration: 0,
              current_phase: "idle",
              error_count: 0,
              warning_count: 0,
            },
          };

          return {
            enabled: true,
            sessionState,
            timeline: [],
            eventHistory: [],
          };
        }),

      // Disable agent parsing
      disableAgentParsing: () =>
        set({
          enabled: false,
        }),

      // Process incoming agent event
      processAgentEvent: (event: AgentEvent) =>
        set((state) => {
          if (!state.sessionState) return state;

          const newState = { ...state.sessionState };
          const newTimeline = [...state.timeline];
          const newEventHistory = [...state.eventHistory, event];

          // Limit event history
          if (newEventHistory.length > state.maxEvents) {
            newEventHistory.splice(0, newEventHistory.length - state.maxEvents);
          }

          // Add to event history
          newState.events.push(event);

          // Update timeline
          newTimeline.push({
            timestamp: event.timestamp,
            type: event.type,
            description: getEventDescription(event),
            data: event.data,
            phase: newState.current_phase,
          });

          // Process event based on type
          switch (event.type) {
            case AgentEventType.COMMAND_START:
              const command: CommandExecution = {
                command: event.data.command || "",
                start_time: event.timestamp,
                output_lines: [],
                events: [event],
                status: "running",
              };
              newState.commands.push(command);
              newState.current_command = command;
              newState.current_phase = "executing";
              break;

            case AgentEventType.COMMAND_END:
              if (newState.current_command) {
                newState.current_command.end_time = event.timestamp;
                newState.current_command.exit_code = event.data.exit_code || 0;
                newState.current_command.status =
                  event.data.exit_code === 0 ? "completed" : "failed";

                // Calculate duration
                const startTime = new Date(newState.current_command.start_time).getTime();
                const endTime = new Date(event.timestamp).getTime();
                newState.current_command.duration_seconds = (endTime - startTime) / 1000;

                newState.current_command = undefined;
              }
              break;

            case AgentEventType.FILE_READ:
            case AgentEventType.FILE_WRITE:
            case AgentEventType.FILE_DELETE:
              const operationMap = {
                [AgentEventType.FILE_READ]: "read",
                [AgentEventType.FILE_WRITE]: "write",
                [AgentEventType.FILE_DELETE]: "delete",
              } as const;

              const files = event.data.files || [event.data.file];
              for (const file of files) {
                if (file) {
                  const change: FileChange = {
                    file_path: file,
                    operation: operationMap[event.type],
                    timestamp: event.timestamp,
                  };
                  newState.file_changes.push(change);
                }
              }
              break;

            case AgentEventType.TEST_START:
              const testRun: TestRun = {
                tool: event.data.tool || "unknown",
                start_time: event.timestamp,
                total_tests: 0,
                passed_tests: 0,
                failed_tests: 0,
                skipped_tests: 0,
                failures: [],
                success_rate: 0,
              };
              newState.test_runs.push(testRun);
              newState.current_test_run = testRun;
              break;

            case AgentEventType.TEST_RESULT:
              if (newState.current_test_run) {
                const status = event.data.status;
                if (status === "passed") {
                  newState.current_test_run.passed_tests++;
                } else if (status === "failed") {
                  newState.current_test_run.failed_tests++;
                  newState.current_test_run.failures.push(event.data);
                } else if (status === "skipped") {
                  newState.current_test_run.skipped_tests++;
                }
              }
              break;

            case AgentEventType.TEST_SUMMARY:
              if (newState.current_test_run) {
                newState.current_test_run.end_time = event.timestamp;
                newState.current_test_run.total_tests = event.data.total || 0;
                if (event.data.passed !== undefined) {
                  newState.current_test_run.passed_tests = event.data.passed;
                }
                newState.current_test_run.success_rate =
                  newState.current_test_run.total_tests > 0
                    ? newState.current_test_run.passed_tests /
                      newState.current_test_run.total_tests
                    : 0;
                newState.current_test_run = undefined;
              }
              break;

            case AgentEventType.AGENT_THINKING:
              newState.current_phase = "thinking";
              break;

            case AgentEventType.AGENT_PLANNING:
              newState.current_phase = "planning";
              break;

            case AgentEventType.AGENT_DECISION:
              newState.current_phase = "executing";
              break;

            case AgentEventType.ERROR:
              newState.metrics.error_count++;
              break;

            case AgentEventType.WARNING:
              newState.metrics.warning_count++;
              break;
          }

          // Update metrics
          newState.metrics = {
            ...newState.metrics,
            total_commands: newState.commands.length,
            total_events: newState.events.length,
            total_files_changed: newState.file_changes.length,
            total_test_runs: newState.test_runs.length,
            session_duration:
              (Date.now() - new Date(newState.start_time).getTime()) / 1000,
            current_phase: newState.current_phase,
          };

          // Update test metrics
          if (newState.test_runs.length > 0) {
            const totalTests = newState.test_runs.reduce(
              (sum: number, run: TestRun) => sum + run.total_tests,
              0
            );
            const passedTests = newState.test_runs.reduce(
              (sum: number, run: TestRun) => sum + run.passed_tests,
              0
            );
            newState.metrics.total_tests = totalTests;
            newState.metrics.tests_passed = passedTests;
            newState.metrics.test_success_rate = totalTests > 0 ? passedTests / totalTests : 0;
          }

          // Add output to current command if running
          if (newState.current_command && event.raw_text) {
            newState.current_command.output_lines.push(event.raw_text);
            newState.current_command.events.push(event);
          }

          return {
            sessionState: newState,
            timeline: newTimeline,
            eventHistory: newEventHistory,
          };
        }),

      // Update session summary (from server)
      updateSessionSummary: (summary: SessionSummary) =>
        set((state) => {
          if (!state.sessionState) return state;

          return {
            sessionState: {
              ...state.sessionState,
              current_phase: summary.current_phase as any,
              metrics: summary.metrics,
            },
          };
        }),

      // Clear session
      clearSession: () =>
        set({
          sessionState: null,
          timeline: [],
          eventHistory: [],
        }),

      // Set max events to keep in history
      setMaxEvents: (max: number) =>
        set({ maxEvents: max }),

      // Getters
      getCurrentCommand: () => {
        const state = get();
        return state.sessionState?.current_command;
      },

      getCurrentTestRun: () => {
        const state = get();
        return state.sessionState?.current_test_run;
      },

      getRecentFiles: (count = 5) => {
        const state = get();
        if (!state.sessionState) return [];
        const files = state.sessionState.file_changes;
        return files.slice(-count);
      },

      getErrorCount: () => {
        const state = get();
        return state.sessionState?.metrics.error_count || 0;
      },

      getTestSummary: () => {
        const state = get();
        if (!state.sessionState || state.sessionState.test_runs.length === 0) {
          return { total: 0, passed: 0, failed: 0, success_rate: 0 };
        }

        const runs = state.sessionState.test_runs;
        const total = runs.reduce((sum: number, run: TestRun) => sum + run.total_tests, 0);
        const passed = runs.reduce((sum: number, run: TestRun) => sum + run.passed_tests, 0);
        const failed = runs.reduce((sum: number, run: TestRun) => sum + run.failed_tests, 0);

        return {
          total,
          passed,
          failed,
          success_rate: total > 0 ? passed / total : 0,
        };
      },

      getSessionDuration: () => {
        const state = get();
        if (!state.sessionState) return 0;
        return (Date.now() - new Date(state.sessionState.start_time).getTime()) / 1000;
      },

      getPhaseHistory: () => {
        const state = get();
        if (!state.timeline) return [];

        const phases: Array<{ phase: string; timestamp: string }> = [];
        let lastPhase = "";

        for (const entry of state.timeline) {
          if (entry.phase !== lastPhase) {
            phases.push({
              phase: entry.phase,
              timestamp: entry.timestamp,
            });
            lastPhase = entry.phase;
          }
        }

        return phases;
      },
    })),
    {
      name: "agent-store",
    }
  )
);

// Helper function (duplicated from types for convenience)
function getEventDescription(event: AgentEvent): string {
  const descriptions: Record<string, string> = {
    command_start: `Running: ${event.data.command || "command"}`,
    command_end: `Completed: ${event.data.command || "command"}`,
    file_read: `Reading: ${event.data.file || "file"}`,
    file_write: `Writing: ${event.data.file || "file"}`,
    file_delete: `Deleting: ${event.data.files?.join(", ") || "files"}`,
    test_start: `Testing with ${event.data.tool || "test tool"}`,
    test_summary: `Tests: ${event.data.passed || 0} passed`,
    agent_thinking: "Agent is thinking...",
    agent_planning: "Agent is planning...",
    agent_decision: "Agent made a decision",
    error: `Error: ${event.data.command || "unknown"}`,
    warning: "Warning detected",
    install_start: "Installing packages...",
    build_start: "Building project...",
  };

  return descriptions[event.type] || event.type;
}