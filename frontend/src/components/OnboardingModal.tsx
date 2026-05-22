import { useEffect, useState } from "react";
import { CheckCircle2, FileText, Sparkles, Upload } from "lucide-react";

const KEY = "sellerlens_onboarded";

const STEPS = [
  {
    icon: Upload,
    title: "Upload your settlement report",
    body: "Drop a Flipkart or Amazon settlement file to see your real profit picture.",
  },
  {
    icon: FileText,
    title: "Upload your listing file (optional)",
    body: "Map SKU codes to readable product names so insights show what you actually sell.",
  },
  {
    icon: Sparkles,
    title: "Ask the AI anything",
    body: "Open Chat with AI and ask questions like \u201cwhich SKUs are losing money?\u201d",
  },
];

export default function OnboardingModal() {
  const [open, setOpen] = useState(false);
  const [step, setStep] = useState(0);

  useEffect(() => {
    try {
      if (!localStorage.getItem(KEY)) setOpen(true);
    } catch {
      /* ignore */
    }
  }, []);

  const dismiss = () => {
    try {
      localStorage.setItem(KEY, "true");
    } catch {
      /* ignore */
    }
    setOpen(false);
  };

  if (!open) return null;

  const Step = STEPS[step];
  const Icon = Step.icon;
  const isLast = step === STEPS.length - 1;

  return (
    <div className="fixed inset-0 z-[100] bg-black/40 flex items-center justify-center px-4">
      <div className="bg-white rounded-2xl shadow-xl max-w-md w-full p-6">
        <div className="flex items-center gap-2 text-xs text-slate-500">
          {STEPS.map((_, i) => (
            <span
              key={i}
              className={`h-1.5 flex-1 rounded ${i <= step ? "bg-brand-green" : "bg-slate-200"}`}
            />
          ))}
        </div>
        <div className="mt-5 flex items-start gap-3">
          <div className="bg-emerald-50 text-brand-green rounded-lg p-2">
            <Icon size={22} />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-slate-900">{Step.title}</h3>
            <p className="text-sm text-slate-600 mt-1">{Step.body}</p>
          </div>
        </div>
        <div className="flex justify-between mt-6">
          <button
            onClick={dismiss}
            className="text-xs text-slate-500 hover:text-slate-900"
          >
            Skip tour
          </button>
          <button
            onClick={() => (isLast ? dismiss() : setStep((s) => s + 1))}
            className="flex items-center gap-1 bg-brand-green hover:bg-emerald-700 text-white text-sm font-medium px-4 py-2 rounded-lg"
          >
            {isLast ? (
              <>
                <CheckCircle2 size={14} /> Got it
              </>
            ) : (
              "Next"
            )}
          </button>
        </div>
      </div>
    </div>
  );
}
