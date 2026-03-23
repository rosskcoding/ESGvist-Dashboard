import { api } from "./api";

interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

interface UserResponse {
  id: number;
  email: string;
  full_name: string;
  is_active: boolean;
  roles: Array<{
    id: number;
    role: string;
    scope_type: string;
    scope_id: number | null;
  }>;
}

export async function login(
  email: string,
  password: string
): Promise<TokenResponse> {
  const data = await api.post<TokenResponse>("/auth/login", {
    email,
    password,
  });
  localStorage.setItem("access_token", data.access_token);
  localStorage.setItem("refresh_token", data.refresh_token);
  return data;
}

export async function register(
  email: string,
  password: string,
  fullName: string
): Promise<UserResponse> {
  return api.post<UserResponse>("/auth/register", {
    email,
    password,
    full_name: fullName,
  });
}

export async function getMe(): Promise<UserResponse> {
  return api.get<UserResponse>("/auth/me");
}

export async function logout(): Promise<void> {
  try {
    await api.post("/auth/logout");
  } finally {
    localStorage.removeItem("access_token");
    localStorage.removeItem("refresh_token");
    localStorage.removeItem("organization_id");
  }
}

export function isAuthenticated(): boolean {
  if (typeof window === "undefined") return false;
  return !!localStorage.getItem("access_token");
}
