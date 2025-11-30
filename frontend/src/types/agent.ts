/**
 * Agent Terminal Overlay Type Definitions
 *
 * Defines the structure of agent events and session state
 * for the enhanced terminal with agent output parsing.
 */

/**
 * Types of events that can be detected in agent output
 */
export enum AgentEventType {
  // Command events
  COMMAND_START = "command_start",
  COMMAND_END = "command_end",
  COMMAND_OUTPUT = "command_output",

  // File events
  FILE_READ = "file_read",
  FILE_WRITE = "file_write",
  FILE_DELETE = "file_delete",
  FILE_DIFF = "file_diff",

  // Test events
  TEST_START = "test_start",
  TEST_RESULT = "test_result",
  TEST_SUMMARY = "test_summary",

  // Build/Install events
  INSTALL_START = "install_start",
  INSTALL_PROGRESS = "install_progress",
  INSTALL_END = "install_end",
  BUILD_START = "build_start",
  BUILD_END = "build_end",

  // Agent reasoning
  AGENT_THINKING = "agent_thinking",
  AGENT_PLANNING = "agent_planning",
  AGENT_DECISION = "agent_decision",
  AGENT_ERROR = "agent_error",

  // Git events
  GIT_STATUS = "git_status",
  GIT_DIFF = "git_diff",
  GIT_COMMIT = "git_commit",

  // General
  ERROR = "error",
  WARNING = "warning",
  INFO = "info",
  PROMPT = "prompt",
}

/**
 * Structured agent event extracted from terminal output
 */
export interface AgentEvent {
  type: AgentEventType;
  timestamp: string;
  data: Record<string, any>;
  raw_text: string;
  line_number?: number;
  confidence?: number;
}

/**
 * Command execution tracking
 */
export interface CommandExecution {
  command: string;
  start_time: string;
  end_time?: string;
  exit_code?: number;
  output_lines: string[];
  events: AgentEvent[];
  status: "running" | "completed" | "failed";
  duration_seconds?: number;
}

/**
 * File change tracking
 */
export interface FileChange {
  file_path: string;
  operation: "read" | "write" | "delete" | "modify";
  timestamp: string;
  line_count?: number;
  diff?: string;
}

/**
 * Test run tracking
 */
export interface TestRun {
  tool: string; // pytest, jest, etc.
  start_time: string;
  end_time?: string;
  total_tests: number;
  passed_tests: number;
  failed_tests: number;
  skipped_tests: number;
  failures: Array<Record<string, any>>;
  success_rate: number;
}

/**
 * Agent session state
 */
export interface AgentSessionState {
  session_id: string;
  start_time: string;
  current_phase: "idle" | "thinking" | "planning" | "executing" | "verifying";
  commands: CommandExecution[];
  file_changes: FileChange[];
  test_runs: TestRun[];
  events: AgentEvent[];
  metrics: AgentMetrics;

  // Current tracking
  current_command?: CommandExecution;
  current_test_run?: TestRun;
}

/**
 * Session metrics
 */
export interface AgentMetrics {
  total_commands: number;
  total_events: number;
  total_files_changed: number;
  total_test_runs: number;
  session_duration: number;
  current_phase: string;
  error_count: number;
  warning_count: number;
  total_tests?: number;
  tests_passed?: number;
  test_success_rate?: number;
}

/**
 * Timeline entry for visualization
 */
export interface TimelineEntry {
  timestamp: string;
  type: string;
  description: string;
  data: Record<string, any>;
  phase: string;
}

/**
 * Session summary for quick overview
 */
export interface SessionSummary {
  session_id: string;
  current_phase: string;
  metrics: AgentMetrics;
  active_command?: string;
  active_test?: string;
  recent_files: string[];
  error_count: number;
  command_count: number;
  test_summary: {
    total: number;
    passed: number;
    failed: number;
    success_rate: number;
  };
}

/**
 * Agent protocol messages for WebSocket
 */
export interface AgentProtocol {
  // Commands to send
  enable: "__AGENT__:enable";
  disable: "__AGENT__:disable";
  summary: "__AGENT__:summary";

  // Messages received
  event: "__AGENT__:event:{json}";
  status: "__AGENT__:status:{enabled|disabled}";
  summary_data: "__AGENT__:summary:{json}";
}

/**
 * Agent event handler type
 */
export type AgentEventHandler = (event: AgentEvent, state: AgentSessionState) => void | Promise<void>;

/**
 * Agent event subscription callback
 */
export type AgentEventCallback = (event: AgentEvent) => void;

/**
 * Phase colors for UI visualization
 */
export const PHASE_COLORS: Record<string, string> = {
  idle: "#gray",
  thinking: "#blue",
  planning: "#orange",
  executing: "#yellow",
  verifying: "#green",
  testing: "#purple",
  building: "#cyan",
  installing: "#pink",
};

/**
 * Event type icons for UI
 */
export const EVENT_ICONS: Record<string, string> = {
  // Commands
  [AgentEventType.COMMAND_START]: "🚀",
  [AgentEventType.COMMAND_END]: "✅",
  [AgentEventType.COMMAND_OUTPUT]: "📝",

  // Files
  [AgentEventType.FILE_READ]: "📖",
  [AgentEventType.FILE_WRITE]: "✏️",
  [AgentEventType.FILE_DELETE]: "🗑️",
  [AgentEventType.FILE_DIFF]: "🔄",

  // Tests
  [AgentEventType.TEST_START]: "🧪",
  [AgentEventType.TEST_RESULT]: "📊",
  [AgentEventType.TEST_SUMMARY]: "📈",

  // Build
  [AgentEventType.INSTALL_START]: "📦",
  [AgentEventType.INSTALL_PROGRESS]: "⏳",
  [AgentEventType.INSTALL_END]: "✅",
  [AgentEventType.BUILD_START]: "🔨",
  [AgentEventType.BUILD_END]: "✅",

  // Agent
  [AgentEventType.AGENT_THINKING]: "🤔",
  [AgentEventType.AGENT_PLANNING]: "📝",
  [AgentEventType.AGENT_DECISION]: "💡",
  [AgentEventType.AGENT_ERROR]: "❌",

  // Git
  [AgentEventType.GIT_STATUS]: "📊",
  [AgentEventType.GIT_DIFF]: "🔍",
  [AgentEventType.GIT_COMMIT]: "📝",

  // General
  [AgentEventType.ERROR]: "🔴",
  [AgentEventType.WARNING]: "🟠",
  [AgentEventType.INFO]: "🔵",
  [AgentEventType.PROMPT]: "❓",
} as const;

/**
 * Parse agent event from WebSocket message
 */
export function parseAgentMessage(message: string): AgentEvent | null {
  if (!message.startsWith("__AGENT__:event:")) {
    return null;
  }

  try {
    const jsonStr = message.substring("__AGENT__:event:".length);
    return JSON.parse(jsonStr) as AgentEvent;
  } catch (error) {
    console.error("Failed to parse agent event:", error);
    return null;
  }
}

/**
 * Parse agent status message
 */
export function parseAgentStatus(message: string): "enabled" | "disabled" | null {
  if (message.startsWith("__AGENT__:status:")) {
    const status = message.substring("__AGENT__:status:".length).trim();
    if (status === "enabled" || status === "disabled") {
      return status;
    }
  }
  return null;
}

/**
 * Parse agent summary message
 */
export function parseAgentSummary(message: string): SessionSummary | null {
  if (!message.startsWith("__AGENT__:summary:")) {
    return null;
  }

  try {
    const jsonStr = message.substring("__AGENT__:summary:".length);
    return JSON.parse(jsonStr) as SessionSummary;
  } catch (error) {
    console.error("Failed to parse agent summary:", error);
    return null;
  }
}

/**
 * Format duration in human-readable form
 */
export function formatDuration(seconds: number): string {
  if (seconds < 1) {
    return `${Math.round(seconds * 1000)}ms`;
  } else if (seconds < 60) {
    return `${seconds.toFixed(1)}s`;
  } else if (seconds < 3600) {
    const mins = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    return `${mins}m ${secs}s`;
  } else {
    const hours = Math.floor(seconds / 3600);
    const mins = Math.floor((seconds % 3600) / 60);
    return `${hours}h ${mins}m`;
  }
}

/**
 * Get human-readable phase name
 */
export function getPhaseName(phase: string): string {
  const phaseNames: Record<string, string> = {
    idle: "Idle",
    thinking: "Thinking",
    planning: "Planning",
    executing: "Executing",
    verifying: "Verifying",
  };
  return phaseNames[phase] || phase;
}

/**
 * Get event description
 */
export function getEventDescription(event: AgentEvent): string {
  const descriptions: Record<AgentEventType, (data: any) => string> = {
    [AgentEventType.COMMAND_START]: (d) => `Running: ${d.command || "command"}`,
    [AgentEventType.COMMAND_END]: (d) => `Completed: ${d.command || "command"}`,
    [AgentEventType.FILE_READ]: (d) => `Reading: ${d.file || "file"}`,
    [AgentEventType.FILE_WRITE]: (d) => `Writing: ${d.file || "file"}`,
    [AgentEventType.FILE_DELETE]: (d) => `Deleting: ${d.files?.join(", ") || "files"}`,
    [AgentEventType.TEST_START]: (d) => `Testing with ${d.tool || "test tool"}`,
    [AgentEventType.TEST_SUMMARY]: (d) => `Tests: ${d.passed || 0} passed`,
    [AgentEventType.AGENT_THINKING]: () => "Agent is thinking...",
    [AgentEventType.AGENT_PLANNING]: () => "Agent is planning...",
    [AgentEventType.AGENT_DECISION]: () => "Agent made a decision",
    [AgentEventType.ERROR]: (d) => `Error: ${d.command || "unknown"}`,
    [AgentEventType.WARNING]: () => "Warning detected",
    [AgentEventType.INSTALL_START]: () => "Installing packages...",
    [AgentEventType.BUILD_START]: () => "Building project...",
    // Default handlers for remaining types
    [AgentEventType.COMMAND_OUTPUT]: () => "Command output",
    [AgentEventType.FILE_DIFF]: () => "File diff",
    [AgentEventType.TEST_RESULT]: (d) => `Test ${d.status}: ${d.test}`,
    [AgentEventType.INSTALL_PROGRESS]: () => "Installation progress",
    [AgentEventType.INSTALL_END]: () => "Installation complete",
    [AgentEventType.BUILD_END]: () => "Build complete",
    [AgentEventType.GIT_STATUS]: () => "Git status",
    [AgentEventType.GIT_DIFF]: () => "Git diff",
    [AgentEventType.GIT_COMMIT]: () => "Git commit",
    [AgentEventType.INFO]: () => "Info",
    [AgentEventType.PROMPT]: (d) => `Prompt: ${d.prompt_type}`,
    [AgentEventType.AGENT_ERROR]: (d) => `Agent error: ${d.error || "unknown"}`,
  };

  const handler = descriptions[event.type];
  return handler ? handler(event.data) : event.type;
}