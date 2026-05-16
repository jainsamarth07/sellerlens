import type { LucideIcon } from "lucide-react";
import { ArrowDown, ArrowUp, Minus } from "lucide-react";

type Tone = "positive" | "negative" | "warning" | "neutral";

interface Props {
  icon: LucideIcon;
  label: string;
  value: string;
  subValue?: string;
  changePct?: number;
  tone?: Tone;
}

const toneStyles: Record<Tone, { bg: string; text: string; iconBg: string }> = {
  positive: { bg: "bg-emerald-50", text: "text-brand-green", iconBg: "bg-emerald-100" },
  negative: { bg: "bg-red-50", text: "text-brand-red", iconBg: "bg-red-100" },
  warning: { bg: "bg-amber-50", text: "text-brand-amber", iconBg: "bg-amber-100" },
  neutral: { bg: "bg-slate-50", text: "text-slate-700", iconBg: "bg-slate-100" },
};

export default function MetricCard({
  icon: Icon,
  label,
  value,
  subValue,
  changePct,
  tone = "neutral",
}: Props) {
  const styles = toneStyles[tone];
  const ChangeIcon =
    changePct === undefined ? null : changePct > 0 ? ArrowUp : changePct < 0 ? ArrowDown : Minus;
  const changeColor =
    changePct === undefined
      ? ""
      : tone === "negative" || tone === "warning"
      ? changePct > 0
        ? "text-brand-red"
        : "text-brand-green"
      : changePct >= 0
      ? "text-brand-green"
      : "text-brand-red";

  return (
    <div className="card flex items-start gap-4">
      <div className={`${styles.iconBg} ${styles.text} rounded-lg p-3`}>
        <Icon size={22} />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-sm text-slate-500 font-medium">{label}</p>
        <p className="text-2xl font-bold text-slate-900 mt-1 truncate">{value}</p>
        <div className="flex items-center gap-2 mt-1.5">
          {ChangeIcon && (
            <span className={`flex items-center gap-0.5 text-xs font-semibold ${changeColor}`}>
              <ChangeIcon size={12} />
              {Math.abs(changePct!).toFixed(1)}%
            </span>
          )}
          {subValue && <span className="text-xs text-slate-500">{subValue}</span>}
        </div>
      </div>
    </div>
  );
}
