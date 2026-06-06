import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  TrendingUp, Wallet, RotateCcw, Receipt, Sparkles, RefreshCw, Upload as UploadIcon,
} from "lucide-react";
import {
  BarChart, Bar, PieChart, Pie, Cell, XAxis, YAxis, Tooltip,
  ResponsiveContainer, Legend,
} from "recharts";
import TopBar from "../components/TopBar";
import MetricCard from "../components/MetricCard";
import WaterfallChart from "../components/WaterfallChart";
import SKUTable from "../components/SKUTable";
import InsightCard from "../components/InsightCard";
import LoadingSkeleton from "../components/LoadingSkeleton";
import SkuDetailPanel from "../components/SkuDetailPanel";
import { useActivePeriod } from "../store/useAppStore";
import {
  fetchInsights, type InsightReport, type SkuRow,
} from "../lib/api";
import { formatINR, formatPct } from "../lib/format";
import { buildSkuMap } from "../lib/sku";

const PIE_COLORS = ["#059669", "#DC2626", "#D97706", "#2563EB", "#7C3AED"];

export default function Dashboard() {
  const navigate = useNavigate();
  const active = useActivePeriod();
  const [insights, setInsights] = useState<InsightReport | null>(null);
  const [insightsLoading, setInsightsLoading] = useState(false);
  const [selectedSku, setSelectedSku] = useState<SkuRow | null>(null);
  const skuMap = useMemo(() => buildSkuMap(active?.upload.skus), [active]);

  const loadInsights = async () => {
    if (!active) return;
    setInsightsLoading(true);
    try {
      const r = await fetchInsights({
        summary: active.upload.summary,
        skus: active.upload.skus,
        ads_total_spend: active.upload.ads_total_spend,
      });
      setInsights(r);
    } catch {
      setInsights(null);
    } finally {
      setInsightsLoading(false);
    }
  };

  useEffect(() => {
    setInsights(null);
    if (active) loadInsights();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active?.upload.upload_id]);

  if (!active) {
    return (
      <div className="flex flex-col h-full">
        <TopBar title="Dashboard" />
        <div className="flex-1 p-8 flex items-center justify-center">
          <div className="max-w-md w-full text-center card">
            <Sparkles className="mx-auto text-brand-green mb-2" size={36} />
            <h2 className="text-xl font-semibold text-slate-900 mb-1">
              No data yet
            </h2>
            <p className="text-slate-500 mb-5 text-sm">
              Upload your first settlement report to see your real profit.
            </p>
            <button
              onClick={() => navigate("/upload")}
              className="bg-brand-green text-white px-5 py-2.5 rounded-lg font-medium inline-flex items-center gap-2 hover:bg-emerald-700"
            >
              <UploadIcon size={16} />
              Upload report
            </button>
          </div>
        </div>
      </div>
    );
  }

  const s = active.upload.summary;
  const ads = active.upload.ads_total_spend ?? 0;
  const returnRate = s.total_sale_orders
    ? (s.total_returns / s.total_sale_orders) * 100
    : 0;
  const reclaimable = (s.input_gst_tcs_credits || 0) + (s.income_tax_credits || 0);
  const netPctOfSales = s.gross_sales_amount
    ? (s.net_bank_settlement / s.gross_sales_amount) * 100
    : 0;

  const barData = [
    { name: "Gross Sales", value: s.gross_sales_amount },
    { name: "Net Settlement", value: s.net_bank_settlement },
  ];

  const youKept = s.net_bank_settlement;
  const pieData = [
    { name: "You kept", value: Math.max(youKept, 0) },
    { name: "Returns", value: s.returns_reversal },
    { name: "MP Fees", value: s.marketplace_fees + s.gst_on_mp_fees },
    { name: "Taxes", value: s.tcs_amount + s.tds_amount },
    { name: "Ads", value: ads },
  ].filter((d) => d.value > 0);

  return (
    <div className="flex flex-col h-full overflow-y-auto">
      <TopBar title="Dashboard" />

      <div className="p-6 space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <MetricCard
            icon={TrendingUp}
            label="Gross Sales"
            value={formatINR(s.gross_sales_amount)}
            tone="positive"
            subValue={`${s.total_sale_orders} orders`}
          />
          <MetricCard
            icon={Wallet}
            label="Net Settlement"
            value={formatINR(s.net_bank_settlement)}
            tone="neutral"
            subValue={`${formatPct(netPctOfSales)} of sales`}
          />
          <MetricCard
            icon={RotateCcw}
            label="Return Rate"
            value={formatPct(returnRate)}
            tone={returnRate > 10 ? "negative" : "positive"}
            subValue={`${s.total_returns} returns`}
          />
          <MetricCard
            icon={Receipt}
            label="Reclaimable Credits"
            value={formatINR(reclaimable)}
            tone="warning"
            subValue="claim before deadline"
          />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div className="card">
            <h3 className="font-semibold text-slate-900 mb-4">Revenue vs Settlement</h3>
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={barData}>
                <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 11 }}
                  tickFormatter={(v) => `₹${(v / 1000).toFixed(0)}k`} />
                <Tooltip formatter={(v: number) => formatINR(v)} />
                <Bar dataKey="value" fill="#059669" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <div className="card">
            <h3 className="font-semibold text-slate-900 mb-4">Cost Breakdown</h3>
            <div className="relative">
              <ResponsiveContainer width="100%" height={260}>
                <PieChart>
                  <Pie data={pieData} dataKey="value" nameKey="name"
                    innerRadius={60} outerRadius={95} paddingAngle={2}>
                    {pieData.map((_, i) => (
                      <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(v: number) => formatINR(v)} />
                  <Legend wrapperStyle={{ fontSize: 12 }} />
                </PieChart>
              </ResponsiveContainer>
              <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none -mt-6">
                <span className="text-xs text-slate-500">You kept</span>
                <span className="text-lg font-bold text-slate-900">{formatINR(youKept)}</span>
              </div>
            </div>
          </div>
        </div>

        <WaterfallChart summary={s} adsSpend={ads} />

        <SKUTable skus={active.upload.skus} onRowClick={setSelectedSku} />

        <div className="card">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <Sparkles size={18} className="text-brand-green" />
              <h3 className="font-semibold text-slate-900">AI Insights</h3>
              <span className="badge bg-emerald-50 text-brand-green">
                Powered by Azure OpenAI
              </span>
            </div>
            <button
              onClick={loadInsights}
              disabled={insightsLoading}
              className="text-sm text-slate-600 hover:text-slate-900 flex items-center gap-1"
            >
              <RefreshCw size={14} className={insightsLoading ? "animate-spin" : ""} />
              Refresh
            </button>
          </div>

          {insightsLoading && <LoadingSkeleton rows={4} />}

          {!insightsLoading && insights && (
            <>
              <p className="text-sm text-slate-600 mb-4 italic">
                {insights.one_line_summary}{" "}
                <span className="font-medium not-italic">
                  Health: {insights.health_label} ({insights.health_score}/100)
                </span>
              </p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {insights.insights.map((ins, i) => (
                  <InsightCard key={i} insight={ins} skuMap={skuMap} />
                ))}
              </div>
            </>
          )}

          {!insightsLoading && !insights && (
            <p className="text-sm text-slate-500">No insights yet.</p>
          )}
        </div>
      </div>

      <SkuDetailPanel sku={selectedSku} onClose={() => setSelectedSku(null)} />
    </div>
  );
}
