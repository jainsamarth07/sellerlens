import { useState } from "react";
import TopBar from "../components/TopBar";
import SKUTable from "../components/SKUTable";
import SkuDetailPanel from "../components/SkuDetailPanel";
import { useActivePeriod } from "../store/useAppStore";
import type { SkuRow } from "../lib/api";

export default function Products() {
  const active = useActivePeriod();
  const [selected, setSelected] = useState<SkuRow | null>(null);

  return (
    <div className="flex flex-col h-full overflow-y-auto">
      <TopBar title="Products" />
      <div className="p-6">
        {!active && (
          <div className="card text-sm text-slate-500">
            Upload a settlement report to view SKU performance.
          </div>
        )}
        {active && <SKUTable skus={active.upload.skus} onRowClick={setSelected} />}
      </div>
      <SkuDetailPanel sku={selected} onClose={() => setSelected(null)} />
    </div>
  );
}
