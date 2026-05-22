import { useEffect, useState } from "react";
import { MessageSquarePlus, Trash2 } from "lucide-react";
import {
  useChatStore,
  type ChatSessionState,
} from "../store/useChatStore";
import { useActivePeriod } from "../store/useAppStore";

function formatDate(iso: string): string {
  try {
    const d = new Date(iso);
    return d.toLocaleDateString(undefined, {
      month: "short",
      day: "numeric",
    });
  } catch {
    return "";
  }
}

export default function ConversationSidebar() {
  const sessionsMap = useChatStore((s) => s.sessions);
  const activeSessionId = useChatStore((s) => s.activeSessionId);
  const setActiveSession = useChatStore((s) => s.setActiveSession);
  const createSession = useChatStore((s) => s.createSession);
  const deleteSession = useChatStore((s) => s.deleteSession);
  const loadMessagesIfNeeded = useChatStore((s) => s.loadMessagesIfNeeded);
  const active = useActivePeriod();
  const [pendingDelete, setPendingDelete] = useState<string | null>(null);

  // Auto-load messages when active changes.
  useEffect(() => {
    if (activeSessionId) {
      loadMessagesIfNeeded(activeSessionId).catch(() => undefined);
    }
  }, [activeSessionId, loadMessagesIfNeeded]);

  const sessions: ChatSessionState[] = Object.values(sessionsMap).sort(
    (a, b) => (b.updatedAt || "").localeCompare(a.updatedAt || ""),
  );

  const handleNew = async () => {
    const period = active?.upload.summary?.payment_duration ?? null;
    const label = period ? `${period} Analysis` : "New chat";
    await createSession(label, period);
  };

  const handleDelete = async (id: string) => {
    setPendingDelete(null);
    await deleteSession(id);
  };

  return (
    <aside className="flex flex-col h-full bg-white rounded-xl border border-slate-200 w-64 shrink-0">
      <div className="p-3 border-b border-slate-200">
        <button
          onClick={handleNew}
          className="w-full flex items-center justify-center gap-2 bg-brand-green text-white rounded-lg px-3 py-2 text-sm font-medium hover:bg-emerald-700"
        >
          <MessageSquarePlus size={14} /> New Chat
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-2 space-y-1">
        {sessions.length === 0 && (
          <p className="text-xs text-slate-400 text-center mt-4 px-2">
            No conversations yet. Start a new chat above.
          </p>
        )}
        {sessions.map((s) => {
          const isActive = s.id === activeSessionId;
          return (
            <div
              key={s.id}
              className={`group rounded-lg px-2 py-2 cursor-pointer text-sm border ${
                isActive
                  ? "bg-emerald-50 border-emerald-200"
                  : "border-transparent hover:bg-slate-50"
              }`}
              onClick={() => setActiveSession(s.id)}
            >
              <div className="flex items-start justify-between gap-2">
                <div className="min-w-0 flex-1">
                  <div className="font-medium text-slate-900 truncate">
                    {s.label || "Untitled chat"}
                  </div>
                  <div className="flex items-center gap-2 mt-0.5">
                    <span className="text-[10px] text-slate-500">
                      {formatDate(s.updatedAt)}
                    </span>
                    {s.settlementPeriod && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-100 text-slate-600 truncate max-w-[8rem]">
                        {s.settlementPeriod}
                      </span>
                    )}
                  </div>
                </div>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setPendingDelete(s.id);
                  }}
                  className="opacity-0 group-hover:opacity-100 text-slate-400 hover:text-red-600 p-1"
                  aria-label="Delete conversation"
                >
                  <Trash2 size={14} />
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {pendingDelete && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
          onClick={() => setPendingDelete(null)}
        >
          <div
            className="bg-white rounded-xl p-5 w-80 shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <h4 className="font-semibold text-slate-900">Delete conversation?</h4>
            <p className="text-sm text-slate-600 mt-1">
              This will permanently remove all messages in this chat.
            </p>
            <div className="flex justify-end gap-2 mt-4">
              <button
                onClick={() => setPendingDelete(null)}
                className="px-3 py-1.5 text-sm rounded-lg border border-slate-300 text-slate-700 hover:bg-slate-50"
              >
                Cancel
              </button>
              <button
                onClick={() => handleDelete(pendingDelete)}
                className="px-3 py-1.5 text-sm rounded-lg bg-red-600 text-white hover:bg-red-700"
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </aside>
  );
}
