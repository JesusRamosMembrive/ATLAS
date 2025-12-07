/**
 * Agent Configuration Store
 *
 * Manages AI Agent (Claude, Codex, Gemini) selection using Zustand.
 * All agents run via Socket.IO terminal - this store only handles agent type preference.
 */

import { create } from "zustand";
import { devtools, persist } from "zustand/middleware";

// ============================================================================
// Agent Types
// ============================================================================

export type AgentType = "claude" | "codex" | "gemini";

export const AGENT_TYPES: AgentType[] = ["claude", "codex", "gemini"];

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

// CLI command for each agent
export const AGENT_CLI_COMMANDS: Record<AgentType, string> = {
  claude: "claude",
  codex: "codex",
  gemini: "gemini",
};

// ============================================================================
// Slash Commands (for reference in UI)
// ============================================================================

export interface SlashCommand {
  command: string;
  label: string;
  description: string;
  hasArgs?: boolean;
  argPlaceholder?: string;
}

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

export const CODEX_SLASH_COMMANDS: SlashCommand[] = [
  { command: "/clear", label: "Clear", description: "Clear conversation history" },
  { command: "/help", label: "Help", description: "Show available commands" },
  { command: "/model", label: "Model", description: "Change the model", hasArgs: true, argPlaceholder: "<model-name>" },
  { command: "/status", label: "Status", description: "View session status" },
];

export const GEMINI_SLASH_COMMANDS: SlashCommand[] = [
  { command: "/clear", label: "Clear", description: "Clear conversation history" },
  { command: "/help", label: "Help", description: "Show available commands" },
  { command: "/status", label: "Status", description: "View session status" },
];

export const AGENT_SLASH_COMMANDS: Record<AgentType, SlashCommand[]> = {
  claude: CLAUDE_SLASH_COMMANDS,
  codex: CODEX_SLASH_COMMANDS,
  gemini: GEMINI_SLASH_COMMANDS,
};

// ============================================================================
// Store Interface
// ============================================================================

interface AgentConfigStore {
  agentType: AgentType;
  setAgentType: (type: AgentType) => void;
  getCliCommand: () => string;
}

// ============================================================================
// Store Implementation
// ============================================================================

export const useClaudeSessionStore = create<AgentConfigStore>()(
  devtools(
    persist(
      (set, get) => ({
        agentType: "claude" as AgentType,

        setAgentType: (type: AgentType) => {
          set({ agentType: type });
        },

        getCliCommand: () => {
          return AGENT_CLI_COMMANDS[get().agentType];
        },
      }),
      {
        name: "agent-config-settings",
        partialize: (state) => ({
          agentType: state.agentType,
        }),
      }
    ),
    {
      name: "agent-config-store",
    }
  )
);

// ============================================================================
// Selectors
// ============================================================================

export const selectAgentType = (state: AgentConfigStore) => state.agentType;
