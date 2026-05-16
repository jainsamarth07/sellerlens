import { AlertTriangle, Lightbulb, Info } from "lucide-react";
import type { Insight } from "../lib/api";

interface Props {
  insight: Insight;
}

const styleByType = {
  warning: {
    Icon: AlertTriangle,
    border: "border-l-brand-red",
    iconBg: "bg-red-100 text-brand-red",
  },
  opportunity: {
    Icon: Lightbulb,
    border: "border-l-brand-green",
    iconBg: "bg-emerald-100 text-brand-green",
  },
  info: {
    Icon: Info,
    border: "border-l-brand-blue",
    iconBg: "bg-blue-100 text-brand-blue",
  },
};

export default function InsightCard({ insight }: Props) {
  const style = styleByType[insight.type] ?? styleByType.info;
  const Icon = style.Icon;

  return (
    <div className={`card border-l-4 ${style.border} flex gap-4`}>
      <div className={`${style.iconBg} rounded-lg p-2.5 h-fit`}>
        <Icon size={18} />
      </div>
      <div className="flex-1 min-w-0">
        <h4 className="font-semibold text-slate-900">{insight.title}</h4>
        <p className="text-sm text-slate-600 mt-1">{insight.finding}</p>
        <div className="flex items-center justify-between mt-3 pt-3 border-t border-slate-100">
          <button className="text-sm font-medium text-brand-blue hover:underline">
            {insight.action}
          </button>
          <span className="text-xs text-slate-500">
            Impact: <span className="font-semibold text-slate-700">{insight.rupee_impact}</span>
          </span>
        </div>
      </div>
    </div>
  );
}
