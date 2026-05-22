import { useEffect, useRef, useState } from "react";
import { Send, Copy, Sparkles, Eraser } from "lucide-react";
import { chat, fetchSuggestions, postSuggestions } from "../lib/api";
import { useActivePeriod } from "../store/useAppStore";
import {
  useActiveChatSession,
  useChatStore,
  type ChatStoredMessage,
} from "../store/useChatStore";

export default function ChatInterface() {
  const active = useActivePeriod();
  const activeSession = useActiveChatSession();
  const addMessage = useChatStore((s) => s.addMessage);
  const clearSession = useChatStore((s) => s.clearSession);
  const createSession = useChatStore((s) => s.createSession);
  const loadMessagesIfNeeded = useChatStore((s) => s.loadMessagesIfNeeded);

  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  const messages: ChatStoredMessage[] = activeSession?.messages ?? [];

  useEffect(() => {
    if (activeSession?.id) {
      loadMessagesIfNeeded(activeSession.id).catch(() => undefined);
    }
  }, [activeSession?.id, loadMessagesIfNeeded]);

  useEffect(() => {
    if (!active) return;
    const sellerData = {
      summary: active.upload.summary,
      skus: active.upload.skus,
      ads_total_spend: active.upload.ads_total_spend,
    };
    fetchSuggestions(active.upload.upload_id)
      .catch(() => postSuggestions(sellerData))
      .then(setSuggestions)
      .catch(() => setSuggestions([]));
  }, [active]);

  useEffect(() => {
    scrollRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length, loading]);

  const ensureSession = async (): Promise<string | null> => {
    if (activeSession?.id) return activeSession.id;
    const period = active?.upload.summary?.payment_duration ?? null;
    const label = period ? `${period} Analysis` : "New chat";
    return await createSession(label, period);
  };

  const send = async (text: string) => {
    const q = text.trim();
    if (!q || loading || !active) return;
    const sid = await ensureSession();
    if (!sid) return;

    addMessage(sid, {
      role: "user",
      text: q,
      createdAt: new Date().toISOString(),
    });
    setInput("");
    setLoading(true);
    try {
      const sellerData = {
        summary: active.upload.summary,
        skus: active.upload.skus,
        ads_total_spend: active.upload.ads_total_spend,
      };
      // Keep last 6 messages in memory for the Azure OpenAI context window
      // — same behaviour as before (server-side memory is keyed by sid).
      const res = await chat(q, sid, {
        upload_id: active.upload.upload_id,
        seller_data: sellerData,
      });
      addMessage(sid, {
        role: "assistant",
        text: res.answer,
        dataUsed: res.data_used,
        followUps: res.follow_ups,
        createdAt: new Date().toISOString(),
      });
    } catch {
      addMessage(sid, {
        role: "assistant",
        text: "Sorry, I couldn't reach the AI service.",
        createdAt: new Date().toISOString(),
      });
    } finally {
      setLoading(false);
    }
  };

  const copy = (text: string) => navigator.clipboard?.writeText(text);

  return (
    <div className="flex flex-col h-full bg-white rounded-xl border border-slate-200">
      {/* header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-200">
        <div className="min-w-0">
          <h3 className="font-semibold text-slate-900 text-sm truncate">
            {activeSession?.label ?? "New conversation"}
          </h3>
          {activeSession?.settlementPeriod && (
            <p className="text-[11px] text-slate-500 truncate">
              {activeSession.settlementPeriod}
            </p>
          )}
        </div>
        {activeSession && messages.length > 0 && (
          <button
            onClick={() => clearSession(activeSession.id)}
            className="text-xs text-slate-600 hover:text-red-600 flex items-center gap-1 px-2 py-1 rounded border border-slate-200 hover:border-red-200"
          >
            <Eraser size={12} /> Clear conversation
          </button>
        )}
      </div>

      {/* messages */}
      <div className="flex-1 overflow-y-auto p-6 space-y-4">
        {messages.length === 0 && (
          <div className="text-center text-slate-400 mt-8">
            <Sparkles size={32} className="mx-auto mb-2 text-brand-green" />
            <p>Ask anything about your settlement data.</p>
          </div>
        )}

        {messages.map((m, i) => (
          <div
            key={i}
            className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[75%] rounded-2xl px-4 py-3 whitespace-pre-wrap ${
                m.role === "user"
                  ? "bg-brand-green text-white"
                  : "bg-slate-100 text-slate-900"
              }`}
            >
              <p className="text-sm leading-relaxed">{m.text}</p>

              {m.role === "assistant" && (
                <>
                  {m.dataUsed && m.dataUsed.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 mt-3">
                      {m.dataUsed.map((d, j) => (
                        <span
                          key={j}
                          title={d.type}
                          className="badge bg-white text-slate-700 border border-slate-200"
                        >
                          {d.value}
                        </span>
                      ))}
                    </div>
                  )}

                  <div className="flex items-center justify-between mt-3">
                    <span className="text-xs text-slate-500 italic">
                      Powered by Azure OpenAI
                    </span>
                    <button
                      onClick={() => copy(m.text)}
                      className="text-xs text-slate-500 hover:text-slate-900 flex items-center gap-1"
                    >
                      <Copy size={11} /> Copy
                    </button>
                  </div>

                  {m.followUps && m.followUps.length > 0 && (
                    <div className="flex flex-wrap gap-1.5 mt-2">
                      {m.followUps.map((f, j) => (
                        <button
                          key={j}
                          onClick={() => send(f)}
                          className="text-xs text-brand-green border border-brand-green rounded-full px-3 py-1 hover:bg-emerald-50"
                        >
                          {f}
                        </button>
                      ))}
                    </div>
                  )}
                </>
              )}
            </div>
          </div>
        ))}

        {loading && (
          <div className="flex justify-start">
            <div className="bg-slate-100 text-slate-500 rounded-2xl px-4 py-3 text-sm italic">
              SellerLens is thinking…
            </div>
          </div>
        )}
        <div ref={scrollRef} />
      </div>

      {/* suggestions + input */}
      <div className="border-t border-slate-200 p-4 space-y-3">
        {messages.length === 0 && suggestions.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {suggestions.map((s, i) => (
              <button
                key={i}
                onClick={() => send(s)}
                className="text-xs px-3 py-1.5 border border-slate-300 rounded-full text-slate-700 hover:border-brand-green hover:text-brand-green"
              >
                {s}
              </button>
            ))}
          </div>
        )}

        <div className="flex gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && send(input)}
            placeholder={active ? "Ask about your sales, returns, fees…" : "Upload a report first."}
            disabled={!active || loading}
            className="flex-1 border border-slate-300 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-green disabled:bg-slate-50"
          />
          <button
            onClick={() => send(input)}
            disabled={!active || loading || !input.trim()}
            className="bg-brand-green text-white rounded-lg px-4 py-2.5 hover:bg-emerald-700 disabled:opacity-40 disabled:cursor-not-allowed flex items-center gap-1"
          >
            <Send size={14} /> Send
          </button>
        </div>
      </div>
    </div>
  );
}
