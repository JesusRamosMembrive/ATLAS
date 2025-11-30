/**
 * Claude Code JSON Streaming Event Types
 *
 * Types for events received from `claude -p --output-format stream-json --verbose`
 * Used by the ClaudeAgentView component for rendering structured Claude output.
 */

// ============================================================================
// Core Event Types
// ============================================================================

/**
 * Event type from Claude Code JSON stream
 */
export type ClaudeEventType =
  | "system"
  | "assistant"
  | "user"
  | "result"
  | "connected"
  | "done"
  | "error"
  | "cancelled"
  | "session_reset"
  | "session_broken"
  | "status"
  | "permission_request"
  | "tool_approval_request"
  | "mcp_approval_request"
  // PTY mode events
  | "session_started"
  | "session_ended"
  | "thinking"
  | "message"
  | "completion"
  | "pty_permission_request"
  | "unknown";

/**
 * Event subtype for more specific classification
 */
export type ClaudeEventSubtype =
  | "init"
  | "text"
  | "tool_use"
  | "tool_result"
  | "thinking"
  | "error"
  | "success"
  | "unknown";

// ============================================================================
// Event Interfaces
// ============================================================================

/**
 * Base event structure from WebSocket
 */
export interface ClaudeBaseEvent {
  type: ClaudeEventType;
  subtype?: ClaudeEventSubtype;
  timestamp?: string;
  session_id?: string | null;
}

/**
 * System initialization event
 */
export interface ClaudeSystemInitEvent extends ClaudeBaseEvent {
  type: "system";
  subtype: "init";
  content: {
    session_id: string;
    model: string;
    tools: string[];
    mcp_servers: Array<{ name: string; status: string }>;
  };
}

/**
 * Assistant text message event
 */
export interface ClaudeTextEvent extends ClaudeBaseEvent {
  type: "assistant";
  subtype: "text";
  content: string;
  usage?: ClaudeUsage;
}

/**
 * Assistant tool use event
 */
export interface ClaudeToolUseEvent extends ClaudeBaseEvent {
  type: "assistant";
  subtype: "tool_use";
  content: {
    id: string;
    name: string;
    input: Record<string, unknown>;
  };
  tool_id?: string;
  tool_name?: string;
  usage?: ClaudeUsage;
}

/**
 * User tool result event
 */
export interface ClaudeToolResultEvent extends ClaudeBaseEvent {
  type: "user";
  subtype: "tool_result";
  content: {
    tool_use_id: string;
    content: string;
    is_error?: boolean;
  };
  tool_id?: string;
}

/**
 * Connection event
 */
export interface ClaudeConnectedEvent extends ClaudeBaseEvent {
  type: "connected";
  cwd: string;
}

/**
 * Done event
 */
export interface ClaudeDoneEvent extends ClaudeBaseEvent {
  type: "done";
}

/**
 * Error event
 */
export interface ClaudeErrorEvent extends ClaudeBaseEvent {
  type: "error";
  content: string;
}

/**
 * Cancelled event
 */
export interface ClaudeCancelledEvent extends ClaudeBaseEvent {
  type: "cancelled";
  note?: string;
}

/**
 * Session reset event
 */
export interface ClaudeSessionResetEvent extends ClaudeBaseEvent {
  type: "session_reset";
}

/**
 * Session broken event - tools executed locally, session cannot be continued
 */
export interface ClaudeSessionBrokenEvent extends ClaudeBaseEvent {
  type: "session_broken";
  reason?: string;
}

/**
 * Status event
 */
export interface ClaudeStatusEvent extends ClaudeBaseEvent {
  type: "status";
  session_info: {
    session_id: string | null;
    model: string | null;
    tools: string[];
    mcp_servers: Array<{ name: string; status: string }>;
  };
  running: boolean;
  continue_session: boolean;
}

/**
 * Permission request event - Claude needs user approval for an action
 */
export interface ClaudePermissionRequestEvent extends ClaudeBaseEvent {
  type: "permission_request";
  request_id: string;
  tool: string;
  input: Record<string, unknown>;
  raw_event?: Record<string, unknown>;
}

/**
 * Tool approval request event - requires user approval before tool execution
 * Used in toolApproval mode for interactive approval with preview/diff
 */
export interface ClaudeToolApprovalRequestEvent extends ClaudeBaseEvent {
  type: "tool_approval_request";
  request_id: string;
  tool_name: string;
  tool_input: Record<string, unknown>;
  tool_use_id: string;
  preview_type: "diff" | "multi_diff" | "command" | "generic";
  preview_data: Record<string, unknown>;
  file_path?: string;
  original_content?: string;
  new_content?: string;
  diff_lines: string[];
}

/**
 * MCP approval request event - requires user approval via MCP permission server
 * Used in mcpApproval mode for real tool interception with --permission-prompt-tool
 *
 * This is the RECOMMENDED approach as it uses Claude Code's native permission system
 * instead of trying to intercept tool calls via plan mode.
 */
export interface ClaudeMCPApprovalRequestEvent extends ClaudeBaseEvent {
  type: "mcp_approval_request";
  request_id: string;
  tool_name: string;
  tool_input: Record<string, unknown>;
  context?: string;
  preview_type: "diff" | "multi_diff" | "command" | "generic";
  preview_data: Record<string, unknown>;
  file_path?: string;
  original_content?: string;
  new_content?: string;
  diff_lines: string[];
}

/**
 * PTY permission request event - permission request from PTY mode
 * Used when running Claude in a real pseudo-terminal with Ink UI
 */
export interface ClaudePTYPermissionRequestEvent extends ClaudeBaseEvent {
  type: "permission_request";
  data: {
    permission_type: string;
    target?: string;
    full_text: string;
  };
  raw_text?: string;
}

/**
 * PTY session started event
 */
export interface ClaudePTYSessionStartedEvent extends ClaudeBaseEvent {
  type: "session_started";
}

/**
 * PTY session ended event
 */
export interface ClaudePTYSessionEndedEvent extends ClaudeBaseEvent {
  type: "session_ended";
}

/**
 * PTY thinking event - Claude is processing
 */
export interface ClaudePTYThinkingEvent extends ClaudeBaseEvent {
  type: "thinking";
  data?: {
    indicator?: string;
  };
}

/**
 * PTY message event - text output from Claude
 */
export interface ClaudePTYMessageEvent extends ClaudeBaseEvent {
  type: "message";
  data: {
    content: string;
  };
  raw_text?: string;
}

/**
 * PTY completion event - task completed
 */
export interface ClaudePTYCompletionEvent extends ClaudeBaseEvent {
  type: "completion";
  data?: {
    tool_type?: string;
    message?: string;
  };
}

/**
 * Permission denial info - tool blocked due to missing permission
 */
export interface PermissionDenial {
  tool_name: string;
  tool_use_id: string;
  tool_input: Record<string, unknown>;
}

/**
 * Result event - final result with potential permission denials
 */
export interface ClaudeResultEvent extends ClaudeBaseEvent {
  type: "result";
  subtype: "success" | "error";
  result: string;
  is_error: boolean;
  duration_ms?: number;
  permission_denials?: PermissionDenial[];
  usage?: ClaudeUsage;
}

/**
 * Union type of all Claude events
 */
export type ClaudeEvent =
  | ClaudeSystemInitEvent
  | ClaudeTextEvent
  | ClaudeToolUseEvent
  | ClaudeToolResultEvent
  | ClaudeConnectedEvent
  | ClaudeDoneEvent
  | ClaudeErrorEvent
  | ClaudeCancelledEvent
  | ClaudeSessionResetEvent
  | ClaudeSessionBrokenEvent
  | ClaudeStatusEvent
  | ClaudePermissionRequestEvent
  | ClaudeToolApprovalRequestEvent
  | ClaudeMCPApprovalRequestEvent
  | ClaudeResultEvent;

// ============================================================================
// Supporting Types
// ============================================================================

/**
 * Token usage information
 */
export interface ClaudeUsage {
  input_tokens?: number;
  output_tokens?: number;
  cache_creation_input_tokens?: number;
  cache_read_input_tokens?: number;
}

/**
 * Message for UI rendering
 */
export interface ClaudeMessage {
  id: string;
  type: "text" | "tool_use" | "tool_result" | "error" | "system";
  role: "user" | "assistant";
  content: string | Record<string, unknown>;
  timestamp: Date;
  toolName?: string;
  toolId?: string;
  isError?: boolean;
  usage?: ClaudeUsage;
}

/**
 * Tool call tracking
 */
export interface ToolCall {
  id: string;
  name: string;
  input: Record<string, unknown>;
  startTime: Date;
  endTime?: Date;
  result?: string;
  isError?: boolean;
  status: "running" | "completed" | "failed";
}

/**
 * Session information
 */
export interface ClaudeSessionInfo {
  sessionId: string | null;
  model: string | null;
  tools: string[];
  mcpServers: Array<{ name: string; status: string }>;
}

// ============================================================================
// WebSocket Commands
// ============================================================================

/**
 * Commands to send to the agent WebSocket
 */
export interface AgentCommand {
  command: "run" | "cancel" | "new_session" | "status" | "permission_response" | "tool_approval_response" | "mcp_approval_response";
  prompt?: string;
  continue?: boolean;
  permission_mode?: string;
  auto_approve_safe?: boolean;
  // For permission_response command
  approved?: boolean;
  always?: boolean;
  // For tool_approval_response command
  request_id?: string;
  feedback?: string;
  // For mcp_approval_response command
  message?: string;
  updated_input?: Record<string, unknown>;
}

/**
 * Commands to send to the PTY agent WebSocket
 */
export interface PTYAgentCommand {
  command: "start" | "run" | "approve" | "deny" | "always_allow" | "cancel" | "stop" | "status";
  prompt?: string;
  timeout?: number;
  init_wait?: number;
}

/**
 * Type guard for PTY permission request event
 */
export function isPTYPermissionRequestEvent(
  event: ClaudeEvent
): event is ClaudePTYPermissionRequestEvent {
  return event.type === "permission_request" && "data" in event;
}

// ============================================================================
// Helpers
// ============================================================================

/**
 * Type guard for system init event
 */
export function isSystemInitEvent(
  event: ClaudeEvent
): event is ClaudeSystemInitEvent {
  return event.type === "system" && event.subtype === "init";
}

/**
 * Type guard for text event
 */
export function isTextEvent(event: ClaudeEvent): event is ClaudeTextEvent {
  return event.type === "assistant" && event.subtype === "text";
}

/**
 * Type guard for tool use event
 */
export function isToolUseEvent(
  event: ClaudeEvent
): event is ClaudeToolUseEvent {
  return event.type === "assistant" && event.subtype === "tool_use";
}

/**
 * Type guard for tool result event
 */
export function isToolResultEvent(
  event: ClaudeEvent
): event is ClaudeToolResultEvent {
  return event.type === "user" && event.subtype === "tool_result";
}

/**
 * Type guard for done event
 */
export function isDoneEvent(event: ClaudeEvent): event is ClaudeDoneEvent {
  return event.type === "done";
}

/**
 * Type guard for error event
 */
export function isErrorEvent(event: ClaudeEvent): event is ClaudeErrorEvent {
  return event.type === "error";
}

/**
 * Type guard for permission request event
 */
export function isPermissionRequestEvent(
  event: ClaudeEvent
): event is ClaudePermissionRequestEvent {
  return event.type === "permission_request";
}

/**
 * Type guard for tool approval request event
 */
export function isToolApprovalRequestEvent(
  event: ClaudeEvent
): event is ClaudeToolApprovalRequestEvent {
  return event.type === "tool_approval_request";
}

/**
 * Type guard for MCP approval request event
 */
export function isMCPApprovalRequestEvent(
  event: ClaudeEvent
): event is ClaudeMCPApprovalRequestEvent {
  return event.type === "mcp_approval_request";
}

/**
 * Type guard for result event
 */
export function isResultEvent(
  event: ClaudeEvent
): event is ClaudeResultEvent {
  return event.type === "result";
}

/**
 * Check if result event has permission denials
 */
export function hasPermissionDenials(
  event: ClaudeEvent
): event is ClaudeResultEvent & { permission_denials: PermissionDenial[] } {
  return isResultEvent(event) &&
    Array.isArray(event.permission_denials) &&
    event.permission_denials.length > 0;
}

/**
 * Tool icons by name
 */
export const TOOL_ICONS: Record<string, string> = {
  Read: "📖",
  Write: "✏️",
  Edit: "📝",
  Bash: "💻",
  Glob: "🔍",
  Grep: "🔎",
  Task: "📋",
  TodoWrite: "✅",
  WebFetch: "🌐",
  WebSearch: "🔍",
  NotebookEdit: "📓",
  // MCP tools
  mcp__playwright__browser_navigate: "🌐",
  mcp__playwright__browser_click: "🖱️",
  mcp__playwright__browser_snapshot: "📸",
  mcp__context7__resolve_library_id: "📚",
  mcp__context7__get_library_docs: "📖",
  mcp__sequential_thinking__sequentialthinking: "🧠",
};

/**
 * Get icon for a tool
 */
export function getToolIcon(toolName: string): string {
  // Check exact match
  if (TOOL_ICONS[toolName]) {
    return TOOL_ICONS[toolName];
  }

  // Check prefix match for MCP tools
  if (toolName.startsWith("mcp__playwright")) return "🎭";
  if (toolName.startsWith("mcp__context7")) return "📚";
  if (toolName.startsWith("mcp__sequential")) return "🧠";
  if (toolName.startsWith("mcp__magic")) return "✨";
  if (toolName.startsWith("mcp__chrome")) return "🔧";

  // Default
  return "🔧";
}

/**
 * Format tool input for display
 */
export function formatToolInput(
  input: Record<string, unknown>,
  maxLength = 100
): string {
  const str = JSON.stringify(input, null, 2);
  if (str.length <= maxLength) return str;
  return str.substring(0, maxLength) + "...";
}

/**
 * Generate unique message ID
 */
export function generateMessageId(): string {
  return `msg_${Date.now()}_${Math.random().toString(36).substring(2, 11)}`;
}
