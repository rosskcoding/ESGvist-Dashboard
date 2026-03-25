import { api, clearLegacyAuthStorage } from "./api";
import { clearSupportModeForLogout } from "./support-mode";

interface TokenResponse {
  token_type: string;
}

export interface UserResponse {
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

export function clearClientAuthState(): void {
  if (typeof window === "undefined") return;
  clearSupportModeForLogout();
  clearLegacyAuthStorage();
}

function resolvePostLoginRoute(me: UserResponse) {
  const orgRole = me.roles.find((role) => role.scope_type === "organization" && role.scope_id);
  if (orgRole?.scope_id) {
    return "/dashboard";
  }
  if (me.roles.some((role) => role.role === "framework_admin")) {
    return "/platform/framework";
  }
  if (me.roles.some((role) => role.role === "platform_admin")) {
    return "/platform/tenants";
  }
  return "/onboarding";
}

export async function login(
  email: string,
  password: string
): Promise<{ next_route: string }> {
  await api.post<TokenResponse>("/auth/login", {
    email,
    password,
  });
  clearLegacyAuthStorage();

  // Auto-set organization_id from user's first org role
  let nextRoute = "/dashboard";
  try {
    const me = await api.get<UserResponse>("/auth/me");
    const orgRole = me.roles.find((r) => r.scope_type === "organization" && r.scope_id);
    if (orgRole?.scope_id) {
      await api.post("/auth/context/organization", {
        organization_id: orgRole.scope_id,
      });
    } else {
      await api.post("/auth/context/organization", {
        organization_id: null,
      });
    }
    nextRoute = resolvePostLoginRoute(me);
  } catch {
    // Ignore — org will be set later
  }

  return { next_route: nextRoute };
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
    clearClientAuthState();
  }
}

export async function logoutAll(): Promise<{ revoked_sessions: number }> {
  try {
    return await api.post<{ revoked_sessions: number }>("/auth/logout-all");
  } finally {
    clearClientAuthState();
  }
}
