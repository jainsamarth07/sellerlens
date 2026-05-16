import { useEffect, useRef, useState } from "react";
import { Send, Copy, Sparkles } from "lucide-react";
import { chat, fetchSuggestions, postSuggestions } from "../lib/api";
import { useAppStore, useActivePeriod } from "../store/useAppStore";

interface DataChip {
  type: string;
  value: string;
}

interface Message {
  role: "user" | "assistant";
  text: string;
  dataUsed?: DataChip[];
  followUps?: string[];
}

export default function ChatInterface() {
  const sessionId = useAppStore((s) => s.sessionId);
  const active = useActivePeriod();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const scrollRef = useRef<HTMLDivElement | null>(null);

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
  }, [messages, loading]);

  const send = async (text: string) => {
    const q = text.trim();
    if (!q || loading || !active) return;
    setMessages((m) => [...m, { role: "user", text: q }]);
    setInput("");
    setLoading(true);
    try {
      const sellerData = {
        summary: active.upload.summary,
        skus: active.upload.skus,
        ads_total_spend: active.upload.ads_total_spend,
      };
      const res = await chat(q, sessionId, {
        upload_id: active.upload.upload_id,
        seller_data: sellerData,
      });
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          text: res.answer,
          dataUsed: res.data_used,
          followUps: res.follow_ups,
        },
      ]);
    } catch {
      setMessages((m) => [
        ...m,
        { role: "assistant", text: "Sorry, I couldn't reach the AI service." },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const copy = (text: string) => navigator.clipboard?.writeText(text);

  return (
    <div className="flex flex-col h-full bg-white rounded-xl border border-slate-200">
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
