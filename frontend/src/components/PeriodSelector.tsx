import { useAppStore } from "../store/useAppStore";

export default function PeriodSelector() {
  const { periods, activePeriodId, setActivePeriod } = useAppStore();

  if (periods.length === 0) {
    return (
      <span className="text-sm text-slate-500 italic">No periods uploaded</span>
    );
  }

  return (
    <select
      value={activePeriodId ?? ""}
      onChange={(e) => setActivePeriod(Number(e.target.value))}
      className="border border-slate-300 rounded-lg px-3 py-2 text-sm bg-white text-slate-700 focus:outline-none focus:ring-2 focus:ring-brand-green"
    >
      {periods.map((p) => (
        <option key={p.upload.upload_id} value={p.upload.upload_id}>
          {p.upload.summary?.payment_duration || p.upload.filename}
        </option>
      ))}
    </select>
  );
}
