import { useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  BarChart3,
  Loader2,
  RefreshCw,
  Rocket,
  Settings as SettingsIcon,
  Sparkles,
  TrendingDown,
  TrendingUp,
  Upload,
  Wallet,
  X,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Label,
  Legend,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";

import LoadingSkeleton from "../components/LoadingSkeleton";
import TopBar from "../components/TopBar";
import {
  fetchAdsAnalysis,
  fetchAdsStatus,
  refreshAdsInsights,
  uploadAdsFile,
  type AdsAnalysis,
  type AdsCampaign,
  type AdsCategoryCrossRef,
  type AdsInsight,
  type AdsProductRow,
  type SkuRow,
} from "../lib/api";
import { formatINR } from "../lib/format";
import { useActivePeriod } from "../store/useAppStore";
import { useAuthStore } from "../store/useAuth";

type VerdictFilter = "all" | "live" | "paused" | "stop";
type ProductFilter = "all" | "loss" | "high_cost" | "profitable";
type AdsTab = "overview" | "category" | "product";

const VERDICT_STYLES: Record<
  AdsCampaign["verdict"],
  { label: string; emoji: string; cls: string; rowCls?: string }
> = {
  star: { label: "Star", emoji: "⭐", cls: "bg-emerald-100 text-emerald-800" },
  decent: { label: "Decent", emoji: "✅", cls: "bg-blue-100 text-blue-800" },
  watch: { label: "Watch", emoji: "⚠️", cls: "bg-amber-100 text-amber-800" },
  stop: {
    label: "Stop",
    emoji: "🛑",
    cls: "bg-red-100 text-red-800",
    rowCls: "bg-red-50/40",
  },
};

const INSIGHT_STYLES: Record<
  AdsInsight["type"],
  { emoji: string; bg: string; border: string; iconBg: string; icon: typeof Rocket }
> = {
  stop: {
    emoji: "🛑",
    bg: "bg-red-50",
    border: "border-red-200",
    iconBg: "bg-red-100 text-red-700",
    icon: AlertTriangle,
  },
  scale: {
    emoji: "🚀",
    bg: "bg-emerald-50",
    border: "border-emerald-200",
    iconBg: "bg-emerald-100 text-emerald-700",
    icon: Rocket,
  },
  optimize: {
    emoji: "⚙️",
    bg: "bg-amber-50",
    border: "border-amber-200",
    iconBg: "bg-amber-100 text-amber-700",
    icon: SettingsIcon,
  },
  info: {
    emoji: "💡",
    bg: "bg-blue-50",
    border: "border-blue-200",
    iconBg: "bg-blue-100 text-blue-700",
    icon: Sparkles,
  },
};

function roiColor(roi: number): string {
  if (roi >= 8) return "text-emerald-600";
  if (roi >= 4) return "text-blue-600";
  if (roi >= 2) return "text-amber-600";
  return "text-red-600";
}

function fmtRoi(roi: number): string {
  return `${roi.toFixed(2)}x`;
}

export default function Ads() {
  const [loading, setLoading] = useState(true);
  const [insightsLoading, setInsightsLoading] = useState(false);
  const [analysis, setAnalysis] = useState<AdsAnalysis | null>(null);
  const [hasAds, setHasAds] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [verdictFilter, setVerdictFilter] = useState<VerdictFilter>("all");
  const [activeTab, setActiveTab] = useState<AdsTab>("overview");
  const fileInputRef = useRef<HTMLInputElement | null>(null);

  const activePeriod = useActivePeriod();
  const user = useAuthStore((s) => s.user);

  async function loadInsights(current: AdsAnalysis) {
    setInsightsLoading(true);
    try {
      const full = await fetchAdsAnalysis(current.settlement_period ?? undefined);
      setAnalysis({ ...current, ai_insights: full.ai_insights });
    } catch {
      /* keep page rendered — insights just won't show */
    } finally {
      setInsightsLoading(false);
    }
  }

  async function reload() {
    setLoading(true);
    setError(null);
    try {
      const status = await fetchAdsStatus();
      setHasAds(status.has_ads);
      if (status.has_ads) {
        // Phase 1: fetch campaigns + summary immediately (no AI call)
        const data = await fetchAdsAnalysis(undefined, false);
        setAnalysis(data);
        setLoading(false);
        // Phase 2: fetch AI insights in the background
        loadInsights(data);
        return;
      } else {
        setAnalysis(null);
      }
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? e?.message ?? "Failed to load ads data.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    reload();
  }, []);

  async function handleFile(file: File) {
    setUploading(true);
    setError(null);
    try {
      await uploadAdsFile(file);
      await reload();
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? e?.message ?? "Upload failed.");
    } finally {
      setUploading(false);
    }
  }

  async function handleRefreshInsights() {
    if (!analysis) return;
    setRefreshing(true);
    try {
      const res = await refreshAdsInsights();
      setAnalysis({ ...analysis, ai_insights: res.ai_insights });
    } catch {
      /* ignore — keep old insights */
    } finally {
      setRefreshing(false);
    }
  }

  return (
    <div className="flex flex-col h-full overflow-y-auto">
      <TopBar title="Ads Analytics" />

      <div className="p-6 space-y-6">
        {/* Hidden uploader (shared across empty state + header button) */}
        <input
          ref={fileInputRef}
          type="file"
          accept=".csv,.xlsx,.xls"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) handleFile(f);
            e.currentTarget.value = "";
          }}
        />

        {error && (
          <div className="card border-red-200 bg-red-50 text-red-800 text-sm">
            {error}
          </div>
        )}

        {loading && (
          <div className="card flex items-center gap-3 text-slate-500">
            <Loader2 size={18} className="animate-spin" /> Loading ads analysis…
          </div>
        )}

        {!loading && !hasAds && (
          <EmptyState
            uploading={uploading}
            onUpload={() => fileInputRef.current?.click()}
          />
        )}

        {!loading && hasAds && analysis && (
          <>
            <HeaderActions
              uploading={uploading}
              onUpload={() => fileInputRef.current?.click()}
              period={analysis.settlement_period}
            />

            {/* Tab navigation */}
            <div className="flex gap-1 border-b border-slate-200">
              {(["overview", "category", "product"] as AdsTab[]).map((tab) => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className={`px-4 py-2.5 text-sm font-medium border-b-2 transition -mb-px ${
                    activeTab === tab
                      ? "border-brand-green text-brand-green"
                      : "border-transparent text-slate-500 hover:text-slate-800"
                  }`}
                >
                  {tab === "overview" ? "Overview" : tab === "category" ? "By Category" : "By Product"}
                </button>
              ))}
            </div>

            {activeTab === "overview" && (
              <>
                <OverviewCards analysis={analysis} />

                <CampaignsCard
                  campaigns={analysis.campaigns}
                  filter={verdictFilter}
                  onFilterChange={setVerdictFilter}
                />

                <ChartsRow campaigns={analysis.campaigns} />

                <InsightsSection
                  insights={analysis.ai_insights?.insights ?? []}
                  loading={insightsLoading}
                  refreshing={refreshing}
                  onRefresh={handleRefreshInsights}
                />
              </>
            )}

            {activeTab === "category" && (
              <CategoryTab
                crossRef={analysis.category_cross_reference}
                skus={activePeriod?.upload.skus ?? []}
              />
            )}

            {activeTab === "product" && (
              <ProductTab
                crossRef={analysis.category_cross_reference}
                skus={activePeriod?.upload.skus ?? []}
                userId={user?.id ?? 0}
                period={analysis.settlement_period ?? ""}
              />
            )}
          </>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Empty state
// ---------------------------------------------------------------------------

function EmptyState({ uploading, onUpload }: { uploading: boolean; onUpload: () => void }) {
  return (
    <div className="card flex flex-col items-center justify-center text-center py-16">
      <div className="bg-emerald-100 text-brand-green rounded-full p-4 mb-4">
        <BarChart3 size={32} />
      </div>
      <h2 className="text-xl font-semibold text-slate-900">
        Upload your Flipkart ads report
      </h2>
      <p className="text-sm text-slate-500 mt-2 max-w-md">
        Cross-reference your campaign spend with settlement revenue to spot
        wasted ad budget, scale your winners and stop losing money on
        underperforming SKUs.
      </p>
      <button
        onClick={onUpload}
        disabled={uploading}
        className="mt-6 flex items-center gap-2 bg-brand-green hover:bg-emerald-700 text-white font-semibold px-5 py-2.5 rounded-lg transition disabled:opacity-60"
      >
        {uploading ? (
          <Loader2 size={16} className="animate-spin" />
        ) : (
          <Upload size={16} />
        )}
        {uploading ? "Uploading…" : "Upload Ads Report"}
      </button>
      <p className="text-xs text-slate-400 mt-3">
        Accepts <span className="font-mono">.xlsx</span> or{" "}
        <span className="font-mono">.csv</span> up to 25 MB.
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Header actions row
// ---------------------------------------------------------------------------

function HeaderActions({
  uploading,
  onUpload,
  period,
}: {
  uploading: boolean;
  onUpload: () => void;
  period: string | null;
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div className="text-sm text-slate-500">
        {period ? (
          <>
            Period: <span className="font-semibold text-slate-700">{period}</span>
          </>
        ) : (
          "Showing all uploaded campaigns"
        )}
      </div>
      <button
        onClick={onUpload}
        disabled={uploading}
        className="flex items-center gap-2 bg-slate-900 hover:bg-slate-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition disabled:opacity-60"
      >
        {uploading ? <Loader2 size={14} className="animate-spin" /> : <Upload size={14} />}
        {uploading ? "Uploading…" : "Re-upload ads"}
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Overview cards (4)
// ---------------------------------------------------------------------------

function OverviewCards({ analysis }: { analysis: AdsAnalysis }) {
  const { summary } = analysis;
  const roi = summary.overall_roi;
  const roiTone =
    roi >= 4 ? "text-brand-green" : roi >= 2 ? "text-brand-amber" : "text-brand-red";

  const items: Array<{
    label: string;
    value: string;
    sub?: string;
    tone?: string;
    icon: typeof Wallet;
    iconBg: string;
  }> = [
    {
      label: "Total Ad Spend",
      value: formatINR(summary.total_spend),
      sub: `${summary.total_campaigns} campaigns (${summary.active_campaigns} live)`,
      icon: Wallet,
      iconBg: "bg-slate-100 text-slate-700",
    },
    {
      label: "Ad Revenue",
      value: formatINR(summary.total_revenue),
      sub: "Direct from ads",
      icon: TrendingUp,
      iconBg: "bg-emerald-100 text-emerald-700",
    },
    {
      label: "Overall ROI",
      value: fmtRoi(roi),
      sub: roi >= 4 ? "Profitable" : roi >= 2 ? "Break-even risk" : "Losing money",
      tone: roiTone,
      icon: BarChart3,
      iconBg: "bg-blue-100 text-blue-700",
    },
    {
      label: "Wasted Spend",
      value: formatINR(summary.wasted_spend),
      sub: `${summary.wasted_campaigns} campaigns earned ₹0`,
      tone: "text-brand-red",
      icon: TrendingDown,
      iconBg: "bg-red-100 text-red-700",
    },
  ];

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      {items.map((it) => (
        <div key={it.label} className="card flex items-start gap-4">
          <div className={`${it.iconBg} rounded-lg p-3`}>
            <it.icon size={22} />
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm text-slate-500 font-medium">{it.label}</p>
            <p
              className={`text-2xl font-bold mt-1 truncate ${
                it.tone ?? "text-slate-900"
              }`}
            >
              {it.value}
            </p>
            {it.sub && (
              <p className="text-xs text-slate-500 mt-1.5">{it.sub}</p>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Campaigns table + filter pills
// ---------------------------------------------------------------------------

function CampaignsCard({
  campaigns,
  filter,
  onFilterChange,
}: {
  campaigns: AdsCampaign[];
  filter: VerdictFilter;
  onFilterChange: (f: VerdictFilter) => void;
}) {
  const counts = useMemo(() => {
    return {
      all: campaigns.length,
      live: campaigns.filter((c) => (c.status ?? "").toUpperCase() === "LIVE").length,
      paused: campaigns.filter((c) => (c.status ?? "").toUpperCase() !== "LIVE").length,
      stop: campaigns.filter((c) => c.verdict === "stop").length,
    };
  }, [campaigns]);

  const filtered = useMemo(() => {
    let rows = [...campaigns];
    if (filter === "live") rows = rows.filter((c) => (c.status ?? "").toUpperCase() === "LIVE");
    if (filter === "paused") rows = rows.filter((c) => (c.status ?? "").toUpperCase() !== "LIVE");
    if (filter === "stop") rows = rows.filter((c) => c.verdict === "stop");
    rows.sort((a, b) => b.ad_spend - a.ad_spend);
    return rows;
  }, [campaigns, filter]);

  const filters: Array<{ key: VerdictFilter; label: string }> = [
    { key: "all", label: `All (${counts.all})` },
    { key: "live", label: `Live (${counts.live})` },
    { key: "paused", label: `Paused (${counts.paused})` },
    { key: "stop", label: `Stop These (${counts.stop})` },
  ];

  return (
    <div className="card">
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <h2 className="text-lg font-semibold text-slate-900">Campaign Performance</h2>
        <div className="flex gap-2 flex-wrap">
          {filters.map((f) => {
            const active = filter === f.key;
            const isStop = f.key === "stop";
            return (
              <button
                key={f.key}
                onClick={() => onFilterChange(f.key)}
                className={`px-3 py-1.5 rounded-lg text-xs font-semibold border transition ${
                  active
                    ? isStop
                      ? "bg-red-600 text-white border-red-600"
                      : "bg-slate-900 text-white border-slate-900"
                    : "bg-white text-slate-600 border-slate-200 hover:bg-slate-50"
                }`}
              >
                {f.label}
              </button>
            );
          })}
        </div>
      </div>

      {filter === "stop" && counts.stop > 0 && (
        <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
          <span className="font-semibold">{counts.stop} campaigns</span> are
          losing money (ROI &lt; 2x or zero revenue). Consider pausing them this
          week.
        </div>
      )}

      <div className="overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead className="text-left text-xs uppercase text-slate-500 border-b border-slate-200">
            <tr>
              <th className="px-3 py-2 font-semibold">Campaign</th>
              <th className="px-3 py-2 font-semibold">Status</th>
              <th className="px-3 py-2 font-semibold text-right">Spend</th>
              <th className="px-3 py-2 font-semibold text-right">Revenue</th>
              <th className="px-3 py-2 font-semibold text-right">ROI</th>
              <th className="px-3 py-2 font-semibold text-right">CTR</th>
              <th className="px-3 py-2 font-semibold text-right">CVR</th>
              <th className="px-3 py-2 font-semibold">Verdict</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {filtered.length === 0 && (
              <tr>
                <td colSpan={8} className="px-3 py-6 text-center text-slate-400">
                  No campaigns match this filter.
                </td>
              </tr>
            )}
            {filtered.map((c) => {
              const v = VERDICT_STYLES[c.verdict];
              return (
                <tr key={c.id} className={v.rowCls ?? ""}>
                  <td className="px-3 py-2 max-w-xs truncate" title={c.campaign_name ?? ""}>
                    {c.campaign_name ?? "—"}
                  </td>
                  <td className="px-3 py-2 text-xs text-slate-600">
                    {c.status ?? "—"}
                  </td>
                  <td className="px-3 py-2 text-right">{formatINR(c.ad_spend)}</td>
                  <td className="px-3 py-2 text-right">{formatINR(c.revenue)}</td>
                  <td className={`px-3 py-2 text-right font-semibold ${roiColor(c.roi)}`}>
                    {fmtRoi(c.roi)}
                  </td>
                  <td className="px-3 py-2 text-right text-slate-600">
                    {c.ctr_pct.toFixed(2)}%
                  </td>
                  <td className="px-3 py-2 text-right text-slate-600">
                    {c.conversion_rate_pct.toFixed(2)}%
                  </td>
                  <td className="px-3 py-2">
                    <span className={`badge ${v.cls}`}>
                      {v.emoji} {v.label}
                    </span>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Charts row: horizontal bar (top 10 by spend) + scatter (Spend vs ROI)
// ---------------------------------------------------------------------------

const VERDICT_BAR_COLOR: Record<AdsCampaign["verdict"], string> = {
  star: "#059669",
  decent: "#2563eb",
  watch: "#d97706",
  stop: "#dc2626",
};

function ChartsRow({ campaigns }: { campaigns: AdsCampaign[] }) {
  const top10 = useMemo(
    () =>
      [...campaigns]
        .sort((a, b) => b.ad_spend - a.ad_spend)
        .slice(0, 10)
        .map((c) => ({
          name:
            (c.campaign_name ?? "Unnamed").length > 28
              ? (c.campaign_name ?? "Unnamed").slice(0, 28) + "…"
              : c.campaign_name ?? "Unnamed",
          spend: c.ad_spend,
          verdict: c.verdict,
        })),
    [campaigns],
  );

  const avgSpend = useMemo(() => {
    if (!campaigns.length) return 0;
    return campaigns.reduce((s, c) => s + c.ad_spend, 0) / campaigns.length;
  }, [campaigns]);

  const scatterData = useMemo(
    () =>
      campaigns.map((c) => ({
        name: c.campaign_name ?? "Unnamed",
        spend: c.ad_spend,
        roi: c.roi,
        verdict: c.verdict,
      })),
    [campaigns],
  );

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      <div className="card">
        <h3 className="text-sm font-semibold text-slate-700 mb-3">
          Top 10 campaigns by ad spend
        </h3>
        <div style={{ width: "100%", height: 360 }}>
          <ResponsiveContainer>
            <BarChart
              data={top10}
              layout="vertical"
              margin={{ top: 5, right: 16, left: 8, bottom: 5 }}
            >
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis
                type="number"
                tick={{ fontSize: 11 }}
                tickFormatter={(v) => formatINR(v as number)}
              />
              <YAxis
                type="category"
                dataKey="name"
                width={170}
                tick={{ fontSize: 11 }}
              />
              <Tooltip formatter={(v: number) => formatINR(v)} />
              <Bar dataKey="spend">
                {top10.map((d, i) => (
                  <Cell key={i} fill={VERDICT_BAR_COLOR[d.verdict]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="card">
        <h3 className="text-sm font-semibold text-slate-700 mb-3">
          Spend vs ROI (quadrant view)
        </h3>
        <div style={{ width: "100%", height: 360 }}>
          <ResponsiveContainer>
            <ScatterChart margin={{ top: 16, right: 24, left: 8, bottom: 16 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
              <XAxis
                type="number"
                dataKey="spend"
                name="Spend"
                tick={{ fontSize: 11 }}
                tickFormatter={(v) => formatINR(v as number)}
              >
                <Label value="Ad Spend (₹)" offset={-8} position="insideBottom" fontSize={11} />
              </XAxis>
              <YAxis
                type="number"
                dataKey="roi"
                name="ROI"
                tick={{ fontSize: 11 }}
                tickFormatter={(v) => `${v}x`}
              >
                <Label value="ROI (x)" angle={-90} position="insideLeft" fontSize={11} />
              </YAxis>
              <ReferenceLine x={avgSpend} stroke="#94a3b8" strokeDasharray="4 4" />
              <ReferenceLine y={4} stroke="#94a3b8" strokeDasharray="4 4" />
              <Tooltip
                cursor={{ strokeDasharray: "3 3" }}
                formatter={(value: number, key: string) =>
                  key === "spend" ? formatINR(value) : `${value.toFixed(2)}x`
                }
                labelFormatter={() => ""}
                content={({ active, payload }) => {
                  if (!active || !payload?.length) return null;
                  const d = payload[0].payload as {
                    name: string;
                    spend: number;
                    roi: number;
                  };
                  return (
                    <div className="rounded-md border border-slate-200 bg-white px-3 py-2 text-xs shadow">
                      <p className="font-semibold text-slate-800 max-w-[220px] truncate">
                        {d.name}
                      </p>
                      <p className="text-slate-500">Spend: {formatINR(d.spend)}</p>
                      <p className="text-slate-500">ROI: {d.roi.toFixed(2)}x</p>
                    </div>
                  );
                }}
              />
              <Scatter data={scatterData}>
                {scatterData.map((d, i) => (
                  <Cell key={i} fill={VERDICT_BAR_COLOR[d.verdict]} />
                ))}
              </Scatter>
            </ScatterChart>
          </ResponsiveContainer>
        </div>
        <div className="grid grid-cols-2 gap-2 mt-3 text-[11px] text-slate-500">
          <div>↗ High spend + high ROI = <span className="text-emerald-700 font-semibold">Scale up</span></div>
          <div>↖ Low spend + high ROI = <span className="text-blue-700 font-semibold">Hidden gems</span></div>
          <div>↘ High spend + low ROI = <span className="text-red-700 font-semibold">Money drain</span></div>
          <div>↙ Low spend + low ROI = <span className="text-slate-600 font-semibold">Low priority</span></div>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// AI insights cards
// ---------------------------------------------------------------------------

function InsightsSection({
  insights,
  loading,
  refreshing,
  onRefresh,
}: {
  insights: AdsInsight[];
  loading: boolean;
  refreshing: boolean;
  onRefresh: () => void;
}) {
  return (
    <div className="card">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-slate-900">AI Recommendations</h2>
        <button
          onClick={onRefresh}
          disabled={loading || refreshing}
          className="flex items-center gap-2 text-sm text-slate-600 hover:text-slate-900 border border-slate-200 hover:bg-slate-50 px-3 py-1.5 rounded-lg transition disabled:opacity-60"
        >
          {loading || refreshing ? (
            <Loader2 size={14} className="animate-spin" />
          ) : (
            <RefreshCw size={14} />
          )}
          Refresh
        </button>
      </div>
      {loading ? (
        <LoadingSkeleton rows={4} height={20} />
      ) : insights.length === 0 ? (
        <p className="text-sm text-slate-500">No insights generated yet.</p>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {insights.map((ins, i) => {
            const s = INSIGHT_STYLES[ins.type] ?? INSIGHT_STYLES.info;
            const Icon = s.icon;
            return (
              <div
                key={i}
                className={`rounded-xl border ${s.border} ${s.bg} p-4`}
              >
                <div className="flex items-start gap-3">
                  <div className={`${s.iconBg} rounded-lg p-2`}>
                    <Icon size={18} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <h3 className="text-sm font-semibold text-slate-900">
                      {s.emoji} {ins.title}
                    </h3>
                    <p className="text-sm text-slate-700 mt-1.5">{ins.finding}</p>
                    <p className="text-sm text-slate-800 mt-2">
                      <span className="font-semibold">Action: </span>
                      {ins.action}
                    </p>
                    {ins.monthly_impact && (
                      <p className="text-xs font-semibold text-slate-900 mt-2">
                        {ins.monthly_impact}
                      </p>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Shared: attribute ad spend proportionally per SKU within its category
// ---------------------------------------------------------------------------

/** Normalize category strings: lowercase + replace underscores with spaces */
function normCat(s: string) {
  return s.toLowerCase().trim().replace(/_/g, " ");
}

/** Find the crossRef entry whose category best matches a SKU's category string. */
function matchCrossRef(skuCat: string, crossRef: AdsCategoryCrossRef[]) {
  const sc = normCat(skuCat);
  if (!sc) return undefined;
  return crossRef.find((c) => {
    const cl = normCat(c.category);
    return cl === sc || sc.includes(cl) || cl.includes(sc);
  });
}

function computeAdsProducts(
  skus: SkuRow[],
  crossRef: AdsCategoryCrossRef[],
): AdsProductRow[] {
  // Build category → total SKU revenue map first so we can attribute
  // proportionally without relying on the API's settlement_revenue (which is 0
  // when settlement SKUs weren't passed to build_analysis on the backend).
  const skuRevByCat = new Map<string, number>();
  for (const sku of skus) {
    if (sku.total_revenue <= 0) continue;
    const entry = matchCrossRef(sku.category ?? "", crossRef);
    if (!entry) continue;
    skuRevByCat.set(entry.category, (skuRevByCat.get(entry.category) ?? 0) + sku.total_revenue);
  }

  return skus
    .filter((s) => s.total_revenue > 0)
    .map((sku) => {
      const matchedEntry = matchCrossRef(sku.category ?? "", crossRef);

      const catAdSpend = matchedEntry?.ad_spend ?? 0;
      // Use SKU-derived total revenue for the denominator — accurate even when
      // the API returns settlement_revenue = 0.
      const catGrossRevenue = matchedEntry
        ? (skuRevByCat.get(matchedEntry.category) ?? 0)
        : 0;
      const share = catGrossRevenue > 0 ? sku.total_revenue / catGrossRevenue : 0;
      const attributedAdSpend = catAdSpend * share;

      const adCostPct =
        sku.total_revenue > 0 ? (attributedAdSpend / sku.total_revenue) * 100 : 0;
      const trueProfit = sku.net_settlement - attributedAdSpend;
      const trueMargPct =
        sku.total_revenue > 0 ? (trueProfit / sku.total_revenue) * 100 : 0;

      let profit_verdict: AdsProductRow["profit_verdict"];
      if (trueProfit < 0) profit_verdict = "pause_ads";
      else if (adCostPct > 25) profit_verdict = "reduce_budget";
      else if (trueMargPct > 40 && adCostPct < 15) profit_verdict = "scale_up";
      else profit_verdict = "review";

      return {
        ...sku,
        attributed_ad_spend: attributedAdSpend,
        ad_cost_pct: adCostPct,
        true_profit: trueProfit,
        true_margin_pct: trueMargPct,
        profit_verdict,
        matched_category: matchedEntry?.category ?? null,
      };
    });
}

// ---------------------------------------------------------------------------
// By Category tab
// ---------------------------------------------------------------------------

interface CategoryMetric {
  category: string;
  ad_spend: number;
  gross_revenue: number;
  net_settlement: number;
  ad_cost_pct: number;
  true_profit: number;
  true_margin_pct: number;
  quadrant: "sweet_spot" | "watch" | "investigate" | "danger";
}

function buildCategoryMetrics(
  skus: SkuRow[],
  crossRef: AdsCategoryCrossRef[],
): CategoryMetric[] {
  // Build gross revenue and net settlement from SKUs directly — more reliable
  // than c.settlement_revenue from the API, which is 0 when SKUs weren't
  // passed to build_analysis at upload time.
  const grossByCat = new Map<string, number>();
  const netByCat = new Map<string, number>();
  for (const sku of skus) {
    const skuCat = (sku.category ?? "").toLowerCase().trim();
    const match = crossRef.find((c) => {
      const cl = normCat(c.category);
      const sc = normCat(skuCat);
      return cl === sc || sc.includes(cl) || cl.includes(sc);
    });
    if (!match) continue;
    const key = match.category;
    grossByCat.set(key, (grossByCat.get(key) ?? 0) + sku.total_revenue);
    netByCat.set(key, (netByCat.get(key) ?? 0) + sku.net_settlement);
  }

  return crossRef
    .filter((c) => c.ad_spend > 0)
    .map((c) => {
      // Prefer SKU-derived values; fall back to API's settlement_revenue
      const grossRevenue =
        grossByCat.get(c.category) ?? c.settlement_revenue ?? 0;
      const netSettlement =
        netByCat.get(c.category) ?? (grossRevenue > 0 ? grossRevenue * 0.75 : 0);
      const trueProfit = netSettlement - c.ad_spend;
      const adCostPct =
        grossRevenue > 0
          ? (c.ad_spend / grossRevenue) * 100
          : (c.ad_cost_ratio_pct ?? 0);
      const trueMargPct = grossRevenue > 0 ? (trueProfit / grossRevenue) * 100 : 0;

      let quadrant: CategoryMetric["quadrant"];
      if (adCostPct <= 15 && trueMargPct > 0) quadrant = "sweet_spot";
      else if (adCostPct > 15 && trueMargPct > 0) quadrant = "watch";
      else if (adCostPct <= 15) quadrant = "investigate";
      else quadrant = "danger";

      return {
        category: c.category,
        ad_spend: c.ad_spend,
        gross_revenue: grossRevenue,
        net_settlement: netSettlement,
        ad_cost_pct: adCostPct,
        true_profit: trueProfit,
        true_margin_pct: trueMargPct,
        quadrant,
      };
    });
}

const QUADRANT_COLORS: Record<CategoryMetric["quadrant"], string> = {
  sweet_spot: "#059669",
  watch: "#d97706",
  investigate: "#2563eb",
  danger: "#dc2626",
};

function CategoryTab({
  crossRef,
  skus,
}: {
  crossRef: AdsCategoryCrossRef[];
  skus: SkuRow[];
}) {
  const metrics = useMemo(() => buildCategoryMetrics(skus, crossRef), [skus, crossRef]);
  const barData = useMemo(
    () =>
      [...metrics]
        .sort((a, b) => b.ad_spend - a.ad_spend)
        .slice(0, 10)
        .map((m) => ({
          name:
            m.category.length > 18 ? m.category.slice(0, 18) + "…" : m.category,
          fullName: m.category,
          ad_spend: m.ad_spend,
          net_after_ads: Math.max(0, m.gross_revenue - m.ad_spend),
        })),
    [metrics],
  );

  if (crossRef.length === 0) {
    return (
      <div className="card text-center py-12 text-slate-400">
        No category data yet. Upload a listing file and re-upload ads for category mapping.
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Category summary table */}
      <div className="card">
        <h3 className="text-sm font-semibold text-slate-700 mb-3">Category Ad Attribution</h3>
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead className="text-left text-xs uppercase text-slate-500 border-b border-slate-200">
              <tr>
                <th className="px-3 py-2 font-semibold">Category</th>
                <th className="px-3 py-2 font-semibold text-right">Ad Spend</th>
                <th className="px-3 py-2 font-semibold text-right">Revenue</th>
                <th className="px-3 py-2 font-semibold text-right">Ad Cost %</th>
                <th className="px-3 py-2 font-semibold text-right">True Margin %</th>
                <th className="px-3 py-2 font-semibold">Verdict</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {metrics.map((m) => {
                const marginColor =
                  m.true_margin_pct > 30
                    ? "text-emerald-600"
                    : m.true_margin_pct >= 10
                    ? "text-amber-600"
                    : "text-red-600";
                const verdictStyle: Record<string, string> = {
                  sweet_spot: "bg-emerald-100 text-emerald-800",
                  watch: "bg-amber-100 text-amber-800",
                  investigate: "bg-blue-100 text-blue-800",
                  danger: "bg-red-100 text-red-800",
                };
                const verdictLabel: Record<string, string> = {
                  sweet_spot: "✅ Efficient",
                  watch: "⚠️ Watch",
                  investigate: "🔍 Investigate",
                  danger: "🛑 Danger",
                };
                return (
                  <tr key={m.category}>
                    <td className="px-3 py-2 font-medium capitalize">
                      {m.category.replace(/_/g, " ")}
                    </td>
                    <td className="px-3 py-2 text-right">{formatINR(m.ad_spend)}</td>
                    <td className="px-3 py-2 text-right">{formatINR(m.gross_revenue)}</td>
                    <td className="px-3 py-2 text-right text-slate-700">
                      {m.ad_cost_pct?.toFixed(1) ?? "—"}%
                    </td>
                    <td className={`px-3 py-2 text-right font-semibold ${marginColor}`}>
                      {m.true_margin_pct.toFixed(1)}%
                    </td>
                    <td className="px-3 py-2">
                      <span className={`badge ${verdictStyle[m.quadrant]}`}>
                        {verdictLabel[m.quadrant]}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Stacked bar: net revenue vs ad spend by category */}
      {barData.length > 0 && (
        <div className="card">
          <h3 className="text-sm font-semibold text-slate-700 mb-3">
            Revenue vs Ad Spend by Category
          </h3>
          <div style={{ width: "100%", height: 320 }}>
            <ResponsiveContainer>
              <BarChart data={barData} layout="vertical" margin={{ left: 8, right: 16 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
                <XAxis
                  type="number"
                  tick={{ fontSize: 11 }}
                  tickFormatter={(v) => formatINR(v as number)}
                />
                <YAxis
                  type="category"
                  dataKey="name"
                  width={130}
                  tick={{ fontSize: 11 }}
                />
                <Tooltip
                  formatter={(v: number, name: string) => [
                    formatINR(v),
                    name === "net_after_ads" ? "Net after ads" : "Ad spend",
                  ]}
                />
                <Legend
                  formatter={(v) => (v === "net_after_ads" ? "Net after ads" : "Ad spend")}
                  iconSize={10}
                  wrapperStyle={{ fontSize: 11 }}
                />
                <Bar dataKey="net_after_ads" stackId="a" fill="#059669" />
                <Bar dataKey="ad_spend" stackId="a" fill="#7c3aed" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {/* Quadrant scatter chart — Feature 3 */}
      {metrics.length > 0 && (
        <QuadrantChart metrics={metrics} />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Feature 3 — Category Efficiency Quadrant Chart
// ---------------------------------------------------------------------------

function QuadrantChart({ metrics }: { metrics: CategoryMetric[] }) {
  const scatterData = useMemo(
    () =>
      metrics.map((m) => ({
        x: m.ad_cost_pct,
        y: m.true_margin_pct,
        z: Math.max(m.gross_revenue / 1000, 200),
        category: m.category,
        ad_spend: m.ad_spend,
        gross_revenue: m.gross_revenue,
        true_profit: m.true_profit,
        quadrant: m.quadrant,
      })),
    [metrics],
  );

  const labelMap: Record<CategoryMetric["quadrant"], string> = {
    sweet_spot: "✅ Sweet Spot — Scale these",
    watch: "⚠️ Watch — Profitable but expensive",
    investigate: "🔍 Investigate — Why low margin?",
    danger: "🛑 Danger Zone — Reduce or stop",
  };

  return (
    <div className="card">
      <h3 className="text-sm font-semibold text-slate-700 mb-1">
        Category Efficiency Map — Ad Cost vs True Margin
      </h3>
      <p className="text-xs text-slate-400 mb-4">
        Bubble size = revenue. Hover for details.
      </p>
      <div className="grid grid-cols-2 gap-x-6 gap-y-1 text-[11px] mb-4">
        {(Object.entries(labelMap) as [CategoryMetric["quadrant"], string][]).map(
          ([q, label]) => (
            <div key={q} className="flex items-center gap-1.5">
              <span
                className="inline-block w-3 h-3 rounded-full"
                style={{ background: QUADRANT_COLORS[q] }}
              />
              <span className="text-slate-500">{label}</span>
            </div>
          ),
        )}
      </div>
      <div style={{ width: "100%", height: 420 }}>
        <ResponsiveContainer>
          <ScatterChart margin={{ top: 20, right: 30, left: 10, bottom: 30 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" />
            <XAxis
              type="number"
              dataKey="x"
              name="Ad Cost %"
              domain={[0, 100]}
              tick={{ fontSize: 11 }}
              tickFormatter={(v) => `${v}%`}
              label={{ value: "Ad Cost %", position: "insideBottom", offset: -15, fontSize: 11 }}
            />
            <YAxis
              type="number"
              dataKey="y"
              name="True Margin %"
              domain={[-40, 80]}
              tick={{ fontSize: 11 }}
              tickFormatter={(v) => `${v}%`}
              label={{ value: "True Margin %", angle: -90, position: "insideLeft", offset: 10, fontSize: 11 }}
            />
            <ZAxis type="number" dataKey="z" range={[400, 3000]} />
            <ReferenceLine x={15} stroke="#94a3b8" strokeDasharray="5 3" label={{ value: "15% threshold", position: "top", fontSize: 10, fill: "#94a3b8" }} />
            <ReferenceLine y={0} stroke="#94a3b8" strokeDasharray="5 3" label={{ value: "Break-even", position: "right", fontSize: 10, fill: "#94a3b8" }} />
            <Tooltip
              cursor={{ strokeDasharray: "3 3" }}
              content={({ active, payload }) => {
                if (!active || !payload?.length) return null;
                const d = payload[0].payload as (typeof scatterData)[number];
                return (
                  <div className="rounded-md border border-slate-200 bg-white px-3 py-2 text-xs shadow space-y-0.5">
                    <p className="font-semibold text-slate-800 capitalize mb-1">
                      {d.category.replace(/_/g, " ")}
                    </p>
                    <p className="text-slate-500">Revenue: {formatINR(d.gross_revenue)}</p>
                    <p className="text-slate-500">Ad Spend: {formatINR(d.ad_spend)}</p>
                    <p className="text-slate-500">Ad Cost: {d.x.toFixed(1)}%</p>
                    <p
                      className={d.y >= 0 ? "text-emerald-700 font-semibold" : "text-red-600 font-semibold"}
                    >
                      True Margin: {d.y.toFixed(1)}%
                    </p>
                    <p className="text-slate-500">True Profit: {formatINR(d.true_profit)}</p>
                  </div>
                );
              }}
            />
            <Scatter data={scatterData} shape="circle">
              {scatterData.map((d, i) => (
                <Cell key={i} fill={QUADRANT_COLORS[d.quadrant]} fillOpacity={0.75} />
              ))}
            </Scatter>
          </ScatterChart>
        </ResponsiveContainer>
      </div>
      {/* Quadrant labels overlaid as a legend */}
      <div className="grid grid-cols-2 mt-2 text-[10px] text-slate-400 gap-y-1 px-1">
        <div>↖ Low cost + high margin = <span className="text-emerald-700 font-semibold">Sweet Spot</span></div>
        <div>↗ High cost + high margin = <span className="text-amber-600 font-semibold">Watch</span></div>
        <div>↙ Low cost + low margin = <span className="text-blue-600 font-semibold">Investigate</span></div>
        <div>↘ High cost + low margin = <span className="text-red-600 font-semibold">Danger Zone</span></div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// By Product tab (Feature 1 + Feature 2 + Feature 4)
// ---------------------------------------------------------------------------

function ProductTab({
  crossRef,
  skus,
  userId,
  period,
}: {
  crossRef: AdsCategoryCrossRef[];
  skus: SkuRow[];
  userId: number;
  period: string;
}) {
  const products = useMemo(() => computeAdsProducts(skus, crossRef), [skus, crossRef]);
  const [productFilter, setProductFilter] = useState<ProductFilter>("all");
  const [selectedProduct, setSelectedProduct] = useState<AdsProductRow | null>(null);
  const [bannerDismissed, setBannerDismissed] = useState(() => {
    try {
      return (
        localStorage.getItem(`ads_loss_banner_dismissed_${userId}_${period}`) === "1"
      );
    } catch {
      return false;
    }
  });

  function dismissBanner() {
    setBannerDismissed(true);
    try {
      localStorage.setItem(`ads_loss_banner_dismissed_${userId}_${period}`, "1");
    } catch {
      /* ignore */
    }
  }

  const filtered = useMemo(() => {
    let rows = [...products];
    if (productFilter === "loss") rows = rows.filter((p) => p.true_profit < 0);
    else if (productFilter === "high_cost") rows = rows.filter((p) => p.ad_cost_pct > 25);
    else if (productFilter === "profitable") rows = rows.filter((p) => p.true_margin_pct >= 30);
    return rows.sort((a, b) => b.total_revenue - a.total_revenue);
  }, [products, productFilter]);

  const lossMakers = useMemo(
    () => products.filter((p) => p.true_profit < 0),
    [products],
  );
  const totalLoss = useMemo(
    () => lossMakers.reduce((s, p) => s + Math.abs(p.true_profit), 0),
    [lossMakers],
  );

  if (skus.length === 0) {
    return (
      <div className="card text-center py-12 text-slate-400">
        Upload a settlement report to see product-level ad attribution.
      </div>
    );
  }

  const filterButtons: Array<{ key: ProductFilter; label: string; count: number }> = [
    { key: "all", label: "All Products", count: products.length },
    { key: "loss", label: "Loss After Ads", count: lossMakers.length },
    {
      key: "high_cost",
      label: "High Ad Cost",
      count: products.filter((p) => p.ad_cost_pct > 25).length,
    },
    {
      key: "profitable",
      label: "Best Margin",
      count: products.filter((p) => p.true_margin_pct >= 30).length,
    },
  ];

  return (
    <div className="space-y-4">
      {/* Feature 4 — Loss Alert Banner */}
      {!bannerDismissed && lossMakers.length > 0 && (
        <div className="rounded-xl border border-red-300 bg-red-50 px-4 py-3">
          <div className="flex items-start justify-between gap-3">
            <div className="flex-1 min-w-0">
              <p className="text-sm font-semibold text-red-800">
                🔴 {lossMakers.length} product{lossMakers.length > 1 ? "s" : ""} are losing money
                when ad spend is included
              </p>
              <p className="text-sm text-red-700 mt-0.5">
                Total loss: {formatINR(totalLoss)}
              </p>
              <button
                onClick={() => setProductFilter("loss")}
                className="mt-1.5 text-xs text-red-700 underline hover:text-red-900"
              >
                View loss-making products ↓
              </button>
            </div>
            <button
              onClick={dismissBanner}
              className="text-red-400 hover:text-red-700 flex-shrink-0"
              aria-label="Dismiss"
            >
              <X size={16} />
            </button>
          </div>
        </div>
      )}

      {/* Filter pills */}
      <div className="card">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
          <h3 className="text-sm font-semibold text-slate-700">Product Ad Attribution</h3>
          <div className="flex gap-2 flex-wrap">
            {filterButtons.map((f) => {
              const active = productFilter === f.key;
              const isLoss = f.key === "loss";
              return (
                <button
                  key={f.key}
                  onClick={() => setProductFilter(f.key)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-semibold border transition ${
                    active
                      ? isLoss
                        ? "bg-red-600 text-white border-red-600"
                        : "bg-slate-900 text-white border-slate-900"
                      : "bg-white text-slate-600 border-slate-200 hover:bg-slate-50"
                  }`}
                >
                  {f.label} ({f.count})
                </button>
              );
            })}
          </div>
        </div>

        {/* Feature 1 — Product table with new columns */}
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead className="text-left text-xs uppercase text-slate-500 border-b border-slate-200">
              <tr>
                <th className="px-3 py-2 font-semibold">Product</th>
                <th className="px-3 py-2 font-semibold">SKU</th>
                <th className="px-3 py-2 font-semibold">Category</th>
                <th className="px-3 py-2 font-semibold text-right">Revenue</th>
                <th className="px-3 py-2 font-semibold text-right">Settlement</th>
                <th className="px-3 py-2 font-semibold text-right">Ad Spend*</th>
                <th className="px-3 py-2 font-semibold text-right">Ad Cost %</th>
                <th className="px-3 py-2 font-semibold text-right">True Profit</th>
                <th className="px-3 py-2 font-semibold text-right">True Margin %</th>
                <th className="px-3 py-2 font-semibold text-right">Orders</th>
                <th className="px-3 py-2 font-semibold text-right">Return Rate</th>
                <th className="px-3 py-2 font-semibold text-center">Action</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {filtered.length === 0 && (
                <tr>
                  <td colSpan={12} className="px-3 py-6 text-center text-slate-400">
                    No products match this filter.
                  </td>
                </tr>
              )}
              {filtered.map((p) => (
                <ProductRow key={p.seller_sku} product={p} onOpen={setSelectedProduct} />
              ))}
            </tbody>
          </table>
        </div>
        <p className="text-[11px] text-slate-400 italic mt-3">
          * Ad spend is attributed proportionally from category-level campaign spend.
        </p>
      </div>

      {/* Feature 2 — SKU waterfall modal */}
      {selectedProduct && (
        <SkuAdsModal
          product={selectedProduct}
          onClose={() => setSelectedProduct(null)}
          crossRef={crossRef}
        />
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Feature 1 — product table row
// ---------------------------------------------------------------------------

function ProductRow({
  product: p,
  onOpen,
}: {
  product: AdsProductRow;
  onOpen: (p: AdsProductRow) => void;
}) {
  const marginColor =
    p.true_margin_pct > 30
      ? "text-emerald-600"
      : p.true_margin_pct >= 10
      ? "text-amber-600"
      : "text-red-600";

  const profitColor = p.true_profit >= 0 ? "text-emerald-700" : "text-red-600";

  const actionBtn = (() => {
    switch (p.profit_verdict) {
      case "pause_ads":
        return (
          <button
            onClick={() => onOpen(p)}
            className="px-2.5 py-1 text-[11px] font-semibold bg-red-100 text-red-700 rounded-lg hover:bg-red-200 transition"
          >
            Pause Ads
          </button>
        );
      case "reduce_budget":
        return (
          <button
            onClick={() => onOpen(p)}
            className="px-2.5 py-1 text-[11px] font-semibold bg-amber-100 text-amber-700 rounded-lg hover:bg-amber-200 transition"
          >
            Reduce Budget
          </button>
        );
      case "scale_up":
        return (
          <button
            onClick={() => onOpen(p)}
            className="px-2.5 py-1 text-[11px] font-semibold bg-emerald-100 text-emerald-700 rounded-lg hover:bg-emerald-200 transition"
          >
            Scale Up
          </button>
        );
      default:
        return (
          <button
            onClick={() => onOpen(p)}
            className="text-[11px] text-slate-500 hover:text-slate-800 underline"
          >
            Review
          </button>
        );
    }
  })();

  return (
    <tr className={p.true_profit < 0 ? "bg-red-50/40" : undefined}>
      <td
        className="px-3 py-2 max-w-[180px] truncate font-medium"
        title={p.product_name ?? p.seller_sku}
      >
        {p.product_name ?? p.seller_sku}
      </td>
      <td className="px-3 py-2 font-mono text-xs text-slate-500">{p.seller_sku}</td>
      <td className="px-3 py-2 text-xs capitalize text-slate-600">
        {(p.matched_category ?? p.category ?? "—").replace(/_/g, " ")}
      </td>
      <td className="px-3 py-2 text-right">{formatINR(p.total_revenue)}</td>
      <td className="px-3 py-2 text-right text-slate-600">{formatINR(p.net_settlement)}</td>
      <td className="px-3 py-2 text-right text-violet-700">{formatINR(p.attributed_ad_spend)}</td>
      <td
        className={`px-3 py-2 text-right font-semibold ${
          p.ad_cost_pct > 25 ? "text-red-600" : "text-slate-700"
        }`}
      >
        {p.ad_cost_pct.toFixed(1)}%
      </td>
      <td className={`px-3 py-2 text-right font-semibold ${profitColor}`}>
        {formatINR(p.true_profit)}
      </td>
      <td className={`px-3 py-2 text-right font-semibold ${marginColor}`}>
        {p.true_margin_pct.toFixed(1)}%
      </td>
      <td className="px-3 py-2 text-right">
        <span className="text-slate-800">{p.total_orders}</span>
        {p.return_orders > 0 && (
          <span className="block text-[10px] text-red-500">{p.return_orders} returns</span>
        )}
      </td>
      <td className="px-3 py-2 text-right text-slate-600">
        {(p.return_rate * 100).toFixed(1)}%
      </td>
      <td className="px-3 py-2 text-center">{actionBtn}</td>
    </tr>
  );
}

// ---------------------------------------------------------------------------
// Feature 2 — SKU Ads Modal with animated waterfall
// ---------------------------------------------------------------------------

function SkuAdsModal({
  product: p,
  onClose,
  crossRef,
}: {
  product: AdsProductRow;
  onClose: () => void;
  crossRef: AdsCategoryCrossRef[];
}) {
  const catEntry = crossRef.find(
    (c) =>
      c.category.toLowerCase() === (p.matched_category ?? "").toLowerCase(),
  );

  const gross = p.total_revenue;
  const mpFees = Math.abs(p.total_mp_fees);
  const returnsLoss = Math.abs(p.total_refunds) + Math.abs(p.total_reverse_shipping);
  const netSettlement = p.net_settlement;
  const adSpend = p.attributed_ad_spend;
  const trueProfit = p.true_profit;

  interface WaterfallBar {
    label: string;
    amount: number;
    type: "start" | "deduction" | "subtotal" | "end";
    color: string;
  }

  const bars: WaterfallBar[] = [
    { label: "Gross Revenue", amount: gross, type: "start", color: "bg-emerald-500" },
    { label: "− MP Fees", amount: -mpFees, type: "deduction", color: "bg-orange-400" },
    { label: "− Returns Loss", amount: -returnsLoss, type: "deduction", color: "bg-red-400" },
    { label: "= Net Settlement", amount: netSettlement, type: "subtotal", color: "bg-slate-300" },
    { label: "− Ad Spend*", amount: -adSpend, type: "deduction", color: "bg-violet-500" },
    {
      label: "= True Profit",
      amount: trueProfit,
      type: "end",
      color: trueProfit >= 0 ? "bg-emerald-700" : "bg-red-600",
    },
  ];

  const maxAbs = Math.max(gross, Math.abs(trueProfit), 1);

  const title = p.product_name?.trim() || p.seller_sku;

  return (
    <>
      <div className="fixed inset-0 bg-black/40 z-40" onClick={onClose} />
      <aside className="fixed right-0 top-0 h-full w-[480px] max-w-full bg-white shadow-2xl z-50 overflow-y-auto">
        <div className="flex items-start justify-between p-5 border-b border-slate-200 gap-3">
          <div className="min-w-0">
            <h2 className="font-semibold text-slate-900 break-words">{title}</h2>
            <p className="text-[11px] text-slate-400 font-mono mt-0.5 truncate">
              {p.seller_sku}
            </p>
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            className="text-slate-400 hover:text-slate-700 flex-shrink-0"
          >
            <X size={20} />
          </button>
        </div>

        <div className="p-5 space-y-5">
          {/* Waterfall */}
          <div>
            <h3 className="text-sm font-semibold text-slate-700 mb-3">
              Where your ₹{(gross / 1000).toFixed(0)}K goes
            </h3>
            <div className="space-y-2.5">
              {bars.map((bar, i) => {
                const widthPct = Math.min((Math.abs(bar.amount) / maxAbs) * 100, 100);
                const isSub = bar.type === "subtotal";
                const isEnd = bar.type === "end";
                return (
                  <div key={i} className="flex items-center gap-2">
                    <div className="w-36 text-xs text-slate-600 text-right font-medium shrink-0">
                      {bar.label}
                    </div>
                    <div className="flex-1 relative h-7 bg-slate-100 rounded overflow-hidden">
                      {isSub ? (
                        <div
                          className="h-full border-2 border-dashed border-slate-400 rounded"
                          style={{ width: `${widthPct}%` }}
                        />
                      ) : (
                        <div
                          className={`${bar.color} h-full rounded transition-all duration-500`}
                          style={{ width: `${widthPct}%` }}
                        />
                      )}
                    </div>
                    <div
                      className={`w-28 text-xs font-semibold text-right shrink-0 ${
                        bar.amount < 0
                          ? "text-red-600"
                          : isEnd && trueProfit < 0
                          ? "text-red-600"
                          : "text-slate-900"
                      }`}
                    >
                      {bar.amount < 0 && "−"}
                      {formatINR(Math.abs(bar.amount))}
                    </div>
                  </div>
                );
              })}
            </div>
            {catEntry && (
              <p className="text-[11px] text-slate-400 italic mt-4">
                * Ad spend attributed proportionally from {formatINR(catEntry.ad_spend)} spent on{" "}
                <span className="capitalize">{catEntry.category.replace(/_/g, " ")}</span>{" "}
                campaigns.
              </p>
            )}
          </div>

          {/* Key metrics grid */}
          <div className="grid grid-cols-2 gap-3">
            {[
              {
                label: "True Margin",
                value: `${p.true_margin_pct.toFixed(1)}%`,
                tone:
                  p.true_margin_pct > 30
                    ? "text-emerald-700"
                    : p.true_margin_pct >= 10
                    ? "text-amber-600"
                    : "text-red-600",
              },
              {
                label: "Ad Cost %",
                value: `${p.ad_cost_pct.toFixed(1)}%`,
                tone: p.ad_cost_pct > 25 ? "text-red-600" : "text-slate-800",
              },
              { label: "Orders", value: String(p.total_orders), tone: "text-slate-800" },
              {
                label: "Return Rate",
                value: `${(p.return_rate * 100).toFixed(1)}%`,
                tone:
                  p.return_rate > 0.15
                    ? "text-red-600"
                    : p.return_rate > 0.08
                    ? "text-amber-600"
                    : "text-emerald-700",
              },
            ].map((item) => (
              <div key={item.label} className="bg-slate-50 rounded-lg p-3">
                <p className="text-xs text-slate-500">{item.label}</p>
                <p className={`text-xl font-bold mt-0.5 ${item.tone}`}>{item.value}</p>
              </div>
            ))}
          </div>
        </div>
      </aside>
    </>
  );
}
