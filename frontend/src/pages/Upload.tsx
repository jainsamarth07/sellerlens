import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  UploadCloud,
  FileSpreadsheet,
  X,
  Check,
  Loader2,
  AlertTriangle,
  Download,
  ArrowRight,
  Sparkles,
  ShieldCheck,
} from "lucide-react";
import confetti from "canvas-confetti";
import TopBar from "../components/TopBar";
import {
  startUpload,
  getUploadStatus,
  sampleDownloadUrl,
  type UploadJobStatus,
  type UploadResponse,
} from "../lib/api";
import { useAppStore } from "../store/useAppStore";
import { formatINR } from "../lib/format";

type Phase = "select" | "processing" | "success" | "error";

const ACCEPT = ".csv,.xlsx,.xls";
const MAX_BYTES = 50 * 1024 * 1024;

function detectPeriodFromName(name: string): string | null {
  // Try simple patterns: "April-2026", "2026-04", "Apr2026"
  const monthRx = /(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*[-_ ]?(\d{4})/i;
  const isoRx = /(\d{4})[-_](\d{2})/;
  const m = name.match(monthRx);
  if (m) return `${m[1][0].toUpperCase()}${m[1].slice(1).toLowerCase()} ${m[2]}`;
  const i = name.match(isoRx);
  if (i) {
    const months = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"];
    return `${months[parseInt(i[2], 10) - 1] ?? ""} ${i[1]}`;
  }
  return null;
}

function fireConfetti() {
  const burst = (origin: { x: number; y: number }) =>
    confetti({
      particleCount: 80,
      spread: 70,
      origin,
      colors: ["#059669", "#2563EB", "#D97706", "#DC2626", "#7C3AED"],
    });
  burst({ x: 0.2, y: 0.6 });
  burst({ x: 0.5, y: 0.5 });
  burst({ x: 0.8, y: 0.6 });
}

export default function Upload() {
  const navigate = useNavigate();
  const addPeriod = useAppStore((s) => s.addPeriod);

  const [phase, setPhase] = useState<Phase>("select");
  const [drag, setDrag] = useState(false);
  const [files, setFiles] = useState<File[]>([]);
  const [job, setJob] = useState<UploadJobStatus | null>(null);
  const [result, setResult] = useState<UploadResponse | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const pollTimer = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (pollTimer.current) window.clearTimeout(pollTimer.current);
    };
  }, []);

  const acceptIncoming = (incoming: FileList | null) => {
    if (!incoming) return;
    const list = Array.from(incoming).filter((f) => {
      if (f.size > MAX_BYTES) {
        setErrorMessage(`${f.name} is larger than 50 MB.`);
        return false;
      }
      return true;
    });
    setFiles(list.slice(0, 6));
    setErrorMessage(null);
  };

  const removeFile = (idx: number) =>
    setFiles((prev) => prev.filter((_, i) => i !== idx));

  const pollOnce = async (jobId: string, fileName: string) => {
    try {
      const snap = await getUploadStatus(jobId);
      setJob(snap);

      if (snap.status === "complete" && snap.result) {
        setResult(snap.result);
        addPeriod(snap.result);
        setPhase("success");
        setTimeout(fireConfetti, 150);
        return;
      }
      if (snap.status === "error") {
        setErrorMessage(snap.error ?? "Processing failed.");
        setPhase("error");
        return;
      }
      pollTimer.current = window.setTimeout(() => pollOnce(jobId, fileName), 2000);
    } catch (e) {
      setErrorMessage((e as Error).message);
      setPhase("error");
    }
  };

  const handleStart = async () => {
    if (!files.length) return;
    setErrorMessage(null);
    setPhase("processing");
    setJob(null);
    setResult(null);
    try {
      const { job_id } = await startUpload(files[0]);
      pollOnce(job_id, files[0].name);
    } catch (e: any) {
      setErrorMessage(
        e?.response?.data?.detail ?? e?.message ?? "Upload failed.",
      );
      setPhase("error");
    }
  };

  const reset = () => {
    if (pollTimer.current) window.clearTimeout(pollTimer.current);
    setPhase("select");
    setFiles([]);
    setJob(null);
    setResult(null);
    setErrorMessage(null);
  };

  return (
    <div className="flex flex-col h-full overflow-y-auto">
      <TopBar title="Upload Settlement Report" />

      <div className="flex-1 px-6 py-10 flex justify-center">
        <div className="w-full max-w-3xl">
          {phase === "select" && (
            <SelectStep
              drag={drag}
              files={files}
              fileInput={fileInput}
              setDrag={setDrag}
              acceptIncoming={acceptIncoming}
              removeFile={removeFile}
              onStart={handleStart}
              errorMessage={errorMessage}
            />
          )}

          {phase === "processing" && (
            <ProcessingStep job={job} fileName={files[0]?.name ?? ""} />
          )}

          {phase === "success" && result && (
            <SuccessStep result={result} onView={() => navigate("/dashboard")} />
          )}

          {phase === "error" && (
            <ErrorStep message={errorMessage ?? "Something went wrong."} onRetry={reset} />
          )}
        </div>
      </div>
    </div>
  );
}

// ---------- Step 1: SELECT ---------------------------------------------------

interface SelectProps {
  drag: boolean;
  files: File[];
  fileInput: React.RefObject<HTMLInputElement>;
  setDrag: (v: boolean) => void;
  acceptIncoming: (f: FileList | null) => void;
  removeFile: (i: number) => void;
  onStart: () => void;
  errorMessage: string | null;
}

function SelectStep({
  drag, files, fileInput, setDrag, acceptIncoming, removeFile, onStart, errorMessage,
}: SelectProps) {
  return (
    <div className="space-y-6">
      <div className="text-center">
        <h2 className="text-3xl font-bold text-slate-900 mb-2">
          See your real profit in seconds
        </h2>
        <p className="text-slate-500">
          Upload your Flipkart or Amazon settlement report — we'll do the rest.
        </p>
      </div>

      <div
        onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDrag(false);
          acceptIncoming(e.dataTransfer.files);
        }}
        className={`border-2 border-dashed rounded-2xl p-12 text-center transition ${
          drag
            ? "border-brand-green bg-emerald-50 scale-[1.01]"
            : "border-slate-300 bg-slate-50 hover:border-brand-green hover:bg-emerald-50/40"
        }`}
      >
        <UploadCloud className="mx-auto text-brand-green mb-3" size={56} />
        <p className="text-lg font-semibold text-slate-900">
          Drop your Flipkart or Amazon settlement report here
        </p>
        <p className="text-sm text-slate-500 mt-2">
          Supports .xlsx, .xls, .csv — up to 50 MB
        </p>
        <button
          type="button"
          onClick={() => fileInput.current?.click()}
          className="mt-5 text-brand-green font-semibold hover:underline"
        >
          Or browse files
        </button>
        <input
          ref={fileInput}
          type="file"
          accept={ACCEPT}
          multiple
          className="hidden"
          onChange={(e) => acceptIncoming(e.target.files)}
        />
      </div>

      {files.length > 0 && (
        <ul className="space-y-2">
          {files.map((f, i) => {
            const period = detectPeriodFromName(f.name);
            return (
              <li
                key={`${f.name}-${i}`}
                className="flex items-center justify-between bg-white border border-slate-200 rounded-lg px-4 py-3"
              >
                <div className="flex items-center gap-3 min-w-0">
                  <FileSpreadsheet className="text-emerald-600 shrink-0" size={20} />
                  <div className="min-w-0">
                    <p className="text-sm font-medium text-slate-900 truncate">{f.name}</p>
                    <p className="text-xs text-slate-500">
                      {(f.size / 1024).toFixed(1)} KB
                      {period && <> · period detected: <span className="text-brand-green font-medium">{period}</span></>}
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => removeFile(i)}
                  className="text-slate-400 hover:text-brand-red"
                  aria-label="Remove file"
                >
                  <X size={18} />
                </button>
              </li>
            );
          })}
        </ul>
      )}

      {errorMessage && (
        <div className="flex items-start gap-2 text-sm text-brand-red bg-red-50 border border-red-200 rounded-lg px-3 py-2">
          <AlertTriangle size={16} className="mt-0.5 shrink-0" />
          <span>{errorMessage}</span>
        </div>
      )}

      <div className="flex flex-col sm:flex-row items-center justify-between gap-4 pt-2">
        <a
          href={sampleDownloadUrl()}
          className="text-sm text-slate-600 hover:text-brand-green flex items-center gap-1.5"
        >
          <Download size={14} />
          Download sample Flipkart template
        </a>
        <button
          onClick={onStart}
          disabled={files.length === 0}
          className="bg-brand-green text-white px-6 py-2.5 rounded-lg font-medium flex items-center gap-2 hover:bg-emerald-700 disabled:opacity-40 disabled:cursor-not-allowed"
        >
          Analyze report
          <ArrowRight size={16} />
        </button>
      </div>

      <div className="flex items-center justify-center gap-2 pt-4 text-xs text-slate-400">
        <ShieldCheck size={14} />
        Your data is encrypted in transit and stored securely in Azure.
      </div>
    </div>
  );
}

// ---------- Step 2: PROCESSING ----------------------------------------------

function ProcessingStep({ job, fileName }: { job: UploadJobStatus | null; fileName: string }) {
  // Default step labels shown before the first poll completes.
  const fallback = [
    { key: "upload", label: "File uploaded securely", status: "running", detail: "" },
    { key: "read", label: "Reading report structure", status: "pending", detail: "" },
    { key: "parse", label: "Parsing transactions", status: "pending", detail: "" },
    { key: "profit", label: "Calculating profit per SKU", status: "pending", detail: "" },
    { key: "insights", label: "Generating AI insights", status: "pending", detail: "" },
  ] as const;

  const steps = job?.steps ?? fallback;

  return (
    <div className="space-y-8">
      <div className="text-center">
        <Sparkles className="mx-auto text-brand-green mb-2" size={36} />
        <h2 className="text-2xl font-bold text-slate-900">Analyzing your report…</h2>
        <p className="text-slate-500 mt-1 text-sm">
          {fileName} · usually takes 15–30 seconds
        </p>
      </div>

      <div className="bg-white border border-slate-200 rounded-2xl p-6 space-y-3">
        {steps.map((step) => {
          const labelText =
            step.label +
            (step.status === "done" && step.detail ? ` (${step.detail})` : "");
          return (
            <div key={step.key} className="flex items-center gap-3">
              <StepIcon status={step.status} />
              <span
                className={`text-sm ${
                  step.status === "done"
                    ? "text-slate-900"
                    : step.status === "running"
                    ? "text-slate-700 font-medium"
                    : step.status === "error"
                    ? "text-brand-red"
                    : "text-slate-400"
                }`}
              >
                {labelText}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function StepIcon({ status }: { status: string }) {
  if (status === "done") {
    return (
      <span className="w-6 h-6 rounded-full bg-emerald-100 text-brand-green flex items-center justify-center">
        <Check size={14} />
      </span>
    );
  }
  if (status === "running") {
    return (
      <span className="w-6 h-6 rounded-full bg-emerald-50 text-brand-green flex items-center justify-center">
        <Loader2 size={14} className="animate-spin" />
      </span>
    );
  }
  if (status === "error") {
    return (
      <span className="w-6 h-6 rounded-full bg-red-100 text-brand-red flex items-center justify-center">
        <AlertTriangle size={14} />
      </span>
    );
  }
  return <span className="w-6 h-6 rounded-full border-2 border-slate-200" />;
}

// ---------- Step 3: SUCCESS --------------------------------------------------

function SuccessStep({
  result,
  onView,
}: {
  result: UploadResponse;
  onView: () => void;
}) {
  const period = result.summary?.payment_duration ?? "your report";
  const reclaim =
    (result.summary?.input_gst_tcs_credits ?? 0) +
    (result.summary?.income_tax_credits ?? 0) +
    Math.abs(result.summary?.tcs_amount ?? 0) +
    Math.abs(result.summary?.tds_amount ?? 0);
  const partial =
    result.parsing_errors.length > 0 &&
    typeof result.rows_total === "number" &&
    result.rows_parsed < result.rows_total;

  return (
    <div className="text-center space-y-6 py-8">
      <div className="w-20 h-20 rounded-full bg-emerald-100 text-brand-green mx-auto flex items-center justify-center">
        <Check size={44} />
      </div>
      <div>
        <h2 className="text-3xl font-bold text-slate-900">
          Your {period} data is ready!
        </h2>
        <p className="text-slate-500 mt-2">
          Parsed {result.rows_parsed} transactions across {result.skus.length} SKUs.
        </p>
      </div>

      {reclaim > 0 && (
        <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-5 inline-block mx-auto">
          <p className="text-sm text-slate-600">We found</p>
          <p className="text-3xl font-bold text-brand-green mt-1">
            {formatINR(reclaim)}
          </p>
          <p className="text-sm text-slate-600 mt-1">in unclaimed credits</p>
        </div>
      )}

      {partial && (
        <p className="text-sm text-amber-700 bg-amber-50 border border-amber-200 rounded-lg px-4 py-2 inline-block">
          We processed {result.rows_parsed} of {result.rows_total} rows.{" "}
          {(result.rows_total ?? 0) - result.rows_parsed} rows had missing data.
        </p>
      )}

      <button
        onClick={onView}
        className="bg-brand-green text-white px-8 py-3 rounded-lg font-semibold flex items-center gap-2 mx-auto hover:bg-emerald-700 text-base"
      >
        View Dashboard
        <ArrowRight size={18} />
      </button>
    </div>
  );
}

// ---------- Step 4: ERROR ----------------------------------------------------

function ErrorStep({ message, onRetry }: { message: string; onRetry: () => void }) {
  const looksLikeFormat = /format|sheet|column|parse|excel|csv/i.test(message);
  return (
    <div className="text-center space-y-5 py-8">
      <div className="w-20 h-20 rounded-full bg-red-100 text-brand-red mx-auto flex items-center justify-center">
        <AlertTriangle size={40} />
      </div>
      <h2 className="text-2xl font-bold text-slate-900">
        {looksLikeFormat
          ? "This doesn't look like a settlement report"
          : "Something went wrong"}
      </h2>
      <p className="text-slate-600 max-w-md mx-auto text-sm">
        {looksLikeFormat
          ? "Download a sample template to see the expected format, then try again."
          : message}
      </p>
      <div className="flex flex-col sm:flex-row gap-3 justify-center">
        <a
          href={sampleDownloadUrl()}
          className="inline-flex items-center gap-2 border border-slate-300 px-5 py-2.5 rounded-lg text-sm font-medium text-slate-700 hover:bg-slate-50"
        >
          <Download size={14} />
          Download sample
        </a>
        <button
          onClick={onRetry}
          className="bg-brand-green text-white px-5 py-2.5 rounded-lg text-sm font-medium hover:bg-emerald-700"
        >
          Try a different file
        </button>
      </div>
    </div>
  );
}
