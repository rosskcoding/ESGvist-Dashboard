/**
 * API Client for ESGvist Platform
 *
 * Handles authentication, error handling, and request/response interceptors.
 * 
 * Security features:
 * - Access tokens in Authorization header
 * - Refresh tokens in httpOnly cookies (XSS protection)
 * - Double-submit cookie CSRF protection
 * - Automatic token refresh with retry
 */

import { useAuthStore } from '@/stores/authStore'

const API_BASE_URL = import.meta.env.VITE_API_URL || ''

// CSRF constants
const CSRF_COOKIE_NAME = 'csrf_token'
const CSRF_HEADER_NAME = 'X-CSRF-Token'

// HTTP methods that require CSRF token
const MUTATING_METHODS = new Set(['POST', 'PUT', 'PATCH', 'DELETE'])

/**
 * Read CSRF token from cookie.
 * Used for double-submit cookie CSRF protection.
 */
function getCsrfToken(): string | null {
  if (typeof document === 'undefined') return null
  
  const cookies = document.cookie.split(';')
  for (const cookie of cookies) {
    const [name, value] = cookie.trim().split('=')
    if (name === CSRF_COOKIE_NAME) {
      return decodeURIComponent(value)
    }
  }
  return null
}

interface RequestOptions extends RequestInit {
  params?: Record<
    string,
    string | number | boolean | Array<string | number | boolean> | null | undefined
  >
  responseType?: 'json' | 'blob'
}

export interface ApiError {
  message: string
  code?: string
  details?: unknown
}

/**
 * HTTP Error class for API responses with error status codes.
 * Used for handling specific HTTP errors like 409 Conflict.
 */
export class ApiHttpError extends Error {
  status: number
  code?: string
  details?: unknown

  constructor(status: number, message: string, code?: string, details?: unknown) {
    super(message)
    this.name = 'ApiHttpError'
    this.status = status
    this.code = code
    this.details = details
  }
}

class ApiClient {
  private baseUrl: string
  private isRefreshing = false
  private refreshPromise: Promise<boolean> | null = null

  constructor(baseUrl: string) {
    this.baseUrl = baseUrl
  }

  /**
   * Attempt to refresh tokens using the refresh token cookie.
   * Returns true if successful, false otherwise.
   * 
   * Note: Refresh token is stored in httpOnly cookie by backend,
   * it will be automatically sent with credentials: 'include'
   */
  private async refreshTokens(): Promise<boolean> {
    // Prevent multiple simultaneous refresh attempts
    if (this.isRefreshing && this.refreshPromise) {
      return this.refreshPromise
    }

    this.isRefreshing = true
    this.refreshPromise = (async () => {
      try {
        const url = new URL('/api/v1/auth/refresh', this.baseUrl || window.location.origin)
        const csrfToken = getCsrfToken()
        const response = await fetch(url.toString(), {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(csrfToken ? { [CSRF_HEADER_NAME]: csrfToken } : {}),
          },
          credentials: 'include', // Important: send httpOnly cookie
          body: JSON.stringify({}), // Empty body - token is in cookie
        })

        if (!response.ok) {
          return false
        }

        const data = await response.json()
        // Only access_token is returned in body
        // Refresh token is set as httpOnly cookie by backend
        useAuthStore.getState().setAccessToken(data.access_token)
        return true
      } catch {
        return false
      } finally {
        this.isRefreshing = false
        this.refreshPromise = null
      }
    })()

    return this.refreshPromise
  }

  private buildHeaders(method: string, extra?: HeadersInit): Headers {
    const headers = new Headers()

    const apply = (src?: HeadersInit) => {
      if (!src) return
      if (src instanceof Headers) {
        src.forEach((v, k) => headers.set(k, v))
        return
      }
      if (Array.isArray(src)) {
        src.forEach(([k, v]) => headers.set(k, v))
        return
      }
      Object.entries(src).forEach(([k, v]) => headers.set(k, v))
    }

    apply(this.getAuthHeaders())
    apply(this.getCsrfHeaders(method))  // Add CSRF header for mutating requests
    apply(extra)
    return headers
  }

  private getAuthHeaders(): HeadersInit {
    const token = useAuthStore.getState().accessToken
    return token
      ? { Authorization: `Bearer ${token}` }
      : {}
  }

  /**
   * Get CSRF header for mutating requests.
   * Reads token from cookie (set by server on login).
   */
  private getCsrfHeaders(method: string): HeadersInit {
    if (!MUTATING_METHODS.has(method)) {
      return {}
    }
    
    const csrfToken = getCsrfToken()
    return csrfToken
      ? { [CSRF_HEADER_NAME]: csrfToken }
      : {}
  }

  private async request<T>(
    method: string,
    path: string,
    options: RequestOptions = {},
    isRetry = false
  ): Promise<{ data: T; status: number; headers: Record<string, string> }> {
    const { params, body, headers: optionHeaders, ...rest } = options

    // Build URL with query params
    const url = new URL(path, this.baseUrl || window.location.origin)
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value === undefined || value === null) return

        if (Array.isArray(value)) {
          for (const item of value) {
            url.searchParams.append(key, String(item))
          }
          return
        }

        url.searchParams.append(key, String(value))
      })
    }

    const requestHeaders = this.buildHeaders(method, optionHeaders)

    // Prepare body / content-type
    let requestBody: BodyInit | undefined = undefined
    const hasBody = body !== undefined && body !== null

    if (hasBody) {
      // FormData (multipart) must NOT set Content-Type manually (browser will set boundary)
      if (typeof FormData !== 'undefined' && body instanceof FormData) {
        requestHeaders.delete('Content-Type')
        requestBody = body
      } else if (
        typeof body === 'string' ||
        body instanceof Blob ||
        body instanceof ArrayBuffer ||
        body instanceof URLSearchParams
      ) {
        requestBody = body as BodyInit
      } else {
        // Default to JSON
        if (!requestHeaders.has('Content-Type')) {
          requestHeaders.set('Content-Type', 'application/json')
        }
        requestBody = JSON.stringify(body)
      }
    }

    // Include credentials for:
    // - auth endpoints (httpOnly refresh cookie)
    // - all mutating requests (CSRF double-submit cookie requires csrf_token cookie)
    const isAuthEndpoint = path.includes('/api/v1/auth/')
    const isMutating = MUTATING_METHODS.has(method)
    const needsCookies = isAuthEndpoint || isMutating
    
    const response = await fetch(url.toString(), {
      method,
      headers: requestHeaders,
      body: requestBody,
      credentials: needsCookies ? 'include' : 'same-origin',
      ...rest,
    })

    // Handle 401 - Unauthorized: try to refresh token
    if (response.status === 401 && !isRetry) {
      // Don't try to refresh on login/refresh endpoints
      const isLoginOrRefresh = path.includes('/auth/login') || path.includes('/auth/refresh')
      
      if (!isLoginOrRefresh) {
        const refreshed = await this.refreshTokens()
        if (refreshed) {
          // Retry the original request with new token
          return this.request<T>(method, path, options, true)
        }
      }
      
      // Refresh failed or not applicable - logout and redirect to login
      // Preserve current URL for redirect back after re-login
      useAuthStore.getState().logout()
      const currentPath = window.location.pathname + window.location.search
      const redirectParam = currentPath && currentPath !== '/' && currentPath !== '/login'
        ? `?redirect=${encodeURIComponent(currentPath)}`
        : ''
      window.location.href = `/login${redirectParam}`
      throw new Error('Unauthorized')
    }

    // Handle errors
    if (!response.ok) {
      const payload: unknown = await response.json().catch(() => null)

      // Try to normalize FastAPI / generic error formats
      let message = `HTTP ${response.status}`
      if (payload && typeof payload === 'object') {
        const obj = payload as Record<string, unknown>

        const msg = obj.message
        if (typeof msg === 'string' && msg.trim()) {
          message = msg
        } else {
          const detail = obj.detail
          if (typeof detail === 'string' && detail.trim()) {
            message = detail
          } else if (Array.isArray(detail)) {
            // FastAPI validation errors: { detail: [{ msg, ...}, ...] }
            const extractMsg = (d: unknown): string | null => {
              if (!d || typeof d !== 'object') return null
              const maybeMsg = (d as Record<string, unknown>).msg
              return typeof maybeMsg === 'string' && maybeMsg.trim() ? maybeMsg : null
            }
            const msgs = detail.map(extractMsg).filter((x): x is string => Boolean(x))
            if (msgs.length) message = msgs.join('; ')
          }
        }
      }

      throw new ApiHttpError(response.status, message)
    }

    // Parse response
    const { responseType } = options
    let data: T
    if (response.status === 204) {
      data = null as T
    } else if (responseType === 'blob') {
      data = await response.blob() as T
    } else {
      data = await response.json()
    }
    
    // Build headers object from response
    const responseHeaders: Record<string, string> = {}
    response.headers.forEach((value, key) => {
      responseHeaders[key] = value
    })
    
    return { data, status: response.status, headers: responseHeaders }
  }

  get<T>(path: string, options?: RequestOptions) {
    return this.request<T>('GET', path, options)
  }

  post<T>(path: string, body?: unknown, options?: RequestOptions) {
    return this.request<T>('POST', path, { ...options, body: body as BodyInit })
  }

  patch<T>(path: string, body?: unknown, options?: RequestOptions) {
    return this.request<T>('PATCH', path, { ...options, body: body as BodyInit })
  }

  put<T>(path: string, body?: unknown, options?: RequestOptions) {
    return this.request<T>('PUT', path, { ...options, body: body as BodyInit })
  }

  delete<T>(path: string, options?: RequestOptions) {
    return this.request<T>('DELETE', path, options)
  }
}

export const apiClient = new ApiClient(API_BASE_URL)
