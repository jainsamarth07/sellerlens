import { useEffect } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuthStore } from "../store/useAuth";
import { useAppStore } from "../store/useAppStore";

/**
 * Wraps protected routes. Redirects to /login when no valid token exists.
 * Shows a tiny loader on first load while ``/auth/me`` is being checked.
 */
export default function PrivateRoute({ children }: { children: React.ReactNode }) {
  const initialize = useAuthStore((s) => s.initialize);
  const initialized = useAuthStore((s) => s.initialized);
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const isLoading = useAuthStore((s) => s.isLoading);
  const restoreFromServer = useAppStore((s) => s.restoreFromServer);
  const location = useLocation();

  useEffect(() => {
    if (!initialized) {
      initialize().catch(() => undefined);
    }
  }, [initialized, initialize]);

  useEffect(() => {
    if (isAuthenticated) {
      restoreFromServer();
    }
  }, [isAuthenticated, restoreFromServer]);

  if (!initialized || isLoading) {
    return (
      <div className="flex h-screen items-center justify-center text-slate-500 text-sm">
        Loading…
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location.pathname }} replace />;
  }

  return <>{children}</>;
}
