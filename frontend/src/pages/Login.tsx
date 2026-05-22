import { useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { Eye, EyeOff, Loader2 } from "lucide-react";
import MicrosoftLogo from "../components/MicrosoftLogo";
import { useAuthStore } from "../store/useAuth";
import { microsoftAuthUrl } from "../lib/authApi";

export default function Login() {
  const loginEmail = useAuthStore((s) => s.loginEmail);
  const navigate = useNavigate();
  const location = useLocation() as { state?: { from?: string } };
  const after = location.state?.from || "/dashboard";

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [busy, setBusy] = useState(false);
  const [msBusy, setMsBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleMicrosoft = async () => {
    setError(null);
    setMsBusy(true);
    try {
      const url = await microsoftAuthUrl();
      window.location.href = url;
    } catch (e: any) {
      setError(e?.response?.data?.detail ?? "Microsoft login unavailable.");
      setMsBusy(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await loginEmail(email, password);
      navigate(after, { replace: true });
    } catch (err: any) {
      setError(err?.response?.data?.detail ?? "Sign in failed.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 px-4">
      <div className="w-full max-w-md bg-white rounded-2xl shadow-lg p-8">
        <div className="text-center mb-6">
          <h1 className="text-2xl font-bold text-slate-900">Welcome to SellerLens</h1>
          <p className="text-sm text-slate-500 mt-1">
            AI-powered profit analytics for Indian e-commerce sellers
          </p>
        </div>

        {/* Primary: Microsoft */}
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
          <span>Sign in with Microsoft</span>
        </button>

        <div className="flex items-center my-5">
          <div className="flex-1 h-px bg-slate-200" />
          <span className="px-3 text-xs uppercase tracking-wide text-slate-400">or</span>
          <div className="flex-1 h-px bg-slate-200" />
        </div>

        {/* Secondary: email/password */}
        <form onSubmit={handleSubmit} className="space-y-3">
          <input
            type="email"
            autoComplete="email"
            placeholder="you@business.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            className="w-full border border-slate-300 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand-green"
          />
          <div className="relative">
            <input
              type={show ? "text" : "password"}
              autoComplete="current-password"
              placeholder="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
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

          {error && (
            <p className="text-xs text-red-600 bg-red-50 border border-red-100 rounded px-2 py-1.5">
              {error}
            </p>
          )}

          <button
            type="submit"
            disabled={busy}
            className="w-full border border-slate-300 hover:border-brand-green hover:text-brand-green text-slate-700 font-medium py-2.5 rounded-lg transition disabled:opacity-60"
          >
            {busy ? "Signing in…" : "Sign in"}
          </button>
        </form>

        <p className="text-xs text-center text-slate-500 mt-4">
          Don&apos;t have an account?{" "}
          <Link to="/signup" className="text-brand-green font-medium hover:underline">
            Sign up
          </Link>
        </p>

        <p className="text-[11px] text-center text-slate-400 mt-5">
          Signing in with Microsoft is recommended for Microsoft Build AI participants
        </p>

        <p className="text-[10px] text-center text-slate-400 mt-6 pt-4 border-t border-slate-100">
          Built on Azure AI Foundry · Microsoft Entra ID · Azure OpenAI
        </p>
      </div>
    </div>
  );
}
