import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Eye, EyeOff, Loader2 } from "lucide-react";
import MicrosoftLogo from "../components/MicrosoftLogo";
import { useAuthStore } from "../store/useAuth";
import { microsoftAuthUrl } from "../lib/authApi";

const REVENUE_OPTIONS = ["<1L", "1L-10L", "10L-50L", "50L+"];

function scorePassword(pw: string): { score: number; label: string; tone: string } {
  let score = 0;
  if (pw.length >= 8) score++;
  if (pw.length >= 12) score++;
  if (/[A-Z]/.test(pw) && /[a-z]/.test(pw)) score++;
  if (/[0-9]/.test(pw)) score++;
  if (/[^A-Za-z0-9]/.test(pw)) score++;
  const labels = ["Too short", "Weak", "Fair", "Good", "Strong", "Excellent"];
  const tones = ["bg-red-300", "bg-red-400", "bg-amber-400", "bg-emerald-400", "bg-emerald-500", "bg-emerald-600"];
  return { score, label: labels[score], tone: tones[score] };
}

export default function Signup() {
  const signupEmail = useAuthStore((s) => s.signupEmail);
  const navigate = useNavigate();

  const [businessName, setBusinessName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [platforms, setPlatforms] = useState<string[]>(["flipkart"]);
  const [revenue, setRevenue] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const [msBusy, setMsBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const pwScore = useMemo(() => scorePassword(password), [password]);

  const togglePlatform = (p: string) => {
    setPlatforms((prev) =>
      prev.includes(p) ? prev.filter((x) => x !== p) : [...prev, p],
    );
  };

  const handleMicrosoft = async () => {
    setError(null);
    setMsBusy(true);
    try {
      const url = await microsoftAuthUrl();
      window.location.href = url;
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? "Microsoft signup unavailable.");
      setMsBusy(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    setBusy(true);
    try {
      await signupEmail({
        email,
        password,
        business_name: businessName || undefined,
        platform: platforms.join(",") || "flipkart",
        monthly_revenue_range: revenue || undefined,
      });
      navigate("/dashboard", { replace: true });
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Sign up failed.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 px-4 py-8">
      <div className="w-full max-w-md bg-white rounded-2xl shadow-lg p-8">
        <h1 className="text-2xl font-bold text-slate-900 text-center">Create your account</h1>
        <p className="text-sm text-slate-500 text-center mt-1 mb-5">
          Start analysing your settlement reports in minutes
        </p>

        <button
          onClick={handleMicrosoft}
          disabled={msBusy}
          className="w-full flex items-center justify-center gap-3 bg-[#2F2F2F] hover:bg-black text-white font-medium py-3 rounded-lg transition disabled:opacity-60"
        >
          {msBusy ? (
            <Loader2 size={16} className="animate-spin" />
          ) : (
            <MicrosoftLogo size={18} />
          )}
          <span>Faster: Sign up with Microsoft</span>
        </button>
        <p className="text-[11px] text-center text-slate-400 mt-1">
          No password needed — use your existing Microsoft account
        </p>

        <div className="flex items-center my-5">
          <div className="flex-1 h-px bg-slate-200" />
          <span className="px-3 text-xs uppercase tracking-wide text-slate-400">or</span>
          <div className="flex-1 h-px bg-slate-200" />
        </div>

        <form onSubmit={handleSubmit} className="space-y-3">
          <input
            placeholder="Business name"
            value={businessName}
            onChange={(e) => setBusinessName(e.target.value)}
            className="w-full border border-slate-300 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-green"
          />
          <input
            type="email"
            autoComplete="email"
            placeholder="Email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full border border-slate-300 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-green"
          />
          <div>
            <div className="relative">
              <input
                type={show ? "text" : "password"}
                autoComplete="new-password"
                placeholder="Password (8+ characters)"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full border border-slate-300 rounded-lg px-3 py-2.5 pr-10 text-sm focus:outline-none focus:ring-2 focus:ring-brand-green"
              />
              <button
                type="button"
                onClick={() => setShow((v) => !v)}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-700 p-1"
                aria-label={show ? "Hide password" : "Show password"}
              >
                {show ? <EyeOff size={14} /> : <Eye size={14} />}
              </button>
            </div>
            {password && (
              <div className="mt-1.5 flex items-center gap-2">
                <div className="flex-1 h-1.5 bg-slate-100 rounded overflow-hidden">
                  <div
                    className={`h-full ${pwScore.tone}`}
                    style={{ width: `${(pwScore.score / 5) * 100}%` }}
                  />
                </div>
                <span className="text-[10px] text-slate-500 w-16 text-right">{pwScore.label}</span>
              </div>
            )}
          </div>

          <div>
            <div className="text-xs text-slate-600 mb-1">Selling on</div>
            <div className="flex gap-3 text-xs text-slate-700">
              {[
                { key: "flipkart", label: "Flipkart" },
                { key: "amazon", label: "Amazon" },
              ].map((p) => (
                <label key={p.key} className="flex items-center gap-1.5 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={platforms.includes(p.key)}
                    onChange={() => togglePlatform(p.key)}
                  />
                  {p.label}
                </label>
              ))}
            </div>
          </div>

          <div>
            <div className="text-xs text-slate-600 mb-1">Monthly revenue</div>
            <select
              value={revenue}
              onChange={(e) => setRevenue(e.target.value)}
              className="w-full border border-slate-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-brand-green"
            >
              <option value="">Select range…</option>
              {REVENUE_OPTIONS.map((r) => (
                <option key={r} value={r}>{r}</option>
              ))}
            </select>
          </div>

          {error && (
            <p className="text-xs text-red-600 bg-red-50 border border-red-100 rounded px-2 py-1.5">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={busy}
            className="w-full bg-brand-green hover:bg-emerald-700 text-white font-medium py-2.5 rounded-lg transition disabled:opacity-60"
          >
            {busy ? "Creating account…" : "Create account"}
          </button>
        </form>

        <p className="text-xs text-center text-slate-500 mt-4">
          Already have an account?{" "}
          <Link to="/login" className="text-brand-green font-medium hover:underline">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
