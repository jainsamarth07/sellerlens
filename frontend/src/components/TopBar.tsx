import { Upload } from "lucide-react";
import { useNavigate } from "react-router-dom";
import PeriodSelector from "./PeriodSelector";
import { useActivePeriod } from "../store/useAppStore";

interface Props {
  title: string;
  showPeriodSelector?: boolean;
}

export default function TopBar({ title, showPeriodSelector = true }: Props) {
  const active = useActivePeriod();
  const navigate = useNavigate();
  const platform = active?.upload.platform ?? "—";

  return (
    <header className="flex items-center justify-between bg-white border-b border-slate-200 px-8 py-4 sticky top-0 z-10">
      <h1 className="text-xl font-semibold text-slate-900">{title}</h1>

      <div className="flex items-center gap-3">
        {showPeriodSelector && <PeriodSelector />}

        {active && (
          <span
            className={`badge ${
              platform.toLowerCase() === "amazon"
                ? "bg-amber-100 text-amber-800"
                : "bg-blue-100 text-blue-800"
            }`}
          >
            {platform.charAt(0).toUpperCase() + platform.slice(1)}
          </span>
        )}

        <button
          onClick={() => navigate("/upload")}
          className="flex items-center gap-2 bg-slate-900 hover:bg-slate-700 text-white px-4 py-2 rounded-lg text-sm font-medium transition"
        >
          <Upload size={14} />
          Upload new report
        </button>
      </div>
    </header>
  );
}
