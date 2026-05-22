import { X } from "lucide-react";
import type { SkuRow } from "../lib/api";
import { formatINR, formatPct } from "../lib/format";

interface Props {
  sku: SkuRow | null;
  onClose: () => void;
}

export default function SkuDetailPanel({ sku, onClose }: Props) {
  if (!sku) return null;

  const rows: [string, string][] = [
    ["Total Revenue", formatINR(sku.total_revenue)],
    ["Net Settlement", formatINR(sku.net_settlement)],
    ["Marketplace Fees", formatINR(sku.total_mp_fees)],
    ["Refunds", formatINR(sku.total_refunds)],
    ["Reverse Shipping", formatINR(sku.total_reverse_shipping)],
    ["Units Sold", String(sku.units_sold)],
    ["Total Orders", String(sku.total_orders)],
    ["Return Orders", String(sku.return_orders)],
    ["Return Rate", formatPct(sku.return_rate)],
    ["Avg Selling Price", formatINR(sku.avg_selling_price)],
    ["Net Per Unit", formatINR(sku.net_per_unit)],
  ];

  // Listing-derived rows (only shown when present).
  const listingRows: [string, string][] = [];
  if (sku.mrp != null) listingRows.push(["MRP (Listing)", formatINR(sku.mrp)]);
  if (sku.listing_selling_price != null)
    listingRows.push(["Listing Price", formatINR(sku.listing_selling_price)]);
  if (sku.current_stock != null)
    listingRows.push(["Current Stock", String(sku.current_stock)]);
  if (sku.listing_status)
    listingRows.push(["Listing Status", sku.listing_status]);
  if (sku.category) listingRows.push(["Category", sku.category]);

  const title = sku.product_name?.trim() || sku.seller_sku;
  const showSubtitle = Boolean(sku.product_name);

  return (
    <>
      <div className="fixed inset-0 bg-black/30 z-40" onClick={onClose} />
      <aside className="fixed right-0 top-0 h-full w-96 bg-white shadow-xl z-50 overflow-y-auto">
        <div className="flex items-start justify-between p-5 border-b border-slate-200 gap-3">
          <div className="min-w-0">
            <h2 className="font-semibold text-slate-900 break-words">{title}</h2>
            {showSubtitle && (
              <p className="text-[11px] text-slate-400 font-mono mt-0.5 truncate">
                {sku.seller_sku}
              </p>
            )}
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            className="text-slate-400 hover:text-slate-700"
          >
            <X size={20} />
          </button>
        </div>
        <div className="p-5 space-y-2">
          {rows.map(([label, value]) => (
            <div
              key={label}
              className="flex justify-between py-2 border-b border-slate-100 last:border-0"
            >
              <span className="text-sm text-slate-500">{label}</span>
              <span className="text-sm font-medium text-slate-900">{value}</span>
            </div>
          ))}
          {listingRows.length > 0 && (
            <div className="pt-4">
              <h3 className="text-xs uppercase tracking-wide text-slate-400 font-semibold mb-1">
                From your listing
              </h3>
              {listingRows.map(([label, value]) => (
                <div
                  key={label}
                  className="flex justify-between py-2 border-b border-slate-100 last:border-0"
                >
                  <span className="text-sm text-slate-500">{label}</span>
                  <span className="text-sm font-medium text-slate-900">{value}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </aside>
    </>
  );
}
