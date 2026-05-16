import { formatINR } from "../lib/format";
import type { SettlementSummary } from "../lib/api";

interface Props {
  summary: SettlementSummary;
  adsSpend: number;
}

interface Step {
  label: string;
  amount: number;
  cumulative: number;
  type: "start" | "deduction" | "end";
}

export default function WaterfallChart({ summary, adsSpend }: Props) {
  const gross = summary.gross_sales_amount || 0;
  const returns = Math.abs(summary.returns_reversal || 0);
  const fees = Math.abs(summary.marketplace_fees || 0);
  const taxes = Math.abs(summary.gst_on_mp_fees || 0) + Math.abs(summary.tcs_amount || 0) + Math.abs(summary.tds_amount || 0);
  const ads = Math.abs(adsSpend || summary.ads_fees || 0);
  const net = summary.net_bank_settlement || 0;

  let cumul = gross;
  const steps: Step[] = [
    { label: "Gross Sales", amount: gross, cumulative: gross, type: "start" },
  ];
  cumul -= returns;
  steps.push({ label: "Returns", amount: -returns, cumulative: cumul, type: "deduction" });
  cumul -= fees;
  steps.push({ label: "Marketplace Fees", amount: -fees, cumulative: cumul, type: "deduction" });
  cumul -= taxes;
  steps.push({ label: "Taxes", amount: -taxes, cumulative: cumul, type: "deduction" });
  cumul -= ads;
  steps.push({ label: "Ads Spend", amount: -ads, cumulative: cumul, type: "deduction" });
  steps.push({ label: "Net Settlement", amount: net, cumulative: net, type: "end" });

  const maxValue = gross || 1;

  return (
    <div className="card">
      <h3 className="font-semibold text-slate-900 mb-4">Where your ₹ goes</h3>
      <div className="space-y-3">
        {steps.map((s, i) => {
          const width = (Math.abs(s.amount) / maxValue) * 100;
          const isStart = s.type === "start";
          const isEnd = s.type === "end";
          const color = isStart
            ? "bg-blue-500"
            : isEnd
            ? "bg-brand-green"
            : "bg-red-400";
          return (
            <div key={i} className="flex items-center gap-3">
              <div className="w-32 text-sm text-slate-700 text-right font-medium">{s.label}</div>
              <div className="flex-1 relative h-7 bg-slate-100 rounded">
                <div
                  className={`${color} h-full rounded transition-all`}
                  style={{ width: `${Math.min(width, 100)}%` }}
                />
              </div>
              <div className={`w-32 text-sm font-semibold ${isStart || isEnd ? "text-slate-900" : "text-brand-red"}`}>
                {s.amount < 0 ? "-" : ""}
                {formatINR(Math.abs(s.amount))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
