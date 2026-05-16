import TopBar from "../components/TopBar";
import ChatInterface from "../components/ChatInterface";
import { useActivePeriod } from "../store/useAppStore";
import { formatINR, formatPct } from "../lib/format";

export default function Chat() {
  const active = useActivePeriod();
  const s = active?.upload.summary;

  return (
    <div className="flex flex-col h-full">
      <TopBar title="Chat with your data" />

      <div className="flex-1 grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-6 p-6 min-h-0">
        <div className="min-h-0">
          <ChatInterface />
        </div>

        <aside className="space-y-4">
          <div className="card">
            <h3 className="font-semibold text-slate-900 mb-3 text-sm uppercase tracking-wide text-slate-500">
              Active Period
            </h3>
            {!active && (
              <p className="text-sm text-slate-500">Upload a report to begin.</p>
            )}
            {active && s && (
              <dl className="space-y-2 text-sm">
                <Row label="Period" value={s.payment_duration} />
                <Row label="Gross Sales" value={formatINR(s.gross_sales_amount)} />
                <Row label="Net Settlement" value={formatINR(s.net_bank_settlement)} />
                <Row label="Orders" value={String(s.total_sale_orders)} />
                <Row label="Returns" value={String(s.total_returns)} />
                <Row
                  label="Return Rate"
                  value={formatPct(
                    s.total_sale_orders ? (s.total_returns / s.total_sale_orders) * 100 : 0,
                  )}
                />
                <Row label="MP Fees" value={formatINR(s.marketplace_fees)} />
                <Row label="Ads Spend" value={formatINR(active.upload.ads_total_spend)} />
              </dl>
            )}
          </div>
        </aside>
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between border-b border-slate-100 pb-1.5 last:border-0">
      <dt className="text-slate-500">{label}</dt>
      <dd className="text-slate-900 font-medium">{value}</dd>
    </div>
  );
}
