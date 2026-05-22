/**
 * MSAL config for browser-side Microsoft SSO (optional convenience path).
 *
 * The primary login flow goes through the backend
 * (`GET /api/auth/microsoft/login` → server-rendered redirect URL → backend
 * `/microsoft/callback` → JWT in URL fragment). MSAL is only used here for
 * the helper button on the signup page that prefers a popup-free redirect.
 */

export const msalConfig = {
  auth: {
    clientId: (import.meta as any).env?.VITE_MICROSOFT_CLIENT_ID ?? "",
    authority: "https://login.microsoftonline.com/common",
    redirectUri:
      (import.meta as any).env?.VITE_REDIRECT_URI ??
      "http://localhost:5173/auth/callback",
  },
  cache: { cacheLocation: "localStorage" as const },
};

export const loginRequest = { scopes: ["User.Read"] };
