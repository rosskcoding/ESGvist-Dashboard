const API_BASE = "/api";

interface ApiError {
  error: {
    code: string;
    message: string;
    details: Array<{ field?: string; reason: string }>;
    requestId: string;
  };
}

class ApiClient {
  private getToken(): string | null {
    if (typeof window === "undefined") return null;
    return localStorage.getItem("access_token");
  }

  private getOrgId(): string | null {
    if (typeof window === "undefined") return null;
    return localStorage.getItem("organization_id");
  }

  private async request<T>(
    path: string,
    options: RequestInit = {}
  ): Promise<T> {
    const token = this.getToken();
    const orgId = this.getOrgId();
    const isAuthFlowRequest =
      path === "/auth/login" ||
      path === "/auth/register" ||
      path.startsWith("/auth/2fa");

    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      ...(options.headers as Record<string, string>),
    };

    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }
    if (orgId) {
      headers["X-Organization-Id"] = orgId;
    }

    const response = await fetch(`${API_BASE}${path}`, {
      ...options,
      headers,
    });

    if (!response.ok) {
      let error: any;
      try {
        error = await response.json();
      } catch {
        throw new Error(`API error: ${response.status} ${response.statusText}`);
      }

      if (response.status === 401 && token && !isAuthFlowRequest) {
        // Try refresh
        const refreshed = await this.tryRefresh();
        if (refreshed) {
          // Retry original request with new token
          headers["Authorization"] = `Bearer ${this.getToken()}`;
          const retryResponse = await fetch(`${API_BASE}${path}`, {
            ...options,
            headers,
          });
          if (retryResponse.ok) {
            return retryResponse.json();
          }
        }
        // Refresh failed — redirect to login
        if (typeof window !== "undefined") {
          localStorage.removeItem("access_token");
          localStorage.removeItem("refresh_token");
          window.location.href = "/login";
        }
      }

      const msg = error?.error?.message
        || (typeof error?.detail === "string" ? error.detail : null)
        || (Array.isArray(error?.detail) ? error.detail.map((d: { msg?: string }) => d.msg).join(", ") : null)
        || `API error: ${response.status}`;
      const err = new Error(msg);
      (err as Error & { code?: string }).code = error?.error?.code;
      throw err;
    }

    if (response.status === 204) {
      return undefined as T;
    }

    return response.json();
  }

  private async tryRefresh(): Promise<boolean> {
    const refreshToken = localStorage.getItem("refresh_token");
    if (!refreshToken) return false;

    try {
      const response = await fetch(`${API_BASE}/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });

      if (!response.ok) return false;

      const data = await response.json();
      localStorage.setItem("access_token", data.access_token);
      localStorage.setItem("refresh_token", data.refresh_token);
      return true;
    } catch {
      return false;
    }
  }

  async get<T>(path: string): Promise<T> {
    return this.request<T>(path);
  }

  async post<T>(path: string, body?: unknown): Promise<T> {
    return this.request<T>(path, {
      method: "POST",
      body: body ? JSON.stringify(body) : undefined,
    });
  }

  async put<T>(path: string, body?: unknown): Promise<T> {
    return this.request<T>(path, {
      method: "PUT",
      body: body ? JSON.stringify(body) : undefined,
    });
  }

  async patch<T>(path: string, body?: unknown): Promise<T> {
    return this.request<T>(path, {
      method: "PATCH",
      body: body ? JSON.stringify(body) : undefined,
    });
  }

  async delete<T>(path: string): Promise<T> {
    return this.request<T>(path, { method: "DELETE" });
  }
}

export const api = new ApiClient();
