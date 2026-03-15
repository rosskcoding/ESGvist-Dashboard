"""
Double-submit cookie CSRF protection middleware.

Enterprise-grade CSRF protection for B2B applications.
Works with httpOnly refresh tokens and SameSite=Lax cookies.

Security model:
- CSRF token stored in non-httpOnly cookie (readable by JS)
- Client sends token in X-CSRF-Token header
- Server validates: cookie.csrf_token == header.X-CSRF-Token
- Protects all mutating requests (POST, PUT, PATCH, DELETE)
"""

import secrets
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from app.config import settings


# Constants
CSRF_COOKIE_NAME = "csrf_token"
CSRF_HEADER_NAME = "X-CSRF-Token"
CSRF_TOKEN_LENGTH = 32  # 256 bits of entropy
CSRF_TOKEN_MAX_AGE = settings.refresh_token_expire_days * 24 * 60 * 60  # seconds

# Methods that require CSRF validation
MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

# Paths excluded from CSRF check (public/auth endpoints and API-only paths with JWT)
CSRF_EXEMPT_PATHS = frozenset({
    "/api/v1/auth/login",
    "/api/v1/auth/logout",
    "/health",
    "/health/ready",
    "/health/live",
    "/docs",
    "/redoc",
    "/openapi.json",
})

# Path prefixes that are JWT-protected and don't need CSRF
# (for programmatic API access without browser cookies)
CSRF_EXEMPT_API_PREFIXES = (
    "/api/v1/assets/",  # Asset upload/management - JWT protected
)

# Path prefixes excluded from CSRF check
CSRF_EXEMPT_PREFIXES = (
    "/health",
)


def generate_csrf_token() -> str:
    """
    Generate cryptographically secure CSRF token.

    Uses secrets.token_urlsafe for URL-safe base64 encoding.
    32 bytes = 256 bits of entropy (enterprise-grade).
    """
    return secrets.token_urlsafe(CSRF_TOKEN_LENGTH)


def get_csrf_cookie_settings() -> dict:
    """
    Get CSRF cookie settings.

    Note: httpOnly=False so JavaScript can read the token.
    This is intentional for double-submit cookie pattern.
    """
    is_production = settings.environment == "production"

    return {
        "key": CSRF_COOKIE_NAME,
        "httponly": False,  # JS must read this cookie
        "samesite": "lax",  # Additional CSRF protection layer
        "secure": is_production,  # HTTPS only in production
        "max_age": CSRF_TOKEN_MAX_AGE,
        "path": "/",  # Available to all paths
    }


def set_csrf_cookie(response: Response, token: str) -> None:
    """Set CSRF token cookie on response."""
    cookie_settings = get_csrf_cookie_settings()
    response.set_cookie(value=token, **cookie_settings)


def delete_csrf_cookie(response: Response) -> None:
    """Delete CSRF cookie (e.g., on logout)."""
    response.delete_cookie(CSRF_COOKIE_NAME, path="/")


class CSRFMiddleware(BaseHTTPMiddleware):
    """
    Double-submit cookie CSRF protection middleware.

    For all mutating requests (POST, PUT, PATCH, DELETE):
    1. Reads csrf_token from cookie
    2. Reads X-CSRF-Token from header
    3. Validates they match
    4. Returns 403 if validation fails

    Excludes:
    - Auth endpoints (login, logout, refresh)
    - Health check endpoints
    - Read-only methods (GET, HEAD, OPTIONS)
    """

    async def dispatch(
        self, request: Request, call_next: Callable
    ) -> Response:
        # Skip CSRF check for non-mutating methods
        if request.method not in MUTATING_METHODS:
            return await call_next(request)

        # Skip CSRF check for exempt paths
        path = request.url.path
        if path in CSRF_EXEMPT_PATHS:
            return await call_next(request)

        # Skip CSRF check for exempt path prefixes
        if any(path.startswith(prefix) for prefix in CSRF_EXEMPT_PREFIXES):
            return await call_next(request)

        # Skip CSRF check for JWT-protected API endpoints (no browser cookies)
        if any(path.startswith(prefix) for prefix in CSRF_EXEMPT_API_PREFIXES):
            return await call_next(request)

        # If the request is authenticated via an explicit Bearer token, CSRF protection
        # is not needed: browsers do not attach Authorization headers cross-site by default,
        # and CSRF relies on ambient credentials (cookies).
        auth_header = request.headers.get("Authorization") or ""
        if auth_header.lower().startswith("bearer "):
            return await call_next(request)

        # Get CSRF token from cookie
        cookie_token = request.cookies.get(CSRF_COOKIE_NAME)

        # Get CSRF token from header
        header_token = request.headers.get(CSRF_HEADER_NAME)

        # Validate CSRF token
        if not cookie_token or not header_token:
            return JSONResponse(
                status_code=403,
                content={
                    "detail": "CSRF validation failed",
                    "code": "CSRF_MISSING",
                },
            )

        # Constant-time comparison to prevent timing attacks
        if not secrets.compare_digest(cookie_token, header_token):
            return JSONResponse(
                status_code=403,
                content={
                    "detail": "CSRF validation failed",
                    "code": "CSRF_MISMATCH",
                },
            )

        # CSRF validation passed
        return await call_next(request)

