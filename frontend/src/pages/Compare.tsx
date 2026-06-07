import { useState } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";
import { Sparkles, CheckSquare, Square } from "lucide-react";
import TopBar from "../components/TopBar";
import LoadingSkeleton from "../components/LoadingSkeleton";
import { runMultiPeriod, type MultiPeriodResult } from "../lib/api";
import { useAppStore } from "../store/useAppStore";
import { formatINR, formatPct } from "../lib/format";

export default function Compare() {
  const periods = useAppStore((s) => s.periods);
  const [selected, setSelected] = useState<number[]>([]);
  const [result, setResult] = useState<MultiPeriodResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const toggle = (id: number) => {
    setSelected((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
    setResult(null);
    setError(null);
  };

  const onAnalyze = async () => {
    if (selected.length < 2) {
      setError("Select at least 2 periods to compare.");
      return;
    }
    setError(null);
    setLoading(true);
    try {
      const res = await runMultiPeriod(selected);
      setResult(res);
    } catch {
      setError("Multi-period analysis failed.");
    } finally {
      setLoading(false);
    }
  };

  const chartData =
    result?.periods.map((p, i) => ({
      period: p,
      revenue: result.metrics.revenue[i],
      net: result.metrics.net_settlement[i],
      returnRate: result.metrics.return_rate[i],
      ads: result.metrics.ads_spend[i],
    })) ?? [];

  return (
    <div className="flex flex-col h-full overflow-y-auto">
      <TopBar title="Compare Periods" />

      <div className="p-6 space-y-6">
        <div className="card">
          <h3 className="font-semibold text-slate-900 mb-1">Select periods to compare</h3>
          <p className="text-sm text-slate-500 mb-4">
            Choose 2–6 already-uploaded settlement reports. Upload more via the Upload page.
          </p>

          {periods.length === 0 ? (
            <p className="text-sm text-slate-400">
              No uploads yet — go to the Upload page to add settlement reports.
            </p>
          ) : (
            <div className="space-y-2 mb-4">
              {periods.map((p) => {
                const id = p.upload.upload_id;
                const isSelected = selected.includes(id);
                return (
                  <button
                    key={id}
                    onClick={() => toggle(id)}
                    className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg border text-left transition-colors ${
                      isSelected
                        ? "border-brand-blue bg-blue-50"
                        : "border-slate-200 hover:border-slate-300"
                    }`}
                  >
                    {isSelected ? (
                      <CheckSquare size={18} className="text-brand-blue shrink-0" />
                    ) : (
                      <Square size={18} className="text-slate-400 shrink-0" />
                    )}
                    <div>
                      <div className="text-sm font-medium text-slate-800">
                        {p.upload.summary?.payment_duration || p.upload.filename}
                      </div>
                      <div className="text-xs text-slate-500">
                        {p.upload.platform} · {p.upload.rows_parsed} rows ·{" "}
                        {formatINR(p.upload.summary?.net_bank_settlement ?? 0)} net
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>
          )}

          <button
            onClick={onAnalyze}
            disabled={selected.length < 2 || loading || periods.length === 0}
            className="btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {loading ? "Analysing…" : `Compare ${selected.length} period${selected.length !== 1 ? "s" : ""}`}
          </button>

          {error && <p className="text-sm text-brand-red mt-2">{error}</p>}
        </div>

        {loading && (
          <div className="space-y-3">
            <LoadingSkeleton />
            <LoadingSkeleton />
            <LoadingSkeleton />
          </div>
        )}

        {result && (
          <>
            <div className="card">
              <h3 className="font-semibold text-slate-900 mb-4">Trend over time</h3>
              <ResponsiveContainer width="100%" height={320}>
                <LineChart data={chartData}>
                  <CartesianGrid stroke="#E2E8F0" strokeDasharray="3 3" />
                  <XAxis dataKey="period" tick={{ fontSize: 12 }} />
                  <YAxis
                    tick={{ fontSize: 11 }}
                    tickFormatter={(v) => `₹${(v / 1000).toFixed(0)}k`}
                  />
                  <Tooltip formatter={(v: number) => formatINR(v)} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                  <Line type="monotone" dataKey="revenue" stroke="#2563EB" strokeWidth={2} />
                  <Line type="monotone" dataKey="net" stroke="#059669" strokeWidth={2} />
                  <Line type="monotone" dataKey="ads" stroke="#D97706" strokeWidth={2} />
                </LineChart>
              </ResponsiveContainer>
            </div>

            <div className="card">
              <h3 className="font-semibold text-slate-900 mb-4">Side-by-side</h3>
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-slate-500 border-b border-slate-200">
                      <th className="py-2 pr-3">Metric</th>
                      {result.periods.map((p) => (
                        <th key={p} className="py-2 px-3">{p}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    <CompareRow label="Revenue" values={result.metrics.revenue} fmt={formatINR} />
                    <CompareRow label="Net Settlement" values={result.metrics.net_settlement} fmt={formatINR} />
                    <CompareRow label="Return Rate" values={result.metrics.return_rate} fmt={formatPct} />
                    <CompareRow label="MP Fee %" values={result.metrics.mp_fee_pct} fmt={formatPct} />
                    <CompareRow label="Ads Spend" values={result.metrics.ads_spend} fmt={formatINR} />
                    <CompareRow label="Reclaimable Credits" values={result.metrics.reclaimable_credits} fmt={formatINR} />
                  </tbody>
                </table>
              </div>
              <p className="text-xs text-slate-500 mt-4">
                Best month: <strong>{result.best_month}</strong> · Worst month:{" "}
                <strong>{result.worst_month}</strong>
              </p>
            </div>

            <div className="card">
              <div className="flex items-center gap-2 mb-3">
                <Sparkles size={18} className="text-brand-green" />
                <h3 className="font-semibold text-slate-900">AI Trend Analysis</h3>
                <span className="badge bg-emerald-50 text-brand-green">
                  Powered by Azure OpenAI
                </span>
              </div>
              <div className="space-y-3 text-sm">
                {Object.entries(result.ai_trend_analysis)
                  .filter(([k]) => !k.startsWith("_"))
                  .map(([k, v]) => (
                    <div key={k}>
                      <div className="text-xs uppercase tracking-wide text-slate-500 mb-1">
                        {k.replace(/_/g, " ")}
                      </div>
                      <div className="text-slate-800 whitespace-pre-wrap">
                        {typeof v === "string" ? v : JSON.stringify(v, null, 2)}
                      </div>
                    </div>
                  ))}
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function CompareRow({
  label,
  values,
  fmt,
}: {
  label: string;
  values: number[];
  fmt: (n: number) => string;
}) {
  return (
    <tr className="border-b border-slate-100">
      <td className="py-2 pr-3 text-slate-500">{label}</td>
      {values.map((v, i) => (
        <td key={i} className="py-2 px-3 text-slate-900 font-medium">
          {fmt(v)}
        </td>
      ))}
    </tr>
  );
}
