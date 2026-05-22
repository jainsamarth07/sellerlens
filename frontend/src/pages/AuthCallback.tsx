import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Loader2 } from "lucide-react";
import { useAuthStore } from "../store/useAuth";

/**
 * Handles the redirect-back from the backend ``/api/auth/microsoft/callback``.
 *
 * The backend appends the JWT in the URL fragment so it never reaches any
 * proxy or server access log:
 *   /auth/callback#token=<jwt>&new=1
 */
export default function AuthCallback() {
  const navigate = useNavigate();
  const setTokenFromCallback = useAuthStore((s) => s.setTokenFromCallback);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const hash = window.location.hash.replace(/^#/, "");
    const params = new URLSearchParams(hash);
    const token = params.get("token");
    const isNew = params.get("new") === "1";

    if (!token) {
      setError("No token in callback URL. Please try again.");
      setTimeout(() => navigate("/login", { replace: true }), 1500);
      return;
    }

    setTokenFromCallback(token).then((user) => {
      // Wipe the hash so the token doesn't linger in history.
      try {
        window.history.replaceState(null, "", window.location.pathname);
      } catch {
        /* ignore */
      }
      if (!user) {
        setError("Sign-in failed. Please try again.");
        setTimeout(() => navigate("/login", { replace: true }), 1500);
        return;
      }
      if (isNew || user.is_new_user) {
        try {
          localStorage.removeItem("sellerlens_onboarded");
        } catch {
          /* ignore */
        }
      }
      navigate("/dashboard", { replace: true });
    });
  }, [navigate, setTokenFromCallback]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50">
      <div className="flex flex-col items-center gap-3 text-slate-600">
        <Loader2 size={28} className="animate-spin text-brand-green" />
        <p className="text-sm">
          {error ?? "Signing you in with Microsoft…"}
        </p>
      </div>
    </div>
  );
}
