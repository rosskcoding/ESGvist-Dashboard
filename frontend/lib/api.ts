import { clearSupportModeForLogout } from "./support-mode";

const API_BASE = "/api";
const CSRF_COOKIE_KEY = "csrf_token";
const CSRF_HEADER_NAME = "X-CSRF-Token";
const FRONTEND_ORIGIN_HEADER_NAME = "X-Frontend-Origin";
const LEGACY_AUTH_STORAGE_KEYS = ["access_token", "refresh_token"] as const;
const CSRF_COOKIE_WAIT_TIMEOUT_MS = 1200;
const CSRF_COOKIE_POLL_INTERVAL_MS = 50;
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

async function waitForCookieValue(
  key: string,
  timeoutMs = CSRF_COOKIE_WAIT_TIMEOUT_MS,
): Promise<string | null> {
  const initial = getCookieValue(key);
  if (initial || typeof window === "undefined") {
    return initial;
  }

  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    await new Promise((resolve) => window.setTimeout(resolve, CSRF_COOKIE_POLL_INTERVAL_MS));
    const value = getCookieValue(key);
    if (value) {
      return value;
    }
  }

  return null;
}

function removeStorageValue(key: string): void {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(key);
}

export function clearLegacyAuthStorage(): void {
  for (const key of LEGACY_AUTH_STORAGE_KEYS) {
    removeStorageValue(key);
  }
}

function emitWindowEvent(name: string, detail?: Record<string, unknown>) {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent(name, { detail }));
}

function currentBrowserPath(): string | undefined {
  if (typeof window === "undefined") return undefined;
  return `${window.location.pathname}${window.location.search}${window.location.hash}`;
}

function currentBrowserOrigin(): string | undefined {
  if (typeof window === "undefined") return undefined;
  return window.location.origin;
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
  clearLegacyAuthStorage();
  clearSupportModeForLogout();
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

function shouldWaitForCsrfCookie(path: string, method?: string): boolean {
  if (!requiresCsrfHeader(method)) return false;
  return path !== "/auth/login" && path !== "/auth/register";
}

function isJsonContentType(response: Response): boolean {
  return response.headers.get("content-type")?.includes("application/json") ?? false;
}

function parseContentDispositionFileName(header: string | null): string | null {
  if (!header) return null;

  const utf8Match = header.match(/filename\*=UTF-8''([^;]+)/i);
  if (utf8Match?.[1]) {
    try {
      return decodeURIComponent(utf8Match[1]);
    } catch {
      return utf8Match[1];
    }
  }

  const asciiMatch = header.match(/filename="([^"]+)"/i) ?? header.match(/filename=([^;]+)/i);
  if (!asciiMatch?.[1]) return null;
  return asciiMatch[1].trim().replace(/^"(.*)"$/, "$1");
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
    const csrfToken = await waitForCookieValue(CSRF_COOKIE_KEY, 300);
    const browserOrigin = currentBrowserOrigin();
    if (csrfToken) {
      headers[CSRF_HEADER_NAME] = csrfToken;
    }
    if (browserOrigin) {
      headers[FRONTEND_ORIGIN_HEADER_NAME] = browserOrigin;
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

  private async buildHeaders(
    path: string,
    headers?: HeadersInit,
    options: AuthHeaderOptions = {},
  ): Promise<Record<string, string>> {
    const merged = mergeHeaders(headers);
    const csrfToken = requiresCsrfHeader(options.method)
      ? shouldWaitForCsrfCookie(path, options.method)
        ? await waitForCookieValue(CSRF_COOKIE_KEY)
        : getCookieValue(CSRF_COOKIE_KEY)
      : null;

    if (options.contentType && !merged["Content-Type"]) {
      merged["Content-Type"] = options.contentType;
    }
    if (csrfToken && !merged[CSRF_HEADER_NAME]) {
      merged[CSRF_HEADER_NAME] = csrfToken;
    }
    if (requiresCsrfHeader(options.method) && !merged[FRONTEND_ORIGIN_HEADER_NAME]) {
      const browserOrigin = currentBrowserOrigin();
      if (browserOrigin) {
        merged[FRONTEND_ORIGIN_HEADER_NAME] = browserOrigin;
      }
    }

    return merged;
  }

  private async execute(
    path: string,
    options: RequestInit,
    headerOptions: AuthHeaderOptions,
  ): Promise<Response> {
    const headers = await this.buildHeaders(path, options.headers, {
      ...headerOptions,
      method: options.method,
    });

    return fetch(`${API_BASE}${path}`, {
      ...options,
      credentials: "same-origin",
      headers,
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
      const csrfToken = await waitForCookieValue(CSRF_COOKIE_KEY, 300);
      const browserOrigin = currentBrowserOrigin();
      const response = await fetch(`${API_BASE}/auth/refresh`, {
        method: "POST",
        credentials: "same-origin",
        headers: (() => {
          const headers: Record<string, string> = {};
          if (csrfToken) {
            headers[CSRF_HEADER_NAME] = csrfToken;
          }
          if (browserOrigin) {
            headers[FRONTEND_ORIGIN_HEADER_NAME] = browserOrigin;
          }
          return Object.keys(headers).length > 0 ? headers : undefined;
        })(),
      });

      if (!response.ok) {
        return false;
      }

      clearLegacyAuthStorage();
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

  async download(path: string): Promise<{ blob: Blob; fileName: string | null; mimeType: string | null }> {
    const response = await this.fetchWithAuth(path);
    if (!response.ok) {
      throw await this.parseErrorResponse(response);
    }

    return {
      blob: await response.blob(),
      fileName: parseContentDispositionFileName(response.headers.get("content-disposition")),
      mimeType: response.headers.get("content-type"),
    };
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
