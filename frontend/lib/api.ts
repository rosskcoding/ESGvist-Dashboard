const API_BASE = "/api";
const CSRF_COOKIE_KEY = "csrf_token";
const CSRF_HEADER_NAME = "X-CSRF-Token";
const LEGACY_ACCESS_TOKEN_KEY = "access_token";
const LEGACY_REFRESH_TOKEN_KEY = "refresh_token";
const ORGANIZATION_ID_KEY = "organization_id";
const SUPPORT_TENANT_ID_KEY = "support_tenant_id";
const SUPPORT_TENANT_NAME_KEY = "support_tenant_name";
export const API_ERROR_EVENT = "app-api-error";
export const AUTH_EXPIRED_EVENT = "app-auth-expired";

type ClientRuntimeEvent = {
  event_type: "api_error" | "auth_expired" | "ui_error" | "unhandled_rejection";
  level: "info" | "warning" | "error";
  message: string;
  path?: string;
  status?: number;
  code?: string;
  request_id?: string;
  details?: Record<string, string | number | boolean | null>;
};

export type ApiErrorDetail = {
  field?: string;
  reason: string;
};

type ApiErrorPayload = {
  error?: {
    code?: string;
    message?: string;
    details?: ApiErrorDetail[];
    requestId?: string;
  };
  detail?: string | Array<{ msg?: string }>;
};

type AuthHeaderOptions = {
  contentType?: string | null;
  method?: string;
};

export class AppApiError extends Error {
  readonly status: number;
  readonly code?: string;
  readonly details: ApiErrorDetail[];
  readonly requestId?: string;
  readonly raw?: unknown;

  constructor({
    status,
    message,
    code,
    details = [],
    requestId,
    raw,
  }: {
    status: number;
    message: string;
    code?: string;
    details?: ApiErrorDetail[];
    requestId?: string;
    raw?: unknown;
  }) {
    super(message);
    this.name = "AppApiError";
    this.status = status;
    this.code = code;
    this.details = details;
    this.requestId = requestId;
    this.raw = raw;
  }
}

export function isAppApiError(error: unknown): error is AppApiError {
  return error instanceof AppApiError;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function getCookieValue(key: string): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie
    .split("; ")
    .find((entry) => entry.startsWith(`${key}=`));
  if (!match) return null;
  return decodeURIComponent(match.slice(key.length + 1));
}

function removeStorageValue(key: string): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(key);
}

function emitWindowEvent(name: string, detail?: Record<string, unknown>) {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent(name, { detail }));
}

function currentBrowserPath(): string | undefined {
  if (typeof window === "undefined") return undefined;
  return `${window.location.pathname}${window.location.search}${window.location.hash}`;
}

function resolveLoginRedirectUrl(reason: "session-expired" | "auth-required"): string {
  if (typeof window === "undefined") {
    return "/login";
  }

  const currentPath = currentBrowserPath();
  const params = new URLSearchParams({ reason });
  if (
    currentPath &&
    !window.location.pathname.startsWith("/login") &&
    !window.location.pathname.startsWith("/register")
  ) {
    params.set("next", currentPath);
  }
  return `/login?${params.toString()}`;
}

function clearStoredSession(reason: "session-expired" | "auth-required" = "session-expired") {
  removeStorageValue(LEGACY_ACCESS_TOKEN_KEY);
  removeStorageValue(LEGACY_REFRESH_TOKEN_KEY);
  removeStorageValue(ORGANIZATION_ID_KEY);
  removeStorageValue(SUPPORT_TENANT_ID_KEY);
  removeStorageValue(SUPPORT_TENANT_NAME_KEY);
  emitWindowEvent(AUTH_EXPIRED_EVENT, {
    reason,
    redirectTo: resolveLoginRedirectUrl(reason),
  });
}

function normalizeErrorDetails(value: unknown): ApiErrorDetail[] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((item) => {
    if (!isRecord(item)) return [];
    const reason = typeof item.reason === "string" ? item.reason : null;
    const field = typeof item.field === "string" ? item.field : undefined;
    return reason ? [{ field, reason }] : [];
  });
}

function parseApiErrorPayload(payload: unknown, status: number): AppApiError {
  const fallbackMessage = `API error: ${status}`;
  if (!isRecord(payload)) {
    return new AppApiError({ status, message: fallbackMessage, raw: payload });
  }

  const errorBlock = isRecord(payload.error) ? payload.error : undefined;
  const detail = payload.detail;
  const details = normalizeErrorDetails(errorBlock?.details);
  const validationMessage = Array.isArray(detail)
    ? detail
        .map((item) => (isRecord(item) && typeof item.msg === "string" ? item.msg : null))
        .filter((item): item is string => Boolean(item))
        .join(", ")
    : null;

  return new AppApiError({
    status,
    message:
      (typeof errorBlock?.message === "string" && errorBlock.message) ||
      (typeof detail === "string" && detail) ||
      validationMessage ||
      fallbackMessage,
    code: typeof errorBlock?.code === "string" ? errorBlock.code : undefined,
    details,
    requestId: typeof errorBlock?.requestId === "string" ? errorBlock.requestId : undefined,
    raw: payload,
  });
}

function mergeHeaders(headers?: HeadersInit): Record<string, string> {
  const merged: Record<string, string> = {};
  if (!headers) return merged;
  const normalized = new Headers(headers);
  normalized.forEach((value, key) => {
    merged[key] = value;
  });
  return merged;
}

function requiresCsrfHeader(method?: string): boolean {
  const normalized = (method || "GET").toUpperCase();
  return !["GET", "HEAD", "OPTIONS", "TRACE"].includes(normalized);
}

function isJsonContentType(response: Response): boolean {
  return response.headers.get("content-type")?.includes("application/json") ?? false;
}

async function parseSuccessBody<T>(response: Response): Promise<T> {
  if (response.status === 204) {
    return undefined as T;
  }

  if (!isJsonContentType(response)) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

export async function reportClientRuntimeEvent(event: ClientRuntimeEvent): Promise<void> {
  if (typeof window === "undefined") return;

  try {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
    };
    const csrfToken = getCookieValue(CSRF_COOKIE_KEY);
    if (csrfToken) {
      headers[CSRF_HEADER_NAME] = csrfToken;
    }

    await fetch(`${API_BASE}/runtime/client-events`, {
      method: "POST",
      credentials: "same-origin",
      headers,
      body: JSON.stringify({
        ...event,
        path: event.path ?? currentBrowserPath(),
        user_agent: typeof navigator !== "undefined" ? navigator.userAgent : undefined,
      }),
      keepalive: true,
    });
  } catch {
    // Telemetry must never break the UI path.
  }
}

export function withQuery(path: string, params: Record<string, string | number | null | undefined>) {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === null || value === undefined || value === "") continue;
    query.set(key, String(value));
  }
  const queryString = query.toString();
  return queryString ? `${path}?${queryString}` : path;
}

class ApiClient {
  private isAuthFlowRequest(path: string): boolean {
    return (
      path === "/auth/login" ||
      path === "/auth/register" ||
      path === "/auth/refresh" ||
      path.startsWith("/auth/2fa")
    );
  }

  private buildHeaders(headers?: HeadersInit, options: AuthHeaderOptions = {}): Record<string, string> {
    const merged = mergeHeaders(headers);
    const csrfToken = requiresCsrfHeader(options.method) ? getCookieValue(CSRF_COOKIE_KEY) : null;

    if (options.contentType && !merged["Content-Type"]) {
      merged["Content-Type"] = options.contentType;
    }
    if (csrfToken && !merged[CSRF_HEADER_NAME]) {
      merged[CSRF_HEADER_NAME] = csrfToken;
    }

    return merged;
  }

  private async execute(
    path: string,
    options: RequestInit,
    headerOptions: AuthHeaderOptions,
  ): Promise<Response> {
    return fetch(`${API_BASE}${path}`, {
      ...options,
      credentials: "same-origin",
      headers: this.buildHeaders(options.headers, {
        ...headerOptions,
        method: options.method,
      }),
    });
  }

  private async parseErrorResponse(response: Response): Promise<AppApiError> {
    let payload: unknown;
    try {
      payload = isJsonContentType(response) ? ((await response.json()) as ApiErrorPayload) : await response.text();
    } catch {
      payload = undefined;
    }

    const error =
      typeof payload === "string"
        ? new AppApiError({
            status: response.status,
            message: payload || `API error: ${response.status} ${response.statusText}`,
            raw: payload,
          })
        : parseApiErrorPayload(payload, response.status);

    emitWindowEvent(API_ERROR_EVENT, {
      status: error.status,
      code: error.code,
      requestId: error.requestId,
      message: error.message,
    });
    void reportClientRuntimeEvent({
      event_type: "api_error",
      level: error.status >= 500 ? "error" : "warning",
      message: error.message,
      status: error.status,
      code: error.code,
      request_id: error.requestId,
      details:
        error.details.length > 0
          ? { detail_count: error.details.length }
          : undefined,
    });
    return error;
  }

  private async fetchWithAuth(
    path: string,
    options: RequestInit = {},
    headerOptions: AuthHeaderOptions = {},
  ): Promise<Response> {
    const authFlow = this.isAuthFlowRequest(path);

    let response = await this.execute(path, options, headerOptions);
    if (response.status !== 401 || authFlow) {
      return response;
    }

    const refreshed = await this.tryRefresh();
    if (refreshed) {
      response = await this.execute(path, options, headerOptions);
      if (response.status !== 401) {
        return response;
      }
    }

    void reportClientRuntimeEvent({
      event_type: "auth_expired",
      level: "warning",
      message: "Session expired after refresh attempt failed",
      status: 401,
      details: {
        request_path: path,
      },
    });
    clearStoredSession("session-expired");
    if (
      typeof window !== "undefined" &&
      !window.location.pathname.startsWith("/login") &&
      !window.location.pathname.startsWith("/register")
    ) {
      window.location.href = resolveLoginRedirectUrl("session-expired");
    }
    return response;
  }

  private async request<T>(
    path: string,
    options: RequestInit = {},
    headerOptions: AuthHeaderOptions = {},
  ): Promise<T> {
    const response = await this.fetchWithAuth(path, options, headerOptions);
    if (!response.ok) {
      throw await this.parseErrorResponse(response);
    }
    return parseSuccessBody<T>(response);
  }

  private async tryRefresh(): Promise<boolean> {
    try {
      const response = await fetch(`${API_BASE}/auth/refresh`, {
        method: "POST",
        credentials: "same-origin",
        headers: (() => {
          const csrfToken = getCookieValue(CSRF_COOKIE_KEY);
          return csrfToken ? { [CSRF_HEADER_NAME]: csrfToken } : undefined;
        })(),
      });

      if (!response.ok) {
        return false;
      }

      removeStorageValue(LEGACY_ACCESS_TOKEN_KEY);
      removeStorageValue(LEGACY_REFRESH_TOKEN_KEY);
      return true;
    } catch {
      return false;
    }
  }

  async get<T>(path: string): Promise<T> {
    return this.request<T>(path);
  }

  async post<T>(path: string, body?: unknown): Promise<T> {
    return this.request<T>(
      path,
      {
        method: "POST",
        body: body ? JSON.stringify(body) : undefined,
      },
      { contentType: "application/json" },
    );
  }

  async put<T>(path: string, body?: unknown): Promise<T> {
    return this.request<T>(
      path,
      {
        method: "PUT",
        body: body ? JSON.stringify(body) : undefined,
      },
      { contentType: "application/json" },
    );
  }

  async patch<T>(path: string, body?: unknown): Promise<T> {
    return this.request<T>(
      path,
      {
        method: "PATCH",
        body: body ? JSON.stringify(body) : undefined,
      },
      { contentType: "application/json" },
    );
  }

  async delete<T>(path: string): Promise<T> {
    return this.request<T>(path, { method: "DELETE" });
  }

  async upload<T>(path: string, formData: FormData): Promise<T> {
    return this.request<T>(
      path,
      {
        method: "POST",
        body: formData,
      },
      { contentType: null },
    );
  }

  async stream(path: string, body: unknown, options: Pick<RequestInit, "signal"> = {}): Promise<Response> {
    const response = await this.fetchWithAuth(
      path,
      {
        method: "POST",
        body: JSON.stringify(body),
        signal: options.signal,
      },
      { contentType: "application/json" },
    );

    if (!response.ok) {
      throw await this.parseErrorResponse(response);
    }

    return response;
  }
}

export const api = new ApiClient();
