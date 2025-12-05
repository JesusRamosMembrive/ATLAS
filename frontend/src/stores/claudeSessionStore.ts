/**
 * Claude Session Store
 *
 * Manages AI Agent (Claude, Codex, Gemini) JSON streaming session state using Zustand.
 * Handles WebSocket connection, message processing, and UI state.
 */

import { create } from "zustand";
import { devtools, subscribeWithSelector, persist } from "zustand/middleware";
import { createLogger } from "../utils/logger";
import {
  ClaudeEvent,
  ClaudeMessage,
  ClaudeSessionInfo,
  ToolCall,
  AgentCommand,
  isSystemInitEvent,
  isTextEvent,
  isToolUseEvent,
  isToolResultEvent,
  isDoneEvent,
  isErrorEvent,
  isPermissionRequestEvent,
  isToolApprovalRequestEvent,
  isMCPApprovalRequestEvent,
  isResultEvent,
  hasPermissionDenials,
  generateMessageId,
  ClaudePermissionRequestEvent,
  ClaudeToolApprovalRequestEvent,
  ClaudeMCPApprovalRequestEvent,
  PermissionDenial,
} from "../types/claude-events";

// Create namespaced logger
const log = createLogger("ClaudeSession");

// ============================================================================
// Agent Types
// ============================================================================

export type AgentType = "claude" | "codex" | "gemini";

export const AGENT_TYPES: AgentType[] = ["claude", "codex", "gemini"];

// Gemini-specific execution modes
// - stream: JSON streaming with auto_edit (auto-approves file ops, blocks shell)
// - terminal: Embedded terminal with native Gemini approval prompts
export type GeminiMode = "stream" | "terminal";

export const GEMINI_MODES: GeminiMode[] = ["stream", "terminal"];

export const GEMINI_MODE_LABELS: Record<GeminiMode, string> = {
  stream: "Stream Mode",
  terminal: "Terminal Mode",
};

export const GEMINI_MODE_DESCRIPTIONS: Record<GeminiMode, string> = {
  stream: "Auto-approve file operations, block shell commands (faster, no prompts)",
  terminal: "Interactive terminal with native approval prompts (full control)",
};

export const AGENT_TYPE_LABELS: Record<AgentType, string> = {
  claude: "Claude Code",
  codex: "OpenAI Codex",
  gemini: "Google Gemini",
};

export const AGENT_TYPE_DESCRIPTIONS: Record<AgentType, string> = {
  claude: "Anthropic's Claude Code CLI - Advanced coding assistant",
  codex: "OpenAI's Codex CLI - Powered by GPT models",
  gemini: "Google's Gemini CLI - Multimodal AI assistant",
};

// WebSocket endpoint paths for each agent
export const AGENT_WS_ENDPOINTS: Record<AgentType, string> = {
  claude: "/api/terminal/ws/agent",
  codex: "/api/terminal/ws/codex-agent",
  gemini: "/api/terminal/ws/gemini-agent",
};

// Available models per agent
export const AGENT_MODELS: Record<AgentType, string[]> = {
  claude: ["claude-sonnet-4-20250514", "claude-opus-4-20250514", "claude-3-5-haiku-20241022"],
  codex: ["gpt-5.1-codex-max", "gpt-5.1-codex", "gpt-5.1-codex-mini", "gpt-5.1"],
  gemini: ["gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.0-flash"],
};

// Default model per agent
export const AGENT_DEFAULT_MODELS: Record<AgentType, string> = {
  claude: "claude-sonnet-4-20250514",
  codex: "gpt-5.1-codex-max",
  gemini: "gemini-2.5-flash",
};

// ============================================================================
// Slash Commands
// ============================================================================

export interface SlashCommand {
  command: string;
  label: string;
  description: string;
  hasArgs?: boolean;
  argPlaceholder?: string;
}

// Claude Code slash commands
export const CLAUDE_SLASH_COMMANDS: SlashCommand[] = [
  { command: "/clear", label: "Clear", description: "Wipe conversation history and start fresh" },
  { command: "/compact", label: "Compact", description: "Compress context to save tokens", hasArgs: true, argPlaceholder: "[instructions]" },
  { command: "/context", label: "Context", description: "View current context usage" },
  { command: "/cost", label: "Cost", description: "Show token usage and estimated cost" },
  { command: "/help", label: "Help", description: "Show available commands and shortcuts" },
  { command: "/memory", label: "Memory", description: "Edit CLAUDE.md project memory file" },
  { command: "/permissions", label: "Permissions", description: "Manage tool permissions" },
  { command: "/review", label: "Review", description: "Request a code review" },
  { command: "/status", label: "Status", description: "View session status and info" },
];

// Codex CLI slash commands (based on codex CLI help)
export const CODEX_SLASH_COMMANDS: SlashCommand[] = [
  { command: "/clear", label: "Clear", description: "Clear conversation history" },
  { command: "/help", label: "Help", description: "Show available commands" },
  { command: "/model", label: "Model", description: "Change the model", hasArgs: true, argPlaceholder: "<model-name>" },
  { command: "/status", label: "Status", description: "View session status" },
];

// Gemini CLI slash commands
export const GEMINI_SLASH_COMMANDS: SlashCommand[] = [
  { command: "/clear", label: "Clear", description: "Clear conversation history" },
  { command: "/help", label: "Help", description: "Show available commands" },
  { command: "/status", label: "Status", description: "View session status" },
];

// Get slash commands for a specific agent type
export const AGENT_SLASH_COMMANDS: Record<AgentType, SlashCommand[]> = {
  claude: CLAUDE_SLASH_COMMANDS,
  codex: CODEX_SLASH_COMMANDS,
  gemini: GEMINI_SLASH_COMMANDS,
};

// ============================================================================
// Types
// ============================================================================

// Permission modes supported
// - bypassPermissions: Uses Claude CLI with --dangerously-skip-permissions
// - mcpProxy: Uses Claude CLI with MCP tool proxy for approval (RECOMMENDED - uses your CLI subscription)
// - toolApproval: Uses Claude CLI in plan mode (may not emit tool_use events reliably)
// - sdk: Uses Anthropic Python SDK directly (requires separate API key with separate billing)
export type PermissionMode = "bypassPermissions" | "mcpProxy" | "toolApproval" | "sdk";

export const PERMISSION_MODES: PermissionMode[] = ["bypassPermissions", "mcpProxy", "toolApproval", "sdk"];

export const PERMISSION_MODE_LABELS: Record<PermissionMode, string> = {
  bypassPermissions: "Auto Execute",
  mcpProxy: "Review & Approve (CLI)",
  toolApproval: "Review & Approve (Plan)",
  sdk: "Review & Approve (SDK)",
};

export const PERMISSION_MODE_DESCRIPTIONS: Record<PermissionMode, string> = {
  bypassPermissions: "Claude executes all actions automatically without asking",
  mcpProxy: "Review and approve each change with diff preview (uses your Claude CLI subscription)",
  toolApproval: "Review and approve changes via plan mode (may be unreliable)",
  sdk: "Review and approve changes (requires separate Anthropic API key with separate billing)",
};

// ============================================================================
// Permission Request Types
// ============================================================================

export interface PendingPermission {
  requestId: string;
  tool: string;
  input: Record<string, unknown>;
  timestamp: Date;
}

// ============================================================================
// Tool Approval Types (for toolApproval mode)
// ============================================================================

export interface PendingToolApproval {
  requestId: string;
  toolName: string;
  toolInput: Record<string, unknown>;
  toolUseId: string;
  previewType: "diff" | "multi_diff" | "command" | "generic";
  previewData: Record<string, unknown>;
  filePath?: string;
  originalContent?: string;
  newContent?: string;
  diffLines: string[];
  timestamp: Date;
}

// ============================================================================
// MCP Approval Types (DEPRECATED - --permission-prompt-tool doesn't exist in Claude Code v2.x)
// Kept for future compatibility if/when Claude Code adds this feature
// ============================================================================

export interface PendingMCPApproval {
  requestId: string;
  toolName: string;
  toolInput: Record<string, unknown>;
  context?: string;
  previewType: "diff" | "multi_diff" | "command" | "generic";
  previewData: Record<string, unknown>;
  filePath?: string;
  originalContent?: string;
  newContent?: string;
  diffLines: string[];
  timestamp: Date;
}

// ============================================================================
// PTY Mode Types
// ============================================================================

export interface PendingPTYPermission {
  permissionType: string;
  target?: string;
  fullText: string;
  rawText?: string;
  timestamp: Date;
}

// Selected models per agent type
export type SelectedModels = Record<AgentType, string>;

// ============================================================================
// Store Interface
// ============================================================================

interface ClaudeSessionStore {
  // Connection state
  connected: boolean;
  connecting: boolean;
  wsUrl: string | null;
  cwd: string | null;

  // Reconnection state
  reconnectAttempts: number;
  maxReconnectAttempts: number;
  reconnectDelay: number;
  isReconnecting: boolean;

  // Session state
  running: boolean;
  sessionInfo: ClaudeSessionInfo;
  continueSession: boolean;
  permissionMode: PermissionMode;
  agentType: AgentType;
  selectedModels: SelectedModels;
  geminiMode: GeminiMode;

  // Messages and tool calls
  messages: ClaudeMessage[];
  activeToolCalls: Map<string, ToolCall>;
  completedToolCalls: ToolCall[];

  // Token usage tracking
  totalInputTokens: number;
  totalOutputTokens: number;
  lastRequestDuration: number | null;

  // Error handling
  lastError: string | null;
  connectionError: string | null;

  // Permission request handling
  pendingPermission: PendingPermission | null;

  // Permission denials - tools that were blocked
  permissionDenials: PermissionDenial[];

  // Tool approval state (for toolApproval mode)
  pendingToolApproval: PendingToolApproval | null;

  // MCP approval state (DEPRECATED - kept for future compatibility)
  pendingMCPApproval: PendingMCPApproval | null;

  // PTY mode state
  ptySessionActive: boolean;
  pendingPTYPermission: PendingPTYPermission | null;
  ptyThinking: boolean;
  ptyMessages: string[];

  // Plan execution state (for toolApproval mode)
  // Tracks when Claude describes actions without emitting tool_use events
  toolUseCountInResponse: number;
  writeToolUseCountInResponse: number; // Tracks Write/Edit/Bash tool_use events specifically
  planDescriptionOnly: boolean;
  executePlanAttempted: boolean; // Prevents showing banner again after clicking Execute Plan

  // WebSocket instance (internal)
  _ws: WebSocket | null;
  _reconnectTimeout: ReturnType<typeof setTimeout> | null;

  // Actions
  connect: (wsUrl: string) => void;
  disconnect: () => void;
  sendPrompt: (prompt: string) => void;
  cancel: () => void;
  newSession: () => void;
  requestStatus: () => void;
  clearMessages: () => void;
  setError: (error: string | null) => void;
  clearConnectionError: () => void;
  setPermissionMode: (mode: PermissionMode) => void;
  setAgentType: (type: AgentType) => void;
  setSelectedModel: (agentType: AgentType, model: string) => void;
  getCurrentModel: () => string;
  setGeminiMode: (mode: GeminiMode) => void;

  // Permission actions
  respondToPermission: (approved: boolean, always?: boolean) => void;
  clearPermissionDenials: () => void;

  // Tool approval actions (for toolApproval mode)
  respondToToolApproval: (approved: boolean, feedback?: string) => void;
  clearPendingToolApproval: () => void;

  // MCP approval actions (DEPRECATED - kept for future compatibility)
  respondToMCPApproval: (approved: boolean, message?: string, updatedInput?: Record<string, unknown>) => void;
  clearPendingMCPApproval: () => void;

  // PTY mode actions
  startPTYSession: () => void;
  stopPTYSession: () => void;
  sendPTYPrompt: (prompt: string) => void;
  respondToPTYPermission: (response: "approve" | "deny" | "always_allow") => void;
  cancelPTY: () => void;
  clearPTYMessages: () => void;

  // Plan execution actions (for toolApproval mode)
  executePlan: () => void;
  clearPlanDescriptionOnly: () => void;

  // Event processing
  processEvent: (event: ClaudeEvent) => void;

  // Getters
  getActiveToolCall: () => ToolCall | undefined;
  getMessagesByType: (type: ClaudeMessage["type"]) => ClaudeMessage[];
  getToolCallById: (id: string) => ToolCall | undefined;
}

// ============================================================================
// Initial State
// ============================================================================

const initialSessionInfo: ClaudeSessionInfo = {
  sessionId: null,
  model: null,
  tools: [],
  mcpServers: [],
};

// ============================================================================
// Store Implementation
// ============================================================================

// Reconnection configuration
const RECONNECT_CONFIG = {
  maxAttempts: 5,
  baseDelay: 1000,
  maxDelay: 30000,
  backoffMultiplier: 2,
};

export const useClaudeSessionStore = create<ClaudeSessionStore>()(
  devtools(
    persist(
      subscribeWithSelector((set, get) => ({
      // Initial state
      connected: false,
      connecting: false,
      wsUrl: null,
      cwd: null,
      reconnectAttempts: 0,
      maxReconnectAttempts: RECONNECT_CONFIG.maxAttempts,
      reconnectDelay: RECONNECT_CONFIG.baseDelay,
      isReconnecting: false,
      running: false,
      sessionInfo: { ...initialSessionInfo },
      continueSession: true,
      permissionMode: "mcpProxy" as PermissionMode,
      agentType: "claude" as AgentType,
      selectedModels: { ...AGENT_DEFAULT_MODELS },
      geminiMode: "stream" as GeminiMode,
      messages: [],
      activeToolCalls: new Map(),
      completedToolCalls: [],
      totalInputTokens: 0,
      totalOutputTokens: 0,
      lastRequestDuration: null,
      lastError: null,
      connectionError: null,
      pendingPermission: null,
      permissionDenials: [],
      pendingToolApproval: null,
      pendingMCPApproval: null,
      ptySessionActive: false,
      pendingPTYPermission: null,
      ptyThinking: false,
      ptyMessages: [],
      toolUseCountInResponse: 0,
      writeToolUseCountInResponse: 0,
      planDescriptionOnly: false,
      executePlanAttempted: false,
      _ws: null,
      _reconnectTimeout: null,

      // Connect to WebSocket
      connect: (wsUrl: string) => {
        const state = get();

        // Clear any pending reconnect timeout
        if (state._reconnectTimeout) {
          clearTimeout(state._reconnectTimeout);
        }

        if (state._ws) {
          state._ws.close();
        }

        set({
          connecting: true,
          wsUrl,
          lastError: null,
          connectionError: null,
          _reconnectTimeout: null,
        });

        const ws = new WebSocket(wsUrl);

        ws.onopen = () => {
          log.info("WebSocket connected");
          set({
            connected: true,
            connecting: false,
            isReconnecting: false,
            reconnectAttempts: 0,
            reconnectDelay: RECONNECT_CONFIG.baseDelay,
            connectionError: null,
            _ws: ws,
          });
        };

        ws.onclose = (event) => {
          log.info("WebSocket closed:", event.code, event.reason);
          const currentState = get();

          set({
            connected: false,
            connecting: false,
            running: false,
            _ws: null,
            // Reset PTY state on disconnect to ensure clean slate for reconnection
            ptySessionActive: false,
            ptyThinking: false,
            pendingPTYPermission: null,
          });

          // Auto-reconnect if not intentionally disconnected (code 1000)
          // and we haven't exceeded max attempts
          if (event.code !== 1000 && currentState.wsUrl) {
            const attempts = currentState.reconnectAttempts;
            if (attempts < RECONNECT_CONFIG.maxAttempts) {
              const delay = Math.min(
                currentState.reconnectDelay * Math.pow(RECONNECT_CONFIG.backoffMultiplier, attempts),
                RECONNECT_CONFIG.maxDelay
              );

              log.info(`Reconnecting in ${delay}ms (attempt ${attempts + 1}/${RECONNECT_CONFIG.maxAttempts})`);

              set({
                isReconnecting: true,
                reconnectAttempts: attempts + 1,
                reconnectDelay: delay,
                connectionError: `Connection lost. Reconnecting in ${Math.round(delay / 1000)}s...`,
              });

              const timeout = setTimeout(() => {
                const s = get();
                if (s.wsUrl && !s.connected) {
                  s.connect(s.wsUrl);
                }
              }, delay);

              set({ _reconnectTimeout: timeout });
            } else {
              set({
                isReconnecting: false,
                connectionError: "Connection failed. Please check the backend and click Reconnect.",
              });
            }
          }
        };

        ws.onerror = (error) => {
          log.error("WebSocket error:", error);
          // Don't set error here - let onclose handle reconnection
          // Only set if we're not already in a reconnection cycle
          const currentState = get();
          if (!currentState.isReconnecting) {
            set({
              connectionError: "Connection error",
            });
          }
        };

        ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data) as ClaudeEvent;
            get().processEvent(data);
          } catch (e) {
            log.error("Failed to parse message:", e);
          }
        };

        set({ _ws: ws });
      },

      // Disconnect
      disconnect: () => {
        const { _ws, _reconnectTimeout } = get();

        // Clear any pending reconnect timeout
        if (_reconnectTimeout) {
          clearTimeout(_reconnectTimeout);
        }

        // Clear wsUrl FIRST to prevent auto-reconnect in onclose handler
        // The onclose handler checks: event.code !== 1000 && currentState.wsUrl
        // By clearing wsUrl before close, we ensure no reconnection attempt
        set({
          wsUrl: null,
          _reconnectTimeout: null,
          isReconnecting: false,
          reconnectAttempts: 0,
          reconnectDelay: RECONNECT_CONFIG.baseDelay,
          connectionError: null,
        });

        if (_ws) {
          _ws.close(1000, "Intentional disconnect");
        }

        set({
          connected: false,
          connecting: false,
          running: false,
          _ws: null,
        });
      },

      // Send a prompt
      sendPrompt: (prompt: string) => {
        const { _ws, connected, running, continueSession, permissionMode, agentType, selectedModels } = get();
        if (!_ws || !connected || running) {
          log.warn("Cannot send prompt: not ready");
          return;
        }

        // Get the selected model for the current agent type
        const model = selectedModels[agentType] || AGENT_DEFAULT_MODELS[agentType];

        const command: AgentCommand & { permission_mode?: string; model?: string } = {
          command: "run",
          prompt,
          continue: continueSession,
          permission_mode: permissionMode,
          model,
        };

        _ws.send(JSON.stringify(command));
        // Reset tool tracking for new response
        // Also reset executePlanAttempted since user is sending a new prompt
        set({ running: true, lastError: null, toolUseCountInResponse: 0, writeToolUseCountInResponse: 0, planDescriptionOnly: false, executePlanAttempted: false });

        // Add user message to history
        const userMessage: ClaudeMessage = {
          id: generateMessageId(),
          type: "text",
          role: "user",
          content: prompt,
          timestamp: new Date(),
        };

        set((state) => ({
          messages: [...state.messages, userMessage],
        }));
      },

      // Cancel running process
      cancel: () => {
        const { _ws, connected } = get();
        if (!_ws || !connected) return;

        const command: AgentCommand = { command: "cancel" };
        _ws.send(JSON.stringify(command));
      },

      // Start new session
      newSession: () => {
        const { _ws, connected } = get();
        if (!_ws || !connected) return;

        const command: AgentCommand = { command: "new_session" };
        _ws.send(JSON.stringify(command));

        // Clear local state
        set({
          messages: [],
          activeToolCalls: new Map(),
          completedToolCalls: [],
          sessionInfo: { ...initialSessionInfo },
          continueSession: false,
        });
      },

      // Request status
      requestStatus: () => {
        const { _ws, connected } = get();
        if (!_ws || !connected) return;

        const command: AgentCommand = { command: "status" };
        _ws.send(JSON.stringify(command));
      },

      // Clear messages
      clearMessages: () => {
        set({
          messages: [],
          activeToolCalls: new Map(),
          completedToolCalls: [],
        });
      },

      // Set error
      setError: (error: string | null) => {
        set({ lastError: error });
      },

      // Clear connection error
      clearConnectionError: () => {
        set({ connectionError: null });
      },

      // Set permission mode
      setPermissionMode: (mode: PermissionMode) => {
        set({ permissionMode: mode });
      },

      // Set agent type
      setAgentType: (type: AgentType) => {
        set({ agentType: type });
      },

      // Set selected model for an agent type
      setSelectedModel: (agentType: AgentType, model: string) => {
        set((state) => ({
          selectedModels: {
            ...state.selectedModels,
            [agentType]: model,
          },
        }));
      },

      // Get current selected model for active agent
      getCurrentModel: () => {
        const state = get();
        return state.selectedModels[state.agentType] || AGENT_DEFAULT_MODELS[state.agentType];
      },

      // Set Gemini execution mode
      setGeminiMode: (mode: GeminiMode) => {
        set({ geminiMode: mode });
      },

      // Respond to a permission request
      respondToPermission: (approved: boolean, always: boolean = false) => {
        const { _ws, connected, pendingPermission } = get();
        if (!_ws || !connected || !pendingPermission) {
          log.warn("Cannot respond to permission: not ready or no pending request");
          return;
        }

        const command: AgentCommand = {
          command: "permission_response",
          approved,
          always,
        };

        _ws.send(JSON.stringify(command));
        log.debug(`Permission response sent: approved=${approved}, always=${always}`);

        // Clear pending permission
        set({ pendingPermission: null });
      },

      // Clear permission denials
      clearPermissionDenials: () => {
        set({ permissionDenials: [] });
      },

      // Respond to a tool approval request
      respondToToolApproval: (approved: boolean, feedback?: string) => {
        const { _ws, connected, pendingToolApproval } = get();
        if (!_ws || !connected || !pendingToolApproval) {
          log.warn("Cannot respond to tool approval: not ready or no pending request");
          return;
        }

        const command: AgentCommand = {
          command: "tool_approval_response",
          request_id: pendingToolApproval.requestId,
          approved,
          feedback,
        };

        _ws.send(JSON.stringify(command));
        log.debug(`Tool approval response sent: approved=${approved}, feedback=${feedback}`);

        // Clear pending approval
        set({ pendingToolApproval: null });
      },

      // Clear pending tool approval (e.g., on cancel)
      clearPendingToolApproval: () => {
        set({ pendingToolApproval: null });
      },

      // Respond to an MCP approval request (DEPRECATED - kept for future compatibility)
      respondToMCPApproval: (approved: boolean, message?: string, updatedInput?: Record<string, unknown>) => {
        const { _ws, connected, pendingMCPApproval } = get();
        if (!_ws || !connected || !pendingMCPApproval) {
          log.warn("Cannot respond to MCP approval: not ready or no pending request");
          return;
        }

        const command: AgentCommand = {
          command: "mcp_approval_response",
          request_id: pendingMCPApproval.requestId,
          approved,
          message,
          updated_input: updatedInput,
        };

        _ws.send(JSON.stringify(command));
        log.debug(`MCP approval response sent: approved=${approved}, message=${message}`);

        // Clear pending approval
        set({ pendingMCPApproval: null });
      },

      // Clear pending MCP approval (e.g., on cancel)
      clearPendingMCPApproval: () => {
        set({ pendingMCPApproval: null });
      },

      // PTY Mode Actions
      startPTYSession: () => {
        const { _ws, connected } = get();
        if (!_ws || !connected) {
          log.warn("Cannot start PTY session: not connected");
          return;
        }

        _ws.send(JSON.stringify({ command: "start" }));
        log.debug("PTY session start requested");
      },

      stopPTYSession: () => {
        const { _ws, connected } = get();
        if (!_ws || !connected) return;

        _ws.send(JSON.stringify({ command: "stop" }));
        set({
          ptySessionActive: false,
          ptyThinking: false,
          pendingPTYPermission: null,
        });
        log.debug("PTY session stop requested");
      },

      sendPTYPrompt: (prompt: string) => {
        const { _ws, connected, ptySessionActive, running } = get();
        if (!_ws || !connected) {
          log.warn("Cannot send PTY prompt: not connected");
          return;
        }
        if (!ptySessionActive) {
          log.warn("Cannot send PTY prompt: no active PTY session");
          return;
        }
        if (running) {
          log.warn("Cannot send PTY prompt: already running");
          return;
        }

        _ws.send(JSON.stringify({ command: "run", prompt }));
        set({ running: true, ptyThinking: true, lastError: null });

        // Add user message to history
        const userMessage: ClaudeMessage = {
          id: generateMessageId(),
          type: "text",
          role: "user",
          content: prompt,
          timestamp: new Date(),
        };

        set((state) => ({
          messages: [...state.messages, userMessage],
        }));

        log.debug("PTY prompt sent");
      },

      respondToPTYPermission: (response: "approve" | "deny" | "always_allow") => {
        const { _ws, connected, pendingPTYPermission } = get();
        if (!_ws || !connected) {
          log.warn("Cannot respond to PTY permission: not connected");
          return;
        }

        // Map response to command
        const command = response === "approve" ? "approve"
          : response === "deny" ? "deny"
          : "always_allow";

        _ws.send(JSON.stringify({ command }));
        set({ pendingPTYPermission: null });
        log.debug(`PTY permission response sent: ${response}`);
      },

      cancelPTY: () => {
        const { _ws, connected } = get();
        if (!_ws || !connected) return;

        _ws.send(JSON.stringify({ command: "cancel" }));
        log.debug("PTY cancel requested");
      },

      clearPTYMessages: () => {
        set({ ptyMessages: [] });
      },

      // Execute Plan action (for toolApproval mode)
      // Sends a message to Claude asking it to execute the described changes
      // IMPORTANT: We switch to bypassPermissions mode for execution because
      // plan mode doesn't emit tool_use events for write operations
      executePlan: () => {
        const { _ws, connected, running, continueSession } = get();
        if (!_ws || !connected || running) {
          log.warn("Cannot execute plan: not ready");
          return;
        }

        // Clear the plan description flag and reset tool tracking
        // Mark that we attempted to execute so we don't show banner again if Claude still describes
        set({ planDescriptionOnly: false, toolUseCountInResponse: 0, writeToolUseCountInResponse: 0, executePlanAttempted: true });

        // Send a prompt asking Claude to execute
        // Use bypassPermissions mode so Claude actually executes the tools
        const executePrompt = "Please proceed with the changes you described. Execute the tools now.";

        const command: AgentCommand & { permission_mode?: string } = {
          command: "run",
          prompt: executePrompt,
          continue: continueSession,
          // Switch to bypassPermissions for actual execution
          permission_mode: "bypassPermissions",
        };

        _ws.send(JSON.stringify(command));
        set({ running: true, lastError: null });

        // Add the execute prompt to message history
        const userMessage: ClaudeMessage = {
          id: generateMessageId(),
          type: "system",
          role: "assistant",
          content: "Executing plan with auto-approve mode...",
          timestamp: new Date(),
        };

        set((state) => ({
          messages: [...state.messages, userMessage],
        }));

        log.debug("Execute plan command sent");
      },

      // Clear plan description only flag
      clearPlanDescriptionOnly: () => {
        set({ planDescriptionOnly: false, toolUseCountInResponse: 0, writeToolUseCountInResponse: 0, executePlanAttempted: false });
      },

      // Process incoming event
      processEvent: (event: ClaudeEvent) => {
        set((state) => {
          // Handle connection event
          if (event.type === "connected") {
            return {
              cwd: (event as { cwd: string }).cwd,
            };
          }

          // Handle system init
          if (isSystemInitEvent(event)) {
            const content = event.content;
            return {
              sessionInfo: {
                sessionId: content.session_id,
                model: content.model,
                tools: content.tools,
                mcpServers: content.mcp_servers,
              },
              continueSession: true, // Reset for next run
            };
          }

          // Handle text message
          if (isTextEvent(event)) {
            const message: ClaudeMessage = {
              id: generateMessageId(),
              type: "text",
              role: "assistant",
              content: event.content,
              timestamp: new Date(),
              usage: event.usage,
            };
            // Accumulate token usage if present
            const inputTokens = event.usage?.input_tokens ?? 0;
            const outputTokens = event.usage?.output_tokens ?? 0;
            return {
              messages: [...state.messages, message],
              totalInputTokens: state.totalInputTokens + inputTokens,
              totalOutputTokens: state.totalOutputTokens + outputTokens,
            };
          }

          // Handle tool use
          if (isToolUseEvent(event)) {
            const toolCall: ToolCall = {
              id: event.content.id,
              name: event.content.name,
              input: event.content.input,
              startTime: new Date(),
              status: "running",
            };

            const message: ClaudeMessage = {
              id: generateMessageId(),
              type: "tool_use",
              role: "assistant",
              content: event.content,
              timestamp: new Date(),
              toolName: event.content.name,
              toolId: event.content.id,
              usage: event.usage,
            };

            const newActiveToolCalls = new Map(state.activeToolCalls);
            newActiveToolCalls.set(toolCall.id, toolCall);

            // Track tool_use events in this response
            // Also track specifically Write/Edit/Bash tools for plan execution detection
            const WRITE_TOOLS = ['Write', 'Edit', 'Bash', 'MultiEdit', 'NotebookEdit'];
            const isWriteTool = WRITE_TOOLS.includes(event.content.name);

            return {
              messages: [...state.messages, message],
              activeToolCalls: newActiveToolCalls,
              toolUseCountInResponse: state.toolUseCountInResponse + 1,
              writeToolUseCountInResponse: state.writeToolUseCountInResponse + (isWriteTool ? 1 : 0),
            };
          }

          // Handle tool result
          if (isToolResultEvent(event)) {
            const toolId = event.content.tool_use_id;
            const existingToolCall = state.activeToolCalls.get(toolId);

            const message: ClaudeMessage = {
              id: generateMessageId(),
              type: "tool_result",
              role: "assistant",
              content: event.content.content,
              timestamp: new Date(),
              toolId,
              isError: event.content.is_error,
            };

            const newActiveToolCalls = new Map(state.activeToolCalls);
            let newCompletedToolCalls = [...state.completedToolCalls];

            if (existingToolCall) {
              const completedToolCall: ToolCall = {
                ...existingToolCall,
                endTime: new Date(),
                result: event.content.content,
                isError: event.content.is_error,
                status: event.content.is_error ? "failed" : "completed",
              };
              newActiveToolCalls.delete(toolId);
              newCompletedToolCalls.push(completedToolCall);
            }

            return {
              messages: [...state.messages, message],
              activeToolCalls: newActiveToolCalls,
              completedToolCalls: newCompletedToolCalls,
            };
          }

          // Handle done
          if (isDoneEvent(event)) {
            // Check if we're in toolApproval mode and no WRITE tool_use events were emitted
            // This means Claude read files but only described modifications (didn't emit Edit/Write)
            // We track Write/Edit/Bash specifically because Read tools work fine in plan mode
            // IMPORTANT: Don't show banner if we already attempted to execute (prevents infinite loop)
            const inToolApprovalMode = state.permissionMode === "toolApproval";
            const noWriteToolsUsed = state.writeToolUseCountInResponse === 0;
            const alreadyAttempted = state.executePlanAttempted;
            const shouldShowExecutePlan = inToolApprovalMode && noWriteToolsUsed && !alreadyAttempted;

            log.debug(`Done event: toolApprovalMode=${inToolApprovalMode}, totalToolUseCount=${state.toolUseCountInResponse}, writeToolUseCount=${state.writeToolUseCountInResponse}, alreadyAttempted=${alreadyAttempted}, planDescriptionOnly=${shouldShowExecutePlan}`);

            return {
              running: false,
              planDescriptionOnly: shouldShowExecutePlan,
            };
          }

          // Handle error
          if (isErrorEvent(event)) {
            // Support both standard format (content) and legacy PTY format (data.message)
            // Use type-safe extraction for legacy format compatibility
            const eventRecord = event as unknown as Record<string, unknown>;
            const legacyData = eventRecord.data;
            const legacyMessage = typeof legacyData === "object" && legacyData !== null
              ? (legacyData as Record<string, unknown>).message
              : undefined;
            const errorContent = event.content ||
              (typeof legacyMessage === "string" ? legacyMessage : undefined) ||
              "Unknown error";
            const message: ClaudeMessage = {
              id: generateMessageId(),
              type: "error",
              role: "assistant",
              content: errorContent,
              timestamp: new Date(),
              isError: true,
            };
            return {
              messages: [...state.messages, message],
              lastError: errorContent,
              running: false,
            };
          }

          // Handle cancelled
          if (event.type === "cancelled") {
            return {
              running: false,
            };
          }

          // Handle session reset
          if (event.type === "session_reset") {
            return {
              sessionInfo: { ...initialSessionInfo },
              continueSession: false,
            };
          }

          // Handle session broken (tools executed locally in toolApproval mode)
          // This means we cannot continue the session - need to start fresh
          if (event.type === "session_broken") {
            log.info("Session broken:", (event as { reason?: string }).reason);
            // Note: We set continueSession to false, and the backend already
            // resets its continue_session flag. This ensures next prompt starts fresh.
            return {
              continueSession: false,
            };
          }

          // Handle status
          if (event.type === "status") {
            const statusEvent = event as {
              session_info: {
                session_id: string | null;
                model: string | null;
                tools: string[];
                mcp_servers: Array<{ name: string; status: string }>;
              };
              running: boolean;
              continue_session: boolean;
            };
            return {
              sessionInfo: {
                sessionId: statusEvent.session_info.session_id,
                model: statusEvent.session_info.model,
                tools: statusEvent.session_info.tools,
                mcpServers: statusEvent.session_info.mcp_servers,
              },
              running: statusEvent.running,
              continueSession: statusEvent.continue_session,
            };
          }

          // Handle permission request
          if (isPermissionRequestEvent(event)) {
            log.debug("Permission request received:", event);
            return {
              pendingPermission: {
                requestId: event.request_id,
                tool: event.tool,
                input: event.input,
                timestamp: new Date(),
              },
            };
          }

          // Handle tool approval request (toolApproval mode)
          if (isToolApprovalRequestEvent(event)) {
            log.debug("Tool approval request received:", event);
            return {
              pendingToolApproval: {
                requestId: event.request_id,
                toolName: event.tool_name,
                toolInput: event.tool_input,
                toolUseId: event.tool_use_id,
                previewType: event.preview_type,
                previewData: event.preview_data,
                filePath: event.file_path,
                originalContent: event.original_content,
                newContent: event.new_content,
                diffLines: event.diff_lines,
                timestamp: new Date(),
              },
            };
          }

          // Handle MCP approval request (DEPRECATED - kept for future compatibility)
          if (isMCPApprovalRequestEvent(event)) {
            log.debug("MCP approval request received:", event);
            return {
              pendingMCPApproval: {
                requestId: event.request_id,
                toolName: event.tool_name,
                toolInput: event.tool_input,
                context: event.context,
                previewType: event.preview_type,
                previewData: event.preview_data,
                filePath: event.file_path,
                originalContent: event.original_content,
                newContent: event.new_content,
                diffLines: event.diff_lines,
                timestamp: new Date(),
              },
            };
          }

          // Handle result event with permission denials
          if (isResultEvent(event)) {
            const updates: Partial<ClaudeSessionStore> = {
              running: false,
            };

            // Track duration if available
            if (event.duration_ms) {
              updates.lastRequestDuration = event.duration_ms;
            }

            // Accumulate token usage if present
            if (event.usage) {
              const inputTokens = event.usage.input_tokens ?? 0;
              const outputTokens = event.usage.output_tokens ?? 0;
              updates.totalInputTokens = state.totalInputTokens + inputTokens;
              updates.totalOutputTokens = state.totalOutputTokens + outputTokens;
            }

            // Capture permission denials
            if (hasPermissionDenials(event)) {
              log.debug("Permission denials detected:", event.permission_denials);
              // Add new denials to existing list, avoiding duplicates by tool_use_id
              const existingIds = new Set(state.permissionDenials.map(d => d.tool_use_id));
              const newDenials = event.permission_denials.filter(d => !existingIds.has(d.tool_use_id));
              updates.permissionDenials = [...state.permissionDenials, ...newDenials];
            }

            // Handle result content - show both errors and successful command output
            if (event.result && event.result.trim()) {
              if (event.is_error) {
                const message: ClaudeMessage = {
                  id: generateMessageId(),
                  type: "error",
                  role: "assistant",
                  content: event.result,
                  timestamp: new Date(),
                  isError: true,
                };
                updates.messages = [...state.messages, message];
                updates.lastError = event.result;
              } else {
                // Show successful result (e.g., from slash commands like /memory, /status)
                const message: ClaudeMessage = {
                  id: generateMessageId(),
                  type: "system",
                  role: "assistant",
                  content: event.result,
                  timestamp: new Date(),
                };
                updates.messages = [...state.messages, message];
              }
            }

            return updates;
          }

          // Handle PTY session started
          if (event.type === "session_started") {
            log.debug("PTY session started");
            return {
              ptySessionActive: true,
              ptyThinking: false,
            };
          }

          // Handle PTY session ended
          if (event.type === "session_ended") {
            log.debug("PTY session ended");
            return {
              ptySessionActive: false,
              ptyThinking: false,
              running: false,
              pendingPTYPermission: null,
            };
          }

          // Handle PTY thinking
          if (event.type === "thinking") {
            return {
              ptyThinking: true,
              running: true,
            };
          }

          // Handle PTY message
          if (event.type === "message") {
            const ptyEvent = event as { data?: { content?: string }; raw_text?: string };
            const content = ptyEvent.data?.content || ptyEvent.raw_text || "";
            if (content) {
              // Add as a regular text message
              const message: ClaudeMessage = {
                id: generateMessageId(),
                type: "text",
                role: "assistant",
                content: content,
                timestamp: new Date(),
              };
              return {
                messages: [...state.messages, message],
                ptyMessages: [...state.ptyMessages, content],
              };
            }
            return {};
          }

          // Handle PTY completion
          if (event.type === "completion") {
            log.debug("PTY completion received");
            return {
              ptyThinking: false,
              running: false,
            };
          }

          // Handle PTY permission request (from PTY mode with data field)
          if (event.type === "permission_request" && "data" in event) {
            const ptyEvent = event as {
              data?: {
                permission_type?: string;
                target?: string;
                full_text?: string;
              };
              raw_text?: string;
            };
            log.debug("PTY permission request received:", ptyEvent);
            return {
              pendingPTYPermission: {
                permissionType: ptyEvent.data?.permission_type || "generic",
                target: ptyEvent.data?.target,
                fullText: ptyEvent.data?.full_text || ptyEvent.raw_text || "Permission required",
                rawText: ptyEvent.raw_text,
                timestamp: new Date(),
              },
            };
          }

          return {};
        });
      },

      // Getters
      getActiveToolCall: () => {
        const state = get();
        const entries = Array.from(state.activeToolCalls.values());
        return entries[entries.length - 1];
      },

      getMessagesByType: (type: ClaudeMessage["type"]) => {
        const state = get();
        return state.messages.filter((m) => m.type === type);
      },

      getToolCallById: (id: string) => {
        const state = get();
        return (
          state.activeToolCalls.get(id) ||
          state.completedToolCalls.find((tc) => tc.id === id)
        );
      },
    })),
      {
        name: "claude-agent-settings",
        partialize: (state) => ({
          agentType: state.agentType,
          permissionMode: state.permissionMode,
          selectedModels: state.selectedModels,
          geminiMode: state.geminiMode,
        }),
      }
    ),
    {
      name: "claude-session-store",
    }
  )
);

// ============================================================================
// Selectors (for performance)
// ============================================================================

export const selectConnected = (state: ClaudeSessionStore) => state.connected;
export const selectRunning = (state: ClaudeSessionStore) => state.running;
export const selectMessages = (state: ClaudeSessionStore) => state.messages;
export const selectSessionInfo = (state: ClaudeSessionStore) =>
  state.sessionInfo;
export const selectLastError = (state: ClaudeSessionStore) => state.lastError;
export const selectActiveToolCalls = (state: ClaudeSessionStore) =>
  state.activeToolCalls;
export const selectPendingPermission = (state: ClaudeSessionStore) =>
  state.pendingPermission;
export const selectPermissionDenials = (state: ClaudeSessionStore) =>
  state.permissionDenials;
export const selectPendingToolApproval = (state: ClaudeSessionStore) =>
  state.pendingToolApproval;
export const selectPendingMCPApproval = (state: ClaudeSessionStore) =>
  state.pendingMCPApproval;
export const selectPTYSessionActive = (state: ClaudeSessionStore) =>
  state.ptySessionActive;
export const selectPendingPTYPermission = (state: ClaudeSessionStore) =>
  state.pendingPTYPermission;
export const selectPTYThinking = (state: ClaudeSessionStore) =>
  state.ptyThinking;
export const selectPermissionMode = (state: ClaudeSessionStore) =>
  state.permissionMode;
export const selectAgentType = (state: ClaudeSessionStore) =>
  state.agentType;
export const selectPlanDescriptionOnly = (state: ClaudeSessionStore) =>
  state.planDescriptionOnly;
export const selectToolUseCountInResponse = (state: ClaudeSessionStore) =>
  state.toolUseCountInResponse;
export const selectGeminiMode = (state: ClaudeSessionStore) =>
  state.geminiMode;
