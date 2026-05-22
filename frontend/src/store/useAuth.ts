import { create } from "zustand";
import { persist } from "zustand/middleware";
import { fetchMe, login as loginApi, logoutApi, signup as signupApi, type SignupBody, type User } from "../lib/authApi";

export const TOKEN_KEY = "sellerlens_token";

interface AuthState {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  /** Set true after the first /auth/me check (avoids login-flash on reload). */
  initialized: boolean;

  initialize: () => Promise<void>;
  loginEmail: (email: string, password: string) => Promise<User>;
  signupEmail: (body: SignupBody) => Promise<User>;
  setTokenFromCallback: (token: string) => Promise<User | null>;
  logout: () => Promise<void>;
}

function readToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

function writeToken(token: string | null): void {
  try {
    if (token === null) {
      localStorage.removeItem(TOKEN_KEY);
    } else {
      localStorage.setItem(TOKEN_KEY, token);
    }
  } catch {
    /* ignore */
  }
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      token: readToken(),
      isLoading: false,
      isAuthenticated: !!readToken(),
      initialized: false,

      initialize: async () => {
        if (get().initialized) return;
        const tok = readToken();
        if (!tok) {
          set({ initialized: true, isAuthenticated: false, user: null });
          return;
        }
        set({ isLoading: true, token: tok });
        try {
          const me = await fetchMe();
          set({
            user: me,
            isAuthenticated: true,
            isLoading: false,
            initialized: true,
          });
        } catch {
          writeToken(null);
          set({
            token: null,
            user: null,
            isAuthenticated: false,
            isLoading: false,
            initialized: true,
          });
        }
      },

      loginEmail: async (email, password) => {
        const res = await loginApi(email, password);
        writeToken(res.token);
        set({
          token: res.token,
          user: res.user,
          isAuthenticated: true,
          initialized: true,
        });
        return res.user;
      },

      signupEmail: async (body) => {
        const res = await signupApi(body);
        writeToken(res.token);
        set({
          token: res.token,
          user: res.user,
          isAuthenticated: true,
          initialized: true,
        });
        return res.user;
      },

      setTokenFromCallback: async (token) => {
        writeToken(token);
        set({ token, isAuthenticated: true, isLoading: true });
        try {
          const me = await fetchMe();
          set({ user: me, isLoading: false, initialized: true });
          return me;
        } catch {
          writeToken(null);
          set({
            token: null,
            user: null,
            isAuthenticated: false,
            isLoading: false,
            initialized: true,
          });
          return null;
        }
      },

      logout: async () => {
        await logoutApi();
        writeToken(null);
        set({
          token: null,
          user: null,
          isAuthenticated: false,
          initialized: true,
        });
        // Clear other global stores so the next user starts clean.
        try {
          localStorage.removeItem("sellerlens-store");
          localStorage.removeItem("sellerlens-chat-store");
        } catch {
          /* ignore */
        }
      },
    }),
    {
      name: "sellerlens-auth",
      partialize: (s) => ({ user: s.user, token: s.token, isAuthenticated: s.isAuthenticated }),
    },
  ),
);
