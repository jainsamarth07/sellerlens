import { api } from "../lib/api";

export interface User {
  id: number;
  email: string;
  business_name: string | null;
  platform: string | null;
  monthly_revenue_range: string | null;
  auth_provider: "email" | "microsoft" | string;
  avatar_url: string | null;
  is_new_user?: boolean;
}

export interface SignupBody {
  email: string;
  password: string;
  business_name?: string;
  platform?: string;
  monthly_revenue_range?: string;
}

export interface AuthResponse {
  token: string;
  user: User;
}

export async function signup(body: SignupBody): Promise<AuthResponse> {
  const res = await api.post<AuthResponse>("/auth/signup", body);
  return res.data;
}

export async function login(email: string, password: string): Promise<AuthResponse> {
  const res = await api.post<AuthResponse>("/auth/login", { email, password });
  return res.data;
}

export async function fetchMe(): Promise<User> {
  const res = await api.get<User>("/auth/me");
  return res.data;
}

export async function microsoftAuthUrl(): Promise<string> {
  const res = await api.get<{ auth_url: string }>("/auth/microsoft/login");
  return res.data.auth_url;
}

export async function logoutApi(): Promise<void> {
  try {
    await api.post("/auth/logout");
  } catch {
    /* ignore */
  }
}
