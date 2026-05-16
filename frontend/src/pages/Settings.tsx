import TopBar from "../components/TopBar";
import { useAppStore } from "../store/useAppStore";

export default function Settings() {
  const periods = useAppStore((s) => s.periods);
  const sessionId = useAppStore((s) => s.sessionId);
  const clearAll = useAppStore((s) => s.clearAll);

  return (
    <div className="flex flex-col h-full overflow-y-auto">
      <TopBar title="Settings" />
      <div className="p-6 space-y-6 max-w-2xl">
        <div className="card">
          <h3 className="font-semibold text-slate-900 mb-2">Session</h3>
          <p className="text-sm text-slate-500">Session ID: <code>{sessionId}</code></p>
          <p className="text-sm text-slate-500 mt-1">
            Uploaded periods: <strong>{periods.length}</strong>
          </p>
        </div>

        <div className="card">
          <h3 className="font-semibold text-slate-900 mb-2">Data</h3>
          <p className="text-sm text-slate-500 mb-4">
            Remove all uploaded data and chat history from this browser.
          </p>
          <button
            onClick={() => {
              if (confirm("Clear all data?")) clearAll();
            }}
            className="bg-brand-red text-white text-sm rounded-lg px-4 py-2 hover:bg-red-700"
          >
            Clear all data
          </button>
        </div>

        <div className="card">
          <h3 className="font-semibold text-slate-900 mb-2">About</h3>
          <p className="text-sm text-slate-600">
            <strong>SellerLens</strong> — AI-powered profit analytics for Indian
            e-commerce sellers. Powered by Azure OpenAI, Document Intelligence, and
            Azure AI Search.
          </p>
        </div>
      </div>
    </div>
  );
}
