import { create } from "zustand";
import { persist } from "zustand/middleware";
import {
  createChatSession,
  deleteChatSession,
  fetchChatMessages,
  listChatSessions,
  saveChatMessage,
} from "../lib/api";

export interface ChatStoredMessage {
  role: "user" | "assistant";
  text: string;
  dataUsed?: { type: string; value: string }[];
  followUps?: string[];
  createdAt: string;
  /** Set once persisted to the backend. */
  remoteId?: string;
}

export interface ChatSessionState {
  id: string;
  label: string;
  settlementPeriod: string | null;
  messages: ChatStoredMessage[];
  createdAt: string;
  updatedAt: string;
  /** True for sessions that exist locally only (offline create). */
  local?: boolean;
}

interface ChatStore {
  sessions: Record<string, ChatSessionState>;
  activeSessionId: string | null;
  hydrated: boolean;

  hydrateFromServer: () => Promise<void>;
  createSession: (label: string, period?: string | null) => Promise<string>;
  setActiveSession: (sessionId: string | null) => void;
  addMessage: (sessionId: string, message: ChatStoredMessage) => void;
  clearSession: (sessionId: string) => void;
  deleteSession: (sessionId: string) => Promise<void>;
  loadMessagesIfNeeded: (sessionId: string) => Promise<void>;
}

const nowIso = () => new Date().toISOString();

const localId = () =>
  `local-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;

export const useChatStore = create<ChatStore>()(
  persist(
    (set, get) => ({
      sessions: {},
      activeSessionId: null,
      hydrated: false,

      hydrateFromServer: async () => {
        try {
          const remote = await listChatSessions();
          set((state) => {
            const merged: Record<string, ChatSessionState> = { ...state.sessions };
            remote.forEach((r) => {
              const existing = merged[r.id];
              merged[r.id] = {
                id: r.id,
                label: r.label ?? "Untitled chat",
                settlementPeriod: r.settlement_period,
                messages: existing?.messages ?? [],
                createdAt: r.created_at,
                updatedAt: r.updated_at,
                local: false,
              };
            });
            return { sessions: merged, hydrated: true };
          });
        } catch {
          set({ hydrated: true });
        }
      },

      createSession: async (label, period = null) => {
        try {
          const remote = await createChatSession(label, period ?? undefined);
          set((state) => ({
            sessions: {
              ...state.sessions,
              [remote.id]: {
                id: remote.id,
                label: remote.label ?? label,
                settlementPeriod: remote.settlement_period,
                messages: [],
                createdAt: remote.created_at,
                updatedAt: remote.updated_at,
                local: false,
              },
            },
            activeSessionId: remote.id,
          }));
          return remote.id;
        } catch {
          const id = localId();
          const t = nowIso();
          set((state) => ({
            sessions: {
              ...state.sessions,
              [id]: {
                id,
                label,
                settlementPeriod: period,
                messages: [],
                createdAt: t,
                updatedAt: t,
                local: true,
              },
            },
            activeSessionId: id,
          }));
          return id;
        }
      },

      setActiveSession: (sessionId) => set({ activeSessionId: sessionId }),

      addMessage: (sessionId, message) => {
        const state = get();
        const session = state.sessions[sessionId];
        if (!session) return;
        const updated: ChatSessionState = {
          ...session,
          messages: [...session.messages, message],
          updatedAt: message.createdAt,
        };
        set({ sessions: { ...state.sessions, [sessionId]: updated } });

        // Fire-and-forget backend persistence (skip for local-only sessions).
        if (!session.local) {
          saveChatMessage(sessionId, message.role, message.text).catch(() => {
            /* swallow — UI already shows the message */
          });
        }
      },

      clearSession: (sessionId) => {
        const state = get();
        const session = state.sessions[sessionId];
        if (!session) return;
        set({
          sessions: {
            ...state.sessions,
            [sessionId]: { ...session, messages: [], updatedAt: nowIso() },
          },
        });
        // Backend "clear" is implemented as delete + recreate of messages on
        // the next save, but we don't need to wipe historical rows here —
        // newly added messages will continue to append. To truly purge on
        // the server, callers can deleteSession + createSession instead.
      },

      deleteSession: async (sessionId) => {
        const state = get();
        const wasActive = state.activeSessionId === sessionId;
        const session = state.sessions[sessionId];
        const { [sessionId]: _omit, ...rest } = state.sessions;
        set({
          sessions: rest,
          activeSessionId: wasActive ? null : state.activeSessionId,
        });
        if (session && !session.local) {
          try {
            await deleteChatSession(sessionId);
          } catch {
            /* best-effort */
          }
        }
      },

      loadMessagesIfNeeded: async (sessionId) => {
        const state = get();
        const session = state.sessions[sessionId];
        if (!session || session.local) return;
        if (session.messages.length > 0) return;
        try {
          const rows = await fetchChatMessages(sessionId);
          const messages: ChatStoredMessage[] = rows.map((r) => ({
            role: r.role,
            text: r.content,
            createdAt: r.created_at,
            remoteId: r.id,
          }));
          set((s) => ({
            sessions: {
              ...s.sessions,
              [sessionId]: { ...s.sessions[sessionId], messages },
            },
          }));
        } catch {
          /* ignore */
        }
      },
    }),
    {
      name: "sellerlens-chat-store",
      partialize: (state) => ({
        sessions: state.sessions,
        activeSessionId: state.activeSessionId,
      }),
    },
  ),
);

export function useActiveChatSession(): ChatSessionState | null {
  return useChatStore((s) =>
    s.activeSessionId ? s.sessions[s.activeSessionId] ?? null : null,
  );
}
