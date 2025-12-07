/**
 * Agent Types
 *
 * Minimal type definitions for agent UI components.
 * All agents now run via Socket.IO terminal - these types support
 * session history and basic UI state only.
 */

// ============================================================================
// Message Types (for session history compatibility)
// ============================================================================

/**
 * Token usage information (kept for history display)
 */
export interface ClaudeUsage {
  input_tokens?: number;
  output_tokens?: number;
  cache_creation_input_tokens?: number;
  cache_read_input_tokens?: number;
}

/**
 * Message for session history storage
 * Simplified from streaming mode - now mainly used for history display
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
 * Session information (minimal)
 */
export interface ClaudeSessionInfo {
  sessionId: string | null;
  model: string | null;
  tools: string[];
  mcpServers: Array<{ name: string; status: string }>;
}

// ============================================================================
// Tool Display Helpers
// ============================================================================

/**
 * Tool icons by name (for history display)
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
};

/**
 * Get icon for a tool
 */
export function getToolIcon(toolName: string): string {
  if (TOOL_ICONS[toolName]) {
    return TOOL_ICONS[toolName];
  }
  if (toolName.startsWith("mcp__")) return "🔧";
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
