import axios from "axios";

const baseURL = import.meta.env.VITE_API_BASE_URL ?? "/api";

export const api = axios.create({ baseURL, timeout: 60000 });

// ---------- Auth interceptors ---------------------------------------------
// Attach the JWT (if any) to every outgoing request and bounce the user to
// /login on a 401. Kept in this file so every existing helper picks it up
// automatically without further changes.

const TOKEN_KEY = "sellerlens_token";

api.interceptors.request.use((config) => {
  try {
    const token = localStorage.getItem(TOKEN_KEY);
    if (token) {
      config.headers = config.headers ?? {};
      (config.headers as any).Authorization = `Bearer ${token}`;
    }
  } catch {
    /* ignore */
  }
  return config;
});

api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err?.response?.status === 401) {
      try {
        localStorage.removeItem(TOKEN_KEY);
      } catch {
        /* ignore */
      }
      const path = window.location.pathname;
      const isAuthRoute =
        path.startsWith("/login") ||
        path.startsWith("/signup") ||
        path.startsWith("/auth/callback");
      if (!isAuthRoute) {
        window.location.href = "/login";
      }
    }
    return Promise.reject(err);
  },
);

// ---------- Types ----------------------------------------------------------

export interface SettlementSummary {
  payment_duration: string;
  total_sale_orders: number;
  total_returns: number;
  gross_sales_amount: number;
  returns_reversal: number;
  marketplace_fees: number;
  tcs_amount: number;
  tds_amount: number;
  gst_on_mp_fees: number;
  ads_fees: number;
  net_bank_settlement: number;
  input_gst_tcs_credits: number;
  income_tax_credits: number;
  total_realizable_amount: number;
}

export interface SkuRow {
  seller_sku: string;
  total_revenue: number;
  total_mp_fees: number;
  total_refunds: number;
  total_reverse_shipping: number;
  net_settlement: number;
  units_sold: number;
  total_orders: number;
  return_orders: number;
  return_rate: number;
  avg_selling_price: number;
  net_per_unit: number;
  // Optional listing-file enrichment (present when a listing has been uploaded).
  product_name?: string | null;
  mrp?: number | null;
  listing_selling_price?: number | null;
  current_stock?: number | null;
  listing_status?: string | null;
  category?: string | null;
}

export interface ParsedSettlement {
  platform: string;
  summary: SettlementSummary;
  orders: any[];
  ads: any[];
  ads_total_spend: number;
  skus: SkuRow[];
  parsing_errors: string[];
}

export interface UploadResponse {
  upload_id: number;
  filename: string;
  platform: string;
  rows_parsed: number;
  rows_total?: number;
  summary: SettlementSummary;
  ads_total_spend: number;
  skus: SkuRow[];
  parsing_errors: string[];
  blob_url: string;
}

export interface UploadJobStep {
  key: "upload" | "read" | "parse" | "profit" | "insights";
  label: string;
  status: "pending" | "running" | "done" | "error";
  detail?: string;
}

export interface UploadJobStatus {
  job_id: string;
  status: "processing" | "complete" | "error";
  error: string | null;
  steps: UploadJobStep[];
  result: UploadResponse | null;
}

export interface Insight {
  type: "warning" | "opportunity" | "info";
  title: string;
  finding: string;
  action: string;
  rupee_impact: string;
}

export interface InsightReport {
  insights: Insight[];
  health_score: number;
  health_label: "Healthy" | "Needs Attention" | "Critical";
  one_line_summary: string;
}

export interface ChatResponse {
  answer: string;
  data_used: { type: string; value: string }[];
  follow_ups: string[];
  session_id: string;
}

export interface MultiPeriodResult {
  periods: string[];
  metrics: {
    revenue: number[];
    net_settlement: number[];
    return_rate: number[];
    mp_fee_pct: number[];
    ads_spend: number[];
    reclaimable_credits: number[];
  };
  pop_comparison: Record<string, any>;
  sku_trends: any[];
  ai_trend_analysis: Record<string, any>;
  best_month: string;
  worst_month: string;
  period_count: number;
}

// ---------- API helpers ----------------------------------------------------

export async function uploadSettlement(file: File, platform = "flipkart"): Promise<UploadResponse> {
  const form = new FormData();
  form.append("file", file);
  const res = await api.post<UploadResponse>(`/upload/?platform=${platform}`, form);
  return res.data;
}

export async function startUpload(file: File, platform = "flipkart"): Promise<{ job_id: string }> {
  const form = new FormData();
  form.append("file", file);
  const res = await api.post<{ job_id: string }>(`/upload/start?platform=${platform}`, form);
  return res.data;
}

export async function getUploadStatus(jobId: string): Promise<UploadJobStatus> {
  const res = await api.get<UploadJobStatus>(`/upload/status/${jobId}`);
  return res.data;
}

export function sampleDownloadUrl(): string {
  return `${baseURL}/upload/sample`;
}

export async function fetchInsights(payload: {
  summary: SettlementSummary;
  skus: SkuRow[];
  ads_total_spend: number;
}): Promise<InsightReport> {
  const res = await api.post<InsightReport>("/analytics/insights", payload);
  return res.data;
}

export async function chat(
  question: string,
  sessionId: string,
  payload: { upload_id?: number; seller_data?: any },
): Promise<ChatResponse> {
  const res = await api.post<ChatResponse>("/chat", {
    question,
    session_id: sessionId,
    ...payload,
  });
  return res.data;
}

export async function fetchSuggestions(uploadId: number): Promise<string[]> {
  const res = await api.get<{ questions: string[] }>(`/chat/suggestions/${uploadId}`);
  return res.data.questions;
}

export async function postSuggestions(sellerData: any): Promise<string[]> {
  const res = await api.post<{ questions: string[] }>("/chat/suggestions", sellerData);
  return res.data.questions;
}

export async function uploadMultiPeriod(files: File[]): Promise<MultiPeriodResult> {
  const form = new FormData();
  files.forEach((f) => form.append("files", f));
  const res = await api.post<MultiPeriodResult>("/analytics/multi-period", form);
  return res.data;
}

// ---------- Listing-file (optional product-name enrichment) ----------------

export interface ListingUploadResponse {
  filename: string;
  matched: number;
  total: number;
  unmatched_skus: string[];
  listing_count: number;
}

export interface ListingStatus {
  user_id: string;
  listing_count: number;
  has_listing: boolean;
}

export interface ListingProductInfo {
  product_name?: string | null;
  mrp?: number | null;
  selling_price?: number | null;
  current_stock?: number | null;
  status?: string | null;
  category?: string | null;
}

export async function uploadListingFile(file: File): Promise<ListingUploadResponse> {
  const form = new FormData();
  form.append("file", file);
  const res = await api.post<ListingUploadResponse>("/upload/listing", form);
  return res.data;
}

export async function fetchListingStatus(): Promise<ListingStatus> {
  const res = await api.get<ListingStatus>("/upload/listing/status");
  return res.data;
}

export async function fetchListingProducts(): Promise<Record<string, ListingProductInfo>> {
  const res = await api.get<{ user_id: string; products: Record<string, ListingProductInfo> }>(
    "/upload/listing/products",
  );
  return res.data.products ?? {};
}

export async function clearUserData(): Promise<void> {
  await api.post("/auth/data/clear");
}

// ---------- Persisted chat sessions ---------------------------------------

export interface ChatSessionMeta {
  id: string;
  label: string | null;
  settlement_period: string | null;
  created_at: string;
  updated_at: string;
  message_count: number;
}

export interface ChatMessageRow {
  id: string;
  role: "user" | "assistant";
  content: string;
  created_at: string;
}

export async function listChatSessions(): Promise<ChatSessionMeta[]> {
  const res = await api.get<ChatSessionMeta[]>("/chat/sessions");
  return res.data;
}

export async function createChatSession(
  label?: string,
  period?: string,
): Promise<ChatSessionMeta> {
  const res = await api.post<ChatSessionMeta>("/chat/sessions", { label, period });
  return res.data;
}

export async function fetchChatMessages(sessionId: string): Promise<ChatMessageRow[]> {
  const res = await api.get<ChatMessageRow[]>(`/chat/sessions/${sessionId}/messages`);
  return res.data;
}

export async function saveChatMessage(
  sessionId: string,
  role: "user" | "assistant",
  content: string,
): Promise<ChatMessageRow> {
  const res = await api.post<ChatMessageRow>(
    `/chat/sessions/${sessionId}/messages`,
    { role, content },
  );
  return res.data;
}

export async function deleteChatSession(sessionId: string): Promise<void> {
  await api.delete(`/chat/sessions/${sessionId}`);
}

// ---------- Ads analytics (additive) --------------------------------------

export interface AdsCampaign {
  id: number;
  campaign_id: string | null;
  campaign_name: string | null;
  status: string | null;
  ad_spend: number;
  revenue: number;
  roi: number;
  ctr_pct: number;
  conversion_rate_pct: number;
  verdict: "star" | "decent" | "watch" | "stop";
  views: number;
  clicks: number;
  conversions: number;
  mapped_category: string | null;
}

export interface AdsSummary {
  total_spend: number;
  total_revenue: number;
  overall_roi: number;
  wasted_spend: number;
  wasted_campaigns: number;
  underperforming_spend: number;
  campaigns_to_stop: string[];
  best_campaign: { name: string; roi: number } | null;
  worst_campaign: { name: string; roi: number } | null;
  total_campaigns: number;
  active_campaigns: number;
}

export interface AdsCategoryCrossRef {
  category: string;
  ad_spend: number;
  settlement_revenue: number;
  ad_cost_ratio_pct: number | null;
  verdict: "efficient" | "expensive" | "unclear";
}

/** Product row enriched with proportionally attributed ad spend. Computed client-side. */
export interface AdsProductRow extends SkuRow {
  attributed_ad_spend: number;
  ad_cost_pct: number;
  true_profit: number;
  true_margin_pct: number;
  profit_verdict: "pause_ads" | "reduce_budget" | "scale_up" | "review";
  matched_category: string | null;
}

export interface AdsInsight {
  type: "stop" | "scale" | "optimize" | "info";
  title: string;
  finding: string;
  action: string;
  monthly_impact: string;
}

export interface AdsAnalysis {
  settlement_period: string | null;
  campaigns: AdsCampaign[];
  summary: AdsSummary;
  category_cross_reference: AdsCategoryCrossRef[];
  ai_insights: { insights: AdsInsight[] } | null;
}

export interface AdsUploadResponse {
  filename: string;
  settlement_period: string | null;
  total_campaigns: number;
  active_campaigns: number;
  total_spend: number;
  total_revenue: number;
}

export async function uploadAdsFile(
  file: File,
  settlementPeriod?: string,
): Promise<AdsUploadResponse> {
  const form = new FormData();
  form.append("file", file);
  const qs = settlementPeriod ? `?settlement_period=${encodeURIComponent(settlementPeriod)}` : "";
  const res = await api.post<AdsUploadResponse>(`/upload/ads${qs}`, form);
  return res.data;
}

export async function fetchAdsAnalysis(
  settlementPeriod?: string,
  includeInsights = true,
): Promise<AdsAnalysis> {
  const params = new URLSearchParams();
  if (settlementPeriod) params.set("settlement_period", settlementPeriod);
  if (!includeInsights) params.set("include_insights", "false");
  const qs = params.toString() ? `?${params.toString()}` : "";
  const res = await api.get<AdsAnalysis>(`/ads/analysis${qs}`);
  return res.data;
}

export async function refreshAdsInsights(
  settlementPeriod?: string,
): Promise<{ ai_insights: { insights: AdsInsight[] } }> {
  const qs = settlementPeriod ? `?settlement_period=${encodeURIComponent(settlementPeriod)}` : "";
  const res = await api.post<{ ai_insights: { insights: AdsInsight[] } }>(
    `/ads/insights/refresh${qs}`,
  );
  return res.data;
}

export async function fetchAdsStatus(): Promise<{ has_ads: boolean }> {
  try {
    const res = await api.get<{ has_ads: boolean }>("/ads/status");
    return res.data;
  } catch (err: any) {
    if (err?.response?.status === 404) {
      return { has_ads: false };
    }
    throw err;
  }
}
