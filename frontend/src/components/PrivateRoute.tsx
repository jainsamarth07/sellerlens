import { useEffect } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuthStore } from "../store/useAuth";
import { useAppStore } from "../store/useAppStore";

export default function PrivateRoute({ children }: { children: React.ReactNode }) {
  const initialize = useAuthStore((s) => s.initialize);
  const initialized = useAuthStore((s) => s.initialized);
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const isLoading = useAuthStore((s) => s.isLoading);
  const user = useAuthStore((s) => s.user);
  const restoreFromServer = useAppStore((s) => s.restoreFromServer);
  const serverRestored = useAppStore((s) => s.serverRestored);
  const location = useLocation();

  useEffect(() => {
    if (!initialized) {
      initialize().catch(() => undefined);
    }
  }, [initialized, initialize]);

  useEffect(() => {
    if (isAuthenticated && !serverRestored) {
      restoreFromServer();
    }
  }, [isAuthenticated, serverRestored, restoreFromServer]);

  // Optimistic render: if we have a persisted token + user from a previous
  // session, show content immediately while /auth/me verifies in background.
  // On 401 the axios interceptor already redirects to /login.
  const hasPersistedAuth = isAuthenticated && user !== null;
  if (!initialized && hasPersistedAuth) {
    return <>{children}</>;
  }

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
