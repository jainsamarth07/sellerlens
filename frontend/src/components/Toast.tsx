/**
 * Minimal toast component — a single-message, auto-dismiss notification.
 * Kept dependency-free (no react-hot-toast / sonner / etc.) so the bundle
 * stays small and the existing setup is untouched.
 */

import { useEffect } from "react";
import { CheckCircle, AlertCircle, X } from "lucide-react";

export interface ToastMessage {
  id: string;
  kind: "success" | "error" | "info";
  text: string;
}

interface Props {
  toast: ToastMessage | null;
  onDismiss: () => void;
  durationMs?: number;
}

export default function Toast({ toast, onDismiss, durationMs = 4000 }: Props) {
  useEffect(() => {
    if (!toast) return;
    const t = window.setTimeout(onDismiss, durationMs);
    return () => window.clearTimeout(t);
  }, [toast, onDismiss, durationMs]);

  if (!toast) return null;

  const styles =
    toast.kind === "success"
      ? "bg-emerald-50 border-emerald-200 text-emerald-900"
      : toast.kind === "error"
      ? "bg-red-50 border-red-200 text-red-900"
      : "bg-blue-50 border-blue-200 text-blue-900";

  const Icon = toast.kind === "error" ? AlertCircle : CheckCircle;

  return (
    <div
      role="status"
      aria-live="polite"
      className={`fixed bottom-6 right-6 z-50 flex items-start gap-3 max-w-sm rounded-lg border px-4 py-3 shadow-lg ${styles}`}
    >
      <Icon size={18} className="mt-0.5 flex-shrink-0" />
      <div className="flex-1 text-sm">{toast.text}</div>
      <button
        onClick={onDismiss}
        aria-label="Dismiss"
        className="text-current opacity-60 hover:opacity-100"
      >
        <X size={16} />
      </button>
    </div>
  );
}
