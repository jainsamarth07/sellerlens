import axios from "axios";

const baseURL = import.meta.env.VITE_API_BASE_URL ?? "/api";

export const api = axios.create({ baseURL, timeout: 60000 });

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
