import { useMemo, useState } from "react";
import { Search, ChevronUp, ChevronDown } from "lucide-react";
import type { SkuRow } from "../lib/api";
import { formatINR, formatPct } from "../lib/format";

interface Props {
  skus: SkuRow[];
  onRowClick?: (sku: SkuRow) => void;
}

type SortKey = keyof Pick<
  SkuRow,
  "seller_sku" | "total_revenue" | "total_mp_fees" | "total_refunds" | "net_settlement" | "return_rate"
>;

function statusOf(sku: SkuRow): { label: string; color: string } {
  if (sku.net_settlement < 0 || sku.net_per_unit < 0) {
    return { label: "Loss", color: "bg-red-100 text-brand-red" };
  }
  if (sku.return_rate > 10) return { label: "Watch", color: "bg-amber-100 text-brand-amber" };
  return { label: "Profitable", color: "bg-emerald-100 text-brand-green" };
}

export default function SKUTable({ skus, onRowClick }: Props) {
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<{ key: SortKey; dir: "asc" | "desc" }>({
    key: "net_settlement",
    dir: "desc",
  });

  const sorted = useMemo(() => {
    const filtered = skus.filter((s) =>
      s.seller_sku.toLowerCase().includes(query.toLowerCase()),
    );
    return [...filtered].sort((a, b) => {
      const va = a[sort.key] as any;
      const vb = b[sort.key] as any;
      if (typeof va === "string") {
        return sort.dir === "asc" ? va.localeCompare(vb) : vb.localeCompare(va);
      }
      return sort.dir === "asc" ? va - vb : vb - va;
    });
  }, [skus, query, sort]);

  const setSortKey = (key: SortKey) =>
    setSort((s) => ({
      key,
      dir: s.key === key && s.dir === "desc" ? "asc" : "desc",
    }));

  const SortHead = ({ k, label }: { k: SortKey; label: string }) => (
    <th
      className="text-left px-4 py-2 cursor-pointer hover:text-slate-900 select-none"
      onClick={() => setSortKey(k)}
    >
      <span className="inline-flex items-center gap-1">
        {label}
        {sort.key === k && (sort.dir === "desc" ? <ChevronDown size={12} /> : <ChevronUp size={12} />)}
      </span>
    </th>
  );

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold text-slate-900">SKU Performance</h3>
        <div className="relative">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search SKU…"
            className="pl-9 pr-3 py-1.5 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-green w-56"
          />
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="text-xs uppercase text-slate-500 border-b border-slate-200">
            <tr>
              <SortHead k="seller_sku" label="SKU" />
              <SortHead k="total_revenue" label="Revenue" />
              <SortHead k="total_mp_fees" label="MP Fees" />
              <SortHead k="total_refunds" label="Returns" />
              <SortHead k="net_settlement" label="Net" />
              <SortHead k="return_rate" label="Return %" />
              <th className="text-left px-4 py-2">Status</th>
              <th className="text-right px-4 py-2">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {sorted.length === 0 && (
              <tr>
                <td colSpan={8} className="text-center text-slate-400 py-8">
                  No SKUs match your search.
                </td>
              </tr>
            )}
            {sorted.map((s) => {
              const status = statusOf(s);
              return (
                <tr
                  key={s.seller_sku}
                  onClick={() => onRowClick?.(s)}
                  className="hover:bg-slate-50 cursor-pointer"
                >
                  <td className="px-4 py-3 font-medium text-slate-900">{s.seller_sku}</td>
                  <td className="px-4 py-3">{formatINR(s.total_revenue)}</td>
                  <td className="px-4 py-3 text-brand-red">{formatINR(s.total_mp_fees)}</td>
                  <td className="px-4 py-3 text-brand-red">{formatINR(s.total_refunds)}</td>
                  <td className={`px-4 py-3 font-semibold ${s.net_settlement >= 0 ? "text-brand-green" : "text-brand-red"}`}>
                    {formatINR(s.net_settlement)}
                  </td>
                  <td className="px-4 py-3">{formatPct(s.return_rate)}</td>
                  <td className="px-4 py-3">
                    <span className={`badge ${status.color}`}>{status.label}</span>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <button className="text-brand-blue text-xs font-medium hover:underline">
                      View →
                    </button>
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
