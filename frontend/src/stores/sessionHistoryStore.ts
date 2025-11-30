/**
 * Session History Store
 *
 * Manages Claude Agent session history with localStorage persistence.
 * Stores conversation snapshots for quick access to past sessions.
 */

import { create } from "zustand";
import { persist } from "zustand/middleware";
import { ClaudeMessage } from "../types/claude-events";
import { type AgentType } from "./claudeSessionStore";

// ============================================================================
// Types
// ============================================================================

// Serialized message type for storage (timestamp as string)
interface SerializedMessage extends Omit<ClaudeMessage, "timestamp"> {
  timestamp: string;
}

// Internal serialized format for storage
interface SerializedSessionSnapshot {
  id: string;
  sessionId: string | null;
  model: string | null;
  agentType: AgentType;
  title: string;
  preview: string;
  messageCount: number;
  createdAt: string;
  updatedAt: string;
  messages: SerializedMessage[];
}

// Public interface with proper Date types
export interface SessionSnapshot {
  id: string;
  sessionId: string | null;
  model: string | null;
  agentType: AgentType;
  title: string;
  preview: string;
  messageCount: number;
  createdAt: string;
  updatedAt: string;
  messages: ClaudeMessage[];
}

interface SessionHistoryState {
  // Internal state uses serialized format for localStorage compatibility
  sessions: SerializedSessionSnapshot[];
  currentSessionId: string | null;
  sidebarOpen: boolean;

  // Actions
  saveSession: (
    sessionId: string | null,
    model: string | null,
    agentType: AgentType,
    messages: ClaudeMessage[]
  ) => string;
  loadSession: (id: string) => SessionSnapshot | null;
  getSessionsByAgent: (agentType: AgentType) => SessionSnapshot[];
  deleteSession: (id: string) => void;
  clearAllSessions: () => void;
  clearSessionsByAgent: (agentType: AgentType) => void;
  setCurrentSessionId: (id: string | null) => void;
  toggleSidebar: () => void;
  setSidebarOpen: (open: boolean) => void;
}

// ============================================================================
// Helpers
// ============================================================================

function generateSessionId(): string {
  return `session_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`;
}

function generateTitle(messages: ClaudeMessage[]): string {
  // Find first user message (text type that looks like user input)
  const firstUserMessage = messages.find(
    (m) => m.type === "text" && typeof m.content === "string"
  );

  if (firstUserMessage && typeof firstUserMessage.content === "string") {
    const content = firstUserMessage.content;
    // Truncate to first 50 chars or first line
    const firstLine = content.split("\n")[0];
    return firstLine.length > 50 ? firstLine.slice(0, 47) + "..." : firstLine;
  }

  return "New Session";
}

function generatePreview(messages: ClaudeMessage[]): string {
  // Get last text message from assistant
  const lastAssistantMessage = [...messages]
    .reverse()
    .find((m) => m.type === "text" && typeof m.content === "string");

  if (lastAssistantMessage && typeof lastAssistantMessage.content === "string") {
    const content = lastAssistantMessage.content;
    return content.length > 100 ? content.slice(0, 97) + "..." : content;
  }

  return "No messages";
}

// Serialize messages for storage (convert Date to string)
function serializeMessages(messages: ClaudeMessage[]): SerializedMessage[] {
  return messages.map((m) => ({
    ...m,
    timestamp: m.timestamp instanceof Date ? m.timestamp.toISOString() : String(m.timestamp),
  }));
}

// Deserialize messages from storage (convert string to Date)
function deserializeMessages(messages: SerializedMessage[]): ClaudeMessage[] {
  return messages.map((m) => ({
    ...m,
    timestamp: new Date(m.timestamp),
  }));
}

// ============================================================================
// Store
// ============================================================================

export const useSessionHistoryStore = create<SessionHistoryState>()(
  persist(
    (set, get) => ({
      sessions: [],
      currentSessionId: null,
      sidebarOpen: false,

      saveSession: (sessionId, model, agentType, messages) => {
        if (messages.length === 0) {
          return get().currentSessionId || generateSessionId();
        }

        const state = get();
        const now = new Date().toISOString();
        const existingIndex = state.sessions.findIndex(
          (s) => s.id === state.currentSessionId
        );

        const snapshot: SerializedSessionSnapshot = {
          id: state.currentSessionId || generateSessionId(),
          sessionId,
          model,
          agentType,
          title: generateTitle(messages),
          preview: generatePreview(messages),
          messageCount: messages.length,
          createdAt: existingIndex >= 0 ? state.sessions[existingIndex].createdAt : now,
          updatedAt: now,
          messages: serializeMessages(messages),
        };

        if (existingIndex >= 0) {
          // Update existing session
          const newSessions = [...state.sessions];
          newSessions[existingIndex] = snapshot;
          set({ sessions: newSessions, currentSessionId: snapshot.id });
        } else {
          // Add new session at the beginning
          set({
            sessions: [snapshot, ...state.sessions].slice(0, 50), // Keep max 50 sessions
            currentSessionId: snapshot.id,
          });
        }

        return snapshot.id;
      },

      loadSession: (id) => {
        const session = get().sessions.find((s) => s.id === id);
        if (session) {
          return {
            ...session,
            messages: deserializeMessages(session.messages),
          };
        }
        return null;
      },

      getSessionsByAgent: (agentType) => {
        return get()
          .sessions.filter((s) => s.agentType === agentType)
          .map((s) => ({
            ...s,
            messages: deserializeMessages(s.messages),
          }));
      },

      deleteSession: (id) => {
        set((state) => ({
          sessions: state.sessions.filter((s) => s.id !== id),
          currentSessionId: state.currentSessionId === id ? null : state.currentSessionId,
        }));
      },

      clearAllSessions: () => {
        set({ sessions: [], currentSessionId: null });
      },

      clearSessionsByAgent: (agentType) => {
        set((state) => ({
          sessions: state.sessions.filter((s) => s.agentType !== agentType),
          currentSessionId: null,
        }));
      },

      setCurrentSessionId: (id) => {
        set({ currentSessionId: id });
      },

      toggleSidebar: () => {
        set((state) => ({ sidebarOpen: !state.sidebarOpen }));
      },

      setSidebarOpen: (open) => {
        set({ sidebarOpen: open });
      },
    }),
    {
      name: "claude-session-history",
      version: 1,
      partialize: (state) => ({
        sessions: state.sessions,
        sidebarOpen: state.sidebarOpen,
      }),
      migrate: (persistedState, version) => {
        const state = persistedState as { sessions: SerializedSessionSnapshot[]; sidebarOpen: boolean };
        if (version === 0) {
          // Migration v0 -> v1: Remove sessions without agentType (legacy sessions)
          state.sessions = state.sessions.filter(
            (s) => s.agentType != null && s.agentType !== undefined
          );
        }
        return state;
      },
    }
  )
);
